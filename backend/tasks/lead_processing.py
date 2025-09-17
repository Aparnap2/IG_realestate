from celery import current_task
from ..celery_app import celery_app
from ..models.lead import Lead
from ..workflow import create_workflow
from ..schemas.state import AgentState

@celery_app.task
def process_lead_task(lead_data: dict):
    """
    Celery task to process a lead through the agentic workflow.
    
    Args:
        lead_data: Dictionary containing lead information
        
    Returns:
        Final state of the lead after processing
    """
    try:
        # Create Lead object from data
        lead = Lead(**lead_data)
        
        # Create the workflow
        workflow = create_workflow()
        
        # Create initial state
        initial_state = AgentState(
            lead=lead,
            messages=[{"role": "user", "content": lead.message}],
            human_feedback=None,
            next_agent="qualifier"
        )
        
        # Process the lead through the workflow
        final_state = workflow.invoke(initial_state)
        
        # Update task state
        current_task.update_state(state="SUCCESS", meta={"result": final_state})
        
        return final_state
    except Exception as e:
        # Update task state with error
        current_task.update_state(state="FAILURE", meta={"error": str(e)})
        raise e