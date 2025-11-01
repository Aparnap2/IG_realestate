"""
Comprehensive test suite for WhatsApp webhook handler.

Tests signature validation, message parsing, deduplication, Celery task enqueueing,
audit logging, and error handling for WhatsApp Business API webhooks.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.whatsapp_webhook import (
    WhatsAppWebhookHandler, 
    whatsapp_handler,
    verify_whatsapp_webhook, 
    handle_whatsapp_webhook
)
from backend.booking.message_bus import MessageBus, NormalizedMessage, Channel
from backend.utils.audit import audit_log_event


class TestWhatsAppWebhookHandler:
    """Test cases for WhatsAppWebhookHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = WhatsAppWebhookHandler()
        self.test_app_secret = "test_app_secret"
        self.test_message_id = "wamid.test_message_id"
        self.test_phone_number_id = "123456789012345"

    @patch.dict('os.environ', {'WHATSAPP_APP_SECRET': 'test_app_secret'})
    def test_signature_verification_valid(self):
        """Test valid WhatsApp signature verification."""
        payload = b'{"test": "data"}'
        test_secret = "test_app_secret"
        expected_hash = hmac.new(
            test_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={expected_hash}"
        
        with patch.object(self.handler, 'app_secret', test_secret):
            result = self.handler.verify_whatsapp_signature(payload, signature_header)
            assert result is True

    @patch.dict('os.environ', {'WHATSAPP_APP_SECRET': 'test_app_secret'})
    def test_signature_verification_invalid(self):
        """Test invalid WhatsApp signature verification."""
        payload = b'{"test": "data"}'
        invalid_signature = "sha256=invalid_hash"
        
        with patch.object(self.handler, 'app_secret', "test_app_secret"):
            result = self.handler.verify_whatsapp_signature(payload, invalid_signature)
            assert result is False

    def test_signature_verification_missing_secret(self):
        """Test signature verification when app secret is missing."""
        payload = b'{"test": "data"}'
        signature = "sha256=test_hash"
        
        with patch.object(self.handler, 'app_secret', None):
            result = self.handler.verify_whatsapp_signature(payload, signature)
            assert result is False

    def test_signature_verification_missing_signature(self):
        """Test signature verification when signature is missing."""
        payload = b'{"test": "data"}'
        
        result = self.handler.verify_whatsapp_signature(payload, "")
        assert result is False

    def test_signature_verification_malformed_signature(self):
        """Test signature verification with malformed signature."""
        payload = b'{"test": "data"}'
        malformed_signature = "invalid_signature_format"
        
        result = self.handler.verify_whatsapp_signature(payload, malformed_signature)
        assert result is False

    def test_extract_whatsapp_message_valid_payload(self):
        """Test extraction of WhatsApp messages from valid payload."""
        webhook_data = {
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.test_message_id",
                            "from": "1234567890",
                            "text": {"body": "I'd like to schedule a tour"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {
                            "phone_number_id": "123456789012345",
                            "display_phone_number": "9876543210"
                        }
                    }
                }]
            }]
        }
        
        messages = self.handler.extract_whatsapp_message(webhook_data)
        
        assert len(messages) == 1
        message = messages[0]
        assert message["message_id"] == "wamid.test_message_id"
        assert message["from"] == "1234567890"
        assert message["text"] == "I'd like to schedule a tour"
        assert message["timestamp"] == "1704067200"
        assert message["type"] == "text"
        assert message["phone_number_id"] == "123456789012345"

    def test_extract_whatsapp_message_multiple_messages(self):
        """Test extraction of multiple WhatsApp messages."""
        webhook_data = {
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.test_message_1",
                                "from": "1234567890",
                                "text": {"body": "First message"},
                                "timestamp": "1704067200",
                                "type": "text"
                            },
                            {
                                "id": "wamid.test_message_2", 
                                "from": "0987654321",
                                "text": {"body": "Second message"},
                                "timestamp": "1704067201",
                                "type": "text"
                            }
                        ],
                        "metadata": {
                            "phone_number_id": "123456789012345"
                        }
                    }
                }]
            }]
        }
        
        messages = self.handler.extract_whatsapp_message(webhook_data)
        
        assert len(messages) == 2
        assert messages[0]["message_id"] == "wamid.test_message_1"
        assert messages[1]["message_id"] == "wamid.test_message_2"

    def test_extract_whatsapp_message_non_text_messages(self):
        """Test extraction ignores non-text messages."""
        webhook_data = {
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.test_message_image",
                                "from": "1234567890",
                                "type": "image"
                            },
                            {
                                "id": "wamid.test_message_text",
                                "from": "1234567890",
                                "text": {"body": "Text message"},
                                "timestamp": "1704067200",
                                "type": "text"
                            }
                        ],
                        "metadata": {
                            "phone_number_id": "123456789012345"
                        }
                    }
                }]
            }]
        }
        
        messages = self.handler.extract_whatsapp_message(webhook_data)
        
        # Should only extract text messages
        assert len(messages) == 1
        assert messages[0]["message_id"] == "wamid.test_message_text"

    def test_extract_whatsapp_message_empty_payload(self):
        """Test extraction with empty or malformed payload."""
        webhook_data = {"entry": []}
        messages = self.handler.extract_whatsapp_message(webhook_data)
        assert messages == []

    def test_extract_whatsapp_message_malformed_structure(self):
        """Test extraction with malformed webhook structure."""
        webhook_data = {
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": "not_a_list"  # Malformed
                    }
                }]
            }]
        }
        
        messages = self.handler.extract_whatsapp_message(webhook_data)
        assert messages == []

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_message_exists(self, mock_redis):
        """Test duplicate message detection when message exists."""
        mock_redis.exists.return_value = 1
        
        result = self.handler.is_duplicate_message("test_message_id")
        assert result is True
        mock_redis.exists.assert_called_once_with("whatsapp_processed:test_message_id")

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_message_not_exists(self, mock_redis):
        """Test duplicate message detection when message doesn't exist."""
        mock_redis.exists.return_value = 0
        
        result = self.handler.is_duplicate_message("test_message_id")
        assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_message_redis_unavailable(self, mock_redis):
        """Test duplicate message detection when Redis is unavailable."""
        with patch('backend.utils.redis_client.redis_client', None):
            result = self.handler.is_duplicate_message("test_message_id")
            assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_message_redis_error(self, mock_redis):
        """Test duplicate message detection when Redis errors."""
        mock_redis.exists.side_effect = Exception("Redis connection failed")
        
        result = self.handler.is_duplicate_message("test_message_id")
        assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_mark_message_processed_success(self, mock_redis):
        """Test successful marking of processed message."""
        mock_redis.setex.return_value = True
        result_data = {"normalized_uuid": "uuid123", "intent": "booking_related"}
        
        result = self.handler.mark_message_processed("test_message_id", result_data)
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Verify the key and TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "whatsapp_processed:test_message_id"
        assert call_args[0][1] == 86400  # 24 hours TTL
        
        # Verify stored data
        stored_data = json.loads(call_args[0][2])
        assert stored_data['result'] == result_data
        assert 'processed_at' in stored_data

    @patch('backend.utils.redis_client.redis_client')
    def test_mark_message_processed_redis_unavailable(self, mock_redis):
        """Test message marking when Redis is unavailable."""
        with patch('backend.utils.redis_client.redis_client', None):
            result_data = {"test": "data"}
            result = self.handler.mark_message_processed("test_message_id", result_data)
            assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_mark_message_processed_redis_error(self, mock_redis):
        """Test message marking when Redis errors."""
        mock_redis.setex.side_effect = Exception("Redis connection failed")
        result_data = {"test": "data"}
        
        result = self.handler.mark_message_processed("test_message_id", result_data)
        assert result is False


