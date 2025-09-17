from langgraph.graph import StateGraph, END
from ..agents.qualifier import qualifier_node
from ..agents.scheduler import scheduler_node
from ..agents.followup import followup_node
from ..schemas.state import AgentState
from ..tools.handoffs import handoff_to_scheduler, handoff_to_followup, handoff_to_end

def create_workflow():
    """
    Create the LangGraph workflow for the lead capture system.
    
    Returns:
        Compiled LangGraph workflow
    """
    # Define a new graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("qualifier", qualifier_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("followup", followup_node)

    # Add edges
    workflow.add_conditional_edges(
        "qualifier",
        lambda state: state["next_agent"],
        {
            "scheduler": "scheduler",
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "scheduler",
        lambda state: state["next_agent"],
        {
            "followup": "followup",
            "end": END
        }
    )
    
    workflow.add_edge("followup", END)

    # Set the entry point
    workflow.set_entry_point("qualifier")

    # Compile the graph
    return workflow.compile()