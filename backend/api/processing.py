from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .workflow import create_workflow
from .models.lead import Lead
from .schemas.state import AgentState
from typing import Dict, Any

app = FastAPI()

# Create the workflow
workflow = create_workflow()

class LeadInput(BaseModel):
    lead: Lead

@app.post("/process-lead")
async def process_lead(lead_input: LeadInput):
    """
    Process a lead through the agentic workflow.
    
    Args:
        lead_input: Lead information to process
        
    Returns:
        Final state of the lead after processing
    """
    try:
        # Create initial state
        initial_state = AgentState(
            lead=lead_input.lead,
            messages=[{"role": "user", "content": lead_input.lead.message}],
            human_feedback=None,
            next_agent="qualifier"
        )
        
        # Process the lead through the workflow
        final_state = workflow.invoke(initial_state)
        
        return {"final_state": final_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))