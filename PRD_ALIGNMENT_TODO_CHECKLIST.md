# PRD Alignment TODO Checklist
## Comprehensive Gap Analysis & Implementation Plan

**Generated:** 2025-01-XX  
**Current Status:** ~60% PRD Compliant  
**Target:** 100% PRD Alignment

---

## Executive Summary

### Current State Assessment
✅ **Implemented (60%)**
- Instagram webhook integration with Meta API
- Basic LangGraph agent structure (Qualifier, Scheduler, FollowUp)
- Supabase database with lead/property tables
- Redis state management (with graceful fallback)
- Fair Housing compliance evaluator
- Production lead processing pipeline
- Basic temporal graph client (Graphiti wrapper)

❌ **Missing Critical Features (40%)**
- Full temporal knowledge graph with Neo4j
- Google Calendar/Meet integration
- HubSpot CRM sync
- Multi-property tour optimization
- Proactive nurture with temporal triggers
- Revenue intelligence & attribution
- Multi-tenant architecture
- Complete audit trail system
- GDPR/TCPA automation

---

## Priority Matrix

### 🔴 P0 - Critical (Blocks Production)
1. Neo4j Graphiti full implementation
2. Google Calendar integration
3. Complete audit trail system
4. HITL console UI

### 🟠 P1 - High (Core PRD Features)
5. HubSpot CRM sync
6. Multi-property tour planning
7. Temporal nurture automation
8. Revenue attribution queries

### 🟡 P2 - Medium (Enhancement)
9. Multi-tenant architecture
10. Advanced analytics dashboard
11. No-show prediction
12. Market intelligence

### 🟢 P3 - Low (Nice-to-Have)
13. Mobile app
14. API endpoints for PropTech
15. White-label UI

---

## SECTION 1: TEMPORAL KNOWLEDGE GRAPH (P0)

### Current State
- ✅ Basic GraphitiClient wrapper exists
- ✅ Fallback to Supabase implemented
- ❌ Neo4j not actually connected
- ❌ No real temporal queries working
- ❌ Missing episode creation logic

### Gap Analysis
**PRD Requirement:** "Temporal memory: 'What was this lead interested in 2 weeks ago?'"  
**Current Reality:** Graphiti client exists but doesn't actually store/retrieve temporal facts

### Implementation Tasks

#### Task 1.1: Neo4j Setup & Connection
**Priority:** P0  
**Effort:** 2 hours  
**Dependencies:** None

**Steps:**
```bash
# 1. Sign up for Neo4j Aura (free tier)
# 2. Create database instance
# 3. Get connection URI and credentials
# 4. Update .env
```

**Code Changes:**
```python
# backend/.env
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
ENABLE_TEMPORAL_GRAPH=true
```

**Validation:**
```bash
# Test connection
python -c "from backend.temporal.graph_client import get_graphiti_client; import asyncio; client = get_graphiti_client(); print('Connected!' if client.graphiti else 'Failed')"
```

---

#### Task 1.2: Implement Real Episode Storage
**Priority:** P0  
**Effort:** 4 hours  
**Dependencies:** Task 1.1

**Current Issue:**
```python
# backend/temporal/graph_client.py line 180
# This doesn't actually work - Graphiti API changed
await self.graphiti.add_messages(
    group_id=f"lead_{lead_id}",
    messages=[episode_data]
)
```

**Fix Required:**
```python
# backend/temporal/graph_client.py
async def _store_in_graphiti(self, lead_id: str, event_type: str, event_data: Dict[str, Any], timestamp: datetime):
    """Store event using correct Graphiti API."""
    from graphiti_core.nodes import EpisodeType
    
    # Create episode with proper structure
    episode = await self.graphiti.add_episode(
        name=f"{event_type}_{lead_id}",
        episode_type=EpisodeType.json,
        content={
            "lead_id": lead_id,
            "event_type": event_type,
            "data": event_data,
            "timestamp": timestamp.isoformat()
        },
        source_description=f"Real Estate AI - {event_type}",
        reference_time=timestamp
    )
    
    return episode.uuid
```

**Test Case:**
```python
# backend/tests/test_temporal_graph.py
async def test_episode_storage():
    client = get_graphiti_client()
    
    result = await client.record_lead_event(
        lead_id="test_123",
        event_type="qualification",
        event_data={"budget": 500000, "location": "Miami"},
        timestamp=datetime.now()
    )
    
    assert result == True
    
    # Verify retrieval
    history = await client.get_lead_history("test_123", days_back=1)
    assert len(history) > 0
    assert history[0]["event_type"] == "qualification"
```

---

#### Task 1.3: Implement Temporal Queries
**Priority:** P0  
**Effort:** 6 hours  
**Dependencies:** Task 1.2

**PRD Examples to Implement:**
1. "What properties was this lead interested in 30 days ago?"
2. "Has their budget changed in the last 2 months?"
3. "Which leads with similar criteria ended up closing?"

**Implementation:**
```python
# backend/temporal/graph_client.py

async def query_temporal_facts(
    self,
    lead_id: str,
    query_text: str,
    as_of_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Natural language temporal query using Graphiti search.
    
    Examples:
    - "What was the budget 30 days ago?"
    - "Which properties did they view last month?"
    """
    if not as_of_date:
        as_of_date = datetime.now(timezone.utc)
    
    # Use Graphiti's semantic search
    results = await self.graphiti.search(
        query=f"Lead {lead_id}: {query_text}",
        num_results=10,
        group_ids=[f"lead_{lead_id}"]
    )
    
    # Filter by temporal validity
    temporal_results = []
    for result in results:
        episode_time = datetime.fromisoformat(result.valid_at)
        if episode_time <= as_of_date:
            temporal_results.append({
                "content": result.content,
                "timestamp": result.valid_at,
                "relevance_score": result.score
            })
    
    return temporal_results

async def detect_preference_changes(
    self,
    lead_id: str,
    lookback_days: int = 30
) -> Dict[str, Any]:
    """
    Detect if lead's preferences evolved (PRD requirement).
    
    Returns:
        {
            "budget_changed": {"from": 300000, "to": 450000, "percent_increase": 50},
            "location_changed": {"from": "Miami", "to": "Fort Lauderdale"},
            "trajectory": "escalating"
        }
    """
    # Get all qualification events
    history = await self.get_lead_history(
        lead_id,
        days_back=lookback_days,
        event_types=["qualification", "property_view"]
    )
    
    if len(history) < 2:
        return {"trajectory": "insufficient_data"}
    
    # Extract budget evolution
    budgets = []
    locations = []
    
    for event in sorted(history, key=lambda x: x["timestamp"]):
        data = event.get("event_data", {})
        if "budget" in data:
            budgets.append((event["timestamp"], data["budget"]))
        if "location" in data:
            locations.append((event["timestamp"], data["location"]))
    
    changes = {}
    
    # Budget analysis
    if len(budgets) >= 2:
        first_budget = budgets[0][1]
        last_budget = budgets[-1][1]
        
        if first_budget != last_budget:
            changes["budget_changed"] = {
                "from": first_budget,
                "to": last_budget,
                "percent_change": ((last_budget - first_budget) / first_budget) * 100,
                "trend": "increasing" if last_budget > first_budget else "decreasing"
            }
    
    # Location analysis
    if len(locations) >= 2:
        first_loc = locations[0][1]
        last_loc = locations[-1][1]
        
        if first_loc != last_loc:
            changes["location_changed"] = {
                "from": first_loc,
                "to": last_loc
            }
    
    # Determine trajectory
    if changes.get("budget_changed", {}).get("percent_change", 0) > 10:
        changes["trajectory"] = "escalating"
    elif changes.get("budget_changed", {}).get("percent_change", 0) < -10:
        changes["trajectory"] = "cooling"
    else:
        changes["trajectory"] = "stable"
    
    return changes
```

**Test Cases:**
```python
# backend/tests/test_temporal_queries.py
async def test_preference_change_detection():
    client = get_graphiti_client()
    
    # Record initial interest
    await client.record_lead_event(
        "test_lead",
        "qualification",
        {"budget": 300000, "location": "Miami"},
        datetime.now() - timedelta(days=30)
    )
    
    # Record evolved interest
    await client.record_lead_event(
        "test_lead",
        "qualification",
        {"budget": 450000, "location": "Fort Lauderdale"},
        datetime.now()
    )
    
    # Detect changes
    changes = await client.detect_preference_changes("test_lead", lookback_days=60)
    
    assert changes["budget_changed"]["from"] == 300000
    assert changes["budget_changed"]["to"] == 450000
    assert changes["budget_changed"]["percent_change"] == 50
    assert changes["location_changed"]["from"] == "Miami"
    assert changes["trajectory"] == "escalating"
```

---

#### Task 1.4: Integrate Temporal Context into Agents
**Priority:** P0  
**Effort:** 3 hours  
**Dependencies:** Task 1.3

