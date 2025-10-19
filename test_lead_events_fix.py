#!/usr/bin/env python3
"""
Test script to verify the lead_events table UUID mapping fix.
This tests the temporal graph client's ability to properly map lead IDs to UUIDs.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from temporal.graph_client import get_graphiti_client
from utils.supabase_client import supabase

async def test_lead_events_insertion():
    """Test that lead_events can be inserted with proper UUID mapping."""
    
    print("🧪 Testing lead_events UUID mapping fix...")
    
    # 1. Create a test lead if it doesn't exist
    test_instagram_id = "test_user_12345"
    
    # Check if lead exists
    existing_lead = supabase.table("leads").select("*").eq("instagram_id", test_instagram_id).execute()
    
    if not existing_lead.data:
        print("📝 Creating test lead...")
        lead_data = {
            "instagram_id": test_instagram_id,
            "instagram_username": "test_user",
            "name": "Test User",
            "phone": "+1234567890",
            "email": "test@example.com",
            "budget": 500000,
            "location": "Miami Beach",
            "timeline": "1-3months"
        }
        
        lead_result = supabase.table("leads").insert(lead_data).execute()
        lead_uuid = lead_result.data[0]["id"]
        print(f"✅ Created test lead with UUID: {lead_uuid}")
    else:
        lead_uuid = existing_lead.data[0]["id"]
        print(f"✅ Using existing test lead with UUID: {lead_uuid}")
    
    # 2. Test the temporal graph client
    graph_client = get_graphiti_client()
    
    # 3. Record a lead event using the temporal graph client
    print("📊 Recording lead event...")
    success = await graph_client.record_lead_event(
        lead_id=test_instagram_id,  # Using instagram_id (should be mapped to UUID)
        event_type="qualified",
        event_data={
            "score": 0.8,
            "budget": 500000,
            "location": "Miami Beach",
            "reason": "High budget, clear location preference"
        },
        timestamp=datetime.now(timezone.utc)
    )
    
    if success:
        print("✅ Successfully recorded lead event")
    else:
        print("❌ Failed to record lead event")
        return False
    
    # 4. Verify the event was stored in lead_events table
    print("🔍 Verifying event in lead_events table...")
    events = supabase.table("lead_events").select("*").eq("lead_id", lead_uuid).execute()
    
    if events.data:
        print(f"✅ Found {len(events.data)} events for lead")
        for event in events.data:
            print(f"   - Event ID: {event['id']}")
            print(f"   - Type: {event['event_type']}")
            print(f"   - Created: {event['created_at']}")
    else:
        print("❌ No events found in lead_events table")
        return False
    
    # 5. Test retrieving lead history
    print("📚 Testing lead history retrieval...")
    history = await graph_client.get_lead_history(
        lead_id=test_instagram_id,  # Using instagram_id (should be mapped to UUID)
        days_back=7
    )
    
    if history:
        print(f"✅ Retrieved {len(history)} events from history")
        for event in history:
            print(f"   - {event.get('event_type', 'unknown')}: {event.get('timestamp', 'no timestamp')}")
    else:
        print("⚠️ No history retrieved (might be expected if Graphiti is not enabled)")
    
    # 6. Clean up test data
    print("🧹 Cleaning up test data...")
    supabase.table("lead_events").delete().eq("lead_id", lead_uuid).execute()
    supabase.table("leads").delete().eq("id", lead_uuid).execute()
    print("✅ Test data cleaned up")
    
    print("\n🎉 All tests passed! The UUID mapping fix is working correctly.")
    return True

if __name__ == "__main__":
    asyncio.run(test_lead_events_insertion())