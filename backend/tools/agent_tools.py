"""
Comprehensive tools for LangGraph agents according to PRD specifications.

These tools handle database queries, API integrations, caching, and handoffs
between agents in the swarm architecture.
"""
import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import hashlib
from langchain_core.tools import tool

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import query_properties_db, save_lead, get_config
from utils.redis_client import cache_query_result, get_cached_query_result
from utils.llm_client import get_llm_response

# Database and Caching Tools
@tool
def query_properties_tool(budget: int, location: str, property_type: str) -> List[Dict[str, Any]]:
    """
    Query properties from the database based on lead criteria.
    
    Args:
        budget: Maximum budget for properties
        location: Desired location
        property_type: Type of property
        
    Returns:
        List of matching properties
    """
    try:
        # First check cache
        query_key = f"properties_{budget}_{location}_{property_type}"
        cached_result = get_cached_query_result(query_key, "system")
        
        if cached_result:
            return cached_result
        
        # Query database
        results = query_properties_db(budget, location, property_type)
        
        # Cache results for 24 hours
        cache_query_result(query_key, "system", results, ttl=86400)
        
        return results
    except Exception as e:
        print(f"Error querying properties: {e}")
        return []

@tool
def save_lead_tool(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save lead information to the database.
    
    Args:
        lead_data: Lead information to save
        
    Returns:
        Saved lead data
    """
    try:
        return save_lead(lead_data)
    except Exception as e:
        print(f"Error saving lead: {e}")
        return {}

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
    try:
        return get_config(key, default_value)
    except Exception as e:
        print(f"Error getting config: {e}")
        return default_value

# LLM Tools
@tool
def qualify_lead_with_llm(
    budget: Optional[int],
    location: Optional[str], 
    property_type: Optional[str],
    timeline: Optional[str],
    db_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use LLM to qualify a lead based on criteria and available properties.
    
    Args:
        budget: Lead's budget
        location: Lead's desired location
        property_type: Lead's desired property type
        timeline: Lead's timeline
        db_results: Available properties from database
        
    Returns:
        Dictionary with score and reasoning
    """
    try:
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
            budget=budget or "Not specified",
            location=location or "Not specified",
            property_type=property_type or "Not specified",
            timeline=timeline or "Not specified",
            db_results=json.dumps(db_results[:3])  # Limit to first 3 properties
        )
        
        # Get LLM response
        response = get_llm_response(prompt)
        
        # Parse response
        try:
            result = json.loads(response)
            score = float(result.get("score", 0.5))
            reasoning = result.get("reasoning", "Default reasoning")
            
            # Normalize score
            score = max(0.0, min(1.0, score))
            
            return {
                "score": score,
                "reasoning": reasoning
            }
        except json.JSONDecodeError:
            # Fallback parsing
            try:
                score = float(response.strip())
                score = max(0.0, min(1.0, score))
                return {
                    "score": score,
                    "reasoning": "Fallback parsing used"
                }
            except:
                return {
                    "score": 0.5,
                    "reasoning": "Default score due to parsing error"
                }
                
    except Exception as e:
        print(f"Error qualifying lead with LLM: {e}")
        return {
            "score": 0.5,
            "reasoning": f"Error occurred: {str(e)}"
        }

