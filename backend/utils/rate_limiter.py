"""
Redis-based rate limiter with sliding window implementation for database tools.

Implements tool-specific rate limits with graceful degradation when Redis is unavailable.
Enhanced with circuit breaker patterns and comprehensive error handling.
Follows DDG MCP best practices for rate limiting.
"""
import time
import redis
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from utils.redis_client import redis_client, redis_health_check, redis_circuit_breaker

logger = logging.getLogger(__name__)

# Enhanced rate limit configurations with burst handling
TOOL_RATE_LIMITS = {
    "query_properties_tool": 100,
    "save_lead_tool": 50,
    "get_config_tool": 200,
    "qualify_lead_with_llm": 30,
    "send_instagram_message": 20,
    "get_available_calendar_slots": 50,
    "book_calendar_event": 10,
    "create_hubspot_contact": 20,
    "create_hubspot_deal": 10,
}

# Burst limits (allow short bursts above normal rate)
BURST_MULTIPLIER = 1.5
BURST_WINDOW = 10  # seconds

# Window size in seconds (1 minute)
WINDOW_SIZE = 60

# Rate limit configurations (requests per minute)
TOOL_RATE_LIMITS = {
    "query_properties_tool": 100,
    "save_lead_tool": 50,
    "get_config_tool": 200,
    "qualify_lead_with_llm": 30,
    "send_instagram_message": 20,
    "get_available_calendar_slots": 50,
    "book_calendar_event": 10,
    "create_hubspot_contact": 20,
    "create_hubspot_deal": 10,
}

# Window size in seconds (1 minute)
WINDOW_SIZE = 60

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, tool_name: str, limit: int, reset_time: int, retry_after: int = None):
        self.tool_name = tool_name
        self.limit = limit
        self.reset_time = reset_time
        self.retry_after = retry_after or reset_time
        super().__init__(f"Rate limit exceeded for {tool_name}. Retry after {self.retry_after} seconds")

class RateLimitError(Exception):
    """Exception raised when rate limiting infrastructure fails"""
    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        self.error = error
        super().__init__(f"Rate limiting error for {tool_name}: {error}")

def _get_redis_key(tool_name: str, identifier: str = "global") -> str:
    """Generate Redis key for rate limiting"""
    return f"ratelimit:{tool_name}:{identifier}"

def _cleanup_old_requests(redis_conn: redis.Redis, key: str, current_time: float) -> None:
    """Remove requests outside the sliding window"""
    try:
        # Remove all timestamps older than current_time - WINDOW_SIZE
        redis_conn.zremrangebyscore(key, 0, current_time - WINDOW_SIZE)
    except Exception:
        pass  # Graceful degradation

def check_rate_limit(tool_name: str, identifier: str = "global") -> Tuple[bool, Dict[str, str]]:
    """
    Check if request is within rate limit using sliding window algorithm with burst handling.

    Args:
        tool_name: Name of the tool being rate limited
        identifier: Optional identifier for per-user limits (default: global)

    Returns:
        Tuple of (allowed: bool, headers: dict with rate limit info)
    """
    limit = TOOL_RATE_LIMITS.get(tool_name, 100)
    burst_limit = int(limit * BURST_MULTIPLIER)
    current_time = time.time()
    key = _get_redis_key(tool_name, identifier)
    burst_key = f"{key}:burst"

    # Check Redis health with circuit breaker
    try:
        health = redis_circuit_breaker.call(lambda: redis_health_check())
        redis_available = health.get("status") == "healthy"
    except Exception:
        redis_available = False

    if not redis_available:
        # Graceful degradation - allow request but log warning
        logger.warning(f"Redis unavailable for rate limiting {tool_name} - allowing request with degraded mode")
        return True, {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "unlimited",
            "X-RateLimit-Reset": str(int(current_time + WINDOW_SIZE)),
            "X-RateLimit-Status": "degraded"
        }

    def _check_limit():
        # Use Redis pipeline for atomic operations
        pipe = redis_client.pipeline()

        # Add current request timestamp to main window
        pipe.zadd(key, {str(current_time): current_time})

        # Add to burst window
        pipe.zadd(burst_key, {str(current_time): current_time})

        # Remove old requests outside main window
        pipe.zremrangebyscore(key, 0, current_time - WINDOW_SIZE)

        # Remove old requests outside burst window
        pipe.zremrangebyscore(burst_key, 0, current_time - BURST_WINDOW)

        # Count requests in main window
        pipe.zcard(key)

        # Count requests in burst window
        pipe.zcard(burst_key)

        # Set expiry on keys
        pipe.expire(key, WINDOW_SIZE * 2)
        pipe.expire(burst_key, BURST_WINDOW * 2)

        # Execute pipeline
        results = pipe.execute()
        main_count = results[4]  # zcard result for main window
        burst_count = results[5]  # zcard result for burst window

        # Check burst limit first (stricter)
        if burst_count >= burst_limit:
            remaining = max(0, burst_limit - burst_count)
            reset_time = int(current_time + BURST_WINDOW)
            return False, {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "X-RateLimit-Status": "burst_exceeded"
            }

        # Check main window limit
        if main_count >= limit:
            remaining = max(0, limit - main_count)
            reset_time = int(current_time + WINDOW_SIZE)
            return False, {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "X-RateLimit-Status": "limit_exceeded"
            }

        # Calculate remaining requests
        remaining = max(0, limit - main_count)
        reset_time = int(current_time + WINDOW_SIZE)

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Status": "active"
        }

        return True, headers

    try:
        return redis_circuit_breaker.call(_check_limit)
    except Exception as e:
        # Graceful degradation on Redis errors
        logger.warning(f"Redis error in rate limiting for {tool_name}: {e} - allowing request")
        return True, {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "unlimited",
            "X-RateLimit-Reset": str(int(current_time + WINDOW_SIZE)),
            "X-RateLimit-Status": "error"
        }

