"""
Intelligent Nurture Tools - Context-Aware Lead Engagement

Implements PRD Section 2.4: Intelligent Nurture with temporal triggers.

Key Features:
- Property-matched alerts based on new inventory
- Temporal engagement tracking and re-engagement strategies
- Market update personalization
- Context-aware nurture message generation
- Engagement trajectory-driven actions
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import get_settings
from utils.audit import audit_log_event
from utils.supabase_client import supabase
from temporal.graph_client import get_graphiti_client

settings = get_settings()

def generate_nurture_action(
    lead: Dict[str, Any],
    temporal_graph: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Generate intelligent nurture action based on temporal context and lead behavior.
    
    Args:
        lead: Lead information and current state
        temporal_graph: Temporal knowledge graph client (optional)
        
    Returns:
        Dictionary with nurture action type, message, and reasoning
    """
    try:
        lead_id = lead.get("user_id") or lead.get("id")
        
        if not temporal_graph:
            temporal_graph = get_graphiti_client()
        
        # Get temporal context
        import asyncio
        engagement_trajectory = asyncio.run(
            temporal_graph.get_engagement_trajectory(lead_id)
        )
        
        interest_evolution = asyncio.run(
            temporal_graph.get_property_interest_evolution(lead_id)
        )
        
        # Check for new inventory matching criteria
        new_matches = get_new_inventory_matches(lead)
        
        # Determine nurture strategy
        nurture_strategy = _determine_nurture_strategy(
            lead, engagement_trajectory, interest_evolution, new_matches
        )
        
        # Generate action based on strategy
        action = _generate_action_for_strategy(
            nurture_strategy, lead, new_matches, engagement_trajectory
        )
        
        # Log nurture action
        audit_log_event("nurture_action_generated", {
            "lead_id": lead_id,
            "strategy": nurture_strategy,
            "action_type": action["type"],
            "engagement_trajectory": engagement_trajectory.get("trajectory"),
            "has_new_matches": len(new_matches) > 0
        })
        
        return action
        
    except Exception as e:
        audit_log_event("nurture_generation_error", {
            "error": str(e),
            "lead_id": lead.get("user_id")
        })
        
        return {
            "type": "generic_followup",
            "message": "Hi! Just checking in to see if you're still interested in finding the perfect property. Any updates on your search criteria?",
            "reasoning": f"Fallback nurture due to error: {str(e)}",
            "priority": "low"
        }

def get_new_inventory_matches(lead: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find new properties that match lead's criteria since last interaction.
    
    Args:
        lead: Lead information with criteria
        
    Returns:
        List of new matching properties
    """
    try:
        # Get lead's last interaction time
        last_interaction = lead.get("last_interaction_at")
        if not last_interaction:
            # If no last interaction, look back 30 days
            last_interaction = (datetime.now() - timedelta(days=30)).isoformat()
        
        # Query for new properties
        query = supabase.table("properties").select("*")
        
        # Apply lead's criteria
        if lead.get("budget"):
            query = query.lte("price", lead["budget"])
        
        if lead.get("location"):
            query = query.eq("location", lead["location"])
        
        if lead.get("property_type"):
            query = query.eq("property_type", lead["property_type"])
        
        # Only new properties since last interaction
        query = query.gte("created_at", last_interaction)
        
        response = query.execute()
        new_properties = response.data or []
        
        # Rank by relevance to lead
        ranked_properties = _rank_properties_by_relevance(new_properties, lead)
        
        return ranked_properties[:5]  # Return top 5 matches
        
    except Exception as e:
        audit_log_event("new_inventory_error", {
            "error": str(e),
            "lead_id": lead.get("user_id")
        })
        return []

def _determine_nurture_strategy(
    lead: Dict[str, Any],
    engagement_trajectory: Dict[str, Any],
    interest_evolution: Dict[str, Any],
    new_matches: List[Dict[str, Any]]
) -> str:
    """
    Determine the best nurture strategy based on lead context.
    
    Returns:
        Strategy name
    """
    try:
        trajectory = engagement_trajectory.get("trajectory", "stable")
        recent_activity = engagement_trajectory.get("recent_activity", 0)
        days_since_last = _calculate_days_since_last_interaction(lead)
        
        # Strategy decision tree
        if new_matches and len(new_matches) >= 2:
            return "new_inventory_alert"
        
        elif trajectory == "cooling" and days_since_last > 14:
            return "re_engagement_with_context"
        
        elif trajectory == "escalating" and recent_activity >= 3:
            return "high_engagement_acceleration"
        
        elif days_since_last > 45:
            return "long_term_nurture"
        
        elif _has_budget_evolution(interest_evolution):
            return "budget_evolution_followup"
        
        elif _has_location_expansion(interest_evolution):
            return "location_expansion_suggestion"
        
        elif days_since_last > 7 and days_since_last <= 21:
            return "standard_followup"
        
        else:
            return "market_update"
            
    except Exception:
        return "generic_followup"

def _generate_action_for_strategy(
    strategy: str,
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate specific action based on nurture strategy."""
    
    strategy_generators = {
        "new_inventory_alert": _generate_new_inventory_alert,
        "re_engagement_with_context": _generate_re_engagement_message,
        "high_engagement_acceleration": _generate_acceleration_message,
        "long_term_nurture": _generate_long_term_nurture,
        "budget_evolution_followup": _generate_budget_evolution_message,
        "location_expansion_suggestion": _generate_location_expansion,
        "standard_followup": _generate_standard_followup,
        "market_update": _generate_market_update,
        "generic_followup": _generate_generic_followup
    }
    
    generator = strategy_generators.get(strategy, _generate_generic_followup)
    
    return generator(lead, new_matches, engagement_trajectory)

def _generate_new_inventory_alert(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate new inventory alert message."""
    
    property_summaries = []
    for prop in new_matches[:3]:  # Top 3 properties
        summary = f"• {prop.get('property_type', 'Property')} in {prop.get('location', 'great location')} - ${prop.get('price', 0):,}"
        if prop.get("amenities"):
            amenities = prop["amenities"]
            if amenities.get("pool"):
                summary += " (Pool)"
            if amenities.get("gym"):
                summary += " (Gym)"
        property_summaries.append(summary)
    
    message = f"Great news! {len(new_matches)} new properties just listed that match your criteria:\n\n"
    message += "\n".join(property_summaries)
    message += f"\n\nThese are fresh on the market and likely to move quickly. Would you like to schedule viewings?"
    
    return {
        "type": "new_inventory_alert",
        "message": message,
        "properties": new_matches,
        "reasoning": f"Found {len(new_matches)} new matches since last interaction",
        "priority": "high",
        "call_to_action": "schedule_viewing"
    }

def _generate_re_engagement_message(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate re-engagement message for cooling leads."""
    
    days_since = _calculate_days_since_last_interaction(lead)
    
    # Reference past interests
    budget = lead.get("budget")
    location = lead.get("location")
    
    message = f"Hi! It's been {days_since} days since we last spoke about your property search"
    
    if location and budget:
        message += f" for properties in {location} around ${budget:,}"
    
    message += ". I wanted to check in - are you still looking, or have your needs changed?\n\n"
    
    if new_matches:
        message += f"I noticed {len(new_matches)} new properties that might interest you have come on the market recently. "
    
    message += "The market has been active lately, and I'd hate for you to miss out on great opportunities."
    
    return {
        "type": "re_engagement",
        "message": message,
        "reasoning": f"Re-engaging cooling lead after {days_since} days",
        "priority": "medium",
        "call_to_action": "update_criteria"
    }

def _generate_acceleration_message(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate message for highly engaged leads."""
    
    recent_activity = engagement_trajectory.get("recent_activity", 0)
    
    message = f"I can see you're actively searching - you've been very engaged recently! "
    message += f"Since you're serious about finding the right property, I want to make sure you're seeing the best options first.\n\n"
    
    if new_matches:
        message += f"I've identified {len(new_matches)} properties that closely match your criteria. "
        message += f"Given the current market pace, would you like me to arrange priority viewings this week?"
    else:
        message += f"While I don't have new matches right now, I'm monitoring the market closely for you. "
        message += f"Should I expand the search slightly to include more options, or are you happy with the current criteria?"
    
    return {
        "type": "high_engagement_acceleration",
        "message": message,
        "reasoning": f"Accelerating for highly engaged lead ({recent_activity} recent interactions)",
        "priority": "high",
        "call_to_action": "priority_scheduling"
    }

def _generate_long_term_nurture(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate long-term nurture message."""
    
    days_since = _calculate_days_since_last_interaction(lead)
    
    message = f"Hi! I hope you're doing well. It's been about {days_since // 30} months since we discussed your property search. "
    message += f"I wanted to reach out because the market has evolved quite a bit since then.\n\n"
    
    if lead.get("location"):
        message += f"In {lead['location']}, we've seen some interesting trends that might affect your search. "
    
    message += f"Are you still looking, or have your housing needs changed? I'd love to catch up and see how I can help."
    
    return {
        "type": "long_term_nurture",
        "message": message,
        "reasoning": f"Long-term nurture after {days_since} days of inactivity",
        "priority": "low",
        "call_to_action": "reconnect"
    }

def _generate_budget_evolution_message(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate message based on budget evolution."""
    
    current_budget = lead.get("budget", 0)
    
    message = f"I've been tracking your search and noticed your budget considerations have evolved. "
    message += f"With your current range around ${current_budget:,}, there are some great opportunities available.\n\n"
    
    if new_matches:
        message += f"I found {len(new_matches)} properties that align well with your updated criteria. "
    
    message += f"Would you like to see what's available in this range, or should we discuss adjusting the search parameters?"
    
    return {
        "type": "budget_evolution",
        "message": message,
        "reasoning": "Budget preferences have evolved over time",
        "priority": "medium",
        "call_to_action": "review_options"
    }

def _generate_location_expansion(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate location expansion suggestion."""
    
    current_location = lead.get("location", "your preferred area")
    
    message = f"I've been monitoring the market in {current_location} and wanted to share an insight. "
    message += f"There are some excellent properties in nearby areas that offer great value and might meet your needs perfectly.\n\n"
    
    # Suggest nearby areas (simplified)
    nearby_areas = _get_nearby_areas(current_location)
    if nearby_areas:
        message += f"Areas like {', '.join(nearby_areas)} have similar amenities but potentially better inventory. "
    
    message += f"Would you be open to exploring a slightly wider area for your search?"
    
    return {
        "type": "location_expansion",
        "message": message,
        "reasoning": "Suggesting location expansion based on interest patterns",
        "priority": "medium",
        "call_to_action": "expand_search"
    }

def _generate_standard_followup(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate standard follow-up message."""
    
    message = f"Hi! I wanted to check in on your property search. "
    
    if new_matches:
        message += f"I have {len(new_matches)} new properties that might interest you. "
    
    message += f"How is your search going? Any updates on your timeline or criteria?"
    
    return {
        "type": "standard_followup",
        "message": message,
        "reasoning": "Standard follow-up timing",
        "priority": "medium",
        "call_to_action": "status_update"
    }

def _generate_market_update(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate market update message."""
    
    location = lead.get("location", "your area")
    
    message = f"Market Update for {location}: I wanted to share some insights that might be relevant to your search.\n\n"
    message += f"Recent trends show good opportunities for buyers in your criteria range. "
    
    if lead.get("budget"):
        message += f"Properties around ${lead['budget']:,} are seeing reasonable market activity. "
    
    message += f"Would you like me to send you a detailed market report, or shall we schedule a call to discuss current opportunities?"
    
    return {
        "type": "market_update",
        "message": message,
        "reasoning": "Providing market context and value",
        "priority": "medium",
        "call_to_action": "market_discussion"
    }

def _generate_generic_followup(
    lead: Dict[str, Any],
    new_matches: List[Dict[str, Any]],
    engagement_trajectory: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate generic follow-up message."""
    
    return {
        "type": "generic_followup",
        "message": "Hi! Just checking in to see how your property search is going. Is there anything I can help you with?",
        "reasoning": "Generic follow-up as fallback",
        "priority": "low",
        "call_to_action": "general_inquiry"
    }

# Helper functions

def _calculate_days_since_last_interaction(lead: Dict[str, Any]) -> int:
    """Calculate days since last interaction."""
    try:
        last_interaction = lead.get("last_interaction_at")
        if not last_interaction:
            return 30  # Default assumption
        
        last_time = datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))
        return (datetime.now() - last_time).days
        
    except Exception:
        return 30

def _has_budget_evolution(interest_evolution: Dict[str, Any]) -> bool:
    """Check if lead's budget has evolved over time."""
    try:
        budget_trend = interest_evolution.get("budget_trend", {})
        return budget_trend.get("trend") in ["increasing", "decreasing"]
    except Exception:
        return False

def _has_location_expansion(interest_evolution: Dict[str, Any]) -> bool:
    """Check if lead has shown interest in multiple locations."""
    try:
        location_prefs = interest_evolution.get("location_preferences", {})
        total_locations = sum(len(locs) for locs in location_prefs.values())
        return total_locations > 2
    except Exception:
        return False

def _rank_properties_by_relevance(
    properties: List[Dict[str, Any]],
    lead: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Rank properties by relevance to lead's criteria."""
    try:
        scored_properties = []
        
        for prop in properties:
            score = 0
            
            # Budget alignment
            if lead.get("budget") and prop.get("price"):
                budget_ratio = prop["price"] / lead["budget"]
                if 0.8 <= budget_ratio <= 1.0:  # Within 80-100% of budget
                    score += 3
                elif 0.6 <= budget_ratio <= 1.2:  # Within 60-120% of budget
                    score += 2
                else:
                    score += 1
            
            # Location match
            if lead.get("location") and prop.get("location"):
                if lead["location"].lower() in prop["location"].lower():
                    score += 2
            
            # Property type match
            if lead.get("property_type") and prop.get("property_type"):
                if lead["property_type"].lower() == prop["property_type"].lower():
                    score += 2
            
            # Amenities bonus
            amenities = prop.get("amenities", {})
            if amenities.get("pool"):
                score += 1
            if amenities.get("gym"):
                score += 1
            
            scored_properties.append((prop, score))
        
        # Sort by score descending
        scored_properties.sort(key=lambda x: x[1], reverse=True)
        
        return [prop for prop, score in scored_properties]
        
    except Exception:
        return properties

def _get_nearby_areas(location: str) -> List[str]:
    """Get nearby areas for location expansion suggestions."""
    nearby_map = {
        "miami": ["Coral Gables", "Aventura", "Doral"],
        "orlando": ["Winter Park", "Altamonte Springs"],
        "tampa": ["St. Petersburg", "Clearwater"],
        "jacksonville": ["Ponte Vedra", "Neptune Beach"]
    }
    
    location_lower = location.lower()
    for city, nearby in nearby_map.items():
        if city in location_lower:
            return nearby[:2]  # Return first 2 suggestions
    
    return []