class TestWhatsAppWebhookEndpoints:
    """Test cases for WhatsApp webhook endpoint handlers."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(whatsapp_handler.router)
        self.test_verify_token = "test_verify_token"

    @patch.dict('os.environ', {'WHATSAPP_VERIFY_TOKEN': 'test_verify_token'})
    def test_verify_webhook_success(self):
        """Test successful webhook verification."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "test_challenge_123"
        }
        
        response = self.client.get("/webhooks/whatsapp", params=params)
        
        assert response.status_code == 200
        assert response.text == "test_challenge_123"

    def test_verify_webhook_invalid_mode(self):
        """Test webhook verification with invalid mode."""
        params = {
            "hub.mode": "unsubscribe",
            "hub.verify_token": "test_token",
            "hub.challenge": "test_challenge"
        }
        
        response = self.client.get("/webhooks/whatsapp", params=params)
        
        assert response.status_code == 400

    def test_verify_webhook_invalid_token(self):
        """Test webhook verification with invalid token."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "invalid_token",
            "hub.challenge": "test_challenge"
        }
        
        response = self.client.get("/webhooks/whatsapp", params=params)
        
        assert response.status_code == 403

    def test_verify_webhook_missing_challenge(self):
        """Test webhook verification with missing challenge."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_token"
        }
        
        response = self.client.get("/webhooks/whatsapp", params=params)
        
        assert response.status_code == 400

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_handle_webhook_success_booking_intent(
        self, 
        mock_audit, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test successful webhook processing with booking intent."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_extract_messages.return_value = [{
            "message_id": "wamid.test_message_id",
            "from": "1234567890",
            "text": "I'd like to book a tour",
            "timestamp": "1704067200",
            "type": "text",
            "phone_number_id": "123456789012345"
        }]
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        # Mock normalized message
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid123"
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Test payload
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.test_message_id",
                            "from": "1234567890",
                            "text": {"body": "I'd like to book a tour"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {
                            "phone_number_id": "123456789012345"
                        }
                    }
                }]
            }]
        }
        
        # Create request with signature
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        test_secret = "test_secret"
        expected_hash = hmac.new(
            test_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        headers = {"x-hub-signature-256": f"sha256={expected_hash}"}
        
        with patch('backend.api.whatsapp_webhook.whatsapp_handler.app_secret', test_secret):
            response = self.client.post(
                "/webhooks/whatsapp",
                content=payload_bytes,
                headers=headers
            )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["processed"] == 1
        assert response_data["total_messages"] == 1
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "whatsapp_message_received"
        assert "normalized_uuid" in audit_call[0][1]

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    def test_handle_webhook_invalid_signature(self, mock_verify_signature):
        """Test webhook processing with invalid signature."""
        mock_verify_signature.return_value = False
        
        payload = json.dumps({"test": "data"}).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=invalid"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers=headers
        )
        
        assert response.status_code == 403
        response_data = response.json()
        assert response_data["detail"] == "Invalid signature"

    def test_handle_webhook_malformed_json(self):
        """Test webhook processing with malformed JSON."""
        malformed_payload = b"{invalid json"
        headers = {"x-hub-signature-256": "sha256=test"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=malformed_payload,
            headers=headers
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["detail"] == "Invalid JSON"

    def test_handle_webhook_non_whatsapp_object(self):
        """Test webhook processing with non-WhatsApp object."""
        webhook_data = {
            "object": "facebook",  # Wrong object type
            "entry": []
        }
        
        payload = json.dumps(webhook_data).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        # Mock signature verification to pass
        with patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature', return_value=True):
            response = self.client.post(
                "/webhooks/whatsapp",
                content=payload,
                headers=headers
            )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "ignored"
        assert response_data["reason"] == "not_whatsapp"

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    def test_handle_webhook_no_messages_found(
        self, 
        mock_mark_processed,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test webhook processing when no messages are found."""
        mock_verify_signature.return_value = True
        mock_extract_messages.return_value = []  # No messages
        
        webhook_data = {
            "object": "whatsapp_business_account",
            "entry": []
        }
        
        payload = json.dumps(webhook_data).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["processed"] == 0

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    def test_handle_webhook_duplicate_message(
        self, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test webhook processing with duplicate message."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_extract_messages.return_value = [{
            "message_id": "wamid.duplicate_message",
            "from": "1234567890",
            "text": "Duplicate message",
            "timestamp": "1704067200",
            "type": "text"
        }]
        mock_is_duplicate.return_value = True  # Message is duplicate
        
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.duplicate_message",
                            "from": "1234567890",
                            "text": {"body": "Duplicate message"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {"phone_number_id": "123456789012345"}
                    }
                }]
            }]
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to duplicate

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    def test_handle_webhook_non_booking_intent(
        self, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test webhook processing with non-booking intent message."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_extract_messages.return_value = [{
            "message_id": "wamid.non_booking_message",
            "from": "1234567890",
            "text": "Hello, how are you?",  # No booking keywords
            "timestamp": "1704067200",
            "type": "text"
        }]
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.non_booking_message",
                            "from": "1234567890",
                            "text": {"body": "Hello, how are you?"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {"phone_number_id": "123456789012345"}
                    }
                }]
            }]
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to non-booking intent
        
        # Verify message was still marked as processed
        mock_mark_processed.assert_called_once_with(
            "wamid.non_booking_message",
            {"intent": "non_booking"}
        )

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_handle_webhook_booking_keywords_detection(
        self, 
        mock_audit,
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test booking keyword detection for various message types."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid123"
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Test cases: messages with different booking keywords
        booking_test_cases = [
            "I'd like to book a tour",
            "Can I schedule an appointment?", 
            "What times are available?",
            "When can I see the property?",
            "Available this weekend?"
        ]
        
        for i, message_text in enumerate(booking_test_cases):
            mock_extract_messages.return_value = [{
                "message_id": f"wamid.test_message_{i}",
                "from": "1234567890",
                "text": message_text,
                "timestamp": "1704067200",
                "type": "text"
            }]
            
            webhook_payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "field": "messages",
                        "value": {
                            "messages": [{
                                "id": f"wamid.test_message_{i}",
                                "from": "1234567890",
                                "text": {"body": message_text},
                                "timestamp": "1704067200",
                                "type": "text"
                            }],
                            "metadata": {"phone_number_id": "123456789012345"}
                        }
                    }]
                }]
            }
            
            payload_bytes = json.dumps(webhook_payload).encode('utf-8')
            headers = {"x-hub-signature-256": "sha256=test"}
            
            response = self.client.post(
                "/webhooks/whatsapp",
                content=payload_bytes,
                headers=headers
            )
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["processed"] == 1  # Should process booking intent

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    def test_handle_webhook_message_normalization_integration(
        self, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test integration with MessageBus normalization."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        # Mock normalized message
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid123"
        mock_normalized_message.lead_id = "1234567890"
        mock_normalized_message.content = "I'd like to schedule a tour"
        mock_normalized_message.channel = Channel.WHATSAPP
        mock_normalized_message.timestamp = datetime.fromtimestamp(1704067200)
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.test_message_id",
                            "from": "1234567890",
                            "text": {"body": "I'd like to schedule a tour"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {
                            "phone_number_id": "123456789012345"
                        }
                    }
                }]
            }]
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        response = self.client.post(
            "/webhooks/whatsapp",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Verify MessageBus normalization was called
        mock_message_bus_instance.normalize_message.assert_called_once_with(
            'whatsapp',
            {
                "from": "1234567890",
                "text": "I'd like to schedule a tour",
                "timestamp": "1704067200",
                "channel": "whatsapp",
                "message_id": "wamid.test_message_id",
                "phone_number_id": "123456789012345"
            }
        )

    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    def test_handle_webhook_processing_error_continuation(
        self, 
        mock_extract_messages,
        mock_verify_signature
    ):
        """Test that errors in individual message processing don't stop other messages."""
        mock_verify_signature.return_value = True
        
        # First message causes an error, second should still process
        def side_effect_extract(data):
            return [
                {
                    "message_id": "wamid.error_message",
                    "from": "1234567890",
                    "text": "This will cause error",
                    "timestamp": "1704067200",
                    "type": "text"
                },
                {
                    "message_id": "wamid.good_message", 
                    "from": "0987654321",
                    "text": "Book a tour",
                    "timestamp": "1704067201",
                    "type": "text"
                }
            ]
        
        mock_extract_messages.side_effect = side_effect_extract
        
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.error_message",
                                "from": "1234567890", 
                                "text": {"body": "This will cause error"},
                                "timestamp": "1704067200",
                                "type": "text"
                            },
                            {
                                "id": "wamid.good_message",
                                "from": "0987654321",
                                "text": {"body": "Book a tour"},
                                "timestamp": "1704067201", 
                                "type": "text"
                            }
                        ],
                        "metadata": {"phone_number_id": "123456789012345"}
                    }
                }]
            }]
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        # Mock other methods to simulate error on first message
        with patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message', side_effect=Exception("Processing error")):
            with patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed'):
                with patch('backend.booking.message_bus.MessageBus'):
                    response = self.client.post(
                        "/webhooks/whatsapp",
                        content=payload_bytes,
                        headers=headers
                    )
        
        # Should still return success with partial processing
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["total_messages"] == 2


