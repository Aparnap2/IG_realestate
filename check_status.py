#!/usr/bin/env python3
"""
Quick status check for AAA Real Estate system
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

def check_env_vars():
    """Check if required environment variables are set"""
    print("\n🔍 Checking Environment Variables...")
    
    required = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "META_PAGE_ACCESS_TOKEN": os.getenv("META_PAGE_ACCESS_TOKEN"),
    }
    
    all_set = True
    for key, value in required.items():
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"   ✅ {key}: {masked}")
        else:
            print(f"   ❌ {key}: NOT SET")
            all_set = False
    
    return all_set

def check_supabase():
    """Check Supabase connection"""
    print("\n🔍 Checking Supabase Connection...")
    try:
        from utils.supabase_client import _ensure_supabase
        client = _ensure_supabase()
        print("   ✅ Supabase connected")
        return True
    except Exception as e:
        print(f"   ❌ Supabase error: {e}")
        return False

def check_gemini():
    """Check Gemini API"""
    print("\n🔍 Checking Gemini API...")
    try:
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("   ❌ GOOGLE_API_KEY not set")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Say 'OK'")
        
        if response.text:
            print("   ✅ Gemini 1.5 Flash working")
            return True
        else:
            print("   ⚠️  Gemini returned empty response")
            return False
    except Exception as e:
        print(f"   ❌ Gemini error: {e}")
        return False

def check_openrouter():
    """Check OpenRouter API"""
    print("\n🔍 Checking OpenRouter API...")
    try:
        import aiohttp
        import asyncio
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("   ⚠️  OPENROUTER_API_KEY not set (will use Gemini fallback)")
            return True
        
        async def test_openrouter():
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "meta-llama/llama-3.2-3b-instruct:free",
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 10
                }
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    return response.status, await response.text()
        
        status, text = asyncio.run(test_openrouter())
        
        if status == 200:
            print("   ✅ OpenRouter working")
            return True
        elif status == 429:
            print("   ⚠️  OpenRouter rate limited (will use Gemini fallback)")
            print("   💡 Add credits at: https://openrouter.ai/credits")
            return True  # Not a blocker, we have fallback
        else:
            print(f"   ❌ OpenRouter error: {status} - {text[:100]}")
            return False
            
    except Exception as e:
        print(f"   ❌ OpenRouter check failed: {e}")
        return False

def check_redis():
    """Check Redis connection"""
    print("\n🔍 Checking Redis Connection...")
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
        print("   ✅ Redis connected")
        return True
    except Exception as e:
        print(f"   ⚠️  Redis not available: {e}")
        print("   💡 Start Redis: redis-server")
        return False

def main():
    """Run all status checks"""
    print("=" * 60)
    print("🏥 AAA Real Estate - System Health Check")
    print("=" * 60)
    
    checks = {
        "Environment Variables": check_env_vars(),
        "Supabase Database": check_supabase(),
        "Gemini API": check_gemini(),
        "OpenRouter API": check_openrouter(),
        "Redis Cache": check_redis(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Health Check Summary")
    print("=" * 60)
    
    for check_name, passed in checks.items():
        status = "✅ HEALTHY" if passed else "❌ ISSUE"
        print(f"{status} - {check_name}")
    
    critical_checks = ["Environment Variables", "Supabase Database", "Gemini API"]
    critical_passed = all(checks[c] for c in critical_checks if c in checks)
    
    print("\n" + "=" * 60)
    if critical_passed:
        print("✅ System is operational!")
        print("\n💡 Tips:")
        if not checks.get("OpenRouter API"):
            print("   - OpenRouter rate limited: Add credits or use Gemini")
        if not checks.get("Redis Cache"):
            print("   - Redis offline: Start with 'redis-server'")
    else:
        print("⚠️  Critical issues detected!")
        print("\n🔧 Next Steps:")
        if not checks.get("Supabase Database"):
            print("   1. Run fix_rls_policies.sql in Supabase SQL Editor")
        if not checks.get("Gemini API"):
            print("   2. Check GOOGLE_API_KEY in backend/.env")
        print("   3. See QUICK_FIX_GUIDE.md for detailed instructions")
    
    print("=" * 60)
    
    return critical_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
