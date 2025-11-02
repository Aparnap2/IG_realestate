"""
WhatsApp Business API Webhook Handler

Implements webhook endpoints for WhatsApp Business API message events
with signature verification, message parsing, and integration with MessageBus.
"""

import os
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime

from backend.booking.message_bus import MessageBus, NormalizedMessage
from backend.utils.audit import audit_log_event
from backend.utils.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

class WhatsAppWebhookHandler:
    """WhatsApp Business API webhook handler with signature verification."""

    def __init__(self):
        self.message_bus = MessageBus()
        self.app_secret = os.getenv("WHATSAPP_APP_SECRET")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        # Reference to the module-level router for FastAPI integration
        self.router = router

    def verify_whatsapp_signature(self, payload: bytes, signature_header: str) -> bool:
        """
        Verify WhatsApp webhook signature using HMAC-SHA256.

        Args:
            payload: Raw request body
            signature_header: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not signature_header or not signature_header.startswith("sha256="):
                return False

            if not self.app_secret:
                logger.error("WHATSAPP_APP_SECRET not configured")
                return False

            provided_hash = signature_header.split("=", 1)[1]
            expected_hash = hmac.new(
                self.app_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(provided_hash, expected_hash)

        except Exception as e:
            logger.error(f"WhatsApp signature verification error: {e}")
            return False

    def extract_whatsapp_message(self, webhook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract message events from WhatsApp webhook payload.

        Args:
            webhook_data: Raw webhook payload from WhatsApp

        Returns:
            List of message event dictionaries
        """
        messages = []

        try:
            for entry in webhook_data.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        value = change.get("value", {})

                        for message in value.get("messages", []):
                            # Only process text messages for booking intents
                            if message.get("type") == "text":
                                message_data = {
                                    "message_id": message.get("id"),
                                    "from": message.get("from"),
                                    "text": message.get("text", {}).get("body", ""),
                                    "timestamp": message.get("timestamp"),
                                    "type": message.get("type"),
                                    "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                                    "display_phone_number": value.get("metadata", {}).get("display_phone_number")
                                }
                                messages.append(message_data)

        except Exception as e:
            logger.error(f"Error extracting WhatsApp messages: {e}")

        return messages

    def is_duplicate_message(self, message_id: str) -> bool:
        """
        Check if WhatsApp message has already been processed.

        Args:
            message_id: WhatsApp message ID

        Returns:
            True if already processed, False otherwise
        """
        if not redis_client:
            return False

        try:
            duplicate_key = f"whatsapp_processed:{message_id}"
            # Convert to boolean to ensure consistent return type
            exists_result = redis_client.exists(duplicate_key)
            return bool(exists_result)
        except Exception as e:
            logger.error(f"Error checking duplicate WhatsApp message: {e}")
            return False

    def mark_message_processed(self, message_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark WhatsApp message as processed.

        Args:
            message_id: WhatsApp message ID
            result: Processing result data

        Returns:
            True if marked successfully, False otherwise
        """
        if not redis_client:
            return False

        try:
            duplicate_key = f"whatsapp_processed:{message_id}"
            processed_data = {
                'processed_at': datetime.now().isoformat(),
                'result': result
            }
            redis_client.setex(duplicate_key, 86400, json.dumps(processed_data, default=str))  # 24 hours
            return True
        except Exception as e:
            logger.error(f"Error marking WhatsApp message processed: {e}")
            return False

# Initialize handler
whatsapp_handler = WhatsAppWebhookHandler()

@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """
    Handle WhatsApp webhook verification challenge.

    WhatsApp sends this when setting up the webhook subscription.
    """
    try:
        hub_mode = request.query_params.get("hub.mode")
        hub_verify_token = request.query_params.get("hub.verify_token")
        hub_challenge = request.query_params.get("hub.challenge")

        if hub_mode == "subscribe":
            expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_verify_token_here")

            if hub_verify_token != expected_token:
                logger.warning(f"WhatsApp webhook verification failed: invalid token {hub_verify_token}")
                raise HTTPException(status_code=403, detail="Invalid verification token")

            if not hub_challenge:
                logger.warning("WhatsApp webhook verification failed: missing challenge")
                raise HTTPException(status_code=400, detail="Missing challenge parameter")

            logger.info("WhatsApp webhook verification successful")
            return PlainTextResponse(content=hub_challenge, status_code=200)

        raise HTTPException(status_code=400, detail="Invalid webhook request")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in WhatsApp verification: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )

@router.post("/webhooks/whatsapp")
async def handle_whatsapp_webhook(request: Request):
    """
    Handle WhatsApp message webhook events.

    Processes incoming messages and triggers booking flow for relevant intents.
    """
    try:
        # Read raw body for signature verification
        raw_body = await request.body()

        # Verify webhook signature
        signature = request.headers.get("x-hub-signature-256", "")
        if not whatsapp_handler.verify_whatsapp_signature(raw_body, signature):
            logger.warning("Invalid WhatsApp webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse webhook data
        try:
            webhook_data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WhatsApp webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Validate webhook object
        if webhook_data.get("object") != "whatsapp_business_account":
            logger.info(f"Ignoring non-WhatsApp webhook: {webhook_data.get('object')}")
            return {"status": "ignored", "reason": "not_whatsapp"}

        # Extract message events
        messages = whatsapp_handler.extract_whatsapp_message(webhook_data)

        if not messages:
            logger.debug("No message events found in WhatsApp webhook")
            return {"status": "success", "processed": 0}

        processed_count = 0

        # Process each message event
        for message in messages:
            try:
                # Skip duplicates
                if whatsapp_handler.is_duplicate_message(message["message_id"]):
                    logger.debug(f"Skipping duplicate WhatsApp message: {message['message_id']}")
                    continue

                # Check for booking-related keywords
                message_text = message.get("text", "").lower()
                booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time"]

                has_booking_intent = any(keyword in message_text for keyword in booking_keywords)

                if not has_booking_intent:
                    logger.debug(f"WhatsApp message without booking intent: {message['message_id']}")
                    # Still mark as processed to avoid rechecking
                    whatsapp_handler.mark_message_processed(message["message_id"], {"intent": "non_booking"})
                    continue

                # Normalize message for MessageBus
                normalized_payload = {
                    "from": message["from"],
                    "text": message["text"],
                    "timestamp": message["timestamp"],
                    "channel": "whatsapp",
                    "message_id": message["message_id"],
                    "phone_number_id": message.get("phone_number_id")
                }

                normalized_message = whatsapp_handler.message_bus.normalize_message(
                    'whatsapp',
                    normalized_payload
                )

                # Record message event with audit log
                audit_log_event("whatsapp_message_received", {
                    "message_id": message["message_id"],
                    "from": message["from"],
                    "text": message["text"],
                    "timestamp": datetime.fromtimestamp(int(message["timestamp"])).isoformat(),
                    "normalized_uuid": normalized_message.message_uuid
                })

                # Enqueue async processing with Celery
                from backend.tasks.whatsapp_processing import process_whatsapp_message
                
                # Convert normalized_message to dict for Celery serialization
                normalized_message_dict = {
                    'message_uuid': normalized_message.message_uuid,
                    'lead_id': normalized_message.lead_id,
                    'content': normalized_message.content,
                    'channel': normalized_message.channel.value if hasattr(normalized_message.channel, 'value') else str(normalized_message.channel),
                    'timestamp': normalized_message.timestamp.isoformat() if hasattr(normalized_message.timestamp, 'isoformat') else str(normalized_message.timestamp),
                    'metadata': normalized_message.metadata
                }
                
                try:
                    # Queue the task for async processing
                    task_result = process_whatsapp_message.delay(normalized_message_dict)
                    logger.info(f"Enqueued WhatsApp message processing: {normalized_message.message_uuid} (Task ID: {task_result.id})")
                except Exception as celery_error:
                    logger.error(f"Failed to enqueue WhatsApp message processing: {celery_error}")
                    # Continue processing other messages even if Celery fails

                # Mark as processed
                whatsapp_handler.mark_message_processed(message["message_id"], {
                    "normalized_uuid": normalized_message.message_uuid,
                    "intent": "booking_related"
                })

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing WhatsApp message {message.get('message_id')}: {e}")
                # Continue processing other messages
                continue

        logger.info(f"Processed {processed_count} WhatsApp booking messages from webhook")

        return {
            "status": "success",
            "processed": processed_count,
            "total_messages": len(messages)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in WhatsApp webhook handler: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )
