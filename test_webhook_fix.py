#!/usr/bin/env python3
"""
Test script to verify the Instagram webhook 405 fix
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_root_get():
    """Test GET / returns API info"""
    print("\n🧪 Test 1: GET / (API Info)")
    print("-" * 50)
    
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Should return 200 OK"
    assert response.json()["service"] == "AAA Real Estate Instagram DM Automation"
    print("✅ PASSED")

def test_root_post():
    """Test POST / handles Instagram webhooks"""
    print("\n🧪 Test 2: POST / (Instagram Webhook at Root)")
    print("-" * 50)
    
    payload = {
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "test_user_root_123"},
                "message": {"text": "Looking for 2BHK in Miami, budget $350k"}
            }]
        }]
    }
    
    response = requests.post(f"{BASE_URL}/", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Should return 200 OK (not 405)"
    assert response.json()["status"] in ["success", "error"], "Should process webhook"
    print("✅ PASSED - No 405 error!")

def test_webhook_post():
    """Test POST /webhook handles Instagram webhooks"""
    print("\n🧪 Test 3: POST /webhook (Instagram Webhook at Standard Path)")
    print("-" * 50)
    
    payload = {
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "test_user_webhook_456"},
                "message": {"text": "3BHK in Miami Beach, budget $800k"}
            }]
        }]
    }
    
    response = requests.post(f"{BASE_URL}/webhook", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Should return 200 OK"
    assert response.json()["status"] in ["success", "error"], "Should process webhook"
    print("✅ PASSED")

def test_root_verification():
    """Test GET / with verification params"""
    print("\n🧪 Test 4: GET / (Webhook Verification at Root)")
    print("-" * 50)
    
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "aaa_real_estate_verify_token_2025",
        "hub.challenge": "12345"
    }
    
    response = requests.get(f"{BASE_URL}/", params=params)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    assert response.status_code == 200, "Should return 200 OK"
    assert response.text == "12345", "Should return challenge token"
    print("✅ PASSED")

def test_webhook_verification():
    """Test GET /webhook with verification params"""
    print("\n🧪 Test 5: GET /webhook (Webhook Verification at Standard Path)")
    print("-" * 50)
    
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "aaa_real_estate_verify_token_2025",
        "hub.challenge": "67890"
    }
    
    response = requests.get(f"{BASE_URL}/webhook", params=params)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    assert response.status_code == 200, "Should return 200 OK"
    assert response.text == "67890", "Should return challenge token"
    print("✅ PASSED")

def test_health():
    """Test health endpoint"""
    print("\n🧪 Test 6: GET /health")
    print("-" * 50)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Should return 200 OK"
    assert response.json()["status"] == "healthy"
    print("✅ PASSED")

def main():
    print("=" * 50)
    print("Instagram Webhook 405 Fix - Test Suite")
    print("=" * 50)
    print(f"Testing server at: {BASE_URL}")
    print("\nMake sure the server is running:")
    print("  python instagram_webhook_server.py")
    print("=" * 50)
    
    try:
        # Test server is running
        requests.get(f"{BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Server is not running!")
        print("Start the server first: python instagram_webhook_server.py")
        sys.exit(1)
    
    tests = [
        test_root_get,
        test_root_post,  # This was failing with 405 before the fix
        test_webhook_post,
        test_root_verification,
        test_webhook_verification,
        test_health
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print("Test Results")
    print("=" * 50)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed! The 405 error is fixed.")
        print("\nThe server now handles Instagram webhooks at both:")
        print("  - POST / (root path)")
        print("  - POST /webhook (standard path)")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
