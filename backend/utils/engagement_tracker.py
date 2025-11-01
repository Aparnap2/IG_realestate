"""
Comprehensive touch point tracking system for conversion prediction.
Tracks every interaction and calculates engagement momentum for enhanced lead scoring.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import redis
from .redis_client import redis_client, redis_circuit_breaker, retry_redis_operation

logger = logging.getLogger(__name__)

# Industry-specific touch requirements for conversion
INDUSTRY_TOUCH_REQUIREMENTS = {
    "real_estate": 8,
    "fitness": 6,
    "restaurant": 7,
    "hotel": 10,
    "default": 8
}

# Touch point types with their weights for engagement calculation
TOUCH_TYPE_WEIGHTS = {
    "text": 1.0,
    "email": 0.8,
    "call": 1.5,
    "property_view": 1.2,
    "website_visit": 0.6,
    "social_engagement": 0.7,
    "booking_attempt": 1.8,
    "form_submission": 1.3
}

# Recency decay factors (days ago -> weight multiplier)
RECENCY_WEIGHTS = {
    0: 1.0,    # Today
    1: 0.9,    # Yesterday
    2: 0.8,    # 2 days ago
    3: 0.7,    # 3 days ago
    7: 0.5,    # Week ago
    14: 0.3,   # 2 weeks ago
    30: 0.1    # Month ago
}

@dataclass
class TouchPoint:
    """Represents a single touch point interaction"""
    user_id: str
    touch_type: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    response_received: bool = False
    response_time_seconds: Optional[int] = None

class EngagementTracker:
    """
    Comprehensive touch point tracking system for conversion prediction.
    
    Tracks every interaction, calculates engagement momentum, and predicts
    conversion readiness based on industry-standard touch requirements.
    """
    
    def __init__(self):
        self.redis_client = redis_client
        self.circuit_breaker = redis_circuit_breaker
        
        # Redis key patterns
        self.TOUCH_POINTS_KEY = "engagement:touch_points:{user_id}"
        self.TOUCH_COUNT_KEY = "engagement:touch_count:{user_id}:{touch_type}"
        self.MOMENTUM_KEY = "engagement:momentum:{user_id}"
        self.CONVERSION_PREDICTION_KEY = "engagement:conversion_prediction:{user_id}"
        
        # TTL settings (in seconds)
        self.TOUCH_POINTS_TTL = 2592000  # 30 days
        self.MOMENTUM_TTL = 86400  # 24 hours
        self.PREDICTION_TTL = 3600  # 1 hour
    
    def record_touch_point(self, user_id: str, touch_type: str, content: str, 
                          metadata: Dict[str, Any] = None) -> bool:
        """
        Record a touch point interaction for a user.
        
        Args:
            user_id: Unique user identifier
            touch_type: Type of touch (text, email, call, etc.)
            content: Content/description of the interaction
            metadata: Additional context data
            
        Returns:
            True if successfully recorded, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot record touch point")
            return False
        
        # Validate touch type
        if touch_type not in TOUCH_TYPE_WEIGHTS:
            logger.warning(f"Unknown touch type '{touch_type}' for user {user_id}")
            touch_type = "text"  # Default to text
        
        # Create touch point
        touch_point = TouchPoint(
            user_id=user_id,
            touch_type=touch_type,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        def _record_operation():
            # Store touch point in sorted list by timestamp
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            touch_data = json.dumps(asdict(touch_point), default=str)
            
            # Use timestamp as score for sorted set
            timestamp_score = touch_point.timestamp.timestamp()
            
            # Add to sorted set
            self.redis_client.zadd(touch_key, {touch_data: timestamp_score})
            
            # Set TTL
            self.redis_client.expire(touch_key, self.TOUCH_POINTS_TTL)
            
            # Increment touch type counter
            count_key = self.TOUCH_COUNT_KEY.format(user_id=user_id, touch_type=touch_type)
            self.redis_client.incr(count_key)
            self.redis_client.expire(count_key, self.TOUCH_POINTS_TTL)
            
            # Invalidate cached momentum and prediction
            self.redis_client.delete(self.MOMENTUM_KEY.format(user_id=user_id))
            self.redis_client.delete(self.CONVERSION_PREDICTION_KEY.format(user_id=user_id))
            
            logger.info(f"Recorded {touch_type} touch point for user {user_id}")
            return True
        
        try:
            return self.circuit_breaker.call(_record_operation)
        except Exception as e:
            logger.error(f"Failed to record touch point for user {user_id}: {e}")
            return False
    
    def get_touch_count(self, user_id: str, days: int = 30) -> int:
        """
        Get the number of touch points for a user within a timeframe.
        
        Args:
            user_id: Unique user identifier
            days: Number of days to look back
            
        Returns:
            Number of touch points in the timeframe
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot get touch count")
            return 0
        
        def _count_operation():
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            
            # Calculate timestamp cutoff
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            cutoff_score = cutoff_time.timestamp()
            
            # Count touch points since cutoff
            count = self.redis_client.zcount(touch_key, cutoff_score, "+inf")
            return int(count) if count else 0
        
        try:
            return self.circuit_breaker.call(_count_operation)
        except Exception as e:
            logger.error(f"Failed to get touch count for user {user_id}: {e}")
            return 0
    
    def calculate_engagement_momentum(self, user_id: str) -> float:
        """
        Calculate engagement momentum score (0-1) based on multiple factors.
        
        Factors considered:
        - Recency: More recent touches weighted higher
        - Frequency: Consistent engagement over time
        - Diversity: Multiple types of interactions
        - Progression: Moving through qualification stages
        - Response Rate: User responsiveness to outreach
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Engagement momentum score between 0 and 1
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot calculate momentum")
            return 0.0
        
        # Check cache first
        cache_key = self.MOMENTUM_KEY.format(user_id=user_id)
        
        def _calculate_operation():
            # Try to get cached value
            cached_momentum = self.redis_client.get(cache_key)
            if cached_momentum:
                return float(cached_momentum)
            
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            
            # Get all touch points from last 30 days
            cutoff_time = datetime.utcnow() - timedelta(days=30)
            cutoff_score = cutoff_time.timestamp()
            
            touch_data = self.redis_client.zrangebyscore(
                touch_key, cutoff_score, "+inf", withscores=True
            )
            
            if not touch_data:
                momentum = 0.0
                self.redis_client.setex(cache_key, self.MOMENTUM_TTL, momentum)
                return momentum
            
            # Parse touch points
            touch_points = []
            for data, score in touch_data:
                try:
                    touch_dict = json.loads(data)
                    touch_points.append(touch_dict)
                except json.JSONDecodeError:
                    continue
            
            # Calculate momentum factors
            
            # 1. Recency Score (0-1)
            recency_score = self._calculate_recency_score(touch_points)
            
            # 2. Frequency Score (0-1)
            frequency_score = self._calculate_frequency_score(touch_points)
            
            # 3. Diversity Score (0-1)
            diversity_score = self._calculate_diversity_score(touch_points)
            
            # 4. Progression Score (0-1)
            progression_score = self._calculate_progression_score(touch_points)
            
            # 5. Response Rate Score (0-1)
            response_score = self._calculate_response_score(touch_points)
            
            # Weighted combination
            momentum = (
                recency_score * 0.3 +
                frequency_score * 0.25 +
                diversity_score * 0.2 +
                progression_score * 0.15 +
                response_score * 0.1
            )
            
            # Cache the result
            self.redis_client.setex(cache_key, self.MOMENTUM_TTL, momentum)
            
            logger.info(f"Calculated engagement momentum {momentum:.3f} for user {user_id}")
            return momentum
        
        try:
            return self.circuit_breaker.call(_calculate_operation)
        except Exception as e:
            logger.error(f"Failed to calculate momentum for user {user_id}: {e}")
            return 0.0
    
    def should_convert_soon(self, user_id: str, industry_type: str) -> bool:
        """
        Predict if a user is ready to convert based on touch patterns.
        
        Args:
            user_id: Unique user identifier
            industry_type: Industry type for touch requirements
            
        Returns:
            True if user is likely to convert soon, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot predict conversion")
            return False
        
        # Check cache first
        cache_key = self.CONVERSION_PREDICTION_KEY.format(user_id=user_id)
        
        def _predict_operation():
            # Try to get cached prediction
            cached_prediction = self.redis_client.get(cache_key)
            if cached_prediction is not None:
                return cached_prediction.lower() == "true"
            
            # Get industry requirements
            required_touches = INDUSTRY_TOUCH_REQUIREMENTS.get(
                industry_type.lower(), 
                INDUSTRY_TOUCH_REQUIREMENTS["default"]
            )
            
            # Get touch count
            touch_count = self.get_touch_count(user_id, days=30)
            
            # Get engagement momentum
            momentum = self.calculate_engagement_momentum(user_id)
            
            # Get touch diversity
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            cutoff_time = datetime.utcnow() - timedelta(days=30)
            cutoff_score = cutoff_time.timestamp()
            
            touch_data = self.redis_client.zrangebyscore(
                touch_key, cutoff_score, "+inf"
            )
            
            # Count unique touch types
            touch_types = set()
            for data in touch_data:
                try:
                    touch_dict = json.loads(data)
                    touch_types.add(touch_dict.get("touch_type", "unknown"))
                except json.JSONDecodeError:
                    continue
            
            diversity_factor = len(touch_types) / len(TOUCH_TYPE_WEIGHTS)
            
            # Conversion prediction logic
            # 1. Minimum touch requirement
            meets_touch_requirement = touch_count >= required_touches
            
            # 2. High engagement momentum (>0.7)
            high_momentum = momentum > 0.7
            
            # 3. Good diversity (>=50% of touch types)
            good_diversity = diversity_factor >= 0.5
            
            # 4. Recent activity (at least one touch in last 7 days)
            recent_activity = self.get_touch_count(user_id, days=7) > 0
            
            # Predict conversion readiness
            should_convert = (
                meets_touch_requirement and
                high_momentum and
                good_diversity and
                recent_activity
            )
            
            # Cache the prediction
            self.redis_client.setex(
                cache_key, 
                self.PREDICTION_TTL, 
                str(should_convert).lower()
            )
            
            logger.info(
                f"Conversion prediction for user {user_id}: {should_convert} "
                f"(touches: {touch_count}/{required_touches}, "
                f"momentum: {momentum:.3f}, "
                f"diversity: {diversity_factor:.3f})"
            )
            
            return should_convert
        
        try:
            return self.circuit_breaker.call(_predict_operation)
        except Exception as e:
            logger.error(f"Failed to predict conversion for user {user_id}: {e}")
            return False
    
    def get_touch_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent touch point history for a user.
        
        Args:
            user_id: Unique user identifier
            limit: Maximum number of touch points to return
            
        Returns:
            List of touch point dictionaries ordered by most recent first
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot get touch history")
            return []
        
        def _history_operation():
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            
            # Get most recent touch points
            touch_data = self.redis_client.zrevrange(touch_key, 0, limit - 1)
            
            touch_points = []
            for data in touch_data:
                try:
                    touch_dict = json.loads(data)
                    touch_points.append(touch_dict)
                except json.JSONDecodeError:
                    continue
            
            return touch_points
        
        try:
            return self.circuit_breaker.call(_history_operation)
        except Exception as e:
            logger.error(f"Failed to get touch history for user {user_id}: {e}")
            return []
    
    def _calculate_recency_score(self, touch_points: List[Dict]) -> float:
        """Calculate recency score based on how recent touches are."""
        if not touch_points:
            return 0.0
        
        now = datetime.utcnow()
        total_weight = 0
        weighted_sum = 0
        
        for touch in touch_points:
            try:
                timestamp = datetime.fromisoformat(touch["timestamp"].replace('Z', '+00:00'))
                days_ago = (now - timestamp).days
                
                # Find appropriate recency weight
                recency_weight = 0.1  # Default for old touches
                for days, weight in RECENCY_WEIGHTS.items():
                    if days_ago <= days:
                        recency_weight = weight
                        break
                
                # Apply touch type weight
                type_weight = TOUCH_TYPE_WEIGHTS.get(touch["touch_type"], 1.0)
                combined_weight = recency_weight * type_weight
                
                weighted_sum += combined_weight
                total_weight += type_weight
                
            except (KeyError, ValueError):
                continue
        
        if total_weight == 0:
            return 0.0
        
        return min(weighted_sum / total_weight, 1.0)
    
    def _calculate_frequency_score(self, touch_points: List[Dict]) -> float:
        """Calculate frequency score based on consistency of engagement."""
        if not touch_points:
            return 0.0
        
        # Group touches by day
        daily_counts = {}
        for touch in touch_points:
            try:
                timestamp = datetime.fromisoformat(touch["timestamp"].replace('Z', '+00:00'))
                day = timestamp.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            except (KeyError, ValueError):
                continue
        
        if not daily_counts:
            return 0.0
        
        # Calculate consistency (days with touches / total days in range)
        date_range = max(daily_counts.keys()) - min(daily_counts.keys())
        total_days = max(date_range.days, 1)
        active_days = len(daily_counts)
        
        consistency = active_days / total_days
        
        # Calculate average touches per active day
        avg_touches = sum(daily_counts.values()) / active_days
        
        # Normalize average touches (cap at 3 per day)
        normalized_avg = min(avg_touches / 3.0, 1.0)
        
        # Combine consistency and frequency
        return (consistency * 0.6 + normalized_avg * 0.4)
    
    def _calculate_diversity_score(self, touch_points: List[Dict]) -> float:
        """Calculate diversity score based on variety of touch types."""
        if not touch_points:
            return 0.0
        
        # Count unique touch types
        touch_types = set()
        for touch in touch_points:
            touch_type = touch.get("touch_type", "unknown")
            if touch_type in TOUCH_TYPE_WEIGHTS:
                touch_types.add(touch_type)
        
        # Calculate diversity ratio
        diversity_ratio = len(touch_types) / len(TOUCH_TYPE_WEIGHTS)
        
        # Bonus for having at least 3 different types
        diversity_bonus = 0.2 if len(touch_types) >= 3 else 0.0
        
        return min(diversity_ratio + diversity_bonus, 1.0)
    
    def _calculate_progression_score(self, touch_points: List[Dict]) -> float:
        """Calculate progression score based on qualification stage movement."""
        if not touch_points:
            return 0.0
        
        # Define progression stages and their weights
        stage_weights = {
            "initial_contact": 0.2,
            "qualification": 0.4,
            "consideration": 0.6,
            "intent": 0.8,
            "decision": 1.0
        }
        
        # Extract progression from metadata
        progression_scores = []
        for touch in touch_points:
            metadata = touch.get("metadata", {})
            stage = metadata.get("stage", "initial_contact")
            weight = stage_weights.get(stage, 0.2)
            progression_scores.append(weight)
        
        if not progression_scores:
            return 0.0
        
        # Calculate trend (are we moving to higher stages?)
        if len(progression_scores) >= 2:
            recent_avg = sum(progression_scores[-3:]) / min(3, len(progression_scores))
            early_avg = sum(progression_scores[:3]) / min(3, len(progression_scores))
            trend_bonus = min((recent_avg - early_avg) * 0.5, 0.2)
        else:
            trend_bonus = 0.0
        
        # Base score is average of all stages
        base_score = sum(progression_scores) / len(progression_scores)
        
        return min(base_score + trend_bonus, 1.0)
    
    def _calculate_response_score(self, touch_points: List[Dict]) -> float:
        """Calculate response rate score based on user responsiveness."""
        if not touch_points:
            return 0.0
        
        # Count touches that received responses
        total_touches = 0
        responded_touches = 0
        
        for touch in touch_points:
            total_touches += 1
            if touch.get("response_received", False):
                responded_touches += 1
        
        if total_touches == 0:
            return 0.0
        
        # Calculate response rate
        response_rate = responded_touches / total_touches
        
        # Bonus for quick responses (under 24 hours)
        quick_response_bonus = 0
        for touch in touch_points:
            if touch.get("response_time_seconds"):
                response_hours = touch["response_time_seconds"] / 3600
                if response_hours < 24:
                    quick_response_bonus += 0.1
        
        quick_response_bonus = min(quick_response_bonus / total_touches, 0.2)
        
        return min(response_rate + quick_response_bonus, 1.0)
    
    def mark_response_received(self, user_id: str, touch_timestamp: datetime, 
                             response_time_seconds: int) -> bool:
        """
        Mark that a user responded to a touch point.
        
        Args:
            user_id: Unique user identifier
            touch_timestamp: Timestamp of the original touch
            response_time_seconds: Time taken to respond in seconds
            
        Returns:
            True if successfully updated, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot mark response")
            return False
        
        def _mark_response_operation():
            touch_key = self.TOUCH_POINTS_KEY.format(user_id=user_id)
            
            # Find the touch point by timestamp
            timestamp_score = touch_timestamp.timestamp()
            touch_data = self.redis_client.zrangebyscore(
                touch_key, timestamp_score, timestamp_score
            )
            
            if not touch_data:
                logger.warning(f"No touch point found for user {user_id} at timestamp {touch_timestamp}")
                return False
            
            # Update the touch point with response info
            try:
                touch_dict = json.loads(touch_data[0])
                touch_dict["response_received"] = True
                touch_dict["response_time_seconds"] = response_time_seconds
                
                # Remove old entry and add updated one
                self.redis_client.zremrangebyscore(touch_key, timestamp_score, timestamp_score)
                updated_data = json.dumps(touch_dict, default=str)
                self.redis_client.zadd(touch_key, {updated_data: timestamp_score})
                
                # Invalidate cached momentum
                self.redis_client.delete(self.MOMENTUM_KEY.format(user_id=user_id))
                
                logger.info(f"Marked response received for user {user_id}")
                return True
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse touch data for user {user_id}")
                return False
        
        try:
            return self.circuit_breaker.call(_mark_response_operation)
        except Exception as e:
            logger.error(f"Failed to mark response for user {user_id}: {e}")
            return False
    
    def get_engagement_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive engagement summary for a user.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Dictionary with engagement metrics and insights
        """
        try:
            # Get basic metrics
            total_touches = self.get_touch_count(user_id, days=30)
            recent_touches = self.get_touch_count(user_id, days=7)
            momentum = self.calculate_engagement_momentum(user_id)
            
            # Get touch type breakdown
            touch_types = {}
            for touch_type in TOUCH_TYPE_WEIGHTS.keys():
                count_key = self.TOUCH_COUNT_KEY.format(user_id=user_id, touch_type=touch_type)
                count = self.redis_client.get(count_key) if self.redis_client else 0
                touch_types[touch_type] = int(count) if count else 0
            
            # Get recent touch history
            recent_history = self.get_touch_history(user_id, limit=5)
            
            # Calculate conversion readiness for different industries
            conversion_predictions = {}
            for industry in INDUSTRY_TOUCH_REQUIREMENTS.keys():
                conversion_predictions[industry] = self.should_convert_soon(user_id, industry)
            
            return {
                "user_id": user_id,
                "total_touches_30_days": total_touches,
                "recent_touches_7_days": recent_touches,
                "engagement_momentum": momentum,
                "touch_type_breakdown": touch_types,
                "recent_touch_history": recent_history,
                "conversion_predictions": conversion_predictions,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get engagement summary for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }

# Global engagement tracker instance
engagement_tracker = EngagementTracker()