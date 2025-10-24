"""
Integration tests to verify all qualification flow and value delivery components work together.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json

from backend.agents.qualifier import QualifierAgent
from backend.agents.followup import FollowupAgent
from backend.agents.offramp import OfframpAgent
from backend.agents.value_delivery import ValueDeliveryAgent
from backend.agents.router import RouterAgent
from backend.tasks.production_lead_processing import ProductionLeadProcessor
from backend.utils.lead_scoring import LeadScoringSystem, calculate_lead_score
from backend.models.lead import Lead
from backend.schemas.state import AgentState, ConversationMessage
from backend.tools.agent_tools import fetch_lead_magnet, deliver_property_info, send_market_insights


class TestQualificationFlowIntegration:
    """Test integration between qualification flow components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_qualification_flow(self):
        """Test complete qualification flow from initial contact to routing."""
        # Initial state - new lead
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="qualifier",
            lead_data={}
        )
        
        with patch('backend.agents.qualifier.SupabaseClient') as mock_supabase, \
             patch('backend.agents.qualifier.LLMClient') as mock_llm:
            
            # Mock qualifier agent
            mock_qualifier = QualifierAgent()
            mock_qualifier.supabase = mock_supabase.return_value
            mock_qualifier.llm = mock_llm.return_value
            
            # Simulate progressive qualification
            responses = [
                "Hi, I'm looking to buy a home in Austin",
                "My budget is around $750,000",
                "I'm looking to move in about 3 months",
                "I'm interested in a single-family home with 3 bedrooms",
                "Yes, that all sounds correct"
            ]
            
            expected_questions = [
                "budget",
                "timeline", 
                "property_type",
                "confirmation"
            ]
            
            for i, response in enumerate(responses):
                with patch.object(mock_qualifier, '_determine_next_question') as mock_next_q, \
                     patch.object(mock_qualifier, '_update_lead_data') as mock_update, \
                     patch.object(mock_qualifier, '_calculate_lead_score') as mock_score, \
                     patch.object(mock_qualifier, '_update_lead_score') as mock_update_score:
                    
                    if i < len(expected_questions) - 1:
                        mock_next_q.return_value = f"What about your {expected_questions[i]}?"
                        mock_update.return_value = None
                        
                        result = await mock_qualifier.process_message(state, response)
                        
                        assert expected_questions[i] in result.response.lower()
                        assert result.next_agent == "qualifier"
                    else:
                        # Final response - should route based on score
                        mock_score.return_value = 0.85  # High score
                        mock_update_score.return_value = None
                        
                        result = await mock_qualifier.process_message(state, response)
                        
                        assert result.next_agent == "scheduler"
                        assert result.lead_data.get("status") == "qualified"
    
    @pytest.mark.asyncio
    async def test_nurture_flow_integration(self):
        """Test nurture flow integration with value delivery."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="followup",
            lead_data={
                "status": "nurturing",
                "qualified_score": 0.6,
                "previous_score": 0.4,
                "location": "Austin, TX",
                "property_type": "condo"
            }
        )
        
        with patch('backend.agents.followup.SupabaseClient') as mock_supabase, \
             patch('backend.agents.followup.LLMClient') as mock_llm:
            
            mock_followup = FollowupAgent()
            mock_followup.supabase = mock_supabase.return_value
            mock_followup.llm = mock_llm.return_value
            
            # Test value delivery during nurture
            with patch.object(mock_followup, '_analyze_nurture_response') as mock_analyze, \
                 patch.object(mock_followup, '_deliver_value_content') as mock_deliver, \
                 patch.object(mock_followup, '_create_nurture_sequence') as mock_nurture:
                
                mock_analyze.return_value = "value_delivery"
                mock_deliver.return_value = "Here's some market insights for Austin condos..."
                mock_nurture.return_value = None
                
                result = await mock_followup.process_message(state, "What's the condo market like in Austin?")
                
                assert "market" in result.response.lower()
                assert result.next_agent == "followup"
                mock_analyze.assert_called_once()
                mock_deliver.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_offramp_flow_integration(self):
        """Test off-ramp flow integration."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="offramp",
            lead_data={
                "status": "disqualified",
                "qualified_score": 0.3,
                "offramp_reason": "long_timeline"
            }
        )
        
        with patch('backend.agents.offramp.SupabaseClient') as mock_supabase, \
             patch('backend.agents.offramp.LLMClient') as mock_llm:
            
            mock_offramp = OfframpAgent()
            mock_offramp.supabase = mock_supabase.return_value
            mock_offramp.llm = mock_llm.return_value
            
            with patch.object(mock_offramp, '_determine_offramp_strategy') as mock_strategy, \
                 patch.object(mock_offramp, '_update_offramp_status') as mock_update:
                
                mock_strategy.return_value = "gentle_rejection"
                mock_update.return_value = None
                
                result = await mock_offramp.process_message(state, "OK")
                
                assert "thank you" in result.response.lower()
                assert "newsletter" in result.response.lower()
                assert result.next_agent == "offramp"
                mock_strategy.assert_called_once()
                mock_update.assert_called_once()