**Update Qualifier Agent:**
```python
# backend/agents/qualifier.py

async def process(self, state: AgentState) -> Dict[str, Any]:
    lead = state["lead"]
    
    # NEW: Get temporal context
    graphiti = get_graphiti_client()
    
    # Check for preference changes
    preference_changes = await graphiti.detect_preference_changes(
        lead.user_id,
        lookback_days=90
    )
    
    # Query past interests
    past_interests = await graphiti.query_temporal_facts(
        lead.user_id,
        "What properties did they view?",
        as_of_date=datetime.now() - timedelta(days=30)
    )
    
    # Adjust qualification based on temporal context
    if preference_changes.get("trajectory") == "escalating":
        # Lead is getting more serious - boost score
        temporal_boost = 0.15
        reasoning = f"Trajectory escalating: budget increased {preference_changes['budget_changed']['percent_change']:.0f}%"
    elif preference_changes.get("trajectory") == "cooling":
        # Lead losing interest - flag for nurture
        temporal_boost = -0.1
        reasoning = "Trajectory cooling - needs re-engagement"
    else:
        temporal_boost = 0
        reasoning = "Stable engagement"
    
    # Apply temporal adjustment to score
    base_score = qualification_result["score"]
    adjusted_score = min(1.0, base_score + temporal_boost)
    
    lead.qualified_score = adjusted_score
    lead.add_history_entry(
        f"Temporal adjustment: {base_score:.2f} → {adjusted_score:.2f}",
        "qualifier",
        reasoning
    )
    
    # ... rest of qualification logic
```

---

### Validation Checklist for Section 1

- [ ] Neo4j Aura account created and connected
- [ ] Episodes successfully stored in Graphiti
- [ ] Temporal queries return correct historical data
- [ ] Preference change detection works with test data
- [ ] Qualifier agent uses temporal context
- [ ] FollowUp agent uses temporal triggers
- [ ] All tests passing: `pytest backend/tests/test_temporal_*.py`

---

## SECTION 2: GOOGLE CALENDAR INTEGRATION (P0)

### Current State
- ✅ Placeholder functions exist in `tools/calendar_integration.py`
- ❌ No actual Google Calendar API connection
- ❌ No OAuth2 flow
- ❌ No Google Meet link generation
- ❌ Scheduler agent doesn't actually book events

### Gap Analysis
**PRD Requirement:** "Frictionless Scheduling - Agent plans optimal slots (calendar + traffic + property availability)"  
**Current Reality:** Scheduler agent returns mock data, no real calendar integration


### Implementation Tasks

#### Task 2.1: Google Calendar API Setup
**Priority:** P0  
**Effort:** 2 hours  
**Dependencies:** None

**Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project: "AAA-RealEstate-AI"
3. Enable APIs:
   - Google Calendar API
   - Google Meet API (for video links)
4. Create Service Account:
   - Name: "real-estate-scheduler"
   - Role: "Editor"
   - Download JSON key
5. Share calendar with service account email

**Environment Setup:**
```bash
# backend/.env
GOOGLE_CALENDAR_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","private_key":"..."}'
GOOGLE_CALENDAR_ID=primary  # or specific calendar ID
```

**Validation:**
```python
# Test connection
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

creds_info = json.loads(os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON"))
credentials = service_account.Credentials.from_service_account_info(
    creds_info,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=credentials)
calendar_list = service.calendarList().list().execute()
print("✅ Connected to Google Calendar")
```

---

#### Task 2.2: Implement Real Calendar Functions
**Priority:** P0  
**Effort:** 6 hours  
**Dependencies:** Task 2.1

**Replace Mock Functions:**
```python
# backend/tools/calendar_integration.py

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds_json = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_CALENDAR_CREDENTIALS_JSON not set")
    
    creds_info = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=SCOPES
    )
    
    return build('calendar', 'v3', credentials=credentials)

def get_available_calendar_slots(
    days_ahead: int = 7,
    duration_minutes: int = 60,
    time_of_day: str = "flexible"
) -> List[datetime]:
    """
    Get real available slots from Google Calendar.
    
    Args:
        days_ahead: Number of days to look ahead
        duration_minutes: Required slot duration
        time_of_day: "morning" (9-12), "afternoon" (12-5), "evening" (5-8), "flexible"
    
    Returns:
        List of available datetime slots
    """
    try:
        service = get_calendar_service()
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        # Define search window
        time_windows = {
            "morning": (9, 12),
            "afternoon": (12, 17),
            "evening": (17, 20),
            "flexible": (9, 20)
        }
        start_hour, end_hour = time_windows.get(time_of_day, (9, 20))
        
        # Query busy times
        now = datetime.now()
        time_min = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        time_max = (now + timedelta(days=days_ahead)).replace(hour=end_hour, minute=0)
        
        freebusy_query = {
            "timeMin": time_min.isoformat() + "Z",
            "timeMax": time_max.isoformat() + "Z",
            "items": [{"id": calendar_id}],
            "timeZone": "America/New_York"
        }
        
        freebusy_result = service.freebusy().query(body=freebusy_query).execute()
        busy_periods = freebusy_result["calendars"][calendar_id]["busy"]
        
        # Find free slots
        available_slots = []
        current_time = time_min
        
        for busy in sorted(busy_periods, key=lambda x: x["start"]):
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
            
            # Check gap before this busy period
            gap_duration = (busy_start - current_time).total_seconds() / 60
            
            if gap_duration >= duration_minutes:
                # Add slots in this gap (every 30 minutes)
                slot_time = current_time
                while (busy_start - slot_time).total_seconds() / 60 >= duration_minutes:
                    available_slots.append(slot_time)
                    slot_time += timedelta(minutes=30)
            
            current_time = busy_end
        
        # Check final gap after last busy period
        if (time_max - current_time).total_seconds() / 60 >= duration_minutes:
            slot_time = current_time
            while (time_max - slot_time).total_seconds() / 60 >= duration_minutes:
                available_slots.append(slot_time)
                slot_time += timedelta(minutes=30)
        
        return available_slots[:10]  # Return top 10 slots
        
    except HttpError as e:
        print(f"❌ Google Calendar API error: {e}")
        return []
    except Exception as e:
        print(f"❌ Calendar error: {e}")
        return []

def book_calendar_event(
    start_time: datetime,
    duration_minutes: int,
    attendee_email: str,
    summary: str,
    description: str,
    property_addresses: List[str] = None
) -> Dict[str, Any]:
    """
    Book actual Google Calendar event with Meet link.
    
    Returns:
        {
            "event_id": "...",
            "meet_link": "https://meet.google.com/...",
            "html_link": "...",
            "status": "confirmed"
        }
    """
    try:
        service = get_calendar_service()
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Build event description with property details
        full_description = description
        if property_addresses:
            full_description += "\n\nProperties to view:\n"
            full_description += "\n".join([f"• {addr}" for addr in property_addresses])
        
        event = {
            "summary": summary,
            "description": full_description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "America/New_York"
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "America/New_York"
            },
            "attendees": [
                {"email": attendee_email, "responseStatus": "needsAction"}
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"tour-{int(start_time.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},  # 1 day before
                    {"method": "popup", "minutes": 60},       # 1 hour before
                    {"method": "popup", "minutes": 15}        # 15 min before
                ]
            },
            "guestsCanModify": False,
            "guestsCanInviteOthers": False
        }
        
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all"  # Send email to attendee
        ).execute()
        
        return {
            "event_id": created_event["id"],
            "meet_link": created_event.get("hangoutLink"),
            "html_link": created_event.get("htmlLink"),
            "status": created_event.get("status"),
            "error": None
        }
        
    except HttpError as e:
        return {
            "error": f"Google Calendar API error: {e}",
            "event_id": None
        }
    except Exception as e:
        return {
            "error": f"Booking error: {e}",
            "event_id": None
        }

def cancel_calendar_event(event_id: str, send_notification: bool = True) -> bool:
    """Cancel a calendar event."""
    try:
        service = get_calendar_service()
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendUpdates="all" if send_notification else "none"
        ).execute()
        
        return True
        
    except HttpError as e:
        if e.resp.status == 410:
            # Already deleted - idempotent
            return True
        print(f"❌ Cancel error: {e}")
        return False
```

---

#### Task 2.3: Update Scheduler Agent to Use Real Calendar
**Priority:** P0  
**Effort:** 3 hours  
**Dependencies:** Task 2.2

