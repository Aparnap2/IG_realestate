"""
Message Bus for Multi-Channel Intake Normalization

Handles normalization of messages from Instagram, WhatsApp, and Email channels
with UUID-based deduplication and atomic message claiming for competing consumers.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from backend.utils.redis_client import redis_client, redis_circuit_breaker

logger = logging.getLogger(__name__)

class Channel(Enum):
    """Supported communication channels."""
    INSTAGRAM = "ig"
    WHATSAPP = "whatsapp"
    EMAIL = "email"

@dataclass
class NormalizedMessage:
    """Normalized message structure across all channels."""
    message_uuid: str  # UUIDv7 for uniqueness
    lead_id: Optional[str]
    content: str
    channel: Channel
    timestamp: datetime
    metadata: Dict[str, Any]

class MessageBus:
    """
    Message bus for normalizing multi-channel intake with deduplication.
    
    Provides atomic message claiming and processing state management
    for Instagram comments/DMs, WhatsApp messages, and email replies.
    """

    def __init__(self):
        self.redis_client = redis_client

    def normalize_message(self, channel: str, raw_payload: Dict[str, Any]) -> NormalizedMessage:
        """
        Normalize raw channel payload into standardized message format.
        
        Args:
            channel: Channel identifier (ig, whatsapp, email)
            raw_payload: Raw payload from webhook
            
        Returns:
            NormalizedMessage instance
        """
        channel_enum = Channel(channel.lower())
        
        # Generate UUIDv7 (using timestamp-based UUID as approximation)
        message_uuid = str(uuid.uuid4())  # TODO: Replace with uuid7 if available
        
        # Parse channel-specific data
        if channel_enum == Channel.INSTAGRAM:
            parsed = self._parse_instagram_webhook(raw_payload)
        elif channel_enum == Channel.WHATSAPP:
            parsed = self._parse_whatsapp_webhook(raw_payload)
        elif channel_enum == Channel.EMAIL:
            parsed = self._parse_email_webhook(raw_payload)
        else:
            raise ValueError(f"Unsupported channel: {channel}")
            
        return NormalizedMessage(
            message_uuid=message_uuid,
            lead_id=parsed.get('lead_id'),
            content=parsed.get('content', ''),
            channel=channel_enum,
            timestamp=parsed.get('timestamp', datetime.now()),
            metadata=parsed.get('metadata', {})
        )

    def is_duplicate(self, message_uuid: str) -> bool:
        """
        Check if message UUID has already been processed.
        
        Args:
            message_uuid: Message UUID to check
            
        Returns:
            True if already processed, False otherwise
        """
        if self.redis_client is None:
            logger.debug("Redis unavailable - cannot check duplicates")
            return False

        def _check_operation():
            key = f"processed_messages:{message_uuid}"
            return self.redis_client.exists(key)

        try:
            return redis_circuit_breaker.call(_check_operation)
        except Exception as e:
            logger.warning(f"Error checking duplicate message {message_uuid}: {e}")
            return False

    def claim_message(self, message_uuid: str) -> bool:
        """
        Atomically claim message for processing using Redis SETNX.
        
        Args:
            message_uuid: Message UUID to claim
            
        Returns:
            True if claimed successfully, False if already claimed
        """
        if self.redis_client is None:
            logger.debug("Redis unavailable - cannot claim message")
            return True  # Allow processing without deduplication

        def _claim_operation():
            key = f"message_claim:{message_uuid}"
            # SETNX returns 1 if key was set, 0 if key already exists
            return self.redis_client.setnx(key, "claimed")

        try:
            claimed = redis_circuit_breaker.call(_claim_operation)
            if claimed:
                # Set TTL on claim key
                self.redis_client.expire(f"message_claim:{message_uuid}", 3600)  # 1 hour
            return bool(claimed)
        except Exception as e:
            logger.warning(f"Error claiming message {message_uuid}: {e}")
            return False

    def mark_processed(self, message_uuid: str, result: Dict[str, Any]) -> bool:
        """
        Mark message as processed with outcome.
        
        Args:
            message_uuid: Message UUID
            result: Processing result data
            
        Returns:
            True if marked successfully, False otherwise
        """
        if self.redis_client is None:
            logger.debug("Redis unavailable - cannot mark processed")
            return False

        def _mark_operation():
            key = f"processed_messages:{message_uuid}"
            processed_data = {
                'processed_at': datetime.now().isoformat(),
                'result': result
            }
            self.redis_client.setex(key, 604800, json.dumps(processed_data, default=str))  # 7 days
            return True

        try:
            return redis_circuit_breaker.call(_mark_operation)
        except Exception as e:
            logger.warning(f"Error marking message {message_uuid} processed: {e}")
            return False

    def _parse_instagram_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Instagram webhook payload."""
        # Based on existing webhook structure from backend/api/webhooks.py
        parsed = {}
        
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "comments":
                        value = change.get("value", {})
                        parsed = {
                            'content': value.get("text", ""),
                            'lead_id': value.get("from", {}).get("id"),
                            'timestamp': datetime.fromisoformat(value.get("created_time")) if value.get("created_time") else datetime.now(),
                            'metadata': {
                                'comment_id': value.get("id"),
                                'post_id': value.get("post_id"),
                                'commenter_name': value.get("from", {}).get("name"),
                                'commenter_username': value.get("from", {}).get("username"),
                                'ig_account_id': entry.get("id"),
                                'media_type': value.get("media_type", "photo")
                            }
                        }
                        break
                if parsed:
                    break
        except Exception as e:
            logger.error(f"Error parsing Instagram webhook: {e}")
            
        return parsed

    def _parse_whatsapp_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse WhatsApp Business API webhook payload."""
        parsed = {}
        
        try:
            # WhatsApp webhook structure: entry[].changes[].value.messages[]
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for message in value.get("messages", []):
                        parsed = {
                            'content': message.get("text", {}).get("body", ""),
                            'lead_id': message.get("from"),
                            'timestamp': datetime.fromtimestamp(int(message.get("timestamp", 0))),
                            'metadata': {
                                'message_id': message.get("id"),
                                'message_type': message.get("type"),
                                'phone_number_id': value.get("metadata", {}).get("phone_number_id"),
                                'display_phone_number': value.get("metadata", {}).get("display_phone_number")
                            }
                        }
                        break
                if parsed:
                    break
        except Exception as e:
            logger.error(f"Error parsing WhatsApp webhook: {e}")
            
        return parsed

    def _parse_email_webhook(self, payload: Dict[str, Any], provider: str = "sendgrid") -> Dict[str, Any]:
        """Parse email webhook payload."""
        parsed = {}
        
        try:
            if provider.lower() == "sendgrid":
                # SendGrid inbound parse webhook
                parsed = {
                    'content': payload.get("text", "") or payload.get("html", ""),
                    'lead_id': self._extract_lead_id_from_email(payload.get("to", "")),
                    'timestamp': datetime.fromisoformat(payload.get("timestamp")) if payload.get("timestamp") else datetime.now(),
                    'metadata': {
                        'message_id': payload.get("message_id"),
                        'from_email': payload.get("from"),
                        'to_email': payload.get("to"),
                        'subject': payload.get("subject"),
                        'provider': 'sendgrid'
                    }
                }
            elif provider.lower() == "mailgun":
                # Mailgun webhook structure
                parsed = {
                    'content': payload.get("body-plain", "") or payload.get("body-html", ""),
                    'lead_id': self._extract_lead_id_from_email(payload.get("recipient", "")),
                    'timestamp': datetime.fromtimestamp(int(payload.get("timestamp", 0))),
                    'metadata': {
                        'message_id': payload.get("message-id"),
                        'from_email': payload.get("from"),
                        'to_email': payload.get("recipient"),
                        'subject': payload.get("subject"),
                        'provider': 'mailgun'
                    }
                }
        except Exception as e:
            logger.error(f"Error parsing email webhook: {e}")
            
        return parsed

    def _extract_lead_id_from_email(self, to_address: str) -> Optional[str]:
        """Extract lead ID from email address format like leads+{lead_id}@domain.com."""
        try:
            if "+" in to_address:
                local_part = to_address.split("@")[0]
                lead_part = local_part.split("+")[1]
                return lead_part
        except Exception:
            pass
        return None
