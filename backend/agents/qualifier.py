import sys
import os
import types
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response_sync
from utils.supabase_client import query_properties_db, get_config, save_lead
from utils.redis_client import cache_query_result, get_cached_query_result
from tools.handoffs import handoff_to_scheduler, handoff_to_followup
from schemas.state import AgentState
from typing import Dict, Any
from utils.observability import track_performance

# Provide legacy module path for tests and backward compatibility
if "agents" not in sys.modules:
    legacy_agents_module = types.ModuleType("agents")
    legacy_agents_module.__path__ = []  # type: ignore[attr-defined]
    sys.modules["agents"] = legacy_agents_module

sys.modules["agents.qualifier"] = sys.modules[__name__]

@track_performance
def qualifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Qualifier agent node that scores leads based on criteria.
    
    Enhanced with partial information handling according to PRD specifications:
    - Detects missing information and asks clarification questions
    - Handles budget mismatches with alternative suggestions
    - Provides waitlist options when no properties match
    - Only qualifies complete, qualified leads
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with qualification score and next agent
    """
    lead = state["lead"]
    
    # Add the incoming message to the lead's history
    lead.history.append({
        "message": lead.message,
        "timestamp": datetime.now().isoformat(),
        "agent": "user"
    })
    
    # Check for missing critical information (PRD Section 3.2)
    missing_info = check_missing_information(lead)
    if missing_info:
        result = handle_missing_information(lead, missing_info, state)
        if result.get("requires_more_info"):
            return result
    
    # Build cache key for property search
    cache_key = (
        f"properties:{lead.budget or 'na'}:{lead.location or 'na'}:"
        f"{lead.property_type or 'na'}"
    )

    # Attempt to fetch cached query results first
    try:
        db_results = get_cached_query_result(cache_key, lead.user_id)
    except Exception as cache_error:
        print(f"Error retrieving cached query result: {cache_error}")
        db_results = None

    # Query properties from DB if not cached
    if not db_results:
        db_results = query_properties_db(
            lead.budget or 0,
            lead.location or "",
            lead.property_type or ""
        )

        # Cache the query results for future lookups (24h TTL handled in utility)
        try:
            cache_query_result(cache_key, lead.user_id, db_results)
        except Exception as cache_error:
            print(f"Error caching query result: {cache_error}")
    
    # Check if no properties match the criteria
    if not db_results:
        return handle_no_matching_properties(lead, state)
    
    # Check for budget mismatches
    budget_analysis = detect_budget_mismatch(lead, db_results)
    if budget_analysis.get("detected"):
        # Build budget mismatch message
        recommendations = budget_analysis.get("recommendations", [])
        rec_text = "\n".join([f"• {rec}" for rec in recommendations])
        
        message = f"""Hi {lead.name or 'there'}! 💰 I found {len(db_results)} properties in {lead.location}, but there's a budget consideration:

{budget_analysis.get("suggest_message", "")}

Here are your options:
{rec_text}

