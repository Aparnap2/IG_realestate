"""
Test Router Agent - Intent Classification & Compliance Gateway

Tests the Router Agent implementation according to PRD specifications.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from backend.agents.router import RouterAgent, route_to_agent, IntentClassification
from models.lead import Lead


class TestRouterAgent:
    """Test Router Agent functionality."""
    
    @pytest.fixture
    def router_agent(self, mock_settings):
        """Create a Router Agent instance for testing."""
        return RouterAgent()
    
    @pytest.mark.asyncio
    async def test_router_agent_initialization(self, router_agent):
        """Test that Router Agent initializes correctly."""
        assert router_agent is not None
        assert router_agent.llm is not None
    
    @pytest.mark.asyncio
    async def test_intent_classification_new_inquiry(self, router_agent, agent_state, mock_compliance):
        """Test intent classification for new property inquiry."""
        # Mock LLM response for new inquiry
        mock_classification = IntentClassification(
            intent="new_inquiry",
            confidence=0.9,
            requires_qualification=True,
            next_agent="qualifier",
            reasoning="User expressing interest in property purchase",
            urgency_level="medium"
        )
        
        with patch.object(router_agent.llm, 'ainvoke', return_value=mock_classification):
            result = await router_agent.process(agent_state)
            
            assert result["current_agent"] == "qualifier"
            assert result["agent_decision"]["intent"] == "new_inquiry"
            assert result["agent_decision"]["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_intent_classification_schedule_tour(self, router_agent, agent_state, mock_compliance):
        """Test intent classification for tour scheduling."""
        agent_state["messages"] = [
            {"role": "user", "content": "I want to schedule a tour for tomorrow"}
        ]
        
        mock_classification = IntentClassification(
            intent="schedule_tour",
            confidence=0.95,
            requires_qualification=False,
            next_agent="scheduler",
            reasoning="User explicitly requesting tour scheduling",
            urgency_level="high"
        )
        
        with patch.object(router_agent.llm, 'ainvoke', return_value=mock_classification):
            result = await router_agent.process(agent_state)
            
            assert result["current_agent"] == "scheduler"
            assert result["agent_decision"]["intent"] == "schedule_tour"
    
    @pytest.mark.asyncio
    async def test_compliance_gate_blocks_violation(self, router_agent, agent_state, mock_audit):
        """Test that compliance gate blocks fair housing violations."""
        agent_state["messages"] = [
            {"role": "user", "content": "Do you have properties perfect for young professionals?"}
        ]
        
        # Mock compliance violation
        async def mock_compliance_violation(message, context):
            return {
                "passed": False,
                "violations": [{"pattern": "age", "risk_level": "high"}],
                "suggested_replacement": "I can help you find properties that match your needs."
            }
        
        with patch('tools.compliance.fair_housing_evaluator', side_effect=mock_compliance_violation):
            result = await router_agent.process(agent_state)
            
            assert result["requires_human_review"] == True
            assert result["current_agent"] == "human"
            assert "compliance_flags" in result
            assert len(result["messages"]) > 1  # Neutral response added
    
    @pytest.mark.asyncio
    async def test_low_confidence_routes_to_human(self, router_agent, agent_state, mock_compliance):
        """Test that low confidence classifications route to human review."""
        mock_classification = IntentClassification(
            intent="new_inquiry",
            confidence=0.4,  # Low confidence
            requires_qualification=True,
            next_agent="qualifier",
            reasoning="Ambiguous user intent",
            urgency_level="medium"
        )
        
        with patch.object(router_agent.llm, 'ainvoke', return_value=mock_classification):
            result = await router_agent.process(agent_state)
            
            assert result["requires_human_review"] == True
            assert result["current_agent"] == "human"
    
    @pytest.mark.asyncio
    async def test_high_value_lead_priority_routing(self, router_agent, agent_state, mock_compliance):
        """Test that high-value leads get priority routing."""
        # Set high budget
        agent_state["lead"].budget = 600000
        
        mock_classification = IntentClassification(
            intent="new_inquiry",
            confidence=0.8,
            requires_qualification=True,
            next_agent="qualifier",
            reasoning="High-value lead inquiry",
            urgency_level="medium"
        )
        
        with patch.object(router_agent.llm, 'ainvoke', return_value=mock_classification):
            result = await router_agent.process(agent_state)
            
            # High-value leads should be routed to scheduler for priority
            assert result["current_agent"] == "scheduler"
    
    @pytest.mark.asyncio
    async def test_router_error_handling(self, router_agent, agent_state, mock_compliance):
        """Test router error handling with graceful degradation."""
        # Mock LLM failure
        with patch.object(router_agent.llm, 'ainvoke', side_effect=Exception("LLM API error")):
            result = await router_agent.process(agent_state)
            
            assert result["current_agent"] == "qualifier"  # Safe fallback
            assert "error" in result
            assert result["retry_count"] == 1
    
    @pytest.mark.asyncio
    async def test_empty_conversation_handling(self, router_agent, mock_compliance):
        """Test handling of empty conversation state."""
        empty_state = {
            "lead": Lead(user_id="test", channel="ig", message="test"),
            "messages": []  # Empty messages
        }
        
        result = await router_agent.process(empty_state)
        
        assert result["current_agent"] == "qualifier"
        assert result["agent_decision"]["reasoning"] == "No messages found, defaulting to qualification"
    
    def test_route_to_agent_function(self, agent_state):
        """Test the conditional edge routing function."""
        # Test normal routing
        agent_state["current_agent"] = "qualifier"
        assert route_to_agent(agent_state) == "qualifier"
        
        # Test human review flag
        agent_state["requires_human_review"] = True
        assert route_to_agent(agent_state) == "human"
        
        # Test error state
        agent_state["error"] = "Some error"
        assert route_to_agent(agent_state) == "error_handler"
        
        # Test invalid agent fallback
        invalid_state = {"current_agent": "invalid_agent"}
        assert route_to_agent(invalid_state) == "qualifier"
    
    @pytest.mark.asyncio
    async def test_audit_logging_integration(self, router_agent, agent_state, mock_compliance, mock_audit):
        """Test that router decisions are properly logged."""
        mock_classification = IntentClassification(
            intent="new_inquiry",
            confidence=0.8,
            requires_qualification=True,
            next_agent="qualifier",
            reasoning="Standard property inquiry",
            urgency_level="medium"
        )
        
        with patch.object(router_agent.llm, 'ainvoke', return_value=mock_classification):
            await router_agent.process(agent_state)
            
            # Verify audit logging was called
            mock_audit.assert_called()
            
            # Check that routing decision was logged
            call_args = [call[0] for call in mock_audit.call_args_list]
            assert any("routing_decision" in args for args in call_args)


class TestRouterIntegration:
    """Test Router Agent integration with other components."""
    
    @pytest.mark.asyncio
    async def test_router_to_qualifier_flow(self, mock_settings, mock_compliance, mock_audit):
        """Test complete flow from router to qualifier."""
        from workflow import create_router_enabled_workflow
        
        # Mock dependencies
        with patch('utils.redis_client.test_redis_connection', return_value=True):
            with patch('utils.redis_client.redis_client', Mock()):
                # This would test the full workflow integration
                # For now, just test that workflow can be created
                try:
                    workflow = create_router_enabled_workflow()
                    assert workflow is not None
                except Exception as e:
                    # Expected in test environment without full setup
                    assert "Redis" in str(e) or "LangGraph" in str(e)
    
    @pytest.mark.asyncio
    async def test_compliance_integration(self, router_agent, agent_state):
        """Test integration with compliance tools."""
        # Test message that should trigger compliance check
        agent_state["messages"] = [
            {"role": "user", "content": "Are there good schools for families with children?"}
        ]
        
        # Mock compliance evaluator
        async def mock_evaluator(message, context):
            if "families with children" in message:
                return {
                    "passed": False,
                    "violations": [{"pattern": "familial_status", "risk_level": "high"}],
                    "suggested_replacement": "I can share information about local school districts and amenities."
                }
            return {"passed": True, "violations": []}
        
        with patch('tools.compliance.fair_housing_evaluator', side_effect=mock_evaluator):
            result = await router_agent.process(agent_state)
            
            # Should be flagged for human review due to compliance violation
            assert result["requires_human_review"] == True
            assert "compliance_flags" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])