class TestValueDeliveryIntegration:
    """Test integration between value delivery components."""
    
    @pytest.mark.asyncio
    async def test_value_delivery_routing_integration(self):
        """Test value delivery routing through the system."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="value_delivery",
            lead_data={
                "location": "Austin, TX",
                "property_type": "single_family",
                "budget": 750000
            }
        )
        
        with patch('backend.agents.value_delivery.SupabaseClient') as mock_supabase, \
             patch('backend.agents.value_delivery.LLMClient') as mock_llm:
            
            mock_value_delivery = ValueDeliveryAgent()
            mock_value_delivery.supabase = mock_supabase.return_value
            mock_value_delivery.llm = mock_llm.return_value
            
            # Test property info request
            with patch.object(mock_value_delivery, '_analyze_value_request') as mock_analyze, \
                 patch.object(mock_value_delivery, '_deliver_property_info') as mock_deliver, \
                 patch.object(mock_value_delivery, '_update_value_delivery_tracking') as mock_update:
                
                mock_analyze.return_value = "property_info"
                mock_deliver.return_value = "Here are 3 properties in Austin that match your criteria..."
                mock_update.return_value = None
                
                result = await mock_value_delivery.process_message(state, "Can you show me properties in Austin?")
                
                assert "property" in result.response.lower()
                assert result.lead_data.get("property_info_delivered") is True
                mock_analyze.assert_called_once()
                mock_deliver.assert_called_once()
                mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lead_scoring_integration(self):
        """Test lead scoring integration across the system."""
        # Test scoring calculation
        lead_data = {
            "budget": 800000,
            "timeline": "3 months",
            "location": "Austin, TX",
            "property_type": "single_family",
            "bedrooms": 3,
            "bathrooms": 2,
            "contact_info": {"email": "test@example.com"}
        }
        
        score = calculate_lead_score(lead_data)
        assert score >= 0.75
        
        # Test routing based on score
        if score >= 0.75:
            next_agent = "scheduler"
            status = "qualified"
        elif score >= 0.4:
            next_agent = "followup"
            status = "nurturing"
        else:
            next_agent = "offramp"
            status = "disqualified"
        
        assert next_agent == "scheduler"
        assert status == "qualified"
        
        # Test score delta calculation
        previous_score = 0.5
        current_score = score
        delta = current_score - previous_score
        
        assert delta > 0
        assert delta == 0.35  # 0.85 - 0.5 = 0.35


class TestRouterIntegration:
    """Test router integration with all agents."""
    
    @pytest.mark.asyncio
    async def test_router_value_delivery_intents(self):
        """Test router handling of value delivery intents."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="router",
            lead_data={
                "location": "Austin, TX",
                "property_type": "condo"
            }
        )
        
        with patch('backend.agents.router.SupabaseClient') as mock_supabase, \
             patch('backend.agents.router.LLMClient') as mock_llm:
            
            mock_router = RouterAgent()
            mock_router.supabase = mock_supabase.return_value
            mock_router.llm = mock_llm.return_value
            
            # Test property info intent
            with patch.object(mock_router, '_classify_intent') as mock_classify:
                mock_classify.return_value = "request_property_info"
                
                result = await mock_router.process_message(state, "Can you show me properties in Austin?")
                
                assert result.next_agent == "value_delivery"
                mock_classify.assert_called_once()
            
            # Test market question intent
            mock_classify.return_value = "ask_market_question"
            
            result = await mock_router.process_message(state, "How's the market in Austin?")
            
            assert result.next_agent == "value_delivery"
            
            # Test lead magnet acceptance
            mock_classify.return_value = "accept_lead_magnet"
            
            result = await mock_router.process_message(state, "Yes, I'd like the home buyer's guide")
            
            assert result.next_agent == "value_delivery"
    
    @pytest.mark.asyncio
    async def test_router_qualification_stage_routing(self):
        """Test router routing based on qualification stage."""
        # Test qualified lead routing
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="router",
            lead_data={
                "status": "qualified",
                "qualified_score": 0.8
            }
        )
        
        with patch('backend.agents.router.SupabaseClient') as mock_supabase, \
             patch('backend.agents.router.LLMClient') as mock_llm:
            
            mock_router = RouterAgent()
            mock_router.supabase = mock_supabase.return_value
            mock_router.llm = mock_llm.return_value
            
            with patch.object(mock_router, '_classify_intent') as mock_classify:
                mock_classify.return_value = "general_question"
                
                result = await mock_router.process_message(state, "What's next?")
                
                assert result.next_agent == "scheduler"
        
        # Test nurturing lead routing
        state.lead_data = {
            "status": "nurturing",
            "qualified_score": 0.6
        }
        
        with patch.object(mock_router, '_classify_intent') as mock_classify:
            mock_classify.return_value = "general_question"
            
            result = await mock_router.process_message(state, "Thanks for the info")
            
            assert result.next_agent == "followup"
        
        # Test disqualified lead routing
        state.lead_data = {
            "status": "disqualified",
            "qualified_score": 0.3
        }
        
        with patch.object(mock_router, '_classify_intent') as mock_classify:
            mock_classify.return_value = "general_question"
            
            result = await mock_router.process_message(state, "OK")
            
            assert result.next_agent == "offramp"


