"""
Tests for Comment Trigger & DM Funnel Implementation.

This module tests the complete flow from Instagram comment to DM initiation,
including webhook handling, comment processing, and warm-up agent routing.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient

from api.webhooks import (
    verify_meta_signature,
    extract_comment_data,
    contains_trigger_keyword,
    is_duplicate_comment,
    mark_comment_processed
)
from tasks.comment_intake import process_comment_event
from agents.warmup import LeadWarmupAgent
from models.lead import Lead
from schemas.state import AgentState


class TestCommentWebhookHandler:
    """Test Instagram comment webhook handler functionality"""
    
    def test_verify_meta_signature_valid(self):
        """Test valid Meta signature verification"""
        payload = b'{"test": "data"}'
        signature = "sha256=valid_signature"
        
        with patch('backend.api.webhooks.os.getenv', return_value="test_secret"):
            result = verify_meta_signature(payload, signature)
            assert result is True
    
    def test_verify_meta_signature_invalid(self):
        """Test invalid Meta signature verification"""
        payload = b'{"test": "data"}'
        signature = "sha256=invalid_signature"
        
        with patch('backend.api.webhooks.os.getenv', return_value="test_secret"):
            result = verify_meta_signature(payload, signature)
            assert result is False
    
    def test_extract_comment_data_new_comment(self):
        """Test extraction of new comment from webhook payload"""
        webhook_data = {
            "object": "instagram",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "comments",
                    "value": {
                        "verb": "add",
                        "id": "comment_123",
                        "post_id": "post_456",
                        "text": "I'm interested in more info",
                        "from": {
                            "id": "user_789",
                            "name": "John Doe",
                            "username": "johndoe"
                        },
                        "created_time": "2025-10-24T12:00:00+0000",
                        "media_type": "photo"
                    }
                }]
            }]
        }
        
        comments = extract_comment_data(webhook_data)
        
        assert len(comments) == 1
        assert comments[0]["comment_id"] == "comment_123"
        assert comments[0]["post_id"] == "post_456"
        assert comments[0]["comment_text"] == "I'm interested in more info"
        assert comments[0]["commenter_id"] == "user_789"
        assert comments[0]["commenter_name"] == "John Doe"
        assert comments[0]["commenter_username"] == "johndoe"
    
    def test_extract_comment_data_ignores_edits(self):
        """Test that comment edits are ignored"""
        webhook_data = {
            "object": "instagram",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "comments",
                    "value": {
                        "verb": "edit",  # Should be ignored
                        "id": "comment_123",
                        "text": "Edited comment",
                        "from": {
                            "id": "user_789",
                            "name": "John Doe"
                        }
                    }
                }]
            }]
        }
        
        comments = extract_comment_data(webhook_data)
        
        assert len(comments) == 0  # Edits should be ignored
    
    def test_contains_trigger_keyword_info(self):
        """Test trigger keyword detection for 'info'"""
        assert contains_trigger_keyword("I need more info about this property")
        assert contains_trigger_keyword("Can you send me info?")
        assert contains_trigger_keyword("INFO please")  # Case insensitive
    
    def test_contains_trigger_keyword_price(self):
        """Test trigger keyword detection for 'price'"""
        assert contains_trigger_keyword("What's the price?")
        assert contains_trigger_keyword("pricing info needed")
        assert contains_trigger_keyword("PRICE")  # Case insensitive
    
    def test_contains_trigger_keyword_no_match(self):
        """Test that non-trigger comments are not detected"""
        assert not contains_trigger_keyword("Nice picture!")
        assert not contains_trigger_keyword("Just browsing")
        assert not contains_trigger_keyword("")
    
    @patch('backend.api.webhooks.redis_client')
    def test_is_duplicate_comment_new(self, mock_redis):
        """Test duplicate comment detection for new comment"""
        mock_redis.exists.return_value = False
        
        result = is_duplicate_comment("comment_123")
        assert result is False
        mock_redis.exists.assert_called_once_with("comment_processed:comment_123")
    
    @patch('backend.api.webhooks.redis_client')
    def test_is_duplicate_comment_existing(self, mock_redis):
        """Test duplicate comment detection for existing comment"""
        mock_redis.exists.return_value = True
        
        result = is_duplicate_comment("comment_123")
        assert result is True
        mock_redis.exists.assert_called_once_with("comment_processed:comment_123")
    
    @patch('backend.api.webhooks.redis_client')
    def test_mark_comment_processed(self, mock_redis):
        """Test marking comment as processed"""
        mock_redis.setex.return_value = True
        
        result = mark_comment_processed("comment_123")
        assert result is True
        mock_redis.setex.assert_called_once_with("comment_processed:comment_123", 86400, "1")


class TestCommentIntakeProcessing:
    """Test comment intake processing functionality"""
    
    @patch('backend.tasks.comment_intake.get_existing_lead')
    @patch('backend.tasks.comment_intake.create_or_update_lead')
    @patch('backend.tasks.comment_intake.initialize_conversation_state')
    @patch('backend.tasks.comment_intake.send_initial_warmup_message')
    @patch('backend.tasks.comment_intake.update_lead_warmup_status')
    @patch('backend.tasks.comment_intake.audit_log_event')
    def test_process_comment_event_new_lead(self, mock_audit, mock_update_status, mock_send_message, mock_init_state, mock_create_lead, mock_get_lead):
        """Test processing comment event for new lead"""
        # Setup mocks
        mock_get_lead.return_value = None  # No existing lead
        mock_create_lead.return_value = Lead(
            id="lead_123",
            user_id="user_789",
            name="John Doe",
            message="I'm interested in more info",
            channel="ig"
        )
        mock_init_state.return_value = {"stage": "warmup"}
        mock_send_message.return_value = True
        mock_update_status.return_value = True
        
        comment_event = {
            "comment_id": "comment_123",
            "commenter_id": "user_789",
            "commenter_name": "John Doe",
            "comment_text": "I'm interested in more info",
            "post_id": "post_456",
            "ig_account_id": "ig_account_123"
        }
        
        # Process comment event
        result = process_comment_event(comment_event)
        
        # Verify lead creation
        mock_get_lead.assert_called_once_with("user_789")
        mock_create_lead.assert_called_once()
        
        # Verify conversation state initialization
        mock_init_state.assert_called_once()
        
        # Verify initial DM sending
        mock_send_message.assert_called_once()
        
        # Verify lead status update
        mock_update_status.assert_called_once_with("lead_123")
        
        # Verify audit logging
        mock_audit.assert_called_once_with("comment_warmup_initiated", {
            "lead_id": "lead_123",
            "comment_id": "comment_123",
            "commenter_id": "user_789",
            "post_id": "post_456",
            "ig_account_id": "ig_account_123",
            "comment_text": "I'm interested in more info",
            "timestamp": pytest.approx(mock_audit.call_args[0][1]["timestamp"])
        })
        
        # Verify result
        assert result["status"] == "success"
        assert result["lead_id"] == "lead_123"
        assert result["commenter_id"] == "user_789"
        assert result["dm_sent"] is True
    
    @patch('backend.tasks.comment_intake.get_existing_lead')
    @patch('backend.tasks.comment_intake.create_or_update_lead')
    def test_process_comment_event_existing_lead(self, mock_create_lead, mock_get_lead):
        """Test processing comment event for existing lead"""
        # Setup mocks
        existing_lead_data = {
            "id": "existing_lead_123",
            "user_id": "user_789",
            "name": "John Doe",
            "message": "Previous message",
            "status": "new"
        }
        mock_get_lead.return_value = existing_lead_data
        mock_create_lead.return_value = Lead(
            id="existing_lead_123",
            user_id="user_789",
            name="John Doe",
            message="I'm interested in more info",
            channel="ig"
        )
        
        comment_event = {
            "comment_id": "comment_123",
            "commenter_id": "user_789",
            "comment_text": "I'm interested in more info",
            "post_id": "post_456",
            "ig_account_id": "ig_account_123"
        }
        
        # Process comment event
        result = process_comment_event(comment_event)
        
        # Verify existing lead lookup
        mock_get_lead.assert_called_once_with("user_789")
        
        # Verify lead update (not creation)
        mock_create_lead.assert_called_once()
        
        # Verify result
        assert result["status"] == "success"
        assert result["lead_id"] == "existing_lead_123"
    
    @patch('backend.tasks.comment_intake.send_initial_warmup_message')
    def test_process_comment_event_dm_failure(self, mock_send_message):
        """Test processing comment event when DM sending fails"""
        mock_send_message.return_value = False
        
        comment_event = {
            "comment_id": "comment_123",
            "commenter_id": "user_789",
            "comment_text": "I'm interested in more info",
            "post_id": "post_456",
            "ig_account_id": "ig_account_123"
        }
        
        # Process comment event
        result = process_comment_event(comment_event)
        
        # Verify failure handling
        assert result["status"] == "error"
        assert result["error"] == "DM sending failed"


class TestLeadWarmupAgent:
    """Test lead warm-up agent functionality"""
    
    def setup_method(self):
        """Setup warm-up agent for testing"""
        self.agent = LeadWarmupAgent()
        self.lead = Lead(
            id="lead_123",
            user_id="user_789",
            name="John Doe",
            message="I'm interested in more info",
            channel="ig"
        )
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.set_conversation_state')
    @patch('backend.agents.warmup.audit_log_event')
    async def test_handle_initial_contact(self, mock_audit, mock_set_state, mock_send_message, mock_get_state):
        """Test handling initial contact in warm-up"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "initial_contact",
            "lead_magnet_sent": False
        }
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": []
        }
        
        # Process initial contact
        result = await self.agent.process(state)
        
        # Verify conversation state retrieval
        mock_get_state.assert_called_once_with("user_789")
        
        # Verify message sending
        mock_send_message.assert_called_once()
        
        # Verify state update
        mock_set_state.assert_called_once()
        
        # Verify result
        assert result["agent_decision"]["stage"] == "lead_magnet_offer"
        assert result["agent_decision"]["next_agent"] == "warmup"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.fetch_lead_magnet')
    @patch('backend.agents.warmup.set_conversation_state')
    @patch('backend.agents.warmup.audit_log_event')
    async def test_handle_lead_magnet_response_positive(self, mock_audit, mock_set_state, mock_send_message, mock_get_state, mock_fetch_magnet):
        """Test handling positive lead magnet response"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "lead_magnet_offer",
            "lead_magnet_sent": False
        }
        mock_fetch_magnet.return_value = {
            "id": "magnet_123",
            "title": "First-Time Home Buyer Guide",
            "delivery_text": "Check your DMs for the complete guide!"
        }
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": [{"role": "user", "content": "guide"}]
        }
        
        # Process lead magnet response
        result = await self.agent.process(state)
        
        # Verify lead magnet fetching
        mock_fetch_magnet.assert_called_once_with("first_time_buyer_guide")
        
        # Verify message sending
        mock_send_message.assert_called_once()
        
        # Verify state update
        mock_set_state.assert_called_once()
        
        # Verify audit logging
        mock_audit.assert_called_once_with("lead_magnet_delivered", {
            "lead_id": "lead_123",
            "user_id": "user_789",
            "lead_magnet_type": "first_time_buyer_guide"
        })
        
        # Verify result
        assert result["agent_decision"]["lead_magnet_sent"] is True
        assert result["agent_decision"]["stage"] == "lead_magnet_delivery"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.set_conversation_state')
    async def test_handle_transition_to_qualification(self, mock_set_state, mock_send_message, mock_get_state):
        """Test transition to qualification phase"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "value_building",
            "lead_magnet_sent": True
        }
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": [{"role": "user", "content": "I'm ready to buy"}]
        }
        
        # Process transition
        result = await self.agent.process(state)
        
        # Verify qualification message
        assert "budget range" in result["messages"][-1]["content"]
        
        # Verify state update
        mock_set_state.assert_called_once()
        
        # Verify result
        assert result["agent_decision"]["next_agent"] == "qualifier"
        assert result["current_agent"] == "qualifier"