**Update Scheduler Agent:**
```python
# backend/agents/scheduler.py

def process(self, state: AgentState) -> Dict[str, Any]:
    lead = state["lead"]
    messages = state.get("messages", [])
    
    try:
        # Get REAL available slots
        available_slots = get_available_calendar_slots(
            days_ahead=7,
            duration_minutes=60,
            time_of_day="flexible"
        )
        
        if not available_slots:
            response_msg = "I'm currently fully booked this week. Let me check next week's availability..."
            
            # Try next week
            available_slots = get_available_calendar_slots(
                days_ahead=14,
                duration_minutes=60
            )
        
        if available_slots and lead.email:
            # Present top 3 options to lead
            slot_options = available_slots[:3]
            
            slots_text = "\n".join([
                f"{i+1}. {slot.strftime('%A, %B %d at %I:%M %p')}"
                for i, slot in enumerate(slot_options)
            ])
            
            response_msg = f"I have these times available for your property tour:\n\n{slots_text}\n\nWhich works best for you? (Reply with the number)"
            
            # Store slots in state for confirmation
            state["pending_slots"] = slot_options
            
        elif not lead.email:
            response_msg = "To schedule your tour, I'll need your email address for the calendar invitation. Could you provide it?"
        
        else:
            response_msg = "I apologize, but I don't have availability in the next two weeks. Let me connect you with our team to find a time that works."
        
        # Send response
        send_instagram_message.invoke({
            "user_id": lead.user_id,
            "message": response_msg
        })
        
        messages.append({
            "role": "assistant",
            "content": response_msg
        })
        
        return {
            "lead": lead,
            "messages": messages,
            "available_slots": available_slots,
            "next_agent": "END"
        }
        
    except Exception as e:
        lead.add_history_entry(f"Scheduling error: {str(e)}", "scheduler")
        return {
            "lead": lead,
            "messages": messages,
            "next_agent": "followup",
            "error_message": str(e)
        }

def confirm_booking(self, state: AgentState, slot_index: int) -> Dict[str, Any]:
    """
    Confirm and book the selected slot.
    
    Called when lead replies with slot number.
    """
    lead = state["lead"]
    pending_slots = state.get("pending_slots", [])
    
    if slot_index < 0 or slot_index >= len(pending_slots):
        return {"error": "Invalid slot selection"}
    
    selected_slot = pending_slots[slot_index]
    
    # Get property addresses for tour
    db_results = state.get("db_results", [])
    property_addresses = [
        f"{prop['location']} - ${prop['price']:,}"
        for prop in db_results[:3]
    ]
    
    # BOOK REAL CALENDAR EVENT
    booking_result = book_calendar_event(
        start_time=selected_slot,
        duration_minutes=60,
        attendee_email=lead.email,
        summary=f"Property Tour - {lead.name or lead.user_id}",
        description=f"Property tour for {lead.property_type} in {lead.location}, budget: ${lead.budget:,}",
        property_addresses=property_addresses
    )
    
    if booking_result.get("error"):
        response_msg = f"I apologize, there was an issue booking that time. Let me try another slot or connect you with our team."
        lead.add_history_entry(f"Booking failed: {booking_result['error']}", "scheduler")
    else:
        # Success!
        lead.meeting_slot = selected_slot.isoformat()
        lead.status = "scheduled"
        lead.calendar_event_id = booking_result["event_id"]
        
        response_msg = f"✅ Perfect! Your property tour is confirmed for {selected_slot.strftime('%A, %B %d at %I:%M %p')}.\n\n"
        response_msg += f"📧 Calendar invitation sent to {lead.email}\n"
        
        if booking_result.get("meet_link"):
            response_msg += f"🎥 Video link: {booking_result['meet_link']}\n\n"
        
        response_msg += "Looking forward to showing you some great properties!"
        
        lead.add_history_entry("Tour successfully scheduled", "scheduler", booking_result)
        
        # Save to database
        save_lead_tool.invoke({"lead_data": lead.to_dict()})
    
    return {
        "lead": lead,
        "booking_result": booking_result,
        "response_message": response_msg
    }
```

---

#### Task 2.4: Add Slot Confirmation Flow
**Priority:** P0  
**Effort:** 2 hours  
**Dependencies:** Task 2.3

**Handle User Slot Selection:**
```python
# backend/tasks/production_lead_processing.py

async def handle_slot_selection(user_id: str, message: str) -> Dict[str, Any]:
    """
    Handle when user replies with slot number (1, 2, or 3).
    """
    # Get thread state from Redis
    thread_state = redis_client.get(f"langgraph:thread:{user_id}")
    
    if not thread_state:
        return {"error": "No pending booking found"}
    
    state = json.loads(thread_state)
    
    # Check if they replied with a number
    import re
    slot_match = re.search(r'\b([1-3])\b', message)
    
    if slot_match and state.get("pending_slots"):
        slot_index = int(slot_match.group(1)) - 1
        
        # Confirm booking
        from agents.scheduler import SchedulerAgent
        scheduler = SchedulerAgent()
        
        result = scheduler.confirm_booking(state, slot_index)
        
        # Send confirmation message
        await send_instagram_reply(
            user_id,
            result["response_message"]
        )
        
        # Update state
        state.update(result)
        redis_client.setex(
            f"langgraph:thread:{user_id}",
            86400,
            json.dumps(state, default=str)
        )
        
        return result
    
    return {"error": "Could not parse slot selection"}
```

---

### Validation Checklist for Section 2

- [ ] Google Calendar API enabled and service account created
- [ ] Real calendar slots retrieved successfully
- [ ] Events booked with Google Meet links
- [ ] Email invitations sent to leads
- [ ] Scheduler agent uses real calendar data
- [ ] Slot confirmation flow works end-to-end
- [ ] Test: Book a tour and verify calendar event created
- [ ] Test: Cancel event and verify deletion

---


## SECTION 3: HUBSPOT CRM INTEGRATION (P1)

### Current State
- ✅ Placeholder functions exist in `tools/agent_tools.py`
- ❌ No actual HubSpot API connection
- ❌ No contact/deal creation
- ❌ No bidirectional sync

### Gap Analysis
**PRD Requirement:** "CRM logging → Manual entry (20% data quality, zero temporal memory)"  
**Current Reality:** No CRM integration at all

### Implementation Tasks

#### Task 3.1: HubSpot API Setup
**Priority:** P1  
**Effort:** 1 hour  
**Dependencies:** None

**Steps:**
1. Sign up for HubSpot (free tier available)
2. Go to Settings → Integrations → Private Apps
3. Create app: "AAA Real Estate AI"
4. Grant scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `crm.schemas.contacts.read`
   - `crm.schemas.deals.read`
5. Copy API key

**Environment Setup:**
```bash
# backend/.env
HUBSPOT_API_KEY=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
HUBSPOT_ENABLED=true
```

---

#### Task 3.2: Implement HubSpot Client
**Priority:** P1  
**Effort:** 4 hours  
**Dependencies:** Task 3.1

**Create HubSpot Client:**
```python
# backend/utils/hubspot_client.py

import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime

class HubSpotClient:
    """HubSpot CRM integration client."""
    
    def __init__(self):
        self.api_key = os.getenv("HUBSPOT_API_KEY")
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def create_contact(
        self,
        email: str,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        **custom_properties
    ) -> Dict[str, Any]:
        """
        Create HubSpot contact.
        
        Returns:
            {"contact_id": "...", "status": "created"}
        """
        try:
            # Check if contact exists
            existing = self.find_contact_by_email(email)
            if existing:
                return {
                    "contact_id": existing["id"],
                    "status": "existing",
                    "error": None
                }
            
            # Create new contact
            properties = {
                "email": email,
                "firstname": first_name,
                "lastname": last_name,
                "phone": phone,
                "lifecyclestage": "lead",
                "lead_source": "Instagram AI Bot",
                **custom_properties
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self.headers,
                json={"properties": properties}
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "contact_id": data["id"],
                    "status": "created",
                    "error": None
                }
            else:
                return {
                    "contact_id": None,
                    "status": "error",
                    "error": response.text
                }
                
        except Exception as e:
            return {
                "contact_id": None,
                "status": "error",
                "error": str(e)
            }
    
    def find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find contact by email."""
        try:
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email
                        }]
                    }]
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    return data["results"][0]
            
            return None
            
        except Exception:
            return None
    
    def create_deal(
        self,
        contact_id: str,
        deal_name: str,
        amount: float,
        deal_stage: str = "appointmentscheduled",
        **custom_properties
    ) -> Dict[str, Any]:
        """
        Create HubSpot deal and associate with contact.
        
        Deal stages:
        - appointmentscheduled
        - qualifiedtobuy
        - presentationscheduled
        - decisionmakerboughtin
        - contractsent
        - closedwon
        - closedlost
        """
        try:
            properties = {
                "dealname": deal_name,
                "amount": str(amount),
                "dealstage": deal_stage,
                "pipeline": "default",
                "closedate": (datetime.now().replace(day=1, month=datetime.now().month + 3)).isoformat(),
                **custom_properties
            }
            
            # Create deal
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=self.headers,
                json={"properties": properties}
            )
            
            if response.status_code != 201:
                return {
                    "deal_id": None,
                    "status": "error",
                    "error": response.text
                }
            
            deal_data = response.json()
            deal_id = deal_data["id"]
            
            # Associate deal with contact
            association_response = requests.put(
                f"{self.base_url}/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/3",
                headers=self.headers
            )
            
            return {
                "deal_id": deal_id,
                "status": "created",
                "error": None
            }
            
        except Exception as e:
            return {
                "deal_id": None,
                "status": "error",
                "error": str(e)
            }
    
    def update_deal_stage(self, deal_id: str, new_stage: str) -> bool:
        """Update deal stage."""
        try:
            response = requests.patch(
                f"{self.base_url}/crm/v3/objects/deals/{deal_id}",
                headers=self.headers,
                json={
                    "properties": {
                        "dealstage": new_stage
                    }
                }
            )
            
            return response.status_code == 200
            
        except Exception:
            return False
    
    def add_note_to_contact(
        self,
        contact_id: str,
        note_body: str
    ) -> bool:
        """Add note/activity to contact."""
        try:
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/notes",
                headers=self.headers,
                json={
                    "properties": {
                        "hs_note_body": note_body,
                        "hs_timestamp": datetime.now().isoformat()
                    },
                    "associations": [{
                        "to": {"id": contact_id},
                        "types": [{
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 202  # Note to Contact
                        }]
                    }]
                }
            )
            
            return response.status_code == 201
            
        except Exception:
            return False

# Global client instance
_hubspot_client = None

def get_hubspot_client() -> HubSpotClient:
    """Get or create HubSpot client."""
    global _hubspot_client
    if _hubspot_client is None:
        _hubspot_client = HubSpotClient()
    return _hubspot_client
```

