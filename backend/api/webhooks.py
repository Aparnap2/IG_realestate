from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import hashlib
import hmac
import os
from ..models.lead import Lead
from ..utils.supabase_client import save_lead
from ..utils.task_queue import queue_lead_for_processing
import json

app = FastAPI()

class WebhookPayload(BaseModel):
    entry: list
    object: str

def verify_meta_signature(request: Request, payload: str) -> bool:
    """
    Verify the signature of a Meta webhook request.
    
    Args:
        request: The incoming request
        payload: The raw payload
        
    Returns:
        True if signature is valid, False otherwise
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        return False
    
    expected_signature = "sha256=" + hmac.new(
        os.getenv("META_APP_SECRET").encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.post("/webhook/ig")
async def instagram_webhook(request: Request):
    """
    Handle Instagram webhook events.
    """
    payload = await request.body()
    payload_str = payload.decode()
    
    # Verify signature
    if not verify_meta_signature(request, payload_str):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    try:
        data = json.loads(payload_str)
        # Process Instagram message
        process_instagram_message(data)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Handle WhatsApp webhook events.
    """
    payload = await request.body()
    payload_str = payload.decode()
    
    # Verify signature
    if not verify_meta_signature(request, payload_str):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    try:
        data = json.loads(payload_str)
        # Process WhatsApp message
        process_whatsapp_message(data)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def process_instagram_message(data):
    """
    Process an Instagram message.
    
    Args:
        data: The webhook data
    """
    # Extract message details
    for entry in data.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            if messaging_event.get("message"):
                sender_id = messaging_event["sender"]["id"]
                message_text = messaging_event["message"]["text"]
                
                # Create lead object
                lead = Lead(
                    id=sender_id,  # Using sender ID as lead ID for now
                    channel="ig",
                    user_id=sender_id,
                    message=message_text
                )
                
                # Save lead to database
                save_lead(lead.model_dump())
                
                # Queue lead for asynchronous processing
                queue_lead_for_processing(lead)

def process_whatsapp_message(data):
    """
    Process a WhatsApp message.
    
    Args:
        data: The webhook data
    """
    # Extract message details
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "messages":
                for message in change.get("value", {}).get("messages", []):
                    if message.get("type") == "text":
                        sender_id = message["from"]
                        message_text = message["text"]["body"]
                        
                        # Create lead object
                        lead = Lead(
                            id=sender_id,  # Using sender ID as lead ID for now
                            channel="whatsapp",
                            user_id=sender_id,
                            message=message_text
                        )
                        
                        # Save lead to database
                        save_lead(lead.model_dump())
                        
                        # Queue lead for asynchronous processing
                        queue_lead_for_processing(lead)