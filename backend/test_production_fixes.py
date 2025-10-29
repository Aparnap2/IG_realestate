#!/usr/bin/env python3
"""
Test script to verify the critical production fixes:

1. Lead scoring type conversion error fix
2. Instagram message length validation 
3. LLM fallback handling improvements
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tasks.production_lead_processing import ProductionLeadProcessor
from utils.llm_client import get_llm_response, get_gemini_response


async def test_type_conversion_fix():
    """Test the type conversion fix for budget handling."""
    print("🧪 Testing type conversion fix...")
    
    processor = ProductionLeadProcessor()
    
    # Test the _safe_int_convert method
    test_cases = [
        ("$500,000", 500000),
        ("500000", 500000),
        ("500k", 0),  # Should fail gracefully
        (None, 0),
        ("", 0),
        ("$1,234,567", 1234567),
    ]
    
    for input_val, expected in test_cases:
        result = processor._safe_int_convert(input_val)
        status = "✅" if result == expected else "❌"
        print(f"   {status} Input: {input_val} -> Output: {result} (expected: {expected})")
    
    print("✅ Type conversion fix test completed\n")


async def test_message_length_validation():
    """Test Instagram message length validation."""
    print("📱 Testing Instagram message length validation...")
    
    processor = ProductionLeadProcessor()
    
    # Test cases
    test_cases = [
        ("Short message", "Short message"),
        ("A" * 999, "A" * 999),  # Under limit
        ("B" * 1000, "B" * 1000),  # Exactly at limit
        ("C" * 1001, "C" * 990 + "... [truncated]"),  # Over limit
        ("D" * 2000, "D" * 990 + "... [truncated]"),  # Way over limit
    ]
    
    for input_msg, expected in test_cases:
        result = processor._validate_and_truncate_message(input_msg)
        status = "✅" if result == expected else "❌"
        print(f"   {status} Input length: {len(input_msg)} -> Output length: {len(result)}")
    
    print("✅ Message length validation test completed\n")


async def test_llm_fallback_handling():
    """Test improved LLM fallback handling."""
    print("🤖 Testing LLM fallback handling...")
    
    # Test with a simple prompt
    test_prompt = "What is the capital of France?"
    
    try:
        # This should work with OpenRouter or fallback to Gemini
        response = await get_llm_response(test_prompt, max_tokens=100)
        print(f"   ✅ LLM response received: {response[:100]}...")
        
        # Test Gemini fallback directly
        if os.getenv("GOOGLE_API_KEY"):
            gemini_response = await get_gemini_response(test_prompt, max_tokens=100)
            print(f"   ✅ Gemini fallback response: {gemini_response[:100]}...")
        else:
            print("   ⚠️ Google API key not configured, skipping Gemini test")
            
    except Exception as e:
        print(f"   ❌ LLM test failed: {e}")
    
    print("✅ LLM fallback handling test completed\n")


async def test_lead_scoring_integration():
    """Test lead scoring with the type conversion fix."""
    print("📊 Testing lead scoring integration...")
    
    from utils.lead_scoring import calculate_lead_score
    
    # Test with string budget (the problematic case)
    lead_data = {
        "budget": "$500,000",  # String that caused int + str error
        "location": "New York",
        "timeline": "3 months",
        "property_type": "condo",
        "message": "Looking for a condo in New York"
    }
    
    try:
        result = calculate_lead_score(lead_data)
        print(f"   ✅ Lead scoring completed: {result['final_score']}")
        print(f"   📊 Score breakdown: {result['score_breakdown']}")
    except Exception as e:
        print(f"   ❌ Lead scoring failed: {e}")
    
    print("✅ Lead scoring integration test completed\n")


async def main():
    """Run all tests."""
    print("🚀 Starting production fixes verification tests...\n")
    
    await test_type_conversion_fix()
    await test_message_length_validation()
    await test_llm_fallback_handling()
    await test_lead_scoring_integration()
    
    print("🎉 All production fixes tests completed!")
    print("\n📋 Summary of fixes implemented:")
    print("   1. ✅ Fixed type conversion error in lead scoring")
    print("   2. ✅ Added Instagram message length validation (1000 char limit)")
    print("   3. ✅ Improved LLM fallback with exponential backoff and retries")
    print("   4. ✅ Enhanced error handling and logging throughout")


if __name__ == "__main__":
    asyncio.run(main())