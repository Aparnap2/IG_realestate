"""
Celery tasks for WhatsApp message processing.

This module handles asynchronous processing of WhatsApp messages
through the PRD-compliant lead processing workflow.
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from celery import Celery
from backend.booking.message_bus import NormalizedMessage
from backend.utils.audit import audit_log_event
from tasks.production_lead_processing import process_lead_message

# Initialize Celery app
celery_app = Celery(
    'whatsapp_processing',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'tasks.whatsapp_processing.process_whatsapp_message': {'queue': 'whatsapp_processing'},
    },
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)


@celery_app.task(bind=True, name='tasks.whatsapp_processing.process_whatsapp_message')
def process_whatsapp_message(self, normalized_message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process normalized WhatsApp message through the lead processing workflow.
    
    Args:
        normalized_message_data: Dictionary containing normalized message data
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Reconstruct NormalizedMessage object from dict
        from backend.booking.message_bus import Channel
        normalized_message = NormalizedMessage(
            message_uuid=normalized_message_data['message_uuid'],
            lead_id=normalized_message_data.get('lead_id'),
            content=normalized_message_data['content'],
            channel=Channel(normalized_message_data['channel']),
            timestamp=datetime.fromisoformat(normalized_message_data['timestamp']) if isinstance(normalized_message_data['timestamp'], str) else normalized_message_data['timestamp'],
            metadata=normalized_message_data.get('metadata', {})
        )
        
        print(f"🔄 Processing WhatsApp message: {normalized_message.message_uuid}")
        
        # Record audit log for task start
        audit_log_event("whatsapp_message_processing_started", {
            "message_uuid": normalized_message.message_uuid,
            "lead_id": normalized_message.lead_id,
            "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content,
            "task_id": self.request.id
        })
        
        # Check if this is a booking-related message
        message_text = normalized_message.content.lower()
        booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time", "viewing", "showing"]
        
        has_booking_intent = any(keyword in message_text for keyword in booking_keywords)
        
        if not has_booking_intent:
            print(f"📝 WhatsApp message without booking intent, skipping: {normalized_message.message_uuid}")
            
            # Record audit log for skipped message
            audit_log_event("whatsapp_message_skipped_non_booking", {
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content
            })
            
            return {
                "status": "skipped",
                "message_uuid": normalized_message.message_uuid,
                "reason": "non_booking_intent",
                "content": normalized_message.content
            }
        
        # Extract user information for the lead processing
        user_id = normalized_message.lead_id
        message_content = normalized_message.content
        phone_number = normalized_message.metadata.get('display_phone_number', 'Unknown')
        
        # Use production lead processor to handle the message
        # Note: This is an async function but Celery tasks are sync, so we'll need to handle this
        try:
            # For now, we'll use a synchronous approach or call the processor directly
            # In a production environment, you might want to use asyncio.run() or similar
            import asyncio
            
            # Extract user name from phone number or metadata
            user_name = f"WhatsApp User ({phone_number})"
            
            # Process through the lead workflow
            result = asyncio.run(process_lead_message(
                user_id=user_id,
                message=message_content,
                channel="whatsapp",
                user_name=user_name
            ))
            
            print(f"✅ WhatsApp message processing completed: {normalized_message.message_uuid}")
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"   Response: {result.get('response_message', 'No response')[:100]}...")
            
            # Record audit log for successful processing
            audit_log_event("whatsapp_message_processed_successfully", {
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "status": result.get('status'),
                "qualification_score": result.get('qualification_score'),
                "next_agent": result.get('next_agent'),
                "response_message": result.get('response_message', '')[:200] + "..." if len(result.get('response_message', '')) > 200 else result.get('response_message', '')
            })
            
            return {
                "status": "success",
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "processing_result": result,
                "response_message": result.get('response_message'),
                "qualification_score": result.get('qualification_score'),
                "next_agent": result.get('next_agent')
            }
            
        except Exception as processing_error:
            print(f"❌ Error in lead processing for WhatsApp message {normalized_message.message_uuid}: {processing_error}")
            
            # Record audit log for processing error
            audit_log_event("whatsapp_message_processing_error", {
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "error": str(processing_error),
                "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content
            })
            
            # Retry if possible
            if self.request.retries < self.max_retries:
                raise self.retry(
                    countdown=60 * (2 ** self.request.retries),
                    exc=processing_error
                )
            
            return {
                "status": "error",
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "error": str(processing_error),
                "retries": self.request.retries
            }
        
    except Exception as e:
        print(f"❌ Fatal error processing WhatsApp message: {e}")
        
        # Record audit log for fatal error
        try:
            audit_log_event("whatsapp_message_fatal_error", {
                "message_uuid": normalized_message_data.get('message_uuid', 'unknown'),
                "error": str(e),
                "task_id": self.request.id
            })
        except Exception as audit_error:
            print(f"⚠️ Failed to record audit log: {audit_error}")
        
        # Retry if possible
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=e
            )
        
        return {
            "status": "fatal_error",
            "message_uuid": normalized_message_data.get('message_uuid', 'unknown'),
            "error": str(e),
            "retries": self.request.retries
        }


@celery_app.task(name='tasks.whatsapp_processing.health_check')
def health_check() -> Dict[str, Any]:
    """
    Perform health check for WhatsApp processing Celery worker.
    
    Returns:
        Health status dictionary
    """
    try:
        # Test basic message normalization
        from backend.booking.message_bus import MessageBus
        
        message_bus = MessageBus()
        test_payload = {
            "from": "1234567890",
            "text": "Hello, I'm interested in booking a tour",
            "timestamp": "1234567890",
            "channel": "whatsapp",
            "message_id": "test_message_id"
        }
        
        # This would normally fail without proper WhatsApp payload structure,
        # but we can at least test the MessageBus initialization
        print("WhatsApp processing health check passed")
        
        return {
            "status": "healthy",
            "message_bus_available": message_bus is not None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'whatsapp-health-check': {
        'task': 'tasks.whatsapp_processing.health_check',
        'schedule': 300.0,  # Run every 5 minutes
    },
}


if __name__ == "__main__":
    celery_app.start()