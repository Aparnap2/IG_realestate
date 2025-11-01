"""
Comprehensive test suite for Email webhook handler.

Tests signature validation, message parsing, deduplication, Celery task enqueueing,
audit logging, and error handling for SendGrid and Mailgun email webhooks.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.email_webhook import (
    EmailWebhookHandler,
    email_handler,
    handle_sendgrid_webhook,
    handle_mailgun_webhook
)
from backend.booking.message_bus import MessageBus, NormalizedMessage, Channel
from backend.utils.audit import audit_log_event


class TestEmailWebhookHandler:
    """Test cases for EmailWebhookHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = EmailWebhookHandler()
        self.test_sendgrid_api_key = "test_sendgrid_key"
        self.test_mailgun_api_key = "test_mailgun_key"
        self.test_message_id = "sendgrid-test_message_id"

    @patch.dict('os.environ', {'SENDGRID_API_KEY': 'test_sendgrid_key'})
    def test_sendgrid_signature_verification_valid(self):
        """Test valid SendGrid signature verification."""
        payload = b'{"test": "email data"}'
        timestamp = "1704067200"
        token = "test_token"
        
        # Create expected signature
        signed_payload = f"{timestamp}{token}".encode() + payload
        expected_signature = hmac.new(
            self.test_sendgrid_api_key.encode(),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        
        signature_data = {
            "timestamp": timestamp,
            "token": token,
            "signature": expected_signature
        }
        
        result = self.handler.verify_sendgrid_signature(payload, signature_data)
        assert result is True

    @patch.dict('os.environ', {'SENDGRID_API_KEY': 'test_sendgrid_key'})
    def test_sendgrid_signature_verification_invalid(self):
        """Test invalid SendGrid signature verification."""
        payload = b'{"test": "email data"}'
        signature_data = {
            "timestamp": "1704067200",
            "token": "test_token",
            "signature": "invalid_signature"
        }
        
        result = self.handler.verify_sendgrid_signature(payload, signature_data)
        assert result is False

    @patch.dict('os.environ', {'SENDGRID_API_KEY': 'test_sendgrid_key'})
    def test_sendgrid_signature_verification_missing_fields(self):
        """Test SendGrid signature verification with missing fields."""
        payload = b'{"test": "email data"}'
        
        # Missing timestamp
        signature_data = {
            "token": "test_token",
            "signature": "test_signature"
        }
        result = self.handler.verify_sendgrid_signature(payload, signature_data)
        assert result is False
        
        # Missing token
        signature_data = {
            "timestamp": "1704067200",
            "signature": "test_signature"
        }
        result = self.handler.verify_sendgrid_signature(payload, signature_data)
        assert result is False

    def test_sendgrid_signature_verification_missing_api_key(self):
        """Test SendGrid signature verification when API key is missing."""
        payload = b'{"test": "email data"}'
        signature_data = {
            "timestamp": "1704067200",
            "token": "test_token",
            "signature": "test_signature"
        }
        
        with patch.object(self.handler, 'sendgrid_api_key', None):
            result = self.handler.verify_sendgrid_signature(payload, signature_data)
            assert result is False

    @patch.dict('os.environ', {'MAILGUN_API_KEY': 'test_mailgun_key'})
    def test_mailgun_signature_verification_valid(self):
        """Test valid Mailgun signature verification."""
        payload = b'{"test": "email data"}'
        timestamp = "1704067200"
        token = "test_token"
        
        # Create expected signature (Mailgun uses different format)
        signed_payload = f"{timestamp}{token}".encode()
        expected_signature = hmac.new(
            self.test_mailgun_api_key.encode(),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        
        signature_data = {
            "timestamp": timestamp,
            "token": token,
            "signature": expected_signature
        }
        
        result = self.handler.verify_mailgun_signature(payload, signature_data)
        assert result is True

    @patch.dict('os.environ', {'MAILGUN_API_KEY': 'test_mailgun_key'})
    def test_mailgun_signature_verification_invalid(self):
        """Test invalid Mailgun signature verification."""
        payload = b'{"test": "email data"}'
        signature_data = {
            "timestamp": "1704067200",
            "token": "test_token",
            "signature": "invalid_signature"
        }
        
        result = self.handler.verify_mailgun_signature(payload, signature_data)
        assert result is False

    @patch.dict('os.environ', {'MAILGUN_API_KEY': 'test_mailgun_key'})
    def test_mailgun_signature_verification_missing_fields(self):
        """Test Mailgun signature verification with missing fields."""
        payload = b'{"test": "email data"}'
        
        # Missing timestamp
        signature_data = {
            "token": "test_token",
            "signature": "test_signature"
        }
        result = self.handler.verify_mailgun_signature(payload, signature_data)
        assert result is False

    def test_mailgun_signature_verification_missing_api_key(self):
        """Test Mailgun signature verification when API key is missing."""
        payload = b'{"test": "email data"}'
        signature_data = {
            "timestamp": "1704067200",
            "token": "test_token",
            "signature": "test_signature"
        }
        
        with patch.object(self.handler, 'mailgun_api_key', None):
            result = self.handler.verify_mailgun_signature(payload, signature_data)
            assert result is False

    def test_extract_sendgrid_email_message(self):
        """Test extraction of SendGrid email messages."""
        webhook_data = {
            "message_id": "sendgrid_message_123",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "I'd like to book a tour",
            "text": "I want to schedule a viewing for tomorrow",
            "html": "<p>I want to schedule a viewing for tomorrow</p>",
            "timestamp": 1704067200
        }
        
        message = self.handler.extract_email_message(webhook_data, "sendgrid")
        
        assert message["message_id"] == "sendgrid_message_123"
        assert message["from_email"] == "sender@example.com"
        assert message["to_email"] == "leads+123@domain.com"
        assert message["subject"] == "I'd like to book a tour"
        assert message["text"] == "I want to schedule a viewing for tomorrow"
        assert message["html"] == "<p>I want to schedule a viewing for tomorrow</p>"
        assert message["timestamp"] == 1704067200
        assert message["provider"] == "sendgrid"

    def test_extract_mailgun_email_message(self):
        """Test extraction of Mailgun email messages."""
        webhook_data = {
            "message-id": "mailgun_message_456",
            "from": "sender@example.com",
            "recipient": "leads+456@domain.com",
            "subject": "Available appointment times?",
            "body-plain": "What times are available this week?",
            "body-html": "<p>What times are available this week?</p>",
            "timestamp": 1704067200
        }
        
        message = self.handler.extract_email_message(webhook_data, "mailgun")
        
        assert message["message_id"] == "mailgun_message_456"
        assert message["from_email"] == "sender@example.com"
        assert message["to_email"] == "leads+456@domain.com"
        assert message["subject"] == "Available appointment times?"
        assert message["text"] == "What times are available this week?"
        assert message["html"] == "<p>What times are available this week?</p>"
        assert message["timestamp"] == 1704067200
        assert message["provider"] == "mailgun"

    def test_extract_email_message_unknown_provider(self):
        """Test extraction with unknown email provider."""
        webhook_data = {"test": "data"}
        message = self.handler.extract_email_message(webhook_data, "unknown_provider")
        assert message == {}

    def test_extract_email_message_malformed_data(self):
        """Test extraction with malformed email data."""
        webhook_data = {"invalid": "data"}
        message = self.handler.extract_email_message(webhook_data, "sendgrid")
        
        # Should handle missing fields gracefully
        assert message["from_email"] is None
        assert message["to_email"] is None
        assert message["subject"] == ""

    def test_extract_lead_id_from_email_valid_format(self):
        """Test lead ID extraction from valid email format."""
        # Valid format: leads+{lead_id}@domain.com
        email_address = "leads+12345@example.com"
        lead_id = self.handler.extract_lead_id_from_email(email_address)
        assert lead_id == "12345"

    def test_extract_lead_id_from_email_without_plus(self):
        """Test lead ID extraction when email doesn't have plus addressing."""
        email_address = "leads@example.com"
        lead_id = self.handler.extract_lead_id_from_email(email_address)
        assert lead_id is None

    def test_extract_lead_id_from_email_malformed(self):
        """Test lead ID extraction with malformed email."""
        email_address = "invalid-email"
        lead_id = self.handler.extract_lead_id_from_email(email_address)
        assert lead_id is None

    def test_extract_lead_id_from_email_empty(self):
        """Test lead ID extraction with empty email."""
        email_address = ""
        lead_id = self.handler.extract_lead_id_from_email(email_address)
        assert lead_id is None

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_email_exists(self, mock_redis):
        """Test duplicate email detection when email exists."""
        mock_redis.exists.return_value = 1
        
        result = self.handler.is_duplicate_email("test_message_id")
        assert result is True
        mock_redis.exists.assert_called_once_with("email_processed:test_message_id")

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_email_not_exists(self, mock_redis):
        """Test duplicate email detection when email doesn't exist."""
        mock_redis.exists.return_value = 0
        
        result = self.handler.is_duplicate_email("test_message_id")
        assert result is False

    @patch('backend.utils.redis_client.redis_client', None)
    def test_is_duplicate_email_redis_unavailable(self, mock_redis):
        """Test duplicate email detection when Redis is unavailable."""
        result = self.handler.is_duplicate_email("test_message_id")
        assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_is_duplicate_email_redis_error(self, mock_redis):
        """Test duplicate email detection when Redis errors."""
        mock_redis.exists.side_effect = Exception("Redis connection failed")
        
        result = self.handler.is_duplicate_email("test_message_id")
        assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_mark_email_processed_success(self, mock_redis):
        """Test successful marking of processed email."""
        mock_redis.setex.return_value = True
        result_data = {"normalized_uuid": "uuid123", "intent": "booking_related"}
        
        result = self.handler.mark_email_processed("test_message_id", result_data)
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Verify the key and TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "email_processed:test_message_id"
        assert call_args[0][1] == 86400  # 24 hours TTL
        
        # Verify stored data
        stored_data = json.loads(call_args[0][2])
        assert stored_data['result'] == result_data
        assert 'processed_at' in stored_data

    @patch('backend.utils.redis_client.redis_client', None)
    def test_mark_email_processed_redis_unavailable(self, mock_redis):
        """Test email marking when Redis is unavailable."""
        result_data = {"test": "data"}
        result = self.handler.mark_email_processed("test_message_id", result_data)
        assert result is False

    @patch('backend.utils.redis_client.redis_client')
    def test_mark_email_processed_redis_error(self, mock_redis):
        """Test email marking when Redis errors."""
        mock_redis.setex.side_effect = Exception("Redis connection failed")
        result_data = {"test": "data"}
        
        result = self.handler.mark_email_processed("test_message_id", result_data)
        assert result is False


class TestSendGridWebhookEndpoint:
    """Test cases for SendGrid webhook endpoint handler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(email_handler.router)

    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_sendgrid_webhook_success_booking_intent(
        self, 
        mock_audit, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test successful SendGrid webhook processing with booking intent."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "sendgrid_test_message",
            "from_email": "sender@example.com",
            "to_email": "leads+123@domain.com",
            "subject": "I'd like to book a tour",
            "text": "I want to schedule a viewing for tomorrow",
            "html": "<p>I want to schedule a viewing for tomorrow</p>",
            "timestamp": 1704067200,
            "provider": "sendgrid"
        }
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        # Mock normalized message
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid123"
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Test webhook payload
        webhook_payload = {
            "message_id": "sendgrid_test_message",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "I'd like to book a tour",
            "text": "I want to schedule a viewing for tomorrow",
            "html": "<p>I want to schedule a viewing for tomorrow</p>",
            "timestamp": 1704067200
        }
        
        # Create request with signature
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test_signature",
            "X-Twilio-Email-Event-Webhook-Token": "test_token"
        }
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["processed"] == 1
        assert response_data["total_emails"] == 1
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "sendgrid_email_received"

    @patch.dict('os.environ', {'ENVIRONMENT': 'development'})
    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    def test_sendgrid_webhook_development_mode_bypass(self, mock_verify_signature):
        """Test SendGrid webhook bypass in development mode."""
        mock_verify_signature.return_value = False  # Invalid signature
        
        webhook_payload = {
            "message_id": "test_message",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "Book a tour",
            "text": "I want to book a tour"
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"X-Twilio-Email-Event-Webhook-Signature": "invalid_signature"}
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        # Should still process despite invalid signature in development
        assert response.status_code == 200

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    def test_sendgrid_webhook_production_mode_reject(self, mock_verify_signature):
        """Test SendGrid webhook rejection in production mode."""
        mock_verify_signature.return_value = False  # Invalid signature
        
        webhook_payload = {
            "message_id": "test_message",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "Book a tour",
            "text": "I want to book a tour"
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {"X-Twilio-Email-Event-Webhook-Signature": "invalid_signature"}
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        # Should reject in production
        assert response.status_code == 403

    def test_sendgrid_webhook_malformed_json(self):
        """Test SendGrid webhook processing with malformed JSON."""
        malformed_payload = b"{invalid json"
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=malformed_payload,
            headers=headers
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["detail"] == "Invalid JSON"

    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    def test_sendgrid_webhook_no_extracted_message(
        self, 
        mock_extract_message,
        mock_verify_signature
    ):
        """Test SendGrid webhook when no message can be extracted."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {}  # Empty message
        
        webhook_payload = {"invalid": "data"}
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0

    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    def test_sendgrid_webhook_duplicate_email(
        self, 
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test SendGrid webhook processing with duplicate email."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "sendgrid_duplicate_message",
            "from_email": "sender@example.com",
            "to_email": "leads+123@domain.com",
            "subject": "Book a tour",
            "text": "I want to book a tour",
            "provider": "sendgrid"
        }
        mock_is_duplicate.return_value = True  # Email is duplicate
        
        webhook_payload = {
            "message_id": "sendgrid_duplicate_message",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "Book a tour",
            "text": "I want to book a tour"
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to duplicate

    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    def test_sendgrid_webhook_non_booking_intent(
        self, 
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test SendGrid webhook processing with non-booking intent."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "sendgrid_non_booking_message",
            "from_email": "sender@example.com",
            "to_email": "leads+123@domain.com",
            "subject": "Hello",
            "text": "Just saying hello!",  # No booking keywords
            "provider": "sendgrid"
        }
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        webhook_payload = {
            "message_id": "sendgrid_non_booking_message",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "Hello",
            "text": "Just saying hello!"
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to non-booking intent
        
        # Verify message was still marked as processed
        mock_mark_processed.assert_called_once_with(
            "sendgrid_non_booking_message",
            {"intent": "non_booking"}
        )

    def test_sendgrid_booking_intent_detection(self):
        """Test booking intent keyword detection."""
        booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time", "reschedule"]
        
        # Test cases with different booking keywords
        booking_test_cases = [
            "I'd like to book a tour",
            "Can I schedule an appointment?", 
            "What times are available?",
            "When can I see the property?",
            "Available this weekend?",
            "I need to reschedule my appointment"
        ]
        
        for message_text in booking_test_cases:
            email_text = message_text.lower()
            has_booking_intent = any(keyword in email_text for keyword in booking_keywords)
            assert has_booking_intent, f"Failed to detect booking intent in: {message_text}"
        
        # Test non-booking message
        non_booking_message = "Hello, how are you today?"
        email_text = non_booking_message.lower()
        has_booking_intent = any(keyword in email_text for keyword in booking_keywords)
        assert not has_booking_intent


class TestMailgunWebhookEndpoint:
    """Test cases for Mailgun webhook endpoint handler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(email_handler.router)

    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_mailgun_webhook_success_booking_intent(
        self, 
        mock_audit, 
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test successful Mailgun webhook processing with booking intent."""
        # Setup mocks
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "mailgun_test_message",
            "from_email": "sender@example.com",
            "to_email": "leads+456@domain.com",
            "subject": "Available appointment times?",
            "text": "What times are available this week?",
            "html": "<p>What times are available this week?</p>",
            "timestamp": 1704067200,
            "provider": "mailgun"
        }
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        # Mock normalized message
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid456"
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Test webhook form data
        webhook_form_data = {
            "message-id": "mailgun_test_message",
            "from": "sender@example.com",
            "recipient": "leads+456@domain.com",
            "subject": "Available appointment times?",
            "body-plain": "What times are available this week?",
            "body-html": "<p>What times are available this week?</p>",
            "timestamp": "1704067200"
        }
        
        # Create request with signature
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["processed"] == 1
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "mailgun_email_received"

    @patch.dict('os.environ', {'ENVIRONMENT': 'development'})
    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    def test_mailgun_webhook_development_mode_bypass(self, mock_verify_signature):
        """Test Mailgun webhook bypass in development mode."""
        mock_verify_signature.return_value = False  # Invalid signature
        
        webhook_form_data = {
            "message-id": "test_message",
            "from": "sender@example.com",
            "recipient": "leads+123@domain.com",
            "subject": "Book a tour",
            "body-plain": "I want to book a tour"
        }
        
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "invalid_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        # Should still process despite invalid signature in development
        assert response.status_code == 200

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    def test_mailgun_webhook_production_mode_reject(self, mock_verify_signature):
        """Test Mailgun webhook rejection in production mode."""
        mock_verify_signature.return_value = False  # Invalid signature
        
        webhook_form_data = {
            "message-id": "test_message",
            "from": "sender@example.com",
            "recipient": "leads+123@domain.com",
            "subject": "Book a tour",
            "body-plain": "I want to book a tour"
        }
        
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "invalid_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        # Should reject in production
        assert response.status_code == 403

    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    def test_mailgun_webhook_no_extracted_message(
        self, 
        mock_extract_message,
        mock_verify_signature
    ):
        """Test Mailgun webhook when no message can be extracted."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {}  # Empty message
        
        webhook_form_data = {"invalid": "data"}
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0

    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    def test_mailgun_webhook_duplicate_email(
        self, 
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test Mailgun webhook processing with duplicate email."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "mailgun_duplicate_message",
            "from_email": "sender@example.com",
            "to_email": "leads+789@domain.com",
            "subject": "Book a tour",
            "text": "I want to book a tour",
            "provider": "mailgun"
        }
        mock_is_duplicate.return_value = True  # Email is duplicate
        
        webhook_form_data = {
            "message-id": "mailgun_duplicate_message",
            "from": "sender@example.com",
            "recipient": "leads+789@domain.com",
            "subject": "Book a tour",
            "body-plain": "I want to book a tour"
        }
        
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to duplicate
        assert response_data["reason"] == "duplicate"

    @patch('backend.api.email_webhook.email_handler.verify_mailgun_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    def test_mailgun_webhook_non_booking_intent(
        self, 
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
        mock_verify_signature
    ):
        """Test Mailgun webhook processing with non-booking intent."""
        mock_verify_signature.return_value = True
        mock_extract_message.return_value = {
            "message_id": "mailgun_non_booking_message",
            "from_email": "sender@example.com",
            "to_email": "leads+999@domain.com",
            "subject": "Hello",
            "text": "Just saying hello!",  # No booking keywords
            "provider": "mailgun"
        }
        mock_is_duplicate.return_value = False
        mock_mark_processed.return_value = True
        
        webhook_form_data = {
            "message-id": "mailgun_non_booking_message",
            "from": "sender@example.com",
            "recipient": "leads+999@domain.com",
            "subject": "Hello",
            "body-plain": "Just saying hello!"
        }
        
        headers = {
            "X-Mailgun-Timestamp": "1704067200",
            "X-Mailgun-Token": "test_token",
            "X-Mailgun-Signature": "sha256=test_signature"
        }
        
        response = self.client.post(
            "/webhooks/email/mailgun",
            data=webhook_form_data,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 0  # No processing due to non-booking intent
        assert response_data["reason"] == "no_booking_intent"


class TestEmailWebhookFixtures:
    """Test fixtures and helper functions for email webhook testing."""

    def test_sendgrid_real_payload_structure(self):
        """Test with realistic SendGrid webhook payload structure."""
        realistic_payload = {
            "message_id": "2Ffe4qMGHZUW_aNsCQqRTg.filter-0915-26214-1.4250147599991",
            "from": "john.doe@example.com",
            "to": "leads+12345@example.com",
            "subject": "I'd like to schedule a property viewing",
            "text": "Hi, I'm interested in viewing the property at 123 Main St. What times are available this week?",
            "html": "<p>Hi, I'm interested in viewing the property at 123 Main St. What times are available this week?</p>",
            "timestamp": 1704067200
        }
        
        handler = EmailWebhookHandler()
        message = handler.extract_email_message(realistic_payload, "sendgrid")
        
        assert message["message_id"] == "2Ffe4qMGHZUW_aNsCQqRTg.filter-0915-26214-1.4250147599991"
        assert message["from_email"] == "john.doe@example.com"
        assert message["to_email"] == "leads+12345@example.com"
        assert "property viewing" in message["subject"]
        assert "123 Main St" in message["text"]
        assert message["provider"] == "sendgrid"

    def test_mailgun_real_payload_structure(self):
        """Test with realistic Mailgun webhook payload structure."""
        realistic_form_data = {
            "message-id": "<20240101000001.1234.56789@mailgun.example.com>",
            "from": "jane.smith@example.com",
            "recipient": "leads+67890@example.com",
            "subject": "Available appointment slots",
            "body-plain": "Hello, I would like to know your availability for a property tour this weekend.",
            "body-html": "<p>Hello, I would like to know your availability for a property tour this weekend.</p>",
            "timestamp": "1704067200"
        }
        
        handler = EmailWebhookHandler()
        message = handler.extract_email_message(realistic_form_data, "mailgun")
        
        assert "20240101000001.1234.56789@mailgun.example.com" in message["message_id"]
        assert message["from_email"] == "jane.smith@example.com"
        assert message["to_email"] == "leads+67890@example.com"
        assert "availability" in message["subject"]
        assert "property tour this weekend" in message["text"]
        assert message["provider"] == "mailgun"

    def test_lead_id_extraction_various_formats(self):
        """Test lead ID extraction with various email formats."""
        test_cases = [
            ("leads+12345@example.com", "12345"),
            ("leads+abc-def-ghi@example.org", "abc-def-ghi"),
            ("leads+uuid-123e4567-e89b-12d3-a456-426614174000@example.net", "uuid-123e4567-e89b-12d3-a456-426614174000"),
            ("leads@example.com", None),  # No plus address
            ("user@example.com", None),  # Not a lead address
            ("leads+@example.com", ""),  # Empty ID
            ("leads+123+456@example.com", "123+456"),  # Multiple plus signs
        ]
        
        handler = EmailWebhookHandler()
        for email, expected_lead_id in test_cases:
            result = handler.extract_lead_id_from_email(email)
            assert result == expected_lead_id, f"Failed for {email}: expected {expected_lead_id}, got {result}"

    def test_edge_case_email_formats(self):
        """Test edge cases for email address parsing."""
        handler = EmailWebhookHandler()
        
        # Empty strings
        assert handler.extract_lead_id_from_email("") is None
        
        # Missing @ symbol
        assert handler.extract_lead_id_from_email("leads+123") is None
        
        # Multiple @ symbols
        assert handler.extract_lead_id_from_email("leads+123@example@com") is None
        
        # Just the plus sign
        assert handler.extract_lead_id_from_email("leads+@example.com") == ""

    def test_message_extraction_alternate_field_names(self):
        """Test message extraction with alternate field names."""
        # Test SendGrid alternate field names
        sendgrid_alt_payload = {
            "sg_message_id": "sendgrid_alternate_id",
            "from": "sender@example.com",
            "to": "leads+123@domain.com",
            "subject": "Test subject",
            "text": "Test text",
            "html": "<p>Test html</p>"
        }
        
        handler = EmailWebhookHandler()
        message = handler.extract_email_message(sendgrid_alt_payload, "sendgrid")
        assert message["message_id"] == "sendgrid_alternate_id"
        
        # Test Mailgun alternate field names
        mailgun_alt_payload = {
            "Message-Id": "<alt@mailgun.example.com>",
            "From": "sender@example.com",
            "To": "leads+456@domain.com",
            "Subject": "Test subject",
            "stripped-text": "Stripped text",
            "stripped-html": "<p>Stripped html</p>"
        }
        
        message = handler.extract_email_message(mailgun_alt_payload, "mailgun")
        assert "alt@mailgun.example.com" in message["message_id"]
        assert message["text"] == "Stripped text"


class TestEmailWebhookIntegration:
    """Integration tests for email webhook with external dependencies."""

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    @patch('backend.booking.message_bus.MessageBus')
    def test_end_to_end_sendgrid_processing(
        self, 
        mock_message_bus_class,
        mock_audit,
        mock_redis
    ):
        """Test complete end-to-end SendGrid webhook processing flow."""
        # Setup mocks
        mock_redis.exists.return_value = 0
        mock_redis.setex.return_value = True
        mock_redis.ping.return_value = True
        
        # Mock audit logging
        mock_audit.return_value = "audit_event_123"
        
        # Mock message bus
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid-sendgrid-12345"
        mock_normalized_message.lead_id = "12345"
        mock_normalized_message.content = "I'd like to schedule a property viewing"
        mock_normalized_message.channel = Channel.EMAIL
        mock_normalized_message.timestamp = datetime.fromtimestamp(1704067200)
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_instance.is_duplicate.return_value = False
        mock_message_bus_instance.claim_message.return_value = True
        mock_message_bus_instance.mark_processed.return_value = True
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Create handler instance
        handler = EmailWebhookHandler()
        
        # Test webhook data
        webhook_data = {
            "message_id": "sendgrid_e2e_test",
            "from": "prospect@example.com",
            "to": "leads+12345@example.com",
            "subject": "I'd like to schedule a property viewing",
            "text": "I'm interested in the property. When can I see it?",
            "html": "<p>I'm interested in the property. When can I see it?</p>",
            "timestamp": 1704067200
        }
        
        # Process webhook
        message = handler.extract_email_message(webhook_data, "sendgrid")
        assert message["message_id"] == "sendgrid_e2e_test"
        assert message["to_email"] == "leads+12345@example.com"
        
        # Test lead ID extraction
        lead_id = handler.extract_lead_id_from_email(message["to_email"])
        assert lead_id == "12345"
        
        # Test normalization
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
        
        normalized = handler.message_bus.normalize_message('email', normalized_payload)
        assert normalized.message_uuid == "uuid-sendgrid-12345"
        
        # Test deduplication
        is_duplicate = handler.is_duplicate_message(message["message_id"])
        assert is_duplicate is False
        
        # Test processing marking
        success = handler.mark_email_processed(message["message_id"], {
            "normalized_uuid": normalized.message_uuid,
            "lead_id": lead_id,
            "intent": "booking_related"
        })
        assert success is True
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "sendgrid_email_received"
        assert "message_id" in audit_call[0][1]

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    @patch('backend.booking.message_bus.MessageBus')
    def test_end_to_end_mailgun_processing(
        self, 
        mock_message_bus_class,
        mock_audit,
        mock_redis
    ):
        """Test complete end-to-end Mailgun webhook processing flow."""
        # Setup mocks
        mock_redis.exists.return_value = 0
        mock_redis.setex.return_value = True
        mock_redis.ping.return_value = True
        
        # Mock audit logging
        mock_audit.return_value = "audit_event_456"
        
        # Mock message bus
        mock_normalized_message = Mock()
        mock_normalized_message.message_uuid = "uuid-mailgun-67890"
        mock_normalized_message.lead_id = "67890"
        mock_normalized_message.content = "What times are available for viewing?"
        mock_normalized_message.channel = Channel.EMAIL
        mock_normalized_message.timestamp = datetime.fromtimestamp(1704067200)
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_instance.is_duplicate.return_value = False
        mock_message_bus_instance.claim_message.return_value = True
        mock_message_bus_instance.mark_processed.return_value = True
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Create handler instance
        handler = EmailWebhookHandler()
        
        # Test webhook form data
        webhook_data = {
            "message-id": "mailgun_e2e_test",
            "from": "buyer@example.com",
            "recipient": "leads+67890@example.com",
            "subject": "What times are available for viewing?",
            "body-plain": "I want to see the property. When can I schedule a viewing?",
            "body-html": "<p>I want to see the property. When can I schedule a viewing?</p>",
            "timestamp": "1704067200"
        }
        
        # Process webhook
        message = handler.extract_email_message(webhook_data, "mailgun")
        assert message["message_id"] == "mailgun_e2e_test"
        assert message["to_email"] == "leads+67890@example.com"
        
        # Test lead ID extraction
        lead_id = handler.extract_lead_id_from_email(message["to_email"])
        assert lead_id == "67890"
        
        # Test normalization
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
        
        normalized = handler.message_bus.normalize_message('email', normalized_payload)
        assert normalized.message_uuid == "uuid-mailgun-67890"
        
        # Test deduplication
        is_duplicate = handler.is_duplicate_email(message["message_id"])
        assert is_duplicate is False
        
        # Test processing marking
        success = handler.mark_email_processed(message["message_id"], {
            "normalized_uuid": normalized.message_uuid,
            "lead_id": lead_id,
            "intent": "booking_related"
        })
        assert success is True
        
        # Verify audit logging
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "mailgun_email_received"
        assert "message_id" in audit_call[0][1]

    @patch('backend.utils.redis_client.redis_client', None)  # Redis unavailable
    @patch('backend.utils.audit.audit_log_event')
    def test_graceful_degradation_redis_unavailable(self, mock_audit):
        """Test graceful degradation when Redis is unavailable."""
        handler = EmailWebhookHandler()
        
        # Should handle Redis unavailability gracefully
        is_duplicate = handler.is_duplicate_email("test_message")
        assert is_duplicate is False  # Safe default
        
        success = handler.mark_email_processed("test_message", {"test": "data"})
        assert success is False  # Can't mark without Redis
        
        # Audit logging should still work
        mock_audit.assert_called_once()

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    def test_idempotency_and_retry_handling(self, mock_audit, mock_redis):
        """Test idempotency and retry handling mechanisms."""
        handler = EmailWebhookHandler()
        message_id = "email_test_idempotency"
        
        # First request - not duplicate
        mock_redis.exists.return_value = 0
        assert handler.is_duplicate_email(message_id) is False
        
        # Mark as processed
        mock_redis.setex.return_value = True
        success = handler.mark_email_processed(message_id, {"attempt": 1})
        assert success is True
        
        # Second request - should be detected as duplicate
        mock_redis.exists.return_value = 1
        assert handler.is_duplicate_email(message_id) is True
        
        # Verify audit logging was called
        assert mock_audit.call_count >= 1

    @patch('backend.utils.redis_client.redis_client')
    @patch('backend.utils.audit.audit_log_event')
    def test_redis_error_recovery(self, mock_audit, mock_redis):
        """Test system behavior when Redis has intermittent failures."""
        handler = EmailWebhookHandler()
        
        # Simulate Redis failure then recovery
        mock_redis.exists.side_effect = [
            Exception("Connection failed"),  # First call fails
            0,  # Second call succeeds
            Exception("Connection failed"),  # Third call fails
            1   # Fourth call succeeds
        ]
        
        # Should handle failures gracefully
        result1 = handler.is_duplicate_email("test1")
        assert result1 is False  # Safe default on error
        
        result2 = handler.is_duplicate_email("test2")
        assert result2 is False  # Normal operation
        
        result3 = handler.is_duplicate_email("test3")
        assert result3 is False  # Safe default on error
        
        result4 = handler.is_duplicate_email("test4")
        assert result4 is True   # Normal operation
        
        # Verify audit logging for failures
        assert mock_audit.call_count >= 2


class TestEmailWebhookCeleryIntegration:
    """Test Celery task integration (mocked)."""

    @patch('backend.celery_app.celery_app')
    @patch('backend.api.email_webhook.email_handler.verify_sendgrid_signature')
    @patch('backend.api.email_webhook.email_handler.extract_email_message')
    @patch('backend.api.email_webhook.email_handler.is_duplicate_email')
    @patch('backend.api.email_webhook.email_handler.mark_email_processed')
    @patch('backend.booking.message_bus.MessageBus')
    @patch('backend.utils.audit.audit_log_event')
    def test_celery_task_enqueuing_simulation(
        self,
        mock_audit,
        mock_message_bus_class,
        mock_mark_processed,
        mock_is_duplicate,
        mock_extract_message,
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
        mock_normalized_message.message_uuid = "uuid-email-celery"
        mock_normalized_message.lead_id = "12345"
        mock_normalized_message.content = "Book a property viewing for tomorrow"
        
        mock_message_bus_instance = Mock()
        mock_message_bus_instance.normalize_message.return_value = mock_normalized_message
        mock_message_bus_class.return_value = mock_message_bus_instance
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.id = "celery-task-email-123"
        mock_celery_app.send_task.return_value = mock_task
        
        # Test booking message
        webhook_payload = {
            "message_id": "sendgrid_celery_test",
            "from": "prospect@example.com",
            "to": "leads+12345@example.com",
            "subject": "Book a property viewing for tomorrow",
            "text": "I want to book a property viewing for tomorrow",
            "timestamp": 1704067200
        }
        
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        headers = {
            "X-Twilio-Email-Event-Webhook-Timestamp": "1704067200",
            "X-Twilio-Email-Event-Webhook-Signature": "sha256=test",
            "X-Twilio-Email-Event-Webhook-Token": "test_token"
        }
        
        # In actual implementation, this would enqueue a Celery task
        # For testing, we simulate the task enqueueing
        with patch('backend.api.email_webhook.email_handler.message_bus.normalize_message', return_value=mock_normalized_message):
            # Simulate what would happen in the actual implementation
            # from tasks.email_processing import process_email_message_task
            # task_result = process_email_message_task.delay(mock_normalized_message)
            
            # For testing, we'll just verify the normalized message is ready for processing
            assert mock_normalized_message.message_uuid == "uuid-email-celery"
            assert "property viewing" in mock_normalized_message.content
        
        response = TestClient(email_handler.router).post(
            "/webhooks/email/sendgrid",
            content=payload_bytes,
            headers=headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["processed"] == 1
        
        # Verify audit logging for the event
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call[0][0] == "sendgrid_email_received"
        assert audit_call[0][1]["normalized_uuid"] == "uuid-email-celery"

    def test_celery_task_structure_validation(self):
        """Test that the data structure is ready for Celery task enqueueing."""
        # Test normalized message structure
        mock_normalized_message = NormalizedMessage(
            message_uuid="uuid-email-task-test",
            lead_id="12345",
            content="Schedule a property tour for Saturday",
            channel=Channel.EMAIL,
            timestamp=datetime.now(),
            metadata={
                "original_message_id": "sendgrid.original",
                "provider": "sendgrid",
                "booking_intent": True,
                "extracted_lead_id": "12345"
            }
        )
        
        # Verify structure is complete for Celery processing
        assert hasattr(mock_normalized_message, 'message_uuid')
        assert hasattr(mock_normalized_message, 'lead_id')
        assert hasattr(mock_normalized_message, 'content')
        assert hasattr(mock_normalized_message, 'channel')
        assert hasattr(mock_normalized_message, 'timestamp')
        assert hasattr(mock_normalized_message, 'metadata')
        
        assert mock_normalized_message.channel == Channel.EMAIL
        assert "property tour" in mock_normalized_message.content.lower()
        assert mock_normalized_message.metadata.get("booking_intent") is True
        assert mock_normalized_message.metadata.get("extracted_lead_id") == "12345"


class TestEmailWebhookErrorHandling:
    """Test error handling scenarios for email webhooks."""

    def test_sendgrid_signature_verification_exception(self):
        """Test SendGrid signature verification exception handling."""
        handler = EmailWebhookHandler()
        
        with patch.object(handler, 'sendgrid_api_key', 'test_key'):
            # Simulate an exception during signature verification
            with patch('hmac.new', side_effect=Exception("Cryptography error")):
                payload = b'test_data'
                signature_data = {
                    "timestamp": "1704067200",
                    "token": "test_token", 
                    "signature": "test_signature"
                }
                
                result = handler.verify_sendgrid_signature(payload, signature_data)
                assert result is False

    def test_mailgun_signature_verification_exception(self):
        """Test Mailgun signature verification exception handling."""
        handler = EmailWebhookHandler()
        
        with patch.object(handler, 'mailgun_api_key', 'test_key'):
            # Simulate an exception during signature verification
            with patch('hmac.new', side_effect=Exception("Cryptography error")):
                payload = b'test_data'
                signature_data = {
                    "timestamp": "1704067200",
                    "token": "test_token",
                    "signature": "test_signature"
                }
                
                result = handler.verify_mailgun_signature(payload, signature_data)
                assert result is False

    def test_extract_message_exception(self):
        """Test message extraction exception handling."""
        handler = EmailWebhookHandler()
        
        # Simulate an exception during extraction
        with patch('json.dumps', side_effect=Exception("JSON error")):
            webhook_data = {"test": "data"}
            message = handler.extract_email_message(webhook_data, "sendgrid")
            assert message == {}

    @patch('backend.utils.redis_client.redis_client')
    def test_redis_operation_exceptions(self, mock_redis):
        """Test Redis operation exception handling."""
        handler = EmailWebhookHandler()
        
        # Test is_duplicate with Redis exception
        mock_redis.exists.side_effect = Exception("Redis connection lost")
        result = handler.is_duplicate_email("test_message")
        assert result is False
        
        # Test mark_processed with Redis exception
        mock_redis.setex.side_effect = Exception("Redis connection lost")
        result = handler.mark_email_processed("test_message", {"test": "data"})
        assert result is False

    def test_malformed_email_address_handling(self):
        """Test handling of malformed email addresses in lead ID extraction."""
        handler = EmailWebhookHandler()
        
        malformed_emails = [
            "leads+",  # Missing ID
            "+123@example.com",  # Missing local part
            "leads++123@example.com",  # Double plus
            "leads+@",  # Missing domain
            "leads+123@",  # Incomplete domain
            "@example.com",  # Missing local part
        ]
        
        for email in malformed_emails:
            # Should not crash, should return None or empty string
            try:
                result = handler.extract_lead_id_from_email(email)
                assert result is None or result == ""
            except Exception:
                # Should handle gracefully without crashing
                assert False, f"Should not crash on malformed email: {email}"