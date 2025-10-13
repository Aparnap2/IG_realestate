import sys
import os
from datetime import datetime, timedelta
import pytz

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_lead
from tools.handoffs import handoff_to_followup, handoff_to_end
from schemas.state import AgentState
from typing import Dict, Any, List
import os
import math

# Optional geopy import for geographic calculations
try:
    from geopy.distance import geodesic
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

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

# Tour Optimization Methods (PRD Section 3.3)

def optimize_tour_sequence(self, properties: List[Dict], time_slots: List[Dict], start_location: str = None) -> Dict[str, Any]:
    """
    Optimize tour sequence by travel time between properties.
    
    Implements PRD requirement: "Optimize Property Sequence by Travel"
    """
    if not properties or len(properties) <= 1:
        return {
            "optimized_sequence": properties,
            "total_travel_time": 0,
            "estimated_tour_duration": 60 if properties else 0,
            "optimization_method": "none"
        }
    
    # Calculate travel times between all properties
    travel_matrix = self._calculate_travel_matrix(properties)
    
    # Find optimal sequence using nearest neighbor algorithm
    optimized_sequence, total_distance = self._nearest_neighbor_tsp(properties, travel_matrix)
    
    # Calculate total travel time (assuming average speed of 40 mph in city)
    total_travel_time = (total_distance / 40) * 60  # Convert to minutes
    
    # Calculate estimated tour duration (20 min per property + travel time)
    estimated_duration = len(optimized_sequence) * 20 + total_travel_time
    
    return {
        "optimized_sequence": optimized_sequence,
        "total_travel_time": total_travel_time,
        "total_distance_miles": total_distance,
        "estimated_tour_duration": estimated_duration,
        "optimization_method": "nearest_neighbor",
        "travel_matrix": travel_matrix
    }

