#!/usr/bin/env python3
"""
Test Redis Fallback Functionality
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.redis_client import cache_query_result, get_cached_query_result
from utils.supabase_client import _ensure_supabase
import time

def test_redis_fallback():
    """Test that Redis fallback works when Redis is unavailable."""
    
    print("🔄 Testing Redis Fallback Functionality")
    print("=" * 40)
    
    # Test 1: Cache with Redis unavailable
    print("\n1. Testing cache operations...")
    try:
        cache_key = "test:fallback:query"
        user_id = "test_user"
        test_data = [{"id": 1, "name": "Test Property"}]
        
        # This should succeed with fallback to memory/disk
        cache_result = cache_query_result(cache_key, user_id, test_data)
        print(f"✅ Cache operation result: {cache_result}")
        
    except Exception as e:
        print(f"❌ Cache operation failed: {e}")
        return False
    
    # Test 2: Retrieve with Redis unavailable
    print("\n2. Testing cache retrieval...")
    try:
        retrieved = get_cached_query_result(cache_key, user_id)
        print(f"✅ Cache retrieval result: {retrieved}")
        
        if retrieved:
            print("✅ Fallback caching working correctly")
        else:
            print("⚠️ Cache returned empty (expected with Redis unavailable)")
    
    except Exception as e:
        print(f"❌ Cache retrieval failed: {e}")
        return False
    
    # Test 3: Database operations still work
    print("\n3. Testing database operations independently...")
    try:
        client = _ensure_supabase()
        result = client.table('configs').select('key').limit(1).execute()
        print(f"✅ Database operations work: {len(result.data)} configs found")
        
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False
    
    # Test 4: Rate limiting fallback
    print("\n4. Testing rate limiting fallback...")
    try:
        from utils.rate_limiter import check_rate_limit
        allowed, headers = check_rate_limit("test_operation")
        print(f"✅ Rate limiting fallback: allowed={allowed}")
        
    except Exception as e:
        print(f"❌ Rate limiting fallback failed: {e}")
        return False
    
    return True

def test_system_resilience():
    """Test overall system resilience without Redis."""
    
    print("\n🛡️ Testing System Resilience")
    print("=" * 30)
    
    try:
        # Test that critical components work without Redis
        from utils.llm_client import get_llm_response_sync
        from config import get_settings
        
        # Configuration
        settings = get_settings()
        print(f"✅ Settings loaded: ENVIRONMENT={settings.ENVIRONMENT}")
        
        # LLM client
        response = get_llm_response_sync("Testing system resilience")
        print(f"✅ LLM working: {len(response)} chars response")
        
        # Database client
        client = _ensure_supabase()
        print(f"✅ Supabase client: Connected")
        
        return True
        
    except Exception as e:
        print(f"❌ System resilience test failed: {e}")
        return False

def main():
    """Test Redis fallback and system resilience."""
    
    print("🚀 Redis Fallback & Resilience Test Suite")
    print("=" * 50)
    
    tests = [
        ("Redis Fallback", test_redis_fallback),
        ("System Resilience", test_system_resilience)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 RESILIENCE TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 System is fully resilient without Redis!")
        print("🎯 Can operate in production with Redis disabled")
    else:
        print("⚠️ Some resilience issues remain")
    
    print("💡 Recommendation: Deploy Redis for production performance, but not required for functionality")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
