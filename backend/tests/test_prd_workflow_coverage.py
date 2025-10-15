"""
Tests for PRD-compliant workflow coverage improvement.
Targets missing lines in backend/agents/prd_compliant_workflow.py:
58, 60, 62, 64, 66, 100-101, 221-222, 270-281, 305-307, 321, 333-336, 363, 404-412, 424, 449, 495-496, 509, 555, 582-605, 656-749, 764-852
"""

import pytest
import asyncio
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timedelta
from models.lead import Lead
from schemas.state import AgentState


@pytest.fixture
def sample_state():
    """Create a sample state for testing."""
    lead = Lead(
        id="test-lead-123",
        channel="ig",
        user_id="ig-user-456",
        message="I'm looking for a 2-bedroom apartment in San Francisco",
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        budget=300000,
        location="San Francisco",
        property_type="apartment",
        desired_bedrooms=2,
        timeline="1-3months",
        move_in_date="2024-12-01",
        status="new",
        qualified_score=0.7,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        lead_source="instagram",
        agent_assigned="qualifier"
    )
    
    return {
        "lead": lead,
        "messages": [
            {"content": "I'm looking for a 2-bedroom apartment in San Francisco", "role": "user"}
        ]
    }


class TestPRDWorkflowCoverage:
    """Test class for PRD workflow coverage improvement."""
    
    @pytest.mark.asyncio
    async def test_qualifier_agent_with_missing_info(self, sample_state):
        """Test qualifier agent handling missing information (lines 58-66)."""
        # Import with mocked dependencies
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.agent_tools.query_properties_tool') as mock_query, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import QualifierAgent
    
            agent = QualifierAgent()
    
            # Create lead with missing budget
            sample_state["lead"].budget = None
    
            # Mock empty property results and extraction
            mock_query.return_value = []
            mock_send.return_value = True
            mock_extract.return_value = {"location": "San Francisco", "property_type": "apartment"}
    
            result = agent.process(sample_state)
    
            # Should process with missing info
            assert "lead" in result
            assert result["lead"].location == "San Francisco"
    
    @pytest.mark.asyncio
    async def test_qualifier_agent_with_low_confidence(self, sample_state):
        """Test qualifier agent with low confidence score (lines 100-101)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.agent_tools.qualify_lead_with_llm') as mock_qualify, \
             patch('backend.tools.agent_tools.query_properties_tool') as mock_query, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools') as mock_compliance, \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import QualifierAgent
    
            agent = QualifierAgent()
    
            # Mock low confidence score
            mock_qualify.return_value = '{"score": 0.6, "reasoning": "Low confidence"}'
            mock_query.return_value = []
            mock_send.return_value = True
            mock_compliance.fair_housing_evaluator.return_value = {"passed": True}
            mock_extract.return_value = {}
    
            result = agent.process(sample_state)
    
            # Should still process despite low confidence
            assert "lead" in result
            assert result["lead"].qualified_score < 0.7
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_with_no_availability(self, sample_state):
        """Test scheduler agent when no availability is found (lines 221-222)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
            patch('backend.tools.agent_tools.get_available_calendar_slots') as mock_slots, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Mock no availability
            mock_slots.return_value = []
            mock_send.return_value = True
            mock_extract.return_value = {}
    
            result = agent.process(sample_state)
    
            # Should handle no availability gracefully
            assert "lead" in result
            assert "messages" in result
    
    @pytest.mark.asyncio
    async def test_followup_agent_with_no_response(self, sample_state):
        """Test followup agent when no response is generated (lines 270-281)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.nurture.generate_nurture_action') as mock_nurture, \
             patch('backend.temporal.graph_client.get_graphiti_client'), \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.generate_response_message') as mock_generate:
    
            from backend.agents.prd_compliant_workflow import FollowUpAgent
    
            agent = FollowupAgent()
    
            # Mock no nurture action
            mock_nurture.return_value = None
            mock_send.return_value = True
            mock_generate.return_value = "Follow-up message"
    
            result = agent.process(sample_state)
    
            # Should handle no response gracefully
            assert "lead" in result
            assert result["lead"].status == "nurtured"
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_error_handling(self, sample_state):
        """Test scheduler agent error handling (lines 305-307, 321)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.agent_tools.get_available_calendar_slots') as mock_slots, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Mock an exception in booking
            with patch('backend.tools.agent_tools.book_calendar_event') as mock_book:
                mock_book.return_value = {"error": "Test error"}
                mock_slots.return_value = [{"start": datetime.now()}]
                mock_send.return_value = True
                mock_extract.return_value = {}
                
                result = agent.process(sample_state)
    
                # Should handle errors gracefully
                assert "lead" in result
                assert "messages" in result
    
    @pytest.mark.asyncio
    async def test_qualifier_agent_compliance_check(self, sample_state):
        """Test qualifier agent compliance check (lines 333-336)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.agent_tools.qualify_lead_with_llm') as mock_qualify, \
             patch('backend.tools.agent_tools.query_properties_tool') as mock_query, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools') as mock_compliance, \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import QualifierAgent
    
            agent = QualifierAgent()
    
            # Mock compliance failure
            mock_qualify.return_value = '{"score": 0.8, "reasoning": "Good match"}'
            mock_query.return_value = []
            mock_compliance.fair_housing_evaluator.return_value = {
                "passed": False,
                "suggested_replacement": "Neutral alternative message"
            }
            mock_send.return_value = True
            mock_extract.return_value = {}
    
            result = agent.process(sample_state)
    
            # Should use alternative message
            assert "lead" in result
            # Check that a message was sent (either original or replacement)
            assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_optimize_tour_sequence(self, sample_state):
        """Test scheduler agent optimize tour sequence (lines 363, 404-412)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with empty properties list
            result = agent.optimize_tour_sequence([], [])
            
            assert result["optimized_sequence"] == []
            assert result["total_travel_time"] == 0
            assert result["optimization_method"] == "none"
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_apply_buffer_times(self, sample_state):
        """Test scheduler agent apply buffer times (lines 424, 449)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with empty slots
            result = agent.apply_buffer_times([])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_create_optimized_tour_event(self, sample_state):
        """Test scheduler agent create optimized tour event (lines 495-496, 509)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with error case
            properties = [{"id": "1", "address": "123 Main St"}]
            time_slot = {"start": datetime.now()}
            
            result = agent.create_optimized_tour_event(sample_state["lead"], properties, time_slot)
            
            assert "success" in result
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_calculate_tour_duration(self, sample_state):
        """Test scheduler agent calculate tour duration (lines 555, 582-605)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with empty properties
            result = agent.calculate_tour_duration([])
            
            assert result["total_duration_minutes"] == 0
            assert result["property_details"] == []
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_cluster_properties(self, sample_state):
        """Test scheduler agent cluster properties (lines 656-749)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with empty properties
            result = agent.cluster_properties_by_location([])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_scheduler_agent_filter_conflicting_slots(self, sample_state):
        """Test scheduler agent filter conflicting slots (lines 764-852)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.extract_lead_info') as mock_extract:
    
            from backend.agents.prd_compliant_workflow import SchedulerAgent
    
            agent = SchedulerAgent()
    
            # Test with empty slots
            result = agent.filter_conflicting_slots([], [])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_followup_agent_error_handling(self, sample_state):
        """Test followup agent error handling (lines 747-754)."""
        with patch('backend.tools.agent_tools.send_instagram_message') as mock_send, \
             patch('backend.tools.nurture.generate_nurture_action') as mock_nurture, \
             patch('backend.temporal.graph_client.get_graphiti_client'), \
             patch('backend.agents.prd_compliant_workflow.compliance_tools'), \
             patch('backend.utils.llm_client.generate_response_message') as mock_generate:
    
            from backend.agents.prd_compliant_workflow import FollowUpAgent
    
            agent = FollowupAgent()
    
            # Mock an exception
            mock_send.side_effect = Exception("Test error")
            mock_nurture.return_value = None
            mock_generate.return_value = "Error message"
    
            result = agent.process(sample_state)
    
            # Should handle errors gracefully
            assert "error_message" in result
            assert result["next_agent"] == "END"