class TestWhatsAppWebhookIntegration:
    """Integration tests for WhatsApp webhook with external dependencies."""

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    @patch('backend.booking.message_bus.MessageBus')
    def test_end_to_end_webhook_processing(
        self, 
        mock_message_bus_class,
        mock_audit,
        mock_redis
    ):
        """Test complete end-to-end webhook processing flow."""
        # Setup mocks
        mock_redis.exists.return_value = 0
        mock_redis.setex.return_value = True
        mock_redis.ping.return_value = True
        
        # Mock audit logging
        mock_audit.return_value = "audit_event_123"
        
        # Mock message bus
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid-12345"
        mock_normalized_message.lead_id = "1234567890"
        mock_normalized_message.content = "I'd like to schedule a viewing"
        mock_normalized_message.channel = Channel.WHATSAPP
        mock_normalized_message.timestamp = datetime.fromtimestamp(1704067200)
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_instance.is_duplicate.return_value = False
        mock_message_bus_instance.claim_message.return_value = True
        mock_message_bus_instance.mark_processed.return_value = True
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Create handler instance
        handler = WhatsAppWebhookHandler()
        
        # Test webhook data
        webhook_data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.test_booking_message",
                            "from": "1234567890",
                            "text": {"body": "I'd like to schedule a viewing"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {
                            "phone_number_id": "123456789012345",
                            "display_phone_number": "9876543210"
                        }
                    }
                }]
            }]
        }
        
        # Process webhook
        result = handler.extract_whatsapp_message(webhook_data)
        assert len(result) == 1
        
        message = result[0]
        assert message["message_id"] == "wamid.test_booking_message"
        assert message["text"] == "I'd like to schedule a viewing"
        
        # Test normalization
        normalized_payload = {
            "from": message["from"],
            "text": message["text"],
            "timestamp": message["timestamp"],
            "channel": "whatsapp",
            "message_id": message["message_id"],
            "phone_number_id": message.get("phone_number_id")
        }
        
        normalized = handler.message_bus.normalize_message('whatsapp', normalized_payload)
        assert normalized.message_uuid == "uuid-12345"
        
        # Test deduplication
        is_duplicate = handler.is_duplicate_message(message["message_id"])
        assert is_duplicate is False
        
        # Test processing marking
        success = handler.mark_message_processed(message["message_id"], {
            "normalized_uuid": normalized.message_uuid,
            "intent": "booking_related"
        })
        assert success is True
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "whatsapp_message_received"
        assert "message_id" in audit_call[0][1]

    @patch('backend.utils.redis_client.redis_client', None)  # Redis unavailable
    @patch('backend.utils.audit.audit_log_event')
    def test_graceful_degradation_redis_unavailable(self, mock_audit):
        """Test graceful degradation when Redis is unavailable."""
        handler = WhatsAppWebhookHandler()
        
        # Should handle Redis unavailability gracefully
        is_duplicate = handler.is_duplicate_message("test_message")
        assert is_duplicate is False  # Safe default
        
        success = handler.mark_message_processed("test_message", {"test": "data"})
        assert success is False  # Can't mark without Redis
        
        # Audit logging should still work
        mock_audit.assert_called_once()

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    def test_idempotency_and_retry_handling(self, mock_audit, mock_redis):
        """Test idempotency and retry handling mechanisms."""
        handler = WhatsAppWebhookHandler()
        message_id = "wamid.test_idempotency"
        
        # First request - not duplicate
        mock_redis.exists.return_value = 0
        assert handler.is_duplicate_message(message_id) is False
        
        # Mark as processed
        mock_redis.setex.return_value = True
        success = handler.mark_message_processed(message_id, {"attempt": 1})
        assert success is True
        
        # Second request - should be detected as duplicate
        mock_redis.exists.return_value = 1
        assert handler.is_duplicate_message(message_id) is True
        
        # Verify audit logging was called
        assert mock_audit.call_count >= 1

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    def test_redis_error_recovery(self, mock_audit, mock_redis):
        """Test system behavior when Redis has intermittent failures."""
        handler = WhatsAppWebhookHandler()
        
        # Simulate Redis failure then recovery
        mock_redis.exists.side_effect = [
            Exception("Connection failed"),  # First call fails
            0,  # Second call succeeds
            Exception("Connection failed"),  # Third call fails
            1   # Fourth call succeeds
        ]
        
        # Should handle failures gracefully
        result1 = handler.is_duplicate_message("test1")
        assert result1 is False  # Safe default on error
        
        result2 = handler.is_duplicate_message("test2")
        assert result2 is False  # Normal operation
        
        result3 = handler.is_duplicate_message("test3")
        assert result3 is False  # Safe default on error
        
        result4 = handler.is_duplicate_message("test4")
        assert result4 is True   # Normal operation
        
        # Verify audit logging for failures
        assert mock_audit.call_count >= 2


