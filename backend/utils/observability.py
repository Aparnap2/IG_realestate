import time
import logging
import inspect
from typing import Callable, Any
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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