# Instagram Graph API Integration
@tool
def send_instagram_message(user_id: str, message: str) -> bool:
    """
    Send a message via Instagram Graph API.
    
    Args:
        user_id: Instagram user ID (PSID)
        message: Message to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from config import get_settings
        settings = get_settings()
        
        if not settings.ENABLE_REAL_INSTAGRAM_API:
            # Mock implementation for development
            print(f"[MOCK] Sending Instagram message to {user_id}: {message}")
            return True
        
        import requests
        
        url = "https://graph.facebook.com/v21.0/me/messages"
        
        payload = {
            "recipient": {"id": user_id},
            "message": {"text": message}
        }
        
        headers = {
            "Authorization": f"Bearer {settings.INSTAGRAM_PAGE_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Log successful send
            from utils.audit import audit_log_event
            audit_log_event("instagram_message_sent", {
                "user_id": user_id,
                "message_length": len(message),
                "response_id": response.json().get("message_id")
            })
            return True
        else:
            # Log failure
            from utils.audit import audit_log_event
            audit_log_event("instagram_message_failed", {
                "user_id": user_id,
                "status_code": response.status_code,
                "error": response.text
            })
            return False
            
    except Exception as e:
        print(f"Error sending Instagram message: {e}")
        from utils.audit import audit_log_event
        audit_log_event("instagram_message_error", {
            "user_id": user_id,
            "error": str(e)
        })
        return False



# Google Calendar Tools (Real Implementation)
@tool
def get_available_calendar_slots(days_ahead: int = 7, time_of_day: str = "any") -> List[datetime]:
    """
    Get available calendar slots from Google Calendar.
    
    Args:
        days_ahead: Number of days to look ahead
        time_of_day: Preferred time ("morning", "afternoon", "evening", "any")
        
    Returns:
        List of available datetime slots
    """
    try:
        from tools.calendar_integration import get_available_calendar_slots as get_slots
        return get_slots(days_ahead=days_ahead, time_of_day=time_of_day)
    except Exception as e:
        print(f"Error getting calendar slots: {e}")
        from utils.audit import audit_log_event
        audit_log_event("calendar_slots_error", {"error": str(e)})
        return []

@tool
def book_calendar_event(
    start_time: datetime,
    duration_minutes: int,
    attendee_email: str,
    summary: str,
    description: str = "",
    property_addresses: List[str] = None
) -> Dict[str, Any]:
    """
    Book a calendar event via Google Calendar API with Google Meet link.
    
    Args:
        start_time: Event start time
        duration_minutes: Event duration in minutes
        attendee_email: Attendee's email
        summary: Event summary
        description: Event description
        property_addresses: List of property addresses for tour
        
    Returns:
        Dictionary with event details or error
    """
    try:
        from tools.calendar_integration import create_tour_event
        return create_tour_event(
            start_time=start_time,
            duration_minutes=duration_minutes,
            attendee_email=attendee_email,
            summary=summary,
            description=description,
            property_addresses=property_addresses or []
        )
    except Exception as e:
        print(f"Error booking calendar event: {e}")
        from utils.audit import audit_log_event
        audit_log_event("calendar_booking_error", {
            "error": str(e),
            "start_time": start_time.isoformat(),
            "attendee_email": attendee_email
        })
        return {"error": str(e)}

# HubSpot Tools (Placeholder implementations)
@tool
def create_hubspot_contact(
    email: str,
    first_name: str = "",
    phone: str = "",
    lifecycle_stage: str = "lead"
) -> Dict[str, Any]:
    """
    Create a contact in HubSpot.
    
    Args:
        email: Contact's email
        first_name: Contact's first name
        phone: Contact's phone number
        lifecycle_stage: HubSpot lifecycle stage
        
    Returns:
        Dictionary with contact details or error
    """
    try:
        # TODO: Implement actual HubSpot API integration
        contact_id = f"contact_{hashlib.md5(email.encode()).hexdigest()[:8]}"
        print(f"Creating HubSpot contact: {email}")
        
        return {
            "contact_id": contact_id,
            "email": email,
            "first_name": first_name,
            "phone": phone,
            "lifecycle_stage": lifecycle_stage,
            "status": "created"
        }
    except Exception as e:
        print(f"Error creating HubSpot contact: {e}")
        return {"error": str(e)}

@tool
def create_hubspot_deal(
    contact_id: str,
    deal_name: str,
    amount: int,
    deal_stage: str = "appointmentscheduled"
) -> Dict[str, Any]:
    """
    Create a deal in HubSpot.
    
    Args:
        contact_id: Associated contact ID
        deal_name: Deal name
        amount: Deal amount
        deal_stage: HubSpot deal stage
        
    Returns:
        Dictionary with deal details or error
    """
    try:
        # TODO: Implement actual HubSpot API integration
        deal_id = f"deal_{hashlib.md5(f'{contact_id}_{deal_name}'.encode()).hexdigest()[:8]}"
        print(f"Creating HubSpot deal: {deal_name} for ${amount}")
        
        return {
            "deal_id": deal_id,
            "contact_id": contact_id,
            "deal_name": deal_name,
            "amount": amount,
            "deal_stage": deal_stage,
            "status": "created"
        }
    except Exception as e:
        print(f"Error creating HubSpot deal: {e}")
        return {"error": str(e)}

# Handoff Tools
@tool
def handoff_to_scheduler() -> str:
    """
    Handoff to scheduler agent.
    
    Returns:
        Next agent name
    """
    return "scheduler"

@tool
def handoff_to_followup() -> str:
    """
    Handoff to followup agent.
    
    Returns:
        Next agent name
    """
    return "followup"

@tool
def handoff_to_end() -> str:
    """
    End the workflow.
    
    Returns:
        End signal
    """
    return "END"

# All available tools for agents
ALL_TOOLS = [
    query_properties_tool,
    save_lead_tool,
    get_config_tool,
    qualify_lead_with_llm,
    send_instagram_message,
    get_available_calendar_slots,
    book_calendar_event,
    create_hubspot_contact,
    create_hubspot_deal,
    handoff_to_scheduler,
    handoff_to_followup,
    handoff_to_end
]