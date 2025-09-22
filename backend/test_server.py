#!/usr/bin/env python3
"""
Simple test server to verify backend functionality.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = FastAPI(
    title="AAA Real Estate Test Server",
    description="Test server for backend verification",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AAA Real Estate Backend Test Server",
        "status": "operational",
        "environment": {
            "supabase_configured": bool(os.getenv("SUPABASE_URL")),
            "redis_configured": bool(os.getenv("REDIS_URL")),
            "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY")),
            "hubspot_configured": bool(os.getenv("HUBSPOT_API_KEY"))
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        # Test Redis connection
        import redis
        redis_client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True
        )
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    try:
        # Test Supabase connection
        from supabase import create_client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            # Try a simple query
            try:
                supabase.table("leads").select("id").limit(1).execute()
                supabase_status = "healthy"
            except Exception as e:
                if "Could not find the table" in str(e):
                    supabase_status = "connected (tables missing)"
                else:
                    supabase_status = f"error: {str(e)}"
        else:
            supabase_status = "not configured"
    except Exception as e:
        supabase_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "components": {
            "redis": redis_status,
            "supabase": supabase_status
        }
    }

@app.post("/test/webhook")
async def test_webhook(data: dict):
    """Test webhook endpoint"""
    return {
        "status": "received",
        "data": data,
        "message": "Webhook test successful"
    }

@app.get("/test/workflow")
async def test_workflow():
    """Test workflow creation"""
    try:
        # Test if we can create a basic workflow
        from langgraph.graph import StateGraph
        from typing import TypedDict
        
        class TestState(TypedDict):
            message: str
        
        def test_node(state: TestState):
            return {"message": "Workflow test successful"}
        
        workflow = StateGraph(TestState)
        workflow.add_node("test", test_node)
        workflow.set_entry_point("test")
        workflow.set_finish_point("test")
        
        compiled = workflow.compile()
        result = compiled.invoke({"message": "test"})
        
        return {
            "status": "success",
            "result": result,
            "message": "Workflow creation successful"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Workflow creation failed"
        }

if __name__ == "__main__":
    print("Starting AAA Real Estate Test Server...")
    print(f"Environment loaded: {bool(os.getenv('SUPABASE_URL'))}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
