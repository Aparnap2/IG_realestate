"""
Comment Intake Processing for Instagram Comment-Triggered DM Funnel.

This module processes comment events from Instagram webhooks, validates trigger keywords,
creates or updates lead records, and initiates the DM warm-up sequence.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from celery import Celery

# CRITICAL FIX: Standardized import path setup
# Add parent directory to Python path for proper imports when running from backend dir
import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(backend_dir)  # Add parent directory so backend module can be found
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.celery_app import celery_app
from backend.utils.supabase_client import supabase, save_lead
from backend.utils.audit import audit_log_event
from backend.utils.redis_client import set_conversation_state, get_conversation_state
from backend.tools.agent_tools import send_instagram_message, fetch_lead_magnet
from backend.models.lead import Lead

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def process_comment_task(self, comment_event: Dict[str, Any]):
    """
    Celery task to process Instagram comment events and initiate DM funnel.
    
    Args:
        comment_event: Dictionary containing comment data from webhook
        
    Returns:
        Processing result with status and details
    """
    try:
        logger.info(f"Processing comment event: {comment_event.get('comment_id')}")
        
        # Extract comment data
        commenter_id = comment_event.get("commenter_id")
        comment_text = comment_event.get("comment_text", "")
        post_id = comment_event.get("post_id")
        ig_account_id = comment_event.get("ig_account_id")
        
        if not commenter_id:
            logger.error("Missing commenter_id in comment event")
            return {"status": "error", "error": "Missing commenter_id"}
        
        # Check if lead already exists
        existing_lead = get_existing_lead(commenter_id)
        
        # Create or update lead record
        lead = create_or_update_lead(comment_event, existing_lead)
        
        if not lead:
            logger.error(f"Failed to create/update lead for commenter: {commenter_id}")
            return {"status": "error", "error": "Lead creation failed"}
        
        # Initialize conversation state in Redis
        conversation_state = initialize_conversation_state(lead, comment_event)
        
        # Send initial DM message
        dm_result = send_initial_warmup_message(lead, comment_event)
        
        if not dm_result:
            logger.error(f"Failed to send initial DM to lead: {lead.id}")
            return {"status": "error", "error": "DM sending failed"}
        
        # Update lead with warm-up initiation
        update_lead_warmup_status(lead.id)
        
        # Log successful processing
        audit_log_event("comment_warmup_initiated", {
            "lead_id": lead.id,
            "comment_id": comment_event.get("comment_id"),
            "commenter_id": commenter_id,
            "post_id": post_id,
            "ig_account_id": ig_account_id,
            "comment_text": comment_text,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Successfully initiated warm-up for lead: {lead.id}")
        
        return {
            "status": "success",
            "lead_id": lead.id,
            "commenter_id": commenter_id,
            "dm_sent": True,
            "conversation_state": conversation_state
        }
        
    except Exception as e:
        logger.error(f"Error processing comment task: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(f"Retrying comment processing in {countdown} seconds")
            raise self.retry(countdown=countdown, exc=e)
        
        # Log final failure
        audit_log_event("comment_processing_failed", {
            "comment_id": comment_event.get("comment_id"),
            "error": str(e),
            "retries": self.request.retries,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "status": "error",
            "error": str(e),
            "retries": self.request.retries
        }

def get_existing_lead(commenter_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if lead already exists for this Instagram user.
    
    Args:
        commenter_id: Instagram user ID (PSID)
        
    Returns:
        Existing lead data or None if not found
    """
    try:
        response = supabase.table("leads").select("*").eq("user_id", commenter_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking existing lead: {e}")
        return None

def create_or_update_lead(comment_event: Dict[str, Any], existing_lead: Optional[Dict[str, Any]]) -> Optional[Lead]:
    """
    Create new lead or update existing lead with comment data.
    
    Args:
        comment_event: Comment event data
        existing_lead: Existing lead data if found
        
    Returns:
        Lead object or None if failed
    """
    try:
        commenter_id = comment_event.get("commenter_id")
        commenter_name = comment_event.get("commenter_name", "")
        commenter_username = comment_event.get("commenter_username", "")
        comment_text = comment_event.get("comment_text", "")
        post_id = comment_event.get("post_id")
        
        # Determine lead name
        lead_name = commenter_name or commenter_username or "Instagram User"
        
        if existing_lead:
            # Update existing lead
            lead_data = {
                "id": existing_lead["id"],
                "message": comment_text,  # Update with latest comment
                "last_interaction_at": datetime.now(),
                "status": "warmup",  # Set to warmup status
                "history": existing_lead.get("history", [])
            }
            
            # Add history entry
            lead_data["history"].append({
                "message": f"Comment trigger: {comment_text}",
                "timestamp": datetime.now().isoformat(),
                "agent": "comment_webhook",
                "details": {
                    "post_id": post_id,
                    "comment_id": comment_event.get("comment_id")
                }
            })
            
            # Update in database
            response = supabase.table("leads").update(lead_data).eq("id", existing_lead["id"]).execute()
            
            if response.data:
                logger.info(f"Updated existing lead: {existing_lead['id']}")
                return Lead(**response.data[0])
            
        else:
            # Create new lead
            lead_data = {
                "channel": "ig",
                "user_id": commenter_id,
                "message": comment_text,
                "name": lead_name,
                "status": "warmup",
                "qualified_score": 0.1,  # Initial low score for comment-triggered leads
                "history": [{
                    "message": f"Comment trigger: {comment_text}",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "comment_webhook",
                    "details": {
                        "post_id": post_id,
                        "comment_id": comment_event.get("comment_id")
                    }
                }],
                "created_at": datetime.now(),
                "last_interaction_at": datetime.now()
            }
            
            # Save to database
            saved_lead = save_lead(lead_data)
            
            if saved_lead:
                logger.info(f"Created new lead: {saved_lead.get('id')}")
                return Lead(**saved_lead)
        
        return None
        
    except Exception as e:
        logger.error(f"Error creating/updating lead: {e}")
        return None

def initialize_conversation_state(lead: Lead, comment_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize conversation state in Redis for warm-up sequence.
    
    Args:
        lead: Lead object
        comment_event: Comment event data
        
    Returns:
        Conversation state dictionary
    """
    try:
        conversation_state = {
            "lead_id": lead.id,
            "user_id": lead.user_id,
            "stage": "warmup",
            "current_step": "initial_contact",
            "trigger_comment": comment_event.get("comment_text", ""),
            "post_id": comment_event.get("post_id"),
            "comment_id": comment_event.get("comment_id"),
            "lead_magnet_sent": False,
            "qualification_started": False,
            "asked_questions": set(),  # Track questions to prevent repeats
            "last_question_sent": None,
            "conversation_start": datetime.now().isoformat(),
            "last_interaction": datetime.now().isoformat()
        }
        
        # Store in Redis with 24-hour TTL
        set_conversation_state(lead.user_id, conversation_state, ttl=86400)
        
        logger.info(f"Initialized conversation state for lead: {lead.id}")
        return conversation_state
        
    except Exception as e:
        logger.error(f"Error initializing conversation state: {e}")
        return {}

def send_initial_warmup_message(lead: Lead, comment_event: Dict[str, Any]) -> bool:
    """
    Send initial warm-up DM message to lead.
    
    Args:
        lead: Lead object
        comment_event: Comment event data
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        # Personalized initial message based on comment
        commenter_name = lead.name or "there"
        post_id = comment_event.get("post_id", "")
        
        # Craft personalized message
        initial_message = f"""Hey {commenter_name}! 👋 Thanks for your comment on our post!

I saw you're interested in more information. I'd be happy to help you find your perfect property.

I have a free guide: "5 Essential Tips for First-Time Home Buyers" that I think you'll find valuable.

Would you like me to send you the free guide? It's packed with insider tips that could save you thousands! 📚💰

Just reply "guide" and I'll send it right over!"""

        # Send message via Instagram
        message_sent = send_instagram_message(lead.user_id, initial_message)
        
        if message_sent:
            logger.info(f"Sent initial warm-up message to lead: {lead.id}")
            
            # Update conversation history
            lead.add_history_entry(
                message=initial_message,
                agent="warmup_agent",
                details="Initial warm-up message with lead magnet offer"
            )
            
            return True
        else:
            logger.error(f"Failed to send initial message to lead: {lead.id}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending initial warm-up message: {e}")
        return False

def update_lead_warmup_status(lead_id: str) -> bool:
    """
    Update lead record with warm-up initiation status.
    
    Args:
        lead_id: Lead ID to update
        
    Returns:
        True if update successful, False otherwise
    """
    try:
        update_data = {
            "status": "warmup",
            "last_dm_sent": datetime.now(),
            "qualification_stage": "warmup_initial"
        }
        
        response = supabase.table("leads").update(update_data).eq("id", lead_id).execute()
        
        if response.data:
            logger.info(f"Updated warm-up status for lead: {lead_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error updating lead warm-up status: {e}")
        return False

def process_comment_event(comment_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process comment event directly (non-async version for testing).
    
    Args:
        comment_event: Comment event data
        
    Returns:
        Processing result
    """
    # Create a mock Celery task for direct processing
    class MockTask:
        def __init__(self):
            self.request = MockRequest()
            self.max_retries = 3
    
    class MockRequest:
        def __init__(self):
            self.retries = 0
    
    mock_task = MockTask()
    return process_comment_task(mock_task, comment_event)