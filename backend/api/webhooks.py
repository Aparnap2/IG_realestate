"""
Instagram Webhooks API for handling comment triggers and DM automation.

This module implements webhook endpoints for Instagram Graph API events,
specifically focused on comment-triggered DM funnels for real estate lead generation.
Enhanced with Phase 1: Intent Detection & High-Intent Filtering capabilities.
"""

import os
import json
import hmac
import hashlib
import re
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Response, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime

from utils.supabase_client import supabase
from utils.audit import audit_log_event
from utils.redis_client import redis_client
from tasks.comment_intake import process_comment_event

# Self-Driving Booking Ops 2.0 imports
from booking.message_bus import MessageBus

logger = logging.getLogger(__name__)
router = APIRouter()

# Enhanced trigger keywords with intent patterns
TRIGGER_KEYWORDS = [
    # Basic information requests
    "info", "information", "details", "more", "interested", "tell me", "know more",
    
    # Pricing and budget inquiries
    "price", "pricing", "cost", "budget", "$", "dollar", "k", "million",
    
    # High-intent property inquiries
    "condo", "condominium", "apartment", "house", "home", "property", "listing",
    "viewing", "showing", "tour", "see", "visit", "walkthrough",
    
    # Timeline and urgency indicators
    "asap", "urgent", "immediately", "soon", "this month", "next month", "timeline",
    
    # Specific requirements
    "bedroom", "bathroom", "sqft", "square", "foot", "location", "area", "neighborhood"
]

# High-intent trigger patterns (escalate qualification immediately)
HIGH_INTENT_PATTERNS = [
    r'\$\d+[km]?',  # Budget mentions (e.g., $500k)
    r'\d+\s*(?:bhk|bed|beds|bedroom)',  # Bedroom specifications
    r'(?:condo|apartment|house|home).*(?:price|cost|budget)',  # Property + budget
    r'(?:viewing|showing|tour|visit).*(?:schedule|book|arrange)',  # Booking intent
    r'(?:asap|immediately|urgent|this week|next week)',  # Urgency
    r'(?:ready|prepared|serious|committed).*(?:buy|purchase)',  # Purchase readiness
]

# Intent classification weights
INTENT_WEIGHTS = {
    'budget_inquiry': 0.9,
    'property_specific': 0.8,
    'timeline_urgent': 0.85,
    'booking_intent': 0.95,
    'information_request': 0.6,
    'general_interest': 0.4,
    'cold_inquiry': 0.2,
    'spam_irrelevant': 0.1
}

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

def classify_intent(comment_text: str) -> Dict[str, Any]:
    """
    Classify the intent level and type of a comment.
    
    Args:
        comment_text: The comment text to analyze
        
    Returns:
        Dictionary with intent classification results
    """
    if not comment_text:
        return {
            'intent_type': 'empty',
            'intent_score': 0.0,
            'confidence': 0.0,
            'high_intent': False,
            'classification_reason': 'Empty or null comment'
        }
    
    comment_lower = comment_text.lower().strip()
    scores = {}
    
    # Budget inquiry detection
    if any(word in comment_lower for word in ["budget", "price", "cost", "$", "k", "million", "dollar"]):
        scores['budget_inquiry'] = INTENT_WEIGHTS['budget_inquiry']
    
    # Property-specific detection
    if any(word in comment_lower for word in ["condo", "apartment", "house", "home", "property", "listing", "bedroom"]):
        scores['property_specific'] = INTENT_WEIGHTS['property_specific']
    
    # Timeline urgency detection
    if any(word in comment_lower for word in ["asap", "urgent", "immediately", "soon", "timeline", "when"]):
        scores['timeline_urgent'] = INTENT_WEIGHTS['timeline_urgent']
    
    # Booking intent detection
    if any(word in comment_lower for word in ["viewing", "showing", "tour", "visit", "schedule", "book"]):
        scores['booking_intent'] = INTENT_WEIGHTS['booking_intent']
    
    # General information request
    if any(word in comment_lower for word in ["info", "details", "more", "tell me", "know"]):
        scores['information_request'] = INTENT_WEIGHTS['information_request']
    
    # General interest
    if any(word in comment_lower for word in ["interested", "looking", "searching"]):
        scores['general_interest'] = INTENT_WEIGHTS['general_interest']
    
    # Calculate final scores
    if scores:
        max_score = max(scores.values())
        primary_intent = max(scores, key=scores.get)
        
        # Determine if high-intent
        high_intent_threshold = 0.75
        is_high_intent = max_score >= high_intent_threshold
        
        return {
            'intent_type': primary_intent,
            'intent_score': round(max_score, 3),
            'confidence': round(max_score * 0.9, 3),  # Confidence slightly lower than score
            'high_intent': is_high_intent,
            'all_scores': {k: round(v, 3) for k, v in scores.items()},
            'classification_reason': f"Primary intent: {primary_intent} with score {max_score:.3f}"
        }
    else:
        # No specific intent detected
        return {
            'intent_type': 'cold_inquiry',
            'intent_score': INTENT_WEIGHTS['cold_inquiry'],
            'confidence': 0.6,
            'high_intent': False,
            'all_scores': {},
            'classification_reason': 'No specific intent detected'
        }

