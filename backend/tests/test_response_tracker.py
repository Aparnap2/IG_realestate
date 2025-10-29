"""
Tests for Response Time Tracking System

Tests the response time tracking functionality including:
- First contact tracking
- Response time calculation
- Urgency score calculation
- Redis integration
- Error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

from utils.response_tracker import (
    ResponseTimeTracker,
    response_tracker,
    track_first_response,
    calculate_urgency_score,
    get_response_time_minutes,
    get_urgency_stats
)


class TestResponseTimeTracker:
    """Test cases for ResponseTimeTracker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ResponseTimeTracker()
        self.test_user_id = "test_user_123"
        self.test_timestamp = datetime.now()
    
    def test_init(self):
        """Test tracker initialization."""
        assert self.tracker is not None
        assert hasattr(self.tracker, 'RESPONSE_THRESHOLDS')
        assert len(self.tracker.RESPONSE_THRESHOLDS) == 5
    
    def test_response_thresholds(self):
        """Test response time thresholds are correctly defined."""
        thresholds = self.tracker.RESPONSE_THRESHOLDS
        
        # Check threshold values and scores
        assert thresholds[0] == (5, 1.0)    # 5 minutes - Excellent
        assert thresholds[1] == (15, 0.8)   # 15 minutes - Good
        assert thresholds[2] == (60, 0.6)   # 1 hour - Acceptable
        assert thresholds[3] == (240, 0.4)  # 4 hours - Poor
        assert thresholds[4] == (float('inf'), 0.2)  # > 4 hours - Very poor
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_track_first_response_success(self, mock_circuit_breaker, mock_redis):
        """Test successful first response tracking."""
        # Mock Redis operations
        mock_redis.get.return_value = None  # No existing contact
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking first response
        result = self.tracker.track_first_response(self.test_user_id, self.test_timestamp)
        
        assert result is True
        assert mock_redis.setex.call_count == 2  # Should set both first contact and tracking keys
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_track_first_response_existing_contact(self, mock_circuit_breaker, mock_redis):
        """Test tracking first response when contact already exists."""
        # Mock existing contact
        mock_redis.get.return_value = json.dumps({
            'user_id': self.test_user_id,
            'first_contact_timestamp': self.test_timestamp.isoformat()
        })
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking first response
        result = self.tracker.track_first_response(self.test_user_id, self.test_timestamp)
        
        assert result is True
        assert mock_redis.setex.call_count == 0  # Should not set if already exists
    
    @patch('utils.response_tracker.redis_client', None)
    def test_track_first_response_no_redis(self):
        """Test tracking first response when Redis is unavailable."""
        result = self.tracker.track_first_response(self.test_user_id, self.test_timestamp)
        assert result is False
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_calculate_urgency_score_new_lead(self, mock_circuit_breaker, mock_redis):
        """Test urgency score calculation for new lead."""
        # Mock no response time available
        mock_redis.get.return_value = None
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test urgency score for new lead
        score = self.tracker.calculate_urgency_score(self.test_user_id)
        
        assert score == 1.0  # New leads get highest urgency
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_calculate_urgency_score_excellent_response(self, mock_circuit_breaker, mock_redis):
        """Test urgency score calculation for excellent response time."""
        # Mock 3-minute response time
        mock_redis.get.return_value = json.dumps({
            'response_time_minutes': 3.0
        })
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test urgency score
        score = self.tracker.calculate_urgency_score(self.test_user_id)
        
        assert score == 1.0  # Excellent response time
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_calculate_urgency_score_poor_response(self, mock_circuit_breaker, mock_redis):
        """Test urgency score calculation for poor response time."""
        # Mock 3-hour response time
        mock_redis.get.return_value = json.dumps({
            'response_time_minutes': 180.0
        })
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test urgency score
        score = self.tracker.calculate_urgency_score(self.test_user_id)
        
        assert score == 0.4  # Poor response time
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_response_time_minutes_available(self, mock_circuit_breaker, mock_redis):
        """Test getting response time when available."""
        # Mock response time data
        mock_redis.get.return_value = json.dumps({
            'response_time_minutes': 15.5
        })
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting response time
        response_time = self.tracker.get_response_time_minutes(self.test_user_id)
        
        assert response_time == 15.5
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_response_time_minutes_calculate_from_first_contact(self, mock_circuit_breaker, mock_redis):
        """Test getting response time calculated from first contact."""
        # Mock first contact data (10 minutes ago)
        first_contact_time = datetime.now() - timedelta(minutes=10)
        mock_redis.get.side_effect = [
            None,  # No tracking data
            json.dumps({  # First contact data
                'user_id': self.test_user_id,
                'first_contact_timestamp': first_contact_time.isoformat()
            })
        ]
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting response time
        response_time = self.tracker.get_response_time_minutes(self.test_user_id)
        
        assert response_time is not None
        assert response_time >= 10.0  # Should be at least 10 minutes
    
    @patch('utils.response_tracker.redis_client', None)
    def test_get_response_time_minutes_no_redis(self):
        """Test getting response time when Redis is unavailable."""
        response_time = self.tracker.get_response_time_minutes(self.test_user_id)
        assert response_time is None
    
    def test_calculate_score_from_time(self):
        """Test score calculation from response time."""
        # Test various response times
        assert self.tracker._calculate_score_from_time(3) == 1.0    # Excellent
        assert self.tracker._calculate_score_from_time(10) == 0.8   # Good
        assert self.tracker._calculate_score_from_time(30) == 0.6   # Acceptable
        assert self.tracker._calculate_score_from_time(120) == 0.4  # Poor
        assert self.tracker._calculate_score_from_time(300) == 0.2  # Very poor
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_tracking_data(self, mock_circuit_breaker, mock_redis):
        """Test getting complete tracking data."""
        # Mock tracking data
        tracking_data = {
            'user_id': self.test_user_id,
            'first_contact_timestamp': self.test_timestamp.isoformat(),
            'response_time_minutes': 15.5,
            'urgency_score': 0.8
        }
        mock_redis.get.return_value = json.dumps(tracking_data)
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting tracking data
        result = self.tracker.get_tracking_data(self.test_user_id)
        
        assert result is not None
        assert result['user_id'] == self.test_user_id
        assert result['response_time_minutes'] == 15.5
        assert result['urgency_score'] == 0.8
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_update_response_timestamp(self, mock_circuit_breaker, mock_redis):
        """Test updating response timestamp."""
        # Mock existing tracking data
        first_contact_time = self.test_timestamp - timedelta(minutes=10)
        tracking_data = {
            'user_id': self.test_user_id,
            'first_contact_timestamp': first_contact_time.isoformat(),
            'response_timestamp': None,
            'response_time_minutes': None,
            'urgency_score': None
        }
        mock_redis.get.return_value = json.dumps(tracking_data)
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test updating response timestamp
        response_time = self.test_timestamp
        result = self.tracker.update_response_timestamp(self.test_user_id, response_time)
        
        assert result is True
        assert mock_redis.setex.called
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_urgency_stats_new_lead(self, mock_circuit_breaker, mock_redis):
        """Test getting urgency stats for new lead."""
        # Mock no tracking data
        mock_redis.get.return_value = None
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting urgency stats
        stats = self.tracker.get_urgency_stats(self.test_user_id)
        
        assert stats is not None
        assert stats['user_id'] == self.test_user_id
        assert stats['response_time_minutes'] is None
        assert stats['urgency_score'] == 1.0
        assert stats['urgency_category'] == 'new_lead'
        assert stats['industry_standard_met'] is False
        assert stats['qualification_impact_factor'] == 1.0
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_urgency_stats_excellent_response(self, mock_circuit_breaker, mock_redis):
        """Test getting urgency stats for excellent response time."""
        # Mock tracking data with 3-minute response
        tracking_data = {
            'user_id': self.test_user_id,
            'response_time_minutes': 3.0,
            'urgency_score': 1.0
        }
        mock_redis.get.return_value = json.dumps(tracking_data)
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting urgency stats
        stats = self.tracker.get_urgency_stats(self.test_user_id)
        
        assert stats is not None
        assert stats['response_time_minutes'] == 3.0
        assert stats['urgency_score'] == 1.0
        assert stats['urgency_category'] == 'excellent'
        assert stats['industry_standard_met'] is True
        assert stats['qualification_impact_factor'] == 1.0
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_get_urgency_stats_poor_response(self, mock_circuit_breaker, mock_redis):
        """Test getting urgency stats for poor response time."""
        # Mock tracking data with 3-hour response
        tracking_data = {
            'user_id': self.test_user_id,
            'response_time_minutes': 180.0,
            'urgency_score': 0.4
        }
        mock_redis.get.return_value = json.dumps(tracking_data)
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test getting urgency stats
        stats = self.tracker.get_urgency_stats(self.test_user_id)
        
        assert stats is not None
        assert stats['response_time_minutes'] == 180.0
        assert stats['urgency_score'] == 0.4
        assert stats['urgency_category'] == 'poor'
        assert stats['industry_standard_met'] is False
        assert stats['qualification_impact_factor'] == 0.1  # 10x drop


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    @patch('utils.response_tracker.response_tracker')
    def test_track_first_response_convenience(self, mock_tracker):
        """Test track_first_response convenience function."""
        mock_tracker.track_first_response.return_value = True
        
        result = track_first_response("test_user", datetime.now())
        
        assert result is True
        mock_tracker.track_first_response.assert_called_once()
    
    @patch('utils.response_tracker.response_tracker')
    def test_calculate_urgency_score_convenience(self, mock_tracker):
        """Test calculate_urgency_score convenience function."""
        mock_tracker.calculate_urgency_score.return_value = 0.8
        
        result = calculate_urgency_score("test_user")
        
        assert result == 0.8
        mock_tracker.calculate_urgency_score.assert_called_once_with("test_user")
    
    @patch('utils.response_tracker.response_tracker')
    def test_get_response_time_minutes_convenience(self, mock_tracker):
        """Test get_response_time_minutes convenience function."""
        mock_tracker.get_response_time_minutes.return_value = 15.5
        
        result = get_response_time_minutes("test_user")
        
        assert result == 15.5
        mock_tracker.get_response_time_minutes.assert_called_once_with("test_user")
    
    @patch('utils.response_tracker.response_tracker')
    def test_get_urgency_stats_convenience(self, mock_tracker):
        """Test get_urgency_stats convenience function."""
        mock_stats = {'user_id': 'test_user', 'urgency_score': 0.8}
        mock_tracker.get_urgency_stats.return_value = mock_stats
        
        result = get_urgency_stats("test_user")
        
        assert result == mock_stats
        mock_tracker.get_urgency_stats.assert_called_once_with("test_user")


