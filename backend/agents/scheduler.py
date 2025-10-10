import sys
import os
from datetime import datetime, timedelta
import pytz

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_lead
from tools.handoffs import handoff_to_followup, handoff_to_end
from schemas.state import AgentState
from typing import Dict, Any
import os

# For Google Calendar integration
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# For HubSpot integration
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInput
from hubspot.crm.deals import SimplePublicObjectInput as DealObjectInput

def scheduler_node(state: AgentState) -> Dict[str, Any]:
    """
    Scheduler agent node that books meetings with qualified leads.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with meeting details and next agent
    """
    lead = state["lead"].model_copy(deep=True)
    
    # Check if this is an interrupt for HITL review
    if state.get("interrupt"):
        # If interrupted, we should wait for human approval before proceeding
        # The workflow will be paused here until /human/approve is called
        return {"lead": lead, "next_agent": "scheduler"}
    
    # Get available time slots using Google Calendar API
    available_slots = get_available_slots_from_google_calendar()
    
    if available_slots:
        # Select the first available slot
        selected_slot = available_slots[0]
        lead.meeting_slot = selected_slot
        
        timestamp = datetime.now().isoformat()
        # Add scheduling intent to the lead's history
        lead.history.append({
            "message": f"Scheduling meeting for {selected_slot}",
            "timestamp": timestamp,
            "agent": "scheduler"
        })
        
        # Book the event in Google Calendar
        event_id = book_calendar_event(lead, selected_slot)

        lead.history.append({
            "message": f"Calendar booking {'confirmed' if event_id else 'pending'} (event_id={event_id or 'N/A'})",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })

        # Trigger HubSpot logging and record the action regardless of mock side effects
        lead.history.append({
            "message": "HubSpot sync initiated for scheduled lead",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })
        try:
            log_to_hubspot(lead)
        except Exception as hubspot_error:
            lead.history.append({
                "message": f"HubSpot sync failed: {hubspot_error}",
                "timestamp": datetime.now().isoformat(),
                "agent": "scheduler"
            })
        
        # Save updated lead information
        save_lead(lead.model_dump())
        
        # Move to followup after scheduling
        return {"lead": lead, "next_agent": "followup"}
    else:
        # If no slots available, end the conversation
        lead.history.append({
            "message": "No available time slots found",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })
        lead.history.append({
            "message": "Lead routed to end state due to scheduling unavailability",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })
        save_lead(lead.model_dump())
        return {"lead": lead, "next_agent": "end"}

def get_google_calendar_service():
    """
    Get authenticated Google Calendar service.
    
    Returns:
        Google Calendar service object
    """
    # In a real implementation, you would load credentials from a secure storage
    # For now, we'll use environment variables
    credentials = Credentials(
        token=os.getenv("GOOGLE_CALENDAR_TOKEN"),
        refresh_token=os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"),
        token_uri=os.getenv("GOOGLE_TOKEN_URI"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
    
    service = build('calendar', 'v3', credentials=credentials)
    return service

def get_available_slots_from_google_calendar() -> list:
    """
    Get available time slots from Google Calendar using Freebusy API.
    
    Returns:
        List of available datetime slots
    """
    try:
        service = get_google_calendar_service()
        
        # Set time range for next week
        now = datetime.utcnow()
        end_time = now + timedelta(days=7)
        
        # Convert to RFC3339 format
        time_min = now.isoformat() + 'Z'
        time_max = end_time.isoformat() + 'Z'
        
        # Request free/busy information
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]  # Use primary calendar
        }
        
        freebusy_result = service.freebusy().query(body=body).execute()
        
        # Get busy times
        busy_times = freebusy_result['calendars']['primary']['busy']
        
        # Generate available slots (9 AM to 5 PM, Monday to Friday)
        available_slots = []
        current_date = now.date()
        
        for i in range(7):  # Next 7 days
            check_date = current_date + timedelta(days=i)
            
            # Skip weekends
            if check_date.weekday() >= 5:
                continue
            
            # Check time slots from 9 AM to 5 PM
            for hour in range(9, 17):
                slot_start = datetime.combine(check_date, datetime.min.time()).replace(hour=hour)
                
                # Convert to user's timezone if available, otherwise use UTC
                user_timezone = pytz.UTC
                if os.getenv("USER_TIMEZONE"):
                    try:
                        user_timezone = pytz.timezone(os.getenv("USER_TIMEZONE"))
                    except:
                        pass
                
                slot_start = user_timezone.localize(slot_start)
                
                # Check if slot is available
                slot_end = slot_start + timedelta(hours=1)
                is_available = True
                
                for busy in busy_times:
                    busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                    
                    # Check for overlap
                    if (slot_start < busy_end) and (slot_end > busy_start):
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append(slot_start)
                
                # Limit to 10 slots
                if len(available_slots) >= 10:
                    break
            
            if len(available_slots) >= 10:
                break
        
        return available_slots
    except Exception as e:
        print(f"Error getting available slots from Google Calendar: {e}")
        # Fallback to dummy slots
        return get_available_slots()