Would you like to:
1. See the {budget_analysis.get("affordable_options", 0)} properties slightly closer to your budget?
2. Adjust your search criteria?
3. Get notified when new properties in your range become available?"""

        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        # Update lead history
        lead.history.append({
            "message": f"Budget mismatch detected: {budget_analysis}",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "budget_mismatch": budget_analysis,
            "requires_more_info": True,
            "next_agent": "qualifier"
        }
    
    # Get thresholds from configuration (with sensible defaults)
    hitl_threshold = float(get_config("hitl_threshold", "0.9"))
    scheduler_threshold = float(get_config("scheduler_threshold", "0.7"))
    
    # Create prompt for LLM to score the lead with explicit scoring rubric
    prompt = f"""
    Score this lead (0-1) for real estate interest based on:
    Budget: {lead.budget}
    Location: {lead.location}
    Type: {lead.property_type}
    Timeline: {lead.timeline}
    
    DB properties: {db_results}
    
    Scoring Rubric:
    - Budget > $500k: +0.3
    - Budget > $300k: +0.2
    - Budget > $100k: +0.1
    - Location and property type match DB: +0.3
    - Timeline < 6 months: +0.1
    
    Provide your response as a JSON object with the following structure:
    {{
        "score": 0.8,
        "reasoning": "Explanation of the score"
    }}
    """
    
    # Get LLM response
    score_response = get_llm_response_sync(prompt)
    
    # Parse the score from JSON response
    try:
        import json
        score_data = json.loads(score_response)
        score = float(score_data["score"])
        if score > 1.0:
            score = 1.0
        elif score < 0.0:
            score = 0.0
    except:
        # Fallback to simple parsing if JSON fails
        try:
            score = float(score_response.strip())
            if score > 1.0:
                score = 1.0
            elif score < 0.0:
                score = 0.0
        except:
            score = 0.5  # Default score if parsing fails
    
    # Add qualification message to the lead's history
    lead.history.append({
        "message": f"Lead qualified with score: {score}",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    # Update lead with score
    lead.qualified_score = score
    
    # Determine next agent based on score
    # According to PRD: > threshold or budget >$500k triggers HITL
    if score > hitl_threshold or (lead.budget and lead.budget > 500000):
        lead.history.append({
            "message": f"High-value lead (score: {score}, threshold: {hitl_threshold}), interrupting for HITL review",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        try:
            save_lead(lead.model_dump())
        except Exception as save_error:
            print(f"Error saving lead during HITL handoff: {save_error}")
        return {"lead": lead, "next_agent": "scheduler", "interrupt": True}
    elif score > scheduler_threshold:
        lead.history.append({
            "message": f"Lead qualified (score: {score}), sending to scheduler",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        try:
            save_lead(lead.model_dump())
        except Exception as save_error:
            print(f"Error saving lead during scheduler handoff: {save_error}")
        return {"lead": lead, "next_agent": "scheduler"}
    else:
        lead.history.append({
            "message": f"Lead not qualified (score: {score}), sending to followup",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        try:
            save_lead(lead.model_dump())
        except Exception as save_error:
            print(f"Error saving lead during followup handoff: {save_error}")
        return {"lead": lead, "next_agent": "followup"}

def check_missing_information(lead: Any) -> Dict[str, bool]:
    """
    Check for missing critical information needed for qualification.
    
    Returns a dict of missing fields and their status.
    """
    missing = {}
    
    # Check budget - critical for property search
    if not lead.budget or lead.budget <= 0:
        missing["budget"] = True
    
    # Check location - essential for property search
    if not lead.location or lead.location.strip() == "":
        missing["location"] = True
    
    # Check property preferences (bedrooms or property type)
    bedrooms_missing = not lead.desired_bedrooms or lead.desired_bedrooms <= 0
    property_type_missing = not lead.property_type or lead.property_type.strip() == ""
    
    if bedrooms_missing and property_type_missing:
        missing["property_preferences"] = True
    
    return missing

def handle_missing_information(lead: Any, missing_info: Dict[str, bool], state: AgentState) -> Dict[str, Any]:
    """
    Handle missing information by asking clarification questions.
    
    Returns a state dict that includes clarification questions.
    """
    questions = []
    
    if missing_info.get("budget"):
        questions.append("What's your approximate budget for this purchase?")
    
    if missing_info.get("location"):
        if questions:  # If we already have budget context
            questions.append("What specific area or neighborhood are you interested in?")
        else:
            questions.append("What area or neighborhood are you looking for properties in?")
    
    if missing_info.get("property_preferences"):
        if questions:  # Context already established
            questions.append("What type of property are you looking for (apartment, house, condo)?")
            questions.append("How many bedrooms do you need?")
        else:
            questions.append("What kind of property are you looking for and how many bedrooms?")
    
    # Build clarification message
    if len(questions) == 1:
        message = f"Hi {lead.name or 'there'}! 👋 To help you find the perfect property, could you let me know {questions[0].lower()}"
    else:
        question_list = " ".join([q.rstrip("?") + "," for q in questions[:-1]]) + f" and {questions[-1].rstrip('.?')}?"
        message = f"Hi {lead.name or 'there'}! 👋 To better assist you, could you let me know {question_list.lower()} This will help me find the best options for you."
    
    # Add the clarification to messages
    if "messages" not in state:
        state["messages"] = []
    
    state["messages"].append({
        "role": "assistant", 
        "content": message
    })
    
    # Update lead history
    lead.history.append({
        "message": f"Requests clarification for: {', '.join(missing_info.keys())}",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    return {
        "lead": lead,
        "messages": state["messages"],
        "requires_more_info": True,
        "missing_info": missing_info,
        "next_agent": "qualifier"  # Stay in qualifier until we have complete info
    }

def detect_budget_mismatch(lead: Any, properties: list) -> Dict[str, Any]:
    """
    Detect and handle budget mismatches with available properties.
    
    Returns analysis of budget compatibility and suggestions.
    """
    if not properties:
        return {"mismatch": False, "message": "No properties found"}
    
    # Calculate property price range
    prices = [prop.get("price", 0) for prop in properties if prop.get("price")]
    if not prices:
        return {"mismatch": False, "message": "Property prices not available"}
    
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    # Check if lead's budget is too low for available options
    if lead.budget and lead.budget < min_price:
        shortfall_pct = ((min_price - lead.budget) / lead.budget) * 100
        suggestion = f"Properties in your criteria range from ${min_price:,.0f} to ${max_price:,.0f}, which is about {shortfall_pct:.0f}% higher than your budget."
        
        # Find properties closer to budget
        affordable_options = [prop for prop in properties if prop.get("price", 0) <= lead.budget * 1.1]  # Within 10%
        
        return {
            "mismatch": True,
            "detected": True,
            "budget": lead.budget,
            "price_range": {"min": min_price, "max": max_price, "avg": avg_price},
            "shortfall_pct": shortfall_pct,
            "suggest_message": suggestion,
            "affordable_options": len(affordable_options),
            "recommendations": _generate_budget_mismatch_recommendations(lead, properties)
        }
    
    return {
        "mismatch": False,
        "detected": False,
        "price_range": {"min": min_price, "max": max_price, "avg": avg_price}
    }

def _generate_budget_mismatch_recommendations(lead: Any, properties: list) -> list:
    """Generate recommendations for budget mismatch scenarios."""
    recommendations = []
    
    if not lead.budget:
        return recommendations
    
    # Find smaller properties within budget
    smaller_properties = []
    for prop in properties:
        if prop.get("price", 0) <= lead.budget:
            bedrooms = prop.get("bedrooms", 0)
            if bedrooms and bedrooms > 0:  # Valid bedroom count
                smaller_properties.append(prop)
    
    if smaller_properties:
        min_bedrooms = min(prop.get("bedrooms", 0) for prop in smaller_properties)
        recommendations.append(f"Consider {min_bedrooms}-bedroom options within your budget")
    
    # Consider higher budget
    min_price = min(prop.get("price", 0) for prop in properties)
    if min_price > lead.budget:
        needed_budget = min_price * 0.8  # Suggest 80% of min price as target
        recommendations.append(f"Properties in your area start around ${min_price:,.0f}. Consider a budget of ${needed_budget:,.0f}+")
    
    # Suggest waitlist
    recommendations.append("Join our waitlist for new properties matching your criteria")
    
    return recommendations[:3]  # Top 3 recommendations

def handle_no_matching_properties(lead: Any, state: AgentState) -> Dict[str, Any]:
    """
    Handle scenario where no properties match the lead's criteria.
    
    Waitlist/Alert handling per PRD Section 3.2.
    """
    message = f"""Hi {lead.name or 'there'}! 👋 

I don't currently have properties matching your exact criteria. Here are your options:

🔔 **Get Notified**: Join our waitlist and I'll alert you when new properties matching your needs become available.

🎯 **Broaden Search**: Would you be open to:
   • Expanding your budget range
   • Considering nearby neighborhoods  
   • Looking at properties with slightly different features

📱 **Personal Consultation**: I can schedule a free consultation to discuss alternatives.

Would you like me to add you to our waitlist for: {lead.budget or 'flexible budget'}, {lead.location or 'your preferred area'}, {lead.desired_bedrooms or 'your preferred bedrooms'} bedrooms?"""

    # Add to messages
    if "messages" not in state:
        state["messages"] = []
    
    state["messages"].append({
        "role": "assistant",
        "content": message
    })
    
    # Update lead history
    lead.history.append({
        "message": f"No matching properties found - offered waitlist and alternatives",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    return {
        "lead": lead,
        "messages": state["messages"],
        "no_properties_found": True,
        "requires_more_info": True,  # Need response about waitlist
        "next_agent": "qualifier"
    }