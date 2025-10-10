import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    # Load project-level environment variables if present
    project_env = PROJECT_ROOT / '.env'
    if project_env.exists():
        load_dotenv(dotenv_path=str(project_env))

    # Ensure backend-specific .env values are also available
    backend_env = PROJECT_ROOT / 'backend' / '.env'
    if backend_env.exists():
        load_dotenv(dotenv_path=str(backend_env), override=True)