def get_available_slots() -> list:
    """
    Get available time slots (fallback implementation).
    
    Returns:
        List of available datetime slots
    """
    # This is a fallback implementation
    # In a real implementation, this would use Google Calendar API
    # to find free slots in the next week
    
    # Return some example slots
    now = datetime.now()
    slots = []
    
    for i in range(1, 8):  # Next 7 days
        slot = now + timedelta(days=i, hours=10)  # 10 AM each day
        slots.append(slot)
    
    return slots

def book_calendar_event(lead, slot) -> str:
    """
    Book an event in Google Calendar.
    
    Args:
        lead: Lead information
        slot: Datetime slot for the meeting
        
    Returns:
        Event ID if successful, empty string otherwise
    """
    try:
        service = get_google_calendar_service()
        
        # Create event
        event = {
            'summary': f'Real Estate Consultation with {lead.name or "Unknown"}',
            'location': 'Online Meeting',
            'description': f'Real estate consultation for {lead.property_type} in {lead.location}',
            'start': {
                'dateTime': slot.isoformat(),
                'timeZone': os.getenv("USER_TIMEZONE", "UTC"),
            },
            'end': {
                'dateTime': (slot + timedelta(hours=1)).isoformat(),
                'timeZone': os.getenv("USER_TIMEZONE", "UTC"),
            },
            'attendees': [
                {'email': os.getenv("AGENT_EMAIL")},
                {'email': lead.email} if lead.email else {'email': 'unknown@example.com'}
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        event_id = event.get('id')
        
        print(f"Event created: {event.get('htmlLink')}")
        return event_id
    except Exception as e:
        print(f"Error booking calendar event: {e}")
        return ""

def get_hubspot_client():
    """
    Get authenticated HubSpot client.
    
    Returns:
        HubSpot client object
    """
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise ValueError("HUBSPOT_API_KEY environment variable is required")
    
    client = HubSpot(api_key=api_key)
    return client

def create_hubspot_contact(lead) -> str:
    """
    Create a contact in HubSpot.
    
    Args:
        lead: Lead information
        
    Returns:
        Contact ID if successful, empty string otherwise
    """
    try:
        client = get_hubspot_client()
        
        # Prepare contact properties
        properties = {
            "firstname": lead.name.split()[0] if lead.name else "Unknown",
            "lastname": " ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else "",
            "email": lead.email or "",
            "phone": "",  # We don't have phone number in our Lead model
            "city": lead.location or "",
            "budget": str(lead.budget) if lead.budget else "",
            "property_type": lead.property_type or "",
            "timeline": lead.timeline or "",
            "qualified_score": str(lead.qualified_score) if lead.qualified_score else ""
        }
        
        # Remove empty properties
        properties = {k: v for k, v in properties.items() if v}
        
        # Create contact
        simple_public_object_input = SimplePublicObjectInput(properties=properties)
        contact = client.crm.contacts.basic_api.create(simple_public_object_input)
        
        return contact.id
    except Exception as e:
        print(f"Error creating HubSpot contact: {e}")
        return ""

def create_hubspot_deal(lead, contact_id: str) -> str:
    """
    Create a deal in HubSpot.
    
    Args:
        lead: Lead information
        contact_id: Associated contact ID
        
    Returns:
        Deal ID if successful, empty string otherwise
    """
    try:
        client = get_hubspot_client()
        
        # Prepare deal properties
        properties = {
            "dealname": f"Real Estate Inquiry - {lead.name or 'Unknown'}",
            "dealstage": "appointmentscheduled",  # Default stage
            "pipeline": "default",  # Default pipeline
            "amount": str(lead.budget) if lead.budget else "",
            "closedate": lead.meeting_slot.isoformat() if lead.meeting_slot else "",
            "property_type": lead.property_type or "",
            "location": lead.location or "",
            "timeline": lead.timeline or ""
        }
        
        # Remove empty properties
        properties = {k: v for k, v in properties.items() if v}
        
        # Create deal
        simple_public_object_input = DealObjectInput(properties=properties)
        deal = client.crm.deals.basic_api.create(simple_public_object_input)
        
        # Associate contact with deal
        if contact_id:
            client.crm.deals.associations_api.create(
                deal.id, "contacts", contact_id, "contact_to_deal"
            )
        
        return deal.id
    except Exception as e:
        print(f"Error creating HubSpot deal: {e}")
        return ""

def log_to_hubspot(lead):
    """
    Log the lead and meeting to HubSpot.
    
    Args:
        lead: Lead information
    """
    try:
        # Create contact in HubSpot
        contact_id = create_hubspot_contact(lead)
        
        # Create deal in HubSpot
        deal_id = create_hubspot_deal(lead, contact_id)
        
        # Add to lead history
        if contact_id or deal_id:
            lead.history.append({
                "message": f"Logged to HubSpot - Contact: {contact_id}, Deal: {deal_id}",
                "timestamp": datetime.now().isoformat(),
                "agent": "scheduler"
            })
        
        print(f"Logged lead {lead.name} to HubSpot - Contact: {contact_id}, Deal: {deal_id}")
    except Exception as e:
        print(f"Error logging to HubSpot: {e}")
        lead.history.append({
            "message": f"Failed to log to HubSpot: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "agent": "scheduler"
        })