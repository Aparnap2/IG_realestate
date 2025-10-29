"""
Comprehensive unit tests for the engagement tracker system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import redis

from backend.utils.engagement_tracker import (
    EngagementTracker, 
    TouchPoint, 
    INDUSTRY_TOUCH_REQUIREMENTS,
    TOUCH_TYPE_WEIGHTS,
    RECENCY_WEIGHTS,
    engagement_tracker
)

class TestEngagementTracker:
    """Test suite for EngagementTracker class"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        return mock_client
    
    @pytest.fixture
    def mock_circuit_breaker(self):
        """Mock circuit breaker for testing"""
        mock_cb = Mock()
        mock_cb.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
        return mock_cb
    
    @pytest.fixture
    def tracker(self, mock_redis_client, mock_circuit_breaker):
        """Create EngagementTracker instance with mocked dependencies"""
        with patch('backend.utils.engagement_tracker.redis_client', mock_redis_client), \
             patch('backend.utils.engagement_tracker.redis_circuit_breaker', mock_circuit_breaker):
            return EngagementTracker()
    
    def test_init(self):
        """Test EngagementTracker initialization"""
        with patch('backend.utils.engagement_tracker.redis_client', Mock()), \
             patch('backend.utils.engagement_tracker.redis_circuit_breaker', Mock()):
            tracker = EngagementTracker()
            
            assert tracker.TOUCH_POINTS_KEY == "engagement:touch_points:{user_id}"
            assert tracker.TOUCH_COUNT_KEY == "engagement:touch_count:{user_id}:{touch_type}"
            assert tracker.MOMENTUM_KEY == "engagement:momentum:{user_id}"
            assert tracker.CONVERSION_PREDICTION_KEY == "engagement:conversion_prediction:{user_id}"
            assert tracker.TOUCH_POINTS_TTL == 2592000
            assert tracker.MOMENTUM_TTL == 86400
            assert tracker.PREDICTION_TTL == 3600
    
    def test_record_touch_point_success(self, tracker, mock_redis_client):
        """Test successful touch point recording"""
        user_id = "test_user_123"
        touch_type = "email"
        content = "Follow-up email about property listing"
        metadata = {"property_id": "prop_456", "stage": "consideration"}
        
        # Mock Redis operations
        mock_redis_client.zadd.return_value = 1
        mock_redis_client.expire.return_value = True
        mock_redis_client.incr.return_value = 1
        mock_redis_client.delete.return_value = 1
        
        result = tracker.record_touch_point(user_id, touch_type, content, metadata)
        
        assert result is True
        mock_redis_client.zadd.assert_called_once()
        mock_redis_client.expire.assert_called()
        mock_redis_client.incr.assert_called_once()
        mock_redis_client.delete.assert_called()
    
    def test_record_touch_point_invalid_type(self, tracker, mock_redis_client):
        """Test recording touch point with invalid type"""
        user_id = "test_user_123"
        touch_type = "invalid_type"
        content = "Test content"
        
        mock_redis_client.zadd.return_value = 1
        mock_redis_client.expire.return_value = True
        mock_redis_client.incr.return_value = 1
        mock_redis_client.delete.return_value = 1
        
        result = tracker.record_touch_point(user_id, touch_type, content)
        
        assert result is True
        # Should default to "text" type
        expected_key = tracker.TOUCH_COUNT_KEY.format(user_id=user_id, touch_type="text")
        mock_redis_client.incr.assert_called_with(expected_key)
    
    def test_record_touch_point_redis_unavailable(self, tracker):
        """Test recording touch point when Redis is unavailable"""
        tracker.redis_client = None
        
        result = tracker.record_touch_point("user123", "email", "test")
        
        assert result is False
    
    def test_record_touch_point_circuit_breaker_open(self, tracker, mock_circuit_breaker):
        """Test recording touch point when circuit breaker is open"""
        mock_circuit_breaker.call.side_effect = redis.ConnectionError("Circuit breaker open")
        
        result = tracker.record_touch_point("user123", "email", "test")
        
        assert result is False
    
    def test_get_touch_count_success(self, tracker, mock_redis_client):
        """Test successful touch count retrieval"""
        user_id = "test_user_123"
        days = 30
        
        mock_redis_client.zcount.return_value = 15
        
        result = tracker.get_touch_count(user_id, days)
        
        assert result == 15
        mock_redis_client.zcount.assert_called_once()
    
    def test_get_touch_count_no_touches(self, tracker, mock_redis_client):
        """Test touch count when no touches exist"""
        user_id = "test_user_123"
        
        mock_redis_client.zcount.return_value = 0
        
        result = tracker.get_touch_count(user_id)
        
        assert result == 0
    
    def test_get_touch_count_redis_unavailable(self, tracker):
        """Test touch count when Redis is unavailable"""
        tracker.redis_client = None
        
        result = tracker.get_touch_count("user123")
        
        assert result == 0
    
    def test_calculate_engagement_momentum_cached(self, tracker, mock_redis_client):
        """Test momentum calculation with cached value"""
        user_id = "test_user_123"
        cached_momentum = "0.75"
        
        mock_redis_client.get.return_value = cached_momentum
        
        result = tracker.calculate_engagement_momentum(user_id)
        
        assert result == 0.75
        mock_redis_client.get.assert_called_once()
        mock_redis_client.zrangebyscore.assert_not_called()
    
    def test_calculate_engagement_momentum_no_touches(self, tracker, mock_redis_client):
        """Test momentum calculation with no touch points"""
        user_id = "test_user_123"
        
        mock_redis_client.get.return_value = None  # No cache
        mock_redis_client.zrangebyscore.return_value = []  # No touches
        
        result = tracker.calculate_engagement_momentum(user_id)
        
        assert result == 0.0
        mock_redis_client.setex.assert_called_once()
    
    def test_calculate_engagement_momentum_with_touches(self, tracker, mock_redis_client):
        """Test momentum calculation with touch points"""
        user_id = "test_user_123"
        
        # Create sample touch points
        now = datetime.utcnow()
        touch_points = [
            {
                "user_id": user_id,
                "touch_type": "email",
                "content": "Follow-up email",
                "timestamp": now.isoformat(),
                "metadata": {"stage": "consideration"},
                "response_received": True,
                "response_time_seconds": 3600
            },
            {
                "user_id": user_id,
                "touch_type": "call",
                "content": "Phone call",
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "metadata": {"stage": "qualification"},
                "response_received": False,
                "response_time_seconds": None
            }
        ]
        
        mock_redis_client.get.return_value = None  # No cache
        mock_redis_client.zrangebyscore.return_value = [
            (json.dumps(touch_points[0]), now.timestamp()),
            (json.dumps(touch_points[1]), (now - timedelta(days=1)).timestamp())
        ]
        
        result = tracker.calculate_engagement_momentum(user_id)
        
        assert 0.0 <= result <= 1.0
        mock_redis_client.setex.assert_called_once()
    
    def test_should_convert_soon_cached(self, tracker, mock_redis_client):
        """Test conversion prediction with cached value"""
        user_id = "test_user_123"
        industry_type = "real_estate"
        
        mock_redis_client.get.return_value = "true"
        
        result = tracker.should_convert_soon(user_id, industry_type)
        
        assert result is True
        mock_redis_client.get.assert_called_once()
    
    def test_should_convert_soon_meets_requirements(self, tracker, mock_redis_client):
        """Test conversion prediction when requirements are met"""
        user_id = "test_user_123"
        industry_type = "real_estate"
        
        # Mock dependencies
        mock_redis_client.get.return_value = None  # No cache
        tracker.get_touch_count = Mock(return_value=10)  # Above requirement (8)
        tracker.calculate_engagement_momentum = Mock(return_value=0.8)  # High momentum
        
        # Mock touch data for diversity calculation
        touch_data = [
            json.dumps({"touch_type": "email"}),
            json.dumps({"touch_type": "call"}),
            json.dumps({"touch_type": "property_view"}),
            json.dumps({"touch_type": "text"})
        ]
        mock_redis_client.zrangebyscore.return_value = touch_data
        
        result = tracker.should_convert_soon(user_id, industry_type)
        
        assert result is True
        mock_redis_client.setex.assert_called_once()
    
    def test_should_convert_soon_insufficient_touches(self, tracker, mock_redis_client):
        """Test conversion prediction with insufficient touches"""
        user_id = "test_user_123"
        industry_type = "real_estate"
        
        mock_redis_client.get.return_value = None  # No cache
        tracker.get_touch_count = Mock(return_value=3)  # Below requirement (8)
        tracker.calculate_engagement_momentum = Mock(return_value=0.8)
        
        result = tracker.should_convert_soon(user_id, industry_type)
        
        assert result is False
    
    def test_get_touch_history_success(self, tracker, mock_redis_client):
        """Test successful touch history retrieval"""
        user_id = "test_user_123"
        limit = 10
        
        # Create sample touch data
        touch_data = [
            json.dumps({
                "user_id": user_id,
                "touch_type": "email",
                "content": "Test email",
                "timestamp": datetime.utcnow().isoformat()
            }),
            json.dumps({
                "user_id": user_id,
                "touch_type": "call",
                "content": "Test call",
                "timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat()
            })
        ]
        
        mock_redis_client.zrevrange.return_value = touch_data
        
        result = tracker.get_touch_history(user_id, limit)
        
        assert len(result) == 2
        assert result[0]["touch_type"] == "email"
        assert result[1]["touch_type"] == "call"
        mock_redis_client.zrevrange.assert_called_once()
    
    def test_get_touch_history_empty(self, tracker, mock_redis_client):
        """Test touch history retrieval with no data"""
        user_id = "test_user_123"
        
        mock_redis_client.zrevrange.return_value = []
        
        result = tracker.get_touch_history(user_id)
        
        assert result == []
    
    def test_mark_response_received_success(self, tracker, mock_redis_client):
        """Test successful response marking"""
        user_id = "test_user_123"
        touch_timestamp = datetime.utcnow()
        response_time_seconds = 3600
        
        # Create original touch data
        original_touch = {
            "user_id": user_id,
            "touch_type": "email",
            "content": "Test email",
            "timestamp": touch_timestamp.isoformat(),
            "response_received": False,
            "response_time_seconds": None
        }
        
        mock_redis_client.zrangebyscore.return_value = [json.dumps(original_touch)]
        mock_redis_client.zremrangebyscore.return_value = 1
        mock_redis_client.zadd.return_value = 1
        mock_redis_client.delete.return_value = 1
        
        result = tracker.mark_response_received(user_id, touch_timestamp, response_time_seconds)
        
        assert result is True
        mock_redis_client.zremrangebyscore.assert_called_once()
        mock_redis_client.zadd.assert_called_once()
    
    def test_mark_response_received_touch_not_found(self, tracker, mock_redis_client):
        """Test response marking when touch is not found"""
        user_id = "test_user_123"
        touch_timestamp = datetime.utcnow()
        response_time_seconds = 3600
        
        mock_redis_client.zrangebyscore.return_value = []
        
        result = tracker.mark_response_received(user_id, touch_timestamp, response_time_seconds)
        
        assert result is False
    
    def test_get_engagement_summary(self, tracker):
        """Test engagement summary generation"""
        user_id = "test_user_123"
        
        # Mock all the dependent methods
        tracker.get_touch_count = Mock(side_effect=lambda user_id, days=30 if days == 30 else 5)
        tracker.calculate_engagement_momentum = Mock(return_value=0.75)
        tracker.get_touch_history = Mock(return_value=[
            {"touch_type": "email", "content": "Test email"}
        ])
        tracker.should_convert_soon = Mock(return_value=True)
        
        # Mock Redis for touch type breakdown
        with patch.object(tracker, 'redis_client') as mock_redis:
            mock_redis.get.return_value = "5"  # Touch count for each type
            
            result = tracker.get_engagement_summary(user_id)
            
            assert result["user_id"] == user_id
            assert result["total_touches_30_days"] == 30
            assert result["recent_touches_7_days"] == 5
            assert result["engagement_momentum"] == 0.75
            assert "touch_type_breakdown" in result
            assert "recent_touch_history" in result
            assert "conversion_predictions" in result
            assert "last_updated" in result
    
    def test_calculate_recency_score(self, tracker):
        """Test recency score calculation"""
        now = datetime.utcnow()
        
        # Test with recent touches
        recent_touches = [
            {"touch_type": "email", "timestamp": now.isoformat()},
            {"touch_type": "call", "timestamp": (now - timedelta(days=1)).isoformat()}
        ]
        
        score = tracker._calculate_recency_score(recent_touches)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high for recent touches
        
        # Test with old touches
        old_touches = [
            {"touch_type": "email", "timestamp": (now - timedelta(days=20)).isoformat()}
        ]
        
        old_score = tracker._calculate_recency_score(old_touches)
        assert old_score < score  # Should be lower for old touches
    
    def test_calculate_frequency_score(self, tracker):
        """Test frequency score calculation"""
        now = datetime.utcnow()
        
        # Test with consistent engagement
        consistent_touches = []
        for i in range(10):
            consistent_touches.append({
                "touch_type": "email",
                "timestamp": (now - timedelta(days=i)).isoformat()
            })
        
        score = tracker._calculate_frequency_score(consistent_touches)
        assert 0.0 <= score <= 1.0
        
        # Test with inconsistent engagement
        inconsistent_touches = [
            {"touch_type": "email", "timestamp": now.isoformat()},
            {"touch_type": "email", "timestamp": (now - timedelta(days=20)).isoformat()}
        ]
        
        inconsistent_score = tracker._calculate_frequency_score(inconsistent_touches)
        assert inconsistent_score < score
    
    def test_calculate_diversity_score(self, tracker):
        """Test diversity score calculation"""
        # Test with diverse touch types
        diverse_touches = [
            {"touch_type": "email"},
            {"touch_type": "call"},
            {"touch_type": "property_view"},
            {"touch_type": "text"}
        ]
        
        score = tracker._calculate_diversity_score(diverse_touches)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high for diverse touches
        
        # Test with single touch type
        single_type_touches = [
            {"touch_type": "email"},
            {"touch_type": "email"},
            {"touch_type": "email"}
        ]
        
        single_score = tracker._calculate_diversity_score(single_type_touches)
        assert single_score < score
    
    def test_calculate_progression_score(self, tracker):
        """Test progression score calculation"""
        # Test with progression through stages
        progression_touches = [
            {"metadata": {"stage": "initial_contact"}},
            {"metadata": {"stage": "qualification"}},
            {"metadata": {"stage": "consideration"}},
            {"metadata": {"stage": "intent"}}
        ]
        
        score = tracker._calculate_progression_score(progression_touches)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high for progressing touches
        
        # Test with no progression
        no_progression_touches = [
            {"metadata": {"stage": "initial_contact"}},
            {"metadata": {"stage": "initial_contact"}}
        ]
        
        no_progression_score = tracker._calculate_progression_score(no_progression_touches)
        assert no_progression_score < score
    
    def test_calculate_response_score(self, tracker):
        """Test response score calculation"""
        # Test with good response rate
        good_response_touches = [
            {"response_received": True, "response_time_seconds": 3600},
            {"response_received": True, "response_time_seconds": 1800},
            {"response_received": False, "response_time_seconds": None}
        ]
        
        score = tracker._calculate_response_score(good_response_touches)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high for good responses
        
        # Test with poor response rate
        poor_response_touches = [
            {"response_received": False, "response_time_seconds": None},
            {"response_received": False, "response_time_seconds": None},
            {"response_received": False, "response_time_seconds": None}
        ]
        
        poor_score = tracker._calculate_response_score(poor_response_touches)
        assert poor_score < score
    
    def test_industry_touch_requirements(self):
        """Test industry-specific touch requirements"""
        assert INDUSTRY_TOUCH_REQUIREMENTS["real_estate"] == 8
        assert INDUSTRY_TOUCH_REQUIREMENTS["fitness"] == 6
        assert INDUSTRY_TOUCH_REQUIREMENTS["restaurant"] == 7
        assert INDUSTRY_TOUCH_REQUIREMENTS["hotel"] == 10
        assert INDUSTRY_TOUCH_REQUIREMENTS["default"] == 8
    
    def test_touch_type_weights(self):
        """Test touch type weights"""
        assert TOUCH_TYPE_WEIGHTS["call"] > TOUCH_TYPE_WEIGHTS["email"]
        assert TOUCH_TYPE_WEIGHTS["booking_attempt"] > TOUCH_TYPE_WEIGHTS["text"]
        assert TOUCH_TYPE_WEIGHTS["website_visit"] < TOUCH_TYPE_WEIGHTS["property_view"]
    
    def test_recency_weights(self):
        """Test recency weight structure"""
        assert RECENCY_WEIGHTS[0] > RECENCY_WEIGHTS[1]
        assert RECENCY_WEIGHTS[1] > RECENCY_WEIGHTS[7]
        assert RECENCY_WEIGHTS[7] > RECENCY_WEIGHTS[30]
    
    def test_global_engagement_tracker_instance(self):
        """Test that global engagement tracker instance is available"""
        assert engagement_tracker is not None
        assert isinstance(engagement_tracker, EngagementTracker)

class TestTouchPoint:
    """Test suite for TouchPoint dataclass"""
    
    def test_touch_point_creation(self):
        """Test TouchPoint creation"""
        timestamp = datetime.utcnow()
        metadata = {"property_id": "prop_123"}
        
        touch_point = TouchPoint(
            user_id="user123",
            touch_type="email",
            content="Test email",
            timestamp=timestamp,
            metadata=metadata,
            response_received=True,
            response_time_seconds=3600
        )
        
        assert touch_point.user_id == "user123"
        assert touch_point.touch_type == "email"
        assert touch_point.content == "Test email"
        assert touch_point.timestamp == timestamp
        assert touch_point.metadata == metadata
        assert touch_point.response_received is True
        assert touch_point.response_time_seconds == 3600
    
    def test_touch_point_defaults(self):
        """Test TouchPoint with default values"""
        timestamp = datetime.utcnow()
        
        touch_point = TouchPoint(
            user_id="user123",
            touch_type="text",
            content="Test text",
            timestamp=timestamp
        )
        
        assert touch_point.metadata is None
        assert touch_point.response_received is False
        assert touch_point.response_time_seconds is None

if __name__ == "__main__":
    pytest.main([__file__])