"""
Tests for nurture sequences system using LangGraph orchestration.

Tests industry-specific sequences, scheduling, template personalization,
and integration with engagement tracker.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from automation.nurture_sequences import (
    NurtureSequenceManager,
    schedule_nurture_sequence,
    get_next_touch_point,
    cancel_nurture_sequence,
    update_sequence_progress,
    IndustryType,
    ChannelType,
    TouchPoint,
    NurtureSequence
)

class TestNurtureSequenceManager:
    """Test cases for NurtureSequenceManager"""
    
    @pytest.fixture
    def manager(self):
        """Create nurture sequence manager for testing"""
        with patch('automation.nurture_sequences.redis_client') as mock_redis:
            with patch('automation.nurture_sequences.redis_circuit_breaker') as mock_breaker:
                mock_redis.ping.return_value = True
                mock_breaker.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
                yield NurtureSequenceManager()
    
    @pytest.fixture
    def sample_lead_data(self):
        """Sample lead data for testing"""
        return {
            "user_id": "test_user_123",
            "first_name": "John",
            "budget": 500000,
            "location": "Miami",
            "timeline": "3 months",
            "property_type": "2BHK"
        }
    
    def test_industry_sequences_initialization(self, manager):
        """Test that industry sequences are properly initialized"""
        assert IndustryType.REAL_ESTATE in manager.sequences
        assert IndustryType.FITNESS in manager.sequences
        assert IndustryType.RESTAURANT in manager.sequences
        
        # Check real estate sequences
        real_estate_seqs = manager.sequences[IndustryType.REAL_ESTATE]
        assert "high_intent" in real_estate_seqs
        assert "low_intent" in real_estate_seqs
        
        # Check high intent sequence structure
        high_intent = real_estate_seqs["high_intent"]
        assert high_intent.industry_type == IndustryType.REAL_ESTATE
        assert high_intent.intent_threshold == 0.6
        assert len(high_intent.touch_points) == 5
        assert high_intent.total_duration_days == 21
    
    def test_message_templates_initialization(self, manager):
        """Test that message templates are properly initialized"""
        assert IndustryType.REAL_ESTATE in manager.templates
        assert IndustryType.FITNESS in manager.templates
        
        # Check real estate templates
        real_estate_templates = manager.templates[IndustryType.REAL_ESTATE]
        assert "market_insights" in real_estate_templates
        assert "property_listings" in real_estate_templates
        
        # Check template structure
        template = real_estate_templates["market_insights"]
        assert "template" in template
        assert "personalization_fields" in template
        assert "compliance_required" in template
        assert isinstance(template["personalization_fields"], list)
    
    def test_schedule_real_estate_high_intent_sequence(self, manager, sample_lead_data):
        """Test scheduling real estate high intent sequence"""
        user_id = sample_lead_data["user_id"]
        lead_score = 0.8  # Above 0.6 threshold
        industry_type = "real_estate"
        
        result = manager.schedule_nurture_sequence(user_id, lead_score, industry_type, sample_lead_data)
        
        assert result is True
        
        # Check sequence was stored
        sequence_key = manager.SEQUENCE_KEY.format(user_id=user_id)
        manager.redis_client.get.assert_called_with(sequence_key)
        
        # Check schedule was created
        schedule_key = manager.SCHEDULE_KEY.format(user_id=user_id)
        manager.redis_client.setex.assert_called()
        
        # Verify sequence data
        stored_sequence = json.loads(manager.redis_client.setex.call_args[0][2])
        assert stored_sequence["user_id"] == user_id
        assert stored_sequence["industry_type"] == industry_type
        assert stored_sequence["lead_score"] == lead_score
        assert stored_sequence["intent_level"] == "high_intent"
        assert stored_sequence["status"] == "active"
    
    def test_schedule_real_estate_low_intent_sequence(self, manager, sample_lead_data):
        """Test scheduling real estate low intent sequence"""
        user_id = sample_lead_data["user_id"]
        lead_score = 0.4  # Below 0.6 threshold
        industry_type = "real_estate"
        
        result = manager.schedule_nurture_sequence(user_id, lead_score, industry_type, sample_lead_data)
        
        assert result is True
        
        # Verify low intent sequence was selected
        stored_sequence = json.loads(manager.redis_client.setex.call_args[0][2])
        assert stored_sequence["intent_level"] == "low_intent"
    
    def test_schedule_fitness_high_intent_sequence(self, manager, sample_lead_data):
        """Test scheduling fitness high intent sequence"""
        user_id = sample_lead_data["user_id"]
        lead_score = 0.7  # Above 0.5 threshold
        industry_type = "fitness"
        
        result = manager.schedule_nurture_sequence(user_id, lead_score, industry_type, sample_lead_data)
        
        assert result is True
        
        # Verify fitness sequence structure
        stored_sequence = json.loads(manager.redis_client.setex.call_args[0][2])
        assert stored_sequence["industry_type"] == industry_type
        assert stored_sequence["intent_level"] == "high_intent"
        
        # Check fitness-specific touch points
        sequence_data = stored_sequence["sequence"]
        assert len(sequence_data["touch_points"]) == 4  # Fitness has 4 touch points
        assert sequence_data["total_duration_days"] == 10
    
    def test_schedule_restaurant_high_intent_sequence(self, manager, sample_lead_data):
        """Test scheduling restaurant high intent sequence"""
        user_id = sample_lead_data["user_id"]
        lead_score = 0.6  # Above 0.55 threshold
        industry_type = "restaurant"
        
        result = manager.schedule_nurture_sequence(user_id, lead_score, industry_type, sample_lead_data)
        
        assert result is True
        
        # Verify restaurant sequence structure
        stored_sequence = json.loads(manager.redis_client.setex.call_args[0][2])
        assert stored_sequence["industry_type"] == industry_type
        assert stored_sequence["intent_level"] == "high_intent"
        
        # Check restaurant-specific touch points
        sequence_data = stored_sequence["sequence"]
        assert len(sequence_data["touch_points"]) == 4  # Restaurant has 4 touch points
        assert sequence_data["total_duration_days"] == 14
    
    def test_get_next_touch_point(self, manager, sample_lead_data):
        """Test getting next scheduled touch point"""
        user_id = sample_lead_data["user_id"]
        
        # Mock schedule data
        schedule_data = {
            "upcoming_touches": [
                {
                    "day": 1,
                    "channel": "sms",
                    "template_key": "market_insights",
                    "scheduled_for": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                    "status": "scheduled"
                },
                {
                    "day": 3,
                    "channel": "email",
                    "template_key": "property_listings",
                    "scheduled_for": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                    "status": "scheduled"
                }
            ]
        }
        
        manager.redis_client.get.return_value = json.dumps(schedule_data)
        
        next_touch = manager.get_next_touch_point(user_id)
        
        assert next_touch is not None
        assert next_touch["day"] == 1
        assert next_touch["channel"] == "sms"
        assert next_touch["template_key"] == "market_insights"
        assert "retrieved_at" in next_touch
    
    def test_get_next_touch_point_no_schedule(self, manager):
        """Test getting next touch point when no schedule exists"""
        user_id = "nonexistent_user"
        
        manager.redis_client.get.return_value = None
        
        next_touch = manager.get_next_touch_point(user_id)
        
        assert next_touch is None
    
    def test_cancel_nurture_sequence(self, manager, sample_lead_data):
        """Test cancelling nurture sequence"""
        user_id = sample_lead_data["user_id"]
        
        # Mock existing sequence
        sequence_data = {
            "user_id": user_id,
            "status": "active",
            "scheduled_at": datetime.utcnow().isoformat()
        }
        manager.redis_client.get.return_value = json.dumps(sequence_data)
        
        result = manager.cancel_nurture_sequence(user_id)
        
        assert result is True
        
        # Verify sequence was marked as cancelled
        updated_sequence = json.loads(manager.redis_client.setex.call_args[0][2])
        assert updated_sequence["status"] == "cancelled"
        assert "cancelled_at" in updated_sequence
        
        # Verify schedule was cleared
        schedule_key = manager.SCHEDULE_KEY.format(user_id=user_id)
        manager.redis_client.delete.assert_called_with(schedule_key)
    
    def test_update_sequence_progress(self, manager, sample_lead_data):
        """Test updating sequence progress"""
        user_id = sample_lead_data["user_id"]
        
        result = manager.update_sequence_progress(user_id, True)
        
        assert result is True
        
        # Verify progress was updated
        progress_key = manager.PROGRESS_KEY.format(user_id=user_id)
        manager.redis_client.setex.assert_called()
        
        # Check progress data structure
        progress_data = json.loads(manager.redis_client.setex.call_args[0][2])
        assert "completed_touches" in progress_data
        assert "last_updated" in progress_data
        assert len(progress_data["completed_touches"]) > 0
    
    @patch('automation.nurture_sequences.engagement_tracker')
    def test_integration_with_engagement_tracker(self, mock_engagement, manager, sample_lead_data):
        """Test integration with engagement tracker"""
        user_id = sample_lead_data["user_id"]
        
        # Schedule sequence (should record touch points)
        manager.schedule_nurture_sequence(user_id, 0.8, "real_estate", sample_lead_data)
        
        # Verify engagement tracker was called
        mock_engagement.record_touch_point.assert_called()
        
        # Check call arguments
        call_args = mock_engagement.record_touch_point.call_args
        assert call_args[0] == user_id  # user_id
        assert call_args[1] in ["sms", "email"]  # touch_type
        assert "metadata" in call_args[2]  # metadata dict
    
    def test_template_personalization(self, manager, sample_lead_data):
        """Test message template personalization"""
        template = manager.templates[IndustryType.REAL_ESTATE]["market_insights"]
        
        # Test personalization with available data
        personalization = {k: sample_lead_data.get(k, f"{{{k}}}") for k in template["personalization_fields"]}
        
        expected_personalization = {
            "first_name": "John",
            "target_area": "Miami",
            "market_data": "{{market_data}}"
        }
        
        assert personalization["first_name"] == expected_personalization["first_name"]
        assert personalization["location"] == expected_personalization["target_area"]
    
    def test_compliance_requirements(self, manager):
        """Test compliance requirements are properly set"""
        # Check that all templates have compliance requirements
        for industry_templates in manager.templates.values():
            for template in industry_templates.values():
                assert "compliance_required" in template
                assert isinstance(template["compliance_required"], bool)
    
    def test_error_handling_redis_unavailable(self, sample_lead_data):
        """Test error handling when Redis is unavailable"""
        with patch('automation.nurture_sequences.redis_client', None):
            manager = NurtureSequenceManager()
            
            result = manager.schedule_nurture_sequence(
                sample_lead_data["user_id"], 
                0.8, 
                "real_estate", 
                sample_lead_data
            )
            
            assert result is False
    
    def test_error_handling_invalid_industry(self, manager, sample_lead_data):
        """Test error handling for invalid industry type"""
        result = manager.schedule_nurture_sequence(
            sample_lead_data["user_id"], 
            0.8, 
            "invalid_industry", 
            sample_lead_data
        )
        
        assert result is False
    
    def test_circuit_breaker_integration(self, manager, sample_lead_data):
        """Test circuit breaker is properly integrated"""
        user_id = sample_lead_data["user_id"]
        
        # Configure circuit breaker to fail
        manager.circuit_breaker.call.side_effect = Exception("Redis circuit open")
        
        result = manager.schedule_nurture_sequence(user_id, 0.8, "real_estate", sample_lead_data)
        
        assert result is False

class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @pytest.fixture
    def mock_manager(self):
        """Mock nurture sequence manager"""
        with patch('automation.nurture_sequences.nurture_sequence_manager') as mock:
            mock.schedule_nurture_sequence.return_value = True
            mock.get_next_touch_point.return_value = {"day": 1, "channel": "sms"}
            mock.cancel_nurture_sequence.return_value = True
            mock.update_sequence_progress.return_value = True
            yield mock
    
    def test_schedule_nurture_sequence_function(self, mock_manager):
        """Test schedule_nurture_sequence convenience function"""
        result = schedule_nurture_sequence("user123", 0.8, "real_estate", {})
        
        assert result is True
        mock_manager.schedule_nurture_sequence.assert_called_once_with("user123", 0.8, "real_estate", {})
    
    def test_get_next_touch_point_function(self, mock_manager):
        """Test get_next_touch_point convenience function"""
        result = get_next_touch_point("user123")
        
        assert result == {"day": 1, "channel": "sms"}
        mock_manager.get_next_touch_point.assert_called_once_with("user123")
    
    def test_cancel_nurture_sequence_function(self, mock_manager):
        """Test cancel_nurture_sequence convenience function"""
        result = cancel_nurture_sequence("user123")
        
        assert result is True
        mock_manager.cancel_nurture_sequence.assert_called_once_with("user123")
    
    def test_update_sequence_progress_function(self, mock_manager):
        """Test update_sequence_progress convenience function"""
        result = update_sequence_progress("user123", True)
        
        assert result is True
        mock_manager.update_sequence_progress.assert_called_once_with("user123", True)

class TestLangGraphIntegration:
    """Test LangGraph workflow integration"""
    
    @pytest.fixture
    def mock_langgraph_available(self):
        """Mock LangGraph as available"""
        with patch('automation.nurture_sequences.LANGGRAPH_AVAILABLE', True):
            with patch('automation.nurture_sequences.MemorySaver') as mock_saver:
                mock_saver.return_value = Mock()
                yield
    
    def test_langgraph_workflow_creation(self, mock_langgraph_available):
        """Test LangGraph workflow creation"""
        from automation.nurture_sequences import NurtureSequenceManager
        
        manager = NurtureSequenceManager()
        sequence = manager.sequences[IndustryType.REAL_ESTATE]["high_intent"]
        lead_data = {"user_id": "test123", "first_name": "John"}
        
        workflow = manager._create_sequence_workflow(sequence, lead_data)
        
        assert workflow is not None
        # The workflow should be a callable (LangGraph compiled workflow)
        assert callable(workflow)
    
    def test_langgraph_unavailable_fallback(self, sample_lead_data):
        """Test fallback behavior when LangGraph is unavailable"""
        with patch('automation.nurture_sequences.LANGGRAPH_AVAILABLE', False):
            manager = NurtureSequenceManager()
            
            result = manager.schedule_nurture_sequence(
                sample_lead_data["user_id"], 
                0.8, 
                "real_estate", 
                sample_lead_data
            )
            
            assert result is True
            # Should use fallback scheduling
            sequence_key = manager.SEQUENCE_KEY.format(user_id=sample_lead_data["user_id"])
            assert manager.redis_client.setex.called

class TestTouchPointDataStructure:
    """Test TouchPoint data structure and validation"""
    
    def test_touch_point_creation(self):
        """Test TouchPoint dataclass creation"""
        touch_point = TouchPoint(
            day=1,
            channel=ChannelType.SMS,
            template_key="market_insights",
            content="Test content",
            personalization_data={"name": "John"},
            compliance_checked=True
        )
        
        assert touch_point.day == 1
        assert touch_point.channel == ChannelType.SMS
        assert touch_point.template_key == "market_insights"
        assert touch_point.content == "Test content"
        assert touch_point.personalization_data == {"name": "John"}
        assert touch_point.compliance_checked is True
    
    def test_nurture_sequence_creation(self):
        """Test NurtureSequence dataclass creation"""
        touch_points = [
            TouchPoint(1, ChannelType.SMS, "test"),
            TouchPoint(3, ChannelType.EMAIL, "test")
        ]
        
        sequence = NurtureSequence(
            industry_type=IndustryType.REAL_ESTATE,
            intent_threshold=0.6,
            touch_points=touch_points,
            total_duration_days=10,
            ab_test_enabled=True
        )
        
        assert sequence.industry_type == IndustryType.REAL_ESTATE
        assert sequence.intent_threshold == 0.6
        assert len(sequence.touch_points) == 2
        assert sequence.total_duration_days == 10
        assert sequence.ab_test_enabled is True

class TestIndustrySpecificLogic:
    """Test industry-specific business logic"""
    
    def test_real_estate_intent_thresholds(self):
        """Test real estate intent thresholds"""
        manager = NurtureSequenceManager()
        
        assert manager._get_intent_threshold(IndustryType.REAL_ESTATE) == 0.6
        assert manager._get_intent_threshold(IndustryType.FITNESS) == 0.5
        assert manager._get_intent_threshold(IndustryType.RESTAURANT) == 0.55
    
    def test_sequence_duration_validation(self):
        """Test sequence duration validation"""
        manager = NurtureSequenceManager()
        
        # Real estate high intent should be 21 days
        real_estate_high = manager.sequences[IndustryType.REAL_ESTATE]["high_intent"]
        assert real_estate_high.total_duration_days == 21
        
        # Real estate low intent should be 10 days
        real_estate_low = manager.sequences[IndustryType.REAL_ESTATE]["low_intent"]
        assert real_estate_low.total_duration_days == 10
        
        # Fitness high intent should be 10 days
        fitness_high = manager.sequences[IndustryType.FITNESS]["high_intent"]
        assert fitness_high.total_duration_days == 10
        
        # Restaurant high intent should be 14 days
        restaurant_high = manager.sequences[IndustryType.RESTAURANT]["high_intent"]
        assert restaurant_high.total_duration_days == 14

if __name__ == "__main__":
    pytest.main([__file__])