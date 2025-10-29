#!/usr/bin/env python3
"""
Comprehensive test script for production fixes.

Tests:
1. Type conversion error fixes in lead scoring
2. Robust LLM fallback system
3. Error handling and graceful degradation
4. Production system integration
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tasks.production_lead_processing import (
    ProductionLeadProcessor, 
    process_lead_message,
    fallback_extract_lead_info,
    generate_fallback_response
)
from utils.llm_client import generate_contextual_fallback
from utils.lead_scoring import calculate_lead_score


class ProductionFixesTest:
    """Test suite for production fixes"""
    
    def __init__(self):
        self.processor = ProductionLeadProcessor()
        self.test_results = []
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_safe_int_convert(self):
        """Test the _safe_int_convert method with various inputs"""
        print("\n🧪 Testing _safe_int_convert method...")
        
        test_cases = [
            ("$500,000", 500000),
            ("250000", 250000),
            ("$1.5M", 1500000),  # This might fail but should not crash
            ("invalid", 0),
            (None, 0),
            ("", 0),
            ("  $300,000  ", 300000),
        ]
        
        all_passed = True
        for input_val, expected in test_cases:
            try:
                result = self.processor._safe_int_convert(input_val)
                if result == expected:
                    self.log_test(f"Convert '{input_val}' to {expected}", True)
                else:
                    self.log_test(f"Convert '{input_val}' to {expected}", False, f"Got {result}")
                    all_passed = False
            except Exception as e:
                self.log_test(f"Convert '{input_val}' without error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    def test_fallback_lead_extraction(self):
        """Test fallback lead extraction"""
        print("\n🧪 Testing fallback lead extraction...")
        
        test_messages = [
            {
                "message": "Looking for a 2BHK apartment in New York with budget around $500,000",
                "expected": {
                    "budget": 500000,
                    "location": "New York",
                    "property_type": "2BHK"
                }
            },
            {
                "message": "I want a house with 3 bedrooms near Los Angeles, my budget is $750k",
                "expected": {
                    "budget": 750000,
                    "location": "Los Angeles", 
                    "property_type": "3BHK"
                }
            },
            {
                "message": "Need a condo immediately in Chicago area",
                "expected": {
                    "location": "Chicago",
                    "property_type": "Condo"
                }
            }
        ]
        
        all_passed = True
        for test_case in test_messages:
            message = test_case["message"]
            expected = test_case["expected"]
            
            try:
                result = fallback_extract_lead_info(message)
                
                # Check each expected field
                case_passed = True
                for field, expected_val in expected.items():
                    if result.get(field) != expected_val:
                        case_passed = False
                        all_passed = False
                
                if case_passed:
                    self.log_test(f"Extract from: '{message}'", True)
                else:
                    self.log_test(f"Extract from: '{message}'", False, f"Expected {expected}, got {result}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Extract from: '{message}' without error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    def test_fallback_response_generation(self):
        """Test fallback response generation"""
        print("\n🧪 Testing fallback response generation...")
        
        test_cases = [
            {
                "agent_type": "qualifier",
                "extracted_info": {"budget": 500000, "location": "New York"},
                "user_name": "John",
                "expected_keywords": ["John", "budget", "location"]
            },
            {
                "agent_type": "scheduler",
                "extracted_info": {"budget": 300000},
                "user_name": "Sarah",
                "expected_keywords": ["Sarah", "qualified", "consultation"]
            },
            {
                "agent_type": "followup",
                "extracted_info": {"budget": 400000, "location": "Austin"},
                "user_name": "Mike",
                "expected_keywords": ["Mike", "options", "Austin"]
            }
        ]
        
        all_passed = True
        for test_case in test_cases:
            try:
                response = generate_fallback_response(
                    test_case["extracted_info"],
                    test_case["agent_type"],
                    test_case["user_name"]
                )
                
                # Check if response contains expected keywords
                has_keywords = all(
                    keyword.lower() in response.lower() 
                    for keyword in test_case["expected_keywords"]
                )
                
                if has_keywords and len(response) > 20:  # Reasonable length
                    self.log_test(f"Generate {test_case['agent_type']} response", True)
                else:
                    self.log_test(f"Generate {test_case['agent_type']} response", False, 
                                f"Missing keywords or too short: {response[:100]}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Generate {test_case['agent_type']} response without error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    def test_contextual_fallback(self):
        """Test contextual fallback generation"""
        print("\n🧪 Testing contextual fallback generation...")
        
        test_cases = [
            {
                "prompt": "Extract lead information from this message",
                "expected_keywords": ["budget", "location", "null"]
            },
            {
                "prompt": "Generate qualifier agent response",
                "expected_keywords": ["budget", "location", "help"]
            },
            {
                "prompt": "Generate scheduler response",
                "expected_keywords": ["schedule", "consultation", "availability"]
            }
        ]
        
        all_passed = True
        for test_case in test_cases:
            try:
                response = generate_contextual_fallback(test_case["prompt"])
                
                # Check if response contains expected keywords
                has_keywords = all(
                    keyword.lower() in response.lower() 
                    for keyword in test_case["expected_keywords"]
                )
                
                if has_keywords and len(response) > 10:  # Reasonable length
                    self.log_test(f"Contextual fallback for '{test_case['prompt'][:30]}...'", True)
                else:
                    self.log_test(f"Contextual fallback for '{test_case['prompt'][:30]}...'", False,
                                f"Missing keywords or too short: {response[:100]}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Contextual fallback without error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    def test_lead_scoring_with_string_budgets(self):
        """Test lead scoring with string budgets to ensure no type errors"""
        print("\n🧪 Testing lead scoring with string budgets...")
        
        test_cases = [
            {
                "lead_data": {
                    "budget": "$500,000",  # String with currency and commas
                    "location": "New York",
                    "timeline": "3 months"
                },
                "expected_score_range": (0.4, 1.0)
            },
            {
                "lead_data": {
                    "budget": "250000",  # String number
                    "location": "Austin",
                    "timeline": "6 months"
                },
                "expected_score_range": (0.4, 1.0)
            },
            {
                "lead_data": {
                    "budget": "invalid",  # Invalid string
                    "location": "Chicago",
                    "timeline": "1 year"
                },
                "expected_score_range": (0.0, 0.8)
            }
        ]
        
        all_passed = True
        for test_case in test_cases:
            try:
                result = calculate_lead_score(test_case["lead_data"])
                score = result.get("final_score", 0)
                min_score, max_score = test_case["expected_score_range"]
                
                if min_score <= score <= max_score and "error" not in result:
                    self.log_test(f"Score lead with budget '{test_case['lead_data']['budget']}'", True)
                else:
                    self.log_test(f"Score lead with budget '{test_case['lead_data']['budget']}'", False,
                                f"Score {score} not in range {min_score}-{max_score} or error: {result.get('error')}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Score lead without type error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    async def test_end_to_end_processing(self):
        """Test end-to-end processing with various scenarios"""
        print("\n🧪 Testing end-to-end processing...")
        
        test_cases = [
            {
                "message": "Looking for a 2BHK apartment in New York with budget $500,000",
                "user_id": "test_user_1",
                "user_name": "John Doe",
                "expected_agent": "followup"  # Should be qualified enough for followup
            },
            {
                "message": "Need help finding property",
                "user_id": "test_user_2", 
                "user_name": "Jane Smith",
                "expected_agent": "qualifier"  # Should need more qualification
            }
        ]
        
        all_passed = True
        for test_case in test_cases:
            try:
                result = await process_lead_message(
                    test_case["user_id"],
                    test_case["message"],
                    "instagram",
                    test_case["user_name"]
                )
                
                # Check basic response structure
                has_required_fields = all(
                    field in result for field in ["status", "response_message", "lead_id"]
                )
                
                # Check if response is reasonable
                response = result.get("response_message", "")
                has_content = len(response) > 20 and "error" not in response.lower()
                
                if has_required_fields and has_content:
                    self.log_test(f"Process message: '{test_case['message'][:30]}...'", True)
                else:
                    self.log_test(f"Process message: '{test_case['message'][:30]}...'", False,
                                f"Missing fields or poor response: {result}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Process message without error", False, f"Exception: {e}")
                all_passed = False
        
        return all_passed
    
    async def run_all_tests(self):
        """Run all tests and generate report"""
        print("🚀 Starting comprehensive production fixes test...\n")
        
        # Run synchronous tests
        tests = [
            ("Safe Integer Conversion", self.test_safe_int_convert),
            ("Fallback Lead Extraction", self.test_fallback_lead_extraction),
            ("Fallback Response Generation", self.test_fallback_response_generation),
            ("Contextual Fallback", self.test_contextual_fallback),
            ("Lead Scoring with String Budgets", self.test_lead_scoring_with_string_budgets),
        ]
        
        for test_name, test_func in tests:
            try:
                passed = test_func()
                if not passed:
                    print(f"⚠️ {test_name} had failures")
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
        
        # Run async tests
        async_tests = [
            ("End-to-End Processing", self.test_end_to_end_processing),
        ]
        
        for test_name, test_func in async_tests:
            try:
                passed = await test_func()
                if not passed:
                    print(f"⚠️ {test_name} had failures")
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  • {result['test']}: {result['details']}")
        
        print("\n" + "="*60)
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Production fixes are working correctly.")
        else:
            print("⚠️ Some tests failed. Please review the issues above.")
        
        print("="*60)


async def main():
    """Main test runner"""
    tester = ProductionFixesTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())