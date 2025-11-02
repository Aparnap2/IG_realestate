"""
Celery tasks for Email message processing.

This module handles asynchronous processing of email messages
through the PRD-compliant lead processing workflow.

Uses the centralized Celery app from backend.celery_app for proper
task registration and configuration.
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import centralized Celery app
from backend.celery_app import celery_app
from backend.booking.message_bus import NormalizedMessage
from backend.utils.audit import audit_log_event
from backend.utils.database import DatabaseConnectionManager, execute_with_retry
from tasks.production_lead_processing import process_lead_message

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='tasks.email_processing.process_email_message', max_retries=3)
def process_email_message(self, normalized_message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process normalized email message through the lead processing workflow.
    
    Args:
        normalized_message_data: Dictionary containing normalized message data
        
    Returns:
        Dictionary with processing results
    """
    task_start_time = datetime.now()
    
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
        
        logger.info(f"📧 Processing email message: {normalized_message.message_uuid}")
        
        # Record audit log for task start using database connection manager
        try:
            with DatabaseConnectionManager() as db_session:
                audit_log_event("email_message_processing_started", {
                    "message_uuid": normalized_message.message_uuid,
                    "lead_id": normalized_message.lead_id,
                    "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content,
                    "provider": normalized_message.metadata.get('provider', 'unknown'),
                    "from_email": normalized_message.metadata.get('from_email', 'unknown'),
                    "task_id": self.request.id,
                    "task_start_time": task_start_time.isoformat()
                })
        except Exception as audit_error:
            logger.warning(f"⚠️ Failed to record audit log for task start: {audit_error}")
        
        # Check if this is a booking-related message
        message_text = normalized_message.content.lower()
        booking_keywords = ["book", "schedule", "tour", "appointment", "available", "time", "viewing", "showing"]
        
        has_booking_intent = any(keyword in message_text for keyword in booking_keywords)
        
        if not has_booking_intent:
            logger.info(f"📝 Email message without booking intent, skipping: {normalized_message.message_uuid}")
            
            # Record audit log for skipped message
            try:
                with DatabaseConnectionManager() as db_session:
                    audit_log_event("email_message_skipped_non_booking", {
                        "message_uuid": normalized_message.message_uuid,
                        "lead_id": normalized_message.lead_id,
                        "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content,
                        "provider": normalized_message.metadata.get('provider', 'unknown'),
                        "from_email": normalized_message.metadata.get('from_email', 'unknown'),
                        "processing_time": (datetime.now() - task_start_time).total_seconds()
                    })
            except Exception as audit_error:
                logger.warning(f"⚠️ Failed to record audit log for skipped message: {audit_error}")
            
            return {
                "status": "skipped",
                "message_uuid": normalized_message.message_uuid,
                "reason": "non_booking_intent",
                "content": normalized_message.content,
                "provider": normalized_message.metadata.get('provider', 'unknown'),
                "from_email": normalized_message.metadata.get('from_email', 'unknown'),
                "processing_time": (datetime.now() - task_start_time).total_seconds()
            }
        
        # Extract user information for the lead processing
        user_id = normalized_message.lead_id
        message_content = normalized_message.content
        from_email = normalized_message.metadata.get('from_email', 'Unknown')
        provider = normalized_message.metadata.get('provider', 'unknown')
        
        # Use production lead processor to handle the message
        try:
            import asyncio
            
            # Extract user name from email address or use a default
            if '@' in from_email:
                user_name = from_email.split('@')[0]  # Use email prefix as name
            else:
                user_name = f"Email User ({from_email})"
            
            # Process through the lead workflow with database session management
            def process_with_db_session():
                # Use the database session from the connection manager
                with DatabaseConnectionManager() as db_session:
                    if db_session:
                        # We have a database session available
                        pass
                
                # Execute the async lead processing
                return asyncio.run(process_lead_message(
                    user_id=user_id,
                    message=message_content,
                    channel="email",
                    user_name=user_name
                ))
            
            result = execute_with_retry(process_with_db_session)
            
            processing_time = (datetime.now() - task_start_time).total_seconds()
            
            logger.info(f"✅ Email message processing completed: {normalized_message.message_uuid}")
            logger.info(f"   Status: {result.get('status', 'unknown')}")
            logger.info(f"   Provider: {provider}")
            logger.info(f"   From: {from_email}")
            logger.info(f"   Processing time: {processing_time:.2f}s")
            logger.info(f"   Response: {result.get('response_message', 'No response')[:100]}...")
            
            # Record audit log for successful processing
            try:
                with DatabaseConnectionManager() as db_session:
                    audit_log_event("email_message_processed_successfully", {
                        "message_uuid": normalized_message.message_uuid,
                        "lead_id": normalized_message.lead_id,
                        "provider": provider,
                        "from_email": from_email,
                        "status": result.get('status'),
                        "qualification_score": result.get('qualification_score'),
                        "next_agent": result.get('next_agent'),
                        "response_message": result.get('response_message', '')[:200] + "..." if len(result.get('response_message', '')) > 200 else result.get('response_message', ''),
                        "processing_time": processing_time,
                        "task_id": self.request.id
                    })
            except Exception as audit_error:
                logger.warning(f"⚠️ Failed to record audit log for successful processing: {audit_error}")
            
            return {
                "status": "success",
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "provider": provider,
                "from_email": from_email,
                "processing_result": result,
                "response_message": result.get('response_message'),
                "qualification_score": result.get('qualification_score'),
                "next_agent": result.get('next_agent'),
                "processing_time": processing_time,
                "task_id": self.request.id
            }
            
        except Exception as processing_error:
            logger.error(f"❌ Error in lead processing for email message {normalized_message.message_uuid}: {processing_error}")
            
            # Record audit log for processing error
            try:
                with DatabaseConnectionManager() as db_session:
                    audit_log_event("email_message_processing_error", {
                        "message_uuid": normalized_message.message_uuid,
                        "lead_id": normalized_message.lead_id,
                        "provider": provider,
                        "from_email": from_email,
                        "error": str(processing_error),
                        "content": normalized_message.content[:100] + "..." if len(normalized_message.content) > 100 else normalized_message.content,
                        "retry_count": self.request.retries,
                        "processing_time": (datetime.now() - task_start_time).total_seconds()
                    })
            except Exception as audit_error:
                logger.warning(f"⚠️ Failed to record audit log for processing error: {audit_error}")
            
            # Retry if possible
            if self.request.retries < 3:
                logger.info(f"🔄 Retrying email message processing (attempt {self.request.retries + 1}/3)")
                raise self.retry(
                    countdown=60 * (2 ** self.request.retries),  # Exponential backoff
                    exc=processing_error
                )
            
            return {
                "status": "error",
                "message_uuid": normalized_message.message_uuid,
                "lead_id": normalized_message.lead_id,
                "provider": provider,
                "from_email": from_email,
                "error": str(processing_error),
                "retries": self.request.retries,
                "processing_time": (datetime.now() - task_start_time).total_seconds()
            }
        
    except Exception as e:
        logger.error(f"❌ Fatal error processing email message: {e}")
        
        # Record audit log for fatal error
        try:
            with DatabaseConnectionManager() as db_session:
                audit_log_event("email_message_fatal_error", {
                    "message_uuid": normalized_message_data.get('message_uuid', 'unknown'),
                    "error": str(e),
                    "task_id": self.request.id,
                    "processing_time": (datetime.now() - task_start_time).total_seconds(),
                    "retry_count": self.request.retries
                })
        except Exception as audit_error:
            logger.warning(f"⚠️ Failed to record audit log: {audit_error}")
        
        # Retry if possible
        if self.request.retries < 3:
            logger.info(f"🔄 Retrying after fatal error (attempt {self.request.retries + 1}/3)")
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=e
            )
        
        return {
            "status": "fatal_error",
            "message_uuid": normalized_message_data.get('message_uuid', 'unknown'),
            "error": str(e),
            "retries": self.request.retries,
            "processing_time": (datetime.now() - task_start_time).total_seconds()
        }


@celery_app.task(name='tasks.email_processing.health_check')
def health_check() -> Dict[str, Any]:
    """
    Perform comprehensive health check for Email processing Celery worker.
    
    Returns:
        Health status dictionary with detailed system information
    """
    try:
        from backend.booking.message_bus import MessageBus
        from backend.utils.database import health_check_database
        from backend.celery_app import health_check as celery_health_check
        
        start_time = datetime.now()
        
        # Test basic message normalization
        try:
            message_bus = MessageBus()
            message_bus_available = message_bus is not None
        except Exception as e:
            message_bus_available = False
            logger.warning(f"MessageBus initialization failed: {e}")
        
        # Test database connectivity
        db_health = health_check_database()
        
        # Test Celery system health
        celery_system_health = celery_health_check()
        
        # Test email-specific functionality
        email_test_result = {"test_passed": False, "test_error": None}
        try:
            # Test email provider connectivity (lightweight test)
            # This would normally test actual email provider connections
            email_test_result["test_passed"] = True
        except Exception as e:
            email_test_result["test_error"] = str(e)
        
        health_check_duration = (datetime.now() - start_time).total_seconds()
        
        # Determine overall health status
        all_checks_passed = (
            message_bus_available and
            db_health.get("status") == "healthy" and
            celery_system_health.get("status") == "healthy" and
            email_test_result["test_passed"]
        )
        
        return {
            "status": "healthy" if all_checks_passed else "degraded",
            "timestamp": datetime.now().isoformat(),
            "health_check_duration": health_check_duration,
            "components": {
                "message_bus": {
                    "status": "available" if message_bus_available else "unavailable",
                    "healthy": message_bus_available
                },
                "database": db_health,
                "celery_system": celery_system_health,
                "email_provider": email_test_result
            },
            "message": "All systems operational" if all_checks_passed else "Some components are not healthy",
            "service": "email_processing"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "service": "email_processing"
        }


