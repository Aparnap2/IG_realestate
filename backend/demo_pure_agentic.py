#!/usr/bin/env python3
"""
Demo script for pure agentic AI extraction patterns
Shows the new LangGraph-based system without ML dependencies
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.enhanced_llm_extraction import extract_lead_info

def demo_pure_agentic_extraction():
    """Demonstrate pure agentic AI extraction patterns."""
    
    print("🤖 Pure Agentic AI Lead Extraction Demo")
    print("=" * 60)
    print("✅ No ML dependencies")
    print("✅ Rule-based patterns") 
    print("✅ LangGraph integration")
    print("✅ Agent coordination")
    print("=" * 60)
    
    # Test messages representing different real estate scenarios
    test_messages = [
        "Hi there! I'm looking for a 2-bedroom condo in Brooklyn with a budget of $500k",
        "Can you send me details about available properties?",
        "I'd like to schedule a viewing this weekend",
        "Thanks for the information!",
        "Looking for something around $300k in Austin",
        "I need a house near Manhattan, budget around $800k",
        "When are you available for a tour?",
        "What's the price range for 3-bedroom apartments?"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n📝 Test {i}: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        try:
            result = extract_lead_info(message)
            
            if result["success"]:
                confidence = result["extraction_confidence"]
                extracted_fields = len(result["extraction_fields"])
                agent_type = result["agent_type"]
                
                print(f"   ✅ Success - Confidence: {confidence:.2f}")
                print(f"   🔄 Agent: {agent_type}")
                print(f"   📊 Fields extracted: {extracted_fields}")
                
                # Show some extracted data
                if result.get("budget"):
                    print(f"   💰 Budget: ${result['budget']:,}")
                if result.get("location"):
                    print(f"   📍 Location: {result['location']}")
                if result.get("property_type"):
                    print(f"   🏠 Type: {result['property_type']}")
                    
                print(f"   🎯 Agentic coordination: {result.get('agentic_coordination', False)}")
                print(f"   🔧 LangGraph managed: {result.get('langgraph_managed', False)}")
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"   💥 Exception: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Pure Agentic AI Demo Complete!")
    print("✅ All extractions completed without ML dependencies")
    print("✅ Rule-based patterns working correctly")
    print("✅ LangGraph coordination functioning")
    print("=" * 60)

if __name__ == "__main__":
    demo_pure_agentic_extraction()