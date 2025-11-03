"""
Enhanced Follow-up Agent for Lead Nurturing

Implements sophisticated nurture strategy for 0.4-0.75 score leads:
- Gentle nurture sequence with value-added content
- Progressive qualification attempts
- Re-qualification after nurturing
- Personalized content delivery
- Long-term relationship building

Implements PRD Section 3.3: Nurture Path & Value Delivery
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response_sync
from backend.utils.supabase_client import get_config, save_lead
from backend.tools.agent_tools import send_instagram_message, create_nurture_sequence, fetch_lead_magnet
from backend.schemas.state import AgentState
from utils.observability import track_performance
from utils.audit import audit_log_event
from utils.lead_scoring import calculate_lead_score, lead_scorer
import logging

logger = logging.getLogger(__name__)

@track_performance
def followup_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced follow-up agent with sophisticated nurture path implementation.
    
    Implements PRD-compliant nurture strategy for 0.4-0.75 score leads:
    - Gentle nurture sequence with value-added content
    - Progressive qualification attempts
    - Re-qualification after nurturing
    - Personalized content delivery
    - Long-term relationship building
    
    Args:
        state: Current agent state with lead and context
        
    Returns:
        Updated state with nurture response and routing
    """
    lead = state["lead"]
    messages = state.get("messages", [])
    
    # Add the incoming message to the lead's history
    lead.history.append({
        "message": lead.message,
        "timestamp": datetime.now().isoformat(),
        "agent": "user"
    })
    
    try:
        # Calculate current score to determine nurture strategy
        lead_data = {
            'budget': lead.budget,
            'location': lead.location,
            'timeline': lead.timeline,
            'property_type': lead.property_type,
            'desired_bedrooms': lead.desired_bedrooms,
            'email': lead.email,
            'name': lead.name,
            'message': lead.message
        }
        
        scoring_result = calculate_lead_score(
            lead_data,
            previous_score=lead.previous_score,
            conversation_history=lead.history
        )
        
        # Update lead with current scoring
        lead.qualified_score = scoring_result['final_score']
        lead.previous_score = lead.previous_score or scoring_result['final_score']
        lead.score_delta = scoring_result['score_delta']
        lead.qualification_stage = scoring_result['qualification_stage']
        
        # Determine nurture strategy based on score and stage
        nurture_strategy = determine_nurture_strategy(lead, scoring_result)
        
        # Generate appropriate nurture response
        if nurture_strategy['type'] == 're_qualification':
            response = generate_re_qualification_response(lead, scoring_result)
            next_agent = 'qualifier'
        elif nurture_strategy['type'] == 'value_delivery':
            response = generate_value_delivery_response(lead, nurture_strategy)
            next_agent = 'value_delivery'
        elif nurture_strategy['type'] == 'engagement':
            response = generate_engagement_response(lead, nurture_strategy)
            next_agent = 'followup'
        else:  # standard_nurture
            response = generate_standard_nurture_response(lead, nurture_strategy)
            next_agent = 'followup'
        
        # Add response to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": response
        })
        
        # Update lead with follow-up tracking
        lead.last_interaction_at = datetime.now()
        lead.status = "nurturing"
        lead.dm_count = (lead.dm_count or 0) + 1
        lead.response_count = (lead.response_count or 0) + 1
        
        # Log nurture event
        audit_log_event("lead_nurtured", {
            "lead_id": lead.user_id,
            "strategy": nurture_strategy['type'],
            "score": scoring_result['final_score'],
            "score_delta": scoring_result['score_delta'],
            "next_agent": next_agent,
            "nurture_content": nurture_strategy.get('content_type', 'standard')
        })
        
        # Save lead state
        try:
            save_lead(lead.model_dump())
        except Exception as save_error:
            logger.error(f"Error saving lead during follow-up: {save_error}")
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": next_agent,
            "nurture_strategy": nurture_strategy,
            "scoring_result": scoring_result,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in follow-up nurturing: {e}")
        
        # Fallback response
        fallback_response = generate_fallback_nurture_response(lead)
        
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": fallback_response
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "error": str(e)
        }

