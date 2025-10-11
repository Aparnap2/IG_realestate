#!/usr/bin/env python3
"""
Comprehensive tests for Instagram Webhook Server API integration.

Tests the corrected Messenger API for Instagram implementation including:
- Webhook verification
- Message processing
- Send API integration
- Error handling
"""

import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram_webhook_server import app, send_instagram_message, process_lead_message


class TestInstagramWebhookServer:
    """Test suite for Instagram Webhook Server"""

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)

    @pytest.fixture
    def valid_instagram_webhook(self):
        """Valid Instagram webhook payload"""
        return {
            "object": "instagram",
            "entry": [
                {
                    "id": "entry_123",
                    "time": 1640995200,
                    "messaging": [
                        {
                            "sender": {"id": "user_123"},
                            "recipient": {"id": "page_456"},
                            "timestamp": 1640995200000,
                            "message": {
                                "mid": "msg_789",
                                "text": "Looking for 2BHK in Miami, budget $350k"
                            }
                        }
                    ]
                }
            ]
        }

    @pytest.fixture
    def valid_verification_request(self):
        """Valid webhook verification request"""
        return {
            "hub.mode": "subscribe",
            "hub.verify_token": "aaa_real_estate_verify_token_2025",
            "hub.challenge": "test_challenge_123"
        }

    def test_webhook_verification_success(self, client, valid_verification_request):
        """Test successful webhook verification"""
        # Patch the VERIFY_TOKEN constant since it's loaded at import time
        with patch('instagram_webhook_server.VERIFY_TOKEN', 'aaa_real_estate_verify_token_2025'):
            response = client.get("/webhook", params=valid_verification_request)

            assert response.status_code == 200
            assert response.text == "test_challenge_123"
            assert response.headers["content-type"] == "text/plain"

    def test_webhook_verification_invalid_token(self, client):
        """Test webhook verification with invalid token"""
        invalid_request = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge_123"
        }

        response = client.get("/webhook", params=invalid_request)

        assert response.status_code == 403

    def test_webhook_verification_invalid_mode(self, client):
        """Test webhook verification with invalid mode"""
        invalid_request = {
            "hub.mode": "invalid_mode",
            "hub.verify_token": "aaa_real_estate_verify_token_2025",
            "hub.challenge": "test_challenge_123"
        }

        response = client.get("/webhook", params=invalid_request)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_instagram_message_processing(self, client, valid_instagram_webhook):
        """Test Instagram message processing with mocked lead processing"""

        # Mock the lead processing function
        with patch('instagram_webhook_server.process_lead_message') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "lead_id": "lead_123",
                "qualified_score": 0.8,
                "next_agent": "scheduler",
                "response_message": "Great! I found properties matching your criteria.",
                "properties_found": 2,
                "interrupt_needed": False
            }

            # Mock the send message function
            with patch('instagram_webhook_server.send_instagram_message') as mock_send:
                mock_send.return_value = True

                response = client.post("/webhook", json=valid_instagram_webhook)

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["processed_leads"] == 1
                assert data["object"] == "instagram"
                assert len(data["leads"]) == 1

                # Verify mocks were called
                mock_process.assert_called_once()
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_instagram_message_processing_error_handling(self, client, valid_instagram_webhook):
        """Test error handling in Instagram message processing"""

        # Mock lead processing to raise an error
        with patch('instagram_webhook_server.process_lead_message') as mock_process:
            mock_process.side_effect = Exception("Database connection failed")

            response = client.post("/webhook", json=valid_instagram_webhook)

            assert response.status_code == 200  # Should still return 200 to avoid retries
            data = response.json()
            assert data["status"] == "error"
            assert "Database connection failed" in data["error"]

    def test_non_instagram_event_ignored(self, client):
        """Test that non-Instagram events are ignored"""
        non_instagram_event = {
            "object": "page",
            "entry": [{"messaging": []}]
        }

        response = client.post("/webhook", json=non_instagram_event)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "not_instagram_event"

    def test_empty_messaging_array(self, client):
        """Test handling of empty messaging array"""
        empty_messaging = {
            "object": "instagram",
            "entry": [{"messaging": []}]
        }

        response = client.post("/webhook", json=empty_messaging)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processed_leads"] == 0

    def test_health_check_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "instagram_api" in data["components"]


