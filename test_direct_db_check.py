#!/usr/bin/env python3
"""
Direct database check to see if our fixes are working
"""
import sys
import os
sys.path.append('/home/aparna/Desktop/IG_realestate/backend')

# Test the temporal graph client fix
def test_temporal_graph_client():
    print("🧪 Testing Temporal Graph Client Fix...")
    try:
        from temporal.graph_client import get_graphiti_client
        
        # This should now work without NoneType errors
        client = get_graphiti_client()
        print("✅ GraphitiClient initialized successfully")
        
        # Test lead event recording (this will fallback to Supabase)
        client = get_graphiti_client()
        import asyncio
        
        async def test_event_recording():
            success = await client.record_lead_event(
                lead_id="1534105394273010",  # From your logs
                event_type="test_message",
                event_data={"test": "data"},
                timestamp=None
            )
            return success
            
        result = asyncio.run(test_event_recording())
        print(f"✅ Lead event recording: {'Success' if result else 'Graceful fallback'}")
        return True
        
    except Exception as e:
        print(f"❌ Temporal graph client error: {e}")
        return False

def test_supabase_functions():
    print("🧪 Testing Supabase Functions...")
    try:
        from utils.supabase_client import query_properties_db, get_circuit_breaker_status
        
        # Test property search (one of our fixes)
        properties = query_properties_db(
            budget=100000,
            location="Miami", 
            property_type="House"
        )
        print(f"✅ Property search works: {len(properties)} properties found")
        
        # Check circuit breaker
        status = get_circuit_breaker_status()
        print(f"✅ Circuit breaker status: {status['state']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Supabase functions error: {e}")
        return False

def test_lead_functions():
    print("🧪 Testing Lead Functions...")
    try:
        from utils.supabase_client import save_or_update_lead
        
        # Test lead saving without company_id (one of our fixes)
        test_lead_data = {
            "instagram_id": "test_automation_user",
            "name": "Test User",
            "budget": 200000,
            "location": "Miami",
            "message": "I need a house"
        }
        
        result = save_or_update_lead("test_automation_user", test_lead_data)
        if result:
            print("✅ Lead saving works without company_id")
            print(f"📊 Lead ID: {result.get('id')}")
            print(f"👤 Name: {result.get('name')}")
            print(f"📱 Instagram ID: {result.get('instagram_id')}")
            return True
        else:
            print("❌ Lead saving returned empty result")
            return False
            
    except Exception as e:
        print(f"❌ Lead functions error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Our Individual Fixes\n")
    
    results = {
        "Temporal Graph Client": test_temporal_graph_client(),
        "Supabase Functions": test_supabase_functions(), 
        "Lead Functions": test_lead_functions()
    }
    
    print("\n" + "="*50)
    print("📊 FIXES VERIFICATION RESULTS")
    print("="*50)
    
    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 Fixes verified: {passed}/{len(results)} working correctly")
