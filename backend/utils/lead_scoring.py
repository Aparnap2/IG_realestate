"""
Lead Scoring System for Real Estate Qualification - Pure Agentic AI Version

Implements rule-based lead scoring without ML dependencies:
- Budget clarity and amount
- Location specificity
- Timeline urgency
- Property type preferences
- Response completeness
- Engagement level

Supports progressive scoring through conversation flow using simple rules.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)

class LeadScoringSystem:
    """
    Rule-based lead scoring system for real estate qualification.
    
    Pure agentic AI approach using simple rules instead of ML models.
    """
    
    # Industry-specific configurations
    INDUSTRY_CONFIGS = {
        'real_estate': {
            'conversion_threshold': 0.6,
            'nurture_threshold': 0.35,
            'required_touches': 8,
            'description': 'Real Estate - High value, longer sales cycle'
        },
        'fitness': {
            'conversion_threshold': 0.5,
            'nurture_threshold': 0.3,
            'required_touches': 6,
            'description': 'Fitness - Lower value, quicker decisions'
        },
        'restaurant': {
            'conversion_threshold': 0.55,
            'nurture_threshold': 0.35,
            'required_touches': 7,
            'description': 'Restaurant - Medium value, impulse decisions'
        },
        'hotel': {
            'conversion_threshold': 0.65,
            'nurture_threshold': 0.4,
            'required_touches': 10,
            'description': 'Hotel - High value, complex booking process'
        }
    }
    
    def __init__(self):
        # Rule-based scoring weights
        self.scoring_weights = {
            'budget': 0.25,        # Budget clarity and amount
            'location': 0.20,       # Location specificity
            'timeline': 0.15,       # Timeline urgency
            'property_type': 0.10,   # Property preferences
            'completeness': 0.15,    # Information completeness
            'engagement': 0.15      # Engagement level
        }
        
        # Simple budget tiers for rule-based scoring
        self.budget_tiers = {
            'high': (500000, 1.0),      # $500k+
            'medium_high': (300000, 0.8), # $300k-$500k
            'medium': (150000, 0.6),     # $150k-$300k
            'low': (50000, 0.4),         # $50k-$150k
            'very_low': (0, 0.2)         # <$50k
        }
        
        # Timeline urgency rules
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
        Calculate lead score using rule-based patterns.
        
        Pure agentic AI approach - no ML classification or complex scoring.
        
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
            # Calculate rule-based scoring components
            scores = {}
            
            scores['budget'] = self._score_budget(budget)
            scores['location'] = self._score_location(location)
            scores['timeline'] = self._score_timeline(timeline)
            scores['property_type'] = self._score_property_type(property_type, desired_bedrooms)
            scores['completeness'] = self._score_completeness(
                budget, location, timeline, property_type, email, name
            )
            scores['engagement'] = self._score_engagement(
                message, conversation_history, previous_score
            )
            
            # Calculate weighted final score
            final_score = sum(
                scores[component] * self.scoring_weights[component]
                for component in self.scoring_weights
            )
            
            # Calculate score delta
            score_delta = None
            if previous_score is not None:
                try:
                    prev_score_float = float(previous_score)
                    score_delta = final_score - prev_score_float
                except (ValueError, TypeError):
                    score_delta = None
            
            # Determine routing using simple rules
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
            
            logger.info(f"Rule-based lead score calculated: {final_score:.3f} -> {routing['next_agent']}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating lead score: {e}")
            return {
                'final_score': 0.5,
                'score_breakdown': {},
                'score_delta': None,
                'routing_recommendation': {'next_agent': 'followup', 'reasoning': 'Scoring error - default to followup'},
                'qualification_stage': 'needs_qualification',
                'scoring_timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _score_budget(self, budget) -> float:
        """Score budget using simple rule-based tier system."""
        try:
            if not budget:
                return 0.0
            
            # Convert to int safely
            if isinstance(budget, str):
                cleaned = budget.replace('$', '').replace(',', '').strip()
                if not cleaned or cleaned.lower() in ['null', 'none', '']:
                    return 0.0
                try:
                    budget = int(cleaned)
                except (ValueError, TypeError):
                    return 0.0
            elif not isinstance(budget, int):
                try:
                    budget = int(budget)
                except (ValueError, TypeError):
                    return 0.0
            
            if budget <= 0:
                return 0.0
            
            # Simple tier-based scoring
            for tier_name, (min_budget, score) in self.budget_tiers.items():
                if budget >= min_budget:
                    return score
            
            return 0.1
            
        except Exception as e:
            logger.warning(f"Error scoring budget '{budget}': {e}")
            return 0.0
    
    def _score_location(self, location: Optional[str]) -> float:
        """Score location using simple specificity rules."""
        if not location or not location.strip():
            return 0.0
        
        location = location.strip().lower()
        
        # High specificity
        if any(indicator in location for indicator in [
            'street', 'ave', 'st', 'blvd', 'road', 'zip', 'code'
        ]) or re.match(r'\d{5}(-\d{4})?', location):
            return 1.0
        
        # Medium specificity
        if any(indicator in location for indicator in [
            ',', 'city', 'downtown', 'uptown', 'district'
        ]) or len(location.split()) >= 2:
            return 0.8
        
        # Low specificity
        if len(location.split()) == 1 and len(location) > 2:
            return 0.6
        
        return 0.3
    
    def _score_timeline(self, timeline: Optional[str]) -> float:
        """Score timeline using simple urgency patterns."""
        if not timeline or not timeline.strip():
            return 0.0
        
        timeline = timeline.strip().lower()
        
        # Simple pattern matching for urgency
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
        
        return 0.5  # Default medium urgency
    
    def _score_property_type(self, property_type: Optional[str], desired_bedrooms) -> float:
        """Score property preferences using simple rules."""
        try:
            score = 0.0
            
            # Property type specificity
            if property_type and property_type.strip():
                property_type = property_type.strip().lower()
                
                specific_types = [
                    'condo', 'apartment', 'house', 'townhouse', 'villa',
                    'studio', 'loft', 'penthouse', 'duplex'
                ]
                
                if any(ptype in property_type for ptype in specific_types):
                    score += 0.6
                elif any(ptype in property_type for ptype in ['residential', 'property']):
                    score += 0.3
                else:
                    score += 0.2
            
            # Bedroom preference
            if desired_bedrooms:
                try:
                    if isinstance(desired_bedrooms, str):
                        cleaned = desired_bedrooms.strip()
                        if cleaned.lower() in ['null', 'none', '']:
                            bedroom_count = 0
                        else:
                            number_match = re.search(r'\d+', cleaned)
                            bedroom_count = int(number_match.group()) if number_match else 0
                    else:
                        bedroom_count = int(desired_bedrooms)
                    
                    if bedroom_count > 0:
                        if 1 <= bedroom_count <= 5:
                            score += 0.4
                        else:
                            score += 0.2
                            
                except (ValueError, TypeError):
                    pass
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error scoring property type '{property_type}' bedrooms '{desired_bedrooms}': {e}")
            return 0.5
    
    def _score_completeness(self, budget, location: Optional[str], timeline: Optional[str],
                           property_type: Optional[str], email: Optional[str], name: Optional[str]) -> float:
        """Score information completeness using simple rules."""
        try:
            # Budget completeness check
            budget_valid = False
            if budget is not None:
                try:
                    if isinstance(budget, str):
                        cleaned = budget.replace('$', '').replace(',', '').strip()
                        budget_num = int(cleaned) if cleaned and cleaned.lower() not in ['null', 'none', ''] else 0
                    else:
                        budget_num = int(budget)
                    budget_valid = budget_num > 0
                except (ValueError, TypeError):
                    budget_valid = False
            
            fields = {
                'budget': budget_valid,
                'location': bool(location is not None and location.strip()),
                'timeline': bool(timeline is not None and timeline.strip()),
                'property_type': bool(property_type is not None and property_type.strip()),
                'email': bool(email is not None and '@' in email),
                'name': bool(name is not None and name.strip())
            }
            
            completed_fields = sum(1 for value in fields.values() if value is True)
            total_fields = len(fields)
            
            return completed_fields / total_fields
            
        except Exception as e:
            logger.warning(f"Error scoring completeness: {e}")
            return 0.5
    
    def _score_engagement(self, message: Optional[str], 
                         conversation_history: Optional[List[Dict[str, Any]]], 
                         previous_score: Optional[float]) -> float:
        """Score engagement using simple interaction rules."""
        score = 0.3  # Base score
        
        # Message quality
        if message:
            message_length = len(message.strip())
            if message_length > 50:
                score += 0.2
            elif message_length > 20:
                score += 0.1
            
            # Question indicators
            if '?' in message:
                score += 0.2
            
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
            
            # Response progression
            if previous_score is not None:
                try:
                    prev_score_float = float(previous_score)
                    score += 0.1
                except (ValueError, TypeError):
                    score += 0.05
        
        return min(score, 1.0)
    
    def _determine_routing(self, score: float) -> Dict[str, Any]:
        """Simple rule-based routing decisions."""
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
                'next_agent': 'qualifier',
                'reasoning': f'Lead needs qualification (score: {score:.3f} < 0.4)',
                'priority': 'high',
                'proactive_qualification': True
            }
    
    def _determine_qualification_stage(self, score: float) -> str:
        """Determine qualification stage using simple thresholds."""
        if score >= 0.75:
            return 'qualified'
        elif score >= 0.4:
            return 'nurturing'
        else:
            return 'disqualified'

# Global scoring system instance
lead_scorer = LeadScoringSystem()

def calculate_lead_score(lead_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Convenience function to calculate lead score."""
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

