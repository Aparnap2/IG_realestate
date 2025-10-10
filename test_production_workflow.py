#!/usr/bin/env python3
"""
Test the complete production workflow
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tasks.production_lead_processing import process_lead_message

async def test_production_workflow():
    """Test the complete production workflow"""
    
    print("🧪 Testing Production Workflow")
    print("=" * 40)
    
    # Test scenarios
    test_cases = [
        {
            "name": "High-Value Lead",
            "user_id": "luxury_buyer_001",
            "message": "Looking for luxury 3BHK penthouse in Miami Beach, budget $800k, need ASAP",
            "channel": "ig"
        },
        {
            "name": "Qualified Lead",
            "user_id": "qualified_buyer_002",
            "message": "2BHK in Miami, budget $350k, flexible timeline",
            "channel": "ig"
        },
        {
            "name": "Browsing Lead",
            "user_id": "browsing_user_003",
            "message": "Just looking at properties in the area",
            "channel": "ig"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['name']}")
        print("-" * 30)
        
        try:
            result = await process_lead_message(
                test_case["user_id"],
                test_case["message"],
                test_case["channel"]
            )
            
            if result["status"] == "success":
                print(f"✅ Lead ID: {result['lead_id']}")
                print(f"✅ Score: {result['qualified_score']}")
                print(f"✅ Next Agent: {result['next_agent']}")
                print(f"✅ Properties Found: {result['properties_found']}")
                print(f"✅ HITL Needed: {result['interrupt_needed']}")
                print(f"✅ Response: {result['response_message'][:100]}...")
            else:
                print(f"❌ Error: {result['error']}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_production_workflow())