"""
Main workflow module for the Vertical Real Estate Revenue Acceleration Platform.

This module provides the entry point for creating the LangGraph workflow
according to PRD specifications with Router Agent and compliance gates.
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.agents.prd_compliant_workflow import create_prd_compliant_workflow
from backend.agents.router import RouterAgent, route_to_agent
from utils.redis_client import test_redis_connection
from config import get_settings

settings = get_settings()

def create_workflow():
    """
    Create the main LangGraph workflow for lead processing.
    
    This function creates a PRD-compliant workflow with:
    - Router Agent (NEW) - Intent classification and compliance gates
    - Three ReAct agents (Qualifier, Scheduler, FollowUp)
    - Redis checkpointer for state persistence
    - HITL interrupts for high-value leads and compliance violations
    - Proper handoff mechanisms with routing logic
    - Database query tools with caching
    - Immutable audit logging
    
    Returns:
        Compiled LangGraph workflow with Router as entry point
    """
    # Test Redis connection first
    if not test_redis_connection():
        raise RuntimeError("Redis connection failed. Please ensure Redis is running.")
    
    # Check if Router Agent is enabled
    if settings.ENABLE_ROUTER_AGENT:
        # Create new workflow with Router Agent as entry point
        return create_router_enabled_workflow()
    else:
        # Fallback to original workflow for backward compatibility
        return create_prd_compliant_workflow()

def create_router_enabled_workflow():
    """
    Create workflow with Router Agent as entry point.
    
    Flow: Router → (Qualifier|Scheduler|FollowUp|Human) → END
    """
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.redis import RedisSaver
    from schemas.state import AgentState
    from utils.redis_client import redis_client
    from backend.agents.prd_compliant_workflow import QualifierAgent, SchedulerAgent, FollowUpAgent
    
    # Initialize agents
    router = RouterAgent()
    qualifier = QualifierAgent()
    scheduler = SchedulerAgent()
    followup = FollowUpAgent()
    
    # Create Redis checkpointer with graceful fallback for tests
    try:
        checkpointer = RedisSaver(redis_client=redis_client)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    
    # Define agent nodes
    async def router_node(state: AgentState) -> dict:
        """Router agent node with compliance gates"""
        return await router.process(state)
    
    def qualifier_node(state: AgentState) -> dict:
        """Enhanced qualifier agent node"""
        return qualifier.process(state)
    
    def scheduler_node(state: AgentState) -> dict:
        """Scheduler agent node"""
        return scheduler.process(state)
    
    def followup_node(state: AgentState) -> dict:
        """Follow-up agent node"""
        return followup.process(state)
    
    def human_node(state: AgentState) -> dict:
        """Human-in-the-loop node for review"""
        from utils.audit import audit_log_event
        
        lead = state["lead"]
        audit_log_event("human_review_required", {
            "lead_id": lead.user_id,
            "reason": state.get("compliance_flags", ["manual_review"]),
            "agent_decision": state.get("agent_decision", {})
        })
        
        # In production, this would pause for human input
        # For now, we'll route to followup as safe fallback
        state["human_feedback"] = "approved"  # Simulate approval
        state["current_agent"] = "followup"
        
        return state
    
    def error_handler_node(state: AgentState) -> dict:
        """Error handling node"""
        from utils.audit import audit_log_event
        
        error = state.get("error", "Unknown error")
        audit_log_event("workflow_error", {
            "error": error,
            "lead_id": state["lead"].user_id,
            "retry_count": state.get("retry_count", 0)
        })
        
        # Route to human review on persistent errors
        state["requires_human_review"] = True
        state["current_agent"] = "human"
        
        return state
    
    # Create the workflow graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("qualifier", qualifier_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("followup", followup_node)
    workflow.add_node("human", human_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set Router as entry point (PRD requirement)
    workflow.set_entry_point("router")
    
    # Add conditional edges from Router
    workflow.add_conditional_edges(
        "router",
        route_to_agent,  # Uses the routing function from router.py
        {
            "qualifier": "qualifier",
            "scheduler": "scheduler", 
            "followup": "followup",
            "human": "human",
            "error_handler": "error_handler"
        }
    )
    
    # Add edges from specialist agents
    workflow.add_edge("qualifier", END)
    workflow.add_edge("scheduler", END)
    workflow.add_edge("followup", END)
    workflow.add_edge("human", END)
    workflow.add_edge("error_handler", END)
    
    # Compile with checkpointer and interrupts
    interrupts = ["human"]  # Always interrupt for human review
    if settings.ENABLE_COMPLIANCE_CHECKS:
        interrupts.append("scheduler")  # Interrupt scheduler for high-value leads
    
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupts
    )

# For backward compatibility
def get_workflow():
    """Get the workflow instance (alias for create_workflow)"""
    return create_workflow()

# Health check function
def validate_workflow_config():
    """
    Validate workflow configuration and dependencies.
    
    Returns:
        Dict with validation results
    """
    from config import validate_instagram_config, validate_neo4j_config
    
    results = {
        "redis_connection": test_redis_connection(),
        "router_enabled": settings.ENABLE_ROUTER_AGENT,
        "compliance_enabled": settings.ENABLE_COMPLIANCE_CHECKS,
        "instagram_config": validate_instagram_config() if settings.ENABLE_REAL_INSTAGRAM_API else True,
        "neo4j_config": validate_neo4j_config() if settings.ENABLE_TEMPORAL_GRAPH else True,
        "audit_logging": settings.ENABLE_AUDIT_LOGGING
    }
    
    results["overall_health"] = all(results.values())
    
    return results
