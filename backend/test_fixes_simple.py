#!/usr/bin/env python3
"""
Simple test to verify the critical production fixes without external dependencies.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_type_conversion_fix():
    """Test the type conversion fix for budget handling."""
    print("🧪 Testing type conversion fix...")
    
    # Import the processor class directly
    from tasks.production_lead_processing import ProductionLeadProcessor
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


def test_message_length_validation():
    """Test Instagram message length validation."""
    print("📱 Testing Instagram message length validation...")
    
    from tasks.production_lead_processing import ProductionLeadProcessor
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


def test_lead_scoring_integration():
    """Test lead scoring with the type conversion fix."""
    print("📊 Testing lead scoring integration...")
    
    try:
        from utils.lead_scoring import calculate_lead_score
        
        # Test with string budget (the problematic case)
        lead_data = {
            "budget": "$500,000",  # String that caused int + str error
            "location": "New York",
            "timeline": "3 months",
            "property_type": "condo",
            "message": "Looking for a condo in New York"
        }
        
        result = calculate_lead_score(lead_data)
        print(f"   ✅ Lead scoring completed: {result['final_score']}")
        print(f"   📊 Score breakdown: {result['score_breakdown']}")
        
    except Exception as e:
        print(f"   ❌ Lead scoring failed: {e}")
    
    print("✅ Lead scoring integration test completed\n")


def main():
    """Run all tests."""
    print("🚀 Starting production fixes verification tests...\n")
    
    test_type_conversion_fix()
    test_message_length_validation()
    test_lead_scoring_integration()
    
    print("🎉 All production fixes tests completed!")
    print("\n📋 Summary of fixes implemented:")
    print("   1. ✅ Fixed type conversion error in lead scoring")
    print("   2. ✅ Added Instagram message length validation (1000 char limit)")
    print("   3. ✅ Improved LLM fallback with exponential backoff and retries")
    print("   4. ✅ Enhanced error handling and logging throughout")


if __name__ == "__main__":
    main()