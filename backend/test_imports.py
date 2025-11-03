#!/usr/bin/env python3
"""
Test script to verify that imports work correctly from within the backend directory
"""
import sys
import os

# Add current directory to path (simulating the same context as main.py)
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def test_imports():
    """Test the specific imports mentioned in the original error"""
    results = {}
    
    # Test Redis import
    try:
        from utils.redis_client import redis_client
        results['Redis'] = "✅ SUCCESS"
        print("✅ Redis import: SUCCESS")
    except ImportError as e:
        results['Redis'] = f"❌ FAILED: {e}"
        print(f"❌ Redis import failed: {e}")
    
    # Test Processing import
    try:
        from api.processing import app as processing_app
        results['Processing'] = "✅ SUCCESS"
        print("✅ Processing app import: SUCCESS")
    except ImportError as e:
        results['Processing'] = f"❌ FAILED: {e}"
        print(f"❌ Processing app import failed: {e}")
    
    # Test Health router import
    try:
        from api.health import router as health_router
        results['Health'] = "✅ SUCCESS"
        print("✅ Health router import: SUCCESS")
    except ImportError as e:
        results['Health'] = f"❌ FAILED: {e}"
        print(f"❌ Health router import failed: {e}")
    
    # Test Analytics router import
    try:
        from api.analytics import router as analytics_router
        results['Analytics'] = "✅ SUCCESS"
        print("✅ Analytics router import: SUCCESS")
    except ImportError as e:
        results['Analytics'] = f"❌ FAILED: {e}"
        print(f"❌ Analytics router import failed: {e}")
    
    # Test Webhooks router import
    try:
        from api.webhooks import router as webhooks_router
        results['Webhooks'] = "✅ SUCCESS"
        print("✅ Webhooks router import: SUCCESS")
    except ImportError as e:
        results['Webhooks'] = f"❌ FAILED: {e}"
        print(f"❌ Webhooks router import failed: {e}")
    
    # Summary
    print("\n" + "="*50)
    print("IMPORT TEST SUMMARY:")
    print("="*50)
    
    for module, status in results.items():
        print(f"{module:12}: {status}")
    
    failed_imports = [k for k, v in results.items() if "❌" in v]
    if failed_imports:
        print(f"\n❌ {len(failed_imports)} import(s) failed: {', '.join(failed_imports)}")
        return False
    else:
        print("\n✅ All imports successful!")
        return True

if __name__ == "__main__":
    print("Testing import paths from within backend directory...")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path includes current dir: {os.getcwd() in sys.path}")
    print("-" * 50)
    
    success = test_imports()
    exit(0 if success else 1)