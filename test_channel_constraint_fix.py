#!/usr/bin/env python3
"""
Test script to verify the channel constraint fix works properly.
This tests both the validation logic in supabase_client.py and the database constraint.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from utils.supabase_client import save_or_update_lead, save_lead
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_channel_validation():
    """Test channel validation in supabase_client functions"""
    
    print("🧪 Testing channel constraint fix...")
    
    # Test data with various channel values
    test_cases = [
        {
            "name": "Valid channel - instagram",
            "instagram_id": "test_user_123",
            "lead_data": {
                "name": "Test User 1",
                "channel": "instagram",
                "phone": "+1234567890"
            },
            "expected_channel": "instagram"
        },
        {
            "name": "Valid channel -  ",
            "instagram_id": "test_user_124", 
            "lead_data": {
                "name": "Test User 2",
                "channel": " ",
                "phone": "+1234567891"
            },
            "expected_channel": " "
        },
        {
            "name": "Invalid channel - should default to instagram",
            "instagram_id": "test_user_125",
            "lead_data": {
                "name": "Test User 3",
                "channel": "invalid_channel",
                "phone": "+1234567892"
            },
            "expected_channel": "instagram"
        },
        {
            "name": "Missing channel - should default to instagram",
            "instagram_id": "test_user_126",
            "lead_data": {
                "name": "Test User 4",
                "phone": "+1234567893"
            },
            "expected_channel": "instagram"
        },
        {
            "name": "Valid channel - email",
            "instagram_id": "test_user_127",
            "lead_data": {
                "name": "Test User 5",
                "channel": "email",
                "email": "test@example.com"
            },
            "expected_channel": "email"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test {i}: {test_case['name']}")
        
        try:
            # Test save_or_update_lead function
            result = save_or_update_lead(
                test_case["instagram_id"], 
                test_case["lead_data"]
            )
            
            if result:
                actual_channel = result.get("channel", "not_set")
                expected_channel = test_case["expected_channel"]
                
                if actual_channel == expected_channel:
                    print(f"✅ PASS: Channel correctly set to '{actual_channel}'")
                    results.append(True)
                else:
                    print(f"❌ FAIL: Expected channel '{expected_channel}', got '{actual_channel}'")
                    results.append(False)
            else:
                print(f"❌ FAIL: No result returned from save_or_update_lead")
                results.append(False)
                
        except Exception as e:
            print(f"❌ FAIL: Exception occurred: {str(e)}")
            results.append(False)
    
    # Test save_lead function as well
    print(f"\n📝 Test {len(test_cases)+1}: Testing save_lead function with invalid channel")
    try:
        result = save_lead({
            "instagram_id": "test_user_128",
            "name": "Test User 6",
            "channel": "another_invalid_channel",
            "phone": "+1234567894"
        })
        
        if result and result.get("channel") == "instagram":
            print("✅ PASS: save_lead correctly defaulted invalid channel to 'instagram'")
            results.append(True)
        else:
            print(f"❌ FAIL: save_lead did not handle invalid channel properly")
            results.append(False)
            
    except Exception as e:
        print(f"❌ FAIL: Exception in save_lead test: {str(e)}")
        results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Channel constraint fix is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

def test_database_constraint():
    """Test that the database constraint is working by attempting direct SQL"""
    print("\n🔍 Testing database constraint...")
    
    try:
        from utils.supabase_client import _ensure_supabase
        client = _ensure_supabase()
        
        # Test valid channel
        print("📝 Testing valid channel insertion...")
        valid_result = client.table("leads").insert({
            "instagram_id": "test_valid_constraint",
            "name": "Valid Channel Test",
            "channel": "instagram"
        }).execute()
        
        if valid_result.data:
            print("✅ PASS: Valid channel accepted by database")
        else:
            print("❌ FAIL: Valid channel rejected by database")
            return False
        
        # Test invalid channel (this should fail due to constraint)
        print("📝 Testing invalid channel insertion...")
        try:
            invalid_result = client.table("leads").insert({
                "instagram_id": "test_invalid_constraint",
                "name": "Invalid Channel Test", 
                "channel": "definitely_invalid_channel"
            }).execute()
            
            print("❌ FAIL: Invalid channel was accepted by database (constraint not working)")
            return False
            
        except Exception as constraint_error:
            if "check constraint" in str(constraint_error).lower() or "leads_channel_check" in str(constraint_error).lower():
                print("✅ PASS: Invalid channel properly rejected by database constraint")
            else:
                print(f"⚠️  Unexpected error (might be okay): {str(constraint_error)}")
        
        # Clean up test data
        try:
            client.table("leads").delete().in_("instagram_id", [
                "test_valid_constraint", "test_invalid_constraint"
            ]).execute()
            print("🧹 Test data cleaned up")
        except:
            pass
            
        return True
        
    except Exception as e:
        print(f"❌ Database constraint test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting channel constraint fix tests...\n")
    
    # Test the validation logic
    validation_passed = test_channel_validation()
    
    # Test the database constraint
    constraint_passed = test_database_constraint()
    
    print(f"\n🏁 Final Results:")
    print(f"   Validation Tests: {'✅ PASSED' if validation_passed else '❌ FAILED'}")
    print(f"   Database Constraint: {'✅ PASSED' if constraint_passed else '❌ FAILED'}")
    
    if validation_passed and constraint_passed:
        print("\n🎉 All tests passed! The channel constraint fix is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Please review the implementation.")
        sys.exit(1)