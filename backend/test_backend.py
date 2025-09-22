#!/usr/bin/env python3
"""
Test script to verify backend functionality and integrations.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import fastapi
        print("  ✓ FastAPI")
    except ImportError as e:
        print(f"  ✗ FastAPI: {e}")
    
    try:
        import langgraph
        print("  ✓ LangGraph")
    except ImportError as e:
        print(f"  ✗ LangGraph: {e}")
    
    try:
        from langgraph.checkpoint.redis import RedisSaver
        print("  ✓ LangGraph Redis Checkpointer")
    except ImportError as e:
        print(f"  ✗ LangGraph Redis Checkpointer: {e}")
    
    try:
        import redis
        print("  ✓ Redis")
    except ImportError as e:
        print(f"  ✗ Redis: {e}")
    
    try:
        import supabase
        print("  ✓ Supabase")
    except ImportError as e:
        print(f"  ✗ Supabase: {e}")
    
    try:
        import openai
        print("  ✓ OpenAI")
    except ImportError as e:
        print(f"  ✗ OpenAI: {e}")
    
    try:
        import celery
        print("  ✓ Celery")
    except ImportError as e:
        print(f"  ✗ Celery: {e}")

def test_environment():
    """Test environment variables"""
    print("\nTesting environment variables...")
    
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY", 
        "REDIS_URL",
        "OPENROUTER_API_KEY",
        "HUBSPOT_API_KEY"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: {'***' + value[-4:] if len(value) > 4 else '***'}")
        else:
            print(f"  ✗ {var}: Not set")

def test_redis_connection():
    """Test Redis connection"""
    print("\nTesting Redis connection...")
    
    try:
        from utils.redis_client import test_redis_connection, redis_health_check
        
        if test_redis_connection():
            print("  ✓ Redis connection successful")
            
            health = redis_health_check()
            print(f"  ✓ Redis health: {health['status']}")
            if health['status'] == 'healthy':
                print(f"    - Connected clients: {health.get('connected_clients', 'unknown')}")
                print(f"    - Memory usage: {health.get('used_memory_human', 'unknown')}")
        else:
            print("  ✗ Redis connection failed")
            
    except Exception as e:
        print(f"  ✗ Redis test error: {e}")

def test_supabase_connection():
    """Test Supabase connection"""
    print("\nTesting Supabase connection...")
    
    try:
        from supabase import create_client
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("  ✗ Supabase credentials not configured")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Test basic connection (this will fail if tables don't exist, but connection works)
        try:
            response = supabase.table("leads").select("id").limit(1).execute()
            print("  ✓ Supabase connection and leads table accessible")
        except Exception as e:
            if "Could not find the table" in str(e):
                print("  ✓ Supabase connection successful (tables need to be created)")
            else:
                print(f"  ✗ Supabase error: {e}")
                
    except Exception as e:
        print(f"  ✗ Supabase test error: {e}")

def test_workflow_creation():
    """Test workflow creation"""
    print("\nTesting workflow creation...")
    
    try:
        # Test if we can import our workflow modules
        from workflow import create_workflow
        print("  ✓ Workflow module imported")
        
        # Note: We can't actually create the workflow without Redis and proper setup
        print("  ℹ Workflow creation requires Redis and database setup")
        
    except Exception as e:
        print(f"  ✗ Workflow test error: {e}")

def test_api_modules():
    """Test API module imports"""
    print("\nTesting API modules...")
    
    try:
        from api.webhooks import app as webhooks_app
        print("  ✓ Webhooks API")
    except Exception as e:
        print(f"  ✗ Webhooks API: {e}")
    
    try:
        from api.hitl import app as hitl_app
        print("  ✓ HITL API")
    except Exception as e:
        print(f"  ✗ HITL API: {e}")
    
    try:
        from api.processing import app as processing_app
        print("  ✓ Processing API")
    except Exception as e:
        print(f"  ✗ Processing API: {e}")

def main():
    """Run all tests"""
    print("=== AAA Real Estate Backend Test Suite ===\n")
    
    test_imports()
    test_environment()
    test_redis_connection()
    test_supabase_connection()
    test_workflow_creation()
    test_api_modules()
    
    print("\n=== Test Summary ===")
    print("✓ = Working correctly")
    print("✗ = Needs attention")
    print("ℹ = Information/Warning")
    
    print("\nNext steps:")
    print("1. Ensure Redis is running (docker-compose up redis)")
    print("2. Create database tables in Supabase (see manual instructions)")
    print("3. Configure remaining API keys (Meta, Google)")
    print("4. Test the full workflow")

if __name__ == "__main__":
    main()