def _calculate_travel_matrix(self, properties: List[Dict]) -> List[List[float]]:
    """Calculate travel time matrix between all properties."""
    n = len(properties)
    matrix = [[0.0] * n for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i != j:
                try:
                    # Calculate distance using geodesic if available
                    if GEOPY_AVAILABLE:
                        coord1 = (properties[i].get('lat', 0), properties[i].get('lng', 0))
                        coord2 = (properties[j].get('lat', 0), properties[j].get('lng', 0))
                        distance_miles = geodesic(coord1, coord2).miles
                        matrix[i][j] = distance_miles
                    else:
                        # Fallback to estimate (1 mile per coordinate degree)
                        lat_diff = abs(properties[i].get('lat', 0) - properties[j].get('lat', 0))
                        lng_diff = abs(properties[i].get('lng', 0) - properties[j].get('lng', 0))
                        matrix[i][j] = math.sqrt(lat_diff**2 + lng_diff**2) * 69  # Rough estimate
                except Exception:
                    # Fallback to estimate (1 mile per coordinate degree)
                    lat_diff = abs(properties[i].get('lat', 0) - properties[j].get('lat', 0))
                    lng_diff = abs(properties[i].get('lng', 0) - properties[j].get('lng', 0))
                    matrix[i][j] = math.sqrt(lat_diff**2 + lng_diff**2) * 69  # Rough estimate
    
    return matrix

def _nearest_neighbor_tsp(self, properties: List[Dict], travel_matrix: List[List[float]]) -> tuple[List[Dict], float]:
    """Solve TSP using nearest neighbor heuristic."""
    if not properties:
        return [], 0
    
    n = len(properties)
    unvisited = set(range(n))
    current = 0  # Start with first property
    sequence = [properties[current]]
    unvisited.remove(current)
    total_distance = 0
    
    while unvisited:
        nearest = min(unvisited, key=lambda x: travel_matrix[current][x])
        total_distance += travel_matrix[current][nearest]
        sequence.append(properties[nearest])
        unvisited.remove(nearest)
        current = nearest
    
    return sequence, total_distance

def apply_buffer_times(self, time_slots: List[Dict], buffer_minutes: int = 30) -> List[Dict]:
    """
    Apply buffer times between consecutive tours.
    
    Implements PRD requirement: buffer slots management.
    """
    if not time_slots:
        return []
    
    # Sort slots by start time
    sorted_slots = sorted(time_slots, key=lambda x: x["start"])
    filtered_slots = [sorted_slots[0]]  # Always keep the first slot
    
    for i in range(1, len(sorted_slots)):
        current_slot = sorted_slots[i]
        previous_slot = filtered_slots[-1]
        
        # Check if there's adequate buffer time
        time_diff = (current_slot["start"] - previous_slot["end"]).total_seconds() / 60
        
        if time_diff >= buffer_minutes:
            filtered_slots.append(current_slot)
    
    return filtered_slots

def create_optimized_tour_event(self, lead: Any, properties: List[Dict], time_slot: Dict) -> Dict[str, Any]:
    """
    Create optimized multi-property tour event.
    
    Implements PRD requirement for multi-property tour optimization.
    """
    try:
        from tools.calendar_integration import create_tour_event
        
        # Optimize property sequence
        optimization_result = self.optimize_tour_sequence(properties, [time_slot])
        optimized_properties = optimization_result["optimized_sequence"]
        
        # Calculate event duration
        duration_minutes = optimization_result["estimated_tour_duration"]
        end_time = time_slot["start"] + timedelta(minutes=duration_minutes)
        
        # Create event with optimized property addresses
        property_addresses = [prop.get("address", "") for prop in optimized_properties]
        
        event_result = create_tour_event(
            start_time=time_slot["start"],
            duration_minutes=duration_minutes,
            attendee_email=lead.email,
            summary=f"Multi-Property Tour: {len(optimized_properties)} Properties",
            description=f"Optimized tour sequence for {len(optimized_properties)} properties.\n"
                        f"Estimated duration: {duration_minutes} minutes\n"
                        f"Properties to visit:\n" + "\n".join([
                            f"{i+1}. {prop.get('address', '')}" 
                            for i, prop in enumerate(optimized_properties)
                        ]),
            property_addresses=property_addresses
        )
        
        return {
            "success": True,
            "event_result": event_result,
            "optimization_result": optimization_result,
            "optimized_properties": optimized_properties
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fallback_mode": True
        }

def calculate_tour_duration(self, properties: List[Dict], visit_duration_per_property: int = 20) -> Dict[str, Any]:
    """
    Calculate accurate tour duration including travel time.
    
    Implements PRD requirement for precise duration calculation.
    """
    if not properties:
        return {"total_duration_minutes": 0, "property_details": []}
    
    # Calculate travel times
    travel_matrix = self._calculate_travel_matrix(properties)
    
    # Find optimal sequence
    optimized_sequence, total_distance = self._nearest_neighbor_tsp(properties, travel_matrix)
    travel_time = (total_distance / 40) * 60  # Minutes
    
    # Calculate total duration
    total_duration = len(properties) * visit_duration_per_property + travel_time
    
    # Build property details
    property_details = []
    for i, prop in enumerate(optimized_sequence):
        details = {
            "property_id": prop.get("id"),
            "address": prop.get("address"),
            "visit_duration": visit_duration_per_property,
            "order": i + 1
        }
        
        # Add travel time to next property (if any)
        if i < len(optimized_sequence) - 1:
            current_idx = properties.index(prop)
            next_prop = optimized_sequence[i + 1]
            next_idx = properties.index(next_prop)
            details["travel_time_to_next"] = (travel_matrix[current_idx][next_idx] / 40) * 60
        
        property_details.append(details)
    
    return {
        "total_duration_minutes": total_duration,
        "property_details": property_details,
        "total_travel_time": travel_time,
        "total_distance_miles": total_distance,
        "optimized_sequence": optimized_sequence
    }

def cluster_properties_by_location(self, properties: List[Dict], cluster_radius_miles: float = 2.0) -> List[List[Dict]]:
    """
    Cluster properties by geographic proximity for efficient tours.
    
    Implements PRD requirement for geographic optimization.
    """
    if not properties or len(properties) <= 1:
        return [properties] if properties else []
    
    clusters = []
    unclustered = properties.copy()
    
    while unclustered:
        # Start a new cluster with the first unclustered property
        cluster = [unclustered.pop(0)]
        
        # Find all properties within cluster radius
        changed = True
        while changed and unclustered:
            changed = False
            for prop in unclustered[:]:  # Copy to avoid modification during iteration
                if self._is_within_cluster_radius(prop, cluster, cluster_radius_miles):
                    cluster.append(prop)
                    unclustered.remove(prop)
                    changed = True
        
        clusters.append(cluster)
    
    return clusters

def _is_within_cluster_radius(self, property: Dict, cluster: List[Dict], radius_miles: float) -> bool:
    """Check if a property is within cluster radius of any property in the cluster."""
    try:
        if GEOPY_AVAILABLE:
            prop_coord = (property.get('lat', 0), property.get('lng', 0))
            
            for cluster_prop in cluster:
                cluster_coord = (cluster_prop.get('lat', 0), cluster_prop.get('lng', 0))
                distance = geodesic(prop_coord, cluster_coord).miles
                
                if distance <= radius_miles:
                    return True
            
            return False
        else:
            # Fallback to simple coordinate distance
            prop_coord = (property.get('lat', 0), property.get('lng', 0))
            
            for cluster_prop in cluster:
                cluster_coord = (cluster_prop.get('lat', 0), cluster_prop.get('lng', 0))
                lat_diff = abs(prop_coord[0] - cluster_coord[0])
                lng_diff = abs(prop_coord[1] - cluster_coord[1])
                distance_miles = math.sqrt(lat_diff**2 + lng_diff**2) * 69  # Rough estimate
                
                if distance_miles <= radius_miles:
                    return True
            
            return False
    except Exception:
        # If all fails, use simple coordinate distance
        return True  # Conservative approach

def filter_conflicting_slots(self, candidate_slots: List[Dict], existing_events: List[Dict]) -> List[Dict]:
    """
    Prevent double booking by filtering conflicting slots.
    
    Implements PRD requirement: "Zero no-shows" through conflict prevention.
    """
    conflict_free_slots = []
    
    for candidate in candidate_slots:
        has_conflict = False
        
        for event in existing_events:
            # Check for any overlap
            conflict = (
                (candidate["start"] >= event["start"] and candidate["start"] < event["end"]) or
                (candidate["end"] > event["start"] and candidate["end"] <= event["end"]) or
                (candidate["start"] <= event["start"] and candidate["end"] >= event["end"])
            )
            
            if conflict:
                has_conflict = True
                break
        
        if not has_conflict:
            conflict_free_slots.append(candidate)
    
    return conflict_free_slots