class TestIntegration:
    """Integration tests for response time tracking."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        # Use a real tracker instance for integration tests
        self.tracker = ResponseTimeTracker()
        self.test_user_id = "integration_test_user"
    
    @patch('utils.response_tracker.redis_client')
    @patch('utils.response_tracker.redis_circuit_breaker')
    def test_full_tracking_workflow(self, mock_circuit_breaker, mock_redis):
        """Test complete tracking workflow from first contact to urgency calculation."""
        # Mock Redis operations - initially no tracking data (new lead)
        tracking_data = None
        first_contact_data = None
        
        def mock_get(key):
            if 'response:tracking:' in key:
                return tracking_data
            elif 'response:first_contact:' in key:
                return first_contact_data
            return None
        
        mock_redis.get.side_effect = mock_get
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Step 1: Track first contact
        first_contact_time = datetime.now() - timedelta(minutes=3)
        result = self.tracker.track_first_response(self.test_user_id, first_contact_time)
        assert result is True
        
        # Update mock data to reflect what was stored
        first_contact_data = json.dumps({
            'user_id': self.test_user_id,
            'first_contact_timestamp': first_contact_time.isoformat(),
            'tracked_at': datetime.now().isoformat()
        })
        tracking_data = json.dumps({
            'user_id': self.test_user_id,
            'first_contact_timestamp': first_contact_time.isoformat(),
            'response_timestamp': None,
            'response_time_minutes': None,
            'urgency_score': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        
        # Step 2: Calculate urgency score (should be high for new lead)
        score = self.tracker.calculate_urgency_score(self.test_user_id)
        assert score == 1.0
        
        # Step 3: Update response timestamp (simulate response after 3 minutes - excellent)
        response_time = datetime.now()
        result = self.tracker.update_response_timestamp(self.test_user_id, response_time)
        assert result is True
        
        # Step 4: Get final urgency stats
        stats = self.tracker.get_urgency_stats(self.test_user_id)
        assert stats is not None
        assert stats['urgency_category'] == 'excellent'
        assert stats['industry_standard_met'] is True


if __name__ == "__main__":
    pytest.main([__file__])