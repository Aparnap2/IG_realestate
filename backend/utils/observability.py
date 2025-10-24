import time
import logging
import inspect
import sys
import os
from typing import Callable, Any, Optional
from functools import wraps

# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class MetricsCollector:
    """Simple metrics collector for tracking response times and throughput"""
    
    def __init__(self):
        self.request_count = 0
        self.total_response_time = 0.0
        self.error_count = 0
        self.counters = {}
        
    def record_request(self, response_time: float, success: bool = True):
        """Record a request with its response time"""
        self.request_count += 1
        self.total_response_time += response_time
        if not success:
            self.error_count += 1
            
    def get_average_response_time(self) -> float:
        """Get the average response time"""
        if self.request_count == 0:
            return 0.0
        return self.total_response_time / self.request_count
        
    def get_throughput(self, time_window: float = 60.0) -> float:
        """Get requests per second over a time window"""
        # This is a simplified implementation
        # In a real system, you would track requests over time
        return self.request_count / time_window if time_window > 0 else 0.0
        
    def get_error_rate(self) -> float:
        """Get the error rate"""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count
        
    def reset(self):
        """Reset all metrics"""
        self.request_count = 0
        self.total_response_time = 0.0
        self.error_count = 0
        self.counters = {}
        
    def increment_counter(self, name: str, value: int = 1):
        """Increment a named counter"""
        if name not in self.counters:
            self.counters[name] = 0
        self.counters[name] += value
        
    def get_counter(self, name: str) -> int:
        """Get the value of a named counter"""
        return self.counters.get(name, 0)
        
    def log_metrics(self):
        """Log current metrics"""
        logger.info(f"Metrics - Requests: {self.request_count}, "
                   f"Avg Response Time: {self.get_average_response_time():.2f}s, "
                   f"Error Rate: {self.get_error_rate():.2%}")

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Structured logging functions for different components
def log_settings_initialization(settings: Any, success: bool = True):
    """Log settings/configuration initialization events."""
    if success:
        logger.info("CONFIG | Settings loaded successfully", extra={
            "component": "settings",
            "supabase_configured": bool(getattr(settings, 'SUPABASE_URL', None) and getattr(settings, 'SUPABASE_KEY', None)),
            "redis_configured": bool(getattr(settings, 'REDIS_URL', None)),
            "llm_configured": bool(getattr(settings, 'OPENROUTER_API_KEY', None)),
            "hubspot_configured": bool(getattr(settings, 'HUBSPOT_ACCESS_TOKEN', None)),
            "compliance_enabled": getattr(settings, 'ENABLE_COMPLIANCE_CHECKS', True)
        })
    else:
        logger.error("CONFIG | Settings initialization failed", extra={
            "component": "settings",
            "error": "Configuration loading error"
        })

def log_llm_response_parsing(function_name: str, success: bool, model: str = None, tokens: int = None, error: str = None):
    """Log LLM response parsing events."""
    log_data = {
        "component": "llm",
        "function": function_name,
        "success": success
    }
    if model:
        log_data["model"] = model
    if tokens:
        log_data["tokens"] = tokens
    if error:
        log_data["error"] = error

    if success:
        logger.info("LLM | Response parsing successful", extra=log_data)
    else:
        logger.warning("LLM | Response parsing failed", extra=log_data)

def log_agent_handoff(from_agent: str, to_agent: str, lead_id: str, confidence: float = None, reasoning: str = None):
    """Log agent handoff events."""
    logger.info("AGENT | Handoff completed", extra={
        "component": "agents",
        "from_agent": from_agent,
        "to_agent": to_agent,
        "lead_id": lead_id,
        "confidence": confidence,
        "reasoning": reasoning
    })

def log_redis_operation(operation: str, success: bool, key: str = None, error: str = None):
    """Log Redis operations."""
    log_data = {
        "component": "redis",
        "operation": operation,
        "success": success
    }
    if key:
        log_data["key"] = key[:50]  # Truncate long keys
    if error:
        log_data["error"] = error

    if success:
        logger.debug("REDIS | Operation successful", extra=log_data)
    else:
        logger.warning("REDIS | Operation failed", extra=log_data)

def log_hubspot_operation(operation: str, success: bool, contact_id: str = None, deal_id: str = None, error: str = None):
    """Log HubSpot integration events."""
    log_data = {
        "component": "hubspot",
        "operation": operation,
        "success": success
    }
    if contact_id:
        log_data["contact_id"] = contact_id
    if deal_id:
        log_data["deal_id"] = deal_id
    if error:
        log_data["error"] = error

    if success:
        logger.info("HUBSPOT | Operation successful", extra=log_data)
    else:
        logger.warning("HUBSPOT | Operation failed", extra=log_data)

def log_supabase_query(table: str, operation: str, success: bool, record_count: int = None, error: str = None):
    """Log Supabase database operations."""
    log_data = {
        "component": "supabase",
        "table": table,
        "operation": operation,
        "success": success
    }
    if record_count is not None:
        log_data["record_count"] = record_count
    if error:
        log_data["error"] = error

    if success:
        logger.debug("SUPABASE | Query successful", extra=log_data)
    else:
        logger.warning("SUPABASE | Query failed", extra=log_data)

def track_performance(func: Callable) -> Callable:
    """Decorator to track performance metrics of functions"""
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                end_time = time.time()
                response_time = end_time - start_time
                metrics_collector.record_request(response_time, success)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        success = True

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            raise e
        finally:
            end_time = time.time()
            response_time = end_time - start_time
            metrics_collector.record_request(response_time, success)

    return sync_wrapper

# Example usage:
# @track_performance
# def some_function():
#     # Your function implementation
#     pass