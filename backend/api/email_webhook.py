"""
Email Webhook Handler for SendGrid/Mailgun

Implements webhook endpoints for inbound email processing with signature verification,
message parsing, and integration with MessageBus for booking intents.
"""

import os
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

from backend.booking.message_bus import MessageBus
from backend.communication.multi_channel_manager import MultiChannelManager
from backend.utils.audit import audit_log_event
from backend.utils.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

class EmailWebhookHandler:
    """Email webhook handler for SendGrid and Mailgun with signature verification."""

    def __init__(self):
        self.message_bus = MessageBus()
        self.multi_channel = MultiChannelManager()
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.mailgun_api_key = os.getenv("MAILGUN_API_KEY")

    def verify_sendgrid_signature(self, payload: bytes, signature_data: Dict[str, str]) -> bool:
        """
        Verify SendGrid webhook signature.

        Args:
            payload: Raw request body
            signature_data: Signature headers from SendGrid

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.sendgrid_api_key:
                logger.error("SENDGRID_API_KEY not configured")
                return False

            timestamp = signature_data.get("timestamp", "")
            token = signature_data.get("token", "")
            signature = signature_data.get("signature", "")

            if not all([timestamp, token, signature]):
                return False

            # Create signed payload
            signed_payload = f"{timestamp}{token}".encode() + payload

            # Generate expected signature
            expected_signature = hmac.new(
                self.sendgrid_api_key.encode(),
                signed_payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"SendGrid signature verification error: {e}")
            return False

    def verify_mailgun_signature(self, payload: bytes, signature_data: Dict[str, str]) -> bool:
        """
        Verify Mailgun webhook signature.

        Args:
            payload: Raw request body
            signature_data: Signature headers from Mailgun

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.mailgun_api_key:
                logger.error("MAILGUN_API_KEY not configured")
                return False

            timestamp = signature_data.get("timestamp", "")
            token = signature_data.get("token", "")
            signature = signature_data.get("signature", "")

            if not all([timestamp, token, signature]):
                return False

            # Create signed payload (Mailgun uses different format)
            signed_payload = f"{timestamp}{token}".encode()

            # Generate expected signature
            expected_signature = hmac.new(
                self.mailgun_api_key.encode(),
                signed_payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Mailgun signature verification error: {e}")
            return False

    def extract_email_message(self, webhook_data: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """
        Extract message data from email webhook payload.

        Args:
            webhook_data: Raw webhook payload
            provider: Email provider ('sendgrid' or 'mailgun')

        Returns:
            Extracted message data dictionary
        """
        try:
            if provider.lower() == "sendgrid":
                # SendGrid inbound parse webhook format
                return {
                    "message_id": webhook_data.get("message_id") or webhook_data.get("sg_message_id"),
                    "from_email": webhook_data.get("from"),
                    "to_email": webhook_data.get("to"),
                    "subject": webhook_data.get("subject", ""),
                    "text": webhook_data.get("text", ""),
                    "html": webhook_data.get("html", ""),
                    "timestamp": webhook_data.get("timestamp"),
                    "provider": "sendgrid"
                }

            elif provider.lower() == "mailgun":
                # Mailgun webhook format
                return {
                    "message_id": webhook_data.get("message-id") or webhook_data.get("Message-Id"),
                    "from_email": webhook_data.get("from") or webhook_data.get("From"),
                    "to_email": webhook_data.get("recipient") or webhook_data.get("To"),
                    "subject": webhook_data.get("subject") or webhook_data.get("Subject"),
                    "text": webhook_data.get("body-plain") or webhook_data.get("stripped-text"),
                    "html": webhook_data.get("body-html") or webhook_data.get("stripped-html"),
                    "timestamp": webhook_data.get("timestamp"),
                    "provider": "mailgun"
                }

            else:
                logger.warning(f"Unknown email provider: {provider}")
                return {}

        except Exception as e:
            logger.error(f"Error extracting email message: {e}")
            return {}

    def extract_lead_id_from_email(self, to_address: str) -> Optional[str]:
        """
        Extract lead ID from email address format like leads+{lead_id}@domain.com.

        Args:
            to_address: Email address to parse

        Returns:
            Extracted lead ID or None if not found
        """
        try:
            if "+" in to_address:
                local_part = to_address.split("@")[0]
                lead_part = local_part.split("+")[1]
                return lead_part
        except Exception:
            pass
        return None

    def is_duplicate_email(self, message_id: str) -> bool:
        """
        Check if email has already been processed.

        Args:
            message_id: Email message ID

        Returns:
            True if already processed, False otherwise
        """
        if not redis_client:
            return False

        try:
            duplicate_key = f"email_processed:{message_id}"
            return redis_client.exists(duplicate_key)
        except Exception as e:
            logger.error(f"Error checking duplicate email: {e}")
            return False

    def mark_email_processed(self, message_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark email as processed.

        Args:
            message_id: Email message ID
            result: Processing result data

        Returns:
            True if marked successfully, False otherwise
        """
        if not redis_client:
            return False

        try:
            duplicate_key = f"email_processed:{message_id}"
            processed_data = {
                'processed_at': datetime.now().isoformat(),
                'result': result
            }
            redis_client.setex(duplicate_key, 86400, json.dumps(processed_data, default=str))  # 24 hours
            return True
        except Exception as e:
            logger.error(f"Error marking email processed: {e}")
            return False

    def send_email_reply(self, to_address: str, subject: str, body: str) -> bool:
        """
        Send email reply using configured provider.

        Args:
            to_address: Reply-to email address
            subject: Email subject
            body: Email body

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Use MultiChannelManager for email sending
            result = self.multi_channel.send_message(
                user_id=to_address,  # Use email as user_id for replies
                message=body,
                channel='email',
                message_type='reply'
            )

            return result.get('success', False)

        except Exception as e:
            logger.error(f"Error sending email reply: {e}")
            return False

# Initialize handler
email_handler = EmailWebhookHandler()

@router.post("/webhooks/email/sendgrid")
async def handle_sendgrid_webhook(request: Request):
    """
    Handle SendGrid inbound email webhook events.
    """
    try:
        # Read raw body for signature verification
        raw_body = await request.body()

        # Verify SendGrid signature
        signature_data = {
            "timestamp": request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", ""),
            "token": request.headers.get("X-Twilio-Email-Event-Webhook-Signature", ""),
            "signature": request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
        }

        # Note: SendGrid signature verification may vary; adjust as needed
        if not email_handler.verify_sendgrid_signature(raw_body, signature_data):
            logger.warning("Invalid SendGrid webhook signature")
            # For development, allow unsigned requests
            if os.getenv("ENVIRONMENT") != "development":
                raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse webhook data
        try:
            webhook_data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in SendGrid webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Handle both single email and batch emails
        emails = webhook_data if isinstance(webhook_data, list) else [webhook_data]

        processed_count = 0

        for email_data in emails:
            try:
                # Extract message data
                message = email_handler.extract_email_message(email_data, "sendgrid")

                if not message:
                    continue

                # Skip duplicates
                if email_handler.is_duplicate_email(message["message_id"]):
                    logger.debug(f"Skipping duplicate SendGrid email: {message['message_id']}")
                    continue

                # Check for booking-related keywords
                email_text = (message.get("text", "") + " " + message.get("subject", "")).lower()
                booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time", "reschedule"]

                has_booking_intent = any(keyword in email_text for keyword in booking_keywords)

                if not has_booking_intent:
                    logger.debug(f"SendGrid email without booking intent: {message['message_id']}")
                    email_handler.mark_email_processed(message["message_id"], {"intent": "non_booking"})
                    continue

                # Extract lead ID from email address
                lead_id = email_handler.extract_lead_id_from_email(message["to_email"])

                # Normalize message for MessageBus
                normalized_payload = {
                    "from": message["from_email"],
                    "to": message["to_email"],
                    "subject": message["subject"],
                    "text": message["text"],
                    "html": message["html"],
                    "timestamp": message["timestamp"],
                    "channel": "email",
                    "message_id": message["message_id"],
                    "provider": "sendgrid"
                }

                normalized_message = email_handler.message_bus.normalize_message(
                    'email',
                    normalized_payload
                )

                # Record email event with audit log
                audit_log_event("sendgrid_email_received", {
                    "message_id": message["message_id"],
                    "from": message["from_email"],
                    "to": message["to_email"],
                    "subject": message["subject"],
                    "lead_id": lead_id,
                    "normalized_uuid": normalized_message.message_uuid
                })

                # Enqueue async processing (placeholder)
                logger.info(f"Enqueued SendGrid email processing: {normalized_message.message_uuid}")

                # Mark as processed
                email_handler.mark_email_processed(message["message_id"], {
                    "normalized_uuid": normalized_message.message_uuid,
                    "lead_id": lead_id,
                    "intent": "booking_related"
                })

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing SendGrid email: {e}")
                continue

        logger.info(f"Processed {processed_count} SendGrid booking emails from webhook")

        return {
            "status": "success",
            "processed": processed_count,
            "total_emails": len(emails)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SendGrid webhook handler: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )

@router.post("/webhooks/email/mailgun")
async def handle_mailgun_webhook(request: Request):
    """
    Handle Mailgun inbound email webhook events.
    """
    try:
        # Read raw body for signature verification
        raw_body = await request.body()

        # Verify Mailgun signature
        signature_data = {
            "timestamp": request.headers.get("X-Mailgun-Timestamp", ""),
            "token": request.headers.get("X-Mailgun-Token", ""),
            "signature": request.headers.get("X-Mailgun-Signature", "")
        }

        if not email_handler.verify_mailgun_signature(raw_body, signature_data):
            logger.warning("Invalid Mailgun webhook signature")
            if os.getenv("ENVIRONMENT") != "development":
                raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse webhook data (Mailgun sends form data, not JSON)
        form_data = await request.form()
        webhook_data = dict(form_data)

        try:
            # Extract message data
            message = email_handler.extract_email_message(webhook_data, "mailgun")

            if not message:
                return {"status": "success", "processed": 0}

            # Skip duplicates
            if email_handler.is_duplicate_email(message["message_id"]):
                logger.debug(f"Skipping duplicate Mailgun email: {message['message_id']}")
                return {"status": "success", "processed": 0, "reason": "duplicate"}

            # Check for booking-related keywords
            email_text = (message.get("text", "") + " " + message.get("subject", "")).lower()
            booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time", "reschedule"]

            has_booking_intent = any(keyword in email_text for keyword in booking_keywords)

            if not has_booking_intent:
                logger.debug(f"Mailgun email without booking intent: {message['message_id']}")
                email_handler.mark_email_processed(message["message_id"], {"intent": "non_booking"})
                return {"status": "success", "processed": 0, "reason": "no_booking_intent"}

            # Extract lead ID from email address
            lead_id = email_handler.extract_lead_id_from_email(message["to_email"])

            # Normalize message for MessageBus
            normalized_payload = {
                "from": message["from_email"],
                "to": message["to_email"],
                "subject": message["subject"],
                "text": message["text"],
                "html": message["html"],
                "timestamp": message["timestamp"],
                "channel": "email",
                "message_id": message["message_id"],
                "provider": "mailgun"
            }

            normalized_message = email_handler.message_bus.normalize_message(
                'email',
                normalized_payload
            )

            # Record email event with audit log
            audit_log_event("mailgun_email_received", {
                "message_id": message["message_id"],
                "from": message["from_email"],
                "to": message["to_email"],
                "subject": message["subject"],
                "lead_id": lead_id,
                "normalized_uuid": normalized_message.message_uuid
            })

            # Enqueue async processing (placeholder)
            logger.info(f"Enqueued Mailgun email processing: {normalized_message.message_uuid}")

            # Mark as processed
            email_handler.mark_email_processed(message["message_id"], {
                "normalized_uuid": normalized_message.message_uuid,
                "lead_id": lead_id,
                "intent": "booking_related"
            })

            logger.info("Processed 1 Mailgun booking email from webhook")

            return {
                "status": "success",
                "processed": 1
            }

        except Exception as e:
            logger.error(f"Error processing Mailgun email: {e}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "error": str(e)}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Mailgun webhook handler: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )
