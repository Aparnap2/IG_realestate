#!/usr/bin/env python3
"""
Test script to verify import fixes are working correctly.
"""

import sys
import os

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def test_imports():
    """Test all the imports that were previously failing."""
    results = []
    
    # Test 1: Agent tools import
    try:
        from tools.agent_tools import send_instagram_message
        results.append("✅ Agent tools import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Agent tools import: FAILED - {e}")
    
    # Test 2: Processing import
    try:
        from api.processing import app as processing_app
        results.append("✅ Processing API import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Processing API import: FAILED - {e}")
    
    # Test 3: Webhooks import
    try:
        from api.webhooks import router as webhooks_router
        results.append("✅ Webhooks API import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Webhooks API import: FAILED - {e}")
    
    # Test 4: Main API imports
    try:
        from api.health import router as health_router
        results.append("✅ Health API import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Health API import: FAILED - {e}")
    
    try:
        from api.analytics import router as analytics_router
        results.append("✅ Analytics API import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Analytics API import: FAILED - {e}")
    
    # Test 5: Redis and other utils
    try:
        from utils.redis_client import redis_client
        results.append("✅ Redis client import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Redis client import: FAILED - {e}")
    
    # Test 6: Supabase import
    try:
        from utils.supabase_client import supabase
        results.append("✅ Supabase client import: SUCCESS")
    except Exception as e:
        results.append(f"❌ Supabase client import: FAILED - {e}")
    
    print("=== Import Test Results ===")
    print()
    for result in results:
        print(result)
    
    # Summary
    success_count = sum(1 for r in results if r.startswith("✅"))
    total_count = len(results)
    
    print()
    print(f"Summary: {success_count}/{total_count} imports successful")
    
    if success_count == total_count:
        print("🎉 All imports working correctly!")
        return True
    else:
        print("⚠️ Some imports still failing")
        return False

if __name__ == "__main__":
    test_imports()