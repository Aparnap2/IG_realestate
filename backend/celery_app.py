from celery import Celery
import os

# Initialize Celery
celery_app = Celery("lead_processing")

# Configure Celery with Redis as broker and backend
celery_app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.tasks"])