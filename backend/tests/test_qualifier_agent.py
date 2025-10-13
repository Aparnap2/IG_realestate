"""
Test Enhanced Qualifier Agent - Budget Reconciliation & Temporal Adjustments

Tests the enhanced qualifier agent with budget reconciliation and temporal scoring.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from backend.agents.prd_compliant_workflow import QualifierAgent
from tools.qualifier_utils import (
    reconcile_budget_mismatch,
    calculate_temporal_qualification_adjustments
)


class TestQualifierAgent:
    """Test Enhanced Qualifier Agent functionality."""
    
    @pytest.fixture
    def qualifier_agent(self, mock_settings):
        """Create a Qualifier Agent instance for testing."""
        return QualifierAgent()
    
    def test_qualifier_agent_initialization(self, qualifier_agent):
        """Test that Qualifier Agent initializes correctly."""
        assert qualifier_agent is not None
        assert len(qualifier_agent.tools) > 0
    
    def test_qualifier_process_basic_flow(self, qualifier_agent, agent_state, mock_supabase, mock_llm, mock_compliance, mock_audit):
        """Test basic qualification flow."""
        # Mock property query results
        mock_supabase.table.return_value.select.return_value.lte.return_value.eq.return_value.eq.return_value.execute.return_value = Mock(
            data=[
                {"id": "prop1", "price": 350000, "location": "Miami", "property_type": "3BHK"}
            ]
        )
        
        # Mock LLM qualification
        with patch('tools.agent_tools.get_llm_response_sync', return_value='{"score": 0.8, "reasoning": "Good match"}'):
            with patch('tools.agent_tools.send_instagram_message') as mock_send:
                mock_send.invoke.return_value = True
                
                result = qualifier_agent.process(agent_state)
                
                assert result["lead"].qualified_score is not None
                assert len(result["messages"]) > 1  # Response added
                assert result["next_agent"] in ["scheduler", "followup"]
    
    def test_qualifier_with_budget_reconciliation(self, qualifier_agent, agent_state, sample_properties, mock_compliance, mock_audit):
        """Test qualifier with budget reconciliation."""
        # Set up mismatch scenario: wants 3BR but budget for 2BR
        agent_state["lead"].desired_bedrooms = 3
        agent_state["lead"].budget = 300000  # Lower budget
        
        # Mock property query to return mixed results
        with patch('tools.agent_tools.query_properties_tool') as mock_query:
            mock_query.invoke.return_value = sample_properties
            
            with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                mock_qualify.invoke.return_value = {"score": 0.7, "reasoning": "Good potential"}
                
                with patch('tools.agent_tools.send_instagram_message') as mock_send:
                    mock_send.invoke.return_value = True
                    
                    result = qualifier_agent.process(agent_state)
                    
                    assert "reconciliation_result" in result
                    assert result["reconciliation_result"] is not None
    
    def test_qualifier_temporal_adjustments(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test qualifier with temporal adjustments."""
        # Set up lead with temporal context
        agent_state["lead"].last_interaction_at = (datetime.now() - timedelta(days=45)).isoformat()
        agent_state["lead"].budget = 600000  # High value
        
        with patch('tools.agent_tools.query_properties_tool') as mock_query:
            mock_query.invoke.return_value = []

    def test_partial_info_handling_missing_budget(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test qualifier handling of missing budget information."""
        # Create lead with missing budget
        agent_state["lead"].budget = None
        agent_state["lead"].message = "Looking for a 3 bedroom house in Miami"
        
        # Mock property query returns results but need budget clarification
        with patch('tools.agent_tools.query_properties_db') as mock_query:
            mock_query.return_value = [
                {"id": "prop1", "price": 350000, "location": "Miami", "bedrooms": 3},
                {"id": "prop2", "price": 650000, "location": "Miami", "bedrooms": 3},
            ]
            
            with patch('tools.agent_tools.send_instagram_message') as mock_send:
                mock_send.return_value = True
                
                result = qualifier_agent.process(agent_state)
                
                # Should ask for budget information instead of qualifying
                messages = result.get("messages", [])
                budget_question_found = any(
                    "budget" in str(msg).lower() for msg in messages
                )
                assert budget_question_found
                assert result.get("requires_more_info", True)
                assert result.get("next_agent") != "scheduler"  # Should not qualify yet

    def test_partial_info_handling_missing_location(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test qualifier handling of missing location information."""
        agent_state["lead"].location = None
        agent_state["lead"].message = "Looking for a 3 bedroom house with budget around $400k"
        
        with patch('tools.agent_tools.send_instagram_message') as mock_send:
            mock_send.return_value = True
            
            result = qualifier_agent.process(agent_state)
            
            # Should ask for location clarification
            messages = result.get("messages", [])
            location_clarification = any(
                "location" in str(msg).lower() or "area" in str(msg).lower() 
                for msg in messages
            )
            assert location_clarification
            assert result.get("requires_more_info", True)

    def test_partial_info_handling_missing_property_preferences(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test qualifier handling of missing property preferences."""
        agent_state["lead"].property_type = None
        agent_state["lead"].desired_bedrooms = None
        agent_state["lead"].message = "Looking for a home in Miami with budget $500k"
        
        with patch('tools.agent_tools.send_instagram_message') as mock_send:
            mock_send.return_value = True
            
            result = qualifier_agent.process(agent_state)
            
            # Should ask for property preferences
            messages = result.get("messages", [])
            preferences_clarification = any(
                "bedroom" in str(msg).lower() or "property type" in str(msg).lower()
                for msg in messages
            )
            assert preferences_clarification

    def test_budget_mismatch_detection(self, qualifier_agent, agent_state, sample_properties, mock_compliance, mock_audit):
        """Test budget mismatch detection and suggestions."""
        # Set up high expectations with low budget
        agent_state["lead"].budget = 300000
        agent_state["lead"].desired_bedrooms = 4
        agent_state["lead"].location = "Miami"
        
        # Mock properties where matching requirements cost more
        with patch('tools.agent_tools.query_properties_db') as mock_query:
            mock_query.return_value = [
                {"id": "prop1", "price": 600000, "bedrooms": 4, "location": "Miami"},
                {"id": "prop2", "price": 550000, "bedrooms": 4, "location": "Miami"},
            ]
            
            with patch('tools.agent_tools.send_instagram_message') as mock_send:
                mock_send.return_value = True
                
                result = qualifier_agent.process(agent_state)
                
                # Should detect budget mismatch and offer alternatives
                messages = result.get("messages", [])
                budget_mismatch_detected = any(
                    "budget" in str(msg).lower() and ("higher" in str(msg).lower() or "afford" in str(msg).lower())
                    for msg in messages
                )
                assert budget_mismatch_detected
                assert "budget_mismatch" in result
                assert result["budget_mismatch"]["detected"] == True

    def test_no_matching_properties_handling(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test handling when no properties match the criteria."""
        agent_state["lead"].budget = 200000
        agent_state["lead"].location = "Miami Beach"
        agent_state["lead"].desired_bedrooms = 3
        
        # Mock empty results
        with patch('tools.agent_tools.query_properties_db') as mock_query:
            mock_query.return_value = []
            
            with patch('tools.agent_tools.send_instagram_message') as mock_send:
                mock_send.return_value = True
                
                result = qualifier_agent.process(agent_state)
                
                # Should offer waitlist or suggest alternatives
                messages = result.get("messages", [])
                no_match_handling = any(
                    "waitlist" in str(msg).lower() or "notify" in str(msg).lower() or "alternative" in str(msg).lower()
                    for msg in messages
                )
                assert no_match_handling
                assert "no_properties_found" in result
                assert result["no_properties_found"] == True

    def test_complete_info_proceeds_to_qualification(self, qualifier_agent, agent_state, sample_properties, mock_compliance, mock_audit):
        """Test that complete information proceeds to normal qualification."""
        # Lead with all required information
        agent_state["lead"].budget = 400000
        agent_state["lead"].location = "Miami"
        agent_state["lead"].desired_bedrooms = 3
        agent_state["lead"].property_type = "house"
        
        # Mock good matching properties
        with patch('tools.agent_tools.query_properties_db') as mock_query:
            mock_query.return_value = sample_properties
            
            with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                mock_qualify.return_value = {"score": 0.8, "reasoning": "Good match"}
                
                result = qualifier_agent.process(agent_state)
                
                # Should proceed to qualification normally
                assert not result.get("requires_more_info", False)
                assert "score" in result or getattr(result.get("lead"), "qualified_score", None) is not None
                assert result.get("next_agent") in ["scheduler", "followup"]
            
            with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                mock_qualify.invoke.return_value = {"score": 0.6, "reasoning": "Base score"}
                
                with patch('tools.agent_tools.send_instagram_message') as mock_send:
                    mock_send.invoke.return_value = True
                    
                    result = qualifier_agent.process(agent_state)
                    
                    assert "temporal_adjustments" in result
                    # Score should be adjusted upward for high-value lead
                    assert result["temporal_adjustments"]["adjusted_score"] > 0.6
    
    def test_qualifier_compliance_integration(self, qualifier_agent, agent_state, mock_audit):
        """Test qualifier compliance integration."""
        # Mock compliance violation
        async def mock_compliance_violation(message, context):
            return {
                "passed": False,
                "violations": [{"pattern": "age", "risk_level": "high"}],
                "suggested_replacement": "I can help you find suitable properties."
            }
        
        with patch('tools.compliance.fair_housing_evaluator', side_effect=mock_compliance_violation):
            with patch('tools.agent_tools.query_properties_tool') as mock_query:
                mock_query.invoke.return_value = []
                
                with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                    mock_qualify.invoke.return_value = {"score": 0.8, "reasoning": "Good"}
                    
                    with patch('tools.agent_tools.send_instagram_message') as mock_send:
                        mock_send.invoke.return_value = True
                        
                        result = qualifier_agent.process(agent_state)
                        
                        # Should use neutral replacement message
                        response_message = result["messages"][-1]["content"]
                        assert "suitable properties" in response_message
    
    def test_qualifier_error_handling(self, qualifier_agent, agent_state):
        """Test qualifier error handling."""
        # Mock database error
        with patch('tools.agent_tools.query_properties_tool') as mock_query:
            mock_query.invoke.side_effect = Exception("Database error")
            
            result = qualifier_agent.process(agent_state)
            
            assert "error_message" in result
            assert result["next_agent"] == "followup"  # Safe fallback


class TestBudgetReconciliation:
    """Test budget reconciliation functionality."""
    
    def test_exact_match_scenario(self, sample_properties):
        """Test when exact matches exist."""
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=400000,
            inventory=sample_properties,
            location="Miami"
        )
        
        assert result["has_exact_match"] == True
        assert result["exact_matches"] > 0
        assert "Great news!" in result["message"]
    
    def test_no_exact_match_with_alternatives(self, sample_properties):
        """Test when no exact matches but alternatives exist."""
        result = reconcile_budget_mismatch(
            desired_bedrooms=4,  # No 4BR in sample data
            budget=400000,
            inventory=sample_properties,
            location="Miami"
        )
        
        assert result["has_exact_match"] == False
        assert len(result["alternatives"]) > 0
        assert result["recommendation"] in ["premium_alternative", "stretch_budget", "location_expansion"]
    
    def test_budget_too_low_scenario(self, sample_properties):
        """Test when budget is too low for desired bedrooms."""
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=200000,  # Too low for 3BR
            inventory=sample_properties,
            location="Miami"
        )
        
        assert result["has_exact_match"] == False
        assert len(result["alternatives"]) > 0
        # Should suggest premium 2BR alternatives
        assert any(alt["type"] == "premium_alternative" for alt in result["alternatives"])
    
    def test_reconciliation_error_handling(self):
        """Test reconciliation error handling."""
        result = reconcile_budget_mismatch(
            desired_bedrooms=None,  # Invalid input
            budget=None,
            inventory=[],
            location=None
        )
        
        assert result["has_exact_match"] == False
        assert result["recommendation"] == "manual_review"
        assert "error" in result["reasoning"].lower()


