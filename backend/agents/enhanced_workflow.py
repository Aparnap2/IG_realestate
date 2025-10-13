"""
Enhanced LangGraph implementation with individual agent graphs and custom tools
"""
from typing import Annotated, Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.redis import RedisSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json

from backend.utils.redis_client import redis_client
from backend.utils.supabase_client import query_properties_db, save_lead, get_config
from backend.utils.llm_client import get_llm_response_sync
from backend.models.lead import Lead
from backend.schemas.state import AgentState

class ConversationState(BaseModel):
    """Enhanced state model with conversation history and context"""
    lead: Lead
    messages: List[Dict[str, str]] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    next_agent: str = "qualifier"
    human_feedback: Optional[str] = None
    interrupt: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PropertySearchResult(BaseModel):
    """Structured property search result"""
    properties: List[Dict[str, Any]]
    search_criteria: Dict[str, Any]
    timestamp: str

class QualificationScore(BaseModel):
    """Structured qualification score with reasoning"""
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    factors: Dict[str, float]
    timestamp: str

# Custom tools for the agents
def search_properties_tool(lead: Lead) -> PropertySearchResult:
    """Search properties in database with Redis fallback"""
    try:
        # Try database first
        properties = query_properties_db(
            lead.budget or 0,
            lead.location or "",
            lead.property_type or ""
        )
        
        # Cache results in Redis
        cache_key = f"properties:{lead.user_id}:{hash(str(lead.model_dump()))}"
        redis_client.setex(
            cache_key, 
            3600,  # 1 hour TTL
            json.dumps(properties)
        )
        
        return PropertySearchResult(
            properties=properties,
            search_criteria={
                "budget": lead.budget,
                "location": lead.location,
                "property_type": lead.property_type
            },
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        # Fallback to Redis cache
        cache_key = f"properties:{lead.user_id}:{hash(str(lead.model_dump()))}"
        cached_result = redis_client.get(cache_key)
        if cached_result:
            properties = json.loads(cached_result)
            return PropertySearchResult(
                properties=properties,
                search_criteria={
                    "budget": lead.budget,
                    "location": lead.location,
                    "property_type": lead.property_type
                },
                timestamp=datetime.now().isoformat()
            )
        raise e

def qualify_lead_tool(lead: Lead, properties: List[Dict[str, Any]]) -> QualificationScore:
    """Advanced lead qualification using LLM with structured output"""
    # Get qualification threshold from config
    hitl_threshold = float(get_config("hitl_threshold", "0.9"))
    
    prompt = f"""
    Analyze this real estate lead and provide a detailed qualification score (0-1):

    Lead Information:
    - Budget: {lead.budget or 'Not specified'}
    - Location: {lead.location or 'Not specified'}
    - Property Type: {lead.property_type or 'Not specified'}
    - Timeline: {lead.timeline or 'Not specified'}
    - Message: {lead.message}

    Available Properties:
    {json.dumps(properties, indent=2)}

    Scoring Factors (provide 0-1 score for each):
    1. Budget Match: How well does the budget match available properties?
    2. Location Match: How well does the location match available properties?
    3. Property Type Match: How well does the property type match?
    4. Market Timing: Is the timeline favorable for real estate transactions?
    5. Lead Quality: How specific and serious does the lead appear?

    HITL Threshold: {hitl_threshold} (leads above this should be reviewed by humans)

    Provide your response in this exact JSON format:
    {{
        "score": 0.85,
        "reasoning": "Detailed explanation of the score",
        "factors": {{
            "budget_match": 0.9,
            "location_match": 0.8,
            "property_type_match": 0.7,
            "market_timing": 0.9,
            "lead_quality": 0.85
        }}
    }}
    """
    
    response = get_llm_response_sync(prompt)
    
    try:
        score_data = json.loads(response)
        return QualificationScore(
            score=min(1.0, max(0.0, float(score_data["score"]))),
            reasoning=score_data["reasoning"],
            factors=score_data["factors"],
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        # Fallback scoring
        return QualificationScore(
            score=0.5,
            reasoning=f"Error in LLM scoring: {str(e)}",
            factors={
                "budget_match": 0.5,
                "location_match": 0.5,
                "property_type_match": 0.5,
                "market_timing": 0.5,
                "lead_quality": 0.5
            },
            timestamp=datetime.now().isoformat()
        )

def save_conversation_state_tool(state: ConversationState) -> bool:
    """Save conversation state to both Supabase and Redis"""
    try:
        # Save to Supabase
        save_lead(state.lead.model_dump())
        
        # Save to Redis for quick access
        state_key = f"conversation:{state.lead.user_id}:{state.lead.id}"
        redis_client.setex(
            state_key,
            86400,  # 24 hour TTL
            state.model_dump_json()
        )
        
        return True
    except Exception as e:
        print(f"Error saving conversation state: {e}")
        return False

# Individual agent graphs
def create_qualifier_graph():
    """Create a specialized graph for the qualifier agent"""
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    
    qualifier_graph = StateGraph(ConversationState)
    
    def qualifier_node(state: ConversationState) -> Dict[str, Any]:
        """Enhanced qualifier node with tool usage"""
        # Add user message to history
        state.messages.append({
            "role": "user",
            "content": state.lead.message
        })
        
        # Search properties
        search_result = search_properties_tool(state.lead)
        
        # Qualify lead
        qualification = qualify_lead_tool(state.lead, search_result.properties)
        
        # Update lead with score
        state.lead.qualified_score = qualification.score
        
        # Add to conversation history
        state.conversation_history.append({
            "agent": "qualifier",
            "action": "qualification",
            "result": qualification.model_dump(),
            "timestamp": datetime.now().isoformat()
        })
        
        # Determine next step
        hitl_threshold = float(get_config("hitl_threshold", "0.9"))
        
        if qualification.score > hitl_threshold or (state.lead.budget and state.lead.budget > 500000):
            return {
                "lead": state.lead,
                "messages": state.messages,
                "conversation_history": state.conversation_history,
                "next_agent": "scheduler",
                "interrupt": True,
                "context": {
                    "qualification": qualification.model_dump(),
                    "properties": search_result.properties
                }
            }
        elif qualification.score > 0.7:
            return {
                "lead": state.lead,
                "messages": state.messages,
                "conversation_history": state.conversation_history,
                "next_agent": "scheduler",
                "context": {
                    "qualification": qualification.model_dump(),
                    "properties": search_result.properties
                }
            }
        else:
            return {
                "lead": state.lead,
                "messages": state.messages,
                "conversation_history": state.conversation_history,
                "next_agent": "followup",
                "context": {
                    "qualification": qualification.model_dump(),
                    "properties": search_result.properties
                }
            }
    
    qualifier_graph.add_node("qualify", qualifier_node)
    qualifier_graph.set_entry_point("qualify")
    qualifier_graph.add_edge("qualify", END)
    
    return qualifier_graph.compile()

def create_scheduler_graph():
    """Create a specialized graph for the scheduler agent"""
    scheduler_graph = StateGraph(ConversationState)
    
    def scheduler_node(state: ConversationState) -> Dict[str, Any]:
        """Enhanced scheduler node"""
        if state.interrupt:
            # Wait for human approval
            return {
                "lead": state.lead,
                "messages": state.messages,
                "conversation_history": state.conversation_history,
                "next_agent": "scheduler",
                "interrupt": True
            }
        
        # Add to conversation history
        state.conversation_history.append({
            "agent": "scheduler",
            "action": "scheduling",
            "timestamp": datetime.now().isoformat()
        })
        
        # In a real implementation, this would integrate with Google Calendar
        # For now, we'll simulate scheduling
        from datetime import timedelta
        meeting_time = datetime.now() + timedelta(days=2, hours=10)
        state.lead.meeting_slot = meeting_time
        
        return {
            "lead": state.lead,
            "messages": state.messages,
            "conversation_history": state.conversation_history,
            "next_agent": "followup"
        }
    
    scheduler_graph.add_node("schedule", scheduler_node)
    scheduler_graph.set_entry_point("schedule")
    scheduler_graph.add_edge("schedule", END)
    
    return scheduler_graph.compile()

def create_followup_graph():
    """Create a specialized graph for the followup agent"""
    followup_graph = StateGraph(ConversationState)
    
    def followup_node(state: ConversationState) -> Dict[str, Any]:
        """Enhanced followup node"""
        # Add to conversation history
        state.conversation_history.append({
            "agent": "followup",
            "action": "followup",
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "lead": state.lead,
            "messages": state.messages,
            "conversation_history": state.conversation_history,
            "next_agent": "end"
        }
    
    followup_graph.add_node("followup", followup_node)
    followup_graph.set_entry_point("followup")
    followup_graph.add_edge("followup", END)
    
    return followup_graph.compile()

# Main workflow orchestrator
def create_main_workflow():
    """Create the main workflow that orchestrates individual agent graphs"""
    # Create Redis checkpointer
    checkpointer = RedisSaver(redis_client)
    
    # Create individual agent graphs
    qualifier_agent = create_qualifier_graph()
    scheduler_agent = create_scheduler_graph()
    followup_agent = create_followup_graph()
    
    # Create main workflow
    workflow = StateGraph(ConversationState)
    
    def route_agent(state: ConversationState) -> str:
        """Route to appropriate agent"""
        return state.next_agent
    
    # Add nodes for each agent
    workflow.add_node("qualifier", qualifier_agent)
    workflow.add_node("scheduler", scheduler_agent)
    workflow.add_node("followup", followup_agent)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "qualifier",
        route_agent,
        {
            "scheduler": "scheduler",
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "scheduler",
        route_agent,
        {
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_edge("followup", END)
    
    # Set entry point
    workflow.set_entry_point("qualifier")
    
    # Compile with checkpointer
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["scheduler"]  # Interrupt before scheduler for HITL
    )

def create_compatible_workflow():
    """Create a workflow compatible with the existing AgentState schema"""
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.redis import RedisSaver
    from ..schemas.state import AgentState
    
    # Create Redis checkpointer
    checkpointer = RedisSaver(redis_client)
    
    # Create individual agent graphs
    qualifier_agent = create_qualifier_graph()
    scheduler_agent = create_scheduler_graph()
    followup_agent = create_followup_graph()
    
    # Create main workflow using the existing AgentState
    workflow = StateGraph(AgentState)
    
    # Add nodes for each agent
    workflow.add_node("qualifier", qualifier_agent)
    workflow.add_node("scheduler", scheduler_agent)
    workflow.add_node("followup", followup_agent)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "qualifier",
        lambda state: state.get("next_agent", "followup"),
        {
            "scheduler": "scheduler",
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "scheduler",
        lambda state: state.get("next_agent", "followup"),
        {
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_edge("followup", END)
    
    # Set entry point
    workflow.set_entry_point("qualifier")
    
    # Compile with checkpointer
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["scheduler"]  # Interrupt before scheduler for HITL
    )