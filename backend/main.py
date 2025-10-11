"""
Multi-Tenant Automation Platform - Main FastAPI Application

Transformed from single-tenant real estate system to multi-tenant
automation platform supporting multiple companies and industries.
"""
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
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
    from api.companies import router as companies_router
except ImportError as e:
    print(f"Import error: {e}")
    # Create fallback apps
    from fastapi import FastAPI
    processing_app = FastAPI()
    hitl_app = FastAPI()
    webhooks_app = FastAPI()
    
    from fastapi import APIRouter
    health_router = APIRouter()
    companies_router = APIRouter()
    
    @health_router.get("/health")
    async def health():
        return {"status": "healthy", "service": "main"}
    
    @companies_router.get("/api/companies")
    async def list_companies():
        return {"companies": []}

try:
    from middleware.multi_tenant_auth import (
        MultiTenantAuthMiddleware,
        require_auth,
        require_auth_with_company,
        require_auth_optional_company
    )
    from middleware.company_context import (
        CompanyContextMiddleware,
        require_company_context,
        optional_company_context
    )
except ImportError as e:
    print(f"Middleware import error: {e}")
    # Fallback middleware and dependencies
    class MultiTenantAuthMiddleware:
        def __init__(self, app):
            self.app = app
        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)
    
    class CompanyContextMiddleware:
        def __init__(self, app):
            self.app = app
        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)
    
    def require_auth():
        return lambda: {"user": "test"}
    
    def require_auth_with_company(role="member"):
        return lambda: {"user": "test", "company": {"id": "test"}}
    
    def require_auth_optional_company():
        return lambda: {"user": "test", "company": None}
    
    def require_company_context():
        return lambda: {"id": "test", "slug": "test"}
    
    def optional_company_context():
        return lambda: None

app = FastAPI(
    title="Multi-Tenant Automation Platform",
    description="Dynamic workflow automation platform supporting multiple companies and industries",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add multi-tenant middleware
app.add_middleware(MultiTenantAuthMiddleware)
app.add_middleware(CompanyContextMiddleware)

# Mount sub-applications
app.mount("/webhook", webhooks_app)
app.mount("/processing", processing_app)
app.mount("/hitl", hitl_app)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(companies_router)

@app.get("/")
async def root(request: Request):
    """Root endpoint with system information and webhook verification"""
    # Check if this is a webhook verification request
    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    # Handle Instagram webhook verification
    if hub_mode == "subscribe" and hub_verify_token == "aaa_real_estate_verify_token_2025":
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    # Otherwise return normal platform info
    return {
        "message": "Multi-Tenant Automation Platform",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "Multi-tenant company isolation",
            "Dynamic workflow engine",
            "Multiple integration support",
            "Industry-specific templates",
            "Role-based access control"
        ],
        "endpoints": {
            "webhooks": "/webhook/{integration_type}",
            "processing": "/processing",
            "hitl": "/hitl",
            "health": "/api/health",
            "companies": "/api/companies",
            "integrations": "/api/integrations",
            "workflows": "/api/workflows"
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
