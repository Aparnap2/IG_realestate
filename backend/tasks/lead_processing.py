"""
Celery tasks for lead processing using LangGraph workflow.

This module handles asynchronous processing of leads through the
PRD-compliant LangGraph swarm architecture.
"""
import sys
import os
from celery import Celery
from typing import Dict, Any
import uuid

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.lead import Lead
from schemas.state import AgentState
from backend.workflow import create_workflow
from utils.redis_client import store_conversation_history
from utils.observability import track_performance, metrics_collector

# Initialize Celery app
celery_app = Celery(
    'lead_processing',
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
        'tasks.lead_processing.process_lead': {'queue': 'lead_processing'},
        'tasks.lead_processing.process_webhook': {'queue': 'webhooks'},
    },
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

@celery_app.task(bind=True, name='tasks.lead_processing.process_lead')
@track_performance
def process_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a lead through the LangGraph workflow.
    
    Args:
        lead_data: Dictionary containing lead information
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Create Lead object
        lead = Lead(**lead_data)
        
        # Create initial state
        initial_state: AgentState = {
            "lead": lead,
            "messages": [
                {
                    "role": "user",
                    "content": lead.message
                }
            ],
            "human_feedback": None,
            "next_agent": "qualifier",
            "interrupt": None,
            "db_results": None,
            "available_slots": None,
            "error_message": None,
            "retry_count": 0
        }
        
        # Create workflow
        workflow = create_workflow()
        
        # Configuration for thread persistence
        config = {
            "configurable": {
                "thread_id": lead.user_id
            }
        }
        
        # Process through workflow
        result = workflow.invoke(initial_state, config)
        
        # Store conversation history
        store_conversation_history(
            lead.user_id,
            {
                "user_message": lead.message,
                "assistant_messages": [msg for msg in result.get("messages", []) if msg.get("role") == "assistant"],
                "timestamp": lead.created_at.isoformat(),
                "status": result["lead"].status,
                "score": result["lead"].qualified_score
            }
        )
        
        # Update metrics
        metrics_collector.increment_counter("leads_processed")
        if result["lead"].qualified_score:
            metrics_collector.record_score("qualification_score", result["lead"].qualified_score)
        
        return {
            "success": True,
            "lead_id": result["lead"].id,
            "status": result["lead"].status,
            "qualified_score": result["lead"].qualified_score,
            "next_agent": result.get("next_agent"),
            "interrupt": result.get("interrupt", False)
        }
        
    except Exception as e:
        # Log error and retry if possible
        print(f"Error processing lead: {e}")
        
        # Update metrics
        metrics_collector.increment_counter("lead_processing_errors")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=e
            )
        
        return {
            "success": False,
            "error": str(e),
            "lead_id": lead_data.get("id"),
            "retries": self.request.retries
        }

@celery_app.task(bind=True, name='tasks.lead_processing.process_webhook')
@track_performance
def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming webhook data and create lead processing task.
    
    Args:
        webhook_data: Raw webhook data from Meta APIs
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Extract lead information from webhook
        channel = webhook_data.get("channel", "unknown")
        
        if channel == "ig":
            # Process Instagram webhook
            entry = webhook_data.get("entry", [{}])[0]
            messaging = entry.get("messaging", [{}])[0]
            sender = messaging.get("sender", {})
            message = messaging.get("message", {})
            
            user_id = sender.get("id")
            message_text = message.get("text", "")
        else:
            raise ValueError(f"Unsupported channel: {channel}")
        
        if not user_id or not message_text:
            raise ValueError("Missing user_id or message_text")
        
        # Create lead data
        lead_data = {
            "id": str(uuid.uuid4()),
            "channel": channel,
            "user_id": user_id,
            "message": message_text,
            "status": "new"
        }
        
        # Queue lead for processing
        task_result = process_lead.delay(lead_data)
        
        # Update metrics
        metrics_collector.increment_counter("webhooks_processed")
        metrics_collector.increment_counter(f"webhooks_{channel}")
        
        return {
            "success": True,
            "task_id": task_result.id,
            "lead_id": lead_data["id"],
            "channel": channel,
            "user_id": user_id
        }
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        
        # Update metrics
        metrics_collector.increment_counter("webhook_processing_errors")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=30 * (2 ** self.request.retries),
                exc=e
            )
        
        return {
            "success": False,
            "error": str(e),
            "webhook_data": webhook_data,
            "retries": self.request.retries
        }

@celery_app.task(name='tasks.lead_processing.resume_interrupted_lead')
@track_performance
def resume_interrupted_lead(lead_id: str, human_feedback: str) -> Dict[str, Any]:
    """
    Resume processing of an interrupted lead after HITL approval.
    
    Args:
        lead_id: Lead identifier
        human_feedback: Human feedback/approval
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Create workflow
        workflow = create_workflow()
        
        # Configuration for thread persistence
        config = {
            "configurable": {
                "thread_id": lead_id  # Using lead_id as thread_id
            }
        }
        
        # Get current state
        current_state = workflow.get_state(config)
        
        if not current_state:
            raise ValueError(f"No state found for lead {lead_id}")
        
        # Update state with human feedback
        updated_state = current_state.values.copy()
        updated_state["human_feedback"] = human_feedback
        
        # Resume workflow
        result = workflow.invoke(updated_state, config)
        
        # Update metrics
        metrics_collector.increment_counter("hitl_resumes")
        
        return {
            "success": True,
            "lead_id": lead_id,
            "status": result["lead"].status,
            "human_feedback": human_feedback
        }
        
    except Exception as e:
        print(f"Error resuming interrupted lead: {e}")
        
        # Update metrics
        metrics_collector.increment_counter("hitl_resume_errors")
        
        return {
            "success": False,
            "error": str(e),
            "lead_id": lead_id
        }

# Health check task
@celery_app.task(name='tasks.lead_processing.health_check')
def health_check() -> Dict[str, Any]:
    """
    Perform health check for Celery worker.
    
    Returns:
        Health status dictionary
    """
    try:
        # Test workflow creation
        workflow = create_workflow()
        
        # Test basic operations
        test_lead = Lead(
            channel="test",
            user_id="health_check",
            message="Health check test"
        )
        
        return {
            "status": "healthy",
            "workflow_available": workflow is not None,
            "timestamp": str(uuid.uuid4())
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# Periodic tasks
@celery_app.task(name='tasks.lead_processing.cleanup_old_threads')
def cleanup_old_threads():
    """Clean up old thread states from Redis"""
    try:
        from utils.redis_client import redis_client
        
        # Clean up threads older than 30 days
        # This is a placeholder - implement actual cleanup logic
        print("Cleaning up old thread states...")
        
        return {"success": True, "message": "Cleanup completed"}
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return {"success": False, "error": str(e)}

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-old-threads': {
        'task': 'tasks.lead_processing.cleanup_old_threads',
        'schedule': 86400.0,  # Run daily
    },
}

if __name__ == "__main__":
    celery_app.start()