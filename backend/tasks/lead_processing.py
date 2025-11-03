"""
Celery tasks for lead processing using LangGraph workflow.

This module handles asynchronous processing of leads through the
PRD-compliant LangGraph swarm architecture.
"""
import sys
import os
from celery import Celery
from typing import Dict, Any, Optional
import uuid
import logging

# CRITICAL FIX: Standardized import path setup
# Add parent directory to Python path for proper imports when running from backend dir
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(backend_dir)  # Add parent directory so backend module can be found
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import asyncio
from backend.models.lead import Lead
from backend.schemas.state import AgentState
from backend.agents.prd_compliant_workflow import create_prd_compliant_workflow as create_workflow
from backend.utils.redis_client import store_conversation_history
from backend.utils.observability import track_performance, metrics_collector
from backend.utils.enhanced_llm_extraction import extract_intent_and_details, classify_high_intent_patterns
from backend.utils.lead_scoring import score_lead_with_intent
from backend.integrations.hubspot_client import HubSpotClient, auto_create_high_intent_contact

logger = logging.getLogger(__name__)

def _should_qualify_lead(intent_analysis: Dict[str, Any], pattern_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1: Determine if a lead should be qualified based on AI intent analysis.
    
    This function implements intelligent filtering to focus qualification resources
    on high-converting prospects while filtering out low-quality leads.
    
    Args:
        intent_analysis: AI intent analysis results
        pattern_analysis: High-intent pattern detection results
        
    Returns:
        Dictionary with qualification decision and reasoning
    """
    # Default thresholds for qualification
    HIGH_INTENT_THRESHOLD = 0.75
    MEDIUM_INTENT_THRESHOLD = 0.6
    MIN_CONFIDENCE_THRESHOLD = 0.5
    
    intent_score = intent_analysis.get('intent_score', 0.0)
    confidence = intent_analysis.get('confidence', 0.0)
    intent_category = intent_analysis.get('intent_category', 'unknown')
    booking_signals = intent_analysis.get('booking_signals', False)
    budget_mentioned = intent_analysis.get('budget_mentioned', False)
    
    # Get pattern analysis results
    immediate_qualification = pattern_analysis.get('immediate_qualification', False)
    pattern_score = pattern_analysis.get('pattern_score', 0.0)
    
    # High-intent criteria: Any of these conditions qualify a lead
    high_intent_conditions = [
        # AI-detected high intent
        (intent_score >= HIGH_INTENT_THRESHOLD and confidence >= MIN_CONFIDENCE_THRESHOLD),
        
        # Booking signals are always high-intent
        booking_signals,
        
        # Immediate qualification patterns detected
        immediate_qualification,
        
        # Budget mentions with decent confidence
        (budget_mentioned and intent_score >= MEDIUM_INTENT_THRESHOLD and confidence >= 0.6),
        
        # Specific high-value intent categories
        (intent_category in ['booking_intent', 'budget_inquiry'] and intent_score >= MEDIUM_INTENT_THRESHOLD),
        
        # High pattern score
        (pattern_score >= 0.5)
    ]
    
    # Check if any high-intent condition is met
    should_qualify = any(high_intent_conditions)
    
    # Determine reason and category for metrics
    if booking_signals:
        reason = "Booking signals detected"
        filter_category = "booking_signals"
        create_crm_contact = True
        high_intent_triggered = True
    elif intent_score >= HIGH_INTENT_THRESHOLD:
        reason = f"High AI intent score: {intent_score:.3f}"
        filter_category = "high_intent_score"
        create_crm_contact = True
        high_intent_triggered = True
    elif immediate_qualification:
        reason = "High-intent patterns detected"
        filter_category = "pattern_match"
        create_crm_contact = True
        high_intent_triggered = True
    elif intent_category in ['booking_intent', 'budget_inquiry']:
        reason = f"High-value intent category: {intent_category}"
        filter_category = "intent_category"
        create_crm_contact = True
        high_intent_triggered = True
    elif intent_score >= MEDIUM_INTENT_THRESHOLD:
        reason = f"Medium AI intent score: {intent_score:.3f}"
        filter_category = "medium_intent"
        create_crm_contact = False
        high_intent_triggered = False
    else:
        reason = f"Low intent score: {intent_score:.3f}"
        filter_category = "low_intent"
        create_crm_contact = False
        high_intent_triggered = False
    
    return {
        'should_qualify': should_qualify,
        'reason': reason,
        'filter_category': filter_category,
        'create_crm_contact': create_crm_contact,
        'high_intent_triggered': high_intent_triggered,
        'intent_score': intent_score,
        'confidence': confidence,
        'qualification_threshold_met': should_qualify
    }

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
    Process a lead through Phase 1 enhanced workflow with intent filtering.
    
    Only qualifies high-intent leads to optimize resource allocation.
    
    Args:
        lead_data: Dictionary containing lead information
        
    Returns:
        Dictionary with processing results and intent analysis
    """
    try:
        # Phase 1: Extract intent data if available (from webhook processing)
        intent_analysis = lead_data.get('intent_analysis', {})
        pattern_analysis = lead_data.get('pattern_analysis', {})
        message = lead_data.get('message', '')
        
        # Phase 1: High-intent filtering - only process leads that meet criteria
        should_qualify = _should_qualify_lead(intent_analysis, pattern_analysis)
        
        if not should_qualify['should_qualify']:
            logger.info(f"Lead {lead_data.get('id', 'unknown')} filtered out: {should_qualify['reason']}")
            
            # Still update metrics for filtered leads
            metrics_collector.increment_counter("leads_filtered")
            metrics_collector.increment_counter(f"filter_reason_{should_qualify['filter_category']}")
            
            return {
                "success": True,
                "lead_id": lead_data.get("id"),
                "status": "filtered",
                "filter_reason": should_qualify['reason'],
                "filter_category": should_qualify['filter_category'],
                "intent_score": intent_analysis.get('intent_score', 0.0),
                "qualified_score": None,
                "next_agent": "filtered",
                "phase_1_filtering": True,
                "intent_analysis": intent_analysis
            }
        
        logger.info(f"High-intent lead qualified for processing: {should_qualify['reason']}")
        
        # Phase 1: Auto-create HubSpot contact for high-intent leads
        hubspot_contact_id = None
        if should_qualify.get('create_crm_contact', False):
            try:
                hubspot_contact_id = auto_create_high_intent_contact(lead_data, intent_analysis)
                if hubspot_contact_id:
                    logger.info(f"Auto-created HubSpot contact: {hubspot_contact_id}")
            except Exception as e:
                logger.warning(f"Failed to auto-create HubSpot contact: {e}")
        
        # Create Lead object
        lead = Lead(**lead_data)
        
        # Create initial state with Phase 1 enhancements
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
            "retry_count": 0,
            # Phase 1: Enhanced state with intent data
            "intent_analysis": intent_analysis,
            "pattern_analysis": pattern_analysis,
            "high_intent_triggered": should_qualify.get('high_intent_triggered', False),
            "hubspot_contact_id": hubspot_contact_id,
            "phase_1_processing": True
        }
        
        # Create workflow
        workflow = create_workflow()
        
        # Configuration for thread persistence
        config = {
            "configurable": {
                "thread_id": lead.user_id
            }
        }
        
        # Process through workflow with enhanced tracking
        result = workflow.invoke(initial_state, config)
        
        # Store conversation history with Phase 1 data
        conversation_data = {
            "user_message": lead.message,
            "assistant_messages": [msg for msg in result.get("messages", []) if msg.get("role") == "assistant"],
            "timestamp": lead.created_at.isoformat(),
            "status": result["lead"].status,
            "score": result["lead"].qualified_score,
            # Phase 1: Store intent and filtering data
            "intent_analysis": intent_analysis,
            "high_intent_processed": should_qualify.get('high_intent_triggered', False),
            "hubspot_contact_created": bool(hubspot_contact_id),
            "filtering_applied": True
        }
        
        store_conversation_history(lead.user_id, conversation_data)
        
        # Update metrics with Phase 1 tracking
        metrics_collector.increment_counter("leads_processed")
        metrics_collector.increment_counter("high_intent_leads_processed")
        
        if result["lead"].qualified_score:
            metrics_collector.record_score("qualification_score", result["lead"].qualified_score)
        
        # Phase 1: Track intent-specific metrics
        if intent_analysis:
            metrics_collector.record_score("ai_intent_score", intent_analysis.get('intent_score', 0.0))
            metrics_collector.increment_counter(f"intent_category_{intent_analysis.get('intent_category', 'unknown')}")
        
        return {
            "success": True,
            "lead_id": result["lead"].id,
            "status": result["lead"].status,
            "qualified_score": result["lead"].qualified_score,
            "next_agent": result.get("next_agent"),
            "interrupt": result.get("interrupt", False),
            # Phase 1: Enhanced response data
            "phase_1_processing": True,
            "intent_analysis": intent_analysis,
            "high_intent_triggered": should_qualify.get('high_intent_triggered', False),
            "hubspot_contact_id": hubspot_contact_id,
            "filtering_reason": should_qualify['reason'],
            "ai_enhanced": True
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
        from backend.utils.redis_client import redis_client
        
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

async def process_lead_message(user_id: str, message: str, channel: str = "instagram", user_name: str = None) -> Dict[str, Any]:
    """
    Process incoming lead message through the PRD workflow.
    
    Args:
        user_id: Instagram user ID
        message: Message content
        channel: Channel source (instagram,  , etc.)
        user_name: Extracted user name for personalization
        
    Returns:
        Processing result with potential response message
    """
    try:
        print(f"🎯 PRD WORKFLOW: Starting lead processing for {user_id} via {channel}")
        
        # Extract user profile information
        if not user_name:
            from backend.agents.prd_compliant_workflow import extract_user_profile
            user_name = extract_user_profile(user_id)
        
        print(f"👤 User profile: {user_name}")
        print(f"📝 MESSAGE: '{message}' from {user_name}")
        
        # Create message data for processing
        message_data = {
            "sender_id": user_id,
            "username": user_name,
            "text": message,
            "channel": channel,
            "timestamp": str(__import__('datetime').datetime.now())
        }
        
        # Initialize or get the workflow state
        from backend.agents.prd_compliant_workflow import run_prd_workflow
        
        # Execute the PRD compliant workflow
        result = await run_prd_workflow(message_data)
        
        print(f"✅ Workflow completed: {result.get('status', 'unknown')}")
        
        if result.get("status") == "success":
            print(f"💬 RESPONSE: {result.get('response_message', 'No response generated')[:100]}...")
        
        return result
        
    except Exception as e:
        error_msg = f"Lead processing error: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Return error result that won't break the response flow
        return {
            "status": "error",
            "error": error_msg,
            "response_message": "I'm having trouble processing your request right now. Please try again later."
        }

if __name__ == "__main__":
    celery_app.start()