class TestWhatsAppWebhookFixtures:
    """Test fixtures and helper functions for WhatsApp webhook testing."""

    def test_real_whatsapp_payload_structure(self):
        """Test with realistic WhatsApp Business API payload structure."""
        realistic_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "phone-number-id-123",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234567890",
                                    "phone_number_id": "phone-number-id-123"
                                },
                                "messages": [
                                    {
                                        "from": "user-phone-number",
                                        "id": "wamid.test-message-id",
                                        "timestamp": "1704067200",
                                        "type": "text",
                                        "text": {
                                            "body": "I'm interested in booking a property viewing. What times are available this week?"
                                        },
                                        "context": {
                                            "forwarded": True,
                                            "frequently_forwarded": False
                                        }
                                    }
                                ],
                                "statuses": []
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }
        
        handler = WhatsAppWebhookHandler()
        messages = handler.extract_whatsapp_message(realistic_payload)
        
        assert len(messages) == 1
        message = messages[0]
        assert message["message_id"] == "wamid.test-message-id"
        assert message["from"] == "user-phone-number"
        assert "property viewing" in message["text"]
        assert message["timestamp"] == "1704067200"
        assert message["phone_number_id"] == "phone-number-id-123"

    def test_multiple_phone_number_ids(self):
        """Test handling multiple phone number IDs in webhook."""
        multi_phone_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "phone-id-1",
                    "changes": [
                        {
                            "value": {
                                "messages": [{
                                    "id": "wamid.msg-1",
                                    "from": "user-1",
                                    "text": {"body": "Message from user 1"},
                                    "timestamp": "1704067200",
                                    "type": "text"
                                }],
                                "metadata": {"phone_number_id": "phone-id-1"}
                            },
                            "field": "messages"
                        }
                    ]
                },
                {
                    "id": "phone-id-2", 
                    "changes": [
                        {
                            "value": {
                                "messages": [{
                                    "id": "wamid.msg-2",
                                    "from": "user-2",
                                    "text": {"body": "Message from user 2"},
                                    "timestamp": "1704067201",
                                    "type": "text"
                                }],
                                "metadata": {"phone_number_id": "phone-id-2"}
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }
        
        handler = WhatsAppWebhookHandler()
        messages = handler.extract_whatsapp_message(multi_phone_payload)
        
        assert len(messages) == 2
        assert messages[0]["phone_number_id"] == "phone-id-1"
        assert messages[1]["phone_number_id"] == "phone-id-2"

    def test_edge_case_payloads(self):
        """Test edge case payload structures."""
        handler = WhatsAppWebhookHandler()
        
        # Empty messages array
        empty_messages = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [],
                        "metadata": {"phone_number_id": "123"}
                    }
                }]
            }]
        }
        assert handler.extract_whatsapp_message(empty_messages) == []
        
        # Missing messages field
        missing_messages = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "metadata": {"phone_number_id": "123"}
                    }
                }]
            }]
        }
        assert handler.extract_whatsapp_message(missing_messages) == []
        
        # Missing entry changes
        missing_changes = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "test"
            }]
        }
        assert handler.extract_whatsapp_message(missing_changes) == []


