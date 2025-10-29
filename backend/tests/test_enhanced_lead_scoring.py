"""
Test suite for Enhanced Lead Scoring System

Tests the integration of ResponseTimeTracker with industry-adaptive scoring
and verifies the enhanced scoring formula works correctly.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from backend.utils.lead_scoring import LeadScoringSystem, calculate_enhanced_lead_score
from backend.utils.response_tracker import ResponseTimeTracker


class TestEnhancedLeadScoring:
    """Test cases for enhanced lead scoring functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = LeadScoringSystem()
        
        # Sample lead data
        self.sample_lead_data = {
            'budget': 350000,
            'location': 'Downtown Austin, TX',
            'timeline': '3-6 months',
            'property_type': 'condo',
            'desired_bedrooms': 2,
            'email': 'test@example.com',
            'name': 'Test User',
            'message': 'Looking for a 2-bedroom condo in downtown Austin with budget around $350k'
        }
        
        # Sample conversation history
        self.sample_conversation_history = [
            {
                'role': 'user',
                'message': 'Hi, I\'m looking for a property',
                'timestamp': (datetime.now() - timedelta(hours=2)).isoformat()
            },
            {
                'role': 'assistant',
                'message': 'I can help you find a property',
                'timestamp': (datetime.now() - timedelta(hours=1, minutes=50)).isoformat()
            },
            {
                'role': 'user',
                'message': 'I need a 2-bedroom condo in downtown Austin',
                'timestamp': (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]
        
        # Sample touch points
        self.sample_touch_points = [
            {
                'type': 'email_open',
                'timestamp': (datetime.now() - timedelta(days=1)).isoformat(),
                'details': 'Opened property listing email'
            },
            {
                'type': 'website_visit',
                'timestamp': (datetime.now() - timedelta(days=2)).isoformat(),
                'details': 'Visited property details page'
            },
            {
                'type': 'form_submit',
                'timestamp': (datetime.now() - timedelta(days=3)).isoformat(),
                'details': 'Submitted contact form'
            }
        ]
    
    def test_industry_configurations(self):
        """Test that industry configurations are properly defined."""
        expected_industries = ['real_estate', 'fitness', 'restaurant', 'hotel']
        
        for industry in expected_industries:
            assert industry in self.scorer.INDUSTRY_CONFIGS
            config = self.scorer.INDUSTRY_CONFIGS[industry]
            
            # Verify required fields exist
            assert 'conversion_threshold' in config
            assert 'nurture_threshold' in config
            assert 'required_touches' in config
            assert 'industry_multiplier' in config
            assert 'description' in config
            
            # Verify thresholds are realistic (not academic 0.75)
            assert config['conversion_threshold'] <= 0.65
            assert config['conversion_threshold'] >= 0.5
            assert config['nurture_threshold'] <= 0.4
            assert config['nurture_threshold'] >= 0.3
    
    def test_real_estate_scoring(self):
        """Test enhanced scoring for real estate industry."""
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_123',
            industry_type='real_estate',
            **self.sample_lead_data,
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points
        )
        
        # Verify result structure
        assert 'enhanced_score' in result
        assert 'base_score' in result
        assert 'urgency_score' in result
        assert 'engagement_momentum_score' in result
        assert 'industry_type' in result
        assert 'industry_config' in result
        assert 'routing_recommendation' in result
        assert 'qualification_stage' in result
        assert 'improvement_potential' in result
        
        # Verify industry-specific values
        assert result['industry_type'] == 'real_estate'
        assert result['industry_config']['conversion_threshold'] == 0.6
        assert result['industry_config']['nurture_threshold'] == 0.35
        assert result['industry_config']['industry_multiplier'] == 1.0
        
        # Verify score ranges
        assert 0 <= result['enhanced_score'] <= 1.0
        assert 0 <= result['base_score'] <= 1.0
        assert 0 <= result['urgency_score'] <= 1.0
        assert 0 <= result['engagement_momentum_score'] <= 1.0
    
    def test_fitness_industry_scoring(self):
        """Test enhanced scoring for fitness industry."""
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_456',
            industry_type='fitness',
            **self.sample_lead_data,
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points
        )
        
        # Verify fitness-specific configuration
        assert result['industry_type'] == 'fitness'
        assert result['industry_config']['conversion_threshold'] == 0.5
        assert result['industry_config']['nurture_threshold'] == 0.3
        assert result['industry_config']['industry_multiplier'] == 0.9
        assert result['industry_config']['required_touches'] == 6
    
    def test_restaurant_industry_scoring(self):
        """Test enhanced scoring for restaurant industry."""
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_789',
            industry_type='restaurant',
            **self.sample_lead_data,
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points
        )
        
        # Verify restaurant-specific configuration
        assert result['industry_type'] == 'restaurant'
        assert result['industry_config']['conversion_threshold'] == 0.55
        assert result['industry_config']['nurture_threshold'] == 0.35
        assert result['industry_config']['industry_multiplier'] == 0.85
        assert result['industry_config']['required_touches'] == 7
    
    def test_hotel_industry_scoring(self):
        """Test enhanced scoring for hotel industry."""
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_999',
            industry_type='hotel',
            **self.sample_lead_data,
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points
        )
        
        # Verify hotel-specific configuration
        assert result['industry_type'] == 'hotel'
        assert result['industry_config']['conversion_threshold'] == 0.65
        assert result['industry_config']['nurture_threshold'] == 0.4
        assert result['industry_config']['industry_multiplier'] == 1.1
        assert result['industry_config']['required_touches'] == 10
    
    def test_unknown_industry_fallback(self):
        """Test fallback to real_estate for unknown industry types."""
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_fallback',
            industry_type='unknown_industry',
            **self.sample_lead_data
        )
        
        # Should fallback to real_estate
        assert result['industry_type'] == 'real_estate'
        assert result['industry_config']['conversion_threshold'] == 0.6
    
    @patch('backend.utils.lead_scoring.ResponseTimeTracker')
    def test_urgency_score_integration(self, mock_tracker_class):
        """Test integration with ResponseTimeTracker for urgency scoring."""
        # Mock the response tracker
        mock_tracker = Mock()
        mock_tracker.calculate_urgency_score.return_value = 0.8
        mock_tracker_class.return_value = mock_tracker
        
        # Create new scorer to use mocked tracker
        scorer = LeadScoringSystem()
        
        result = scorer.calculate_enhanced_lead_score(
            user_id='test_user_urgency',
            industry_type='real_estate',
            **self.sample_lead_data
        )
        
        # Verify urgency score was calculated
        mock_tracker.calculate_urgency_score.assert_called_once_with('test_user_urgency')
        assert result['urgency_score'] == 0.8
    
    def test_engagement_momentum_calculation(self):
        """Test engagement momentum calculation with various inputs."""
        # Test with no conversation history or touch points
        result = self.scorer._calculate_engagement_momentum(
            conversation_history=None,
            touch_points=None,
            previous_score=None
        )
        assert 0 <= result <= 1.0
        
        # Test with conversation history only
        result = self.scorer._calculate_engagement_momentum(
            conversation_history=self.sample_conversation_history,
            touch_points=None,
            previous_score=None
        )
        assert 0 <= result <= 1.0
        
        # Test with touch points only
        result = self.scorer._calculate_engagement_momentum(
            conversation_history=None,
            touch_points=self.sample_touch_points,
            previous_score=None
        )
        assert 0 <= result <= 1.0
        
        # Test with both conversation history and touch points
        result = self.scorer._calculate_engagement_momentum(
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points,
            previous_score=0.4
        )
        assert 0 <= result <= 1.0
    
    def test_enhanced_scoring_formula(self):
        """Test the enhanced scoring formula calculation."""
        base_score = 0.7
        urgency_score = 0.8
        engagement_momentum_score = 0.6
        industry_multiplier = 1.0
        
        result = self.scorer._calculate_enhanced_score(
            base_score, urgency_score, engagement_momentum_score, industry_multiplier
        )
        
        expected = (base_score * 0.6 + urgency_score * 0.2 + engagement_momentum_score * 0.2) * industry_multiplier
        assert abs(result - expected) < 0.001
        assert result <= 1.0
    
    def test_industry_specific_routing(self):
        """Test routing recommendations use industry-specific thresholds."""
        # Test high score for different industries
        high_score_result = self.scorer._determine_enhanced_routing(
            0.7,  # High score
            self.scorer.INDUSTRY_CONFIGS['real_estate']
        )
        assert high_score_result['next_agent'] == 'scheduler'
        
        # Test medium score
        medium_score_result = self.scorer._determine_enhanced_routing(
            0.5,  # Medium score
            self.scorer.INDUSTRY_CONFIGS['fitness']
        )
        assert medium_score_result['next_agent'] == 'followup'
        
        # Test low score
        low_score_result = self.scorer._determine_enhanced_routing(
            0.2,  # Low score
            self.scorer.INDUSTRY_CONFIGS['hotel']
        )
        assert low_score_result['next_agent'] == 'offramp'
    
    def test_improvement_potential_calculation(self):
        """Test improvement potential calculation."""
        base_score = 0.5
        urgency_score = 0.6
        engagement_momentum_score = 0.4
        industry_config = self.scorer.INDUSTRY_CONFIGS['real_estate']
        
        result = self.scorer._calculate_improvement_potential(
            base_score, urgency_score, engagement_momentum_score, industry_config
        )
        
        # Verify structure
        assert 'potential' in result
        assert 'focus_areas' in result
        assert 'target_score' in result
        assert 'current_gap' in result
        
        # Verify values
        assert result['target_score'] == industry_config['conversion_threshold']
        assert isinstance(result['potential'], (int, float))
        assert isinstance(result['focus_areas'], list)
    
    def test_backward_compatibility(self):
        """Test that original calculate_lead_score still works."""
        # Test original function
        original_result = self.scorer.calculate_lead_score(**self.sample_lead_data)
        
        # Verify original structure is maintained
        assert 'final_score' in original_result
        assert 'score_breakdown' in original_result
        assert 'routing_recommendation' in original_result
        assert 'qualification_stage' in original_result
        assert 'scoring_timestamp' in original_result
        
        # Verify original thresholds are used
        assert original_result['thresholds']['scheduler_threshold'] == 0.75
        assert original_result['thresholds']['followup_threshold'] == 0.4
    
    def test_convenience_function(self):
        """Test the convenience function for enhanced scoring."""
        result = calculate_enhanced_lead_score(
            self.sample_lead_data,
            user_id='test_user_convenience',
            industry_type='real_estate',
            conversation_history=self.sample_conversation_history,
            touch_points=self.sample_touch_points
        )
        
        # Verify result structure
        assert 'enhanced_score' in result
        assert 'industry_type' in result
        assert result['industry_type'] == 'real_estate'
    
    def test_error_handling(self):
        """Test error handling in enhanced scoring."""
        # Test with invalid data that might cause errors
        result = self.scorer.calculate_enhanced_lead_score(
            user_id='test_user_error',
            industry_type='real_estate',
            budget='invalid_budget',  # Invalid type
            location=None,
            timeline=None,
            property_type=None,
            email='invalid_email',  # Invalid email
            name=None,
            message=None
        )
        
        # Should return safe default on error
        assert 'enhanced_score' in result
        assert 'error' in result
        assert 0 <= result['enhanced_score'] <= 1.0
    
    def test_touch_point_recency_check(self):
        """Test the touch point recency checking logic."""
        # Recent touch point (within 7 days)
        recent_touch = {
            'type': 'email_open',
            'timestamp': (datetime.now() - timedelta(days=3)).isoformat()
        }
        assert self.scorer._is_recent_touch(recent_touch) == True
        
        # Old touch point (more than 7 days)
        old_touch = {
            'type': 'website_visit',
            'timestamp': (datetime.now() - timedelta(days=10)).isoformat()
        }
        assert self.scorer._is_recent_touch(old_touch) == False
        
        # Touch point without timestamp
        no_timestamp_touch = {
            'type': 'form_submit'
        }
        assert self.scorer._is_recent_touch(no_timestamp_touch) == False
        
        # Touch point with invalid timestamp
        invalid_touch = {
            'type': 'phone_call',
            'timestamp': 'invalid-date'
        }
        assert self.scorer._is_recent_touch(invalid_touch) == False


if __name__ == '__main__':
    pytest.main([__file__])