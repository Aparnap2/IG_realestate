#!/usr/bin/env python3
"""
Production Instagram DM Automation Server
Following the exact guide provided for Instagram Messaging API integration.

This implements the complete PRD workflow with proper Instagram webhook handling.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Load environment variables
load_dotenv(dotenv_path='backend/.env')

# Import our production processor
from tasks.production_lead_processing import process_lead_message

app = FastAPI(
    title="AAA Real Estate Instagram DM Automation",
    description="Production-grade Instagram DM automation for real estate lead capture",
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

# Configuration
VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN", "aaa_real_estate_verify_token_2025")
PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN")

print(f"🔧 Instagram Webhook Server Configuration:")
print(f"   Verify Token: {'✅ Set' if VERIFY_TOKEN else '❌ Missing'}")
print(f"   Page Access Token: {'✅ Set' if PAGE_ACCESS_TOKEN else '❌ Missing'}")

@app.get("/")
async def root(request: Request):
    """Root endpoint - handles both info requests and webhook verification"""
    # Check if this is a webhook verification request
    if request.query_params.get("hub.mode") == "subscribe":
        print("⚠️  Webhook verification received at root path '/' - handling it")
        print("💡 Tip: Configure Instagram webhook URL to include /webhook path")
        
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token") 
        challenge = request.query_params.get("hub.challenge")
        
        print(f"🔍 Webhook verification request at /:")
        print(f"   Mode: {mode}")
        print(f"   Token: {token}")
        print(f"   Challenge: {challenge}")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ Instagram webhook verification successful!")
            return int(challenge)
        else:
            print("❌ Instagram webhook verification failed!")
            raise HTTPException(status_code=403, detail="Verification failed")
    
    # Otherwise return normal root response
    return {
        "service": "AAA Real Estate Instagram DM Automation",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "webhook_verification": "GET /webhook (or GET /)",
            "webhook_receiver": "POST /webhook (or POST /)", 
            "health": "GET /health",
            "test": "POST /test"
        },
        "features": [
            "Instagram DM automation",
            "Real estate lead qualification",
            "Automated property matching",
            "Calendar scheduling integration",
            "HITL for high-value leads"
        ]
    }

@app.post("/")
async def root_webhook(request: Request):
    """Handle Instagram webhooks sent to root path (common misconfiguration)"""
    print("⚠️  Webhook received at root path '/' - redirecting to webhook handler")
    print("💡 Tip: Configure Instagram webhook URL to include /webhook path")
    return await receive_instagram_webhook(request)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": "connected",
            "redis": "connected", 
            "instagram_api": "configured" if PAGE_ACCESS_TOKEN else "not_configured"
        }
    }

@app.get("/webhook")
async def verify_instagram_webhook(request: Request):
    """
    Instagram webhook verification endpoint.
    
    Instagram calls this endpoint to verify the webhook URL.
    Must return the hub.challenge value to complete verification.
    """
    try:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token") 
        challenge = request.query_params.get("hub.challenge")
        
        print(f"🔍 Webhook verification request at /webhook:")
        print(f"   Mode: {mode}")
        print(f"   Token: {token}")
        print(f"   Challenge: {challenge}")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ Instagram webhook verification successful!")
            return int(challenge)  # Must return challenge as integer for Instagram API
        else:
            print("❌ Instagram webhook verification failed!")
            print(f"   Expected token: {VERIFY_TOKEN}")
            print(f"   Received token: {token}")
            print(f"   Mode: {mode}")
            raise HTTPException(status_code=403, detail="Instagram webhook verification failed")
            
    except Exception as e:
        print(f"❌ Webhook verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def receive_instagram_webhook(request: Request):
    """
    Instagram webhook receiver endpoint.
    
    Instagram sends DM events to this endpoint.
    Processes messages through the complete PRD workflow.
    """
    try:
        body = await request.json()
        
        print(f"📨 Received Instagram webhook:")
        print(f"   Body: {json.dumps(body, indent=2)}")
        
        # Check if it's Instagram messaging event
        if body.get("object") != "instagram":
            print(f"⚠️  Not an Instagram event: {body.get('object')}")
            return {"status": "ignored", "reason": "not_instagram_event"}
        
        # Process Instagram messaging events specifically
        processed_leads = []
        
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                
                print(f"👤 Processing Instagram message from sender: {sender_id}")
                
                # Check if it's a message (not postback, delivery, etc.)
                if messaging_event.get("message"):
                    message_text = messaging_event["message"].get("text", "")
                    
                    if message_text:  # Only process text messages
                        print(f"💬 Instagram Message: {message_text}")
                        
                        # Process through our production lead processor
                        result = await process_lead_message(sender_id, message_text, "ig")
                        
                        if result["status"] == "success":
                            print(f"✅ Lead processed successfully:")
                            print(f"   Lead ID: {result['lead_id']}")
                            print(f"   Score: {result['qualified_score']}")
                            print(f"   Next Agent: {result['next_agent']}")
                            print(f"   Properties Found: {result['properties_found']}")
                            print(f"   HITL Needed: {result['interrupt_needed']}")
                            
                            # Send auto-reply via Instagram Send API
                            await send_instagram_message(sender_id, result['response_message'])
                            
                            processed_leads.append({
                                "sender_id": sender_id,
                                "lead_id": result['lead_id'],
                                "qualified_score": result['qualified_score'],
                                "next_agent": result['next_agent']
                            })
                        else:
                            print(f"❌ Lead processing failed: {result['error']}")
                            # Send fallback message
                            await send_instagram_message(
                                sender_id, 
                                "Thank you for your message! We'll get back to you shortly."
                            )
                    else:
                        print("⚠️  Empty message text, skipping")
                else:
                    print("⚠️  Not a message event, skipping")
        
        return {
            "status": "success",
            "processed_leads": len(processed_leads),
            "leads": processed_leads,
            "timestamp": datetime.now().isoformat(),
            "object": body.get("object")  # Confirm it's Instagram
        }
        
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        import traceback
        traceback.print_exc()
        
        # Still return 200 to Instagram to avoid retries
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def process_instagram_webhook_async(body: dict):
    """
    Process Instagram webhook events asynchronously.
    
    This ensures we return 200 OK immediately to Meta while processing
    the events in the background to avoid webhook timeouts.
    """
    try:
        # Process Instagram messaging events specifically
        processed_leads = []
        
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                
                # Check if it's a message (not postback, delivery, etc.)
                if messaging_event.get("message"):
                    message_text = messaging_event["message"].get("text", "")
                    
                    if message_text:  # Only process text messages
                        # Process through our production lead processor
                        result = await process_lead_message(sender_id, message_text, "ig")
                        
                        if result["status"] == "success":
                            # Send auto-reply via Instagram Send API
                            await send_instagram_message(sender_id, result['response_message'])
                            
                            processed_leads.append({
                                "sender_id": sender_id,
                                "lead_id": result['lead_id'],
                                "qualified_score": result['qualified_score'],
                                "next_agent": result['next_agent']
                            })
        
        print(f"✅ Async processing completed for {len(processed_leads)} leads")
        
    except Exception as e:
        print(f"❌ Async webhook processing error: {e}")
        import traceback
        traceback.print_exc()
async def send_instagram_message(recipient_id: str, message_text: str):
    """
    Send a message via Instagram Messaging API.
    
    Args:
        recipient_id: Instagram user ID (sender ID from webhook)
        message_text: Message to send
    """
    if not PAGE_ACCESS_TOKEN:
        print("❌ No PAGE_ACCESS_TOKEN configured, cannot send message")
        return False
    
    try:
        import aiohttp
        
        url = "https://graph.facebook.com/v21.0/me/messages"
        headers = {"Content-Type": "application/json"}
        params = {"access_token": PAGE_ACCESS_TOKEN}
        
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text},
            "messaging_type": "RESPONSE"  # Required for Instagram business messaging compliance
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Message sent successfully: {result.get('message_id')}")
                    return True
                else:
                    error_text = await response.text()
                    error_data = await response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    print(f"❌ Failed to send Instagram message: {response.status} - {error_text}")
                    
                    # Handle specific Instagram API errors
                    if response.status == 400:
                        error_code = error_data.get('error', {}).get('code', 0)
                        if error_code == 613:  # Calls to this API have exceeded the rate limit
                            print("⚠️  Instagram API rate limit exceeded")
                        elif error_code == 100:  # Invalid parameter
                            print("⚠️  Invalid parameter in Instagram API request")
                        elif error_code == 200:  # Permissions error
                            print("⚠️  Missing permissions for Instagram API")
                    
                    return False
                    
    except Exception as e:
        print(f"❌ Error sending Instagram message: {e}")
        return False

@app.post("/test")
async def test_lead_processing(request: Request):
    """
    Test endpoint for lead processing without Instagram webhook.
    Useful for testing the complete workflow.
    """
    try:
        body = await request.json()
        
        # Extract test data
        user_id = body.get("user_id", "test_user_123")
        message = body.get("message", "Looking for 2BHK in Miami, budget $350k")
        
        print(f"🧪 Testing lead processing:")
        print(f"   User ID: {user_id}")
        print(f"   Message: {message}")
        
        # Process through production workflow
        result = await process_lead_message(user_id, message, "ig")
        
        return {
            "status": "success",
            "test_result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Test processing error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/leads")
async def get_recent_leads():
    """Get recent leads for monitoring"""
    try:
        from utils.supabase_client import supabase
        
        # Get recent leads
        response = supabase.table('leads').select('*').order('created_at', desc=True).limit(10).execute()
        
        return {
            "status": "success",
            "leads": response.data,
            "count": len(response.data)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    print("🚀 Starting AAA Real Estate Instagram DM Automation Server")
    print("=" * 60)
    print("📋 Setup Instructions:")
    print("1. Configure Instagram Business account")
    print("2. Create Meta App with Messenger product")
    print("3. Set webhook URL to: https://yourdomain.com/webhook")
    print("4. Set verify token in environment: INSTAGRAM_VERIFY_TOKEN")
    print("5. Get Page Access Token and set: META_PAGE_ACCESS_TOKEN")
    print("=" * 60)
    
    # Run server
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )