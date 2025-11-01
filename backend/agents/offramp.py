"""
Polite Off-Ramp Agent for Disqualified Leads

Handles graceful disqualification with value preservation:
- Polite disqualification messages
- Newsletter subscription offer
- Future re-engagement options
- Brand reputation protection

Implements PRD Section 3.4: Polite Off-Ramp & Future Re-engagement
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response_sync
from utils.supabase_client import save_lead, get_config
from tools.agent_tools import send_instagram_message
from schemas.state import AgentState
from utils.observability import track_performance
from utils.audit import audit_log_event
import logging

logger = logging.getLogger(__name__)

@track_performance
def offramp_node(state: AgentState) -> Dict[str, Any]:
    """
    Off-ramp agent that handles disqualified leads politely.
    
    Implements graceful disqualification:
    - Polite rejection with value preservation
    - Newsletter subscription offer
    - Future re-engagement options
    - Brand reputation protection
    
    Args:
        state: Current agent state with lead and context
        
    Returns:
        Updated state with off-ramp handling
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
        # Determine off-ramp reason and strategy
        offramp_reason = determine_offramp_reason(lead)
        offramp_strategy = get_offramp_strategy(offramp_reason, lead)
        
        # Build appropriate off-ramp message
        offramp_message = build_offramp_message(lead, offramp_reason, offramp_strategy)
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": offramp_message
        })
        
        # Update lead with off-ramp tracking
        lead.offramp_sent_at = datetime.now()
        lead.offramp_reason = offramp_reason
        lead.status = "disqualified"
        lead.qualification_stage = "disqualified"
        
        # Update lead history
        lead.history.append({
            "message": f"Polite off-ramp sent: {offramp_reason}",
            "timestamp": datetime.now().isoformat(),
            "agent": "offramp"
        })
        
        # Log off-ramp event
        audit_log_event("lead_offramped", {
            "lead_id": lead.user_id,
            "reason": offramp_reason,
            "strategy": offramp_strategy,
            "qualified_score": lead.qualified_score,
            "offramp_sent_at": lead.offramp_sent_at.isoformat()
        })
        
        # Save lead with off-ramp information
        try:
            save_lead(lead.model_dump())
        except Exception as save_error:
            logger.error(f"Error saving lead during off-ramp: {save_error}")
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "END",
            "offramp_reason": offramp_reason,
            "offramp_strategy": offramp_strategy,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in off-ramp handling: {e}")
        
        # Fallback off-ramp message
        fallback_message = build_fallback_offramp_message(lead)
        
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": fallback_message
        })
        
        lead.history.append({
            "message": "Fallback off-ramp due to error",
            "timestamp": datetime.now().isoformat(),
            "agent": "offramp"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "END",
            "error": str(e)
        }

def determine_offramp_reason(lead: Any) -> str:
    """
    Determine the reason for off-ramp based on lead profile.
    
    Args:
        lead: Lead object with qualification information
        
    Returns:
        Off-ramp reason string
    """
    score = lead.qualified_score or 0.0
    
    # Low score reasons
    if score < 0.2:
        return "very_low_score"
    elif score < 0.4:
        return "low_score"
    
    # Budget-related reasons
    if lead.budget and lead.budget < 50000:
        return "budget_too_low"
    elif lead.budget and lead.budget > 2000000:
        return "budget_unrealistic"
    
    # Information completeness reasons
    missing_critical = []
    if not lead.budget or lead.budget <= 0:
        missing_critical.append("budget")
    if not lead.location or not lead.location.strip():
        missing_critical.append("location")
    
    if missing_critical:
        return "missing_critical_info"
    
    # Timeline reasons
    if lead.timeline and "year" in lead.timeline.lower() and "5+" in lead.timeline:
        return "timeline_too_long"
    
    # Default reason
    return "general_disqualification"

def get_offramp_strategy(offramp_reason: str, lead: Any) -> Dict[str, Any]:
    """
    Determine the appropriate off-ramp strategy based on reason.
    
    Args:
        offramp_reason: Reason for off-ramp
        lead: Lead object
        
    Returns:
        Strategy dictionary with approach and options
    """
    strategies = {
        "very_low_score": {
            "approach": "gentle_rejection",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": True,
            "timeline": "6_months"
        },
        "low_score": {
            "approach": "nurture_invitation",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": True,
            "timeline": "3_months"
        },
        "budget_too_low": {
            "approach": "helpful_guidance",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": True,
            "timeline": "12_months",
            "specific_advice": "budget_preparation"
        },
        "budget_unrealistic": {
            "approach": "reality_check",
            "offer_newsletter": True,
            "offer_future_reengagement": False,
            "provide_resources": True,
            "timeline": "immediate",
            "specific_advice": "market_education"
        },
        "missing_critical_info": {
            "approach": "information_request",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": False,
            "timeline": "1_month"
        },
        "timeline_too_long": {
            "approach": "future_planning",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": True,
            "timeline": "6_months"
        },
        "general_disqualification": {
            "approach": "polite_closure",
            "offer_newsletter": True,
            "offer_future_reengagement": True,
            "provide_resources": True,
            "timeline": "3_months"
        }
    }
    
    return strategies.get(offramp_reason, strategies["general_disqualification"])

def build_offramp_message(lead: Any, reason: str, strategy: Dict[str, Any]) -> str:
    """
    Build personalized off-ramp message based on reason and strategy.
    
    Args:
        lead: Lead object
        reason: Off-ramp reason
        strategy: Off-ramp strategy dictionary
        
    Returns:
        Personalized off-ramp message
    """
    name = lead.name or "there"
    approach = strategy["approach"]
    
    # Build message based on approach
    if approach == "gentle_rejection":
        return build_gentle_rejection_message(lead, strategy)
    elif approach == "nurture_invitation":
        return build_nurture_invitation_message(lead, strategy)
    elif approach == "helpful_guidance":
        return build_helpful_guidance_message(lead, reason, strategy)
    elif approach == "reality_check":
        return build_reality_check_message(lead, strategy)
    elif approach == "information_request":
        return build_information_request_message(lead, strategy)
    elif approach == "future_planning":
        return build_future_planning_message(lead, strategy)
    else:  # polite_closure
        return build_polite_closure_message(lead, strategy)

def build_gentle_rejection_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build gentle rejection message for very low score leads."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thank you for your interest in our properties.

After reviewing your inquiry, it appears that our current properties might not be the best match for your needs at this time. This doesn't mean we can't help you in the future!

📧 **Stay Connected**:
I'd love to keep you updated on:
• New properties that might better fit your criteria
• Market changes that could affect your search
• Special programs and financing options
• Educational resources for home buyers

Would you like me to add you to our newsletter for valuable updates?

🔄 **Future Opportunities**:
Your situation might change, and when it does, we'll be here to help. Sometimes timing is everything in real estate!

💡 **Helpful Resources**:
While you're planning, I can share:
• Budget preparation guides
• Market trend information
• Neighborhood research tips
• Financing education materials

Thank you for reaching out, and I hope we can assist you in the future! 🌟

Would you like to receive our newsletter with helpful tips and updates?"""
    
    return message

def build_nurture_invitation_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build nurture invitation message for low score leads."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thanks for sharing your property search details with us.

Based on what you've told me about your budget of ${lead.budget or 'flexible'} and interest in {lead.location or 'your preferred area'}, I think we could help you better with a bit more preparation.

🌱 **Let's Grow Together**:
I'd love to send you helpful information while you continue your search:
• Market updates for your target area
• Tips for improving your buying position
• New property alerts as they become available
• Educational content about the buying process

📧 **Stay in the Loop**:
Would you like to receive our weekly newsletter with:
• Market trends and insights
• Buying tips and strategies
• New property listings
• Exclusive opportunities

🎯 **Next Steps**:
In the meantime, I can help you:
• Understand what affects your qualification score
• Identify areas for improvement
• Plan for future property purchases
• Access helpful resources

Sometimes the perfect property just needs a little more time to align! 🚀

Would you like to receive our newsletter and helpful resources?"""
    
    return message

def build_helpful_guidance_message(lead: Any, reason: str, strategy: Dict[str, Any]) -> str:
    """Build helpful guidance message for budget-related issues."""
    name = lead.name or "there"
    
    if reason == "budget_too_low":
        message = f"""Hi {name}! 👋 Thank you for your interest in finding a property.

I appreciate you sharing your budget of ${lead.budget:,}. In the current market, this budget range presents some challenges for the areas you're interested in, but I have some suggestions that might help!

💡 **Budget Preparation Tips**:
• Start saving consistently with automatic transfers
• Look into first-time buyer assistance programs
• Consider government-backed loan options (FHA, VA)
• Explore down payment assistance programs
• Improve your credit score for better rates

📚 **Free Resources**:
I can send you guides on:
• Budget planning for home purchase
• Down payment saving strategies
• First-time buyer programs
• Credit improvement tips

📧 **Stay Updated**:
The market changes constantly! I can notify you when:
• New affordable properties become available
• Interest rates change favorably
• New assistance programs launch
• Market conditions improve

🔄 **Future Planning**:
Many successful buyers start with smaller steps:
• Build savings for 6-12 months
• Improve credit and financial position
• Research neighborhoods thoroughly
• Connect with lenders early

Would you like me to send you budget preparation guides and keep you updated on new opportunities?"""
    
    else:  # Other budget issues
        message = f"""Hi {name}! 👋 Thank you for sharing your property search details.

I want to help you find the perfect property, and I think we can work together to make that happen!

🎯 **Let's Find the Right Path**:
Based on your criteria, I can help you:
• Understand current market conditions
• Explore different financing options
• Identify properties that offer the best value
• Plan for future opportunities

📧 **Helpful Updates**:
I'd love to keep you informed about:
• Market changes that could help your search
• New property listings
• Special programs and incentives
• Educational resources

💡 **Next Steps**:
Sometimes the perfect match just needs a little more time or the right strategy. I'm here to help you navigate this journey!

Would you like to receive helpful updates and resources while you continue your search?"""
    
    return message

def build_reality_check_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build reality check message for unrealistic budgets."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thank you for your interest in luxury properties.

I appreciate you sharing your budget of ${lead.budget:,}. That's a substantial budget that opens up many premium options! However, I want to make sure we find properties that truly match your expectations.

🏰 **Luxury Market Insights**:
• High-end properties have unique features and locations
• Premium properties often require specialized searches
• Luxury markets move differently than standard markets
• Exclusive listings may not be widely advertised

🎯 **How I Can Help**:
• Access to exclusive luxury property networks
• Connections with luxury property specialists
• Detailed market analysis for premium areas
• Coordination with specialized lenders

📧 **Premium Updates**:
For luxury property searches, I recommend:
• Exclusive property alerts
• Private showing arrangements
• Discreet communication preferences
• Personalized service options

💎 **Next Steps**:
Luxury property purchases often require:
• Specialized financing options
• Additional due diligence
• Professional representation
• Longer search timelines

Would you like me to connect you with our luxury property specialists and provide exclusive market updates?"""
    
    return message

def build_information_request_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build information request message for incomplete profiles."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thanks for reaching out about property search.

I'd love to help you find the perfect property, but I need a bit more information to provide the best recommendations.

📋 **Missing Details**:
To give you accurate property suggestions, I need:
• Your approximate budget range
• Preferred location or area
• Timeline for purchase
• Property type preferences

🎯 **How This Helps You**:
With complete information, I can:
• Show only relevant properties
• Provide accurate market insights
• Suggest appropriate financing options
• Save you time and effort

📧 **Helpful Resources**:
While you gather this information, I can send:
• Budget planning guides
• Area research tips
• Property comparison tools
• Buying process education

💡 **Quick Tips**:
• Research neighborhoods you're interested in
• Check your credit score and financing options
• Make a list of must-have features
• Consider your timeline and flexibility

Once you have these details, I'll be able to provide much better assistance!

Would you like me to send helpful planning guides while you prepare?"""
    
    return message

def build_future_planning_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build future planning message for long timelines."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thank you for planning ahead with your property search!

I appreciate you thinking about your future home purchase with a timeline of {lead.timeline}. That's actually very smart planning!

🗓️ **Long-Term Planning Benefits**:
• More time to save for down payment
• Opportunity to improve credit score
• Thorough neighborhood research
• Better financial preparation
• Access to more financing options

📚 **Planning Resources**:
I can send you guides for:
• Long-term savings strategies
• Credit improvement plans
• Market trend analysis
• Neighborhood research frameworks
• First-time buyer programs

📧 **Stay Informed**:
The market will change between now and your purchase timeline. I can keep you updated on:
• Market trends and predictions
• New development projects
• Interest rate changes
• New property types and features
• Program and incentive changes

🎯 **Preparation Steps**:
Use your timeline advantage to:
• Build strong savings habits
• Research neighborhoods thoroughly
• Connect with lenders early
• Understand all costs involved
• Plan for life changes

Would you like me to send planning resources and keep you updated on market changes?"""
    
    return message

def build_polite_closure_message(lead: Any, strategy: Dict[str, Any]) -> str:
    """Build polite closure message for general disqualification."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thank you for your interest in our property services.

I appreciate you taking the time to share your property search details with us. While our current offerings might not be the perfect match for your needs right now, I want to make sure you have access to helpful resources.

📧 **Valuable Updates**:
I'd love to keep you informed about:
• Market changes and new opportunities
• Educational content about buying
• Tips for improving your position
• New programs and incentives

💡 **Helpful Resources**:
I can share guides on:
• Budget preparation and planning
• Market research strategies
• Financing options and programs
• Buying process education

🔄 **Future Possibilities**:
Circumstances change, and when they do, we'll be here to help. Sometimes the perfect opportunity just needs the right timing!

🌟 **Stay Connected**:
Even if we can't help right now, I'd love to:
• Send you market insights and tips
• Notify you of new opportunities
• Provide educational resources
• Keep you updated on industry changes

Thank you for reaching out, and I hope we can assist you in the future!

Would you like to receive our newsletter with helpful tips and market updates?"""
    
    return message

def build_fallback_offramp_message(lead: Any) -> str:
    """Build fallback off-ramp message when errors occur."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 Thank you for your interest in our property services.

I appreciate you reaching out to us. While I'm having some technical difficulties processing your request right now, I want to make sure you have access to helpful information.

📧 **Stay Informed**:
I'd love to send you:
• Market updates and insights
• Property search tips
• Educational resources
• New opportunity notifications

💡 **Helpful Resources**:
I can share guides on:
• Budget planning for home purchase
• Market research strategies
• Financing options
• Buying process education

🔄 **Next Steps**:
Please feel free to reach out again if you have:
• Specific questions about properties
• Budget and location details
• Timeline information
• Any other questions about buying

Thank you for your patience, and I hope we can assist you better soon!

Would you like to receive helpful resources and updates?"""
    
    return message

def handle_newsletter_opt_in(lead: Any, response: str) -> Dict[str, Any]:
    """
    Handle newsletter opt-in response from lead.
    
    Args:
        lead: Lead object
        response: Lead's response to newsletter offer
        
    Returns:
        Updated lead information and response
    """
    response_lower = response.lower().strip()
    
    # Check for positive responses
    positive_indicators = [
        "yes", "yeah", "sure", "ok", "okay", "absolutely",
        "definitely", "sounds good", "please do", "add me"
    ]
    
    negative_indicators = [
        "no", "nope", "not interested", "don't", "do not",
        "unsubscribe", "remove", "stop"
    ]
    
    if any(indicator in response_lower for indicator in positive_indicators):
        lead.newsletter_opt_in = True
        return {
            "opted_in": True,
            "message": "Great! I've added you to our newsletter. You'll receive helpful updates and tips regularly."
        }
    elif any(indicator in response_lower for indicator in negative_indicators):
        lead.newsletter_opt_in = False
        return {
            "opted_in": False,
            "message": "No problem! I won't add you to our newsletter. Feel free to reach out if you change your mind."
        }
    else:
        # Unclear response
        return {
            "opted_in": None,
            "message": "I'm not sure if you'd like to receive our newsletter. Just let me know with a simple 'yes' or 'no'!"
        }

def schedule_future_reengagement(lead: Any, timeline_months: int) -> Dict[str, Any]:
    """
    Schedule future re-engagement with the lead.
    
    Args:
        lead: Lead object
        timeline_months: Months until re-engagement
        
    Returns:
        Scheduling information
    """
    reengage_date = datetime.now() + timedelta(days=timeline_months * 30)
    
    return {
        "scheduled_date": reengage_date,
        "lead_id": lead.user_id,
        "reason": "future_reengagement",
        "message": f"I'll reach out again around {reengage_date.strftime('%B %d, %Y')} to see if your situation has changed."
    }


class OfframpAgent:
    """
    Offramp Agent class wrapper for testing compatibility.
    """
    
    def __init__(self):
        pass
    
    def process(self, state):
        """Process state through off-ramp"""
        return offramp_node(state)