def get_next_qualification_question(lead_data: Dict[str, Any], asked_questions: List[str] = None) -> Optional[Dict[str, Any]]:
    """
    Determine the next qualification question to ask based on missing information.
    
    Args:
        lead_data: Lead information dictionary
        asked_questions: List of questions already asked
        
    Returns:
        Dictionary with next question information, or None if no more questions needed
    """
    if asked_questions is None:
        asked_questions = []
    
    # Define qualification questions in order of importance
    qualification_questions = [
        {
            "field": "budget",
            "question": "What's your budget range for this property?",
            "required": True,
            "weight": 0.3
        },
        {
            "field": "location",
            "question": "Which areas or neighborhoods are you most interested in?",
            "required": True,
            "weight": 0.25
        },
        {
            "field": "property_type",
            "question": "What type of property are you looking for? (house, condo, apartment, etc.)",
            "required": False,
            "weight": 0.15
        },
        {
            "field": "timeline",
            "question": "What's your timeline for purchasing?",
            "required": False,
            "weight": 0.15
        },
        {
            "field": "desired_bedrooms",
            "question": "How many bedrooms are you looking for?",
            "required": False,
            "weight": 0.1
        },
        {
            "field": "email",
            "question": "Could you share your email so I can send you specific listings?",
            "required": False,
            "weight": 0.05
        }
    ]
    
    # Check what information is missing
    missing_fields = []
    for q in qualification_questions:
        field = q["field"]
        if field not in asked_questions:
            # Check if field has valid data
            value = lead_data.get(field)
            if field == "budget":
                # Budget must be > 0
                if not value or (isinstance(value, (int, str)) and int(value) <= 0):
                    missing_fields.append(q)
            elif field == "email":
                # Email must contain @
                if not value or "@" not in str(value):
                    missing_fields.append(q)
            else:
                # Other fields must not be empty
                if not value or not str(value).strip():
                    missing_fields.append(q)
    
    # Return the highest priority missing question
    if missing_fields:
        # Sort by weight (descending) to get most important first
        missing_fields.sort(key=lambda x: x["weight"], reverse=True)
        return missing_fields[0]
    
    return None