class TestProductionLeadProcessorIntegration:
    """Test production lead processor integration."""
    
    @pytest.mark.asyncio
    async def test_production_processor_qualification_flow(self):
        """Test production processor with qualification flow."""
        processor = ProductionLeadProcessor()
        
        with patch('backend.tasks.production_lead_processing.SupabaseClient') as mock_supabase, \
             patch('backend.tasks.production_lead_processing.LLMClient') as mock_llm, \
             patch('backend.tasks.production_lead_processing.QualifierAgent') as mock_qualifier, \
             patch('backend.tasks.production_lead_processing.LeadScoringSystem') as mock_scoring:
            
            # Mock dependencies
            mock_supabase_instance = mock_supabase.return_value
            mock_llm_instance = mock_llm.return_value
            mock_qualifier_instance = mock_qualifier.return_value
            mock_scoring_instance = mock_scoring.return_value
            
            # Mock lead data
            lead_data = {
                "id": "test_lead",
                "contact_info": {"email": "test@example.com"},
                "budget": 750000,
                "timeline": "3 months",
                "location": "Austin, TX",
                "property_type": "single_family"
            }
            
            mock_supabase_instance.get_lead.return_value = lead_data
            mock_scoring_instance.calculate_lead_score.return_value = 0.85
            mock_qualifier_instance.process_message.return_value = Mock(
                response="Great! You're qualified for scheduling.",
                next_agent="scheduler",
                lead_data={"status": "qualified", "qualified_score": 0.85}
            )
            
            # Process the lead
            result = await processor.process_lead("test_lead", "I'm ready to buy a home in Austin")
            
            assert result is not None
            mock_qualifier_instance.process_message.assert_called_once()
            mock_scoring_instance.calculate_lead_score.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_production_processor_value_delivery(self):
        """Test production processor with value delivery."""
        processor = ProductionLeadProcessor()
        
        with patch('backend.tasks.production_lead_processing.SupabaseClient') as mock_supabase, \
             patch('backend.tasks.production_lead_processing.LLMClient') as mock_llm, \
             patch('backend.tasks.production_lead_processing.ValueDeliveryAgent') as mock_value_delivery:
            
            # Mock dependencies
            mock_supabase_instance = mock_supabase.return_value
            mock_llm_instance = mock_llm.return_value
            mock_value_delivery_instance = mock_value_delivery.return_value
            
            # Mock lead data
            lead_data = {
                "id": "test_lead",
                "status": "nurturing",
                "location": "Austin, TX",
                "property_type": "condo"
            }
            
            mock_supabase_instance.get_lead.return_value = lead_data
            mock_value_delivery_instance.process_message.return_value = Mock(
                response="Here are some market insights for Austin condos...",
                next_agent="followup",
                lead_data={"market_insights_sent": True}
            )
            
            # Process the lead
            result = await processor.process_lead("test_lead", "What's the condo market like in Austin?")
            
            assert result is not None
            mock_value_delivery_instance.process_message.assert_called_once()


