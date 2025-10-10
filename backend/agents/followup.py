import sys
import os
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_lead
from tools.handoffs import handoff_to_end
from schemas.state import AgentState
from typing import Dict, Any

def followup_node(state: AgentState) -> Dict[str, Any]:
    """
    FollowUp agent node that nurtures low-scoring leads.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with followup message and next agent
    """
    lead = state["lead"]
    
    # Send a followup message (simplified implementation)
    # In a real implementation, this would integrate with Meta APIs
    # to send messages via Instagram
    
    followup_message = "Thank you for your interest! Here are some properties that might match your criteria."
    
    # Add the followup message to the lead's history
    lead.history.append({
        "message": followup_message,
        "timestamp": datetime.now().isoformat(),
        "agent": "followup"
    })
    
    # Save updated lead information
    save_lead(lead.model_dump())
    
    # End the conversation
    return {"lead": lead, "next_agent": "end"}