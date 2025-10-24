"""
Instagram Webhooks API for handling comment triggers and DM automation.

This module implements webhook endpoints for Instagram Graph API events,
specifically focused on comment-triggered DM funnels for real estate lead generation.
"""

import os
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Response, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime

from utils.supabase_client import supabase
from utils.audit import audit_log_event
from utils.redis_client import redis_client
from tasks.comment_intake import process_comment_event

logger = logging.getLogger(__name__)
router = APIRouter()

# Comment trigger keywords that initiate DM funnel
TRIGGER_KEYWORDS = ["info", "price", "details", "more", "interested", "tour", "showing"]

def verify_meta_signature(payload: bytes, signature_header: str) -> bool:
    """
    Verify Meta (Instagram) webhook signature using HMAC-SHA256.
    
    Args:
        payload: Raw request body
        signature_header: X-Hub-Signature-256 header value
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        if not signature_header or not signature_header.startswith("sha256="):
            return False
            
        provided_hash = signature_header.split("=", 1)[1]
        app_secret = os.getenv("META_APP_SECRET")
        
        if not app_secret:
            logger.error("META_APP_SECRET not configured")
            return False
            
        expected_hash = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(provided_hash, expected_hash)
        
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def extract_comment_data(webhook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract comment events from Instagram webhook payload.
    
    Args:
        webhook_data: Raw webhook payload from Meta
        
    Returns:
        List of comment event dictionaries
    """
    comment_events = []
    
    try:
        for entry in webhook_data.get("entry", []):
            ig_account_id = entry.get("id")
            
            # Handle comment changes
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    
                    # Only process new comments (not edits or deletes)
                    if value.get("verb") == "add":
                        comment_data = {
                            "comment_id": value.get("id"),
                            "post_id": value.get("post_id"),
                            "comment_text": value.get("text", ""),
                            "commenter_id": value.get("from", {}).get("id"),
                            "commenter_name": value.get("from", {}).get("name"),
                            "commenter_username": value.get("from", {}).get("username"),
                            "ig_account_id": ig_account_id,
                            "timestamp": value.get("created_time"),
                            "media_type": value.get("media_type", "photo")  # photo, video, carousel
                        }
                        comment_events.append(comment_data)
                        
    except Exception as e:
        logger.error(f"Error extracting comment data: {e}")
        
    return comment_events

def contains_trigger_keyword(comment_text: str) -> bool:
    """
    Check if comment contains any trigger keywords.
    
    Args:
        comment_text: The comment text to check
        
    Returns:
        True if comment contains trigger keywords, False otherwise
    """
    if not comment_text:
        return False
        
    # Convert to lowercase for case-insensitive matching
    comment_lower = comment_text.lower()
    
    # Check for exact keyword matches
    for keyword in TRIGGER_KEYWORDS:
        if keyword.lower() in comment_lower:
            return True
            
    return False

def is_duplicate_comment(comment_id: str) -> bool:
    """
    Check if comment has already been processed to prevent duplicates.
    
    Args:
        comment_id: Instagram comment ID
        
    Returns:
        True if comment was already processed, False otherwise
    """
    if not redis_client:
        return False
        
    try:
        duplicate_key = f"comment_processed:{comment_id}"
        return redis_client.exists(duplicate_key)
    except Exception as e:
        logger.error(f"Error checking duplicate comment: {e}")
        return False

def mark_comment_processed(comment_id: str, ttl: int = 86400) -> bool:
    """
    Mark comment as processed to prevent duplicates.
    
    Args:
        comment_id: Instagram comment ID
        ttl: Time to live in seconds (default: 24 hours)
        
    Returns:
        True if successfully marked, False otherwise
    """
    if not redis_client:
        return False
        
    try:
        duplicate_key = f"comment_processed:{comment_id}"
        redis_client.setex(duplicate_key, ttl, "1")
        return True
    except Exception as e:
        logger.error(f"Error marking comment processed: {e}")
        return False

