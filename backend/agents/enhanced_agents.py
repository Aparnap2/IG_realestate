"""
Enhanced LangGraph implementation with individual agent graphs and proper tool integration
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import query_properties_db, save_lead, get_config
from utils.redis_client import cache_query_result, get_cached_query_result, redis_client
from utils.llm_client import get_llm_response
from schemas.state import AgentState
from utils.observability import track_performance, metrics_collector

# Tool definitions
@tool
def query_properties_tool(budget: int, location: str, property_type: str) -> List[Dict[str, Any]]:
    """
    Query properties from the database based on criteria.
    
    Args:
        budget: Maximum budget for properties
        location: Desired location
        property_type: Type of property
        
    Returns:
        List of matching properties
    """
    return query_properties_db(budget, location, property_type)

@tool
def get_cached_query_tool(query: str, user_id: str) -> Optional[Any]:
    """
    Get cached query results from Redis.
    
    Args:
        query: Query string
        user_id: User ID
        
    Returns:
        Cached results or None
    """
    return get_cached_query_result(query, user_id)

@tool
def cache_query_tool(query: str, user_id: str, result: Any) -> None:
    """
    Cache query results in Redis.
    
    Args:
        query: Query string
        user_id: User ID
        result: Query results to cache
    """
    cache_query_result(query, user_id, result)

@tool
def save_lead_tool(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save lead information to the database.
    
    Args:
        lead_data: Lead information to save
        
    Returns:
        Saved lead data
    """
    return save_lead(lead_data)

@tool
def get_config_tool(key: str, default_value: str = "") -> str:
    """
    Get configuration value from the database.
    
    Args:
        key: Configuration key
        default_value: Default value if key is not found
        
    Returns:
        Configuration value or default value
    """
    return get_config(key, default_value)

# Qualifier Agent Graph
def create_qualifier_graph():
    """Create a LangGraph for the qualifier agent"""
    
    class QualifierState(AgentState):
        """Enhanced state for qualifier agent"""
        db_results: List[Dict[str, Any]] = []
        qualification_reasoning: str = ""
        tools_called: List[str] = []
    
    def query_properties_node(state: QualifierState) -> Dict[str, Any]:
        """Node to query properties from database"""
        lead = state["lead"]
        results = query_properties_tool.invoke({
            "budget": lead.budget or 0,
            "location": lead.location or "",
            "property_type": lead.property_type or ""
        })
        
        return {
            "db_results": results,
            "tools_called": state["tools_called"] + ["query_properties"]
        }
    
    def cache_query_node(state: QualifierState) -> Dict[str, Any]:
        """Node to cache query results"""
        lead = state["lead"]
        query = f"SELECT * FROM properties WHERE price <= {lead.budget} AND location = '{lead.location}' AND property_type = '{lead.property_type}'"
        
        cache_query_tool.invoke({
            "query": query,
            "user_id": lead.user_id,
            "result": state["db_results"]
        })
        
        return {
            "tools_called": state["tools_called"] + ["cache_query"]
        }
    
    def qualify_lead_node(state: QualifierState) -> Dict[str, Any]:
        """Node to qualify the lead using LLM"""
        lead = state["lead"]
        db_results = state["db_results"]
        
        # Get qualification prompt from config
        prompt_template = get_config_tool.invoke({
            "key": "qualifier_prompt",
            "default_value": """Score this lead (0-1) for real estate interest based on:
Budget: {budget}
Location: {location}
Type: {property_type}
Timeline: {timeline}

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
}}"""
        })
        
        # Format the prompt
        prompt = prompt_template.format(
            budget=lead.budget,
            location=lead.location,
            property_type=lead.property_type,
            timeline=lead.timeline,
            db_results=db_results
        )
        
        # Get LLM response
        score_response = get_llm_response(prompt)
        
        # Parse the response
        try:
            import json
            score_data = json.loads(score_response)
            score = float(score_data["score"])
            reasoning = score_data["reasoning"]
            
            # Normalize score
            if score > 1.0:
                score = 1.0
            elif score < 0.0:
                score = 0.0
                
        except Exception as e:
            # Fallback parsing
            try:
                score = float(score_response.strip())
                reasoning = "Fallback parsing used"
                if score > 1.0:
                    score = 1.0
                elif score < 0.0:
                    score = 0.0
            except:
                score = 0.5
                reasoning = "Default score used due to parsing error"
        
        # Update lead history
        lead.history.append({
            "message": f"Lead qualified with score: {score}",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier",
            "details": reasoning
        })
        
        # Update lead with score
        lead.qualified_score = score
        
        return {
            "lead": lead,
            "qualification_reasoning": reasoning
        }
    
    def decide_next_step_node(state: QualifierState) -> str:
        """Node to decide next step based on qualification score"""
        lead = state["lead"]
        score = lead.qualified_score or 0.0
        
        # Get HITL threshold from config
        hitl_threshold = float(get_config_tool.invoke({
            "key": "hitl_threshold",
            "default_value": "0.9"
        }))
        
        if score > hitl_threshold or (lead.budget and lead.budget > 500000):
            return "interrupt_for_hitl"
        elif score > 0.7:
            return "route_to_scheduler"
        else:
            return "route_to_followup"
    
    # Create the graph
    qualifier_graph = StateGraph(QualifierState)
    
    # Add nodes
    qualifier_graph.add_node("query_properties", query_properties_node)
    qualifier_graph.add_node("cache_query", cache_query_node)
    qualifier_graph.add_node("qualify_lead", qualify_lead_node)
    qualifier_graph.add_node("decide_next", decide_next_step_node)
    
    # Add edges
    qualifier_graph.add_edge("query_properties", "cache_query")
    qualifier_graph.add_edge("cache_query", "qualify_lead")
    qualifier_graph.add_edge("qualify_lead", "decide_next")
    
    # Add conditional edges
    qualifier_graph.add_conditional_edges(
        "decide_next",
        lambda x: x,
        {
            "interrupt_for_hitl": "interrupt_for_hitl",
            "route_to_scheduler": "route_to_scheduler",
            "route_to_followup": "route_to_followup"
        }
    )
    
    # Set entry point
    qualifier_graph.set_entry_point("query_properties")
    
    return qualifier_graph.compile()