def determine_nurture_strategy(lead: Any, scoring_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine the appropriate nurture strategy based on lead profile and score.
    
    Args:
        lead: Lead object
        scoring_result: Current scoring results
        
    Returns:
        Strategy dictionary with type and parameters
    """
    score = scoring_result['final_score']
    score_delta = scoring_result.get('score_delta', 0)
    
    # Check for score improvement
    if score_delta and score_delta > 0.1:
        # Score improving significantly - try re-qualification
        return {
            'type': 're_qualification',
            'reason': 'Score improving significantly',
            'confidence': 'high'
        }
    
    # Check if lead is close to qualification threshold
    if score >= 0.65:
        return {
            'type': 're_qualification',
            'reason': 'Close to qualification threshold',
            'confidence': 'medium'
        }
    
    # Check for missing critical information
    missing_critical = []
    if not lead.budget or lead.budget <= 0:
        missing_critical.append('budget')
    if not lead.location or not lead.location.strip():
        missing_critical.append('location')
    
    if missing_critical:
        return {
            'type': 're_qualification',
            'reason': f'Missing critical info: {", ".join(missing_critical)}',
            'confidence': 'high'
        }
    
    # Determine value delivery strategy based on lead interests
    if lead.message and any(keyword in lead.message.lower() for keyword in 
                      ['property', 'home', 'house', 'market', 'neighborhood', 'area']):
        return {
            'type': 'value_delivery',
            'reason': 'User showing specific interest',
            'content_type': 'targeted_value',
            'confidence': 'medium'
        }
    
    # Check for engagement opportunities
    if lead.response_count and lead.response_count > 2:
        return {
            'type': 'engagement',
            'reason': 'Engaged lead - build relationship',
            'content_type': 'relationship_building',
            'confidence': 'medium'
        }
    
    # Default to standard nurture
    return {
        'type': 'standard_nurture',
        'reason': 'Standard nurturing sequence',
        'content_type': 'general_value',
        'confidence': 'low'
    }

def generate_re_qualification_response(lead: Any, scoring_result: Dict[str, Any]) -> str:
    """Generate re-qualification response for improving leads."""
    name = lead.name or "there"
    score = scoring_result['final_score']
    
    message = f"""Hi {name}! 👋 Great to hear from you again!

I notice your profile is looking stronger - your current qualification score is {score:.2f}. That's fantastic progress! 🎯

📊 **What's Changed**:
Based on our recent conversations, you've provided more information that helps me understand your needs better.

🎯 **Next Steps**:
I'd love to help you take the next step. Could you share any updates on:
• Your budget range
• Preferred locations
• Timeline for purchasing
• Property type preferences

With this additional information, I can provide much better property recommendations and market insights!

💡 **How I Can Help**:
• Show you properties that match your updated criteria
• Send detailed market analysis for your target areas
• Share educational resources about the buying process
• Connect you with financing options if needed

What would be most helpful for you right now?"""
    
    return message

def generate_value_delivery_response(lead: Any, nurture_strategy: Dict[str, Any]) -> str:
    """Generate value delivery response based on user interests."""
    name = lead.name or "there"
    
    # Analyze user message for specific interests
    message_lower = lead.message.lower() if lead.message else ""
    
    if any(keyword in message_lower for keyword in ['property', 'home', 'house', 'condo']):
        return f"""Hi {name}! 👋 I'd be happy to share some property information with you!

Based on your interest in properties and your criteria:
• Budget: ${lead.budget or 'flexible'}
• Location: {lead.location or 'your preferred area'}
• Timeline: {lead.timeline or 'flexible'}

🏠 **Property Options**:
I can send you:
• Detailed property listings that match your criteria
• Virtual tour options for available properties
• Neighborhood information for areas you're considering
• Comparison tools to evaluate different options

Which would be most helpful? I can tailor the information specifically to your needs!"""
    
    elif any(keyword in message_lower for keyword in ['market', 'prices', 'trends', 'area']):
        return f"""Hi {name}! 👋 Great question about the market! 📊

Based on your interest in market information for {lead.location or 'your target area'}:

📈 **Market Analysis**:
I can provide you with:
• Current price trends and predictions
• Neighborhood comparisons and ratings
• Investment potential analysis
• Market inventory and availability
• Future development plans

💡 **How This Helps**:
Understanding the market helps you:
• Make competitive offers
• Identify good value opportunities
• Time your purchase strategically
• Negotiate more effectively

Would you like me to send you a detailed market analysis for your area?"""
    
    else:
        return f"""Hi {name}! 👋 I'm here to help you with your property search!

Based on what you've shared, I can provide valuable information:
• Property recommendations matching your criteria
• Market insights for your target areas
• Educational content about buying process
• Financing options and programs

🎯 **Your Current Profile**:
• Budget: ${lead.budget or 'Not specified'}
• Location: {lead.location or 'Not specified'}
• Timeline: {lead.timeline or 'Not specified'}
• Property Type: {lead.property_type or 'Not specified'}

What would you like to explore today? I can provide:
• Property listings and details
• Market trends and analysis
• Buying guides and checklists
• Personalized recommendations

Just let me know what interests you most! 🚀"""

def generate_engagement_response(lead: Any, nurture_strategy: Dict[str, Any]) -> str:
    """Generate engagement response for relationship building."""
    name = lead.name or "there"
    
    # Personalize based on interaction history
    interaction_count = lead.response_count or 1
    
    message = f"""Hi {name}! 👋 Great to hear from you again!

I appreciate you staying engaged in your property search journey. You've now interacted with me {interaction_count} times, which shows you're serious about finding the right property! 🎯

💬 **Building Our Partnership**:
I'm here to be your trusted advisor throughout this process. The more we interact, the better I can understand your needs and preferences.

🎯 **Your Progress**:
• Current qualification score: {lead.qualified_score or 0.5:.2f}/1.0
• Status: {lead.status or 'active'}
• Last interaction: {lead.last_interaction_at or 'Just now'}

💡 **How I Can Serve You Better**:
• Remember your preferences for future recommendations
• Provide increasingly personalized content
• Alert you to new opportunities that match your criteria
• Share insights specific to your situation

📊 **What's on Your Mind**:
Is there anything specific about your property search that's on your mind today? I'm here to help with questions, concerns, or next steps!"""

def generate_standard_nurture_response(lead: Any, nurture_strategy: Dict[str, Any]) -> str:
    """Generate standard nurture response with value-added content."""
    name = lead.name or "there"
    
    # Determine content type based on lead profile
    if lead.timeline and "first" in lead.timeline.lower():
        content_type = "first_time_buyer"
        content_message = "first-time buyer tips and guidance"
    elif lead.budget and lead.budget < 300000:
        content_type = "affordable_options"
        content_message = "affordable housing options and programs"
    elif lead.budget and lead.budget > 500000:
        content_type = "luxury_market"
        content_message = "luxury property insights and exclusive opportunities"
    else:
        content_type = "general_guidance"
        content_message = "comprehensive buying guidance and market tips"
    
    message = f"""Hi {name}! 👋 Following up with some helpful information for your property search.

I wanted to share some valuable {content_message} that might help you in your journey.

📚 **Helpful Resources**:
Based on your situation, I can provide:
• Educational content about the buying process
• Market insights for your target areas
• Property recommendations tailored to your budget
• Financing options and program information

🎯 **Your Current Progress**:
Your current qualification score is {lead.qualified_score or 0.5:.2f}/1.0. We're making good progress in understanding your needs!

💡 **Next Steps**:
I'm here to help you move forward. Would you like to:
• Explore specific property options?
• Learn more about market conditions?
• Access educational resources?
• Discuss financing possibilities?

What would be most valuable for you right now?"""

def generate_fallback_nurture_response(lead: Any) -> str:
    """Generate fallback nurture response when errors occur."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 I'm here to help you with your property search.

I'm working to provide you with the most relevant information for your needs. In the meantime, I can help you with:

🏠 **Property Search**:
• Find properties that match your criteria
• Provide detailed property information
• Schedule viewings and consultations

📊 **Market Information**:
• Share market trends and insights
• Compare different neighborhoods
• Analyze price ranges and values

📚 **Educational Resources**:
• Buying guides and checklists
• Financing options and programs
• Tips for successful purchasing

What aspect of your property search would you like to explore today? I'm here to help with questions, concerns, or next steps!"""

def create_nurture_campaign(lead: Any) -> Dict[str, Any]:
    """
    Create a comprehensive nurture campaign for the lead.
    
    Args:
        lead: Lead object with profile information
        
    Returns:
        Nurture campaign configuration
    """
    try:
        # Determine campaign strategy based on lead profile
        lead_data = {
            'budget': lead.budget,
            'location': lead.location,
            'timeline': lead.timeline,
            'property_type': lead.property_type,
            'qualified_score': lead.qualified_score or 0.5,
            'lead_stage': lead.qualification_stage or 'nurturing',
            'user_id': lead.user_id
        }
        
        # Create nurture sequence using enhanced tool
        campaign_result = create_nurture_sequence.invoke(lead_data)
        
        if campaign_result.get('success'):
            return {
                'campaign_id': f"nurture_{lead.user_id}_{datetime.now().strftime('%Y%m%d')}",
                'strategy': campaign_result.get('strategy', 'standard_nurture'),
                'sequence': campaign_result.get('sequence', []),
                'timeline': campaign_result.get('timeline', '4_weeks'),
                'created_at': datetime.now().isoformat(),
                'success': True
            }
        else:
            return {
                'error': campaign_result.get('error', 'Failed to create nurture campaign'),
                'success': False
            }
            
    except Exception as e:
        logger.error(f"Error creating nurture campaign: {e}")
        return {
            'error': str(e),
            'success': False
        }

def schedule_nurture_followup(lead: Any, days_ahead: int = 7) -> Dict[str, Any]:
    """
    Schedule next nurture follow-up for the lead.
    
    Args:
        lead: Lead object
        days_ahead: Days until next follow-up
        
    Returns:
        Scheduling information
    """
    followup_date = datetime.now() + timedelta(days=days_ahead)
    
    return {
        'lead_id': lead.user_id,
        'scheduled_date': followup_date,
        'purpose': 'nurture_followup',
        'message': f"Scheduled nurture follow-up for {followup_date.strftime('%B %d, %Y')}",
        'created_at': datetime.now().isoformat()
    }


class FollowupAgent:
    """
    Follow-up Agent class wrapper for testing compatibility.
    """
    
    def __init__(self):
        pass
    
    def process(self, state):
        """Process state through follow-up"""
        return followup_node(state)