class TestTemporalAdjustments:
    """Test temporal qualification adjustments."""
    
    def test_re_engagement_bonus(self):
        """Test re-engagement after long absence bonus."""
        lead_data = {
            "user_id": "test_123",
            "last_interaction_at": (datetime.now() - timedelta(days=45)).isoformat(),
            "budget": 300000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.6)
        
        assert result["adjusted_score"] > 0.6
        assert any("Re-engaged" in adj for adj in result["adjustments"])
    
    def test_high_value_lead_bonus(self):
        """Test high-value lead bonus."""
        lead_data = {
            "user_id": "test_123",
            "budget": 600000  # High value
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.6)
        
        assert result["adjusted_score"] > 0.6
        assert any("High-value" in adj for adj in result["adjustments"])
    
    def test_escalating_engagement_bonus(self):
        """Test escalating engagement trajectory bonus."""
        lead_data = {
            "user_id": "test_123",
            "engagement_trajectory": "escalating",
            "budget": 300000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.6)
        
        assert result["adjusted_score"] > 0.6
        assert any("Escalating" in adj for adj in result["adjustments"])
    
    def test_immediate_timeline_bonus(self):
        """Test immediate timeline bonus."""
        lead_data = {
            "user_id": "test_123",
            "timeline": "immediate",
            "budget": 300000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.6)
        
        assert result["adjusted_score"] > 0.6
        assert any("Immediate" in adj for adj in result["adjustments"])
    
    def test_cooling_engagement_penalty(self):
        """Test cooling engagement trajectory penalty."""
        lead_data = {
            "user_id": "test_123",
            "engagement_trajectory": "cooling",
            "budget": 300000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.7)
        
        assert result["adjusted_score"] < 0.7
        assert any("Cooling" in adj for adj in result["adjustments"])
    
    def test_score_capping(self):
        """Test that adjusted score is capped at 1.0."""
        lead_data = {
            "user_id": "test_123",
            "budget": 800000,  # Very high value
            "timeline": "immediate",
            "engagement_trajectory": "escalating",
            "last_interaction_at": (datetime.now() - timedelta(days=60)).isoformat()
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.9)
        
        assert result["adjusted_score"] <= 1.0
        assert len(result["adjustments"]) > 2  # Multiple bonuses applied
    
    def test_temporal_adjustment_error_handling(self):
        """Test temporal adjustment error handling."""
        invalid_lead_data = {
            "user_id": None,  # Invalid data
            "budget": "invalid"
        }
        
        result = calculate_temporal_qualification_adjustments(invalid_lead_data, 0.6)
        
        assert result["adjusted_score"] == 0.6  # Should return base score
        assert len(result["adjustments"]) == 0
        assert "error" in result["reasoning"].lower()


