"""
Google Calendar Integration for Real Estate Tour Scheduling

Implements PRD Section 2.3: Frictionless Scheduling with multi-constraint planning.

Key Features:
- Real Google Calendar API integration with OAuth2
- Free/busy time queries for agent availability
- Automated event creation with Google Meet links
- Timezone handling and conflict detection
- Batch operations for multi-property tours
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pytz

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import get_settings
from utils.audit import audit_log_event

settings = get_settings()

class GoogleCalendarClient:
    """Google Calendar API client with OAuth2 authentication."""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service with credentials."""
        try:
            if not settings.ENABLE_GOOGLE_CALENDAR:
                return None
            
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            
            creds = None
            # Load existing credentials
            if settings.GOOGLE_CALENDAR_CREDENTIALS_JSON:
                creds_data = json.loads(settings.GOOGLE_CALENDAR_CREDENTIALS_JSON)
                creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # This would require interactive flow in production
                    # For now, we'll use service account or pre-authorized credentials
                    pass
            
            if creds:
                self.service = build('calendar', 'v3', credentials=creds)
                
        except Exception as e:
            audit_log_event("calendar_init_error", {"error": str(e)})
            self.service = None
    
    def get_freebusy(
        self, 
        calendar_id: str = 'primary',
        days_ahead: int = 7,
        time_min: datetime = None,
        time_max: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get free/busy information for the specified calendar.
        
        Args:
            calendar_id: Calendar ID (default: 'primary')
            days_ahead: Number of days to look ahead
            time_min: Start time for query
            time_max: End time for query
            
        Returns:
            List of free time slots
        """
        try:
            if not self.service:
                return self._mock_freebusy_slots(days_ahead)
            
            # Set time range
            if not time_min:
                time_min = datetime.now(pytz.UTC)
            if not time_max:
                time_max = time_min + timedelta(days=days_ahead)
            
            # Query freebusy
            freebusy_query = {
                'timeMin': time_min.isoformat(),
                'timeMax': time_max.isoformat(),
                'items': [{'id': calendar_id}]
            }
            
            freebusy_result = self.service.freebusy().query(body=freebusy_query).execute()
            
            # Extract busy periods
            busy_periods = []
            calendar_busy = freebusy_result.get('calendars', {}).get(calendar_id, {})
            for busy_period in calendar_busy.get('busy', []):
                busy_periods.append({
                    'start': datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00')),
                    'end': datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                })
            
            # Generate free slots
            free_slots = self._calculate_free_slots(time_min, time_max, busy_periods)
            
            audit_log_event("calendar_freebusy_query", {
                "calendar_id": calendar_id,
                "time_range": f"{time_min.isoformat()} to {time_max.isoformat()}",
                "busy_periods": len(busy_periods),
                "free_slots": len(free_slots)
            })
            
            return free_slots
            
        except Exception as e:
            audit_log_event("calendar_freebusy_error", {"error": str(e)})
            return self._mock_freebusy_slots(days_ahead)
    
    def create_event(
        self,
        start_time: datetime,
        end_time: datetime,
        summary: str,
        description: str = "",
        attendee_emails: List[str] = None,
        location: str = "",
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Create a calendar event with Google Meet link.
        
        Args:
            start_time: Event start time
            end_time: Event end time
            summary: Event title
            description: Event description
            attendee_emails: List of attendee email addresses
            location: Event location
            calendar_id: Calendar to create event in
            
        Returns:
            Dictionary with event details
        """
        try:
            if not self.service:
                return self._mock_create_event(start_time, end_time, summary, attendee_emails)
            
            # Prepare attendees
            attendees = []
            if attendee_emails:
                attendees = [{'email': email} for email in attendee_emails]
            
            # Create event body
            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC'
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC'
                },
                'attendees': attendees,
                'location': location,
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meet-{int(start_time.timestamp())}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 24 hours
                        {'method': 'popup', 'minutes': 30},       # 30 minutes
                    ]
                }
            }
            
            # Create the event
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            # Extract Google Meet link
            meet_link = None
            if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                for entry_point in event['conferenceData']['entryPoints']:
                    if entry_point['entryPointType'] == 'video':
                        meet_link = entry_point['uri']
                        break
            
            result = {
                'event_id': event['id'],
                'html_link': event.get('htmlLink'),
                'meet_link': meet_link,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'summary': summary,
                'attendees': attendee_emails or [],
                'status': 'created'
            }
            
            audit_log_event("calendar_event_created", {
                "event_id": event['id'],
                "summary": summary,
                "start_time": start_time.isoformat(),
                "attendees_count": len(attendee_emails) if attendee_emails else 0,
                "has_meet_link": meet_link is not None
            })
            
            return result
            
        except Exception as e:
            audit_log_event("calendar_event_creation_error", {
                "error": str(e),
                "summary": summary,
                "start_time": start_time.isoformat()
            })
            return self._mock_create_event(start_time, end_time, summary, attendee_emails)
    
    def update_event(
        self,
        event_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        summary: str = None,
        description: str = None,
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            if not self.service:
                return {"status": "mock_updated", "event_id": event_id}
            
            # Get existing event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # Update fields
            if start_time:
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC'
                }
            if end_time:
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC'
                }
            if summary:
                event['summary'] = summary
            if description:
                event['description'] = description
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            audit_log_event("calendar_event_updated", {
                "event_id": event_id,
                "updated_fields": {
                    "start_time": start_time.isoformat() if start_time else None,
                    "summary": summary
                }
            })
            
            return {
                "status": "updated",
                "event_id": updated_event['id'],
                "html_link": updated_event.get('htmlLink')
            }
            
        except Exception as e:
            audit_log_event("calendar_event_update_error", {
                "error": str(e),
                "event_id": event_id
            })
            return {"status": "error", "error": str(e)}
    
    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete a calendar event."""
        try:
            if not self.service:
                return True  # Mock success
            
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            audit_log_event("calendar_event_deleted", {"event_id": event_id})
            return True
            
        except Exception as e:
            audit_log_event("calendar_event_deletion_error", {
                "error": str(e),
                "event_id": event_id
            })
            return False
    
    def _calculate_free_slots(
        self,
        time_min: datetime,
        time_max: datetime,
        busy_periods: List[Dict[str, datetime]],
        slot_duration: int = 60  # minutes
    ) -> List[Dict[str, Any]]:
        """Calculate free time slots from busy periods."""
        free_slots = []
        
        # Business hours: 9 AM to 6 PM, Monday to Friday
        current_time = time_min.replace(hour=9, minute=0, second=0, microsecond=0)
        
        while current_time < time_max:
            # Skip weekends
            if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                current_time += timedelta(days=1)
                current_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
                continue
            
            # Skip outside business hours
            if current_time.hour < 9 or current_time.hour >= 18:
                if current_time.hour >= 18:
                    # Move to next day
                    current_time += timedelta(days=1)
                    current_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
                else:
                    current_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
                continue
            
            slot_end = current_time + timedelta(minutes=slot_duration)
            
            # Check if slot conflicts with any busy period
            is_free = True
            for busy_period in busy_periods:
                if (current_time < busy_period['end'] and slot_end > busy_period['start']):
                    is_free = False
                    # Jump to end of busy period
                    current_time = busy_period['end']
                    break
            
            if is_free:
                free_slots.append({
                    'start': current_time,
                    'end': slot_end,
                    'duration_minutes': slot_duration
                })
                current_time += timedelta(minutes=slot_duration)
            
            # Prevent infinite loops
            if len(free_slots) > 50:  # Reasonable limit
                break
        
        return free_slots
    
    def _mock_freebusy_slots(self, days_ahead: int) -> List[Dict[str, Any]]:
        """Generate mock free slots for development/testing."""
        slots = []
        now = datetime.now(pytz.UTC)
        
        for day in range(1, days_ahead + 1):
            date = now + timedelta(days=day)
            
            # Skip weekends
            if date.weekday() >= 5:
                continue
            
            # Generate slots: 10 AM, 2 PM, 4 PM
            for hour in [10, 14, 16]:
                slot_start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(hours=1)
                
                slots.append({
                    'start': slot_start,
                    'end': slot_end,
                    'duration_minutes': 60
                })
        
        return slots[:10]  # Return first 10 slots
    
    def _mock_create_event(
        self,
        start_time: datetime,
        end_time: datetime,
        summary: str,
        attendee_emails: List[str] = None
    ) -> Dict[str, Any]:
        """Mock event creation for development/testing."""
        event_id = f"mock_event_{int(start_time.timestamp())}"
        
        return {
            'event_id': event_id,
            'html_link': f"https://calendar.google.com/calendar/event?eid={event_id}",
            'meet_link': f"https://meet.google.com/mock-{event_id[:8]}",
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'summary': summary,
            'attendees': attendee_emails or [],
            'status': 'mock_created'
        }

# Global client instance
_calendar_client = None

def get_calendar_client() -> GoogleCalendarClient:
    """Get or create the global calendar client instance."""
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = GoogleCalendarClient()
    return _calendar_client

# Convenience functions for agent tools
def get_available_calendar_slots(
    days_ahead: int = 7,
    time_of_day: str = "any"  # "morning", "afternoon", "evening", "any"
) -> List[datetime]:
    """
    Get available calendar slots for the agent.
    
    Args:
        days_ahead: Number of days to look ahead
        time_of_day: Preferred time of day
        
    Returns:
        List of available datetime slots
    """
    try:
        client = get_calendar_client()
        free_slots = client.get_freebusy(days_ahead=days_ahead)
        
        # Filter by time of day preference
        filtered_slots = []
        for slot in free_slots:
            hour = slot['start'].hour
            
            if time_of_day == "morning" and 9 <= hour < 12:
                filtered_slots.append(slot['start'])
            elif time_of_day == "afternoon" and 12 <= hour < 17:
                filtered_slots.append(slot['start'])
            elif time_of_day == "evening" and 17 <= hour < 19:
                filtered_slots.append(slot['start'])
            elif time_of_day == "any":
                filtered_slots.append(slot['start'])
        
        return filtered_slots[:10]  # Return top 10 slots
        
    except Exception as e:
        audit_log_event("get_calendar_slots_error", {"error": str(e)})
        return []

def create_tour_event(
    start_time: datetime,
    duration_minutes: int,
    attendee_email: str,
    summary: str,
    description: str = "",
    property_addresses: List[str] = None
) -> Dict[str, Any]:
    """
    Create a property tour event with Google Meet link.
    
    Args:
        start_time: Tour start time
        duration_minutes: Tour duration
        attendee_email: Lead's email address
        summary: Event title
        description: Event description
        property_addresses: List of property addresses for the tour
        
    Returns:
        Dictionary with event details
    """
    try:
        client = get_calendar_client()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Enhance description with property details
        if property_addresses:
            description += f"\n\nProperty Tour Locations:\n"
            for i, address in enumerate(property_addresses, 1):
                description += f"{i}. {address}\n"
        
        description += f"\n\nTour Duration: {duration_minutes} minutes"
        description += f"\nScheduled via Real Estate AI Assistant"
        
        result = client.create_event(
            start_time=start_time,
            end_time=end_time,
            summary=summary,
            description=description,
            attendee_emails=[attendee_email],
            location=property_addresses[0] if property_addresses else ""
        )
        
        return result
        
    except Exception as e:
        audit_log_event("create_tour_event_error", {
            "error": str(e),
            "start_time": start_time.isoformat(),
            "attendee_email": attendee_email
        })
        return {"error": str(e)}

def reschedule_tour_event(
    event_id: str,
    new_start_time: datetime,
    new_duration_minutes: int = None
) -> Dict[str, Any]:
    """Reschedule an existing tour event."""
    try:
        client = get_calendar_client()
        
        end_time = None
        if new_duration_minutes:
            end_time = new_start_time + timedelta(minutes=new_duration_minutes)
        
        result = client.update_event(
            event_id=event_id,
            start_time=new_start_time,
            end_time=end_time
        )
        
        return result
        
    except Exception as e:
        audit_log_event("reschedule_tour_error", {
            "error": str(e),
            "event_id": event_id,
            "new_start_time": new_start_time.isoformat()
        })
        return {"error": str(e)}

def cancel_tour_event(event_id: str) -> bool:
    """Cancel a tour event."""
    try:
        client = get_calendar_client()
        return client.delete_event(event_id)
        
    except Exception as e:
        audit_log_event("cancel_tour_error", {
            "error": str(e),
            "event_id": event_id
        })
        return False