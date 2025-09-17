from ..models.lead import Lead
from ..tasks.lead_processing import process_lead_task

def queue_lead_for_processing(lead: Lead):
    """
    Queue a lead for asynchronous processing.
    
    Args:
        lead: Lead object to process
        
    Returns:
        Celery task ID
    """
    # Convert Lead object to dictionary
    lead_data = lead.model_dump()
    
    # Queue the task
    task = process_lead_task.delay(lead_data)
    
    return task.id