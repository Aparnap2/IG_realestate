from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_init, worker_shutdown
import os
import redis
import logging
from typing import Optional
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global database session storage
_db_session = None

def get_broker_url() -> str:
    """Get and validate broker URL from environment."""
    broker_url = os.getenv("CELERY_BROKER_URL")
    if not broker_url:
        # Try Redis URL first
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            broker_url = f"{redis_url}/0"
        else:
            # Default to local Redis
            broker_url = "redis://localhost:6379/0"
    
    logger.info(f"Using broker URL: {broker_url}")
    return broker_url

def get_result_backend() -> str:
    """Get and validate result backend URL from environment."""
    result_backend = os.getenv("CELERY_RESULT_BACKEND")
    if not result_backend:
        # Use same as broker for Redis
        broker_url = get_broker_url()
        if broker_url.startswith("redis://"):
            result_backend = broker_url
        else:
            result_backend = "redis://localhost:6379/0"
    
    logger.info(f"Using result backend: {result_backend}")
    return result_backend

def validate_broker_connection(broker_url: str, timeout: int = 10) -> bool:
    """Validate broker connection with timeout."""
    try:
        if broker_url.startswith("redis://"):
            # Parse Redis URL
            import re
            match = re.match(r'redis://([^:]+):(\d+)/(\d+)', broker_url)
            if match:
                host, port, db = match.groups()
                r = redis.Redis(host=host, port=int(port), db=int(db), socket_timeout=timeout)
                r.ping()
                logger.info("✅ Redis broker connection validated")
                return True
        elif broker_url.startswith("amqp"):
            # For RabbitMQ, we'll just check the URL format
            logger.info("✅ RabbitMQ broker URL configured")
            return True
        else:
            logger.warning(f"⚠️ Unknown broker type: {broker_url}")
            return False
    except Exception as e:
        logger.error(f"❌ Broker connection failed: {e}")
        return False

# Initialize Celery
celery_app = Celery("lead_processing")

# Configure Celery
broker_url = get_broker_url()
result_backend = get_result_backend()

# Validate broker connection
if not validate_broker_connection(broker_url):
    logger.error("❌ Failed to validate broker connection. Check your broker configuration.")

# Celery configuration
celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing and queues
    task_routes={
        'tasks.whatsapp_processing.*': {'queue': 'whatsapp_processing'},
        'tasks.email_processing.*': {'queue': 'email_processing'},
        'tasks.lead_processing.*': {'queue': 'lead_processing'},
        'tasks.production_lead_processing.*': {'queue': 'lead_processing'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Task retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Task track started
    task_track_started=True,
    
    # Time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
    
    # Task priorities
    task_default_priority=5,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.tasks"])

# Signal handlers for database connection management
@worker_init.connect
def init_worker(sender=None, **kwargs):
    """Initialize worker database connections."""
    global _db_session
    logger.info("🔄 Initializing worker database connections...")
    
    try:
        # Import database utilities here to avoid circular imports
        from backend.utils.database import get_database_session
        _db_session = get_database_session()
        logger.info("✅ Worker database connections initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize worker database connections: {e}")
        _db_session = None

@worker_shutdown.connect
def shutdown_worker(sender=None, **kwargs):
    """Clean up worker database connections."""
    global _db_session
    logger.info("🔄 Shutting down worker database connections...")
    
    if _db_session:
        try:
            _db_session.close()
            logger.info("✅ Worker database connections closed")
        except Exception as e:
            logger.error(f"❌ Error closing worker database connections: {e}")
        finally:
            _db_session = None

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task pre-run setup."""
    logger.debug(f"🔄 Starting task: {task.name} (ID: {task_id})")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Handle task post-run cleanup."""
    logger.debug(f"✅ Completed task: {task.name} (ID: {task_id}, State: {state})")

# Health check function
def health_check() -> dict:
    """Comprehensive Celery health check."""
    try:
        # Check broker connection
        broker_status = validate_broker_connection(broker_url)
        
        # Check active tasks (if Flower is available)
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            worker_count = len(stats) if stats else 0
            active_count = sum(len(tasks) for tasks in (active_tasks or {}).values())
            scheduled_count = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
        except Exception as e:
            logger.warning(f"Could not get worker stats: {e}")
            worker_count = active_count = scheduled_count = -1
        
        return {
            "status": "healthy" if broker_status else "unhealthy",
            "broker": {
                "status": "connected" if broker_status else "disconnected",
                "url": broker_url.replace(":", "//").split("@")[-1] if "@" in broker_url else broker_url
            },
            "workers": {
                "count": worker_count,
                "active_tasks": active_count,
                "scheduled_tasks": scheduled_count
            },
            "result_backend": result_backend.replace(":", "//").split("@")[-1] if "@" in result_backend else result_backend,
            "timestamp": time.time(),
            "version": celery_app.version()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

# Export health check function
__all__ = ['celery_app', 'health_check', 'validate_broker_connection']