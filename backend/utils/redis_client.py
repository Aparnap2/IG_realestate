"""
Redis client for LangGraph checkpointer and query caching according to PRD.
"""
import redis
import json
import os
import hashlib
from typing import Any, Optional
from datetime import timedelta

# Initialize Redis client
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True
)

def test_redis_connection() -> bool:
    """
    Test Redis connection.
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        redis_client.ping()
        return True
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False

def cache_query_result(query: str, user_id: str, result: Any, ttl: int = 86400) -> bool:
    """
    Cache query results in Redis with TTL.
    
    Args:
        query: Query string or identifier
        user_id: User ID for namespacing
        result: Query result to cache
        ttl: Time to live in seconds (default: 24 hours)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create cache key
        cache_key = f"query:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"
        
        # Serialize result
        serialized_result = json.dumps(result, default=str)
        
        # Store in Redis with TTL
        redis_client.setex(cache_key, ttl, serialized_result)
        
        return True
    except Exception as e:
        print(f"Error caching query result: {e}")
        return False

def get_cached_query_result(query: str, user_id: str) -> Optional[Any]:
    """
    Get cached query results from Redis.
    
    Args:
        query: Query string or identifier
        user_id: User ID for namespacing
        
    Returns:
        Cached result or None if not found
    """
    try:
        # Create cache key
        cache_key = f"query:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"
        
        # Get from Redis
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            return json.loads(cached_data)
        
        return None
    except Exception as e:
        print(f"Error getting cached query result: {e}")
        return None

def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern: Redis key pattern (e.g., "query:user123:*")
        
    Returns:
        Number of keys deleted
    """
    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except Exception as e:
        print(f"Error invalidating cache: {e}")
        return 0

def store_thread_state(thread_id: str, state: dict, ttl: int = 604800) -> bool:
    """
    Store thread state for LangGraph checkpointer.
    
    Args:
        thread_id: Thread identifier
        state: State dictionary
        ttl: Time to live in seconds (default: 7 days)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        state_key = f"thread:{thread_id}:state"
        serialized_state = json.dumps(state, default=str)
        redis_client.setex(state_key, ttl, serialized_state)
        return True
    except Exception as e:
        print(f"Error storing thread state: {e}")
        return False

def get_thread_state(thread_id: str) -> Optional[dict]:
    """
    Get thread state for LangGraph checkpointer.
    
    Args:
        thread_id: Thread identifier
        
    Returns:
        State dictionary or None if not found
    """
    try:
        state_key = f"thread:{thread_id}:state"
        cached_state = redis_client.get(state_key)
        
        if cached_state:
            return json.loads(cached_state)
        
        return None
    except Exception as e:
        print(f"Error getting thread state: {e}")
        return None

def store_conversation_history(user_id: str, message: dict, max_messages: int = 100) -> bool:
    """
    Store conversation history in Redis.
    
    Args:
        user_id: User identifier
        message: Message dictionary
        max_messages: Maximum messages to keep
        
    Returns:
        True if successful, False otherwise
    """
    try:
        history_key = f"conversation:{user_id}"
        
        # Add message to list
        redis_client.lpush(history_key, json.dumps(message, default=str))
        
        # Trim to max_messages
        redis_client.ltrim(history_key, 0, max_messages - 1)
        
        # Set expiry (30 days)
        redis_client.expire(history_key, 2592000)
        
        return True
    except Exception as e:
        print(f"Error storing conversation history: {e}")
        return False

def get_conversation_history(user_id: str, limit: int = 50) -> list:
    """
    Get conversation history from Redis.
    
    Args:
        user_id: User identifier
        limit: Maximum messages to retrieve
        
    Returns:
        List of message dictionaries
    """
    try:
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
    except Exception as e:
        print(f"Error getting conversation history: {e}")
        return []

def increment_counter(key: str, ttl: int = 3600) -> int:
    """
    Increment a counter with TTL.
    
    Args:
        key: Counter key
        ttl: Time to live in seconds
        
    Returns:
        New counter value
    """
    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        result = pipe.execute()
        return result[0]
    except Exception as e:
        print(f"Error incrementing counter: {e}")
        return 0

def get_counter(key: str) -> int:
    """
    Get counter value.
    
    Args:
        key: Counter key
        
    Returns:
        Counter value
    """
    try:
        value = redis_client.get(key)
        return int(value) if value else 0
    except Exception as e:
        print(f"Error getting counter: {e}")
        return 0

def store_temporary_data(key: str, data: Any, ttl: int = 3600) -> bool:
    """
    Store temporary data with TTL.
    
    Args:
        key: Data key
        data: Data to store
        ttl: Time to live in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        serialized_data = json.dumps(data, default=str)
        redis_client.setex(key, ttl, serialized_data)
        return True
    except Exception as e:
        print(f"Error storing temporary data: {e}")
        return False

def get_temporary_data(key: str) -> Optional[Any]:
    """
    Get temporary data.
    
    Args:
        key: Data key
        
    Returns:
        Data or None if not found
    """
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Error getting temporary data: {e}")
        return None

# Health check function
def redis_health_check() -> dict:
    """
    Perform Redis health check.
    
    Returns:
        Health status dictionary
    """
    try:
        # Test basic operations
        test_key = "health_check_test"
        redis_client.set(test_key, "test_value", ex=10)
        value = redis_client.get(test_key)
        redis_client.delete(test_key)
        
        # Get Redis info
        info = redis_client.info()
        
        return {
            "status": "healthy" if value == "test_value" else "unhealthy",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "redis_version": info.get("redis_version", "unknown")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