---

#### Task 3.3: Integrate HubSpot into Workflow
**Priority:** P1  
**Effort:** 3 hours  
**Dependencies:** Task 3.2

**Update Scheduler Agent:**
```python
# backend/agents/scheduler.py

def confirm_booking(self, state: AgentState, slot_index: int) -> Dict[str, Any]:
    lead = state["lead"]
    selected_slot = state["pending_slots"][slot_index]
    
    # Book calendar event (existing code)
    booking_result = book_calendar_event(...)
    
    if booking_result.get("error"):
        return {...}
    
    # NEW: Sync to HubSpot
    if os.getenv("HUBSPOT_ENABLED") == "true":
        from utils.hubspot_client import get_hubspot_client
        
        hubspot = get_hubspot_client()
        
        # Create/update contact
        contact_result = hubspot.create_contact(
            email=lead.email,
            first_name=lead.name.split()[0] if lead.name else "",
            last_name=" ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else "",
            phone=lead.user_id,  # Instagram ID as phone placeholder
            budget_max=str(lead.budget) if lead.budget else "",
            desired_bedrooms=str(lead.desired_bedrooms) if lead.desired_bedrooms else "",
            preferred_location=lead.location or "",
            lead_status="scheduled"
        )
        
        if contact_result["contact_id"]:
            # Create deal
            deal_result = hubspot.create_deal(
                contact_id=contact_result["contact_id"],
                deal_name=f"Property Tour - {lead.name or lead.user_id}",
                amount=lead.budget or 0,
                deal_stage="appointmentscheduled",
                property_type=lead.property_type or "",
                tour_date=selected_slot.isoformat()
            )
            
            # Add note with conversation history
            conversation_summary = "\n".join([
                f"{msg['role']}: {msg['content'][:100]}..."
                for msg in state.get("messages", [])[-5:]  # Last 5 messages
            ])
            
            hubspot.add_note_to_contact(
                contact_result["contact_id"],
                f"AI Agent Conversation:\n{conversation_summary}\n\nTour scheduled for {selected_slot.strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Store HubSpot IDs in lead
            lead.hubspot_contact_id = contact_result["contact_id"]
            lead.hubspot_deal_id = deal_result.get("deal_id")
            
            lead.add_history_entry(
                "Synced to HubSpot CRM",
                "scheduler",
                {
                    "contact_id": contact_result["contact_id"],
                    "deal_id": deal_result.get("deal_id")
                }
            )
    
    # ... rest of confirmation logic
```

**Update Qualifier Agent:**
```python
# backend/agents/qualifier.py

def process(self, state: AgentState) -> Dict[str, Any]:
    lead = state["lead"]
    
    # ... existing qualification logic ...
    
    # NEW: Create HubSpot contact for qualified leads
    if lead.qualified_score > 0.7 and os.getenv("HUBSPOT_ENABLED") == "true":
        from utils.hubspot_client import get_hubspot_client
        
        hubspot = get_hubspot_client()
        
        if lead.email:
            contact_result = hubspot.create_contact(
                email=lead.email,
                first_name=lead.name.split()[0] if lead.name else "",
                phone=lead.user_id,
                budget_max=str(lead.budget) if lead.budget else "",
                lifecyclestage="marketingqualifiedlead",
                lead_score=str(int(lead.qualified_score * 100))
            )
            
            if contact_result["contact_id"]:
                lead.hubspot_contact_id = contact_result["contact_id"]
                lead.add_history_entry("Created HubSpot contact", "qualifier")
    
    # ... rest of qualification logic
```

---

### Validation Checklist for Section 3

- [ ] HubSpot API key configured
- [ ] Contacts created successfully
- [ ] Deals created and associated with contacts
- [ ] Notes added to contact timeline
- [ ] Scheduler agent syncs bookings to HubSpot
- [ ] Qualifier agent creates contacts for qualified leads
- [ ] Test: Complete workflow and verify HubSpot records
- [ ] Test: View contact in HubSpot with full activity history

---


## SECTION 4: MULTI-PROPERTY TOUR OPTIMIZATION (P1)

### Current State
- ❌ No multi-property tour planning
- ❌ No travel time calculation
- ❌ No route optimization
- ❌ No Google Maps integration

### Gap Analysis
**PRD Requirement:** "Multi-constraint planner (calendar + property + traffic)"  
**Current Reality:** Single property booking only, no optimization

### Implementation Tasks

#### Task 4.1: Google Maps API Setup
**Priority:** P1  
**Effort:** 1 hour  
**Dependencies:** None

**Steps:**
1. Enable Google Maps Distance Matrix API
2. Enable Google Maps Directions API
3. Get API key

**Environment Setup:**
```bash
# backend/.env
GOOGLE_MAPS_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

---

#### Task 4.2: Implement Travel Time Calculator
**Priority:** P1  
**Effort:** 3 hours  
**Dependencies:** Task 4.1

**Create Maps Client:**
```python
# backend/utils/maps_client.py

import os
import requests
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

