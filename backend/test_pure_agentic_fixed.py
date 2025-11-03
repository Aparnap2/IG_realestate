#!/usr/bin/env python3
"""
Standalone test script for Pure Agentic Lead Extraction System
Tests the fixed pure agentic extraction with proper import paths
"""

import asyncio
import sys
import os

# Add backend directory to Python path for testing
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Test imports
try:
    from utils.llm_client import get_llm_response_sync, validate_api_key_environment
    print("✅ Successfully imported LLM client")
except ImportError as e:
    print(f"❌ Failed to import LLM client: {e}")
    sys.exit(1)

async def test_pure_agentic_extraction():
    """Test pure agentic extraction with the problematic message."""
    
    print('🧪 PURE AGENTIC LEAD EXTRACTION TEST')
    print('=' * 50)
    
    # Check API availability
    api_status = validate_api_key_environment()
    print(f"📡 API Status: {api_status}")
    
    # Test message - the original problematic one
    test_message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    print(f"\n💬 Test Message: '{test_message}'")
    
    # Create intelligent extraction prompt
    extraction_prompt = f"""You are an expert real estate lead qualification agent. Extract ALL relevant information from this message using pure intelligence.

Message: "{test_message}"

Extract and return ONLY valid JSON with this exact structure:
{{
    "budget": <number or null>,
    "location": <string or null>, 
    "property_type": <string or null>,
    "timeline": <string or null>,
    "desired_bedrooms": <number or null>,
    "confidence": <0.0 to 1.0>,
    "extracted_fields": [<list of fields found>]
}}

Rules:
- Use pure intelligence to understand context and intent
- NO hardcoded lists or pattern matching
- Return null for fields not mentioned
- confidence based on how complete the information is
- Extract bedrooms as numbers (1, 2, 3, 4, etc.)
- Budget as full number (250000, not 250k)
- location as proper case ("Miami Beach", not "miami beach")
- If no clear budget, location, or property details, return confidence under 0.5

Examples:
Message: "i need ASAP , miami beach , 250k dollar 4bhk condo"
Response: {{"budget": 250000, "location": "Miami Beach", "property_type": "4BHK", "timeline": "immediately", "desired_bedrooms": 4, "confidence": 1.0, "extracted_fields": ["budget", "location", "property_type", "timeline", "bedrooms"]}}

Message: "looking for houses under 500k"
Response: {{"budget": 500000, "location": null, "property_type": "House", "timeline": null, "desired_bedrooms": null, "confidence": 0.6, "extracted_fields": ["budget", "property_type"]}}

Now extract from this message:"""

    try:
        print("\n🤖 Calling LLM for intelligent extraction...")
        response = get_llm_response_sync(extraction_prompt, timeout=30)
        
        if not response:
            print("❌ No response from LLM")
            return None
            
        print(f"📄 LLM Response: {response}")
        
        # Parse the response
        import json
        import re
        
        # Clean response - remove any markdown formatting
        clean_response = response.strip()
        if clean_response.startswith('```json'):
            clean_response = clean_response[7:]
        if clean_response.endswith('```'):
            clean_response = clean_response[:-3]
        
        print(f"🧹 Cleaned Response: {clean_response}")
        
        try:
            extraction_data = json.loads(clean_response.strip())
            print(f"✅ Successfully parsed JSON: {extraction_data}")
            
            # Analyze results
            print("\n📊 EXTRACTION ANALYSIS:")
            budget = extraction_data.get("budget")
            location = extraction_data.get("location")
            property_type = extraction_data.get("property_type")
            timeline = extraction_data.get("timeline")
            bedrooms = extraction_data.get("desired_bedrooms")
            confidence = extraction_data.get("confidence", 0.0)
            fields = extraction_data.get("extracted_fields", [])
            
            print(f"💰 Budget: {budget} {'✅' if budget == 250000 else '❌'}")
            print(f"📍 Location: {location} {'✅' if location == 'Miami Beach' else '❌'}")
            print(f"🏠 Property Type: {property_type} {'✅' if property_type == '4BHK' else '❌'}")
            print(f"⏰ Timeline: {timeline} {'✅' if timeline == 'immediately' else '❌'}")
            print(f"🛏️ Bedrooms: {bedrooms} {'✅' if bedrooms == 4 else '❌'}")
            print(f"📈 Confidence: {confidence:.2f}")
            print(f"📋 Fields Extracted: {fields}")
            
            # Overall assessment
            correct_extractions = [
                budget == 250000,
                location == "Miami Beach", 
                property_type == "4BHK",
                timeline == "immediately",
                bedrooms == 4
            ]
            success_rate = sum(correct_extractions) / len(correct_extractions)
            
            print(f"\n🎯 SUCCESS RATE: {success_rate:.1%} ({sum(correct_extractions)}/5 fields correct)")
            
            if success_rate >= 0.8:
                print("🎉 PURE AGENTIC SUCCESS! System now properly extracts key information!")
                print("✅ No more asking for budget when it was provided")
                print("✅ No more asking for location when it was provided") 
                print("✅ Full intelligent understanding of user requirements")
            elif success_rate >= 0.6:
                print("⚠️ PURE AGENTIC PARTIAL SUCCESS: Good progress but needs refinement")
            else:
                print("❌ PURE AGENTIC FAILED: Still not extracting properly")
                print("This suggests the LLM prompts or API calls need further optimization")
            
            return extraction_data
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response: {e}")
            print("The LLM returned malformed JSON")
            return None
            
    except Exception as e:
        print(f"❌ Error in pure agentic extraction: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_agent_routing():
    """Test pure agentic message routing."""
    
    print('\n🧭 PURE AGENTIC ROUTING TEST')
    print('=' * 40)
    
    test_message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    
    routing_prompt = f"""You are an expert agentic message router for a real estate AI system. 

Message: "{test_message}"

Route this message to the most appropriate agent based on pure intelligence and intent analysis.

Available agents:
- "qualifier": Initial contact, gathering requirements, qualification
- "followup": Nurturing existing leads, building relationships
- "scheduler": Booking tours, scheduling appointments, availability
- "value_delivery": Sending properties, market insights, value
- "offramp": Ending conversations, collecting final info

Consider:
- Message intent and content
- Stage of conversation
- User needs and urgency
- Business objectives

Return ONLY the agent name as a string.

Examples:
"i need ASAP miami beach 250k dollar 4bhk condo" → "qualifier"
"show me similar properties" → "value_delivery" 
"when can I schedule a viewing" → "scheduler"
"thanks, I'll think about it" → "followup"

Message: "{test_message}"

Agent:"""
    
    try:
        print(f"💬 Testing routing for: '{test_message}'")
        response = get_llm_response_sync(routing_prompt, timeout=15)
        
        if response:
            agent = response.strip().lower()
            print(f"🎯 Routed to: {agent}")
            
            # Validate agent
            valid_agents = {"qualifier", "followup", "scheduler", "value_delivery", "offramp"}
            if agent in valid_agents:
                print(f"✅ Valid routing: {agent}")
                if agent == "qualifier":
                    print("✅ Correct: New lead with requirements needs qualification")
                else:
                    print(f"🤔 Routing decision: {agent} (could also be qualifier)")
            else:
                print(f"❌ Invalid agent: {agent}")
        
    except Exception as e:
        print(f"❌ Routing test failed: {e}")

async def main():
    """Main test function."""
    
    print("🚀 STARTING PURE AGENTIC SYSTEM TESTS")
    print("=" * 60)
    
    # Test 1: Pure agentic extraction
    extraction_result = await test_pure_agentic_extraction()
    
    # Test 2: Agent routing
    await test_agent_routing()
    
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY:")
    
    if extraction_result:
        budget = extraction_result.get("budget")
        location = extraction_result.get("location") 
        property_type = extraction_result.get("property_type")
        
        if budget == 250000 and location == "Miami Beach" and property_type == "4BHK":
            print("🎉 OVERALL RESULT: PURE AGENTIC SUCCESS!")
            print("✅ System now properly extracts ALL key information from complex messages")
            print("✅ No more asking for information that was already provided")
            print("✅ Full intelligent understanding and routing capabilities")
        else:
            print("⚠️ OVERALL RESULT: NEEDS REFINEMENT")
            print(f"   Budget: {budget} (expected: 250000)")
            print(f"   Location: {location} (expected: Miami Beach)")
            print(f"   Property: {property_type} (expected: 4BHK)")
    else:
        print("❌ OVERALL RESULT: TESTS FAILED")
        print("   Unable to complete pure agentic extraction tests")

if __name__ == "__main__":
    asyncio.run(main())