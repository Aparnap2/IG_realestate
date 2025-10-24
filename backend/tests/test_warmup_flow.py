"""
Tests for Warm-up Flow in Instagram DM Automation.

This module tests the complete warm-up sequence from comment trigger
to qualification transition, including lead magnet delivery and conversation state management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from agents.warmup import LeadWarmupAgent
from models.lead import Lead
from schemas.state import AgentState


class TestLeadWarmupFlow:
    """Test complete warm-up flow from comment trigger to qualification"""
    
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
    async def test_complete_warmup_sequence(self, mock_audit, mock_set_state, mock_send_message, mock_get_state):
        """Test complete warm-up sequence from initial contact to qualification"""
        # Setup conversation state progression
        mock_get_state.side_effect = [
            {"current_step": "initial_contact", "lead_magnet_sent": False},
            {"current_step": "lead_magnet_offer", "lead_magnet_sent": False},
            {"current_step": "lead_magnet_delivery", "lead_magnet_sent": True},
            {"current_step": "value_building", "lead_magnet_sent": True},
            {"current_step": "qualification_transition", "lead_magnet_sent": True}
        ]
        
        # Mock successful message sending
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": []
        }
        
        # Stage 1: Initial contact (already handled in comment_intake)
        state["messages"].append({"role": "user", "content": "guide"})
        result = await self.agent.process(state)
        
        assert result["agent_decision"]["stage"] == "lead_magnet_delivery"
        assert result["agent_decision"]["lead_magnet_sent"] is True
        
        # Stage 2: Post-delivery value building
        state["messages"].append({"role": "user", "content": "Thanks for the guide!"})
        result = await self.agent.process(state)
        
        assert result["agent_decision"]["stage"] == "value_building"
        
        # Stage 3: Transition to qualification
        state["messages"].append({"role": "user", "content": "I'm ready to buy"})
        result = await self.agent.process(state)
        
        assert result["agent_decision"]["next_agent"] == "qualifier"
        assert result["current_agent"] == "qualifier"
        
        # Verify audit logging
        assert mock_audit.call_count == 3  # Initial, delivery, transition
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.fetch_lead_magnet')
    async def test_lead_magnet_delivery_success(self, mock_get_state, mock_send_message, mock_fetch_magnet):
        """Test successful lead magnet delivery"""
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
        
        # Process lead magnet request
        result = await self.agent.process(state)
        
        # Verify lead magnet fetching
        mock_fetch_magnet.assert_called_once_with("first_time_buyer_guide")
        
        # Verify message sending
        mock_send_message.assert_called_once()
        sent_message = mock_send_message.call_args[0][1]
        assert "First-Time Home Buyer Guide" in sent_message
        assert "Check your DMs for the complete guide!" in sent_message
        
        # Verify state update
        mock_get_state.assert_called()
        
        # Verify result
        assert result["agent_decision"]["lead_magnet_sent"] is True
        assert result["agent_decision"]["stage"] == "lead_magnet_delivery"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.fetch_lead_magnet')
    async def test_lead_magnet_delivery_failure(self, mock_get_state, mock_send_message, mock_fetch_magnet):
        """Test lead magnet delivery failure handling"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "lead_magnet_offer",
            "lead_magnet_sent": False
        }
        mock_fetch_magnet.return_value = {}  # Failure
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": [{"role": "user", "content": "guide"}]
        }
        
        # Process lead magnet request
        result = await self.agent.process(state)
        
        # Verify lead magnet fetching
        mock_fetch_magnet.assert_called_once_with("first_time_buyer_guide")
        
        # Verify fallback message
        mock_send_message.assert_called_once()
        sent_message = mock_send_message.call_args[0][1]
        assert "budget range" in sent_message  # Fallback to qualification
        
        # Verify result
        assert result["agent_decision"]["next_agent"] == "qualifier"
        assert result["agent_decision"]["stage"] == "qualification_transition"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    async def test_objection_handling(self, mock_get_state, mock_send_message):
        """Test handling of lead magnet objections"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "lead_magnet_offer",
            "lead_magnet_sent": False
        }
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": [{"role": "user", "content": "I don't have time"}]
        }
        
        # Process objection
        result = await self.agent.process(state)
        
        # Verify objection handling
        mock_send_message.assert_called_once()
        sent_message = mock_send_message.call_args[0][1]
        assert "2 minutes" in sent_message
        assert "no pressure" in sent_message
        
        # Verify result
        assert result["agent_decision"]["stage"] == "lead_magnet_offer"
        assert result["agent_decision"]["action"] == "address_objection"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    async def test_value_building_engagement(self, mock_get_state, mock_send_message):
        """Test value building stage engagement"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "lead_magnet_delivery",
            "lead_magnet_sent": True
        }
        mock_send_message.return_value = True
        
        state = {
            "lead": self.lead,
            "messages": [{"role": "user", "content": "Thanks for the guide!"}]
        }
        
        # Process value building
        result = await self.agent.process(state)
        
        # Verify engagement message
        mock_send_message.assert_called_once()
        sent_message = mock_send_message.call_args[0][1]
        assert "timeline" in sent_message
        assert "properties" in sent_message
        
        # Verify result
        assert result["agent_decision"]["stage"] == "qualification_transition"
        assert result["agent_decision"]["action"] == "prepare_transition"
    
    @patch('backend.agents.warmup.get_conversation_state')
    @patch('backend.agents.warmup.send_instagram_message')
    @patch('backend.agents.warmup.audit_log_event')
    async def test_error_handling(self, mock_get_state, mock_audit):
        """Test warm-up agent error handling"""
        # Setup mocks
        mock_get_state.return_value = {
            "current_step": "lead_magnet_offer",
            "lead_magnet_sent": False
        }
        
        # Mock LLM error
        with patch.object(self.agent, 'llm') as mock_llm:
            mock_llm.ainvoke.side_effect = Exception("LLM error")
            
            state = {
                "lead": self.lead,
                "messages": [{"role": "user", "content": "guide"}]
            }
            
            # Process with error
            result = await self.agent.process(state)
            
            # Verify error handling
            assert result["error"] == "LLM error"
            assert result["current_agent"] == "qualifier"  # Fallback
            
            # Verify audit logging
            mock_audit.assert_called_once_with("warmup_agent_error", {
                "lead_id": "lead_123",
                "error": "LLM error"
            })
    
    def test_contains_lead_magnet_intent_positive(self):
        """Test positive lead magnet intent detection"""
        agent = LeadWarmupAgent()
        
        assert agent._contains_lead_magnet_intent("guide")
        assert agent._contains_lead_magnet_intent("yes please")
        assert agent._contains_lead_magnet_intent("send it")
        assert agent._contains_lead_magnet_intent("I want it")
        assert agent._contains_lead_magnet_intent("interested")
    
    def test_contains_lead_magnet_intent_negative(self):
        """Test negative lead magnet intent detection"""
        agent = LeadWarmupAgent()
        
        assert not agent._contains_lead_magnet_intent("no thanks")
        assert not agent._contains_lead_magnet_intent("not interested")
        assert not agent._contains_lead_magnet_intent("just browsing")
        assert not agent._contains_lead_magnet_intent("")
    
    def test_contains_transition_intent_positive(self):
        """Test positive transition intent detection"""
        agent = LeadWarmupAgent()
        
        assert agent._contains_transition_intent("ready to buy")
        assert agent._contains_transition_intent("let's qualify")
        assert agent._contains_transition_intent("I want properties")
        assert agent._contains_transition_intent("help me find")
    
    def test_contains_transition_intent_negative(self):
        """Test negative transition intent detection"""
        agent = LeadWarmupAgent()
        
        assert not agent._contains_transition_intent("just looking")
        assert not agent._contains_transition_intent("maybe later")
        assert not agent._contains_transition_intent("have questions")
    
    def test_contains_objection_positive(self):
        """Test objection detection"""
        agent = LeadWarmupAgent()
        
        assert agent._contains_objection("I don't have time")
        assert agent._contains_objection("too busy")
        assert agent._contains_objection("can't right now")
    
    def test_contains_objection_negative(self):
        """Test non-objection detection"""
        agent = LeadWarmupAgent()
        
        assert not agent._contains_objection("yes please")
        assert not agent._contains_objection("sounds good")
        assert not agent._contains_objection("ready when")


if __name__ == "__main__":
    pytest.main([__file__])