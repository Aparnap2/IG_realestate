"""
Celery Tasks for Reminder System

Implements async tasks for multi-touch reminder scheduling, confirmation tracking,
and last-chance alerts with channel preference optimization.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from backend.celery_app import celery_app
from backend.communication.multi_channel_manager import MultiChannelManager
from backend.booking.reminder_scheduler import ReminderScheduler
from backend.tools.calendar_integration import GoogleCalendarClient
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

# Initialize components
reminder_scheduler = ReminderScheduler()
multi_channel = MultiChannelManager()
calendar_client = GoogleCalendarClient()

@celery_app.task(bind=True, max_retries=3)
def send_reminder_24h(self, lead_id: str, event_id: str, slot_time_str: str):
    """
    Send 24-hour reminder for upcoming booking.

    Args:
        lead_id: Lead identifier
        event_id: Calendar event ID
        slot_time_str: ISO format slot time string
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Sending 24h reminder for lead {lead_id}, event {event_id}")

        # Send reminder message
        success = reminder_scheduler._send_reminder_message(
            lead_id=lead_id,
            event_id=event_id,
            reminder_type='24h',
            slot_time=slot_time
        )

        if success:
            audit_log_event("reminder_24h_sent", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })
        else:
            audit_log_event("reminder_24h_failed", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })

            # Retry on failure
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=300)  # Retry in 5 minutes

    except Exception as e:
        logger.error(f"Error in send_reminder_24h task: {e}")
        audit_log_event("reminder_24h_error", {
            "lead_id": lead_id,
            "event_id": event_id,
            "error": str(e),
            "task_id": self.request.id
        })

        # Retry on exception
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task(bind=True, max_retries=3)
def send_reminder_3h(self, lead_id: str, event_id: str, slot_time_str: str):
    """
    Send 3-hour reminder for upcoming booking.

    Args:
        lead_id: Lead identifier
        event_id: Calendar event ID
        slot_time_str: ISO format slot time string
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Sending 3h reminder for lead {lead_id}, event {event_id}")

        # Send reminder message
        success = reminder_scheduler._send_reminder_message(
            lead_id=lead_id,
            event_id=event_id,
            reminder_type='3h',
            slot_time=slot_time
        )

        if success:
            audit_log_event("reminder_3h_sent", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })
        else:
            audit_log_event("reminder_3h_failed", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })

            # Retry on failure
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=300)

    except Exception as e:
        logger.error(f"Error in send_reminder_3h task: {e}")
        audit_log_event("reminder_3h_error", {
            "lead_id": lead_id,
            "event_id": event_id,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task(bind=True, max_retries=3)
def send_reminder_30m(self, lead_id: str, event_id: str, slot_time_str: str):
    """
    Send 30-minute reminder for upcoming booking.

    Args:
        lead_id: Lead identifier
        event_id: Calendar event ID
        slot_time_str: ISO format slot time string
    """
    try:
        slot_time = datetime.fromisoformat(slot_time_str)

        logger.info(f"Sending 30m reminder for lead {lead_id}, event {event_id}")

        # Send reminder message
        success = reminder_scheduler._send_reminder_message(
            lead_id=lead_id,
            event_id=event_id,
            reminder_type='30m',
            slot_time=slot_time
        )

        if success:
            audit_log_event("reminder_30m_sent", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })
        else:
            audit_log_event("reminder_30m_failed", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time_str,
                "task_id": self.request.id
            })

            # Retry on failure
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=300)

    except Exception as e:
        logger.error(f"Error in send_reminder_30m task: {e}")
        audit_log_event("reminder_30m_error", {
            "lead_id": lead_id,
            "event_id": event_id,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task(bind=True, max_retries=2)
def check_confirmation_task(self, lead_id: str, event_id: str):
    """
    Check confirmation status and send last-chance reminder if needed.

    This task runs at T-60 minutes to check if the booking has been confirmed.
    If not confirmed, sends last-chance reminder and alerts.

    Args:
        lead_id: Lead identifier
        event_id: Calendar event ID
    """
    try:
        logger.info(f"Checking confirmation status for lead {lead_id}, event {event_id}")

        # Check if confirmed (look for confirmation in calendar event)
        # This is a simplified check - in production, would query calendar API
        schedule = reminder_scheduler._get_reminder_schedule(lead_id)

        is_confirmed = False
        if schedule and schedule.get('confirmed_at'):
            is_confirmed = True

        if is_confirmed:
            logger.info(f"Booking confirmed for lead {lead_id}")
            audit_log_event("confirmation_verified", {
                "lead_id": lead_id,
                "event_id": event_id,
                "confirmed_at": schedule['confirmed_at'],
                "task_id": self.request.id
            })
            return

        # Not confirmed - send last-chance reminder
        logger.warning(f"No confirmation received for lead {lead_id} - sending last chance")

        success = reminder_scheduler.send_last_chance_reminder(lead_id, event_id)

        audit_log_event("last_chance_reminder_triggered", {
            "lead_id": lead_id,
            "event_id": event_id,
            "reminder_sent": success,
            "task_id": self.request.id
        })

    except Exception as e:
        logger.error(f"Error in check_confirmation_task: {e}")
        audit_log_event("confirmation_check_error", {
            "lead_id": lead_id,
            "event_id": event_id,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=600)  # Retry in 10 minutes

@celery_app.task(bind=True, max_retries=3)
def process_confirmation_reply(self, lead_id: str, event_id: str, message: str):
    """
    Process a confirmation reply from a lead.

    Args:
        lead_id: Lead identifier
        event_id: Calendar event ID
        message: Reply message content
    """
    try:
        logger.info(f"Processing confirmation reply for lead {lead_id}")

        # Check if message indicates confirmation
        confirmation_keywords = ['yes', 'confirm', 'confirmed', 'see you', 'looking forward']
        message_lower = message.lower()

        is_confirmation = any(keyword in message_lower for keyword in confirmation_keywords)

        if is_confirmation:
            # Track confirmation
            confirmed_at = datetime.now()
            success = reminder_scheduler.track_confirmation(lead_id, event_id, confirmed_at)

            audit_log_event("confirmation_reply_processed", {
                "lead_id": lead_id,
                "event_id": event_id,
                "confirmed": True,
                "message": message[:100],  # Truncate for audit
                "tracking_success": success,
                "task_id": self.request.id
            })

            # Send confirmation acknowledgment
            try:
                confirmation_msg = "Great! Your booking is confirmed. We'll see you at the scheduled time. If you need to make any changes, just let us know."

                multi_channel.send_message(
                    user_id=lead_id,
                    message=confirmation_msg,
                    channel='auto',
                    priority='normal',
                    message_type='confirmation_ack'
                )
            except Exception as e:
                logger.warning(f"Failed to send confirmation acknowledgment: {e}")

        else:
            audit_log_event("non_confirmation_reply", {
                "lead_id": lead_id,
                "event_id": event_id,
                "message": message[:100],
                "task_id": self.request.id
            })

    except Exception as e:
        logger.error(f"Error processing confirmation reply: {e}")
        audit_log_event("confirmation_reply_error", {
            "lead_id": lead_id,
            "event_id": event_id,
            "error": str(e),
            "task_id": self.request.id
        })

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

@celery_app.task
def check_unconfirmed_bookings():
    """
    Periodic task to check for unconfirmed bookings and send alerts.

    Runs every 15 minutes to find bookings that should have confirmations
    but don't, indicating potential no-shows.
    """
    try:
        logger.info("Running periodic unconfirmed booking check")

        # This would query for bookings in the next few hours that haven't been confirmed
        # For now, this is a placeholder implementation

        # In production, this would:
        # 1. Query database for events in next 2 hours
        # 2. Check confirmation status in calendar metadata
        # 3. Send alerts for unconfirmed bookings
        # 4. Trigger backfill if configured

        audit_log_event("unconfirmed_check_completed", {
            "checked_count": 0,  # Placeholder
            "alerts_sent": 0
        })

    except Exception as e:
        logger.error(f"Error in check_unconfirmed_bookings task: {e}")
        audit_log_event("unconfirmed_check_error", {
            "error": str(e)
        })

@celery_app.task
def generate_weekly_digest():
    """
    Generate and send weekly performance digest.

    Runs every Monday at 9 AM to summarize booking performance metrics.
    """
    try:
        logger.info("Generating weekly booking digest")

        from backend.booking.observability_metrics import ObservabilityMetrics

        metrics = ObservabilityMetrics()
        result = metrics.generate_weekly_digest()

        audit_log_event("weekly_digest_task_completed", {
            "result": result
        })

    except Exception as e:
        logger.error(f"Error generating weekly digest: {e}")
        audit_log_event("weekly_digest_task_error", {
            "error": str(e)
        })