class GoogleMapsClient:
    """Google Maps integration for travel time and routing."""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def get_travel_time(
        self,
        origin: str,
        destination: str,
        departure_time: datetime = None
    ) -> Dict[str, Any]:
        """
        Get travel time between two addresses.
        
        Returns:
            {
                "duration_minutes": 25,
                "distance_miles": 12.5,
                "traffic_delay_minutes": 5
            }
        """
        try:
            if not departure_time:
                departure_time = datetime.now()
            
            params = {
                "origins": origin,
                "destinations": destination,
                "departure_time": int(departure_time.timestamp()),
                "traffic_model": "best_guess",
                "key": self.api_key
            }
            
            response = requests.get(
                f"{self.base_url}/distancematrix/json",
                params=params
            )
            
            if response.status_code != 200:
                return {"error": "Maps API error"}
            
            data = response.json()
            
            if data["status"] != "OK":
                return {"error": data["status"]}
            
            element = data["rows"][0]["elements"][0]
            
            if element["status"] != "OK":
                return {"error": element["status"]}
            
            duration_seconds = element["duration"]["value"]
            distance_meters = element["distance"]["value"]
            
            # Get duration in traffic if available
            duration_in_traffic = element.get("duration_in_traffic", {}).get("value", duration_seconds)
            
            return {
                "duration_minutes": duration_seconds // 60,
                "distance_miles": distance_meters / 1609.34,
                "traffic_delay_minutes": (duration_in_traffic - duration_seconds) // 60,
                "error": None
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def optimize_route(
        self,
        start_location: str,
        property_addresses: List[str],
        return_to_start: bool = False
    ) -> Dict[str, Any]:
        """
        Optimize route through multiple properties.
        
        Uses nearest-neighbor algorithm for simplicity.
        For >10 properties, consider TSP solver.
        
        Returns:
            {
                "optimized_order": [2, 0, 1],  # Indices of properties
                "total_duration_minutes": 90,
                "total_distance_miles": 45.2,
                "route_segments": [...]
            }
        """
        try:
            if len(property_addresses) <= 1:
                return {
                    "optimized_order": list(range(len(property_addresses))),
                    "total_duration_minutes": 0,
                    "total_distance_miles": 0,
                    "route_segments": []
                }
            
            # Build distance matrix
            all_locations = [start_location] + property_addresses
            distance_matrix = {}
            
            for i, origin in enumerate(all_locations):
                for j, dest in enumerate(all_locations):
                    if i != j:
                        travel = self.get_travel_time(origin, dest)
                        distance_matrix[(i, j)] = {
                            "duration": travel.get("duration_minutes", 999),
                            "distance": travel.get("distance_miles", 999)
                        }
            
            # Nearest-neighbor optimization
            unvisited = set(range(1, len(all_locations)))  # Exclude start (index 0)
            route = [0]  # Start at office/agent location
            current = 0
            
            while unvisited:
                nearest = min(
                    unvisited,
                    key=lambda x: distance_matrix.get((current, x), {}).get("duration", 999)
                )
                route.append(nearest)
                unvisited.remove(nearest)
                current = nearest
            
            if return_to_start:
                route.append(0)
            
            # Calculate total metrics
            total_duration = 0
            total_distance = 0
            route_segments = []
            
            for i in range(len(route) - 1):
                from_idx = route[i]
                to_idx = route[i + 1]
                
                segment = distance_matrix.get((from_idx, to_idx), {})
                total_duration += segment.get("duration", 0)
                total_distance += segment.get("distance", 0)
                
                route_segments.append({
                    "from": all_locations[from_idx],
                    "to": all_locations[to_idx],
                    "duration_minutes": segment.get("duration", 0),
                    "distance_miles": segment.get("distance", 0)
                })
            
            # Convert route indices (subtract 1 to get property indices)
            optimized_property_order = [idx - 1 for idx in route[1:] if idx > 0]
            
            return {
                "optimized_order": optimized_property_order,
                "total_duration_minutes": total_duration,
                "total_distance_miles": total_distance,
                "route_segments": route_segments,
                "error": None
            }
            
        except Exception as e:
            return {"error": str(e)}

# Global client
_maps_client = None

def get_maps_client() -> GoogleMapsClient:
    global _maps_client
    if _maps_client is None:
        _maps_client = GoogleMapsClient()
    return _maps_client
```

---

#### Task 4.3: Implement Multi-Property Tour Scheduler
**Priority:** P1  
**Effort:** 4 hours  
**Dependencies:** Task 4.2

**Update Scheduler Agent:**
```python
# backend/agents/scheduler.py

def plan_multi_property_tour(
    self,
    state: AgentState,
    selected_slot: datetime,
    property_ids: List[str]
) -> Dict[str, Any]:
    """
    Plan optimized multi-property tour.
    
    Returns:
        {
            "tour_schedule": [...],
            "total_duration_minutes": 180,
            "properties_order": [1, 0, 2]
        }
    """
    try:
        from utils.maps_client import get_maps_client
        from utils.supabase_client import supabase
        
        # Get property details
        properties = []
        for prop_id in property_ids:
            result = supabase.table("properties").select("*").eq("id", prop_id).execute()
            if result.data:
                properties.append(result.data[0])
        
        if not properties:
            return {"error": "No properties found"}
        
        # Get property addresses
        property_addresses = [
            f"{prop['location']}, FL"  # Assuming Florida
            for prop in properties
        ]
        
        # Optimize route
        maps = get_maps_client()
        agent_office = os.getenv("AGENT_OFFICE_ADDRESS", "Miami, FL")
        
        route_plan = maps.optimize_route(
            start_location=agent_office,
            property_addresses=property_addresses,
            return_to_start=False
        )
        
        if route_plan.get("error"):
            return {"error": route_plan["error"]}
        
        # Build tour schedule
        tour_schedule = []
        current_time = selected_slot
        viewing_duration = 45  # minutes per property
        
        # Start at office
        tour_schedule.append({
            "type": "start",
            "location": agent_office,
            "time": current_time.strftime("%I:%M %p"),
            "notes": "Meet at office"
        })
        
        # Visit properties in optimized order
        for i, prop_idx in enumerate(route_plan["optimized_order"]):
            property_data = properties[prop_idx]
            
            # Add travel segment
            if i < len(route_plan["route_segments"]):
                segment = route_plan["route_segments"][i]
                travel_time = segment["duration_minutes"]
                
                tour_schedule.append({
                    "type": "travel",
                    "duration_minutes": travel_time,
                    "distance_miles": segment["distance_miles"],
                    "notes": f"{travel_time} min drive"
                })
                
                current_time += timedelta(minutes=travel_time)
            
            # Add property viewing
            tour_schedule.append({
                "type": "viewing",
                "property_id": property_data["id"],
                "address": property_data["location"],
                "price": property_data["price"],
                "bedrooms": property_data.get("bedrooms"),
                "time": current_time.strftime("%I:%M %p"),
                "duration_minutes": viewing_duration,
                "notes": f"Property viewing ({viewing_duration} min)"
            })
            
            current_time += timedelta(minutes=viewing_duration)
        
        # Calculate total duration
        total_duration = (current_time - selected_slot).total_seconds() / 60
        
        return {
            "tour_schedule": tour_schedule,
            "total_duration_minutes": int(total_duration),
            "properties_order": route_plan["optimized_order"],
            "total_distance_miles": route_plan["total_distance_miles"],
            "start_time": selected_slot,
            "end_time": current_time,
            "error": None
        }
        
    except Exception as e:
        return {"error": str(e)}

def format_tour_schedule(self, tour_plan: Dict[str, Any]) -> str:
    """Format tour schedule as readable message."""
    
    schedule_text = f"🗓️ **Property Tour Schedule**\n\n"
    schedule_text += f"📅 Date: {tour_plan['start_time'].strftime('%A, %B %d, %Y')}\n"
    schedule_text += f"⏱️ Duration: {tour_plan['total_duration_minutes']} minutes\n"
    schedule_text += f"🚗 Total Distance: {tour_plan['total_distance_miles']:.1f} miles\n\n"
    
    for item in tour_plan["tour_schedule"]:
        if item["type"] == "start":
            schedule_text += f"🏢 {item['time']} - {item['notes']}\n"
        elif item["type"] == "travel":
            schedule_text += f"🚗 {item['notes']} ({item['distance_miles']:.1f} mi)\n"
        elif item["type"] == "viewing":
            schedule_text += f"\n📍 {item['time']} - {item['address']}\n"
            schedule_text += f"   💰 ${item['price']:,} | {item['bedrooms']}BR\n"
            schedule_text += f"   ⏱️ {item['duration_minutes']} min viewing\n"
    
    return schedule_text
```

---

### Validation Checklist for Section 4

- [ ] Google Maps API enabled and key configured
- [ ] Travel time calculation working
- [ ] Route optimization returns correct order
- [ ] Multi-property tour schedule generated
- [ ] Calendar event includes all properties
- [ ] Test: Plan 3-property tour and verify optimal route
- [ ] Test: Verify total duration includes travel + viewing time

---

## SECTION 5: COMPLETE AUDIT TRAIL SYSTEM (P0)

### Current State
- ✅ Basic audit_log_event function exists
- ❌ No immutable storage (just prints to console)
- ❌ No audit_logs table in Supabase
- ❌ No tamper detection (hashing)
- ❌ No compliance-grade logging

### Gap Analysis
**PRD Requirement:** "Immutable audit logs for all agent actions"  
**Current Reality:** Audit events logged to console only, no persistence

### Implementation Tasks

#### Task 5.1: Create Audit Logs Table
**Priority:** P0  
**Effort:** 1 hour  
**Dependencies:** None

**SQL Schema:**
```sql
-- backend/scripts/create_audit_logs_table.sql

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event identification
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL, -- 'agent_action', 'compliance', 'system', 'user_interaction'
    
    -- Entity tracking
    entity_type VARCHAR(50), -- 'lead', 'conversation', 'tour', 'message'
    entity_id VARCHAR(255),
    
    -- Agent context
    agent_type VARCHAR(50), -- 'qualifier', 'scheduler', 'followup', 'human'
    agent_action VARCHAR(100),
    
    -- State snapshots
    state_before JSONB,
    state_after JSONB,
    
    -- Policy & compliance
    policy_checks JSONB,
    compliance_flags TEXT[],
    
    -- Human review
    human_reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMPTZ,
    
    -- Temporal tracking
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Tamper detection
    event_hash VARCHAR(64) NOT NULL, -- SHA-256 of event data
    prev_hash VARCHAR(64), -- Hash of previous event (blockchain-style)
    
    -- Metadata
    metadata JSONB,
    
    -- Indexes for fast queries
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type, timestamp DESC);
CREATE INDEX idx_audit_logs_agent ON audit_logs(agent_type, timestamp DESC);
CREATE INDEX idx_audit_logs_compliance ON audit_logs USING GIN(compliance_flags);
CREATE INDEX idx_audit_logs_human_review ON audit_logs(human_reviewed) WHERE human_reviewed = FALSE;
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- Enable Row Level Security
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Audit logs are append-only (no updates/deletes)
CREATE POLICY "Audit logs are append-only" ON audit_logs
    FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Audit logs are read-only after creation" ON audit_logs
    FOR SELECT
    USING (true);

-- Prevent updates and deletes
CREATE POLICY "No updates allowed" ON audit_logs
    FOR UPDATE
    USING (false);

CREATE POLICY "No deletes allowed" ON audit_logs
    FOR DELETE
    USING (false);
```

**Run Migration:**
```bash
cd backend
psql $DATABASE_URL -f scripts/create_audit_logs_table.sql
```

---

#### Task 5.2: Implement Immutable Audit Logger
**Priority:** P0  
**Effort:** 3 hours  
**Dependencies:** Task 5.1

**Update Audit Module:**
```python
# backend/utils/audit.py

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
from utils.supabase_client import supabase

