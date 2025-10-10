"""
Webhook API endpoints for Instagram integration.

This module handles webhook verification and processing for Meta APIs
(Instagram Graph API) according to PRD specifications.
"""
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import hashlib
import hmac
import os
import json
import logging
from typing import Optional, Dict, Any, List
import uuid
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tasks.lead_processing import process_webhook
except ImportError:
    # Fallback for testing
    def process_webhook(data):
        class MockTask:
            def __init__(self):
                self.id = str(uuid.uuid4())
        return MockTask()

try:
    from utils.observability import track_performance, metrics_collector
except ImportError:
    # Fallback decorators for testing
    def track_performance(func):
        return func
    
    class MockMetricsCollector:
        def increment_counter(self, name, value=1):
            pass
    
    metrics_collector = MockMetricsCollector()

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Meta API configuration
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "aaa_real_estate_verify_token_2025")

class WebhookPayload(BaseModel):
    """Base webhook payload model"""
    entry: List[Dict[str, Any]]
    object: str

class InstagramWebhookEntry(BaseModel):
    """Instagram webhook entry model"""
    id: str
    time: int
    messaging: Optional[List[Dict[str, Any]]] = None



def verify_meta_signature(payload: bytes, signature: str) -> bool:
    """
    Verify the signature of a Meta webhook request.
    
    Args:
        payload: Raw request payload
        signature: X-Hub-Signature-256 header value
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not META_APP_SECRET:
        logger.warning("Missing signature or app secret")
        return False
    
    try:
        # Remove 'sha256=' prefix
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        # Calculate expected signature
        expected_signature = hmac.new(
            META_APP_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return False

@app.get("/webhook")
async def webhook_verification(
    hub_mode: Optional[str] = None,
    hub_challenge: Optional[str] = None,
    hub_verify_token: Optional[str] = None
):
    """
    Handle webhook verification for Meta APIs.
    
    This endpoint handles the initial webhook verification process
    required by Meta APIs.
    """
    logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")
    
    if (hub_mode == "subscribe" and 
        hub_verify_token == META_VERIFY_TOKEN and 
        hub_challenge):
        logger.info("Webhook verification successful")
        return PlainTextResponse(content=str(hub_challenge), status_code=200)
    
    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
@track_performance
async def instagram_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    Handle Instagram Graph API webhooks.
    
    This endpoint receives and processes Instagram messages according
    to the PRD specifications.
    """
    try:
        # Get raw payload for signature verification
        payload = await request.body()
        
        # Verify signature (skip in development)
        if os.getenv("ENVIRONMENT") != "development":
            if not verify_meta_signature(payload, x_hub_signature_256 or ""):
                logger.warning("Invalid Instagram webhook signature")
                raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse JSON payload
        try:
            webhook_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Instagram webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        logger.info(f"Instagram webhook received: {webhook_data}")
        
        # Validate webhook structure
        if webhook_data.get("object") != "instagram":
            logger.warning(f"Unexpected object type: {webhook_data.get('object')}")
            return {"status": "ignored"}
        
        # Process each entry
        results = []
        for entry in webhook_data.get("entry", []):
            if "messaging" in entry:
                for messaging_event in entry["messaging"]:
                    # Check if it's a message event
                    if "message" in messaging_event and "text" in messaging_event["message"]:
                        # Extract message data
                        sender_id = messaging_event.get("sender", {}).get("id")
                        message_text = messaging_event.get("message", {}).get("text")
                        message_id = messaging_event.get("message", {}).get("mid")
                        
                        if sender_id and message_text:
                            # Prepare webhook data for processing
                            processed_webhook_data = {
                                "channel": "ig",
                                "entry": [{
                                    "messaging": [{
                                        "sender": {"id": sender_id},
                                        "message": {"text": message_text, "mid": message_id}
                                    }]
                                }]
                            }
                            
                            # Queue for processing
                            task_result = process_webhook(processed_webhook_data)
                            
                            results.append({
                                "sender_id": sender_id,
                                "task_id": task_result.id,
                                "status": "queued"
                            })
                            
                            logger.info(f"Instagram message queued: {sender_id} -> {task_result.id}")
        
        # Update metrics
        metrics_collector.increment_counter("instagram_webhooks_received")
        metrics_collector.increment_counter("instagram_messages_processed", len(results))

        return {
            "status": "success",
            "processed": len(results),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Instagram webhook: {e}")
        metrics_collector.increment_counter("instagram_webhook_errors")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/webhook/health")
async def webhook_health():
    """Health check endpoint for webhooks"""
    try:
        return {
            "status": "healthy",
            "webhook_service": "operational",
            "meta_app_secret_configured": bool(META_APP_SECRET),
            "verify_token_configured": bool(META_VERIFY_TOKEN)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "webhook_service": "operational"
        }

# Test endpoint for development
@app.post("/webhook/test")
async def test_webhook(test_data: Dict[str, Any]):
    """
    Test endpoint for webhook processing during development.
    
    This endpoint allows testing the webhook processing pipeline
    without requiring actual Meta API integration.
    """
    try:
        # Add test channel identifier
        test_data["channel"] = test_data.get("channel", "test")
        
        # Queue for processing
        task_result = process_webhook(test_data)
        
        return {
            "status": "success",
            "task_id": task_result.id,
            "test_data": test_data
        }
        
    except Exception as e:
        logger.error(f"Error processing test webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))