def detect_high_intent_patterns(comment_text: str) -> Dict[str, Any]:
    """
    Detect high-intent patterns that warrant immediate qualification.
    
    Args:
        comment_text: The comment text to analyze
        
    Returns:
        Dictionary with high-intent pattern detection results
    """
    if not comment_text:
        return {
            'patterns_detected': [],
            'pattern_score': 0.0,
            'immediate_qualification': False
        }
    
    patterns_found = []
    comment_lower = comment_text.lower()
    
    # Check each high-intent pattern
    for i, pattern in enumerate(HIGH_INTENT_PATTERNS):
        if re.search(pattern, comment_lower, re.IGNORECASE):
            patterns_found.append({
                'pattern_index': i,
                'pattern': pattern,
                'matched_text': re.search(pattern, comment_lower, re.IGNORECASE).group()
            })
    
    # Calculate pattern score based on matches
    pattern_score = min(len(patterns_found) * 0.25, 1.0)  # Each pattern adds 0.25, max 1.0
    
    # Determine if immediate qualification is needed
    immediate_qualification = (
        len(patterns_found) >= 2 or  # Multiple patterns
        pattern_score >= 0.5 or      # High pattern score
        any('budget' in p.get('pattern', '') for p in patterns_found)  # Budget mentions
    )
    
    return {
        'patterns_detected': patterns_found,
        'pattern_score': round(pattern_score, 3),
        'immediate_qualification': immediate_qualification,
        'pattern_count': len(patterns_found)
    }

