from supabase import create_client, Client
import os
from typing import List, Dict, Any

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), 
    os.getenv("SUPABASE_KEY")
)

def query_properties_db(budget: int, location: str, property_type: str) -> List[Dict[str, Any]]:
    """
    Query properties from Supabase based on lead criteria.
    
    Args:
        budget: Maximum budget for the property
        location: Desired location of the property
        property_type: Type of property (e.g., 2BHK, Condo)
        
    Returns:
        List of properties matching the criteria
    """
    # Query properties where price is less than or equal to budget,
    # location matches, and property type matches
    response = supabase.table("properties").select("*").lte("price", budget).eq("location", location).eq("property_type", property_type).execute()
    
    return response.data

def get_lead_history(lead_id: str) -> List[Dict[str, Any]]:
    """
    Get conversation history for a lead from Supabase.
    
    Args:
        lead_id: ID of the lead
        
    Returns:
        List of conversation history entries
    """
    response = supabase.table("leads").select("history").eq("id", lead_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0].get("history", [])
    return []

def save_lead(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save or update lead information in Supabase.
    
    Args:
        lead_data: Dictionary containing lead information
        
    Returns:
        Saved lead data
    """
    response = supabase.table("leads").upsert(lead_data).execute()
    
    return response.data[0] if response.data else {}