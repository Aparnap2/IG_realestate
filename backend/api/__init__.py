# Webhooks now handled directly in main.py
import sys
import os

# Add backend directory to Python path for proper imports when running from backend dir
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from processing import app as processing_app
from health import router as health_router