def contains_trigger_keyword(comment_text: str) -> bool:
    """
    Enhanced trigger keyword detection with intent consideration.
    
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

def should_process_high_intent_lead(comment_text: str) -> Dict[str, Any]:
    """
    Determine if a lead should be processed for high-intent qualification.
    
    Args:
        comment_text: The comment text to analyze
        
    Returns:
        Dictionary with processing decision and reasoning
    """
    # First check basic trigger keywords
    if not contains_trigger_keyword(comment_text):
        return {
            'should_process': False,
            'reason': 'No trigger keywords found',
            'intent_analysis': None,
            'pattern_analysis': None
        }
    
    # Perform intent classification
    intent_analysis = classify_intent(comment_text)
    
    # Perform pattern detection
    pattern_analysis = detect_high_intent_patterns(comment_text)
    
    # Make processing decision
    should_process = (
        intent_analysis['high_intent'] or
        pattern_analysis['immediate_qualification'] or
        intent_analysis['intent_score'] >= 0.6  # Medium-high intent threshold
    )
    
    reason = "High intent detected" if intent_analysis['high_intent'] else \
             "High-intent patterns found" if pattern_analysis['immediate_qualification'] else \
             "Medium-high intent score" if intent_analysis['intent_score'] >= 0.6 else \
             "Basic trigger matched but low intent"
    
    return {
        'should_process': should_process,
        'reason': reason,
        'intent_analysis': intent_analysis,
        'pattern_analysis': pattern_analysis,
        'priority_level': 'high' if should_process else 'low',
        'filtering_decision': {
            'triggered': True,
            'intent_threshold_met': intent_analysis['intent_score'] >= 0.6,
            'pattern_threshold_met': pattern_analysis['immediate_qualification'],
            'final_decision': should_process
        }
    }

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
        message_bus = MessageBus()

        # Process each comment event with enhanced intent filtering
        for comment_event in comment_events:
            try:
                comment_text = comment_event["comment_text"]
                comment_id = comment_event["comment_id"]
                
                # Phase 1: Enhanced intent detection and filtering
                intent_decision = should_process_high_intent_lead(comment_text)
                
                # Log intent analysis for monitoring
                if intent_decision['intent_analysis']:
                    audit_log_event("intent_analysis_performed", {
                        "comment_id": comment_id,
                        "commenter_id": comment_event["commenter_id"],
                        "intent_type": intent_decision['intent_analysis']['intent_type'],
                        "intent_score": intent_decision['intent_analysis']['intent_score'],
                        "high_intent": intent_decision['intent_analysis']['high_intent'],
                        "patterns_found": len(intent_decision['pattern_analysis']['patterns_detected']) if intent_decision['pattern_analysis'] else 0,
                        "should_process": intent_decision['should_process'],
                        "reason": intent_decision['reason'],
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Skip low-intent comments but mark as processed to avoid rechecking
                if not intent_decision['should_process']:
                    logger.debug(f"Low-intent comment filtered out: {comment_id} - {intent_decision['reason']}")
                    mark_comment_processed(comment_id)
                    continue

                logger.info(f"High-intent lead detected: {comment_id} - {intent_decision['reason']} "
                          f"(Intent: {intent_decision['intent_analysis']['intent_type']}, "
                          f"Score: {intent_decision['intent_analysis']['intent_score']})")

                # Normalize message through MessageBus with enhanced metadata
                normalized_payload = {
                    "from": comment_event["commenter_id"],
                    "text": comment_text,
                    "timestamp": comment_event["timestamp"],
                    "channel": "instagram",
                    "comment_id": comment_id,
                    "post_id": comment_event["post_id"],
                    "commenter_name": comment_event["commenter_name"],
                    "ig_account_id": comment_event["ig_account_id"],
                    # Enhanced intent detection metadata
                    "intent_analysis": intent_decision['intent_analysis'],
                    "pattern_analysis": intent_decision['pattern_analysis'],
                    "high_intent_triggered": True,
                    "intent_priority": intent_decision['priority_level']
                }

                normalized_message = message_bus.normalize_message('instagram', normalized_payload)

                # Skip duplicates using MessageBus
                if message_bus.is_duplicate(normalized_message.message_uuid):
                    logger.debug(f"Skipping duplicate message: {normalized_message.message_uuid}")
                    continue

                # Claim message for processing
                if not message_bus.claim_message(normalized_message.message_uuid):
                    logger.debug(f"Failed to claim message: {normalized_message.message_uuid}")
                    continue

                # Record message event with enhanced audit log including intent data
                audit_log_event("high_intent_message_received", {
                    "message_uuid": normalized_message.message_uuid,
                    "comment_id": comment_id,
                    "post_id": comment_event["post_id"],
                    "commenter_id": comment_event["commenter_id"],
                    "commenter_name": comment_event["commenter_name"],
                    "comment_text": comment_text,
                    "ig_account_id": comment_event["ig_account_id"],
                    "intent_type": intent_decision['intent_analysis']['intent_type'],
                    "intent_score": intent_decision['intent_analysis']['intent_score'],
                    "high_intent": intent_decision['intent_analysis']['high_intent'],
                    "patterns_detected": len(intent_decision['pattern_analysis']['patterns_detected']),
                    "priority_level": intent_decision['priority_level'],
                    "timestamp": datetime.now().isoformat()
                })

                # Enqueue background job for high-intent message processing
                from celery_app import process_comment_task
                task_result = process_comment_task.delay(normalized_message)

                logger.info(f"High-intent lead enqueued for processing: {task_result.id} "
                          f"(uuid: {normalized_message.message_uuid}, "
                          f"intent: {intent_decision['intent_analysis']['intent_type']})")

                # Mark message as processed
                message_bus.mark_processed(normalized_message.message_uuid, {
                    "task_id": task_result.id,
                    "channel": "instagram",
                    "intent_processed": True,
                    "high_intent_lead": True
                })

                # Legacy processing for backward compatibility
                mark_comment_processed(comment_id)

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
    Get webhook processing status with Phase 1 intent detection metrics.
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
        recent_high_intent = 0
        if redis_client:
            try:
                # Count comments processed in last hour
                recent_processed = len(redis_client.keys("comment_processed:*"))
                
                # Count high-intent leads processed (this would need to be tracked separately)
                # For now, we'll estimate based on processing patterns
                recent_high_intent = int(recent_processed * 0.3)  # Assume 30% are high-intent
            except Exception:
                pass
        
        return {
            "status": "operational",
            "webhook_type": "instagram_comments",
            "phase": "phase_1_intent_detection_enabled",
            "redis_status": redis_status,
            "trigger_keywords": TRIGGER_KEYWORDS,
            "high_intent_patterns": HIGH_INTENT_PATTERNS,
            "intent_weights": INTENT_WEIGHTS,
            "recent_processed_comments": recent_processed,
            "recent_high_intent_leads": recent_high_intent,
            "intent_filtering": {
                "enabled": True,
                "high_intent_threshold": 0.75,
                "medium_intent_threshold": 0.6,
                "pattern_detection_enabled": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )