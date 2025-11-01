"""
Test script for email Celery integration.

This script tests the new email processing Celery task
to ensure proper integration with the email webhook.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_email_processing_import():
    """Test that email processing module can be imported."""
    try:
        from tasks.email_processing import process_email_message, health_check, celery_app
        print("✅ Successfully imported email processing modules")
        return True
    except Exception as e:
        print(f"❌ Failed to import email processing modules: {e}")
        return False

def test_celery_app_configuration():
    """Test Celery app configuration for email processing."""
    try:
        from tasks.email_processing import celery_app
        
        # Check configuration
        assert celery_app.conf.task_routes is not None
        assert 'tasks.email_processing.process_email_message' in celery_app.conf.task_routes
        
        # Check queue configuration
        queue_config = celery_app.conf.task_routes['tasks.email_processing.process_email_message']
        assert 'email_processing' in queue_config['queue']
        
        print("✅ Celery app configuration is correct")
        return True
    except Exception as e:
        print(f"❌ Celery app configuration test failed: {e}")
        return False

def test_email_task_function():
    """Test email processing task function exists and has correct signature."""
    try:
        from tasks.email_processing import process_email_message
        
        # Check task name
        assert process_email_message.name == 'tasks.email_processing.process_email_message'
        
        # Check it's bound (has self parameter)
        assert hasattr(process_email_message, 'request')
        
        print("✅ Email processing task function is properly configured")
        return True
    except Exception as e:
        print(f"❌ Email task function test failed: {e}")
        return False

def test_normalized_message_conversion():
    """Test conversion of NormalizedMessage to dict for Celery serialization."""
    try:
        from backend.booking.message_bus import MessageBus, Channel
        import uuid
        
        # Create a test message
        message_bus = MessageBus()
        test_data = {
            "from": "test@example.com",
            "to": "leads+123@example.com", 
            "subject": "Tour Booking Inquiry",
            "text": "Hi, I'm interested in booking a tour for next week.",
            "html": "<p>Hi, I'm interested in booking a tour for next week.</p>",
            "timestamp": "1234567890",
            "channel": "email",
            "message_id": "test_msg_123",
            "provider": "sendgrid"
        }
        
        normalized_message = message_bus.normalize_message('email', test_data)
        
        # Convert to dict for Celery
        normalized_message_dict = {
            'message_uuid': normalized_message.message_uuid,
            'lead_id': normalized_message.lead_id,
            'content': normalized_message.content,
            'channel': normalized_message.channel.value if hasattr(normalized_message.channel, 'value') else str(normalized_message.channel),
            'timestamp': normalized_message.timestamp.isoformat() if hasattr(normalized_message.timestamp, 'isoformat') else str(normalized_message.timestamp),
            'metadata': normalized_message.metadata
        }
        
        # Verify the dict can be serialized
        import json
        json_str = json.dumps(normalized_message_dict)
        reconstructed = json.loads(json_str)
        
        assert 'message_uuid' in reconstructed
        assert 'lead_id' in reconstructed
        assert 'content' in reconstructed
        assert 'channel' in reconstructed
        assert 'timestamp' in reconstructed
        assert 'metadata' in reconstructed
        
        print("✅ NormalizedMessage conversion test passed")
        return True
    except Exception as e:
        print(f"❌ NormalizedMessage conversion test failed: {e}")
        return False

def test_email_webhook_integration():
    """Test that email webhook properly imports and can use the Celery task."""
    try:
        # This simulates what happens in the webhook
        from backend.booking.message_bus import MessageBus
        
        # Simulate email webhook processing
        message_bus = MessageBus()
        test_email_data = {
            "from": "john@example.com",
            "to": "leads+456@example.com",
            "subject": "Schedule a Viewing",
            "text": "Can we schedule a viewing for the property at 123 Main St?",
            "html": "<p>Can we schedule a viewing for the property at 123 Main St?</p>",
            "timestamp": "1234567890",
            "channel": "email",
            "message_id": "test_email_789",
            "provider": "mailgun"
        }
        
        normalized_message = message_bus.normalize_message('email', test_email_data)
        
        # Simulate the conversion that happens in the webhook
        normalized_message_dict = {
            'message_uuid': normalized_message.message_uuid,
            'lead_id': normalized_message.lead_id,
            'content': normalized_message.content,
            'channel': normalized_message.channel.value if hasattr(normalized_message.channel, 'value') else str(normalized_message.channel),
            'timestamp': normalized_message.timestamp.isoformat() if hasattr(normalized_message.timestamp, 'isoformat') else str(normalized_message.timestamp),
            'metadata': normalized_message.metadata
        }
        
        # Test that we can import the task function
        from tasks.email_processing import process_email_message
        
        print("✅ Email webhook integration test passed")
        return True
    except Exception as e:
        print(f"❌ Email webhook integration test failed: {e}")
        return False

def main():
    """Run all tests for email Celery integration."""
    print("🧪 Testing Email Celery Integration")
    print("=" * 50)
    
    tests = [
        test_email_processing_import,
        test_celery_app_configuration,
        test_email_task_function,
        test_normalized_message_conversion,
        test_email_webhook_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\n🔍 Running {test.__name__}...")
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Email Celery integration is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)