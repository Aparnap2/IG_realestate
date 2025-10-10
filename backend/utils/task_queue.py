from backend.models.lead import Lead
from backend.tasks.lead_processing import process_lead

def queue_lead_for_processing(lead: Lead):
    """
    Queue a lead for asynchronous processing with retries and backoff.
    
    Args:
        lead: Lead object to process
        
    Returns:
        Celery task ID
    """
    # Convert Lead object to dictionary
    lead_data = lead.model_dump()
    
    # Queue the task with retry policy using Celery options
    task = process_lead.delay(lead_data)
    return task.id