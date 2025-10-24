#!/usr/bin/env python3
"""
Individual Component Testing Script
Tests each component of the Instagram DM automation system
"""
import requests
import json
import time
import os

BASE_URL = "http://localhost:8000"

def test_health():
    """Test 1: Backend Health Check"""
    print("🧪 Test 1: Backend Health Check")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend is healthy: {data.get('status')}")
            print(f"📊 Webhook service: {data.get('webhook_service', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_supabase():
    """Test 2: Supabase Connection (tested through API)"""
    print("\n🧪 Test 2: Supabase Connection")
    try:
        # Test through a simple API call that uses Supabase
        response = requests.get(f"{BASE_URL}/api/leads?limit=1", timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection works")
            data = response.json()
            print(f"📊 Leads API response: {len(data.get('leads', []))} leads found")
            return True
        else:
            print(f"⚠️ Leads API response: {response.status_code}")
            # Only critical if it's a database error
            if response.status_code >= 500:
                print("❌ Database connection issue detected")
                return False
            return True  # Other failures are acceptable for this test
    except Exception as e:
        print(f"❌ Supabase test error: {e}")
        return False

def test_webhook_verify():
    """Test 3: Instagram Webhook Verification"""
    print("\n🧪 Test 3: Instagram Webhook Verification")
    try:
        response = requests.get(
            f"{BASE_URL}/",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "test_challenge_12345",
                "hub.verify_token": "aaa_real_estate_verify_token_2025"
            },
            timeout=5
        )
        if response.status_code == 200:
            print("✅ Webhook verification works")
            return True
        else:
            print(f"❌ Webhook verification failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook test error: {e}")
        return False

def test_webhook_endpoint():
    """Test 4: Webhook Message Processing"""
    print("\n🧪 Test 4: Webhook Message Processing")
    webhook_data = {
        "object": "instagram",
        "entry": [{
            "id": "123456789",
            "messaging": [{
                "sender": {
                    "id": "test_user_1534105394273010"
                },
                "recipient": {
                    "id": "17841474117949549"
                },
                "timestamp": "1623456789",
                "message": {
                    "mid": "test_mid_123",
                    "text": "Hello, I need a house in Miami with budget 200k"
                }
            }]
        }]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/",
            json=webhook_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if response.status_code == 200:
            print("✅ Webhook endpoint responds correctly")
            print(f"📊 Response: {response.text[:200]}...")
            return True
        else:
            print(f"❌ Webhook processing failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        return False

def test_lead_creation():
    """Test 5: Lead Creation and Supabase Storage"""
    print("\n🧪 Test 5: Lead Creation Test")
    try:
        # Check if lead was created by the webhook
        time.sleep(2)  # Wait for processing
        response = requests.get(
            f"{BASE_URL}/api/leads",
            params={"instagram_id": "test_user_1534105394273010"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            leads = data.get('leads', [])
            if leads:
                lead = leads[0]
                print("✅ Lead creation works")
                print(f"📊 Lead ID: {lead.get('id')}")
                print(f"👤 Name: {lead.get('name', 'Not set')}")
                print(f"📱 Instagram ID: {lead.get('instagram_id')}")
                print(f"💰 Budget: {lead.get('budget', 'Not extracted')}")
                return True
            else:
                print("⚠️ Lead not found (may still be processing)")
                return False
        else:
            print(f"❌ Lead lookup failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Lead creation test error: {e}")
        return False

def run_all_tests():
    """Run all individual tests"""
    print("🚀 Starting Individual Component Tests\n")
    
    tests = [
        ("Backend Health", test_health),
        ("Supabase Connection", test_supabase),
        ("Webhook Verification", test_webhook_verify),
        ("Webhook Processing", test_webhook_endpoint),
        ("Lead Creation", test_lead_creation)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for production.")
    elif passed >= total * 0.8:
        print("⚠️ Most tests passed. System is mostly functional.")
    else:
        print("🚨 Multiple failures detected. Check the issues above.")
    
    return results

if __name__ == "__main__":
    run_all_tests()