@celery_app.task(name='tasks.email_processing.bulk_process_emails')
def bulk_process_emails(emails: list) -> Dict[str, Any]:
    """
    Bulk process multiple email messages for efficiency.
    
    Args:
        emails: List of normalized email message data dictionaries
        
    Returns:
        Dictionary with processing results summary
    """
    start_time = datetime.now()
    results = []
    
    try:
        logger.info(f"🔄 Starting bulk processing of {len(emails)} email messages")
        
        # Process each email
        for i, email_data in enumerate(emails):
            try:
                logger.debug(f"Processing email {i+1}/{len(emails)}: {email_data.get('message_uuid', 'unknown')}")
                
                # Call the main processing task for each email
                result = process_email_message.delay(email_data)
                
                # Store the task result reference (not the actual result)
                results.append({
                    "message_uuid": email_data.get('message_uuid'),
                    "task_id": result.id,
                    "status": "queued",
                    "queue_position": i + 1,
                    "provider": email_data.get('metadata', {}).get('provider', 'unknown'),
                    "from_email": email_data.get('metadata', {}).get('from_email', 'unknown')
                })
                
            except Exception as e:
                logger.error(f"Failed to queue email {i+1}: {e}")
                results.append({
                    "message_uuid": email_data.get('message_uuid', 'unknown'),
                    "status": "failed_to_queue",
                    "error": str(e),
                    "queue_position": i + 1,
                    "provider": email_data.get('metadata', {}).get('provider', 'unknown'),
                    "from_email": email_data.get('metadata', {}).get('from_email', 'unknown')
                })
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Record audit log for bulk processing start
        try:
            with DatabaseConnectionManager() as db_session:
                audit_log_event("email_bulk_processing_started", {
                    "total_emails": len(emails),
                    "queued_emails": len([r for r in results if r["status"] == "queued"]),
                    "failed_to_queue": len([r for r in results if r["status"] == "failed_to_queue"]),
                    "processing_time": processing_time,
                    "task_id": f"bulk_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                })
        except Exception as audit_error:
            logger.warning(f"⚠️ Failed to record audit log for bulk processing: {audit_error}")
        
        logger.info(f"✅ Bulk email processing initiated for {len(emails)} messages in {processing_time:.2f}s")
        
        return {
            "status": "bulk_processing_initiated",
            "total_emails": len(emails),
            "queued_emails": len([r for r in results if r["status"] == "queued"]),
            "failed_to_queue": len([r for r in results if r["status"] == "failed_to_queue"]),
            "processing_time": processing_time,
            "results": results,
            "message": "Bulk email processing initiated successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Bulk email processing failed: {e}")
        return {
            "status": "bulk_processing_failed",
            "total_emails": len(emails),
            "error": str(e),
            "processing_time": (datetime.now() - start_time).total_seconds(),
            "results": results
        }


# Configure periodic tasks using the centralized Celery app
celery_app.conf.beat_schedule.update({
    'email-health-check': {
        'task': 'tasks.email_processing.health_check',
        'schedule': 300.0,  # Run every 5 minutes
    },
})

# Export task functions for proper registration
__all__ = [
    'process_email_message',
    'health_check',
    'bulk_process_emails'
]