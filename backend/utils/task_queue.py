from ..models.lead import Lead
from ..tasks.lead_processing import process_lead_task

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
    
    # Queue the task with retry policy
    task = process_lead_task.apply_async(
        args=[lead_data],
        retry=True,
        retry_policy={
            'max_retries': 3,
            'interval_start': 0,
            'interval_step': 1,
            'interval_max': 5,
        }
    )
    
    return task.id