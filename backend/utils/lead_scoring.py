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

logger = logging.getLogger(__name__)

class LeadScoringSystem:
    """
    Advanced lead scoring system for real estate qualification.
    
    Scoring thresholds:
    - >= 0.75: Highly qualified (route to scheduler)
    - 0.4-0.75: Needs nurturing (route to followup)
    - < 0.4: Disqualified (route to off-ramp)
    """
    
    def __init__(self):
        self.scoring_weights = {
            'budget': 0.25,        # Budget clarity and amount
            'location': 0.20,       # Location specificity
            'timeline': 0.15,       # Timeline urgency
            'property_type': 0.10,   # Property preferences
            'completeness': 0.15,    # Information completeness
            'engagement': 0.15       # Engagement level
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
                score_delta = final_score - previous_score
            
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
                score += 0.1  # Continued engagement
        
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