@router.get("/webhooks/instagram/comments")
async def verify_webhook(request: Request):
    """
    Handle Instagram webhook verification challenge.
    
    Meta sends this when setting up the webhook subscription.
    """
    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    
    if hub_mode == "subscribe":
        expected_token = os.getenv("META_VERIFY_TOKEN", "aaa_real_estate_verify_token_2025")
        
        if hub_verify_token != expected_token:
            logger.warning(f"Webhook verification failed: invalid token {hub_verify_token}")
            raise HTTPException(status_code=403, detail="Invalid verification token")
            
        if not hub_challenge:
            logger.warning("Webhook verification failed: missing challenge")
            raise HTTPException(status_code=400, detail="Missing challenge parameter")
            
        logger.info("Instagram webhook verification successful")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    raise HTTPException(status_code=400, detail="Invalid webhook request")

@router.post("/webhooks/instagram/comments")
async def handle_comment_webhook(request: Request):
    """
    Handle Instagram comment webhook events.
    
    Processes new comments and triggers DM funnel for comments containing
    trigger keywords like "info", "price", "details", etc.
    """
    try:
        # Read raw body for signature verification
        raw_body = await request.body()
        
        # Verify webhook signature
        signature = request.headers.get("x-hub-signature-256", "")
        if not verify_meta_signature(raw_body, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse webhook data
        try:
            webhook_data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        # Validate webhook object
        if webhook_data.get("object") != "instagram":
            logger.info(f"Ignoring non-Instagram webhook: {webhook_data.get('object')}")
            return {"status": "ignored", "reason": "not_instagram"}
        
        # Extract comment events
        comment_events = extract_comment_data(webhook_data)
        
        if not comment_events:
            logger.debug("No comment events found in webhook")
            return {"status": "success", "processed": 0}
        
        processed_count = 0
        
        # Process each comment event
        for comment_event in comment_events:
            try:
                # Skip duplicates
                if is_duplicate_comment(comment_event["comment_id"]):
                    logger.debug(f"Skipping duplicate comment: {comment_event['comment_id']}")
                    continue
                
                # Check for trigger keywords
                if not contains_trigger_keyword(comment_event["comment_text"]):
                    logger.debug(f"Comment without trigger keywords: {comment_event['comment_id']}")
                    # Still mark as processed to avoid rechecking
                    mark_comment_processed(comment_event["comment_id"])
                    continue
                
                # Record comment event with audit log
                audit_log_event("comment_trigger_detected", {
                    "comment_id": comment_event["comment_id"],
                    "post_id": comment_event["post_id"],
                    "commenter_id": comment_event["commenter_id"],
                    "commenter_name": comment_event["commenter_name"],
                    "comment_text": comment_event["comment_text"],
                    "ig_account_id": comment_event["ig_account_id"],
                    "timestamp": datetime.now().isoformat()
                })
                
                # Enqueue background job for comment processing
                from celery_app import process_comment_task
                task_result = process_comment_task.delay(comment_event)
                
                logger.info(f"Enqueued comment processing task: {task_result.id}")
                
                # Mark as processed to prevent duplicates
                mark_comment_processed(comment_event["comment_id"])
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing comment event {comment_event.get('comment_id')}: {e}")
                # Continue processing other comments
                continue
        
        logger.info(f"Processed {processed_count} comment triggers from webhook")
        
        return {
            "status": "success",
            "processed": processed_count,
            "total_events": len(comment_events)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in comment webhook handler: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )

@router.get("/webhooks/instagram/comments/status")
async def webhook_status():
    """
    Get webhook processing status for monitoring.
    """
    try:
        # Check Redis connection
        redis_status = "healthy"
        if redis_client:
            try:
                redis_client.ping()
            except Exception:
                redis_status = "unhealthy"
        else:
            redis_status = "not_configured"
        
        # Get recent processing stats
        recent_processed = 0
        if redis_client:
            try:
                # Count comments processed in last hour
                recent_processed = len(redis_client.keys("comment_processed:*"))
            except Exception:
                pass
        
        return {
            "status": "operational",
            "webhook_type": "instagram_comments",
            "redis_status": redis_status,
            "trigger_keywords": TRIGGER_KEYWORDS,
            "recent_processed_comments": recent_processed,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )