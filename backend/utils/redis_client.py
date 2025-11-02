
"""
Redis client for LangGraph checkpointer and query caching according to PRD.
Enhanced with comprehensive error handling, circuit breaker patterns, and graceful degradation.
"""
import redis
import json
import os
import hashlib
import time
import threading
import copy
from typing import Any, Optional, Dict, Tuple
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Circuit breaker for Redis operations
class RedisCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise redis.ConnectionError("Redis circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
            self._on_failure()
            raise e

    def _on_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = 'CLOSED'

    def _on_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'

redis_circuit_breaker = RedisCircuitBreaker()

# Retry configuration
MAX_RETRIES = 2
BASE_DELAY = 0.5

def retry_redis_operation(func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Retry Redis operations with exponential backoff"""
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(f"Redis operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Redis operation failed after {max_retries + 1} attempts: {e}")
                raise last_exception
        except Exception as e:
            # Don't retry for non-transient errors
            logger.error(f"Non-retryable Redis error: {e}")
            raise e

# Initialize Redis client with enhanced retry/backoff and circuit breaker
def create_redis_client():
    """Create Redis client with comprehensive error handling and resilience"""
    def _create_client():
        client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30  # Enable connection health checks
        )
        # Test connection with timeout
        client.ping()
        return client

    try:
        return retry_redis_operation(_create_client)
    except Exception as e:
        logger.error(f"Failed to create Redis client after retries: {e}")
        # Return a mock client for graceful degradation
        return None

redis_client = create_redis_client()

_memory_store: Dict[str, Tuple[Optional[float], Any]] = {}
_memory_lock = threading.Lock()


def _memory_set(key: str, value: Any, ttl: int) -> bool:
    expiry = time.time() + ttl if ttl else None
    with _memory_lock:
        _memory_store[key] = (expiry, copy.deepcopy(value))
    return True


def _memory_get(key: str) -> Optional[Any]:
    with _memory_lock:
        entry = _memory_store.get(key)
        if not entry:
            return None
        expiry, stored_value = entry
        if expiry and expiry <= time.time():
            _memory_store.pop(key, None)
            return None
        return copy.deepcopy(stored_value)


def _memory_exists(key: str) -> bool:
    with _memory_lock:
        entry = _memory_store.get(key)
        if not entry:
            return False
        expiry, _ = entry
        if expiry and expiry <= time.time():
            _memory_store.pop(key, None)
            return False
        return True

def test_redis_connection() -> bool:
    """
    Test Redis connection with circuit breaker protection.

    Returns:
        True if connection is successful, False otherwise
    """
    if redis_client is None:
        logger.warning("Redis client is None - system operating without caching")
        return False

    def _test_connection():
        redis_client.ping()
        return True

    try:
        return redis_circuit_breaker.call(_test_connection)
    except Exception as e:
        logger.warning(f"Redis connection test failed: {e}")
        return False

def cache_query_result(query: str, user_id: str, result: Any, ttl: int = 86400) -> bool:
    """
    Cache query results in Redis with TTL and comprehensive error handling.

    Args:
        query: Query string or identifier
        user_id: User ID for namespacing
        result: Query result to cache
        ttl: Time to live in seconds (default: 24 hours)

    Returns:
        True if successful, False otherwise (graceful degradation)
    """
    if redis_client is None:
        logger.debug("Redis unavailable - skipping cache operation")
        return False

    def _cache_operation():
        # Create cache key
        cache_key = f"query:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"

        # Serialize result
        serialized_result = json.dumps(result, default=str)

        # Store in Redis with TTL
        redis_client.setex(cache_key, ttl, serialized_result)
        return True

    try:
        return redis_circuit_breaker.call(_cache_operation)
    except Exception as e:
        logger.warning(f"Error caching query result: {e} - continuing without caching")
        return False

def set_conversation_state(user_id: str, state: Dict[str, Any], ttl: int = 86400) -> bool:
    """
    Store per-user conversation state (e.g., progressive Q&A) with TTL.

    Args:
        user_id: User identifier
        state: Arbitrary JSON-serializable state
        ttl: Time to live in seconds (default: 24 hours)

    Returns:
        True if successful, False otherwise (graceful degradation)
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        return _memory_set(key, state, ttl)

    def _store_operation():
        serializable_state = copy.deepcopy(state)
        if "asked_questions" in serializable_state and isinstance(serializable_state["asked_questions"], set):
            serializable_state["asked_questions"] = list(serializable_state["asked_questions"])
        redis_client.setex(key, ttl, json.dumps(serializable_state, default=str))
        return True

    try:
        return redis_circuit_breaker.call(_store_operation)
    except Exception as e:
        logger.warning(f"Error storing conversation state for {user_id}: {e}")
        return _memory_set(key, state, ttl)

def get_conversation_state(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve per-user conversation state.

    Args:
        user_id: User identifier

    Returns:
        State dict or None if not found/unavailable
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        return _memory_get(key)

    def _get_operation():
        data = redis_client.get(key)
        if data:
            state = json.loads(data)
            # Convert string sets back to actual sets for compatibility
            if "asked_questions" in state and isinstance(state["asked_questions"], list):
                state["asked_questions"] = set(state["asked_questions"])
            return state
        return None

    try:
        return redis_circuit_breaker.call(_get_operation)
    except Exception as e:
        logger.warning(f"Error getting conversation state for {user_id}: {e}")
        return _memory_get(key)

def update_conversation_state(user_id: str, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields in conversation state without overwriting entire state.

    Args:
        user_id: User identifier
        updates: Dictionary of fields to update

    Returns:
        True if successful, False otherwise
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        state = _memory_get(key) or {}
        state.update(updates)
        return _memory_set(key, state, 86400)

    def _update_operation():
        existing_data = redis_client.get(key)
        if existing_data:
            state = json.loads(existing_data)
            # Convert string sets back to actual sets
            if "asked_questions" in state and isinstance(state["asked_questions"], list):
                state["asked_questions"] = set(state["asked_questions"])
        else:
            state = {}
        
        # Update with new values
        state.update(updates)
        
        # Convert sets to lists for JSON serialization
        if "asked_questions" in state and isinstance(state["asked_questions"], set):
            state["asked_questions"] = list(state["asked_questions"])
        
        # Update with extended TTL
        serializable_state = copy.deepcopy(state)
        if "asked_questions" in serializable_state and isinstance(serializable_state["asked_questions"], set):
            serializable_state["asked_questions"] = list(serializable_state["asked_questions"])
        redis_client.setex(key, 86400, json.dumps(serializable_state, default=str))
        return True

    try:
        return redis_circuit_breaker.call(_update_operation)
    except Exception as e:
        logger.warning(f"Error updating conversation state for {user_id}: {e}")
        state = _memory_get(key) or {}
        state.update(updates)
        return _memory_set(key, state, 86400)

def add_asked_question(user_id: str, question: str) -> bool:
    """
    Add a question to the set of asked questions to prevent repeats.

    Args:
        user_id: User identifier
        question: Question identifier to add

    Returns:
        True if successful, False otherwise
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        state = _memory_get(key) or {}
        asked_questions = state.get("asked_questions", set())
        if not isinstance(asked_questions, set):
            asked_questions = set(asked_questions)
        asked_questions.add(question)
        state["asked_questions"] = asked_questions
        return _memory_set(key, state, 86400)

    def _add_question_operation():
        existing_data = redis_client.get(key)
        if existing_data:
            state = json.loads(existing_data)
            # Convert string sets back to actual sets
            if "asked_questions" in state and isinstance(state["asked_questions"], list):
                state["asked_questions"] = set(state["asked_questions"])
            else:
                state["asked_questions"] = set()
        else:
            state = {"asked_questions": set()}
        
        # Add new question
        state["asked_questions"].add(question)
        
        serializable_state = copy.deepcopy(state)
        serializable_state["asked_questions"] = list(serializable_state["asked_questions"])
        redis_client.setex(key, 86400, json.dumps(serializable_state, default=str))
        return True

    try:
        return redis_circuit_breaker.call(_add_question_operation)
    except Exception as e:
        logger.warning(f"Error adding asked question for {user_id}: {e}")
        state = _memory_get(key) or {}
        asked_questions = state.get("asked_questions", set())
        if not isinstance(asked_questions, set):
            asked_questions = set(asked_questions)
        asked_questions.add(question)
        state["asked_questions"] = asked_questions
        return _memory_set(key, state, 86400)

def has_asked_question(user_id: str, question: str) -> bool:
    """
    Check if a question has already been asked to prevent repeats.

    Args:
        user_id: User identifier
        question: Question identifier to check

    Returns:
        True if question was asked, False otherwise
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        state = _memory_get(key)
        if not state:
            return False
        asked_questions = state.get("asked_questions", [])
        if isinstance(asked_questions, set):
            return question in asked_questions
        return question in asked_questions

    def _check_question_operation():
        existing_data = redis_client.get(key)
        
        if not existing_data:
            return False
            
        state = json.loads(existing_data)
        asked_questions = state.get("asked_questions", [])
        
        # Handle both list and set formats
        if isinstance(asked_questions, list):
            return question in asked_questions
        elif isinstance(asked_questions, set):
            return question in asked_questions
        
        return False

    try:
        return redis_circuit_breaker.call(_check_question_operation)
    except Exception as e:
        logger.warning(f"Error checking asked question for {user_id}: {e}")
        state = _memory_get(key)
        if not state:
            return False
        asked_questions = state.get("asked_questions", [])
        if isinstance(asked_questions, set):
            return question in asked_questions
        return question in asked_questions

def get_current_question(user_id: str) -> Optional[str]:
    """
    Get the current question in the conversation flow.

    Args:
        user_id: User identifier

    Returns:
        Current question identifier or None if not found
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        state = _memory_get(key)
        if not state:
            return None
        return state.get("current_question")

    def _get_current_question_operation():
        data = redis_client.get(key)
        
        if not data:
            return None
            
        state = json.loads(data)
        return state.get("current_question")

    try:
        return redis_circuit_breaker.call(_get_current_question_operation)
    except Exception as e:
        logger.warning(f"Error getting current question for {user_id}: {e}")
        state = _memory_get(key)
        if not state:
            return None
        return state.get("current_question")

def set_current_question(user_id: str, question: str) -> bool:
    """
    Set the current question in the conversation flow.

    Args:
        user_id: User identifier
        question: Current question identifier

    Returns:
        True if successful, False otherwise
    """
    key = f"conv:{user_id}"

    if redis_client is None:
        state = _memory_get(key) or {}
        state["current_question"] = question
        state["last_question_sent"] = datetime.now().isoformat()
        return _memory_set(key, state, 86400)

    def _set_current_question_operation():
        existing_data = redis_client.get(key)
        if existing_data:
            state = json.loads(existing_data)
        else:
            state = {}
        
        # Set current question
        state["current_question"] = question
        state["last_question_sent"] = datetime.now().isoformat()
        
        # Update with extended TTL
        serializable_state = copy.deepcopy(state)
        if "asked_questions" in serializable_state and isinstance(serializable_state["asked_questions"], set):
            serializable_state["asked_questions"] = list(serializable_state["asked_questions"])
        redis_client.setex(key, 86400, json.dumps(serializable_state, default=str))
        return True

    try:
        return redis_circuit_breaker.call(_set_current_question_operation)
    except Exception as e:
        logger.warning(f"Error setting current question for {user_id}: {e}")
        state = _memory_get(key) or {}
        state["current_question"] = question
        state["last_question_sent"] = datetime.now().isoformat()
        return _memory_set(key, state, 86400)

def get_cached_query_result(query: str, user_id: str) -> Optional[Any]:
    """
    Get cached query results from Redis with error handling.

    Args:
        query: Query string or identifier
        user_id: User ID for namespacing

    Returns:
        Cached result or None if not found or Redis unavailable
    """
    if redis_client is None:
        logger.debug("Redis unavailable - no cached result available")
        return None

    def _get_cache_operation():
        # Create cache key
        cache_key = f"query:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"

        # Get from Redis
        cached_data = redis_client.get(cache_key)

        if cached_data:
            return json.loads(cached_data)

        return None

    try:
        return redis_circuit_breaker.call(_get_cache_operation)
    except Exception as e:
        logger.warning(f"Error getting cached query result: {e} - treating as cache miss")
        return None

def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern with error handling.

    Args:
        pattern: Redis key pattern (e.g., "query:user123:*")

    Returns:
        Number of keys deleted, or 0 on failure
    """
    if redis_client is None:
        logger.debug("Redis unavailable - cannot invalidate cache")
        return 0

    def _invalidate_operation():
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0

    try:
        return redis_circuit_breaker.call(_invalidate_operation)
    except Exception as e:
        logger.warning(f"Error invalidating cache pattern '{pattern}': {e}")
        return 0

def store_thread_state(thread_id: str, state: dict, ttl: int = 604800) -> bool:
    """
    Store thread state for LangGraph checkpointer with error handling.

    Args:
        thread_id: Thread identifier
        state: State dictionary
        ttl: Time to live in seconds (default: 7 days)

    Returns:
        True if successful, False otherwise (graceful degradation)
    """
    state_key = f"thread:{thread_id}:state"

    if redis_client is None:
        return _memory_set(state_key, state, ttl)

    def _store_operation():
        serialized_state = json.dumps(state, default=str)
        redis_client.setex(state_key, ttl, serialized_state)
        return True

    try:
        return redis_circuit_breaker.call(_store_operation)
    except Exception as e:
        logger.warning(f"Error storing thread state for {thread_id}: {e}")
        return _memory_set(state_key, state, ttl)

def get_thread_state(thread_id: str) -> Optional[dict]:
    """
    Get thread state for LangGraph checkpointer with error handling.

    Args:
        thread_id: Thread identifier

    Returns:
        State dictionary or None if not found or Redis unavailable
    """
    state_key = f"thread:{thread_id}:state"

    if redis_client is None:
        return _memory_get(state_key)

    def _get_operation():
        cached_state = redis_client.get(state_key)

        if cached_state:
            return json.loads(cached_state)

        return None

    try:
        return redis_circuit_breaker.call(_get_operation)
    except Exception as e:
        logger.warning(f"Error getting thread state for {thread_id}: {e}")
        return _memory_get(state_key)

def store_conversation_history(user_id: str, message: dict, max_messages: int = 100) -> bool:
    """
    Store conversation history in Redis with error handling.

    Args:
        user_id: User identifier
        message: Message dictionary
        max_messages: Maximum messages to keep

    Returns:
        True if successful, False otherwise (graceful degradation)
    """
    if redis_client is None:
        logger.debug("Redis unavailable - cannot store conversation history")
        return False

    def _store_operation():
        history_key = f"conversation:{user_id}"

        # Add message to list
        redis_client.lpush(history_key, json.dumps(message, default=str))

        # Trim to max_messages
        redis_client.ltrim(history_key, 0, max_messages - 1)

        # Set expiry (30 days)
        redis_client.expire(history_key, 2592000)

        return True

    try:
        return redis_circuit_breaker.call(_store_operation)
    except Exception as e:
        logger.warning(f"Error storing conversation history for {user_id}: {e}")
        return False

def get_conversation_history(user_id: str, limit: int = 50) -> list:
    """
    Get conversation history from Redis with error handling.

    Args:
        user_id: User identifier
        limit: Maximum messages to retrieve

    Returns:
        List of message dictionaries, or empty list on failure
    """
    if redis_client is None:
        logger.debug("Redis unavailable - no conversation history available")
        return []

    def _get_operation():
        history_key = f"conversation:{user_id}"

        # Get messages (most recent first)
        messages = redis_client.lrange(history_key, 0, limit - 1)

        # Parse JSON messages
        parsed_messages = []
        for msg in messages:
            try:
                parsed_messages.append(json.loads(msg))
            except json.JSONDecodeError:
                continue

        # Return in chronological order (oldest first)
        return list(reversed(parsed_messages))

    try:
        return redis_circuit_breaker.call(_get_operation)
    except Exception as e:
        logger.warning(f"Error getting conversation history for {user_id}: {e}")
        return []

def increment_counter(key: str, ttl: int = 3600) -> int:
    """
    Increment a counter with TTL and error handling.

    Args:
        key: Counter key
        ttl: Time to live in seconds

    Returns:
        New counter value, or 0 on failure
    """
    if redis_client is None:
        logger.debug("Redis unavailable - cannot increment counter")
        return 0

    def _increment_operation():
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        result = pipe.execute()
        return result[0]

    try:
        return redis_circuit_breaker.call(_increment_operation)
    except Exception as e:
        logger.warning(f"Error incrementing counter '{key}': {e}")
        return 0

def get_counter(key: str) -> int:
    """
    Get counter value with error handling.

    Args:
        key: Counter key

    Returns:
        Counter value, or 0 on failure
    """
    if redis_client is None:
        logger.debug("Redis unavailable - counter value unavailable")
        return 0

    def _get_operation():
        value = redis_client.get(key)
        return int(value) if value else 0

    try:
        return redis_circuit_breaker.call(_get_operation)
    except Exception as e:
        logger.warning(f"Error getting counter '{key}': {e}")
        return 0

def store_temporary_data(key: str, data: Any, ttl: int = 3600) -> bool:
    """
    Store temporary data with TTL and error handling.

    Args:
        key: Data key
        data: Data to store
        ttl: Time to live in seconds

    Returns:
        True if successful, False otherwise (graceful degradation)
    """
    if redis_client is None:
        return _memory_set(key, data, ttl)

    def _store_operation():
        serialized_data = json.dumps(data, default=str)
        redis_client.setex(key, ttl, serialized_data)
        return True

    try:
        return redis_circuit_breaker.call(_store_operation)
    except Exception as e:
        logger.warning(f"Error storing temporary data for key '{key}': {e}")
        return _memory_set(key, data, ttl)

def get_temporary_data(key: str) -> Optional[Any]:
    """
    Get temporary data with error handling.

    Args:
        key: Data key

    Returns:
        Data or None if not found or Redis unavailable
    """
    if redis_client is None:
        return _memory_get(key)

    def _get_operation():
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    try:
        return redis_circuit_breaker.call(_get_operation)
    except Exception as e:
        logger.warning(f"Error getting temporary data for key '{key}': {e}")
        return _memory_get(key)

# Health check function
def redis_health_check() -> dict:
    """
    Perform Redis health check with comprehensive error handling.

    Returns:
        Health status dictionary
    """
    if redis_client is None:
        return {
            "status": "unhealthy",
            "error": "Redis client not initialized",
            "fallback_available": True
        }

    try:
        # Test basic operations with circuit breaker
        def _health_check():
            test_key = "health_check_test"
            redis_client.set(test_key, "test_value", ex=10)
            value = redis_client.get(test_key)
            redis_client.delete(test_key)
            return value == "test_value"

        test_passed = redis_circuit_breaker.call(_health_check)

        if test_passed:
            # Get Redis info
            info = redis_client.info()
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
        else:
            return {
                "status": "unhealthy",
                "error": "Redis health check failed",
                "fallback_available": True
            }

    except redis.ConnectionError:
        return {
            "status": "unhealthy",
            "error": "Redis connection refused - system can operate without caching",
            "fallback_available": True
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": f"Redis operation failed: {str(e)}",
            "fallback_available": True
        }

def get_redis_circuit_breaker_status() -> dict:
    """
    Get the current status of the Redis circuit breaker for monitoring.

    Returns:
        Dictionary with circuit breaker status information
    """
    return {
        "state": redis_circuit_breaker.state,
        "failure_count": redis_circuit_breaker.failure_count,
        "last_failure_time": redis_circuit_breaker.last_failure_time,
        "recovery_timeout": redis_circuit_breaker.recovery_timeout
    }
