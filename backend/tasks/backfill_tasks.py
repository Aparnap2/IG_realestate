"""
Celery Tasks for Waitlist Backfill System

Implements async tasks for waitlist backfill operations, candidate outreach,
and backfill attempt tracking with guardrail enforcement.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from backend.celery_app import celery_app
from backend.booking.waitlist_manager import WaitlistManager
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

# Initialize components
waitlist_manager = WaitlistManager()

@celery_app.task(bind=True, max_retries=2)
def trigger_waitlist_backfill(self, slot_time_str: str, service: str, location: str, reason: str = "no_show"):
    """
    Trigger waitlist backfill for a no-show slot.

    Args:
        slot_time_str: ISO format slot time string
        service: Service type
        location: Service location
        reason: Reason for backfill (no_show, cancellation, etc.)
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Triggering waitlist backfill for {slot_time} in {location} ({reason})")

        # Trigger backfill process
        result = waitlist_manager.trigger_backfill(slot_time, service, location)

        audit_log_event("backfill_trigger_task_completed", {
            "slot_time": slot_time_str,
            "service": service,
            "location": location,
            "reason": reason,
            "result": result,
            "task_id": self.request.id
        })

        # Log results
        if result.get('status') == 'backfill_attempted':
            logger.info(f"Backfill attempted: {result['attempts_made']} candidates contacted")

            # Check if we need to follow up on any attempts
            successful_backfills = sum(1 for r in result.get('results', [])
                                     if r.get('status') in ['accepted', 'offered'])

            if successful_backfills == 0:
                logger.warning(f"No successful backfills for {slot_time} - consider expanding criteria")

    except Exception as e:
        logger.error(f"Error in trigger_waitlist_backfill task: {e}")
        audit_log_event("backfill_trigger_task_error", {
            "slot_time": slot_time_str,
            "service": service,
            "location": location,
            "reason": reason,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Retry in 5 minutes

@celery_app.task(bind=True, max_retries=3)
def attempt_backfill_for_candidate(self, lead_id: str, slot_time_str: str):
    """
    Attempt backfill offer for a specific waitlist candidate.

    Args:
        lead_id: Candidate lead ID
        slot_time_str: ISO format slot time string
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Attempting backfill for candidate {lead_id} at {slot_time}")

        # Attempt backfill
        result = waitlist_manager.attempt_backfill_for_candidate(lead_id, slot_time)

        audit_log_event("backfill_attempt_task_completed", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "result": result,
            "task_id": self.request.id
        })

        # Handle different outcomes
        status = result.get('status')

        if status == 'accepted':
            logger.info(f"Backfill accepted by {lead_id}!")
            # Could trigger additional tasks here (confirmation, etc.)

        elif status == 'guardrail_failed':
            logger.debug(f"Backfill guardrails prevented outreach to {lead_id}")

        elif status == 'send_failed':
            logger.warning(f"Failed to send backfill offer to {lead_id}")
            # Could retry or mark for manual follow-up

        elif status == 'offered':
            logger.info(f"Backfill offer sent to {lead_id}, awaiting response")

    except Exception as e:
        logger.error(f"Error in attempt_backfill_for_candidate task: {e}")
        audit_log_event("backfill_attempt_task_error", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task(bind=True, max_retries=2)
def process_backfill_acceptance(self, lead_id: str, slot_time_str: str, message: str):
    """
    Process acceptance of a backfill offer.

    Args:
        lead_id: Lead who accepted the offer
        slot_time_str: ISO format slot time string
        message: Acceptance message content
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Processing backfill acceptance from {lead_id} for {slot_time}")

        # This would transition the lead to booking state machine
        # For now, just log and audit

        audit_log_event("backfill_acceptance_processed", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "message": message[:100],  # Truncate for audit
            "task_id": self.request.id
        })

        # In production, this would:
        # 1. Create booking attempt with idempotency key
        # 2. Write to calendar
        # 3. Schedule reminders
        # 4. Update waitlist status

        # Send confirmation message
        try:
            from backend.communication.multi_channel_manager import MultiChannelManager
            multi_channel = MultiChannelManager()

            confirmation_msg = f"Perfect! Your booking has been confirmed for {slot_time.strftime('%A, %B %d at %I:%M %p')}. We'll send you all the details shortly."

            multi_channel.send_message(
                user_id=lead_id,
                message=confirmation_msg,
                channel='auto',
                priority='high',
                message_type='backfill_confirmation'
            )

        except Exception as e:
            logger.warning(f"Failed to send backfill confirmation: {e}")

    except Exception as e:
        logger.error(f"Error processing backfill acceptance: {e}")
        audit_log_event("backfill_acceptance_error", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task
def cleanup_expired_backfill_attempts():
    """
    Clean up expired backfill attempts and reset candidate counters.

    Runs daily to maintain waitlist health and prevent permanent blocking.
    """
    try:
        logger.info("Cleaning up expired backfill attempts")

        # This would:
        # 1. Find backfill attempts older than X days
        # 2. Reset attempt counters for candidates
        # 3. Clean up expired backfill state data

        # Placeholder implementation
        audit_log_event("backfill_cleanup_completed", {
            "expired_attempts_cleaned": 0,  # Placeholder
            "counters_reset": 0
        })

    except Exception as e:
        logger.error(f"Error in backfill cleanup task: {e}")
        audit_log_event("backfill_cleanup_error", {
            "error": str(e)
        })

@celery_app.task(bind=True, max_retries=2)
def retry_failed_backfill_outreach(self, lead_id: str, slot_time_str: str, attempt_count: int = 1):
    """
    Retry failed backfill outreach attempts.

    Args:
        lead_id: Lead to retry outreach for
        slot_time_str: ISO format slot time string
        attempt_count: Current attempt count
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Retrying backfill outreach for {lead_id} (attempt {attempt_count})")

        # Check if we should still attempt (guardrails)
        max_attempts = 3  # Could be configurable
        if attempt_count >= max_attempts:
            logger.warning(f"Max retry attempts reached for {lead_id}")
            audit_log_event("backfill_retry_exhausted", {
                "lead_id": lead_id,
                "slot_time": slot_time_str,
                "final_attempt": attempt_count,
                "task_id": self.request.id
            })
            return

        # Attempt the outreach again
        result = waitlist_manager.attempt_backfill_for_candidate(lead_id, slot_time)

        audit_log_event("backfill_retry_attempted", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "attempt_count": attempt_count,
            "result": result,
            "task_id": self.request.id
        })

        # If still failed, schedule another retry
        if result.get('status') == 'send_failed' and attempt_count < max_attempts:
            retry_eta = datetime.now() + timedelta(hours=1)  # Retry in 1 hour
            retry_failed_backfill_outreach.apply_async(
                args=[lead_id, slot_time_str, attempt_count + 1],
                eta=retry_eta
            )

    except Exception as e:
        logger.error(f"Error in retry backfill outreach: {e}")
        audit_log_event("backfill_retry_error", {
            "lead_id": lead_id,
            "slot_time": slot_time_str,
            "attempt_count": attempt_count,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=600)  # Retry in 10 minutes

@celery_app.task
def analyze_backfill_performance():
    """
    Analyze backfill performance and suggest improvements.

    Runs weekly to analyze backfill success rates, timing, and candidate quality.
    """
    try:
        logger.info("Analyzing backfill performance")

        # This would:
        # 1. Query backfill attempt data
        # 2. Calculate success rates by time of day, day of week
        # 3. Analyze candidate response times
        # 4. Suggest optimal backfill timing and criteria

        # Placeholder analysis
        analysis = {
            "total_backfills": 0,
            "success_rate": 0.0,
            "avg_response_time": 0,
            "best_times": [],
            "recommendations": []
        }

        audit_log_event("backfill_performance_analyzed", {
            "analysis": analysis
        })

    except Exception as e:
        logger.error(f"Error analyzing backfill performance: {e}")
        audit_log_event("backfill_performance_analysis_error", {
            "error": str(e)
        })
