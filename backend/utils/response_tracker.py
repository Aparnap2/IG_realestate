"""
Response Time Tracking System for Lead Qualification Scoring

Implements industry-standard response time tracking to improve conversion rates:
- Tracks first contact time for each user ID
- Calculates urgency score based on 5-minute response window standard
- Stores data in Redis with appropriate TTL
- Provides methods to track response time and calculate urgency scores

Industry Standards:
- Response ≤ 5 minutes: Score 1.0 (Excellent - meets industry standard)
- Response ≤ 15 minutes: Score 0.8 (Good)
- Response ≤ 60 minutes: Score 0.6 (Acceptable)
- Response ≤ 4 hours: Score 0.4 (Poor)
- Response > 4 hours: Score 0.2 (Very poor - qualification drops 10x)
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging

from .redis_client import redis_client, redis_circuit_breaker

logger = logging.getLogger(__name__)


class ResponseTimeTracker:
    """
    Tracks response times for lead qualification and calculates urgency scores.
    
    This system implements industry-standard response time tracking to help
    improve conversion rates by prioritizing leads based on response urgency.
    """
    
    # Response time thresholds (in minutes) and corresponding scores
    RESPONSE_THRESHOLDS = [
        (5, 1.0),    # 5 minutes - Excellent (industry standard)
        (15, 0.8),   # 15 minutes - Good
        (60, 0.6),   # 1 hour - Acceptable
        (240, 0.4),  # 4 hours - Poor
        (float('inf'), 0.2)  # > 4 hours - Very poor (qualification drops 10x)
    ]
    
    # Redis key patterns
    FIRST_CONTACT_KEY = "response:first_contact:{user_id}"
    RESPONSE_TRACKING_KEY = "response:tracking:{user_id}"
    
    # TTL settings (in seconds)
    FIRST_CONTACT_TTL = 86400 * 7  # 7 days - keep first contact for a week
    RESPONSE_TRACKING_TTL = 86400 * 30  # 30 days - keep tracking data for a month
    
    def __init__(self):
        """Initialize the response time tracker."""
        self._validate_redis_connection()
    
    def _validate_redis_connection(self):
        """Validate Redis connection is available."""
        if redis_client is None:
            logger.warning("Redis client not available - response tracking will be disabled")
            return False
        
        try:
            # Test connection with circuit breaker
            def _test_connection():
                redis_client.ping()
                return True
            
            redis_circuit_breaker.call(_test_connection)
            return True
            
        except Exception as e:
            logger.warning(f"Redis connection test failed: {e} - response tracking will be disabled")
            return False
    
    def track_first_response(self, user_id: str, message_timestamp: datetime) -> bool:
        """
        Record the first contact time for a user.
        
        Args:
            user_id: Unique identifier for the user/lead
            message_timestamp: Timestamp of the first message/contact
            
        Returns:
            True if successfully tracked, False otherwise
        """
        if redis_client is None:
            logger.debug("Redis unavailable - cannot track first response")
            return False
        
        if not user_id or not message_timestamp:
            logger.warning("Invalid parameters for track_first_response")
            return False
        
        def _track_first_contact():
            # Check if first contact already exists
            first_contact_key = self.FIRST_CONTACT_KEY.format(user_id=user_id)
            existing_contact = redis_client.get(first_contact_key)
            
            if existing_contact:
                logger.debug(f"First contact already tracked for user {user_id}")
                return True
            
            # Store first contact timestamp
            contact_data = {
                'user_id': user_id,
                'first_contact_timestamp': message_timestamp.isoformat(),
                'tracked_at': datetime.now().isoformat()
            }
            
            # Store with TTL
            redis_client.setex(
                first_contact_key,
                self.FIRST_CONTACT_TTL,
                json.dumps(contact_data, default=str)
            )
            
            # Also store in tracking data structure
            tracking_key = self.RESPONSE_TRACKING_KEY.format(user_id=user_id)
            tracking_data = {
                'user_id': user_id,
                'first_contact_timestamp': message_timestamp.isoformat(),
                'response_timestamp': None,
                'response_time_minutes': None,
                'urgency_score': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            redis_client.setex(
                tracking_key,
                self.RESPONSE_TRACKING_TTL,
                json.dumps(tracking_data, default=str)
            )
            
            logger.info(f"First contact tracked for user {user_id} at {message_timestamp.isoformat()}")
            return True
        
        try:
            return redis_circuit_breaker.call(_track_first_contact)
        except Exception as e:
            logger.error(f"Error tracking first response for user {user_id}: {e}")
            return False
    
    def calculate_urgency_score(self, user_id: str) -> float:
        """
        Calculate the urgency score based on response time.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Urgency score between 0.0 and 1.0
        """
        response_time = self.get_response_time_minutes(user_id)
        
        if response_time is None:
            # No response time available - assume high urgency for new leads
            return 1.0
        
        # Find appropriate score based on response time
        for threshold_minutes, score in self.RESPONSE_THRESHOLDS:
            if response_time <= threshold_minutes:
                return score
        
        # Should not reach here, but return minimum score as fallback
        return 0.2
    
    def get_response_time_minutes(self, user_id: str) -> Optional[float]:
        """
        Get the response time in minutes for a user.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Response time in minutes, or None if not available
        """
        if redis_client is None:
            logger.debug("Redis unavailable - cannot get response time")
            return None
        
        def _get_response_time():
            tracking_key = self.RESPONSE_TRACKING_KEY.format(user_id=user_id)
            tracking_data = redis_client.get(tracking_key)
            
            if not tracking_data:
                # Try to get first contact and calculate response time
                return self._calculate_response_time_from_first_contact(user_id)
            
            try:
                data = json.loads(tracking_data)
                response_time = data.get('response_time_minutes')
                
                if response_time is not None:
                    return float(response_time)
                
                # If response time not calculated yet, try to calculate it
                return self._calculate_response_time_from_first_contact(user_id)
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error parsing tracking data for user {user_id}: {e}")
                return None
        
        try:
            return redis_circuit_breaker.call(_get_response_time)
        except Exception as e:
            logger.error(f"Error getting response time for user {user_id}: {e}")
            return None
    
    def _calculate_response_time_from_first_contact(self, user_id: str) -> Optional[float]:
        """
        Calculate response time from first contact timestamp.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Response time in minutes, or None if not available
        """
        def _calculate():
            first_contact_key = self.FIRST_CONTACT_KEY.format(user_id=user_id)
            first_contact_data = redis_client.get(first_contact_key)
            
            if not first_contact_data:
                return None
            
            try:
                data = json.loads(first_contact_data)
                first_contact_timestamp = datetime.fromisoformat(
                    data['first_contact_timestamp']
                )
                
                # Calculate response time (time since first contact)
                now = datetime.now()
                response_time = (now - first_contact_timestamp).total_seconds() / 60.0
                
                # Update tracking data with calculated response time
                tracking_key = self.RESPONSE_TRACKING_KEY.format(user_id=user_id)
                tracking_data = {
                    'user_id': user_id,
                    'first_contact_timestamp': first_contact_timestamp.isoformat(),
                    'response_timestamp': now.isoformat(),
                    'response_time_minutes': response_time,
                    'urgency_score': self._calculate_score_from_time(response_time),
                    'updated_at': now.isoformat()
                }
                
                redis_client.setex(
                    tracking_key,
                    self.RESPONSE_TRACKING_TTL,
                    json.dumps(tracking_data, default=str)
                )
                
                return response_time
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"Error parsing first contact data for user {user_id}: {e}")
                return None
        
        try:
            return redis_circuit_breaker.call(_calculate)
        except Exception as e:
            logger.error(f"Error calculating response time for user {user_id}: {e}")
            return None
    
    def _calculate_score_from_time(self, response_time_minutes: float) -> float:
        """
        Calculate urgency score from response time.
        
        Args:
            response_time_minutes: Response time in minutes
            
        Returns:
            Urgency score between 0.0 and 1.0
        """
        for threshold_minutes, score in self.RESPONSE_THRESHOLDS:
            if response_time_minutes <= threshold_minutes:
                return score
        
        return 0.2
    
    def get_tracking_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete tracking data for a user.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Tracking data dictionary, or None if not available
        """
        if redis_client is None:
            logger.debug("Redis unavailable - cannot get tracking data")
            return None
        
        def _get_tracking_data():
            tracking_key = self.RESPONSE_TRACKING_KEY.format(user_id=user_id)
            tracking_data = redis_client.get(tracking_key)
            
            if not tracking_data:
                return None
            
            try:
                return json.loads(tracking_data)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing tracking data for user {user_id}: {e}")
                return None
        
        try:
            return redis_circuit_breaker.call(_get_tracking_data)
        except Exception as e:
            logger.error(f"Error getting tracking data for user {user_id}: {e}")
            return None
    
    def update_response_timestamp(self, user_id: str, response_timestamp: datetime) -> bool:
        """
        Update the response timestamp for a user.
        
        Args:
            user_id: Unique identifier for the user/lead
            response_timestamp: Timestamp of the response
            
        Returns:
            True if successfully updated, False otherwise
        """
        if redis_client is None:
            logger.debug("Redis unavailable - cannot update response timestamp")
            return False
        
        def _update_response():
            tracking_key = self.RESPONSE_TRACKING_KEY.format(user_id=user_id)
            tracking_data = redis_client.get(tracking_key)
            
            if not tracking_data:
                logger.warning(f"No tracking data found for user {user_id}")
                return False
            
            try:
                data = json.loads(tracking_data)
                first_contact_timestamp = datetime.fromisoformat(
                    data['first_contact_timestamp']
                )
                
                # Calculate response time
                response_time = (response_timestamp - first_contact_timestamp).total_seconds() / 60.0
                
                # Update tracking data
                updated_data = {
                    **data,
                    'response_timestamp': response_timestamp.isoformat(),
                    'response_time_minutes': response_time,
                    'urgency_score': self._calculate_score_from_time(response_time),
                    'updated_at': datetime.now().isoformat()
                }
                
                redis_client.setex(
                    tracking_key,
                    self.RESPONSE_TRACKING_TTL,
                    json.dumps(updated_data, default=str)
                )
                
                logger.info(f"Response timestamp updated for user {user_id}: {response_time:.2f} minutes")
                return True
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"Error updating response timestamp for user {user_id}: {e}")
                return False
        
        try:
            return redis_circuit_breaker.call(_update_response)
        except Exception as e:
            logger.error(f"Error updating response timestamp for user {user_id}: {e}")
            return False
    
    def get_urgency_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive urgency statistics for a user.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Dictionary with urgency statistics
        """
        response_time = self.get_response_time_minutes(user_id)
        urgency_score = self.calculate_urgency_score(user_id)
        tracking_data = self.get_tracking_data(user_id)
        
        # Determine urgency category
        if response_time is None:
            category = "new_lead"
            description = "New lead - no response time data"
        elif response_time <= 5:
            category = "excellent"
            description = "Excellent response time (≤ 5 minutes)"
        elif response_time <= 15:
            category = "good"
            description = "Good response time (≤ 15 minutes)"
        elif response_time <= 60:
            category = "acceptable"
            description = "Acceptable response time (≤ 1 hour)"
        elif response_time <= 240:
            category = "poor"
            description = "Poor response time (≤ 4 hours)"
        else:
            category = "very_poor"
            description = "Very poor response time (> 4 hours)"
        
        return {
            'user_id': user_id,
            'response_time_minutes': response_time,
            'urgency_score': urgency_score,
            'urgency_category': category,
            'category_description': description,
            'tracking_data': tracking_data,
            'industry_standard_met': response_time is not None and response_time <= 5,
            'qualification_impact_factor': 1.0 if urgency_score >= 0.6 else 0.1,  # 10x drop for poor response
            'stats_timestamp': datetime.now().isoformat()
        }


# Global tracker instance
response_tracker = ResponseTimeTracker()


def track_first_response(user_id: str, message_timestamp: datetime) -> bool:
    """
    Convenience function to track first response time.
    
    Args:
        user_id: Unique identifier for the user/lead
        message_timestamp: Timestamp of the first message/contact
        
    Returns:
        True if successfully tracked, False otherwise
    """
    return response_tracker.track_first_response(user_id, message_timestamp)


def calculate_urgency_score(user_id: str) -> float:
    """
    Convenience function to calculate urgency score.
    
    Args:
        user_id: Unique identifier for the user/lead
        
    Returns:
        Urgency score between 0.0 and 1.0
    """
    return response_tracker.calculate_urgency_score(user_id)


def get_response_time_minutes(user_id: str) -> Optional[float]:
    """
    Convenience function to get response time in minutes.
    
    Args:
        user_id: Unique identifier for the user/lead
        
    Returns:
        Response time in minutes, or None if not available
    """
    return response_tracker.get_response_time_minutes(user_id)


def get_urgency_stats(user_id: str) -> Dict[str, Any]:
    """
    Convenience function to get comprehensive urgency statistics.
    
    Args:
        user_id: Unique identifier for the user/lead
        
    Returns:
        Dictionary with urgency statistics
    """
    return response_tracker.get_urgency_stats(user_id)