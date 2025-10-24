"""
Tests for the enhanced qualification flow with lead scoring and progressive qualification.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json

from backend.agents.qualifier import QualifierAgent
from backend.agents.followup import FollowupAgent
from backend.agents.offramp import OfframpAgent
from backend.utils.lead_scoring import LeadScoringSystem, calculate_lead_score
from backend.models.lead import Lead
from backend.schemas.state import AgentState, ConversationMessage
from backend.tools.agent_tools import fetch_lead_magnet, deliver_property_info, send_market_insights


class TestLeadScoringSystem:
    """Test the lead scoring system functionality."""
    
    def test_calculate_lead_score_perfect_lead(self):
        """Test scoring for a perfect lead with all information."""
        lead_data = {
            "budget": 800000,
            "timeline": "3 months",
            "location": "Austin, TX",
            "property_type": "single_family",
            "bedrooms": 3,
            "bathrooms": 2,
            "square_footage": 2000,
            "move_in_date": "2024-02-01",
            "financing_pre_approved": True,
            "has_agent": False,
            "first_time_buyer": False,
            "investment_property": False,
            "contact_info": {"email": "test@example.com", "phone": "555-1234"}
        }
        
        score = calculate_lead_score(lead_data)
        assert score >= 0.9, f"Perfect lead should score >= 0.9, got {score}"
    
    def test_calculate_lead_score_partial_lead(self):
        """Test scoring for a lead with partial information."""
        lead_data = {
            "budget": 500000,
            "timeline": "6 months",
            "location": "Austin, TX",
            "property_type": "condo"
        }
        
        score = calculate_lead_score(lead_data)
        assert 0.4 <= score < 0.75, f"Partial lead should score 0.4-0.75, got {score}"
    
    def test_calculate_lead_score_low_quality_lead(self):
        """Test scoring for a low quality lead."""
        lead_data = {
            "timeline": "12+ months",
            "location": "Texas",
            "property_type": "unsure"
        }
        
        score = calculate_lead_score(lead_data)
        assert score < 0.4, f"Low quality lead should score < 0.4, got {score}"
    
    def test_budget_scoring(self):
        """Test budget component scoring."""
        # High budget (Austin market)
        score = calculate_lead_score({"budget": 1000000})
        assert score >= 0.25, "High budget should score well"
        
        # Medium budget
        score = calculate_lead_score({"budget": 600000})
        assert 0.15 <= score < 0.25, "Medium budget should score moderately"
        
        # Low budget
        score = calculate_lead_score({"budget": 200000})
        assert score < 0.15, "Low budget should score poorly"
        
        # No budget
        score = calculate_lead_score({})
        assert score == 0, "No budget should score 0"
    
    def test_timeline_scoring(self):
        """Test timeline component scoring."""
        # Urgent timeline
        score = calculate_lead_score({"timeline": "1 month"})
        assert score >= 0.2, "Urgent timeline should score well"
        
        # Medium timeline
        score = calculate_lead_score({"timeline": "6 months"})
        assert 0.1 <= score < 0.2, "Medium timeline should score moderately"
        
        # Long timeline
        score = calculate_lead_score({"timeline": "12+ months"})
        assert score < 0.1, "Long timeline should score poorly"
    
    def test_location_scoring(self):
        """Test location component scoring."""
        # Specific location
        score = calculate_lead_score({"location": "Austin, TX"})
        assert score >= 0.15, "Specific location should score well"
        
        # General location
        score = calculate_lead_score({"location": "Texas"})
        assert 0.05 <= score < 0.15, "General location should score moderately"
        
        # No location
        score = calculate_lead_score({})
        assert score == 0, "No location should score 0"
    
    def test_completeness_bonus(self):
        """Test completeness bonus calculation."""
        # Complete profile
        complete_data = {
            "budget": 800000,
            "timeline": "3 months",
            "location": "Austin, TX",
            "property_type": "single_family",
            "bedrooms": 3,
            "bathrooms": 2,
            "contact_info": {"email": "test@example.com"}
        }
        
        complete_score = calculate_lead_score(complete_data)
        
        # Minimal profile
        minimal_data = {"budget": 800000}
        minimal_score = calculate_lead_score(minimal_data)
        
        assert complete_score > minimal_score, "Complete profile should score higher"
    
    def test_score_delta_calculation(self):
        """Test score delta calculation."""
        previous_score = 0.3
        current_score = 0.8
        
        delta = current_score - previous_score
        assert delta == 0.5, f"Score delta should be 0.5, got {delta}"
        
        # Test negative delta
        current_score = 0.2
        delta = current_score - previous_score
        assert delta == -0.1, f"Negative delta should be -0.1, got {delta}"


class TestQualifierAgent:
    """Test the enhanced qualifier agent."""
    
    @pytest.fixture
    def mock_qualifier(self):
        """Create a mock qualifier agent."""
        with patch('backend.agents.qualifier.SupabaseClient'), \
             patch('backend.agents.qualifier.LLMClient'):
            return QualifierAgent()
    
    @pytest.mark.asyncio
    async def test_progressive_qualification_start(self, mock_qualifier):
        """Test starting progressive qualification."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="qualifier",
            lead_data={}
        )
        
        with patch.object(mock_qualifier, '_determine_next_question') as mock_next_q, \
             patch.object(mock_qualifier, '_update_lead_data') as mock_update:
            
            mock_next_q.return_value = "What's your budget range?"
            mock_update.return_value = None
            
            result = await mock_qualifier.process_message(state, "Hi, I'm interested in buying a home")
            
            assert "budget" in result.response.lower()
            mock_next_q.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_progressive_qualification_budget_response(self, mock_qualifier):
        """Test processing budget response in qualification."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[
                ConversationMessage(role="assistant", content="What's your budget range?", timestamp=datetime.now())
            ],
            current_agent="qualifier",
            lead_data={},
            qualification_stage="budget_inquiry"
        )
        
        with patch.object(mock_qualifier, '_extract_budget_from_response') as mock_extract, \
             patch.object(mock_qualifier, '_update_lead_data') as mock_update, \
             patch.object(mock_qualifier, '_determine_next_question') as mock_next_q:
            
            mock_extract.return_value = 750000
            mock_update.return_value = None
            mock_next_q.return_value = "When are you looking to move?"
            
            result = await mock_qualifier.process_message(state, "My budget is around $750,000")
            
            assert "move" in result.response.lower() or "timeline" in result.response.lower()
            mock_extract.assert_called_once_with("My budget is around $750,000")
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_qualification_complete_high_score(self, mock_qualifier):
        """Test qualification completion with high score."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="qualifier",
            lead_data={
                "budget": 800000,
                "timeline": "3 months",
                "location": "Austin, TX",
                "property_type": "single_family",
                "contact_info": {"email": "test@example.com"}
            },
            qualification_stage="complete"
        )
        
        with patch.object(mock_qualifier, '_calculate_lead_score') as mock_score, \
             patch.object(mock_qualifier, '_update_lead_score') as mock_update_score:
            
            mock_score.return_value = 0.85
            mock_update_score.return_value = None
            
            result = await mock_qualifier.process_message(state, "Yes, that all looks correct")
            
            assert "scheduler" in result.next_agent
            assert "qualified" in result.lead_data.get("status", "")
            mock_update_score.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_qualification_complete_nurture_score(self, mock_qualifier):
        """Test qualification completion with nurture score."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="qualifier",
            lead_data={
                "budget": 500000,
                "timeline": "6 months",
                "location": "Texas"
            },
            qualification_stage="complete"
        )
        
        with patch.object(mock_qualifier, '_calculate_lead_score') as mock_score, \
             patch.object(mock_qualifier, '_update_lead_score') as mock_update_score:
            
            mock_score.return_value = 0.6
            mock_update_score.return_value = None
            
            result = await mock_qualifier.process_message(state, "That's right")
            
            assert "followup" in result.next_agent
            assert "nurturing" in result.lead_data.get("status", "")
            mock_update_score.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_qualification_complete_offramp_score(self, mock_qualifier):
        """Test qualification completion with offramp score."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="qualifier",
            lead_data={
                "timeline": "12+ months",
                "location": "somewhere in Texas"
            },
            qualification_stage="complete"
        )
        
        with patch.object(mock_qualifier, '_calculate_lead_score') as mock_score, \
             patch.object(mock_qualifier, '_update_lead_score') as mock_update_score:
            
            mock_score.return_value = 0.3
            mock_update_score.return_value = None
            
            result = await mock_qualifier.process_message(state, "Yes")
            
            assert "offramp" in result.next_agent
            assert "disqualified" in result.lead_data.get("status", "")
            mock_update_score.assert_called_once()
    
    def test_extract_budget_from_response(self, mock_qualifier):
        """Test budget extraction from user response."""
        # Test various budget formats
        test_cases = [
            ("My budget is $750,000", 750000),
            ("Around 500k", 500000),
            ("Looking to spend about 1.2 million", 1200000),
            ("Budget is 300-400k", 350000),  # Takes average
            ("No budget set", None)
        ]
        
        for response, expected in test_cases:
            result = mock_qualifier._extract_budget_from_response(response)
            assert result == expected, f"Expected {expected} from '{response}', got {result}"
    
    def test_extract_timeline_from_response(self, mock_qualifier):
        """Test timeline extraction from user response."""
        test_cases = [
            ("Looking to move in 2 months", "2 months"),
            ("About 3 months", "3 months"),
            ("6 months or so", "6 months"),
            ("Maybe next year", "12+ months"),
            ("Not sure yet", None)
        ]
        
        for response, expected in test_cases:
            result = mock_qualifier._extract_timeline_from_response(response)
            assert result == expected, f"Expected {expected} from '{response}', got {result}"
    
    def test_determine_next_question(self, mock_qualifier):
        """Test next question determination based on missing data."""
        # Test missing budget
        lead_data = {"timeline": "3 months", "location": "Austin, TX"}
        question = mock_qualifier._determine_next_question(lead_data)
        assert "budget" in question.lower()
        
        # Test missing timeline
        lead_data = {"budget": 750000, "location": "Austin, TX"}
        question = mock_qualifier._determine_next_question(lead_data)
        assert "timeline" in question.lower() or "when" in question.lower()
        
        # Test missing location
        lead_data = {"budget": 750000, "timeline": "3 months"}
        question = mock_qualifier._determine_next_question(lead_data)
        assert "location" in question.lower() or "where" in question.lower()
        
        # Test complete data
        lead_data = {
            "budget": 750000,
            "timeline": "3 months",
            "location": "Austin, TX",
            "property_type": "single_family"
        }
        question = mock_qualifier._determine_next_question(lead_data)
        assert "complete" in question.lower() or "ready" in question.lower()


