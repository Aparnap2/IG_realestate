#!/usr/bin/env python3
"""
Debug script to test webhook message processing.
This helps identify why messages from your other Instagram account are being skipped.
"""

import os
import sys
import json
import requests
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_webhook_with_sample_payload():
    """Test webhook with a sample payload that mimics an echo message"""
    
    # Sample payload that resembles an echo message from another account
    sample_payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "1234567890",  # Your IG account ID
                "time": int(time.time()),
                "messaging": [
                    {
                        "sender": {
                            "id": "USER_ID_FROM_OTHER_ACCOUNT"  # This would be the other account's ID
                        },
                        "recipient": {
                            "id": "1234567890"  # Your IG account ID
                        },
                        "timestamp": int(time.time()),
                        "message": {
                            "mid": "message_id_12345",
                            "text": "Hello from my other account",
                            "is_echo": True  # This is what causes the skipping
                        }
                    }
                ]
            }
        ]
    }
    
    webhook_url = "http://localhost:8000/"
    
    print("🔧 Testing webhook with echo message payload...")
    print(f"📤 Sending to: {webhook_url}")
    print(f"📋 Payload: {json.dumps(sample_payload, indent=2)}")
    
    try:
        response = requests.post(
            webhook_url,
            json=sample_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook test successful")
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")

def test_webhook_with_normal_payload():
    """Test webhook with a normal (non-echo) message"""
    
    normal_payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "1234567890",
                "time": int(time.time()),
                "messaging": [
                    {
                        "sender": {
                            "id": "USER_ID_FROM_OTHER_ACCOUNT"
                        },
                        "recipient": {
                            "id": "1234567890"
                        },
                        "timestamp": int(time.time()),
                        "message": {
                            "mid": "message_id_67890",
                            "text": "Hello from my other account (normal message)",
                            "is_echo": False  # Normal message
                        }
                    }
                ]
            }
        ]
    }
    
    webhook_url = "http://localhost:8000/"
    
    print("\n🔧 Testing webhook with normal message payload...")
    print(f"📤 Sending to: {webhook_url}")
    print(f"📋 Payload: {json.dumps(normal_payload, indent=2)}")
    
    try:
        response = requests.post(
            webhook_url,
            json=normal_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook test successful")
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")

def check_environment():
    """Check current environment settings"""
    print("\n🔍 Current Environment Settings:")
    print(f"  - ALLOW_ECHO_MESSAGES: {os.getenv('ALLOW_ECHO_MESSAGES', 'not set')}")
    print(f"  - ENVIRONMENT: {os.getenv('ENVIRONMENT', 'not set')}")
    print(f"  - META_VERIFY_TOKEN: {os.getenv('META_VERIFY_TOKEN', 'not set')}")
    print(f"  - META_APP_SECRET: {'set' if os.getenv('META_APP_SECRET') else 'not set'}")

if __name__ == "__main__":
    print("🐛 Instagram Webhook Debug Tool")
    print("=" * 50)
    
    check_environment()
    
    print("\n" + "=" * 50)
    print("Testing webhook message processing...")
    
    # Test with echo message (should be skipped unless ALLOW_ECHO_MESSAGES=true)
    test_webhook_with_sample_payload()
    
    # Test with normal message (should always be processed)
    test_webhook_with_normal_payload()
    
    print("\n" + "=" * 50)
    print("📝 Debug Instructions:")
    print("1. To allow echo messages during testing, set:")
    print("   export ALLOW_ECHO_MESSAGES=true")
    print("2. Restart the backend server after setting the environment variable")
    print("3. Check the backend logs for detailed debugging information")
    print("4. Use ngrok to expose the webhook to Meta's servers")
    print("5. Test with your other Instagram account")