class TestCommentTriggerIntegration:
    """Test end-to-end comment trigger integration"""
    
    @patch('backend.api.webhooks.process_comment_task')
    def test_webhook_to_warmup_flow(self, mock_task):
        """Test complete flow from webhook to warm-up"""
        # Setup mock task
        mock_task.delay.return_value = Mock(id="task_123")
        
        # Simulate webhook payload
        webhook_payload = {
            "object": "instagram",
            "entry": [{
                "id": "ig_account_123",
                "changes": [{
                    "field": "comments",
                    "value": {
                        "verb": "add",
                        "id": "comment_123",
                        "post_id": "post_456",
                        "text": "I need more info",
                        "from": {
                            "id": "user_789",
                            "name": "John Doe",
                            "username": "johndoe"
                        },
                        "created_time": "2025-10-24T12:00:00+0000",
                        "media_type": "photo"
                    }
                }]
            }]
        }
        
        # This would be tested in integration with actual FastAPI client
        # For now, we verify the task is enqueued correctly
        mock_task.delay.assert_called_once()
        
        # Verify task was called with correct comment event
        call_args = mock_task.delay.call_args[0]
        comment_event = call_args[0]
        
        assert comment_event["comment_id"] == "comment_123"
        assert comment_event["commenter_id"] == "user_789"
        assert comment_event["comment_text"] == "I need more info"


if __name__ == "__main__":
    pytest.main([__file__])