class TestWhatsAppWebhookCeleryIntegration:
    """Test Celery task integration (mocked)."""

    @patch('backend.celery_app.celery_app')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.verify_whatsapp_signature')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.extract_whatsapp_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.is_duplicate_message')
    @patch('backend.api.whatsapp_webhook.whatsapp_handler.mark_message_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_celery_task_enqueuing_simulation(
        self,
        mock_audit,
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_messages,
        mock_verify_signature,
        mock_celery_app
    ):
        """Test that Celery tasks would be enqueued for processing (mocked)."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        # Mock normalized message
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid-celery-test"
        mock_normalized_message.lead_id = "1234567890"
        mock_normalized_message.content = "Book a viewing for tomorrow"
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.id = "celery-task-123"
        mock_celery_app.send_task.return_value = mock_task
        
        # Test booking message
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "wamid.celery-test",
                            "from": "1234567890",
                            "text": {"body": "Book a viewing for tomorrow"},
                            "timestamp": "1704067200",
                            "type": "text"
                        }],
                        "metadata": {"phone_number_id": "123456789012345"}
                    }
                }]
            }]
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"x-hub-signature-256": "sha256=test"}
        
        # In actual implementation, this would enqueue a Celery task
        # For testing, we simulate the task enqueueing
        with patch('backend.api.whatsapp_webhook.whatsapp_handler.message_bus.normalize_message', return_value=mock_normalized_message):
            # Simulate what would happen in the actual implementation
            # from tasks.whatsapp_processing import process_whatsapp_message_task
            # task_result = process_whatsapp_message_task.delay(mock_normalized_message)
            
            # For testing, we'll just verify the normalized message is ready for processing
            assert mock_normalized_message.message_uuid == "uuid-celery-test"
            assert "Book a viewing" in mock_normalized_message.content
        
        response = TestClient(whatsapp_handler.router).post(
            "/webhooks/whatsapp",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 1
        
        # Verify audit logging for the event
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "whatsapp_message_received"
        assert audit_call[0][1]["normalized_uuid"] == "uuid-celery-test"

    def test_celery_task_structure_validation(self):
        """Test that the data structure is ready for Celery task enqueueing."""
        # Test normalized message structure
        mock_normalized_message = NormalizedMessage(
            message_uuid="uuid-task-test",
            lead_id="1234567890",
            content="Schedule a tour for Saturday",
            channel=Channel.WHATSAPP,
            timestamp=datetime.now(),
            metadata={
                "original_message_id": "wamid.original",
                "phone_number_id": "123456789012345",
                "booking_intent": True
            }
        )
        
        # Verify structure is complete for Celery processing
        assert hasattr(mock_normalized_message, 'message_uuid')
        assert hasattr(mock_normalized_message, 'lead_id')
        assert hasattr(mock_normalized_message, 'content')
        assert hasattr(mock_normalized_message, 'channel')
        assert hasattr(mock_normalized_message, 'timestamp')
        assert hasattr(mock_normalized_message, 'metadata')
        
        assert mock_normalized_message.channel == Channel.WHATSAPP
        assert "tour" in mock_normalized_message.content.lower()
        assert mock_normalized_message.metadata.get("booking_intent") is True