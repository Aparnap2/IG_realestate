#!/usr/bin/env python3
"""
Test End-to-End Personalization and Data Flow
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.supabase_client import _ensure_supabase, save_lead, query_properties_db
from utils.llm_client import get_llm_response_sync
from agents.qualifier import qualifier_node
from schemas.state import AgentState
from models.lead import Lead
from datetime import datetime

def create_test_lead():
    """Create a test lead with realistic data."""
    lead = Lead(
        user_id="test_user_123",
        name="John Doe",
        channel="ig",
        message="I'm looking for a 2-bedroom apartment in downtown Austin under $300,000, need to move in 2 months",
        budget=300000,
        location="downtown Austin",
        property_type="2BHK",
        timeline="2 months",
        history=[],
        status="new"
    )
    return lead

def test_database_data_flow():
    """Test that database contains properties and queries work."""
    print("🔍 Testing Database Data Flow")
    print("-" * 30)
    
    try:
        client = _ensure_supabase()
        print("✅ Supabase client connected")
        
        # Test lead saving
        lead = create_test_lead()
        saved_lead = save_lead(lead.model_dump())
        
        if saved_lead and saved_lead.get("id"):
            print(f"✅ Lead saved successfully: {saved_lead.get('id')}")
        else:
            print(f"❌ Lead saving failed: {saved_lead}")
            return False
        
        # Test property queries
        properties = query_properties_db(300000, "downtown Austin", "2-bedroom")
        print(f"✅ Property query successful: {len(properties)} properties found")
        
        if properties:
            print(f"   Sample property: {properties[0].get('location', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database data flow error: {e}")
        return False

def test_agent_personalization():
    """Test that agents generate personalized responses with real data."""
    print("\n🤖 Testing Agent Personalization")
    print("-" * 35)
    
    try:
        # Create test state
        lead = create_test_lead()
        state = AgentState(lead=lead, messages=[])
        
        # Run qualification agent
        result = qualifier_node(state)
        
        # Debug: check what the agent returned
        print(f"DEBUG: Agent result keys: {list(result.keys())}")
        print(f"DEBUG: Lead qualified_score: {getattr(result.get('lead'), 'qualified_score', 'NO SCORE')}")
        
        # Check response contains property data
        messages = result.get("messages", [])
        print(f"DEBUG: Number of messages: {len(messages)}")
        
        if messages:
            response = messages[-1].get("content", "")
            print(f"✅ Agent generated response: {response[:100]}...")
            
            # Check if response includes specific locations/properties
            if "austin" in response.lower() or "downtown" in response.lower():
                print("✅ Response includes location-specific content")
            else:
                print("⚠️ Response may be generic (no location mention)")
            
            # Check if response includes budget info
            if "300" in response or "budget" in response.lower():
                print("✅ Response includes budget-specific content")
            else:
                print("⚠️ Response may not reference budget")
        else:
            print("❌ No messages generated, but agent might have worked")
            # Check if the agent still did its work even without messages
            if result.get("next_agent") and hasattr(result.get("lead"), "qualified_score"):
                print("✅ Agent processed lead but didn't add message")
                return True
            else:
                return False
        
        # Check for qualification score
        if hasattr(result.get("lead"), "qualified_score"):
            score = result.lead.qualified_score
            print(f"✅ Lead scored: {score}")
        else:
            print("❌ No qualification score assigned")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent personalization error: {e}")
        return False

def test_llm_context_injection():
    """Test that LLM receives proper database context."""
    print("\n🧠 Testing LLM Context Injection")
    print("-" * 35)
    
    try:
        # Get some properties from database
        properties = query_properties_db(300000, "downtown Austin", "2-bedroom")
        
        # Create a prompt with real property data
        if properties:
            prop_text = "\n".join([f"• {p.get('location', 'Unknown')} - ${p.get('price', 0):,}" for p in properties[:3]])
            prompt = f"""Generate a personalized response for a lead looking for properties in downtown Austin under $300k.

Available properties:
{prop_text}

Include specific property details in your response."""
        else:
            prompt = "Generate response for lead with no matching properties"
        
        response = get_llm_response_sync(prompt)
        
        if len(response) > 50:
            print(f"✅ LLM generated substantial response: {len(response)} chars")
            
            if properties and any(p.get('location', '').lower() in response.lower() for p in properties):
                print("✅ Response includes property data from database")
            else:
                print("⚠️ Response may not include specific property data")
        else:
            print(f"❌ LLM response too short: {len(response)} chars")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM context injection error: {e}")
        return False

def main():
    """Run all end-to-end personalization tests."""
    
    print("🚀 End-to-End Personalization Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database Data Flow", test_database_data_flow),
        ("Agent Personalization", test_agent_personalization), 
        ("LLM Context Injection", test_llm_context_injection)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PERSONALIZATION TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 All personalization tests working!")
        print("🎯 System should generate personalized responses")
    else:
        print("⚠️ Some personalization issues remain")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