# Scheduler Agent Graph
def create_scheduler_graph():
    """Create a LangGraph for the scheduler agent"""
    
    def get_available_slots_node(state: AgentState) -> Dict[str, Any]:
        """Node to get available time slots"""
        # In a real implementation, this would integrate with Google Calendar API
        # For now, we'll return dummy slots
        now = datetime.now()
        slots = []
        for i in range(1, 8):  # Next 7 days
            slot = now + timedelta(days=i, hours=10)  # 10 AM each day
            slots.append(slot)
        return {"available_slots": slots}
    
    def book_calendar_event_node(state: AgentState) -> Dict[str, Any]:
        """Node to book calendar event"""
        # In a real implementation, this would integrate with Google Calendar API
        lead = state["lead"]
        # For now, we'll just add to history
        lead.history.append({
            "message": "Meeting scheduled",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })
        return {"lead": lead}
    
    def log_to_hubspot_node(state: AgentState) -> Dict[str, Any]:
        """Node to log to HubSpot"""
        # In a real implementation, this would integrate with HubSpot API
        lead = state["lead"]
        # For now, we'll just add to history
        lead.history.append({
            "message": "Logged to HubSpot",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })
        return {"lead": lead}
    
    def save_lead_node(state: AgentState) -> Dict[str, Any]:
        """Node to save lead to database"""
        lead = state["lead"]
        save_lead_tool.invoke({"lead_data": lead.model_dump()})
        return {"lead": lead}
    
    # Create the graph
    scheduler_graph = StateGraph(AgentState)
    
    # Add nodes
    scheduler_graph.add_node("get_slots", get_available_slots_node)
    scheduler_graph.add_node("book_event", book_calendar_event_node)
    scheduler_graph.add_node("log_hubspot", log_to_hubspot_node)
    scheduler_graph.add_node("save_lead", save_lead_node)
    
    # Add edges
    scheduler_graph.add_edge("get_slots", "book_event")
    scheduler_graph.add_edge("book_event", "log_hubspot")
    scheduler_graph.add_edge("log_hubspot", "save_lead")
    
    # Set entry point
    scheduler_graph.set_entry_point("get_slots")
    
    return scheduler_graph.compile()

# FollowUp Agent Graph
def create_followup_graph():
    """Create a LangGraph for the followup agent"""
    
    def send_followup_message_node(state: AgentState) -> Dict[str, Any]:
        """Node to send followup message"""
        lead = state["lead"]
        # In a real implementation, this would integrate with Meta APIs
        # For now, we'll just add to history
        lead.history.append({
            "message": "Follow-up message sent",
            "timestamp": datetime.now().isoformat(),
            "agent": "followup"
        })
        return {"lead": lead}
    
    def save_lead_node(state: AgentState) -> Dict[str, Any]:
        """Node to save lead to database"""
        lead = state["lead"]
        save_lead_tool.invoke({"lead_data": lead.model_dump()})
        return {"lead": lead}
    
    # Create the graph
    followup_graph = StateGraph(AgentState)
    
    # Add nodes
    followup_graph.add_node("send_message", send_followup_message_node)
    followup_graph.add_node("save_lead", save_lead_node)
    
    # Add edges
    followup_graph.add_edge("send_message", "save_lead")
    
    # Set entry point
    followup_graph.set_entry_point("send_message")
    
    return followup_graph.compile()

# Main workflow that orchestrates the agent graphs
def create_main_workflow():
    """Create the main workflow that orchestrates all agent graphs"""
    
    # Create Redis checkpointer
    checkpointer = RedisSaver(redis_client)
    
    def qualifier_agent_node(state: AgentState) -> Dict[str, Any]:
        """Node to run the qualifier agent graph"""
        qualifier_graph = create_qualifier_graph()
        result = qualifier_graph.invoke(state)
        return result
    
    def scheduler_agent_node(state: AgentState) -> Dict[str, Any]:
        """Node to run the scheduler agent graph"""
        scheduler_graph = create_scheduler_graph()
        result = scheduler_graph.invoke(state)
        return result
    
    def followup_agent_node(state: AgentState) -> Dict[str, Any]:
        """Node to run the followup agent graph"""
        followup_graph = create_followup_graph()
        result = followup_graph.invoke(state)
        return result
    
    def interrupt_handler_node(state: AgentState) -> Dict[str, Any]:
        """Node to handle interrupts for HITL"""
        lead = state["lead"]
        lead.history.append({
            "message": "Interrupted for HITL review",
            "timestamp": datetime.now().isoformat(),
            "agent": "system"
        })
        return {"lead": lead, "interrupt": True}
    
    # Create the main workflow graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("qualifier_agent", qualifier_agent_node)
    workflow.add_node("scheduler_agent", scheduler_agent_node)
    workflow.add_node("followup_agent", followup_agent_node)
    workflow.add_node("interrupt_handler", interrupt_handler_node)
    
    # Add edges
    workflow.add_conditional_edges(
        "qualifier_agent",
        lambda state: state.get("next_agent", "followup"),
        {
            "scheduler": "scheduler_agent",
            "followup": "followup_agent",
            "interrupt": "interrupt_handler"
        }
    )
    
    workflow.add_edge("scheduler_agent", END)
    workflow.add_edge("followup_agent", END)
    workflow.add_edge("interrupt_handler", END)
    
    # Set entry point
    workflow.set_entry_point("qualifier_agent")
    
    # Compile with checkpointer
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["scheduler_agent"]  # Interrupt before scheduler if flagged
    )

# Enhanced qualifier node that uses the agent graph
@track_performance
def qualifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced qualifier agent node that uses LangGraph for individual agent processing.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with qualification results
    """
    try:
        # Create and run the qualifier agent graph
        qualifier_graph = create_qualifier_graph()
        result = qualifier_graph.invoke(state)
        return result
    except Exception as e:
        # Log error and return fallback
        metrics_collector.record_request(0.0, success=False)
        lead = state["lead"]
        lead.history.append({
            "message": f"Qualification error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "agent": "system"
        })
        return {"lead": lead, "next_agent": "followup"}

# Enhanced scheduler node that uses the agent graph
@track_performance
def scheduler_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced scheduler agent node that uses LangGraph for individual agent processing.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state after scheduling
    """
    try:
        # Check if this is an interrupt for HITL review
        if state.get("interrupt"):
            return {"lead": state["lead"], "next_agent": "scheduler"}
        
        # Create and run the scheduler agent graph
        scheduler_graph = create_scheduler_graph()
        result = scheduler_graph.invoke(state)
        return {"lead": result["lead"], "next_agent": "followup"}
    except Exception as e:
        # Log error and handle gracefully
        metrics_collector.record_request(0.0, success=False)
        lead = state["lead"]
        lead.history.append({
            "message": f"Scheduling error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "agent": "system"
        })
        return {"lead": lead, "next_agent": "end"}

# Enhanced followup node that uses the agent graph
@track_performance
def followup_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced followup agent node that uses LangGraph for individual agent processing.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state after followup
    """
    try:
        # Create and run the followup agent graph
        followup_graph = create_followup_graph()
        result = followup_graph.invoke(state)
        return {"lead": result["lead"], "next_agent": "end"}
    except Exception as e:
        # Log error and handle gracefully
        metrics_collector.record_request(0.0, success=False)
        lead = state["lead"]
        lead.history.append({
            "message": f"Followup error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "agent": "system"
        })
        return {"lead": lead, "next_agent": "end"}