class AuditLogger:
    """
    Immutable audit logger with tamper detection.
    
    Features:
    - Blockchain-style hash chaining
    - Append-only storage
    - Compliance-grade logging
    """
    
    def __init__(self):
        self.last_hash = self._get_last_hash()
    
    def _get_last_hash(self) -> Optional[str]:
        """Get hash of most recent audit log entry."""
        try:
            result = supabase.table("audit_logs")\
                .select("event_hash")\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                return result.data[0]["event_hash"]
            
            return None
            
        except Exception:
            return None
    
    def _compute_hash(self, event_data: Dict[str, Any], prev_hash: Optional[str]) -> str:
        """Compute SHA-256 hash of event data."""
        hash_input = json.dumps(event_data, sort_keys=True, default=str)
        if prev_hash:
            hash_input = prev_hash + hash_input
        
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        event_category: str = "system",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        agent_action: Optional[str] = None,
        state_before: Optional[Dict] = None,
        state_after: Optional[Dict] = None,
        policy_checks: Optional[Dict] = None,
        compliance_flags: Optional[list] = None
    ) -> bool:
        """
        Log audit event with tamper detection.
        
        Returns:
            True if logged successfully
        """
        try:
            timestamp = datetime.now().isoformat()
            
            # Prepare event record
            event_record = {
                "event_type": event_type,
                "event_category": event_category,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "agent_type": agent_type,
                "agent_action": agent_action,
                "state_before": state_before,
                "state_after": state_after,
                "policy_checks": policy_checks,
                "compliance_flags": compliance_flags or [],
                "timestamp": timestamp,
                "metadata": event_data
            }
            
            # Compute hash with chaining
            event_hash = self._compute_hash(event_record, self.last_hash)
            event_record["event_hash"] = event_hash
            event_record["prev_hash"] = self.last_hash
            
            # Insert into database (append-only)
            result = supabase.table("audit_logs").insert(event_record).execute()
            
            if result.data:
                # Update last hash for next event
                self.last_hash = event_hash
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Audit logging failed: {e}")
            # Fallback: Write to file
            self._fallback_log(event_type, event_data)
            return False
    
    def _fallback_log(self, event_type: str, event_data: Dict[str, Any]):
        """Fallback logging to file if database fails."""
        try:
            import os
            fallback_dir = "backend/audit_fallback"
            os.makedirs(fallback_dir, exist_ok=True)
            
            filename = f"{fallback_dir}/audit_fallback_{datetime.now().date()}.jsonl"
            
            with open(filename, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "event_type": event_type,
                    "data": event_data
                }) + "\n")
                
        except Exception as e:
            print(f"❌ Fallback logging failed: {e}")
    
    def verify_chain_integrity(self, limit: int = 100) -> Dict[str, Any]:
        """
        Verify audit log chain integrity.
        
        Returns:
            {
                "valid": True/False,
                "total_checked": 100,
                "broken_links": []
            }
        """
        try:
            # Get recent audit logs
            result = supabase.table("audit_logs")\
                .select("id, event_hash, prev_hash, created_at")\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()
            
            logs = result.data
            
            if not logs:
                return {"valid": True, "total_checked": 0, "broken_links": []}
            
            broken_links = []
            
            for i in range(1, len(logs)):
                current = logs[i]
                previous = logs[i - 1]
                
                # Check if current.prev_hash matches previous.event_hash
                if current["prev_hash"] != previous["event_hash"]:
                    broken_links.append({
                        "index": i,
                        "log_id": current["id"],
                        "expected_prev_hash": previous["event_hash"],
                        "actual_prev_hash": current["prev_hash"]
                    })
            
            return {
                "valid": len(broken_links) == 0,
                "total_checked": len(logs),
                "broken_links": broken_links
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

# Global logger instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

def audit_log_event(event_type: str, event_data: Dict[str, Any], **kwargs) -> bool:
    """Convenience function for logging audit events."""
    logger = get_audit_logger()
    return logger.log_event(event_type, event_data, **kwargs)
```

---

#### Task 5.3: Integrate Audit Logging into All Agents
**Priority:** P0  
**Effort:** 2 hours  
**Dependencies:** Task 5.2

**Update Agent Actions:**
```python
# backend/agents/qualifier.py

def process(self, state: AgentState) -> Dict[str, Any]:
    lead = state["lead"]
    
    # Capture state before
    state_before = lead.to_dict()
    
    # ... qualification logic ...
    
    # Capture state after
    state_after = lead.to_dict()
    
    # Log to audit trail
    audit_log_event(
        event_type="lead_qualified",
        event_category="agent_action",
        entity_type="lead",
        entity_id=lead.user_id,
        agent_type="qualifier",
        agent_action="qualify_and_score",
        state_before=state_before,
        state_after=state_after,
        policy_checks=compliance_check if 'compliance_check' in locals() else None,
        compliance_flags=["fair_housing_checked"],
        event_data={
            "qualified_score": lead.qualified_score,
            "properties_found": len(db_results),
            "next_agent": next_agent
        }
    )
    
    # ... rest of logic
```

---

### Validation Checklist for Section 5

- [ ] audit_logs table created in Supabase
- [ ] RLS policies prevent updates/deletes
- [ ] Hash chaining working correctly
- [ ] All agent actions logged
- [ ] Compliance checks logged
- [ ] Chain integrity verification passes
- [ ] Test: Verify audit trail for complete workflow
- [ ] Test: Attempt to modify audit log (should fail)

---


## SECTION 6: REMAINING PRD GAPS (P1-P2)

### 6.1 Proactive Nurture Automation (P1)

**Current State:** Basic nurture logic exists but not automated  
**Gap:** No cron jobs, no temporal triggers, no automated re-engagement

**Implementation:**
```python
# backend/tasks/nurture_automation.py

from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
from utils.supabase_client import supabase
from agents.followup import FollowUpAgent
from temporal.graph_client import get_graphiti_client

app = Celery('nurture_tasks', broker='redis://localhost:6379/0')

@app.task
def detect_cooling_leads():
    """
    Daily task: Detect leads that haven't engaged in 7+ days.
    """
    cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
    
    result = supabase.table("leads")\
        .select("*")\
        .lt("last_interaction_at", cutoff_date)\
        .in_("status", ["qualified", "new"])\
        .execute()
    
    cooling_leads = result.data or []
    
    for lead in cooling_leads:
        # Trigger nurture workflow
        trigger_nurture_workflow.delay(lead["user_id"])
    
    return {"cooling_leads_found": len(cooling_leads)}

@app.task
def trigger_nurture_workflow(user_id: str):
    """
    Execute nurture workflow for a specific lead.
    """
    # Get lead data
    result = supabase.table("leads").select("*").eq("user_id", user_id).execute()
    
    if not result.data:
        return {"error": "Lead not found"}
    
    lead_data = result.data[0]
    
    # Get temporal context
    graphiti = get_graphiti_client()
    
    # Generate nurture action
    from tools.nurture import generate_nurture_action
    nurture_action = generate_nurture_action(lead_data, graphiti)
    
    # Send message via Instagram
    if nurture_action.get("message"):
        from tools.agent_tools import send_instagram_message
        send_instagram_message.invoke({
            "user_id": user_id,
            "message": nurture_action["message"]
        })
        
        # Log nurture action
        from utils.audit import audit_log_event
        audit_log_event(
            "automated_nurture_sent",
            {
                "user_id": user_id,
                "action_type": nurture_action["type"],
                "priority": nurture_action["priority"]
            },
            event_category="agent_action",
            agent_type="followup"
        )
    
    return {"status": "success", "action_type": nurture_action.get("type")}

@app.task
def check_new_inventory_matches():
    """
    Hourly task: Check for new properties matching lead criteria.
    """
    # Get all active leads
    result = supabase.table("leads")\
        .select("*")\
        .in_("status", ["qualified", "new", "nurtured"])\
        .execute()
    
    leads = result.data or []
    matches_found = 0
    
    for lead in leads:
        if not lead.get("budget") or not lead.get("location"):
            continue
        
        # Check for new properties (last 24 hours)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        props_result = supabase.table("properties")\
            .select("*")\
            .lte("price", lead["budget"])\
            .eq("location", lead["location"])\
            .gte("created_at", cutoff)\
            .execute()
        
        new_properties = props_result.data or []
        
        if new_properties:
            # Send property alert
            send_property_alert.delay(lead["user_id"], new_properties)
            matches_found += 1
    
    return {"leads_checked": len(leads), "matches_found": matches_found}

@app.task
def send_property_alert(user_id: str, properties: list):
    """Send new property alert to lead."""
    message = f"🏠 New Property Alert!\n\n"
    message += f"I found {len(properties)} new properties that match your criteria:\n\n"
    
    for prop in properties[:3]:
        message += f"• {prop['property_type']} in {prop['location']} - ${prop['price']:,}\n"
    
    message += "\nThese just hit the market! Would you like to schedule viewings?"
    
    from tools.agent_tools import send_instagram_message
    send_instagram_message.invoke({
        "user_id": user_id,
        "message": message
    })

# Celery beat schedule
app.conf.beat_schedule = {
    'detect-cooling-leads-daily': {
        'task': 'nurture_automation.detect_cooling_leads',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
    'check-new-inventory-hourly': {
        'task': 'nurture_automation.check_new_inventory_matches',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

**Setup:**
```bash
# Install Celery
pip install celery redis

# Start Celery worker
celery -A backend.tasks.nurture_automation worker --loglevel=info

# Start Celery beat (scheduler)
celery -A backend.tasks.nurture_automation beat --loglevel=info
```

---

### 6.2 Revenue Intelligence & Attribution (P1)

**Current State:** No analytics, no attribution queries  
**Gap:** Cannot answer "which actions drove closings?"

**Implementation:**
```python
# backend/utils/analytics.py

from datetime import datetime, timedelta
from typing import Dict, Any, List
from utils.supabase_client import supabase
from temporal.graph_client import get_graphiti_client

class RevenueAnalytics:
    """Revenue intelligence and attribution queries."""
    
    def get_lead_to_close_attribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Analyze which agent actions led to closings.
        
        Returns:
            {
                "total_closed_deals": 5,
                "total_revenue": 2500000,
                "attribution_by_agent": {...},
                "avg_time_to_close_days": 45
            }
        """
        # Get closed deals
        result = supabase.table("leads")\
            .select("*")\
            .eq("status", "closed")\
            .gte("created_at", start_date.isoformat())\
            .lte("created_at", end_date.isoformat())\
            .execute()
        
        closed_leads = result.data or []
        
        if not closed_leads:
            return {
                "total_closed_deals": 0,
                "total_revenue": 0,
                "attribution_by_agent": {},
                "avg_time_to_close_days": 0
            }
        
        # Analyze attribution
        attribution = {
            "qualifier": {"count": 0, "revenue": 0},
            "scheduler": {"count": 0, "revenue": 0},
            "followup": {"count": 0, "revenue": 0}
        }
        
        total_revenue = 0
        total_days_to_close = 0
        
        for lead in closed_leads:
            budget = lead.get("budget", 0)
            total_revenue += budget
            
            # Calculate time to close
            created = datetime.fromisoformat(lead["created_at"])
            closed_at = datetime.fromisoformat(lead.get("closed_at", lead["updated_at"]))
            days_to_close = (closed_at - created).days
            total_days_to_close += days_to_close
            
            # Analyze history to determine primary agent
            history = lead.get("history", [])
            agent_interactions = {}
            
            for entry in history:
                agent = entry.get("agent", "unknown")
                agent_interactions[agent] = agent_interactions.get(agent, 0) + 1
            
            # Attribute to agent with most interactions
            if agent_interactions:
                primary_agent = max(agent_interactions, key=agent_interactions.get)
                if primary_agent in attribution:
                    attribution[primary_agent]["count"] += 1
                    attribution[primary_agent]["revenue"] += budget
        
        return {
            "total_closed_deals": len(closed_leads),
            "total_revenue": total_revenue,
            "attribution_by_agent": attribution,
            "avg_time_to_close_days": total_days_to_close / len(closed_leads) if closed_leads else 0,
            "avg_deal_size": total_revenue / len(closed_leads) if closed_leads else 0
        }
    
    def get_agent_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for each agent.
        
        Returns:
            {
                "qualifier": {
                    "total_leads_processed": 100,
                    "avg_qualification_score": 0.75,
                    "conversion_to_scheduled": 0.40
                },
                ...
            }
        """
        # Get all leads
        result = supabase.table("leads").select("*").execute()
        leads = result.data or []
        
        metrics = {
            "qualifier": {
                "total_leads_processed": 0,
                "avg_qualification_score": 0,
                "conversion_to_scheduled": 0
            },
            "scheduler": {
                "total_tours_scheduled": 0,
                "no_show_rate": 0,
                "conversion_to_closed": 0
            },
            "followup": {
                "total_nurture_sent": 0,
                "re_engagement_rate": 0
            }
        }
        
        # Analyze qualifier performance
        qualified_leads = [l for l in leads if l.get("qualified_score")]
        if qualified_leads:
            metrics["qualifier"]["total_leads_processed"] = len(qualified_leads)
            metrics["qualifier"]["avg_qualification_score"] = sum(
                l["qualified_score"] for l in qualified_leads
            ) / len(qualified_leads)
            
            scheduled = [l for l in qualified_leads if l.get("status") == "scheduled"]
            metrics["qualifier"]["conversion_to_scheduled"] = len(scheduled) / len(qualified_leads)
        
        # Analyze scheduler performance
        scheduled_leads = [l for l in leads if l.get("status") in ["scheduled", "toured", "closed"]]
        if scheduled_leads:
            metrics["scheduler"]["total_tours_scheduled"] = len(scheduled_leads)
            
            # No-show rate (simplified - would need tour attendance data)
            toured = [l for l in scheduled_leads if l.get("status") in ["toured", "closed"]]
            metrics["scheduler"]["no_show_rate"] = 1 - (len(toured) / len(scheduled_leads))
            
            closed = [l for l in toured if l.get("status") == "closed"]
            metrics["scheduler"]["conversion_to_closed"] = len(closed) / len(toured) if toured else 0
        
        return metrics
    
    def get_channel_performance(self) -> Dict[str, Any]:
        """
        Analyze performance by channel (Instagram, WhatsApp, Web).
        """
        result = supabase.table("leads").select("channel, status, budget").execute()
        leads = result.data or []
        
        channel_stats = {}
        
        for lead in leads:
            channel = lead.get("channel", "unknown")
            
            if channel not in channel_stats:
                channel_stats[channel] = {
                    "total_leads": 0,
                    "qualified": 0,
                    "scheduled": 0,
                    "closed": 0,
                    "total_revenue": 0
                }
            
            channel_stats[channel]["total_leads"] += 1
            
            status = lead.get("status")
            if status in ["qualified", "scheduled", "toured", "closed"]:
                channel_stats[channel]["qualified"] += 1
            if status in ["scheduled", "toured", "closed"]:
                channel_stats[channel]["scheduled"] += 1
            if status == "closed":
                channel_stats[channel]["closed"] += 1
                channel_stats[channel]["total_revenue"] += lead.get("budget", 0)
        
        # Calculate conversion rates
        for channel, stats in channel_stats.items():
            total = stats["total_leads"]
            if total > 0:
                stats["qualification_rate"] = stats["qualified"] / total
                stats["scheduling_rate"] = stats["scheduled"] / total
                stats["close_rate"] = stats["closed"] / total
        
        return channel_stats

# Global analytics instance
_analytics = None

def get_analytics() -> RevenueAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = RevenueAnalytics()
    return _analytics
```

**API Endpoint:**
```python
# backend/api/analytics.py

from fastapi import APIRouter
from datetime import datetime, timedelta
from utils.analytics import get_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/attribution")
async def get_attribution(days_back: int = 30):
    """Get lead-to-close attribution for last N days."""
    analytics = get_analytics()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    return analytics.get_lead_to_close_attribution(start_date, end_date)

@router.get("/agent-performance")
async def get_agent_performance():
    """Get performance metrics for all agents."""
    analytics = get_analytics()
    return analytics.get_agent_performance_metrics()

@router.get("/channel-performance")
async def get_channel_performance():
    """Get performance by channel (IG, WhatsApp, Web)."""
    analytics = get_analytics()
    return analytics.get_channel_performance()
```

---

### 6.3 HITL Console UI (P0)

**Current State:** No UI for human review  
**Gap:** Cannot review/approve high-value leads

**Implementation:**
```typescript
// frontend/src/components/HITLConsole.tsx

import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';

interface PendingLead {
  id: string;
  user_id: string;
  name: string;
  budget: number;
  location: string;
  qualified_score: number;
  message: string;
  created_at: string;
  properties_matched: number;
}

export function HITLConsole() {
  const [pendingLeads, setPendingLeads] = useState<PendingLead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPendingLeads();
    
    // Real-time subscription
    const subscription = supabase
      .channel('hitl_leads')
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'leads',
        filter: 'status=eq.hitl_pending'
      }, (payload) => {
        setPendingLeads(prev => [payload.new as PendingLead, ...prev]);
      })
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const fetchPendingLeads = async () => {
    const { data, error } = await supabase
      .from('leads')
      .select('*')
      .eq('status', 'hitl_pending')
      .order('created_at', { ascending: false });

    if (!error && data) {
      setPendingLeads(data);
    }
    setLoading(false);
  };

  const handleApprove = async (leadId: string) => {
    // Update lead status
    await supabase
      .from('leads')
      .update({ 
        status: 'approved',
        reviewed_by: 'admin',
        reviewed_at: new Date().toISOString()
      })
      .eq('id', leadId);

    // Trigger scheduler agent
    await fetch('/api/processing/resume-workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        lead_id: leadId,
        action: 'approve',
        next_agent: 'scheduler'
      })
    });

    // Remove from pending list
    setPendingLeads(prev => prev.filter(l => l.id !== leadId));
  };

  const handleReject = async (leadId: string, reason: string) => {
    await supabase
      .from('leads')
      .update({ 
        status: 'rejected',
        rejection_reason: reason,
        reviewed_by: 'admin',
        reviewed_at: new Date().toISOString()
      })
      .eq('id', leadId);

    setPendingLeads(prev => prev.filter(l => l.id !== leadId));
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="hitl-console">
      <h2>🚨 High-Value Leads Pending Review</h2>
      
      {pendingLeads.length === 0 ? (
        <p>No leads pending review</p>
      ) : (
        <div className="leads-grid">
          {pendingLeads.map(lead => (
            <div key={lead.id} className="lead-card">
              <div className="lead-header">
                <h3>{lead.name || lead.user_id}</h3>
                <span className="score-badge">
                  Score: {(lead.qualified_score * 100).toFixed(0)}%
                </span>
              </div>

              <div className="lead-details">
                <p><strong>Budget:</strong> ${lead.budget?.toLocaleString()}</p>
                <p><strong>Location:</strong> {lead.location}</p>
                <p><strong>Properties Matched:</strong> {lead.properties_matched}</p>
                <p><strong>Message:</strong> {lead.message}</p>
                <p><strong>Received:</strong> {new Date(lead.created_at).toLocaleString()}</p>
              </div>

              <div className="actions">
                <button 
                  className="btn-approve"
                  onClick={() => handleApprove(lead.id)}
                >
                  ✅ Approve & Schedule
                </button>
                <button 
                  className="btn-reject"
                  onClick={() => {
                    const reason = prompt('Rejection reason:');
                    if (reason) handleReject(lead.id, reason);
                  }}
                >
                  ❌ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## SECTION 7: TESTING STRATEGY

### 7.1 Unit Tests (Target: 80% Coverage)

**Priority Tests:**
```python
# backend/tests/test_temporal_graph.py
- test_episode_storage()
- test_temporal_queries()
- test_preference_change_detection()
- test_engagement_trajectory()

# backend/tests/test_calendar_integration.py
- test_get_available_slots()
- test_book_calendar_event()
- test_cancel_event()
- test_duplicate_booking_prevention()

# backend/tests/test_hubspot_integration.py
- test_create_contact()
- test_create_deal()
- test_find_contact_by_email()
- test_add_note()

# backend/tests/test_multi_property_tour.py
- test_route_optimization()
- test_travel_time_calculation()
- test_tour_schedule_generation()

# backend/tests/test_audit_trail.py
- test_immutable_logging()
- test_hash_chaining()
- test_chain_integrity_verification()
- test_prevent_updates_deletes()

# backend/tests/test_compliance.py
- test_fair_housing_pattern_detection()
- test_llm_compliance_check()
- test_neutral_replacement_generation()
- test_gdpr_data_minimization()
```

---

### 7.2 Integration Tests

**End-to-End Workflow Tests:**
```python
# backend/tests/test_e2e_workflow.py

async def test_complete_lead_to_booking_flow():
    """Test entire workflow from IG message to calendar booking."""
    
    # 1. Simulate Instagram webhook
    webhook_payload = {
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "test_user_123"},
                "message": {"text": "Looking for 3BHK in Miami, budget $500k, need ASAP"}
            }]
        }]
    }
    
    response = await client.post("/webhook", json=webhook_payload)
    assert response.status_code == 200
    
    # 2. Verify lead created
    lead = await get_lead_by_user_id("test_user_123")
    assert lead is not None
    assert lead["budget"] == 500000
    assert lead["location"] == "Miami"
    
    # 3. Verify qualification
    assert lead["qualified_score"] > 0.7
    assert lead["status"] == "qualified"
    
    # 4. Verify temporal graph entry
    graphiti = get_graphiti_client()
    history = await graphiti.get_lead_history("test_user_123")
    assert len(history) > 0
    
    # 5. Verify HubSpot contact created
    assert lead["hubspot_contact_id"] is not None
    
    # 6. Simulate slot selection
    await handle_slot_selection("test_user_123", "1")
    
    # 7. Verify calendar event created
    lead = await get_lead_by_user_id("test_user_123")
    assert lead["calendar_event_id"] is not None
    assert lead["status"] == "scheduled"
    
    # 8. Verify audit trail
    audit_logs = await get_audit_logs_for_lead("test_user_123")
    assert len(audit_logs) >= 5  # Multiple agent actions logged
    
    # 9. Verify chain integrity
    integrity = await verify_audit_chain()
    assert integrity["valid"] == True