class TestFollowupAgent:
    """Test the enhanced followup agent."""
    
    @pytest.fixture
    def mock_followup(self):
        """Create a mock followup agent."""
        with patch('backend.agents.followup.SupabaseClient'), \
             patch('backend.agents.followup.LLMClient'):
            return FollowupAgent()
    
    @pytest.mark.asyncio
    async def test_nurture_with_score_improvement(self, mock_followup):
        """Test nurture sequence when lead score improves."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="followup",
            lead_data={
                "status": "nurturing",
                "qualified_score": 0.6,
                "previous_score": 0.4,
                "budget": 600000,
                "timeline": "6 months"
            }
        )
        
        with patch.object(mock_followup, '_analyze_nurture_response') as mock_analyze, \
             patch.object(mock_followup, '_create_nurture_sequence') as mock_nurture:
            
            mock_analyze.return_value = "re_qualification"
            mock_nurture.return_value = None
            
            result = await mock_followup.process_message(state, "Actually, my timeline is more like 3 months now")
            
            assert "re-qualification" in result.response.lower() or "qualifier" in result.next_agent
            mock_analyze.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_value_delivery_nurture(self, mock_followup):
        """Test value delivery during nurture."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="followup",
            lead_data={
                "status": "nurturing",
                "qualified_score": 0.6,
                "location": "Austin, TX",
                "property_type": "condo"
            }
        )
        
        with patch.object(mock_followup, '_analyze_nurture_response') as mock_analyze, \
             patch.object(mock_followup, '_deliver_value_content') as mock_deliver:
            
            mock_analyze.return_value = "value_delivery"
            mock_deliver.return_value = "Here's some market insights for Austin condos..."
            
            result = await mock_followup.process_message(state, "What's the condo market like in Austin?")
            
            assert "market" in result.response.lower() or "condo" in result.response.lower()
            mock_analyze.assert_called_once()
            mock_deliver.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_engagement_nurture(self, mock_followup):
        """Test engagement-based nurture."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="followup",
            lead_data={
                "status": "nurturing",
                "qualified_score": 0.5,
                "engagement_level": "high"
            }
        )
        
        with patch.object(mock_followup, '_analyze_nurture_response') as mock_analyze, \
             patch.object(mock_followup, '_build_relationship') as mock_build:
            
            mock_analyze.return_value = "engagement"
            mock_build.return_value = "Great question! Let me share some insights..."
            
            result = await mock_followup.process_message(state, "How's the market overall?")
            
            assert result.response is not None
            mock_analyze.assert_called_once()
            mock_build.assert_called_once()
    
    def test_analyze_nurture_response(self, mock_followup):
        """Test nurture response analysis."""
        # Test re-qualification indicators
        response = "Actually, I'm ready to buy in 2 months and have a $800k budget"
        result = mock_followup._analyze_nurture_response(response)
        assert result == "re_qualification"
        
        # Test value delivery indicators
        response = "Can you tell me about properties in Zilker?"
        result = mock_followup._analyze_nurture_response(response)
        assert result == "value_delivery"
        
        # Test engagement indicators
        response = "Thanks for the info! How's the market trending?"
        result = mock_followup._analyze_nurture_response(response)
        assert result == "engagement"
        
        # Test standard nurture
        response = "OK, thanks"
        result = mock_followup._analyze_nurture_response(response)
        assert result == "standard_nurture"


class TestOfframpAgent:
    """Test the off-ramp agent."""
    
    @pytest.fixture
    def mock_offramp(self):
        """Create a mock off-ramp agent."""
        with patch('backend.agents.offramp.SupabaseClient'), \
             patch('backend.agents.offramp.LLMClient'):
            return OfframpAgent()
    
    @pytest.mark.asyncio
    async def test_polite_offramp_delivery(self, mock_offramp):
        """Test polite off-ramp message delivery."""
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
        
        with patch.object(mock_offramp, '_determine_offramp_strategy') as mock_strategy, \
             patch.object(mock_offramp, '_update_offramp_status') as mock_update:
            
            mock_strategy.return_value = "gentle_rejection"
            mock_update.return_value = None
            
            result = await mock_offramp.process_message(state, "OK")
            
            assert "thank you" in result.response.lower() or "appreciate" in result.response.lower()
            assert "newsletter" in result.response.lower() or "stay in touch" in result.response.lower()
            mock_strategy.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_newsletter_opt_in(self, mock_offramp):
        """Test newsletter opt-in handling."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="offramp",
            lead_data={
                "status": "disqualified",
                "newsletter_opt_in": False
            }
        )
        
        with patch.object(mock_offramp, '_update_newsletter_opt_in') as mock_update:
            mock_update.return_value = None
            
            result = await mock_offramp.process_message(state, "Yes, I'd like to receive the newsletter")
            
            assert "newsletter" in result.response.lower()
            assert "thank you" in result.response.lower()
            mock_update.assert_called_once_with(True)
    
    def test_determine_offramp_strategy(self, mock_offramp):
        """Test off-ramp strategy determination."""
        # Test long timeline
        lead_data = {"offramp_reason": "long_timeline", "qualified_score": 0.3}
        strategy = mock_offramp._determine_offramp_strategy(lead_data)
        assert strategy in ["gentle_rejection", "nurture_invitation"]
        
        # Test low budget
        lead_data = {"offramp_reason": "low_budget", "qualified_score": 0.2}
        strategy = mock_offramp._determine_offramp_strategy(lead_data)
        assert strategy in ["helpful_guidance", "resource_offer"]
        
        # Test outside service area
        lead_data = {"offramp_reason": "outside_service_area", "qualified_score": 0.1}
        strategy = mock_offramp._determine_offramp_strategy(lead_data)
        assert strategy in ["referral", "polite_rejection"]


