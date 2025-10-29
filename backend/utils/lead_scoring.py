"""
Lead Scoring System for Real Estate Qualification

Implements sophisticated lead scoring algorithm based on multiple factors:
- Budget clarity and amount
- Location specificity
- Timeline urgency
- Property type preferences
- Response completeness
- Engagement level

Supports progressive scoring through conversation flow.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re
import logging

from .response_tracker import ResponseTimeTracker

logger = logging.getLogger(__name__)

class LeadScoringSystem:
    """
    Advanced lead scoring system with industry-adaptive scoring and response time tracking.
    
    Enhanced scoring formula:
    enhanced_score = (
        base_score * 0.6 +           # Existing scoring 60%
        urgency_score * 0.2 +          # Response time 20%
        engagement_score * 0.2            # Engagement momentum 20%
    ) * industry_multiplier
    """
    
    # Industry-specific configurations with realistic thresholds
    INDUSTRY_CONFIGS = {
        'real_estate': {
            'conversion_threshold': 0.6,
            'nurture_threshold': 0.35,
            'required_touches': 8,
            'industry_multiplier': 1.0,
            'description': 'Real Estate - High value, longer sales cycle'
        },
        'fitness': {
            'conversion_threshold': 0.5,
            'nurture_threshold': 0.3,
            'required_touches': 6,
            'industry_multiplier': 0.9,
            'description': 'Fitness - Lower value, quicker decisions'
        },
        'restaurant': {
            'conversion_threshold': 0.55,
            'nurture_threshold': 0.35,
            'required_touches': 7,
            'industry_multiplier': 0.85,
            'description': 'Restaurant - Medium value, impulse decisions'
        },
        'hotel': {
            'conversion_threshold': 0.65,
            'nurture_threshold': 0.4,
            'required_touches': 10,
            'industry_multiplier': 1.1,
            'description': 'Hotel - High value, complex booking process'
        }
    }
    
    def __init__(self):
        # Initialize response time tracker
        self.response_tracker = ResponseTimeTracker()
        
        # Original scoring weights (for backward compatibility)
        self.scoring_weights = {
            'budget': 0.25,        # Budget clarity and amount
            'location': 0.20,       # Location specificity
            'timeline': 0.15,       # Timeline urgency
            'property_type': 0.10,   # Property preferences
            'completeness': 0.15,    # Information completeness
            'engagement': 0.15       # Engagement level
        }
        
        # Enhanced scoring weights
        self.enhanced_scoring_weights = {
            'base_score': 0.6,       # Existing scoring 60%
            'urgency_score': 0.2,    # Response time 20%
            'engagement_momentum': 0.2  # Engagement momentum 20%
        }
        
        self.budget_tiers = {
            'high': (500000, 1.0),      # $500k+
            'medium_high': (300000, 0.8), # $300k-$500k
            'medium': (150000, 0.6),     # $150k-$300k
            'low': (50000, 0.4),         # $50k-$150k
            'very_low': (0, 0.2)         # <$50k
        }
        
        self.timeline_urgency = {
            'immediate': (0, 1.0),        # 0-1 month
            'urgent': (1, 0.8),           # 1-3 months
            'normal': (3, 0.6),          # 3-6 months
            'relaxed': (6, 0.4),          # 6-12 months
            'future': (12, 0.2)           # 12+ months
        }
    
    def calculate_lead_score(
        self,
        budget: Optional[int] = None,
        location: Optional[str] = None,
        timeline: Optional[str] = None,
        property_type: Optional[str] = None,
        desired_bedrooms: Optional[int] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        message: Optional[str] = None,
        previous_score: Optional[float] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive lead score with detailed breakdown.
        
        Args:
            budget: Lead's budget in USD
            location: Desired location
            timeline: Purchase timeline
            property_type: Property type preference
            desired_bedrooms: Number of bedrooms desired
            email: Lead's email address
            name: Lead's name
            message: Original message content
            previous_score: Previous qualification score
            conversation_history: Previous conversation messages
            
        Returns:
            Dictionary with score, breakdown, and routing recommendation
        """
        try:
            # Initialize scoring components
            scores = {}
            
            # Budget scoring (0-1)
            scores['budget'] = self._score_budget(budget)
            
            # Location scoring (0-1)
            scores['location'] = self._score_location(location)
            
            # Timeline scoring (0-1)
            scores['timeline'] = self._score_timeline(timeline)
            
            # Property type scoring (0-1)
            scores['property_type'] = self._score_property_type(property_type, desired_bedrooms)
            
            # Information completeness scoring (0-1)
            scores['completeness'] = self._score_completeness(
                budget, location, timeline, property_type, email, name
            )
            
            # Engagement scoring (0-1)
            scores['engagement'] = self._score_engagement(
                message, conversation_history, previous_score
            )
            
            # Calculate weighted final score
            final_score = sum(
                scores[component] * self.scoring_weights[component]
                for component in self.scoring_weights
            )
            
            # Apply score delta calculation
            score_delta = None
            if previous_score is not None:
                try:
                    prev_score_float = float(previous_score)
                    score_delta = final_score - prev_score_float
                except (ValueError, TypeError):
                    score_delta = None
            
            # Determine routing recommendation
            routing = self._determine_routing(final_score)
            
            # Determine qualification stage
            qualification_stage = self._determine_qualification_stage(final_score)
            
            result = {
                'final_score': round(final_score, 3),
                'score_breakdown': scores,
                'score_delta': round(score_delta, 3) if score_delta is not None else None,
                'routing_recommendation': routing,
                'qualification_stage': qualification_stage,
                'scoring_timestamp': datetime.now().isoformat(),
                'thresholds': {
                    'scheduler_threshold': 0.75,
                    'followup_threshold': 0.4,
                    'offramp_threshold': 0.4
                }
            }
            
            logger.info(f"Lead score calculated: {final_score:.3f} -> {routing['next_agent']}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating lead score: {e}")
            # Return safe default on error
            return {
                'final_score': 0.5,
                'score_breakdown': {},
                'score_delta': None,
                'routing_recommendation': {'next_agent': 'followup', 'reasoning': 'Scoring error - default to followup'},
                'qualification_stage': 'needs_qualification',
                'scoring_timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _score_budget(self, budget: Optional[int]) -> float:
        """Score budget based on amount and clarity."""
        if not budget or budget <= 0:
            return 0.0  # No budget provided
        
        # Find appropriate tier
        for tier_name, (min_budget, score) in self.budget_tiers.items():
            if budget >= min_budget:
                return score
        
        return 0.1  # Below lowest tier
    
    def _score_location(self, location: Optional[str]) -> float:
        """Score location based on specificity."""
        if not location or not location.strip():
            return 0.0
        
        location = location.strip().lower()
        
        # High specificity: neighborhood, zip code, specific address
        if any(indicator in location for indicator in [
            'street', 'ave', 'st', 'blvd', 'road', 'zip', 'code'
        ]) or re.match(r'\d{5}(-\d{4})?', location):
            return 1.0
        
        # Medium specificity: city + state, well-known area
        if any(indicator in location for indicator in [
            ',', 'city', 'downtown', 'uptown', 'district'
        ]) or len(location.split()) >= 2:
            return 0.8
        
        # Low specificity: just city name
        if len(location.split()) == 1 and len(location) > 2:
            return 0.6
        
        # Very low specificity: vague area
        return 0.3
    
    def _score_timeline(self, timeline: Optional[str]) -> float:
        """Score timeline based on urgency."""
        if not timeline or not timeline.strip():
            return 0.0
        
        timeline = timeline.strip().lower()
        
        # Extract time periods and map to urgency
        time_patterns = {
            r'\b(immediately|now|asap|right away|urgent)\b': 'immediate',
            r'\b(1|one)\s*(month|months?)\b': 'urgent',
            r'\b(2|3|two|three)\s*(month|months?)\b': 'urgent',
            r'\b([4-6]|four|five|six)\s*(month|months?)\b': 'normal',
            r'\b([7-9]|seven|eight|nine)\s*(month|months?)\b': 'relaxed',
            r'\b(1[0-2]|ten|eleven|twelve)\s*(month|months?)\b': 'relaxed',
            r'\b(year|years?|1\+|more than)\b': 'future'
        }
        
        for pattern, urgency in time_patterns.items():
            if re.search(pattern, timeline):
                return self.timeline_urgency[urgency][1]
        
        # Default to medium urgency if timeline mentioned but unclear
        return 0.5
    
    def _score_property_type(
        self, 
        property_type: Optional[str], 
        desired_bedrooms: Optional[int]
    ) -> float:
        """Score property preferences."""
        score = 0.0
        
        # Property type specificity
        if property_type and property_type.strip():
            property_type = property_type.strip().lower()
            
            # Specific property types
            specific_types = [
                'condo', 'apartment', 'house', 'townhouse', 'villa',
                'studio', 'loft', 'penthouse', 'duplex'
            ]
            
            if any(ptype in property_type for ptype in specific_types):
                score += 0.6
            # General property types
            elif any(ptype in property_type for ptype in ['residential', 'property']):
                score += 0.3
            # Bedroom count mentioned
            else:
                score += 0.2
        
        # Bedroom preference
        if desired_bedrooms and desired_bedrooms > 0:
            if 1 <= desired_bedrooms <= 5:  # Reasonable range
                score += 0.4
            else:  # Unusual range
                score += 0.2
        
        return min(score, 1.0)
    
    def _score_completeness(
        self,
        budget: Optional[int],
        location: Optional[str],
        timeline: Optional[str],
        property_type: Optional[str],
        email: Optional[str],
        name: Optional[str]
    ) -> float:
        """Score based on information completeness."""
        fields = {
            'budget': budget is not None and budget > 0,
            'location': location is not None and location.strip(),
            'timeline': timeline is not None and timeline.strip(),
            'property_type': property_type is not None and property_type.strip(),
            'email': email is not None and '@' in email,
            'name': name is not None and name.strip()
        }
        
        completed_fields = sum(fields.values())
        total_fields = len(fields)
        
        return completed_fields / total_fields
    
    def _score_engagement(
        self,
        message: Optional[str],
        conversation_history: Optional[List[Dict[str, Any]]],
        previous_score: Optional[float]
    ) -> float:
        """Score based on engagement level."""
        score = 0.3  # Base score for responding
        
        # Message quality
        if message:
            message_length = len(message.strip())
            if message_length > 50:
                score += 0.2  # Detailed message
            elif message_length > 20:
                score += 0.1  # Moderate message
            
            # Question indicators
            if '?' in message:
                score += 0.2  # Asking questions
            
            # Specificity indicators
            specific_words = [
                'budget', 'price', 'location', 'area', 'bedroom',
                'bathroom', 'square', 'foot', 'timeline', 'when'
            ]
            word_count = sum(1 for word in specific_words if word in message.lower())
            score += min(word_count * 0.05, 0.2)
        
        # Conversation history engagement
        if conversation_history:
            user_messages = [
                msg for msg in conversation_history 
                if msg.get('role') == 'user'
            ]
            
            if len(user_messages) > 1:
                score += 0.2  # Multiple interactions
            
            # Response progression (improving score)
            if previous_score is not None:
                try:
                    # Ensure previous_score is a number
                    prev_score_float = float(previous_score)
                    score += 0.1  # Continued engagement
                except (ValueError, TypeError):
                    # If previous_score is not a valid number, just add base engagement
                    score += 0.05
        
        return min(score, 1.0)
    
    def _determine_routing(self, score: float) -> Dict[str, Any]:
        """Determine routing based on score thresholds."""
        if score >= 0.75:
            return {
                'next_agent': 'scheduler',
                'reasoning': f'Highly qualified lead (score: {score:.3f} >= 0.75)',
                'priority': 'high'
            }
        elif score >= 0.4:
            return {
                'next_agent': 'followup',
                'reasoning': f'Lead needs nurturing (score: {score:.3f} between 0.4-0.75)',
                'priority': 'medium'
            }
        else:
            return {
                'next_agent': 'offramp',
                'reasoning': f'Lead disqualified (score: {score:.3f} < 0.4)',
                'priority': 'low'
            }
    
    def _determine_qualification_stage(self, score: float) -> str:
        """Determine qualification stage based on score."""
        if score >= 0.75:
            return 'qualified'
        elif score >= 0.4:
            return 'nurturing'
        else:
            return 'disqualified'
    
    def get_next_qualification_question(
        self,
        lead_data: Dict[str, Any],
        asked_questions: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Determine the next qualification question to ask.
        
        Args:
            lead_data: Current lead information
            asked_questions: List of questions already asked
            
        Returns:
            Next question data or None if qualification complete
        """
        if not asked_questions:
            asked_questions = []
        
        # Define question priority and field mapping
        question_flow = [
            {
                'field': 'budget',
                'question': "What's your approximate budget for this property purchase?",
                'priority': 1,
                'required': True
            },
            {
                'field': 'location',
                'question': "What specific area or neighborhood are you interested in?",
                'priority': 2,
                'required': True
            },
            {
                'field': 'timeline',
                'question': "When are you planning to make this purchase?",
                'priority': 3,
                'required': True
            },
            {
                'field': 'property_type',
                'question': "What type of property are you looking for (house, condo, apartment)?",
                'priority': 4,
                'required': False
            },
            {
                'field': 'desired_bedrooms',
                'question': "How many bedrooms do you need?",
                'priority': 5,
                'required': False
            },
            {
                'field': 'email',
                'question': "What's your email address so I can send you property details?",
                'priority': 6,
                'required': True
            }
        ]
        
        # Find next unasked required question
        for q in question_flow:
            if (q['field'] not in asked_questions and 
                q['field'] not in lead_data and
                q['required']):
                return {
                    'field': q['field'],
                    'question': q['question'],
                    'priority': q['priority'],
                    'required': q['required']
                }
        
        # Find next unasked optional question
        for q in question_flow:
            if (q['field'] not in asked_questions and 
                q['field'] not in lead_data and
                not q['required']):
                return {
                    'field': q['field'],
                    'question': q['question'],
                    'priority': q['priority'],
                    'required': q['required']
                }
        
        # All questions asked or fields provided
        return None
    
    def should_continue_qualification(
        self,
        lead_data: Dict[str, Any],
        current_score: float
    ) -> bool:
        """
        Determine if qualification should continue based on current state.
        
        Args:
            lead_data: Current lead information
            current_score: Current qualification score
            
        Returns:
            True if qualification should continue, False otherwise
        """
        # Check if all required fields are present
        required_fields = ['budget', 'location', 'timeline', 'email']
        missing_required = [
            field for field in required_fields 
            if not lead_data.get(field)
        ]
        
        # Continue if missing required fields
        if missing_required:
            return True
        
        # Continue if score is in nurturing range and could improve
        if 0.4 <= current_score < 0.75:
            # Check if optional fields could improve score
            optional_fields = ['property_type', 'desired_bedrooms']
            missing_optional = [
                field for field in optional_fields 
                if not lead_data.get(field)
            ]
            if missing_optional:
                return True
        
        # Qualification complete
        return False
    
    def calculate_enhanced_lead_score(
        self,
        user_id: Optional[str] = None,
        industry_type: str = 'real_estate',
        budget: Optional[int] = None,
        location: Optional[str] = None,
        timeline: Optional[str] = None,
        property_type: Optional[str] = None,
        desired_bedrooms: Optional[int] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        message: Optional[str] = None,
        previous_score: Optional[float] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        touch_points: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Calculate enhanced lead score with response time urgency and engagement momentum.
        
        Args:
            user_id: Unique identifier for the user/lead
            industry_type: Industry type for adaptive scoring (real_estate, fitness, restaurant, hotel)
            budget: Lead's budget in USD
            location: Desired location
            timeline: Purchase timeline
            property_type: Property type preference
            desired_bedrooms: Number of bedrooms desired
            email: Lead's email address
            name: Lead's name
            message: Original message content
            previous_score: Previous qualification score
            conversation_history: Previous conversation messages
            touch_points: List of engagement touch points with timestamps
            
        Returns:
            Dictionary with enhanced score, breakdown, and routing recommendation
        """
        try:
            # Validate industry type
            if industry_type not in self.INDUSTRY_CONFIGS:
                logger.warning(f"Unknown industry type '{industry_type}', defaulting to 'real_estate'")
                industry_type = 'real_estate'
            
            industry_config = self.INDUSTRY_CONFIGS[industry_type]
            
            # Calculate base score using existing scoring system
            base_result = self.calculate_lead_score(
                budget=budget,
                location=location,
                timeline=timeline,
                property_type=property_type,
                desired_bedrooms=desired_bedrooms,
                email=email,
                name=name,
                message=message,
                previous_score=previous_score,
                conversation_history=conversation_history
            )
            base_score = base_result['final_score']
            
            # Calculate urgency score based on response time
            urgency_score = self._calculate_urgency_score(user_id)
            
            # Calculate engagement momentum score
            engagement_momentum_score = self._calculate_engagement_momentum(
                conversation_history, touch_points, previous_score
            )
            
            # Calculate enhanced score using industry-adaptive formula
            enhanced_score = self._calculate_enhanced_score(
                base_score, urgency_score, engagement_momentum_score, industry_config['industry_multiplier']
            )
            
            # Determine routing using industry-specific thresholds
            routing = self._determine_enhanced_routing(enhanced_score, industry_config)
            
            # Determine qualification stage
            qualification_stage = self._determine_enhanced_qualification_stage(
                enhanced_score, industry_config
            )
            
            # Calculate score improvement potential
            improvement_potential = self._calculate_improvement_potential(
                base_score, urgency_score, engagement_momentum_score, industry_config
            )
            
            result = {
                'enhanced_score': round(enhanced_score, 3),
                'base_score': round(base_score, 3),
                'urgency_score': round(urgency_score, 3),
                'engagement_momentum_score': round(engagement_momentum_score, 3),
                'industry_type': industry_type,
                'industry_config': industry_config,
                'score_breakdown': {
                    'base_weight': self.enhanced_scoring_weights['base_score'],
                    'urgency_weight': self.enhanced_scoring_weights['urgency_score'],
                    'engagement_momentum_weight': self.enhanced_scoring_weights['engagement_momentum'],
                    'industry_multiplier': industry_config['industry_multiplier']
                },
                'routing_recommendation': routing,
                'qualification_stage': qualification_stage,
                'improvement_potential': improvement_potential,
                'scoring_timestamp': datetime.now().isoformat(),
                'thresholds': {
                    'conversion_threshold': industry_config['conversion_threshold'],
                    'nurture_threshold': industry_config['nurture_threshold'],
                    'required_touches': industry_config['required_touches']
                }
            }
            
            logger.info(f"Enhanced lead score calculated: {enhanced_score:.3f} -> {routing['next_agent']} for {industry_type}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating enhanced lead score: {e}")
            # Return safe default on error
            return {
                'enhanced_score': 0.5,
                'base_score': 0.5,
                'urgency_score': 0.5,
                'engagement_momentum_score': 0.5,
                'industry_type': industry_type,
                'industry_config': self.INDUSTRY_CONFIGS.get(industry_type, self.INDUSTRY_CONFIGS['real_estate']),
                'score_breakdown': {},
                'routing_recommendation': {'next_agent': 'followup', 'reasoning': 'Enhanced scoring error - default to followup'},
                'qualification_stage': 'needs_qualification',
                'improvement_potential': {'potential': 0.0, 'focus_areas': []},
                'scoring_timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _calculate_urgency_score(self, user_id: Optional[str]) -> float:
        """
        Calculate urgency score based on response time tracking.
        
        Args:
            user_id: Unique identifier for the user/lead
            
        Returns:
            Urgency score between 0.0 and 1.0
        """
        if not user_id:
            # No user ID provided - assume medium urgency
            return 0.6
        
        try:
            # Use response tracker to calculate urgency score
            urgency_score = self.response_tracker.calculate_urgency_score(user_id)
            return urgency_score
        except Exception as e:
            logger.warning(f"Error calculating urgency score for user {user_id}: {e}")
            return 0.6  # Default to medium urgency on error
    
    def _calculate_engagement_momentum(
        self,
        conversation_history: Optional[List[Dict[str, Any]]],
        touch_points: Optional[List[Dict[str, Any]]],
        previous_score: Optional[float]
    ) -> float:
        """
        Calculate engagement momentum score based on touch points and conversation history.
        
        Args:
            conversation_history: Previous conversation messages
            touch_points: List of engagement touch points with timestamps
            previous_score: Previous qualification score
            
        Returns:
            Engagement momentum score between 0.0 and 1.0
        """
        score = 0.3  # Base score for any engagement
        
        try:
            # Score based on conversation history
            if conversation_history:
                user_messages = [
                    msg for msg in conversation_history
                    if msg.get('role') == 'user'
                ]
                
                # Multiple interactions increase momentum
                if len(user_messages) > 1:
                    score += min(0.2, len(user_messages) * 0.05)
                
                # Recent activity increases momentum
                if user_messages:
                    latest_message = max(
                        user_messages,
                        key=lambda x: x.get('timestamp', datetime.min.isoformat())
                    )
                    try:
                        msg_time = datetime.fromisoformat(
                            latest_message.get('timestamp', datetime.min.isoformat())
                        )
                        time_since_last = (datetime.now() - msg_time).total_seconds() / 3600  # hours
                        
                        if time_since_last <= 1:  # Within last hour
                            score += 0.3
                        elif time_since_last <= 24:  # Within last day
                            score += 0.2
                        elif time_since_last <= 72:  # Within last 3 days
                            score += 0.1
                    except (ValueError, TypeError):
                        pass
            
            # Score based on structured touch points
            if touch_points:
                recent_touches = [
                    tp for tp in touch_points
                    if self._is_recent_touch(tp)
                ]
                
                # More recent touches increase momentum
                score += min(0.3, len(recent_touches) * 0.1)
                
                # Different types of engagement increase momentum
                touch_types = set(tp.get('type') for tp in recent_touches)
                score += min(0.2, len(touch_types) * 0.05)
            
            # Score progression from previous score
            if previous_score is not None:
                try:
                    prev_score_float = float(previous_score)
                    if prev_score_float < 0.5:  # Coming from low score
                        score += 0.2  # Positive momentum
                    elif prev_score_float >= 0.7:  # Maintaining high score
                        score += 0.1  # Consistent momentum
                except (ValueError, TypeError):
                    pass
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating engagement momentum: {e}")
            return 0.5  # Default to medium momentum on error
    
    def _is_recent_touch(self, touch_point: Dict[str, Any]) -> bool:
        """
        Check if a touch point is recent (within last 7 days).
        
        Args:
            touch_point: Touch point dictionary with timestamp
            
        Returns:
            True if touch point is recent, False otherwise
        """
        try:
            timestamp_str = touch_point.get('timestamp')
            if not timestamp_str:
                return False
            
            touch_time = datetime.fromisoformat(timestamp_str)
            days_since = (datetime.now() - touch_time).days
            return days_since <= 7
        except (ValueError, TypeError):
            return False
    
    def _calculate_enhanced_score(
        self,
        base_score: float,
        urgency_score: float,
        engagement_momentum_score: float,
        industry_multiplier: float
    ) -> float:
        """
        Calculate enhanced score using industry-adaptive formula.
        
        Args:
            base_score: Base lead score from traditional scoring
            urgency_score: Response time urgency score
            engagement_momentum_score: Engagement momentum score
            industry_multiplier: Industry-specific multiplier
            
        Returns:
            Enhanced lead score
        """
        enhanced_score = (
            base_score * self.enhanced_scoring_weights['base_score'] +
            urgency_score * self.enhanced_scoring_weights['urgency_score'] +
            engagement_momentum_score * self.enhanced_scoring_weights['engagement_momentum']
        ) * industry_multiplier
        
        return min(enhanced_score, 1.0)  # Cap at 1.0
    
    def _determine_enhanced_routing(
        self,
        score: float,
        industry_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine routing based on enhanced score and industry-specific thresholds.
        
        Args:
            score: Enhanced lead score
            industry_config: Industry-specific configuration
            
        Returns:
            Routing recommendation dictionary
        """
        conversion_threshold = industry_config['conversion_threshold']
        nurture_threshold = industry_config['nurture_threshold']
        
        if score >= conversion_threshold:
            return {
                'next_agent': 'scheduler',
                'reasoning': f'Highly qualified lead (score: {score:.3f} >= {conversion_threshold}) for {industry_config["description"]}',
                'priority': 'high',
                'industry_type': industry_config.get('description', 'Unknown')
            }
        elif score >= nurture_threshold:
            return {
                'next_agent': 'followup',
                'reasoning': f'Lead needs nurturing (score: {score:.3f} between {nurture_threshold}-{conversion_threshold}) for {industry_config["description"]}',
                'priority': 'medium',
                'industry_type': industry_config.get('description', 'Unknown')
            }
        else:
            return {
                'next_agent': 'offramp',
                'reasoning': f'Lead disqualified (score: {score:.3f} < {nurture_threshold}) for {industry_config["description"]}',
                'priority': 'low',
                'industry_type': industry_config.get('description', 'Unknown')
            }
    
    def _determine_enhanced_qualification_stage(
        self,
        score: float,
        industry_config: Dict[str, Any]
    ) -> str:
        """
        Determine qualification stage based on enhanced score and industry thresholds.
        
        Args:
            score: Enhanced lead score
            industry_config: Industry-specific configuration
            
        Returns:
            Qualification stage string
        """
        conversion_threshold = industry_config['conversion_threshold']
        nurture_threshold = industry_config['nurture_threshold']
        
        if score >= conversion_threshold:
            return 'qualified'
        elif score >= nurture_threshold:
            return 'nurturing'
        else:
            return 'disqualified'
    
    def _calculate_improvement_potential(
        self,
        base_score: float,
        urgency_score: float,
        engagement_momentum_score: float,
        industry_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate improvement potential and focus areas.
        
        Args:
            base_score: Base lead score
            urgency_score: Response time urgency score
            engagement_momentum_score: Engagement momentum score
            industry_config: Industry-specific configuration
            
        Returns:
            Dictionary with improvement potential and focus areas
        """
        focus_areas = []
        potential = 0.0
        
        # Check urgency score potential
        if urgency_score < 0.8:
            focus_areas.append('response_time')
            potential += (0.8 - urgency_score) * self.enhanced_scoring_weights['urgency_score']
        
        # Check engagement momentum potential
        if engagement_momentum_score < 0.8:
            focus_areas.append('engagement_momentum')
            potential += (0.8 - engagement_momentum_score) * self.enhanced_scoring_weights['engagement_momentum']
        
        # Check base score potential
        if base_score < industry_config['conversion_threshold']:
            focus_areas.append('lead_qualification')
            potential += (industry_config['conversion_threshold'] - base_score) * self.enhanced_scoring_weights['base_score']
        
        return {
            'potential': round(potential, 3),
            'focus_areas': focus_areas,
            'target_score': industry_config['conversion_threshold'],
            'current_gap': round(industry_config['conversion_threshold'] - (base_score * 0.6 + urgency_score * 0.2 + engagement_momentum_score * 0.2), 3)
        }

# Global scoring system instance
lead_scorer = LeadScoringSystem()

def calculate_lead_score(lead_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Convenience function to calculate lead score.
    
    Args:
        lead_data: Dictionary containing lead information
        **kwargs: Additional parameters for scoring
        
    Returns:
        Scoring result dictionary
    """
    return lead_scorer.calculate_lead_score(
        budget=lead_data.get('budget'),
        location=lead_data.get('location'),
        timeline=lead_data.get('timeline'),
        property_type=lead_data.get('property_type'),
        desired_bedrooms=lead_data.get('desired_bedrooms'),
        email=lead_data.get('email'),
        name=lead_data.get('name'),
        message=lead_data.get('message'),
        **kwargs
    )

def get_next_qualification_question(
    lead_data: Dict[str, Any],
    asked_questions: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get next qualification question.
    """
    return lead_scorer.get_next_qualification_question(lead_data, asked_questions)


def calculate_enhanced_lead_score(
    lead_data: Dict[str, Any],
    user_id: Optional[str] = None,
    industry_type: str = 'real_estate',
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to calculate enhanced lead score.
    
    Args:
        lead_data: Dictionary containing lead information
        user_id: Unique identifier for the user/lead
        industry_type: Industry type for adaptive scoring (real_estate, fitness, restaurant, hotel)
        **kwargs: Additional parameters for scoring
        
    Returns:
        Enhanced scoring result dictionary
    """
    return lead_scorer.calculate_enhanced_lead_score(
        user_id=user_id,
        industry_type=industry_type,
        budget=lead_data.get('budget'),
        location=lead_data.get('location'),
        timeline=lead_data.get('timeline'),
        property_type=lead_data.get('property_type'),
        desired_bedrooms=lead_data.get('desired_bedrooms'),
        email=lead_data.get('email'),
        name=lead_data.get('name'),
        message=lead_data.get('message'),
        **kwargs
    )