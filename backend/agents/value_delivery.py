"""
Value Delivery Agent for Real Estate Lead Nurturing

Handles delivery of value-added content to qualified and nurturing leads:
- Property information delivery
- Market insights and neighborhood data
- Educational content about buying process
- Lead magnet delivery and tracking

Implements PRD Section 3.3: Value Delivery & Content Strategy
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response_sync
from utils.supabase_client import query_properties_db, get_config, save_lead
from tools.agent_tools import fetch_lead_magnet, send_instagram_message
from schemas.state import AgentState
from utils.observability import track_performance
from utils.audit import audit_log_event
import logging

logger = logging.getLogger(__name__)

@track_performance
def value_delivery_node(state: AgentState) -> Dict[str, Any]:
    """
    Value delivery agent that provides relevant content based on lead interests.
    
    Implements intelligent content delivery:
    - Property information for specific inquiries
    - Market insights for general interest
    - Educational content for first-time buyers
    - Lead magnets for nurturing leads
    
    Args:
        state: Current agent state with lead and context
        
    Returns:
        Updated state with value delivery content
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
        # Analyze user intent for value delivery
        intent = analyze_value_delivery_intent(lead.message, messages)
        
        # Route to appropriate value delivery function
        if intent["type"] == "property_info":
            result = deliver_property_information(lead, state, intent)
        elif intent["type"] == "market_insights":
            result = deliver_market_insights(lead, state, intent)
        elif intent["type"] == "educational_content":
            result = deliver_educational_content(lead, state, intent)
        elif intent["type"] == "lead_magnet":
            result = deliver_lead_magnet(lead, state, intent)
        else:
            # Default: provide general value content
            result = deliver_general_value_content(lead, state, intent)
        
        # Update lead with delivery tracking
        update_lead_delivery_tracking(lead, intent, result)
        
        # Log value delivery event
        audit_log_event("value_delivered", {
            "lead_id": lead.user_id,
            "intent_type": intent["type"],
            "content_type": result.get("content_type", "unknown"),
            "delivery_successful": result.get("success", False)
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in value delivery: {e}")
        
        # Fallback response
        fallback_message = build_fallback_value_message(lead)
        
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": fallback_message
        })
        
        lead.history.append({
            "message": "Fallback value delivery due to error",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "error": str(e)
        }

def analyze_value_delivery_intent(message: str, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze user message to determine value delivery intent.
    
    Args:
        message: Current user message
        conversation_history: Previous conversation messages
        
    Returns:
        Intent analysis with type and parameters
    """
    message_lower = message.lower()
    
    # Property information indicators
    property_keywords = [
        "property", "home", "house", "condo", "apartment",
        "details", "information", "tell me about", "show me",
        "address", "specific", "particular"
    ]
    
    # Market insights indicators
    market_keywords = [
        "market", "prices", "trends", "neighborhood", "area",
        "average", "statistics", "data", "insights"
    ]
    
    # Educational content indicators
    education_keywords = [
        "how to", "process", "steps", "guide", "tips",
        "first time", "beginner", "learn", "advice"
    ]
    
    # Lead magnet indicators
    magnet_keywords = [
        "guide", "checklist", "ebook", "download", "resource",
        "free", "template", "checklist"
    ]
    
    # Count keyword matches
    property_score = sum(1 for kw in property_keywords if kw in message_lower)
    market_score = sum(1 for kw in market_keywords if kw in message_lower)
    education_score = sum(1 for kw in education_keywords if kw in message_lower)
    magnet_score = sum(1 for kw in magnet_keywords if kw in message_lower)
    
    # Determine primary intent
    scores = {
        "property_info": property_score,
        "market_insights": market_score,
        "educational_content": education_score,
        "lead_magnet": magnet_score
    }
    
    primary_intent = max(scores, key=scores.get)
    
    # Extract parameters based on intent
    parameters = {}
    
    if primary_intent == "property_info":
        parameters = extract_property_parameters(message_lower)
    elif primary_intent == "market_insights":
        parameters = extract_market_parameters(message_lower)
    elif primary_intent == "educational_content":
        parameters = extract_education_parameters(message_lower)
    elif primary_intent == "lead_magnet":
        parameters = extract_magnet_parameters(message_lower)
    
    return {
        "type": primary_intent,
        "confidence": scores[primary_intent] / max(sum(scores.values()), 1),
        "parameters": parameters,
        "all_scores": scores
    }

def deliver_property_information(lead: Any, state: AgentState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deliver detailed property information based on user inquiry.
    
    Args:
        lead: Lead object
        state: Current agent state
        intent: Analyzed intent with parameters
        
    Returns:
        Updated state with property information
    """
    try:
        # Extract property parameters
        params = intent["parameters"]
        property_id = params.get("property_id")
        property_address = params.get("address")
        
        # Query properties based on lead criteria and specific parameters
        properties = []
        
        if lead.budget and lead.location:
            properties = query_properties_db(
                budget=lead.budget,
                location=lead.location,
                property_type=lead.property_type or ""
            )
        
        # Filter for specific property if requested
        target_property = None
        if property_id:
            target_property = next((p for p in properties if str(p.get("id")) == property_id), None)
        elif property_address:
            target_property = next((p for p in properties if property_address.lower() in p.get("address", "").lower()), None)
        
        # If no specific property found, use best matching property
        if not target_property and properties:
            target_property = properties[0]  # Use first/best match
        
        if not target_property:
            # No property found - provide helpful response
            message = build_no_property_message(lead, params)
        else:
            # Build detailed property information
            message = build_property_details_message(target_property, lead)
            
            # Mark property info as delivered
            lead.property_info_delivered = True
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        lead.history.append({
            "message": f"Delivered property information for {target_property.get('address', 'unknown property') if target_property else 'no matching property'}",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "content_type": "property_information",
            "success": True,
            "property_id": target_property.get("id") if target_property else None
        }
        
    except Exception as e:
        logger.error(f"Error delivering property information: {e}")
        return {
            "lead": lead,
            "messages": state.get("messages", []),
            "next_agent": "followup",
            "content_type": "property_information",
            "success": False,
            "error": str(e)
        }

def deliver_market_insights(lead: Any, state: AgentState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deliver market insights and neighborhood data.
    
    Args:
        lead: Lead object
        state: Current agent state
        intent: Analyzed intent with parameters
        
    Returns:
        Updated state with market insights
    """
    try:
        # Extract market parameters
        params = intent["parameters"]
        location = params.get("location") or lead.location
        insight_type = params.get("type", "general")  # prices, trends, neighborhood, general
        
        # Generate market insights using LLM
        insights_prompt = f"""
        Generate real estate market insights for {location or 'the requested area'}.
        
        Focus on: {insight_type}
        Lead's budget: ${lead.budget or 'not specified'}
        Property type: {lead.property_type or 'not specified'}
        
        Provide:
        1. Current market trends
        2. Average price ranges
        3. Neighborhood highlights
        4. Investment potential
        5. Buying tips for this area
        
        Keep it concise but informative (2-3 paragraphs max).
        """
        
        insights_content = get_llm_response_sync(insights_prompt)
        
        # Build market insights message
        message = build_market_insights_message(insights_content, location, insight_type, lead)
        
        # Mark market insights as delivered
        lead.market_insights_sent = True
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        lead.history.append({
            "message": f"Delivered market insights for {location or 'requested area'}",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "content_type": "market_insights",
            "success": True,
            "location": location,
            "insight_type": insight_type
        }
        
    except Exception as e:
        logger.error(f"Error delivering market insights: {e}")
        return {
            "lead": lead,
            "messages": state.get("messages", []),
            "next_agent": "followup",
            "content_type": "market_insights",
            "success": False,
            "error": str(e)
        }

def deliver_educational_content(lead: Any, state: AgentState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deliver educational content about the buying process.
    
    Args:
        lead: Lead object
        state: Current agent state
        intent: Analyzed intent with parameters
        
    Returns:
        Updated state with educational content
    """
    try:
        # Extract education parameters
        params = intent["parameters"]
        topic = params.get("topic", "general")  # financing, inspection, closing, general
        experience_level = params.get("experience", "first_time")  # first_time, experienced
        
        # Generate educational content using LLM
        education_prompt = f"""
        Create educational content about real estate {topic} for a {experience_level} buyer.
        
        Lead context:
        Budget: ${lead.budget or 'not specified'}
        Location: {lead.location or 'not specified'}
        Timeline: {lead.timeline or 'not specified'}
        
        Provide:
        1. Key concepts explained simply
        2. Step-by-step process
        3. Common pitfalls to avoid
        4. Pro tips for success
        5. Next steps to take
        
        Keep it practical and actionable (2-3 paragraphs max).
        """
        
        education_content = get_llm_response_sync(education_prompt)
        
        # Build educational message
        message = build_educational_content_message(education_content, topic, experience_level, lead)
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        lead.history.append({
            "message": f"Delivered educational content about {topic}",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "content_type": "educational_content",
            "success": True,
            "topic": topic,
            "experience_level": experience_level
        }
        
    except Exception as e:
        logger.error(f"Error delivering educational content: {e}")
        return {
            "lead": lead,
            "messages": state.get("messages", []),
            "next_agent": "followup",
            "content_type": "educational_content",
            "success": False,
            "error": str(e)
        }

def deliver_lead_magnet(lead: Any, state: AgentState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deliver appropriate lead magnet based on lead profile.
    
    Args:
        lead: Lead object
        state: Current agent state
        intent: Analyzed intent with parameters
        
    Returns:
        Updated state with lead magnet delivery
    """
    try:
        # Determine appropriate lead magnet type
        magnet_type = determine_lead_magnet_type(lead, intent)
        
        # Fetch lead magnet
        magnet_data = fetch_lead_magnet.invoke({"magnet_type": magnet_type})
        
        if not magnet_data:
            # Fallback if no magnet found
            message = build_fallback_magnet_message(lead)
        else:
            # Build lead magnet delivery message
            message = build_lead_magnet_message(magnet_data, lead)
            
            # Update lead with magnet tracking
            lead.lead_magnet_sent_at = datetime.now()
            lead.lead_magnet_type = magnet_type
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        lead.history.append({
            "message": f"Delivered lead magnet: {magnet_type}",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "content_type": "lead_magnet",
            "success": True,
            "magnet_type": magnet_type,
            "magnet_data": magnet_data
        }
        
    except Exception as e:
        logger.error(f"Error delivering lead magnet: {e}")
        return {
            "lead": lead,
            "messages": state.get("messages", []),
            "next_agent": "followup",
            "content_type": "lead_magnet",
            "success": False,
            "error": str(e)
        }

def deliver_general_value_content(lead: Any, state: AgentState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deliver general value content when specific intent is unclear.
    
    Args:
        lead: Lead object
        state: Current agent state
        intent: Analyzed intent with parameters
        
    Returns:
        Updated state with general value content
    """
    try:
        # Build general value message based on lead profile
        message = build_general_value_message(lead, intent)
        
        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        lead.history.append({
            "message": "Delivered general value content",
            "timestamp": datetime.now().isoformat(),
            "agent": "value_delivery"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "next_agent": "followup",
            "content_type": "general_value",
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error delivering general value content: {e}")
        return {
            "lead": lead,
            "messages": state.get("messages", []),
            "next_agent": "followup",
            "content_type": "general_value",
            "success": False,
            "error": str(e)
        }

# Helper functions for parameter extraction
def extract_property_parameters(message: str) -> Dict[str, Any]:
    """Extract property-specific parameters from message."""
    params = {}
    
    # Simple keyword extraction (can be enhanced with NLP)
    if "address" in message:
        # Extract address patterns (simplified)
        import re
        address_pattern = r'\d+\s+[^,.]+(?:street|st|ave|avenue|road|blvd|drive|lane|court|circle|way)'
        matches = re.findall(address_pattern, message)
        if matches:
            params["address"] = matches[0]
    
    if "id" in message or "#" in message:
        # Extract property ID patterns
        import re
        id_pattern = r'(?:id|#)\s*[:#]?\s*(\w+)'
        matches = re.findall(id_pattern, message)
        if matches:
            params["property_id"] = matches[0]
    
    return params

def extract_market_parameters(message: str) -> Dict[str, Any]:
    """Extract market insight parameters from message."""
    params = {}
    
    if "price" in message or "cost" in message:
        params["type"] = "prices"
    elif "trend" in message or "trending" in message:
        params["type"] = "trends"
    elif "neighborhood" in message or "area" in message:
        params["type"] = "neighborhood"
    else:
        params["type"] = "general"
    
    return params

def extract_education_parameters(message: str) -> Dict[str, Any]:
    """Extract educational content parameters from message."""
    params = {}
    
    if "financ" in message or "mortgage" in message:
        params["topic"] = "financing"
    elif "inspect" in message:
        params["topic"] = "inspection"
    elif "closing" in message:
        params["topic"] = "closing"
    elif "first time" in message or "beginner" in message:
        params["experience"] = "first_time"
    elif "experienced" in message or "seasoned" in message:
        params["experience"] = "experienced"
    else:
        params["topic"] = "general"
        params["experience"] = "first_time"
    
    return params

def extract_magnet_parameters(message: str) -> Dict[str, Any]:
    """Extract lead magnet parameters from message."""
    params = {}
    
    if "buyer" in message:
        params["type"] = "first_time_buyer_guide"
    elif "checklist" in message:
        params["type"] = "buying_checklist"
    elif "financ" in message:
        params["type"] = "financing_guide"
    else:
        params["type"] = "general_guide"
    
    return params

# Helper functions for message building
def build_property_details_message(property_data: Dict[str, Any], lead: Any) -> str:
    """Build detailed property information message."""
    address = property_data.get("address", "Beautiful Property")
    price = property_data.get("price", 0)
    bedrooms = property_data.get("bedrooms", "N/A")
    bathrooms = property_data.get("bathrooms", "N/A")
    sqft = property_data.get("square_feet", "N/A")
    description = property_data.get("description", "Wonderful property with great features")
    
    name = lead.name or "there"
    
    message = f"""Hi {name}! 🏠 Here are the details for the property you're interested in:

📍 **{address}**
💰 **Price**: ${price:,}
🛏️ **Bedrooms**: {bedrooms}
🚿 **Bathrooms**: {bathrooms}
📏 **Square Feet**: {sqft}

📝 **Description**: {description}

This property matches your criteria perfectly! Would you like to:
• Schedule a viewing to see it in person?
• Get more information about the neighborhood?
• See similar properties in the area?

Let me know what interests you most! 🎯"""
    
    return message

def build_market_insights_message(insights: str, location: str, insight_type: str, lead: Any) -> str:
    """Build market insights message."""
    name = lead.name or "there"
    area = location or "your area of interest"
    
    message = f"""Hi {name}! 📊 Here are the latest market insights for {area}:

{insights}

💡 **Key Takeaways**:
• These trends can help you make an informed decision
• Your budget of ${lead.budget or 'flexible'} positions you well in this market
• Now is a great time to explore options in this area

Would you like me to:
• Show you properties that fit this market analysis?
• Provide more specific neighborhood information?
• Share financing options for this price range?

I'm here to help you navigate this market successfully! 🚀"""
    
    return message

def build_educational_content_message(content: str, topic: str, experience_level: str, lead: Any) -> str:
    """Build educational content message."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 📚 Here's some helpful information about {topic}:

{content}

🎯 **Next Steps**:
• Apply these insights to your property search
• Consider how this affects your budget and timeline
• Feel free to ask me any follow-up questions

This knowledge will help you make confident decisions throughout your buying journey! 💪

What aspect of {topic} would you like to explore further?"""
    
    return message

def build_lead_magnet_message(magnet_data: Dict[str, Any], lead: Any) -> str:
    """Build lead magnet delivery message."""
    name = lead.name or "there"
    title = magnet_data.get("title", "Helpful Guide")
    description = magnet_data.get("description", "Valuable resource for your property search")
    delivery_text = magnet_data.get("delivery_text", "I've sent you a comprehensive guide")
    
    message = f"""Hi {name}! 🎁 I have the perfect resource for your property search:

📖 **{title}**

{description}

{delivery_text}

This guide will help you:
• Navigate the buying process with confidence
• Avoid common pitfalls
• Make informed decisions
• Save time and money

Keep an eye out for the delivery! 📬

Would you like me to:
• Send you additional resources?
• Schedule a consultation to discuss your specific needs?
• Update you on new properties matching your criteria?"""
    
    return message

def build_general_value_message(lead: Any, intent: Dict[str, Any]) -> str:
    """Build general value content message."""
    name = lead.name or "there"
    
    # Personalize based on lead information
    personalization = []
    
    if lead.budget:
        personalization.append(f"budget of ${lead.budget:,}")
    
    if lead.location:
        personalization.append(f"interest in {lead.location}")
    
    if lead.timeline:
        personalization.append(f"timeline of {lead.timeline}")
    
    personalization_text = ", ".join(personization) if personalization else "your property search"
    
    message = f"""Hi {name}! 👋 I'm here to help you find the perfect property based on your {personalization_text}.

🎯 **How I can assist you**:
• Show you properties that match your criteria
• Provide market insights for your target area
• Share educational content about the buying process
• Send you helpful guides and resources

🏠 **Your Current Profile**:
• Budget: ${lead.budget or 'Not specified'}
• Location: {lead.location or 'Not specified'}
• Timeline: {lead.timeline or 'Not specified'}
• Property Type: {lead.property_type or 'Not specified'}

What would you like to explore first? I can provide:
• Property listings and details
• Market trends and neighborhood information
• Buying guides and educational content
• Personalized recommendations

Just let me know what interests you most! 🚀"""
    
    return message

def build_no_property_message(lead: Any, params: Dict[str, Any]) -> str:
    """Build message when no specific property is found."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 🔍 I couldn't find the specific property you're asking about.

Let me help you in a different way:

🏠 **Available Options**:
• I can show you the best available properties in {lead.location or 'your target area'}
• Provide market insights for your budget range of ${lead.budget or 'flexible'}
• Share neighborhood information for areas you're considering

📋 **To help you better**, could you:
• Double-check the property address or ID?
• Let me know your specific criteria?
• Allow me to show you top matching properties?

I'm committed to finding you the perfect home! 🎯

What would you like to explore?"""
    
    return message

def build_fallback_magnet_message(lead: Any) -> str:
    """Build fallback message when no lead magnet is available."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 📚 I'd love to share some helpful resources with you.

While I prepare your personalized guide, here are some valuable tips:

🏠 **Property Search Tips**:
• Get pre-approved for financing first
• Make a list of must-have features
• Research neighborhoods thoroughly
• Visit multiple properties before deciding

📊 **Market Research**:
• Compare prices in your target area
• Consider future development plans
• Look at school ratings and amenities
• Check commute times to work

💡 **Next Steps**:
• I can send you detailed property information
• Provide market insights for your area
• Share educational content about buying

What would be most helpful for you right now?"""
    
    return message

def build_fallback_value_message(lead: Any) -> str:
    """Build fallback value message when errors occur."""
    name = lead.name or "there"
    
    message = f"""Hi {name}! 👋 I'm here to help you with your property search.

Based on what you've shared, I can assist you with:
• Finding properties that match your criteria
• Providing market insights and trends
• Sharing educational content about buying
• Answering any questions you have

I'm working to get you the most relevant information. In the meantime, what specific aspect of your property search would you like to explore?

🏠 Properties
📊 Market Data  
📚 Buying Guides
❓ Questions & Answers

What interests you most?"""
    
    return message

def determine_lead_magnet_type(lead: Any, intent: Dict[str, Any]) -> str:
    """Determine the most appropriate lead magnet type."""
    params = intent.get("parameters", {})
    
    # Use explicit type if provided
    if params.get("type"):
        return params["type"]
    
    # Determine based on lead profile
    if lead.timeline and "first" in lead.timeline.lower():
        return "first_time_buyer_guide"
    elif lead.budget and lead.budget < 300000:
        return "affordable_housing_guide"
    elif lead.budget and lead.budget > 500000:
        return "luxury_property_guide"
    elif lead.location and "downtown" in lead.location.lower():
        return "urban_living_guide"
    else:
        return "general_buying_guide"

def update_lead_delivery_tracking(lead: Any, intent: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Update lead with delivery tracking information."""
    intent_type = intent["type"]
    
    if intent_type == "property_info":
        lead.property_info_delivered = result.get("success", False)
    elif intent_type == "market_insights":
        lead.market_insights_sent = result.get("success", False)
    elif intent_type == "lead_magnet":
        if result.get("success", False):
            lead.lead_magnet_sent_at = datetime.now()
            lead.lead_magnet_type = result.get("magnet_type", "unknown")
    
    # Update last interaction
    lead.last_interaction_at = datetime.now()