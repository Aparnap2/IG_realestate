"""
Database utility functions for Celery worker connection handling.

This module provides proper database session management for Celery workers,
including connection pooling, health checks, and graceful error handling.
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
from functools import wraps

# Supabase imports for database operations
try:
    from supabase import create_client, Client
    from backend.utils.supabase_client import _ensure_supabase, supabase_circuit_breaker
except ImportError:
    # Fallback imports for testing
    try:
        from supabase import create_client, Client
        _ensure_supabase = lambda: None
        supabase_circuit_breaker = None
    except ImportError:
        create_client = None
        Client = None
        _ensure_supabase = None
        supabase_circuit_breaker = None

logger = logging.getLogger(__name__)

# Global database session storage for worker processes
_db_session: Optional[Client] = None
_db_lock = threading.Lock()
_db_health_status = {
    "status": "unknown",
    "last_check": None,
    "connection_errors": 0,
    "total_operations": 0,
    "failed_operations": 0
}

def get_database_session() -> Optional[Client]:
    """
    Get or create a database session for Celery workers.
    
    This function implements connection pooling and reuse for worker processes
    to avoid creating new connections for every task.
    
    Returns:
        Supabase client instance or None if unavailable
    """
    global _db_session, _db_health_status
    
    with _db_lock:
        # Check if we have a valid session
        if _db_session is not None:
            return _db_session
        
        try:
            logger.info("🔄 Creating new database session for worker...")
            
            # Get settings
            from config import get_settings
            settings = get_settings()
            
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                raise ValueError("Missing Supabase configuration")
            
            # Create client
            _db_session = _ensure_supabase()
            
            if _db_session:
                logger.info("✅ Database session created successfully")
                _db_health_status["status"] = "healthy"
                _db_health_status["last_check"] = time.time()
            else:
                raise Exception("Failed to create Supabase client")
            
            return _db_session
            
        except Exception as e:
            logger.error(f"❌ Failed to create database session: {e}")
            _db_health_status["status"] = "error"
            _db_health_status["connection_errors"] += 1
            _db_session = None
            return None

def validate_database_connection(timeout: int = 10) -> bool:
    """
    Validate database connection with health check.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection is valid, False otherwise
    """
    try:
        logger.debug("🔍 Validating database connection...")
        
        client = get_database_session()
        if not client:
            return False
        
        # Test connection with a simple query
        start_time = time.time()
        
        # Use circuit breaker if available
        if supabase_circuit_breaker:
            # Simple connection test
            result = supabase_circuit_breaker.call(
                lambda: client.table("leads").select("id").limit(1).execute()
            )
        else:
            # Direct query without circuit breaker
            result = client.table("leads").select("id").limit(1).execute()
        
        duration = time.time() - start_time
        
        if duration > timeout:
            logger.warning(f"⚠️ Database connection slow: {duration:.2f}s")
            return False
        
        logger.debug(f"✅ Database connection validated ({duration:.2f}s)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection validation failed: {e}")
        return False

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    
    Yields:
        Database client instance
        
    Raises:
        Exception: If database connection fails
    """
    client = None
    try:
        client = get_database_session()
        if not client:
            raise Exception("Database session unavailable")
        
        # Update health status
        _db_health_status["total_operations"] += 1
        _db_health_status["status"] = "healthy"
        _db_health_status["last_check"] = time.time()
        
        yield client
        
    except Exception as e:
        _db_health_status["failed_operations"] += 1
        logger.error(f"Database session error: {e}")
        raise
    finally:
        # No explicit cleanup needed for Supabase client
        pass

def health_check_database() -> Dict[str, Any]:
    """
    Comprehensive database health check.
    
    Returns:
        Dictionary with health status information
    """
    try:
        is_healthy = validate_database_connection(timeout=5)
        
        # Get circuit breaker status if available
        circuit_status = {}
        if supabase_circuit_breaker:
            circuit_status = {
                "state": getattr(supabase_circuit_breaker, 'state', 'unknown'),
                "failure_count": getattr(supabase_circuit_breaker, 'failure_count', 0),
                "last_failure_time": getattr(supabase_circuit_breaker, 'last_failure_time', None)
            }
        
        # Calculate success rate
        total_ops = _db_health_status["total_operations"]
        failed_ops = _db_health_status["failed_operations"]
        success_rate = ((total_ops - failed_ops) / total_ops * 100) if total_ops > 0 else 0
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "session_available": _db_session is not None,
            "connection_validation": is_healthy,
            "operations": {
                "total": total_ops,
                "failed": failed_ops,
                "success_rate": round(success_rate, 2)
            },
            "circuit_breaker": circuit_status,
            "last_check": _db_health_status["last_check"],
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

def reset_database_session():
    """
    Reset the global database session.
    
    This should be called when the session becomes stale or corrupted.
    """
    global _db_session, _db_health_status
    
    with _db_lock:
        if _db_session:
            logger.info("🔄 Resetting database session...")
            _db_session = None
        
        # Reset health status but preserve counters
        _db_health_status["status"] = "unknown"
        _db_health_status["last_check"] = None
        
        logger.info("✅ Database session reset complete")

def with_database_session(func):
    """
    Decorator to automatically provide database session to functions.
    
    Usage:
        @with_database_session
        def my_function(db_session):
            return db_session.table("leads").select("*").execute()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_db_session() as db_session:
            # Add db_session as first argument if not already provided
            if 'db_session' not in kwargs:
                return func(db_session, *args, **kwargs)
            else:
                return func(*args, **kwargs)
    
    return wrapper

class DatabaseConnectionManager:
    """
    Context manager for handling database connections in Celery tasks.
    
    This class provides automatic connection management, retry logic,
    and health monitoring for database operations in worker processes.
    """
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        self.max_retries = max_retries
        self.timeout = timeout
        self._retries = 0
        self._last_error = None
    
    def __enter__(self):
        """Enter context manager."""
        return get_database_session()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if exc_type is not None:
            self._last_error = str(exc_val)
            self._retries += 1
            
            # Reset session on critical errors
            if isinstance(exc_val, (ConnectionError, TimeoutError, OSError)):
                if self._retries >= self.max_retries:
                    logger.error(f"❌ Max retries reached ({self.max_retries}). Resetting database session.")
                    reset_database_session()
                    self._retries = 0
                else:
                    logger.warning(f"⚠️ Database operation failed (retry {self._retries}/{self.max_retries}): {exc_val}")
        
        return False  # Don't suppress exceptions
    
    @property
    def last_error(self) -> Optional[str]:
        """Get the last error encountered."""
        return self._last_error
    
    @property
    def retry_count(self) -> int:
        """Get the current retry count."""
        return self._retries

def execute_with_retry(operation_func, *args, max_retries: int = 3, **kwargs) -> Any:
    """
    Execute a database operation with automatic retry logic.
    
    Args:
        operation_func: Function to execute
        *args: Arguments for the function
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the operation
        
    Raises:
        Exception: If all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            with DatabaseConnectionManager(max_retries=1) as db_session:  # Outer retry
                if not db_session:
                    raise ConnectionError("Database session unavailable")
                
                # Execute the operation
                return operation_func(db_session, *args, **kwargs)
                
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                delay = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
                break
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    
    return None

# Export public functions
__all__ = [
    'get_database_session',
    'validate_database_connection', 
    'get_db_session',
    'health_check_database',
    'reset_database_session',
    'with_database_session',
    'DatabaseConnectionManager',
    'execute_with_retry'
]