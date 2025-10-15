import sys
import os
import asyncio
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_lead
from tools.handoffs import handoff_to_end
from tools.nurture import generate_nurture_action
from temporal.graph_client import get_graphiti_client
from schemas.state import AgentState
from typing import Dict, Any
from tools import compliance as compliance_tools
from tools.agent_tools import send_instagram_message

def followup_node(state: AgentState) -> Dict[str, Any]:
    """
    FollowUp agent node that nurtures low-scoring leads using temporal insights.
    
    Implements PRD Section 2.4: Intelligent Nurture with temporal triggers.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with followup message and next agent
    """
    lead = state["lead"]
    
    try:
        # Get temporal graph client for context-aware nurturing
        temporal_graph = get_graphiti_client()
        
        # Generate intelligent nurture action based on temporal context
        nurture_action = generate_nurture_action(
            lead=lead.model_dump(),
            temporal_graph=temporal_graph
        )
        
        # Extract the personalized message from nurture action
        followup_message = nurture_action.get("message", "Thank you for your interest! Here are some properties that might match your criteria.")
        
        # Run compliance check before sending message (PRD Section 2.6)
        compliance_result = asyncio.run(compliance_tools.fair_housing_evaluator(
            followup_message,
            {"lead_id": lead.user_id, "message_direction": "outbound"}
        ))
        
        # Handle compliance violations
        if compliance_result.get("blocked", False):
            # Use neutral alternative if provided
            followup_message = compliance_result.get("neutral_alternative",
                "Thank you for your interest! I'd be happy to help you find a property that meets your needs.")
            
            # Log compliance decision
            lead.history.append({
                "message": f"Compliance check blocked original message. Used alternative: {compliance_result.get('violations', [])}",
                "timestamp": datetime.now().isoformat(),
                "agent": "followup",
                "compliance_violation": True,
                "metadata": compliance_result
            })
        else:
            # Log compliance approval
            lead.history.append({
                "message": f"Compliance check passed: {compliance_result.get('status', 'approved')}",
                "timestamp": datetime.now().isoformat(),
                "agent": "followup",
                "compliance_passed": True
            })
        
        # Record the nurture event in temporal graph
        asyncio.run(temporal_graph.record_lead_event(
            lead_id=lead.user_id or lead.id,
            event_type="nurture",
            event_data={
                "strategy": nurture_action.get("type", "generic_followup"),
                "reasoning": nurture_action.get("reasoning", "Standard followup"),
                "priority": nurture_action.get("priority", "medium"),
                "has_new_matches": len(nurture_action.get("properties", [])) > 0
            }
        ))
        
        # Send the followup message with compliance check
        send_instagram_message.invoke({
            "user_id": lead.user_id,
            "message": followup_message
        })
        
        # Add the followup message to the lead's history
        lead.history.append({
            "message": followup_message,
            "timestamp": datetime.now().isoformat(),
            "agent": "followup",
            "metadata": {
                "nurture_strategy": nurture_action.get("type"),
                "priority": nurture_action.get("priority"),
                "new_properties_count": len(nurture_action.get("properties", []))
            }
        })
        
        # Update lead's last interaction timestamp
        lead.last_interaction_at = datetime.now().isoformat()
        
        # Save updated lead information
        save_lead(lead.model_dump())
        
        # End the conversation
        return {"lead": lead, "next_agent": "end"}
        
    except Exception as e:
        # Fallback to basic followup if temporal features fail
        followup_message = "Thank you for your interest! Here are some properties that might match your criteria."
        
        # Run compliance check on fallback message
        compliance_result = asyncio.run(compliance_tools.fair_housing_evaluator(
            followup_message,
            {"lead_id": lead.user_id, "message_direction": "outbound"}
        ))
        
        # Handle compliance violations in fallback
        if compliance_result.get("blocked", False):
            followup_message = compliance_result.get("neutral_alternative",
                "Thank you for your interest! I'd be happy to help you find a property that meets your needs.")
        
        # Send the followup message with compliance check
        send_instagram_message.invoke({
            "user_id": lead.user_id,
            "message": followup_message
        })
        
        lead.history.append({
            "message": followup_message,
            "timestamp": datetime.now().isoformat(),
            "agent": "followup",
            "metadata": {"error": str(e), "fallback_mode": True, "compliance_checked": True}
        })
        
        # Save updated lead information
        save_lead(lead.model_dump())
        
        # End the conversation
        return {"lead": lead, "next_agent": "end"}