class TestQualifierIntegration:
    """Test qualifier integration with other components."""
    
    def test_qualifier_to_scheduler_routing(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test routing to scheduler for high-scoring leads."""
        # Set up high-scoring scenario
        agent_state["lead"].budget = 600000  # High value
        
        with patch('tools.agent_tools.query_properties_tool') as mock_query:
            mock_query.invoke.return_value = [{"id": "prop1", "price": 550000}]
            
            with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                mock_qualify.invoke.return_value = {"score": 0.9, "reasoning": "Excellent match"}
                
                with patch('tools.agent_tools.send_instagram_message') as mock_send:
                    mock_send.invoke.return_value = True
                    
                    result = qualifier_agent.process(agent_state)
                    
                    assert result["next_agent"] == "scheduler"
                    assert result.get("interrupt") == True  # HITL for high-value
    
    def test_qualifier_to_followup_routing(self, qualifier_agent, agent_state, mock_compliance, mock_audit):
        """Test routing to followup for lower-scoring leads."""
        with patch('tools.agent_tools.query_properties_tool') as mock_query:
            mock_query.invoke.return_value = []
            
            with patch('tools.agent_tools.qualify_lead_with_llm') as mock_qualify:
                mock_qualify.invoke.return_value = {"score": 0.4, "reasoning": "Low match"}
                
                with patch('tools.agent_tools.send_instagram_message') as mock_send:
                    mock_send.invoke.return_value = True
                    
                    result = qualifier_agent.process(agent_state)
                    
                    assert result["next_agent"] == "followup"
                    assert result.get("interrupt") != True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])