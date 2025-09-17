import redis
import os
import hashlib
import json
from typing import Dict, Any, Optional

# Initialize Redis client
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

def cache_query_result(query: str, user_id: str, result: Any, ttl: int = 86400) -> None:
    """
    Cache a database query result in Redis.
    
    Args:
        query: The query string
        user_id: ID of the user
        result: Query result to cache
        ttl: Time to live in seconds (default 24 hours)
    """
    # Create a hash key for the query
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    cache_key = f"query:{user_id}:{query_hash}"
    
    # Store the result as JSON
    redis_client.setex(cache_key, ttl, json.dumps(result))

def get_cached_query_result(query: str, user_id: str) -> Optional[Any]:
    """
    Retrieve a cached database query result from Redis.
    
    Args:
        query: The query string
        user_id: ID of the user
        
    Returns:
        Cached result if found, None otherwise
    """
    # Create a hash key for the query
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    cache_key = f"query:{user_id}:{query_hash}"
    
    # Retrieve the cached result
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        return json.loads(cached_result)
    
    return None

def save_thread_state(thread_id: str, state: Dict[str, Any]) -> None:
    """
    Save the state of a conversation thread in Redis.
    
    Args:
        thread_id: ID of the thread (usually user_id)
        state: Current state of the conversation
    """
    redis_client.set(f"thread:{thread_id}", json.dumps(state))

def get_thread_state(thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the state of a conversation thread from Redis.
    
    Args:
        thread_id: ID of the thread (usually user_id)
        
    Returns:
        Thread state if found, None otherwise
    """
    state = redis_client.get(f"thread:{thread_id}")
    
    if state:
        return json.loads(state)
    
    return None