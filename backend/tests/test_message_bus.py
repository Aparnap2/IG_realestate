"""
Test suite for Multi-Channel Message Bus

Tests UUID-based deduplication and channel normalization across Instagram, WhatsApp, Email.
"""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from backend.booking.message_bus import MessageBus, NormalizedMessage, Channel


class TestMessageBus:
    """Test cases for message bus functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.bus = MessageBus()

    def test_channel_enum(self):
        """Test channel enum values."""
        assert Channel.INSTAGRAM.value == "ig"
        assert Channel.WHATSAPP.value == "whatsapp"
        assert Channel.EMAIL.value == "email"

    @patch('backend.booking.message_bus.redis_client')
    def test_normalize_instagram_message(self, mock_redis):
        """Test Instagram message normalization."""
        raw_payload = {
            "object": "instagram",
            "entry": [{
                "changes": [{
                    "field": "comments",
                    "value": {
                        "from": {"id": "user_123", "name": "John Doe"},
                        "text": "Looking for 3BR condo",
                        "id": "comment_456",
                        "created_time": "2024-01-01T10:00:00Z"
                    }
                }]
            }]
        }

        normalized = self.bus.normalize_message("instagram", raw_payload)

        assert isinstance(normalized, NormalizedMessage)
        assert normalized.channel == Channel.INSTAGRAM
        assert normalized.lead_id == "user_123"
        assert "3BR condo" in normalized.content
        assert len(normalized.message_uuid) > 0  # UUID generated

    @patch('backend.booking.message_bus.redis_client')
    def test_normalize_whatsapp_message(self, mock_redis):
        """Test WhatsApp message normalization."""
        raw_payload = {
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "id": "msg_789",
                            "from": "1234567890",
                            "text": {"body": "Need tour tomorrow"},
                            "timestamp": "1704067200",  # 2024-01-01 00:00:00 UTC
                            "type": "text"
                        }]
                    }
                }]
            }]
        }

        normalized = self.bus.normalize_message("whatsapp", raw_payload)

        assert normalized.channel == Channel.WHATSAPP
        assert normalized.lead_id == "1234567890"
        assert normalized.content == "Need tour tomorrow"
        assert isinstance(normalized.timestamp, datetime)

    @patch('backend.booking.message_bus.redis_client')
    def test_normalize_email_message(self, mock_redis):
        """Test email message normalization."""
        raw_payload = {
            "message_id": "email_123",
            "from": "john@example.com",
            "to": "leads+lead_456@domain.com",
            "subject": "Property Inquiry",
            "text": "Interested in your 2BR listing",
            "timestamp": "2024-01-01T10:00:00Z"
        }

        normalized = self.bus.normalize_message("email", raw_payload)

        assert normalized.channel == Channel.EMAIL
        assert normalized.lead_id == "lead_456"  # Extracted from email address
        assert "2BR listing" in normalized.content

    @patch('backend.booking.message_bus.redis_client')
    def test_message_deduplication(self, mock_redis):
        """Test message deduplication with Redis."""
        message_uuid = "test-uuid-123"

        # First call - not duplicate
        mock_redis.exists.return_value = 0
        is_duplicate = self.bus.is_duplicate(message_uuid)
        assert is_duplicate is False

        # Second call - is duplicate
        mock_redis.exists.return_value = 1
        is_duplicate = self.bus.is_duplicate(message_uuid)
        assert is_duplicate is True

    @patch('backend.booking.message_bus.redis_client')
    def test_atomic_message_claiming(self, mock_redis):
        """Test atomic message claiming with SETNX."""
        message_uuid = "test-uuid-456"

        # First claim succeeds
        mock_redis.setnx.return_value = 1
        claimed = self.bus.claim_message(message_uuid)
        assert claimed is True

        # Second claim fails
        mock_redis.setnx.return_value = 0
        claimed = self.bus.claim_message(message_uuid)
        assert claimed is False

    @patch('backend.booking.message_bus.redis_client')
    def test_message_processing_marking(self, mock_redis):
        """Test marking messages as processed."""
        message_uuid = "test-uuid-789"
        result = {"status": "processed", "agent_response": "Thank you"}

        mock_redis.setex.return_value = True
        success = self.bus.mark_processed(message_uuid, result)
        assert success is True

        # Verify Redis was called with correct data
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"processed_messages:{message_uuid}"
        assert call_args[0][1] == 604800  # 7 days

        stored_data = json.loads(call_args[0][2])
        assert stored_data["result"]["status"] == "processed"

    def test_email_lead_id_extraction(self):
        """Test lead ID extraction from email addresses."""
        # Test various email formats
        test_cases = [
            ("leads+lead_123@domain.com", "lead_123"),
            ("inquiry+user_456@app.com", "user_456"),
            ("regular@email.com", None),  # No + separator
            ("leads+@domain.com", None),  # Empty lead ID
        ]

        for email, expected in test_cases:
            result = self.bus._extract_lead_id_from_email(email)
            assert result == expected

    def test_unknown_channel_error(self):
        """Test error handling for unknown channels."""
        with pytest.raises(ValueError, match="Unsupported channel"):
            self.bus.normalize_message("unknown", {})

    @patch('backend.booking.message_bus.redis_client')
    def test_redis_unavailable_graceful_degradation(self, mock_redis):
        """Test graceful degradation when Redis is unavailable."""
        # Simulate Redis failure
        mock_redis.exists.side_effect = Exception("Redis connection failed")

        # Should not raise exceptions, just return safe defaults
        is_duplicate = self.bus.is_duplicate("test-uuid")
        assert is_duplicate is False  # Safe default

        claimed = self.bus.claim_message("test-uuid")
        assert claimed is True  # Allow processing without deduplication

        marked = self.bus.mark_processed("test-uuid", {})
        assert marked is False  # Can't mark without Redis

    def test_normalized_message_structure(self):
        """Test NormalizedMessage dataclass structure."""
        msg = NormalizedMessage(
            message_uuid="uuid-123",
            lead_id="lead_456",
            content="Test message",
            channel=Channel.INSTAGRAM,
            timestamp=datetime.now(),
            metadata={"source": "test"}
        )

        assert msg.message_uuid == "uuid-123"
        assert msg.lead_id == "lead_456"
        assert msg.content == "Test message"
        assert msg.channel == Channel.INSTAGRAM
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata["source"] == "test"
