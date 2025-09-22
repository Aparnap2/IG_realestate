import sys
import os
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response
from utils.supabase_client import query_properties_db, get_config
from utils.redis_client import cache_query_result, get_cached_query_result
from tools.handoffs import handoff_to_scheduler, handoff_to_followup
from schemas.state import AgentState
from typing import Dict, Any
from utils.observability import track_performance

@track_performance
def qualifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Qualifier agent node that scores leads based on criteria.
    
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
    
    # Query properties from DB based on lead criteria
    db_results = query_properties_db(
        lead.budget or 0,
        lead.location or "",
        lead.property_type or ""
    )
    
    # Cache the query results
    query = f"SELECT * FROM properties WHERE price <= {lead.budget} AND location = '{lead.location}' AND property_type = '{lead.property_type}'"
    cache_query_result(query, lead.user_id, db_results)
    
    # Get HITL threshold from config (default to 0.9)
    hitl_threshold = float(get_config("hitl_threshold", "0.9"))
    
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
    score_response = get_llm_response(prompt)
    
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
        # High-value lead, interrupt for HITL
        lead.history.append({
            "message": f"High-value lead (score: {score}, threshold: {hitl_threshold}), interrupting for HITL review",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "scheduler", "interrupt": True}
    elif score > 0.7:
        lead.history.append({
            "message": f"Lead qualified (score: {score}), sending to scheduler",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "scheduler"}
    else:
        lead.history.append({
            "message": f"Lead not qualified (score: {score}), sending to followup",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "followup"}