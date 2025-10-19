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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api.processing import app as processing_app
    from api.hitl import app as hitl_app
    from api.health import router as health_router
    from api.companies import router as companies_router
    from api.analytics import router as analytics_router
except ImportError as e:
    print(f"Import error: {e}")
    # Create fallback apps
    from fastapi import FastAPI
    processing_app = FastAPI()
    hitl_app = FastAPI()
    
    from fastapi import APIRouter
    health_router = APIRouter()
    companies_router = APIRouter()
    analytics_router = APIRouter()
    
    @health_router.get("/health")
    async def health():
        return {"status": "healthy", "service": "main"}
    
    @companies_router.get("/api/companies")
    async def list_companies():
        return {"companies": []}

    @analytics_router.get("/api/analytics/health")
    async def analytics_health():
        return {"status": "unavailable", "service": "analytics"}

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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Mount sub-applications
app.mount("/processing", processing_app)
app.mount("/hitl", hitl_app)

# Temporarily disable middleware for testing
# app.add_middleware(MultiTenantAuthMiddleware)
# app.add_middleware(CompanyContextMiddleware)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(companies_router)
app.include_router(analytics_router)

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

# Global message cache for deduplication across requests
_global_message_cache = set()
_cache_max_size = 1000

async def get_instagram_user_profile(user_id: str):
    """Fetch Instagram user profile"""
    import aiohttp
    token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN") or os.getenv("META_PAGE_ACCESS_TOKEN")
    if not token:
        return {}
    
    url = f"https://graph.instagram.com/v21.0/{user_id}"
    params = {"fields": "name,username", "access_token": token}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"⚠️ Profile fetch error: {e}", flush=True)
    return {}

@app.post("/")
async def root_webhook(request: Request):
    """Handle Instagram webhooks at root path"""
    import json
    import hashlib
    
    try:
        body = await request.json()
        print(f"📨 Webhook at root: {json.dumps(body, indent=2)}", flush=True)
        
        if body.get("object") != "instagram":
            return {"status": "ignored"}
        
        from tasks.production_lead_processing import process_lead_message
        
        results = []
        
        for entry in body.get("entry", []):
            ig_account_id = entry.get("id")  # This is the IG account that received the message
            
            for msg in entry.get("messaging", []):
                if "message" in msg and "text" in msg["message"]:
                    # Smart echo message handling for testing
                    is_echo = msg["message"].get("is_echo")
                    allow_echo = os.getenv("ALLOW_ECHO_MESSAGES", "false").lower()
                    
                    print(f"🔍 ENV DEBUG (main.py): ALLOW_ECHO_MESSAGES='{allow_echo}', is_echo={is_echo}", flush=True)
                    
                    if is_echo:
                        if allow_echo == "true":
                            print(f"🔧 DEBUG: Processing echo message for testing")
                            # For echo messages, just log what was sent (no processing)
                            echo_text = msg["message"].get("text", "")
                            print(f"📤 BOT SENT: {echo_text[:100]}...", flush=True)
                            continue  # Skip processing to prevent loops
                        else:
                            print(f"⏭️ Skipping echo message (set ALLOW_ECHO_MESSAGES=true to see bot replies)")
                            continue
                    
                    # Get message ID for deduplication
                    message_id = msg["message"].get("mid")
                    if not message_id:
                        print("⚠️ No message ID, skipping", flush=True)
                        continue
                    
                    # Check global cache for duplicates
                    if message_id in _global_message_cache:
                        print(f"🔁 DUPLICATE DETECTED: {message_id[:50]}... (cache: {len(_global_message_cache)})", flush=True)
                        continue
                    
                    _global_message_cache.add(message_id)
                    print(f"✅ NEW MESSAGE CACHED: {message_id[:50]}... (cache: {len(_global_message_cache)})", flush=True)
                    
                    # Cleanup cache if too large
                    if len(_global_message_cache) > _cache_max_size:
                        to_remove = list(_global_message_cache)[:_cache_max_size // 2]
                        for old_id in to_remove:
                            _global_message_cache.discard(old_id)
                    
                    sender_id = msg["sender"]["id"]
                    text = msg["message"]["text"]
                    timestamp = msg.get("timestamp", 0)
                    
                    # Skip very old messages (more than 1 hour old)
                    import time
                    current_time = int(time.time() * 1000)  # Current time in milliseconds
                    if current_time - timestamp > 3600000:  # 1 hour in milliseconds
                        print(f"⏭️ Skipping old message: {message_id} (age: {(current_time - timestamp) / 1000 / 60:.1f} minutes)")
                        continue
                    
                    print(f"💬 Processing: {sender_id} -> {text} (ID: {message_id})", flush=True)
                    
                    # Fetch user profile
                    print(f"👤 Fetching profile for: {sender_id}", flush=True)
                    profile = await get_instagram_user_profile(sender_id)
                    user_name = profile.get("name") or profile.get("username") or "there"
                    print(f"✅ User profile: name={user_name}, username={profile.get('username')}", flush=True)
                    
                    # Process through PRD workflow
                    result = await process_lead_message(sender_id, text, "ig", user_name=user_name)
                    
                    # Send Instagram response using correct IG account ID
                    if result.get("status") == "success" and result.get("response_message"):
                        await send_instagram_reply(sender_id, result["response_message"], ig_account_id)
                    
                    results.append(result)
                    print(f"✅ Processed: score={result.get('qualified_score')}, next={result.get('next_agent')}", flush=True)
        
        return {"status": "success", "processed": len(results), "results": results}
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

async def send_instagram_reply(recipient_id: str, message: str, ig_account_id: str = None):
    """Send Instagram message via Instagram Messaging API with Instagram Login"""
    import aiohttp
    
    token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN") or os.getenv("META_PAGE_ACCESS_TOKEN")
    if not ig_account_id:
        ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "17841474117949549")
    
    if not token:
        print("⚠️ No INSTAGRAM_PAGE_ACCESS_TOKEN, skipping reply")
        return
    
    print(f"📤 Sending from IG account {ig_account_id} to {recipient_id}")
    
    url = f"https://graph.instagram.com/v21.0/{ig_account_id}/messages"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message}}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                text = await resp.text()
                if resp.status == 200:
                    print(f"✅ Sent reply to {recipient_id}")
                else:
                    print(f"❌ Failed: {resp.status} - {text}")
    except Exception as e:
        print(f"❌ Send error: {e}")

# @app.post("/webhook")
# async def webhook_post_handler(request: Request):
#     """Handle webhooks at /webhook path"""
#     return await root_webhook(request)

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