```

---

### 7.3 Performance Tests

**Load Testing:**
```python
# backend/tests/test_performance.py

async def test_concurrent_lead_processing():
    """Test system handles 100 concurrent leads."""
    
    import asyncio
    
    async def process_lead(i):
        return await process_lead_message(
            f"test_user_{i}",
            f"Looking for property in Miami, budget ${300000 + i*1000}",
            "ig"
        )
    
    # Process 100 leads concurrently
    results = await asyncio.gather(*[
        process_lead(i) for i in range(100)
    ])
    
    # Verify all processed successfully
    successful = [r for r in results if r.get("status") == "success"]
    assert len(successful) >= 95  # 95% success rate

async def test_temporal_query_performance():
    """Ensure temporal queries complete in <500ms."""
    
    import time
    
    graphiti = get_graphiti_client()
    
    start = time.time()
    history = await graphiti.get_lead_history("test_user", days_back=90)
    duration = time.time() - start
    
    assert duration < 0.5  # 500ms max
```

---

## SECTION 8: DEPLOYMENT CHECKLIST

### 8.1 Pre-Deployment Validation

- [ ] All P0 tasks completed
- [ ] Unit tests passing (>80% coverage)
- [ ] Integration tests passing
- [ ] Performance tests passing
- [ ] Security audit completed
- [ ] Compliance review completed

### 8.2 Infrastructure Setup

**Neo4j Aura:**
- [ ] Database created
- [ ] Connection tested
- [ ] Indices built

**Google APIs:**
- [ ] Calendar API enabled
- [ ] Maps API enabled
- [ ] Service account created
- [ ] Calendar shared with service account

**HubSpot:**
- [ ] Account created
- [ ] Private app configured
- [ ] API key generated
- [ ] Custom properties created

**Celery/Redis:**
- [ ] Redis instance provisioned
- [ ] Celery worker configured
- [ ] Celery beat scheduler configured
- [ ] Monitoring setup

### 8.3 Environment Variables

```bash
# Production .env checklist
✅ SUPABASE_URL
✅ SUPABASE_KEY
✅ OPENROUTER_API_KEY
✅ INSTAGRAM_PAGE_ACCESS_TOKEN
✅ INSTAGRAM_ACCOUNT_ID
✅ NEO4J_URI
✅ NEO4J_USERNAME
✅ NEO4J_PASSWORD
✅ GOOGLE_CALENDAR_CREDENTIALS_JSON
✅ GOOGLE_CALENDAR_ID
✅ GOOGLE_MAPS_API_KEY
✅ HUBSPOT_API_KEY
✅ REDIS_URL
✅ SENTRY_DSN (error tracking)
✅ LANGFUSE_PUBLIC_KEY (LLM observability)
✅ LANGFUSE_SECRET_KEY
```

### 8.4 Monitoring & Observability

**Setup:**
- [ ] Sentry error tracking configured
- [ ] Langfuse LLM tracing enabled
- [ ] Uptime monitoring (UptimeRobot)
- [ ] Log aggregation (Papertrail/Logtail)
- [ ] Performance monitoring (New Relic/DataDog)

**Alerts:**
- [ ] Error rate > 5%
- [ ] Response time > 3s
- [ ] Audit chain integrity broken
- [ ] Compliance violation detected
- [ ] HITL queue > 10 pending

---

## SECTION 9: ESTIMATED TIMELINE

### Sprint 1 (Week 1-2): Critical Infrastructure
- Task 1.1-1.4: Neo4j Graphiti (16 hours)
- Task 2.1-2.4: Google Calendar (13 hours)
- Task 5.1-5.3: Audit Trail (6 hours)
- **Total: 35 hours**

### Sprint 2 (Week 3-4): Core Integrations
- Task 3.1-3.3: HubSpot CRM (8 hours)
- Task 4.1-4.3: Multi-Property Tours (8 hours)
- Task 6.1: Nurture Automation (6 hours)
- Task 6.3: HITL Console (4 hours)
- **Total: 26 hours**

### Sprint 3 (Week 5-6): Analytics & Testing
- Task 6.2: Revenue Analytics (6 hours)
- Unit tests (16 hours)
- Integration tests (12 hours)
- Performance tests (4 hours)
- **Total: 38 hours**

### Sprint 4 (Week 7-8): Deployment & Polish
- Documentation (8 hours)
- Security audit (4 hours)
- Deployment setup (8 hours)
- Monitoring configuration (4 hours)
- Bug fixes & polish (16 hours)
- **Total: 40 hours**

**Grand Total: ~140 hours (7-8 weeks for 1 developer)**

---

## SECTION 10: SUCCESS METRICS

### Technical Metrics
- [ ] 100% PRD feature coverage
- [ ] >80% test coverage
- [ ] <3s average response time
- [ ] 99.5% uptime
- [ ] 0 compliance violations

### Business Metrics
- [ ] 50% reduction in lead-to-meeting time
- [ ] 30% lift in booking rate
- [ ] 95% qualification accuracy
- [ ] 100% audit trail coverage
- [ ] <5% no-show rate

### User Experience Metrics
- [ ] <5min Instagram response time
- [ ] 3-click booking flow
- [ ] Real-time HITL notifications
- [ ] Automated nurture engagement

---

## APPENDIX: QUICK REFERENCE

### Key Files to Modify
```
backend/temporal/graph_client.py          # Neo4j integration
backend/tools/calendar_integration.py     # Google Calendar
backend/utils/hubspot_client.py           # HubSpot CRM
backend/utils/maps_client.py              # Google Maps
backend/utils/audit.py                    # Audit logging
backend/tasks/nurture_automation.py       # Celery tasks
backend/utils/analytics.py                # Revenue intelligence
frontend/src/components/HITLConsole.tsx   # HITL UI
```

### Testing Commands
```bash
# Run all tests
pytest backend/tests/ -v --cov=backend --cov-report=html

