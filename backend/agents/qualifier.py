from ..utils.llm_client import get_llm_response
from ..utils.supabase_client import query_properties_db
from ..utils.redis_client import cache_query_result, get_cached_query_result
from ..tools.handoffs import handoff_to_scheduler, handoff_to_followup
from ..schemas.state import AgentState
from typing import Dict, Any

def qualifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Qualifier agent node that scores leads based on criteria.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with qualification score and next agent
    """
    lead = state["lead"]
    
    # Query properties from DB based on lead criteria
    db_results = query_properties_db(
        lead.budget or 0,
        lead.location or "",
        lead.property_type or ""
    )
    
    # Cache the query results
    query = f"SELECT * FROM properties WHERE price <= {lead.budget} AND location = '{lead.location}' AND property_type = '{lead.property_type}'"
    cache_query_result(query, lead.user_id, db_results)
    
    # Create prompt for LLM to score the lead
    prompt = f"""
    Score this lead (0-1) for real estate interest based on:
    Budget: {lead.budget}
    Location: {lead.location}
    Type: {lead.property_type}
    Timeline: {lead.timeline}
    
    DB properties: {db_results}
    
    High score if budget >$100k, location/type match, timeline <6 months.
    """
    
    # Get LLM response
    score_text = get_llm_response(prompt)
    
    # Parse the score (this is a simplified parser)
    try:
        score = float(score_text.strip())
        if score > 1.0:
            score = 1.0
        elif score < 0.0:
            score = 0.0
    except:
        score = 0.5  # Default score if parsing fails
    
    # Update lead with score
    lead.qualified_score = score
    
    # Determine next agent based on score
    if score > 0.7:
        if lead.budget and lead.budget > 500000:
            # High-value lead, interrupt for HITL
            return {"lead": lead, "next_agent": "scheduler", "interrupt": True}
        else:
            return {"lead": lead, "next_agent": "scheduler"}
    else:
        return {"lead": lead, "next_agent": "followup"}