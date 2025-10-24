#!/usr/bin/env python3
"""
Debug webhook to test Instagram message processing
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Test webhook with actual Instagram format
def test_webhook_specific():
    print("🧪 Testing Instagram Webhook with Specific Message...")
    
    webhook_data = {
        "object": "instagram",
        "entry": [{
            "id": "17841474117949549",  # Your IG account
            "time": 1623456789,
            "messaging": [{
                "sender": {
                    "id": "1534105394273010"  # Your user IG ID
                },
                "recipient": {
                    "id": "17841474117949549"  # Bot account
                },
                "timestamp": 1623456789,
                "message": {
                    "mid": "test_mid_debug_12345",
                    "seq": 0,
                    "text": "Hi! I have a budget of $300,000 and I'm looking for a condo in Miami. What do you have available?"
                }
            }]
        }]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/",
            json=webhook_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                processed = result.get("processed", 0)
                print(f"✅ Webhook accepted and processed {processed} messages")
                return True
            else:
                print(f"❌ Webhook error: {result.get('error', 'Unknown')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_webhook_verification():
    print("\n🧪 Testing Webhook Verification...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "test_challenge_67890",
                "hub.verify_token": "aaa_real_estate_verify_token_2025"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Webhook verification works")
            print(f"📄 Challenge Response: {response.text}")
            return True
        else:
            print(f"❌ Verification failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def check_logs():
    print("\n🧪 Checking for any processing logs in the response...")
    print("📝 The webhook POST should show processing logs in your terminal")
    print("   Look for patterns like:")
    print("   - '✅ Processing: mid=...'")
    print("   - '🎯 PRD WORKFLOW: Starting lead processing'")
    print("   - '🤖 LLM EXTRACTION: Using OpenRouter'")

if __name__ == "__main__":
    print("🚀 Instagram Webhook Debug Tool")
    print("="*40)
    
    # Test 1: Verification
    test_webhook_verification()
    
    # Test 2: Message processing
    test_webhook_specific()
    
    # Test 3: Log check
    check_logs()
    
    print("\n📋 Next Steps:")
    print("1. Watch your terminal for processing logs")
    print("2. If no logs appear, the webhook might not be reaching the backend")
    print("3. If logs appear but no response, check the ngrok configuration")
