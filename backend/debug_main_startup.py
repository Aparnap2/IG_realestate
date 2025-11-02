#!/usr/bin/env python3
"""
Debug script to diagnose startup issues in main.py
"""
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def diagnose_python_path():
    """Diagnose Python path and module import issues"""
    logger.info("🔍 DIAGNOSING PYTHON PATH ISSUES")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python path: {sys.path}")
    
    # Check if backend directory exists and its contents
    backend_dir = Path("backend")
    if backend_dir.exists():
        logger.info(f"✅ Backend directory exists: {backend_dir.absolute()}")
        logger.info(f"Backend directory contents: {list(backend_dir.iterdir())}")
    else:
        logger.error(f"❌ Backend directory not found: {backend_dir.absolute()}")
    
    # Check for __init__.py files
    backend_init = backend_dir / "__init__.py"
    if backend_init.exists():
        logger.info("✅ backend/__init__.py exists")
    else:
        logger.error("❌ backend/__init__.py missing")
    
    # Test module imports
    try:
        logger.info("🧪 Testing 'backend' module import...")
        import backend
        logger.info(f"✅ Successfully imported backend module: {backend}")
        logger.info(f"Backend module path: {backend.__file__}")
    except ImportError as e:
        logger.error(f"❌ Failed to import backend: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error importing backend: {e}")

def diagnose_llm_client():
    """Diagnose LLM client async issues"""
    logger.info("🔍 DIAGNOSING LLM CLIENT ISSUES")
    
    try:
        # Test import of LLM client
        from utils.llm_client import LLMClient
        logger.info("✅ Successfully imported LLMClient")
        
        # Check if we can create an instance
        llm_client = LLMClient()
        logger.info("✅ Successfully created LLMClient instance")
        
        # Test async event loop detection
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            logger.warning(f"⚠️ Async event loop already running: {loop}")
            logger.warning("This may cause conflicts with new async calls")
        except RuntimeError:
            logger.info("✅ No async event loop currently running")
            
    except ImportError as e:
        logger.error(f"❌ Failed to import LLMClient: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error with LLMClient: {e}")

def diagnose_dependencies():
    """Check key dependencies"""
    logger.info("🔍 DIAGNOSING DEPENDENCIES")
    
    dependencies = [
        'fastapi',
        'uvicorn', 
        'celery',
        'redis',
        'httpx',
        'supabase',
        'asyncio',
        'temporal'
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            logger.info(f"✅ {dep} available")
        except ImportError:
            logger.error(f"❌ {dep} missing or failed to import")
        except Exception as e:
            logger.error(f"⚠️ {dep} import issue: {e}")

def main():
    """Run all diagnostics"""
    logger.info("🚀 STARTING COMPREHENSIVE DIAGNOSTICS")
    logger.info("=" * 60)
    
    # Change to backend directory if we're not already there
    if not Path("main.py").exists() and Path("backend/main.py").exists():
        logger.info("Switching to backend directory...")
        os.chdir("backend")
    
    diagnose_python_path()
    logger.info("-" * 40)
    
    diagnose_llm_client()
    logger.info("-" * 40)
    
    diagnose_dependencies()
    logger.info("=" * 60)
    logger.info("🏁 DIAGNOSTICS COMPLETE")

if __name__ == "__main__":
    main()