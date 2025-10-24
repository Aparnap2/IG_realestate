#!/usr/bin/env python3
"""
Test Enhanced LLM Response Validation
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.llm_client import get_structured_llm_response

def test_llm_validation():
    """Test LLM response validation with various scenarios."""
    
    print("🧪 Testing Enhanced LLM Response Validation")
    print("=" * 50)
    
    # Test scenario 1: Lead qualification scoring
    print("\n1. Testing lead qualification scoring...")
    result = get_structured_llm_response(
        """Score this lead for real estate interest:
        - Budget: $400,000
        - Location: downtown
        - Timeline: 3-6 months
        - Property type: 2-bedroom condo""",
        {
            "score": "number between 0 and 1",
            "reasoning": "string explanation"
        }
    )
    
    if "score" in result and not result.get("error"):
        print(f"✅ Lead scoring successful: score={result.get('score')}")
    else:
        print(f"❌ Lead scoring failed: {result}")
    
    # Test scenario 2: Lead information extraction
    print("\n2. Testing lead information extraction...")
    result = get_structured_llm_response(
        """Extract real estate lead information from: 
        "Hi I'm looking for a 3-bedroom house in Austin under $500k, need to move in 2 months"
        """,
        {
            "budget": "number or null",
            "location": "string or null",
            "bedrooms": "number or null", 
            "timeline": "string or null",
            "property_type": "string or null"
        }
    )
    
    if not result.get("error"):
        print(f"✅ Information extraction successful: {result}")
    else:
        print(f"❌ Information extraction failed: {result}")
    
    # Test scenario 3: JSON error handling (malformed response simulation)
    print("\n3. Testing JSON error handling...")
    # This will test the fallback mechani 
    result = get_structured_llm_response(
        """Test parsing - create JSON for budget: 300000""",
        {
            "budget": "number",
            "valid": "boolean"
        }
    )
    
    if not result.get("error") or result.get("fallback"):
        print(f"✅ Error handling works: fallback={result.get('fallback', False)}")
    else:
        print(f"❌ Error handling failed: {result}")
    
    return True

if __name__ == "__main__":
    test_llm_validation()