class TestInstagramSendAPI:
    """Test Instagram Send API functionality"""

    @pytest.mark.asyncio
    async def test_send_instagram_message_success(self):
        """Test successful message sending"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"message_id": "msg_123"}
            mock_post.return_value.__aenter__.return_value = mock_response

            # Set environment variable for token
            with patch.dict(os.environ, {"META_PAGE_ACCESS_TOKEN": "test_token"}):
                result = await send_instagram_message("user_123", "Hello, world!")

                assert result is True
                mock_post.assert_called_once()

                # Verify the API call structure
                call_args = mock_post.call_args
                assert call_args[1]["params"]["access_token"] == "test_token"

                # Check request body includes messaging_type
                request_body = call_args[1]["json"]
                assert request_body["recipient"]["id"] == "user_123"
                assert request_body["message"]["text"] == "Hello, world!"
                assert request_body["messaging_type"] == "RESPONSE"

    @pytest.mark.asyncio
    async def test_send_instagram_message_no_token(self):
        """Test message sending without access token"""
        with patch.dict(os.environ, {}, clear=True):
            result = await send_instagram_message("user_123", "Hello, world!")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_instagram_message_api_error(self):
        """Test handling of API errors"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock API error response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text.return_value = "Invalid parameter"
            mock_response.json.return_value = {"error": {"code": 100}}
            mock_response.headers = {"content-type": "application/json"}
            mock_post.return_value.__aenter__.return_value = mock_response

            with patch.dict(os.environ, {"META_PAGE_ACCESS_TOKEN": "test_token"}):
                result = await send_instagram_message("user_123", "Hello, world!")

                assert result is False

    @pytest.mark.asyncio
    async def test_send_instagram_message_rate_limit_error(self):
        """Test handling of rate limit errors"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock rate limit error response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text.return_value = "Rate limit exceeded"
            mock_response.json.return_value = {"error": {"code": 613}}
            mock_response.headers = {"content-type": "application/json"}
            mock_post.return_value.__aenter__.return_value = mock_response

            with patch.dict(os.environ, {"META_PAGE_ACCESS_TOKEN": "test_token"}):
                result = await send_instagram_message("user_123", "Hello, world!")

                assert result is False


class TestLeadProcessingIntegration:
    """Test lead processing integration"""

    @pytest.mark.asyncio
    async def test_process_lead_message_integration(self):
        """Test the complete lead processing workflow"""
        # Mock all external dependencies
        with patch('instagram_webhook_server.supabase') as mock_supabase, \
             patch('instagram_webhook_server.redis_client') as mock_redis, \
             patch('instagram_webhook_server.get_llm_response') as mock_llm:

            # Mock Supabase responses
            mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []

            # Mock Redis
            mock_redis.setex.return_value = True

            # Mock LLM response for lead extraction
            mock_llm.return_value = {
                "budget": 350000,
                "location": "Miami",
                "property_type": "2BHK"
            }

            # Test lead processing
            result = await process_lead_message("user_123", "Looking for 2BHK in Miami, budget $350k", "ig")

            assert result["status"] == "success"
            assert "lead_id" in result
            assert "qualified_score" in result
            assert "next_agent" in result
            assert "response_message" in result

    def test_test_endpoint_functionality(self, client):
        """Test the test endpoint for development"""
        test_data = {
            "user_id": "test_user_123",
            "message": "Looking for 3BHK in Orlando, budget $500k"
        }

        response = client.post("/test", json=test_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "test_result" in data


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
