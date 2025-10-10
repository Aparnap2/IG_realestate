from datetime import datetime
from backend.models.lead import Lead
from backend.utils.supabase_client import save_lead

def update_lead_status(lead_id: str, status: str):
    """
    Update the status of a lead in the database.
    
    Args:
        lead_id: ID of the lead to update
        status: New status for the lead
    """
    # In a real implementation, this would update the lead in the database
    # For now, we'll just print the update
    print(f"Updating lead {lead_id} status to {status}")
    
    # Actual implementation would look something like:
    # supabase.table("leads").update({"status": status}).eq("id", lead_id).execute()

def log_error(error_message: str, lead_id: str = None):
    """
    Log an error to the database or error tracking system.
    
    Args:
        error_message: Description of the error
        lead_id: ID of the lead associated with the error (if applicable)
    """
    # In a real implementation, this would log the error to a database
    # or error tracking system
    print(f"Error: {error_message} (Lead ID: {lead_id})")
    
    # Actual implementation might look like:
    # supabase.table("errors").insert({
    #     "message": error_message,
    #     "lead_id": lead_id,
    #     "timestamp": datetime.now().isoformat()
    # }).execute()

def format_phone_number(phone: str) -> str:
    """
    Format a phone number for consistent storage.
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Formatted phone number
    """
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # If we have 10 digits, format as (XXX) XXX-XXXX
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    # If we have 11 digits and the first is 1, format as +1 (XXX) XXX-XXXX
    if len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    # Otherwise, return as is
    return phone