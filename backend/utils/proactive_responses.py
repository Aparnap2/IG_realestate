"""
Proactive Response Generation System

Implements PRD-compliant proactive reasoning engine that:
- Anticipates user needs beyond initial prompts
- Pre-empts follow-up questions with recommendations
- Provides optimal actions with rationale
- Generates contextual responses with next steps

Based on the Qualification & Proactive AI Engine specification.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ProactiveResponseEngine:
    """
    Proactive response engine that anticipates user needs and provides 
    contextual recommendations with rationale.
    """
    
    def __init__(self):
        """Initialize the proactive response engine."""
        self.conversation_patterns = {
            'budget_inquiry': ['budget', 'price', 'cost', '$', 'money'],
            'property_search': ['looking', 'find', 'property', 'house', 'condo'],
            'bedroom_request': ['bhk', 'bedroom', 'bed'],
            'location_interest': ['location', 'area', 'neighborhood', 'near'],
            'timeline_inquiry': ['when', 'timeline', 'soon', 'asap'],
            'availability_check': ['option', 'available', 'show', 'see']
        }
    
    def generate_proactive_response(
        self,
        lead_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        conversation_stage: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Generate proactive response based on lead data and conversation context.
        
        Args:
            lead_data: Current lead information
            scoring_result: Lead scoring results
            conversation_stage: Current conversation stage
            user_message: User's latest message
            
        Returns:
            Proactive response with recommendations and rationale
        """
        try:
            # Analyze conversation pattern
            pattern = self._analyze_conversation_pattern(user_message, conversation_stage)
            
            # Generate proactive recommendations
            recommendations = self._generate_recommendations(lead_data, scoring_result, pattern)
            
            # Build proactive response message
            response_message = self._build_proactive_message(
                lead_data, recommendations, pattern, conversation_stage
            )
            
            # Determine next actions
            next_actions = self._determine_next_actions(lead_data, scoring_result, recommendations)
            
            return {
                "response_message": response_message,
                "recommendations": recommendations,
                "next_actions": next_actions,
                "pattern_detected": pattern,
                "proactive_confidence": self._calculate_proactive_confidence(lead_data, pattern),
                "rationale": self._generate_rationale(recommendations, pattern),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating proactive response: {e}")
            return self._generate_fallback_response(lead_data, conversation_stage)
    
    def _analyze_conversation_pattern(self, message: str, stage: str) -> str:
        """Analyze conversation pattern to determine proactive response strategy."""
        message_lower = message.lower()
        
        # Check for specific patterns
        for pattern_name, keywords in self.conversation_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return pattern_name
        
        # Default pattern based on stage
        stage_patterns = {
            'greeting': 'welcome',
            'information_request': 'provide_info',
            'qualification': 'assist_qualification'
        }
        
        return stage_patterns.get(stage, 'general_assistance')
    
    def _generate_recommendations(
        self,
        lead_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        pattern: str
    ) -> List[Dict[str, Any]]:
        """Generate contextual recommendations based on lead data and pattern."""
        recommendations = []
        
        # Budget-based recommendations
        if lead_data.get('budget') and lead_data.get('budget') > 0:
            recommendations.append({
                "type": "budget_analysis",
                "title": f"Budget Range: ${lead_data['budget']:,}",
                "description": self._analyze_budget_range(lead_data['budget']),
                "confidence": 0.9,
                "actionable": True
            })
        
        # Property type recommendations
        if lead_data.get('property_type') or lead_data.get('desired_bedrooms'):
            prop_type = lead_data.get('property_type') or f"{lead_data.get('desired_bedrooms', 'N/A')}BHK"
            recommendations.append({
                "type": "property_match",
                "title": f"Property Type: {prop_type}",
                "description": self._analyze_property_preferences(lead_data),
                "confidence": 0.8,
                "actionable": True
            })
        
        # Location-based recommendations
        if lead_data.get('location'):
            recommendations.append({
                "type": "location_analysis",
                "title": f"Location: {lead_data['location']}",
                "description": self._analyze_location_benefits(lead_data['location']),
                "confidence": 0.7,
                "actionable": True
            })
        
        # Score-based recommendations
        score = scoring_result.get('final_score', 0)
        if score >= 0.4:
            recommendations.append({
                "type": "next_steps",
                "title": "Ready for Next Phase",
                "description": self._get_next_phase_recommendation(score, lead_data),
                "confidence": min(score + 0.2, 1.0),
                "actionable": True
            })
        
        return recommendations
    
    def _analyze_budget_range(self, budget: int) -> str:
        """Analyze budget range and provide market context."""
        if budget >= 500000:
            return "Premium market segment with luxury options and high-end amenities."
        elif budget >= 300000:
            return "Mid-range market with good selection of quality properties."
        elif budget >= 150000:
            return "Entry-level market with starter homes and investment opportunities."
        else:
            return "Budget-friendly options available, consider financing programs."
    
    def _analyze_property_preferences(self, lead_data: Dict[str, Any]) -> str:
        """Analyze property preferences and market availability."""
        prop_type = lead_data.get('property_type', '')
        bedrooms = lead_data.get('desired_bedrooms', 0)
        
        if bedrooms:
            if bedrooms <= 2:
                return "Popular segment with high demand and quick sales."
            elif bedrooms <= 4:
                return "Family-friendly segment with good inventory."
            else:
                return "Premium segment with limited but high-value inventory."
        else:
            return "Flexible search criteria increase available options."
    
    def _analyze_location_benefits(self, location: str) -> str:
        """Analyze location benefits and market conditions."""
        location_lower = location.lower()
        
        # Common location patterns
        if any(city in location_lower for city in ['new york', 'nyc', 'manhattan']):
            return "High-value market with excellent appreciation potential."
        elif any(city in location_lower for city in ['los angeles', 'la', 'beverly']):
            return "Premium coastal market with strong demand."
        elif any(city in location_lower for city in ['miami', 'florida']):
            return "Growing market with favorable tax environment."
        else:
            return "Local market with specific advantages and opportunities."
    
    def _get_next_phase_recommendation(self, score: float, lead_data: Dict[str, Any]) -> str:
        """Get recommendation for next phase based on score."""
        if score >= 0.75:
            return "Ready to schedule property tours and viewings."
        elif score >= 0.4:
            return "Ready for property recommendations and market analysis."
        else:
            return "Continue gathering requirements for better matches."
    
    def _build_proactive_message(
        self,
        lead_data: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        pattern: str,
        stage: str
    ) -> str:
        """Build proactive response message with recommendations."""
        name = lead_data.get('name', 'there')
        
        # Build context summary
        context_parts = []
        if lead_data.get('budget'):
            context_parts.append(f"budget of ${lead_data['budget']:,}")
        if lead_data.get('property_type') or lead_data.get('desired_bedrooms'):
            prop_info = lead_data.get('property_type') or f"{lead_data.get('desired_bedrooms', 'N/A')}BHK"
            context_parts.append(f"looking for {prop_info}")
        if lead_data.get('location'):
            context_parts.append(f"in {lead_data['location']}")
        
        context_str = " with " + ", ".join(context_parts) if context_parts else ""
        
        # Start proactive message
        if pattern == 'availability_check':
            message = f"Hi {name}! 👋 Based on your criteria{context_str}, I have some great options for you!"
        elif pattern == 'budget_inquiry':
            message = f"Hi {name}! 💰 Your budget of ${lead_data.get('budget', 0):,} opens up excellent opportunities."
        elif pattern == 'property_search':
            message = f"Hi {name}! 🏠 I can help you find the perfect property{context_str}."
        else:
            message = f"Hi {name}! ✨ Based on what you've shared{context_str}, here's what I can offer:"
        
        # Add recommendations
        message += "\n\n"
        for i, rec in enumerate(recommendations, 1):
            message += f"{i}. **{rec['title']}**\n"
            message += f"   {rec['description']}\n\n"
        
        # Add next steps based on score
        score = lead_data.get('qualified_score', 0)
        if score >= 0.75:
            message += "🎯 **Ready to take action?** I can schedule property tours this week."
        elif score >= 0.4:
            message += "📋 **Next steps:** I can send you specific property recommendations."
        else:
            message += "🔍 **Let me help:** Share a bit more about your timeline and I'll find exact matches."
        
        return message
    
    def _determine_next_actions(
        self,
        lead_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Determine specific next actions for the user."""
        score = scoring_result.get('final_score', 0)
        actions = []
        
        if score >= 0.75:
            actions.append({
                "action": "schedule_tour",
                "description": "Schedule property viewing",
                "priority": "high"
            })
            actions.append({
                "action": "send_properties",
                "description": "Send specific property listings",
                "priority": "high"
            })
        elif score >= 0.4:
            actions.append({
                "action": "send_recommendations",
                "description": "Send curated property recommendations",
                "priority": "medium"
            })
            actions.append({
                "action": "market_update",
                "description": "Provide market analysis and trends",
                "priority": "medium"
            })
        else:
            actions.append({
                "action": "gather_requirements",
                "description": "Continue qualification process",
                "priority": "high"
            })
            actions.append({
                "action": "educational_content",
                "description": "Send buying guide and tips",
                "priority": "low"
            })
        
        return actions
    
    def _calculate_proactive_confidence(self, lead_data: Dict[str, Any], pattern: str) -> float:
        """Calculate confidence level for proactive response."""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on data completeness
        data_fields = ['budget', 'location', 'property_type', 'desired_bedrooms']
        filled_fields = sum(1 for field in data_fields if lead_data.get(field))
        confidence += (filled_fields / len(data_fields)) * 0.4
        
        # Increase confidence for clear patterns
        clear_patterns = ['availability_check', 'budget_inquiry', 'property_search']
        if pattern in clear_patterns:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_rationale(self, recommendations: List[Dict[str, Any]], pattern: str) -> str:
        """Generate rationale for proactive recommendations."""
        rationale_parts = []
        
        if recommendations:
            rationale_parts.append(f"Generated {len(recommendations)} recommendations based on")
            
            rec_types = [rec['type'] for rec in recommendations]
            if 'budget_analysis' in rec_types:
                rationale_parts.append("budget analysis")
            if 'property_match' in rec_types:
                rationale_parts.append("property preferences")
            if 'location_analysis' in rec_types:
                rationale_parts.append("location benefits")
            if 'next_steps' in rec_types:
                rationale_parts.append("qualification score")
            
            rationale_parts.append(f"for {pattern} conversation pattern")
        
        return " ".join(rationale_parts)
    
    def _generate_fallback_response(self, lead_data: Dict[str, Any], stage: str) -> Dict[str, Any]:
        """Generate fallback response when proactive generation fails."""
        name = lead_data.get('name', 'there')
        
        fallback_message = f"""Hi {name}! 👋 I'm here to help you find the perfect property. 

Based on what you've shared, I can:
• Send you available properties matching your criteria
• Provide market analysis and trends  
• Schedule property tours and viewings
• Answer any questions about the buying process

What would be most helpful for you right now?"""
        
        return {
            "response_message": fallback_message,
            "recommendations": [],
            "next_actions": [
                {"action": "show_properties", "description": "Display available properties", "priority": "high"},
                {"action": "answer_questions", "description": "Address specific questions", "priority": "medium"}
            ],
            "pattern_detected": "fallback",
            "proactive_confidence": 0.3,
            "rationale": "Fallback response due to generation error",
            "timestamp": datetime.now().isoformat()
        }

# Global proactive response engine instance
proactive_engine = ProactiveResponseEngine()

def generate_proactive_response(
    lead_data: Dict[str, Any],
    scoring_result: Dict[str, Any],
    conversation_stage: str,
    user_message: str
) -> Dict[str, Any]:
    """
    Main API function for generating proactive responses.
    
    Args:
        lead_data: Current lead information
        scoring_result: Lead scoring results
        conversation_stage: Current conversation stage
        user_message: User's latest message
        
    Returns:
        Proactive response dictionary
    """
    return proactive_engine.generate_proactive_response(
        lead_data, scoring_result, conversation_stage, user_message
    )