class TestDatabaseIntegration:
    """Test database integration across all components."""
    
    @pytest.mark.asyncio
    async def test_lead_data_persistence(self):
        """Test that lead data is properly persisted across the flow."""
        with patch('backend.utils.supabase_client.SupabaseClient') as mock_supabase:
            mock_instance = mock_supabase.return_value
            
            # Test lead creation
            lead_data = {
                "contact_info": {"email": "test@example.com"},
                "budget": 750000,
                "timeline": "3 months",
                "location": "Austin, TX",
                "property_type": "single_family"
            }
            
            mock_instance.create_lead.return_value = {"id": "test_lead", **lead_data}
            
            result = await mock_instance.create_lead(lead_data)
            assert result["id"] == "test_lead"
            assert result["budget"] == 750000
            
            # Test lead update with scoring
            update_data = {
                "qualified_score": 0.85,
                "previous_score": 0.6,
                "score_delta": 0.25,
                "status": "qualified",
                "qualification_stage": "complete"
            }
            
            mock_instance.update_lead.return_value = {"id": "test_lead", **update_data}
            
            result = await mock_instance.update_lead("test_lead", update_data)
            assert result["qualified_score"] == 0.85
            assert result["status"] == "qualified"
            
            # Test value delivery tracking
            value_update = {
                "property_info_delivered": True,
                "market_insights_sent": True,
                "lead_magnet_sent_at": datetime.now()
            }
            
            mock_instance.update_lead.return_value = {"id": "test_lead", **value_update}
            
            result = await mock_instance.update_lead("test_lead", value_update)
            assert result["property_info_delivered"] is True
            assert result["market_insights_sent"] is True
            assert result["lead_magnet_sent_at"] is not None
    
    @pytest.mark.asyncio
    async def test_conversation_history_storage(self):
        """Test that conversation history is properly stored."""
        with patch('backend.utils.supabase_client.SupabaseClient') as mock_supabase:
            mock_instance = mock_supabase.return_value
            
            # Test conversation message storage
            conversation_data = {
                "lead_id": "test_lead",
                "role": "user",
                "content": "I'm looking for a home in Austin",
                "timestamp": datetime.now(),
                "agent": "qualifier"
            }
            
            mock_instance.create_conversation_message.return_value = {"id": "msg_001", **conversation_data}
            
            result = await mock_instance.create_conversation_message(conversation_data)
            assert result["lead_id"] == "test_lead"
            assert result["role"] == "user"
            assert result["agent"] == "qualifier"
            
            # Test conversation history retrieval
            mock_instance.get_conversation_history.return_value = [
                {"id": "msg_001", "role": "user", "content": "I'm looking for a home in Austin"},
                {"id": "msg_002", "role": "assistant", "content": "What's your budget range?"}
            ]
            
            result = await mock_instance.get_conversation_history("test_lead")
            assert len(result) == 2
            assert result[0]["role"] == "user"
            assert result[1]["role"] == "assistant"


class TestGraphitiIntegration:
    """Test Graphiti integration for conversation transcript storage."""
    
    @pytest.mark.asyncio
    async def test_conversation_transcript_storage(self):
        """Test that conversation transcripts are stored in Graphiti."""
        with patch('backend.temporal.graph_client.GraphitiClient') as mock_graphiti:
            mock_instance = mock_graphiti.return_value
            
            # Test transcript storage
            transcript_data = {
                "lead_id": "test_lead",
                "conversation": [
                    {"role": "user", "content": "I'm looking for a home in Austin", "timestamp": datetime.now()},
                    {"role": "assistant", "content": "What's your budget range?", "timestamp": datetime.now()},
                    {"role": "user", "content": "Around $750,000", "timestamp": datetime.now()}
                ],
                "metadata": {
                    "agent": "qualifier",
                    "qualification_stage": "budget_inquiry",
                    "lead_score": 0.6
                }
            }
            
            mock_instance.store_conversation_transcript.return_value = {"id": "transcript_001", **transcript_data}
            
            result = await mock_instance.store_conversation_transcript(transcript_data)
            assert result["lead_id"] == "test_lead"
            assert len(result["conversation"]) == 3
            assert result["metadata"]["agent"] == "qualifier"
            
            # Test transcript retrieval
            mock_instance.get_conversation_transcript.return_value = transcript_data
            
            result = await mock_instance.get_conversation_transcript("test_lead")
            assert result["lead_id"] == "test_lead"
            assert len(result["conversation"]) == 3


class TestRedisIntegration:
    """Test Redis integration for conversation state management."""
    
    @pytest.mark.asyncio
    async def test_conversation_state_management(self):
        """Test that conversation state is managed in Redis."""
        with patch('backend.utils.redis_client.RedisClient') as mock_redis:
            mock_instance = mock_redis.return_value
            
            # Test state storage
            state_data = {
                "lead_id": "test_lead",
                "current_agent": "qualifier",
                "qualification_stage": "budget_inquiry",
                "lead_data": {"budget": None, "timeline": None, "location": "Austin, TX"}
            }
            
            mock_instance.set_conversation_state.return_value = True
            
            result = await mock_instance.set_conversation_state("test_lead", state_data)
            assert result is True
            
            # Test state retrieval
            mock_instance.get_conversation_state.return_value = state_data
            
            result = await mock_instance.get_conversation_state("test_lead")
            assert result["lead_id"] == "test_lead"
            assert result["current_agent"] == "qualifier"
            assert result["qualification_stage"] == "budget_inquiry"
            
            # Test state expiration
            mock_instance.set_conversation_state_with_expiry.return_value = True
            
            result = await mock_instance.set_conversation_state_with_expiry("test_lead", state_data, 3600)
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__])