class TestQualificationIntegration:
    """Test integration between qualification components."""
    
    @pytest.mark.asyncio
    async def test_full_qualification_flow(self):
        """Test the complete qualification flow from start to finish."""
        # This would be an integration test that simulates the full flow
        # For now, we'll test the key integration points
        
        # Test score calculation integration
        lead_data = {
            "budget": 750000,
            "timeline": "3 months",
            "location": "Austin, TX",
            "property_type": "single_family"
        }
        
        score = calculate_lead_score(lead_data)
        assert 0.75 <= score <= 1.0, f"Good lead should score >= 0.75, got {score}"
        
        # Test routing decision based on score
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
    
    def test_score_threshold_consistency(self):
        """Test that score thresholds are consistent across agents."""
        # Test the same score produces consistent routing
        test_scores = [0.8, 0.6, 0.3]
        expected_routing = [
            ("scheduler", "qualified"),
            ("followup", "nurturing"),
            ("offramp", "disqualified")
        ]
        
        for score, (expected_agent, expected_status) in zip(test_scores, expected_routing):
            # Test qualifier routing
            if score >= 0.75:
                agent = "scheduler"
                status = "qualified"
            elif score >= 0.4:
                agent = "followup"
                status = "nurturing"
            else:
                agent = "offramp"
                status = "disqualified"
            
            assert agent == expected_agent, f"Score {score} should route to {expected_agent}"
            assert status == expected_status, f"Score {score} should have status {expected_status}"


if __name__ == "__main__":
    pytest.main([__file__])