# Run specific test suite
pytest backend/tests/test_temporal_graph.py -v

# Run integration tests only
pytest backend/tests/test_e2e_workflow.py -v

# Check test coverage
open backend/htmlcov/index.html
```

### Deployment Commands
```bash
# Start all services
docker-compose up -d

# Start Celery worker
celery -A backend.tasks.nurture_automation worker -l info

# Start Celery beat
celery -A backend.tasks.nurture_automation beat -l info

# Run migrations
python backend/scripts/apply_migrations.py

# Verify audit chain
python -c "from backend.utils.audit import get_audit_logger; print(get_audit_logger().verify_chain_integrity())"
```

---

## CONCLUSION

This checklist provides a complete roadmap to achieve 100% PRD alignment. Focus on P0 tasks first (Sections 1, 2, 5) to establish critical infrastructure, then move to P1 features (Sections 3, 4, 6) for core functionality.

**Next Steps:**
1. Review and prioritize tasks with team
2. Set up development environment
3. Begin Sprint 1 (Neo4j + Calendar + Audit)
4. Track progress using this checklist
5. Update README.md as features are completed

**Questions or Issues?**
- Refer to PRD for detailed requirements
- Check existing code for implementation patterns
- Use MCP tools to search documentation
- Test incrementally to catch issues early

Good luck! 🚀
