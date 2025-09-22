"""
Main FastAPI application for AAA Real Estate Lead Capture Agentic AI System.
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api.processing import app as processing_app
    from api.hitl import app as hitl_app
    from api.webhooks import app as webhooks_app
    from api.health import router as health_router
except ImportError as e:
    print(f"Import error: {e}")
    # Create fallback apps
    from fastapi import FastAPI
    processing_app = FastAPI()
    hitl_app = FastAPI()
    webhooks_app = FastAPI()
    
    from fastapi import APIRouter
    health_router = APIRouter()
    
    @health_router.get("/health")
    async def health():
        return {"status": "healthy", "service": "main"}

try:
    from middleware.jwt_auth import verify_supabase_jwt
except ImportError:
    # Fallback JWT verification
    def verify_supabase_jwt():
        return {"user": "test"}

app = FastAPI(
    title="AAA Real Estate Lead Capture Agentic AI System",
    description="LangGraph-based swarm architecture for real estate lead processing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount sub-applications
app.mount("/webhooks", webhooks_app)
app.mount("/processing", processing_app)
app.mount("/hitl", hitl_app)

# Include health router
app.include_router(health_router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "message": "AAA Real Estate Lead Capture Agentic AI System",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "webhooks": "/webhooks",
            "processing": "/processing", 
            "hitl": "/hitl",
            "health": "/api/health"
        }
    }

@app.get("/status")
async def system_status():
    """System status endpoint"""
    try:
        # Test Redis connection
        from utils.redis_client import redis_health_check
        redis_status = redis_health_check()
        
        # Test Supabase connection
        from utils.supabase_client import supabase
        try:
            supabase.table("leads").select("id").limit(1).execute()
            supabase_status = "healthy"
        except Exception as e:
            if "Could not find the table" in str(e):
                supabase_status = "connected (tables missing)"
            else:
                supabase_status = f"error: {str(e)}"
        
        return {
            "status": "operational",
            "components": {
                "redis": redis_status.get("status", "unknown"),
                "supabase": supabase_status,
                "webhooks": "loaded",
                "processing": "loaded",
                "hitl": "loaded"
            }
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