def record_request(tool_name: str, identifier: str = "global") -> None:
    """
    Record a successful request (called after rate limit check passes).
    Includes circuit breaker protection and error handling.

    Args:
        tool_name: Name of the tool
        identifier: Optional identifier for per-user limits
    """
    try:
        health = redis_circuit_breaker.call(lambda: redis_health_check())
        if health.get("status") != "healthy":
            return  # Skip recording if Redis is down
    except Exception:
        return  # Skip recording if health check fails

    def _record():
        current_time = time.time()
        key = _get_redis_key(tool_name, identifier)
        burst_key = f"{key}:burst"

        # Add timestamp to both windows and cleanup in one operation
        pipe = redis_client.pipeline()
        pipe.zadd(key, {str(current_time): current_time})
        pipe.zadd(burst_key, {str(current_time): current_time})
        pipe.zremrangebyscore(key, 0, current_time - WINDOW_SIZE)
        pipe.zremrangebyscore(burst_key, 0, current_time - BURST_WINDOW)
        pipe.expire(key, WINDOW_SIZE * 2)
        pipe.expire(burst_key, BURST_WINDOW * 2)
        pipe.execute()

    try:
        redis_circuit_breaker.call(_record)
    except Exception as e:
        logger.warning(f"Failed to record rate limit request for {tool_name}: {e}")

def get_rate_limit_status(tool_name: str, identifier: str = "global") -> Dict[str, any]:
    """
    Get current rate limit status for monitoring with enhanced error handling.

    Args:
        tool_name: Name of the tool
        identifier: Optional identifier

    Returns:
        Dictionary with rate limit status information
    """
    limit = TOOL_RATE_LIMITS.get(tool_name, 100)
    burst_limit = int(limit * BURST_MULTIPLIER)
    current_time = time.time()
    key = _get_redis_key(tool_name, identifier)
    burst_key = f"{key}:burst"

    try:
        health = redis_circuit_breaker.call(lambda: redis_health_check())
        redis_available = health.get("status") == "healthy"
    except Exception:
        redis_available = False

    if not redis_available:
        return {
            "tool_name": tool_name,
            "limit": limit,
            "burst_limit": burst_limit,
            "current": 0,
            "burst_current": 0,
            "remaining": limit,
            "burst_remaining": burst_limit,
            "reset_time": int(current_time + WINDOW_SIZE),
            "burst_reset_time": int(current_time + BURST_WINDOW),
            "status": "degraded"
        }

    def _get_status():
        # Clean up and count for both windows
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, current_time - WINDOW_SIZE)
        pipe.zremrangebyscore(burst_key, 0, current_time - BURST_WINDOW)
        pipe.zcard(key)
        pipe.zcard(burst_key)
        results = pipe.execute()

        current = results[2]
        burst_current = results[3]
        remaining = max(0, limit - current)
        burst_remaining = max(0, burst_limit - burst_current)
        reset_time = int(current_time + WINDOW_SIZE)
        burst_reset_time = int(current_time + BURST_WINDOW)

        return {
            "tool_name": tool_name,
            "limit": limit,
            "burst_limit": burst_limit,
            "current": current,
            "burst_current": burst_current,
            "remaining": remaining,
            "burst_remaining": burst_remaining,
            "reset_time": reset_time,
            "burst_reset_time": burst_reset_time,
            "status": "active"
        }

    try:
        return redis_circuit_breaker.call(_get_status)
    except Exception as e:
        return {
            "tool_name": tool_name,
            "limit": limit,
            "burst_limit": burst_limit,
            "current": 0,
            "burst_current": 0,
            "remaining": limit,
            "burst_remaining": burst_limit,
            "reset_time": int(current_time + WINDOW_SIZE),
            "burst_reset_time": int(current_time + BURST_WINDOW),
            "status": "error",
            "error": str(e)
        }