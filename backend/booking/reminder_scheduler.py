"""
Multi-Touch Reminder Scheduler for Self-Driving Booking Ops 2.0

Implements T-24h, T-3h, T-30m reminder cadence with confirmation tracking,
channel preference optimization, and Slack alerting for no-shows.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.celery_app import celery_app
from backend.communication.multi_channel_manager import MultiChannelManager
from backend.tools.calendar_integration import GoogleCalendarClient
from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

# Reminder templates for different channels and types
REMINDER_TEMPLATES = {
    "24h": {
        "sms": "Hi! Just confirming your tour at {time}. Reply 'CONFIRM' or call us at (555) 123-4567 if you need to reschedule.",
        "email": "Hi there,\n\nThis is a friendly reminder about your scheduled tour at {time}.\n\nPlease reply to this email or call (555) 123-4567 if you need to make any changes.\n\nWe're looking forward to showing you around!\n\nBest regards,\nYour Real Estate Team",
        "dm": "👋 Hi! Just checking in about your tour scheduled for {time}. Everything still good? Let us know if you need to reschedule! 🏡"
    },
    "3h": {
        "sms": "Reminder: Your tour is in 3 hours at {time}. See you soon!",
        "email": "Subject: Your tour is coming up in 3 hours!\n\nHi,\n\nJust a quick reminder that your tour is scheduled for {time} (in about 3 hours).\n\nWe'll meet you at the property. If you have any questions, feel free to reply to this email.\n\nSafe travels!\n\nBest,\nYour Real Estate Team",
        "dm": "⏰ Quick reminder: Your tour is in 3 hours at {time}! Can't wait to show you around. 🏠"
    },
    "30m": {
        "sms": "Your tour starts in 30 minutes at {time}. We're excited to meet you!",
        "email": "Subject: Your tour starts in 30 minutes!\n\nHi,\n\nYour tour is scheduled to begin in 30 minutes at {time}.\n\nPlease arrive a few minutes early. If you're running late or need to reschedule, please call (555) 123-4567 immediately.\n\nSee you soon!\n\nBest,\nYour Real Estate Team",
        "dm": "🚗 Your tour starts in 30 minutes at {time}! We're getting everything ready for you. See you soon! 😊"
    },
    "last_chance": {
        "sms": "FINAL REMINDER: Your tour is in 1 hour. If you can't make it, reply 'CANCEL' or we'll assume you're on your way.",
        "email": "Subject: FINAL REMINDER: Your tour is in 1 hour\n\nHi,\n\nThis is your final reminder that your tour is scheduled for {time} (in about 1 hour).\n\nIf you need to reschedule or cancel, please reply to this email or call (555) 123-4567 immediately.\n\nWe hope to see you soon!\n\nBest,\nYour Real Estate Team",
        "dm": "⚠️ FINAL REMINDER: Your tour is in 1 hour at {time}. If you can't make it, let us know now so we can help someone else! ⏰"
    }
}

class ReminderScheduler:
    """
    Multi-touch reminder scheduler with confirmation tracking and channel optimization.
    
    Schedules T-24h, T-3h, T-30m reminders and tracks confirmations via calendar metadata.
    Handles channel preferences and sends Slack alerts for no-show predictions.
    """

    def __init__(self):
        self.multi_channel = MultiChannelManager()
        self.calendar_client = GoogleCalendarClient()
        self.redis_client = redis_client

    def schedule_reminders(
        self,
        event_id: str,
        lead_id: str,
        slot_time: datetime,
        channel_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Schedule multi-touch reminders for a confirmed booking.
        
        Args:
            event_id: Google Calendar event ID
            lead_id: Lead identifier
            slot_time: Tour/appointment time
            channel_preferences: Preferred channels for this lead
            
        Returns:
            Dict with scheduling status and task IDs
        """
        try:
            # Calculate reminder times
            reminder_times = {
                '24h': slot_time - timedelta(hours=24),
                '3h': slot_time - timedelta(hours=3),
                '30m': slot_time - timedelta(minutes=30),
                '60m': slot_time - timedelta(minutes=60)  # For last-chance check
            }

            # Schedule Celery tasks
            tasks = {}

            # T-24h reminder
            if reminder_times['24h'] > datetime.now():
                task_24h = send_reminder_24h.apply_async(
                    args=[lead_id, event_id, slot_time.isoformat()],
                    eta=reminder_times['24h']
                )
                tasks['24h'] = task_24h.id

            # T-3h reminder
            if reminder_times['3h'] > datetime.now():
                task_3h = send_reminder_3h.apply_async(
                    args=[lead_id, event_id, slot_time.isoformat()],
                    eta=reminder_times['3h']
                )
                tasks['3h'] = task_3h.id

            # T-30m reminder
            if reminder_times['30m'] > datetime.now():
                task_30m = send_reminder_30m.apply_async(
                    args=[lead_id, event_id, slot_time.isoformat()],
                    eta=reminder_times['30m']
                )
                tasks['30m'] = task_30m.id

            # Store reminder schedule in Redis
            self._store_reminder_schedule(lead_id, {
                'event_id': event_id,
                'slot_time': slot_time.isoformat(),
                'reminder_24h_sent': False,
                'reminder_3h_sent': False,
                'reminder_30m_sent': False,
                'confirmed_at': None,
                'last_chance_sent': False,
                'task_ids': tasks
            })

            audit_log_event("reminders_scheduled", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time.isoformat(),
                "tasks_scheduled": len(tasks)
            })

            return {
                "status": "scheduled",
                "lead_id": lead_id,
                "event_id": event_id,
                "tasks": tasks,
                "reminder_times": {k: v.isoformat() for k, v in reminder_times.items()}
            }

        except Exception as e:
            logger.error(f"Error scheduling reminders for {lead_id}: {e}")
            audit_log_event("reminder_scheduling_error", {
                "lead_id": lead_id,
                "event_id": event_id,
                "error": str(e)
            })
            return {
                "status": "error",
                "error": str(e)
            }

    def track_confirmation(self, lead_id: str, event_id: str, confirmed_at: datetime) -> bool:
        """
        Track user confirmation of attendance.
        
        Args:
            lead_id: Lead identifier
            event_id: Calendar event ID
            confirmed_at: When confirmation was received
            
        Returns:
            True if successfully tracked, False otherwise
        """
        try:
            # Update calendar event metadata
            success = self.calendar_client.update_event_metadata(event_id, {
                'confirmed_at': confirmed_at.isoformat(),
                'confirmation_method': 'reminder_response'
            })

            if success:
                # Update Redis tracking
                self._update_reminder_status(lead_id, {
                    'confirmed_at': confirmed_at.isoformat()
                })

                audit_log_event("confirmation_tracked", {
                    "lead_id": lead_id,
                    "event_id": event_id,
                    "confirmed_at": confirmed_at.isoformat()
                })

            return success

        except Exception as e:
            logger.error(f"Error tracking confirmation for {lead_id}: {e}")
            return False

    def check_confirmation_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if event has been confirmed by attendee.
        
        Args:
            event_id: Calendar event ID
            
        Returns:
            Dict with confirmation status or None if not found
        """
        try:
            # Get event details from calendar
            event = self.calendar_client.get_event_by_idempotency_key(None)  # Would need to implement this
            # For now, check Redis tracking
            # This is a placeholder - would need proper calendar integration

            return None  # Placeholder

        except Exception as e:
            logger.error(f"Error checking confirmation status for {event_id}: {e}")
            return None

    def send_last_chance_reminder(self, lead_id: str, event_id: str) -> bool:
        """
        Send last-chance reminder and Slack alert for potential no-show.
        
        Args:
            lead_id: Lead identifier
            event_id: Calendar event ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get reminder schedule
            schedule = self._get_reminder_schedule(lead_id)
            if not schedule:
                logger.warning(f"No reminder schedule found for {lead_id}")
                return False

            slot_time = datetime.fromisoformat(schedule['slot_time'])

            # Send last-chance reminder
            self._send_reminder_message(
                lead_id=lead_id,
                event_id=event_id,
                reminder_type='last_chance',
                slot_time=slot_time
            )

            # Send Slack alert
            self._send_slack_alert({
                "alert_type": "no_show_prediction",
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time.isoformat(),
                "last_reminder_sent": datetime.now().isoformat()
            })

            # Mark as no-show predicted
            self._update_reminder_status(lead_id, {
                'last_chance_sent': True,
                'no_show_predicted': True
            })

            audit_log_event("last_chance_reminder_sent", {
                "lead_id": lead_id,
                "event_id": event_id,
                "slot_time": slot_time.isoformat()
            })

            return True

        except Exception as e:
            logger.error(f"Error sending last-chance reminder for {lead_id}: {e}")
            return False

    def _send_reminder_message(
        self,
        lead_id: str,
        event_id: str,
        reminder_type: str,
        slot_time: datetime
    ) -> bool:
        """Send reminder message via optimal channel."""
        try:
            # Get user preferences for channel selection
            user_prefs = self.multi_channel.get_user_preferences(lead_id)

            # Determine optimal channel (SMS > Email > DM priority for reminders)
            channel_priority = ['sms', 'email', 'dm']
            selected_channel = None

            for channel in channel_priority:
                if channel == 'sms' and user_prefs.preferred_channel.value == 'sms':
                    selected_channel = 'sms'
                    break
                elif channel == 'email':
                    selected_channel = 'email'
                    break
                elif channel == 'dm' and 'instagram' in user_prefs.preferred_channel.value:
                    selected_channel = 'dm'
                    break

            if not selected_channel:
                selected_channel = 'dm'  # Default fallback

            # Get template
            template = REMINDER_TEMPLATES.get(reminder_type, {}).get(selected_channel)
            if not template:
                logger.warning(f"No template found for {reminder_type} on {selected_channel}")
                return False

            # Format message
            formatted_time = slot_time.strftime("%I:%M %p on %A, %B %d")
            message = template.format(time=formatted_time)

            # Send message
            result = self.multi_channel.send_message(
                user_id=lead_id,
                message=message,
                channel=selected_channel,
                priority='high',
                message_type='booking_reminder'
            )

            # Track reminder sent
            reminder_key = f"reminder_{reminder_type}_sent"
            self._update_reminder_status(lead_id, {reminder_key: True})

            return result.get('success', False)

        except Exception as e:
            logger.error(f"Error sending reminder message: {e}")
            return False

    def _store_reminder_schedule(self, lead_id: str, schedule: Dict[str, Any]) -> bool:
        """Store reminder schedule in Redis."""
        if self.redis_client is None:
            return False

        def _store_operation():
            key = f"reminder_schedule:{lead_id}"
            self.redis_client.setex(key, 604800, json.dumps(schedule, default=str))  # 7 days
            return True

        try:
            return redis_circuit_breaker.call(_store_operation)
        except Exception as e:
            logger.warning(f"Error storing reminder schedule for {lead_id}: {e}")
            return False

    def _get_reminder_schedule(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get reminder schedule from Redis."""
        if self.redis_client is None:
            return None

        def _get_operation():
            key = f"reminder_schedule:{lead_id}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None

        try:
            return redis_circuit_breaker.call(_get_operation)
        except Exception as e:
            logger.warning(f"Error getting reminder schedule for {lead_id}: {e}")
            return None

    def _update_reminder_status(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Update reminder status in Redis."""
        schedule = self._get_reminder_schedule(lead_id)
        if not schedule:
            return False

        schedule.update(updates)
        return self._store_reminder_schedule(lead_id, schedule)

    def _send_slack_alert(self, alert_data: Dict[str, Any]) -> None:
        """Send Slack alert for booking issues."""
        try:
            import requests
            import os

            webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            if not webhook_url:
                logger.warning("SLACK_WEBHOOK_URL not configured")
                return

            message = {
                "text": f"🚨 Booking Alert: {alert_data['alert_type']}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Booking Alert: {alert_data['alert_type']}*\\n"
                                   f"Lead: {alert_data['lead_id']}\\n"
                                   f"Event: {alert_data['event_id']}\\n"
                                   f"Time: {alert_data['slot_time']}"
                        }
                    }
                ]
            }

            requests.post(webhook_url, json=message, timeout=10)

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")


# Celery task definitions
@celery_app.task
def send_reminder_24h(lead_id: str, event_id: str, slot_time_str: str):
    """Send 24-hour reminder."""
    scheduler = ReminderScheduler()
    slot_time = datetime.fromisoformat(slot_time_str)
    scheduler._send_reminder_message(lead_id, event_id, '24h', slot_time)

@celery_app.task
def send_reminder_3h(lead_id: str, event_id: str, slot_time_str: str):
    """Send 3-hour reminder."""
    scheduler = ReminderScheduler()
    slot_time = datetime.fromisoformat(slot_time_str)
    scheduler._send_reminder_message(lead_id, event_id, '3h', slot_time)

@celery_app.task
def send_reminder_30m(lead_id: str, event_id: str, slot_time_str: str):
    """Send 30-minute reminder."""
    scheduler = ReminderScheduler()
    slot_time = datetime.fromisoformat(slot_time_str)
    scheduler._send_reminder_message(lead_id, event_id, '30m', slot_time)

@celery_app.task
def check_confirmation_task(lead_id: str, event_id: str):
    """Check confirmation status and send last-chance if needed."""
    scheduler = ReminderScheduler()

    # Check if confirmed
    schedule = scheduler._get_reminder_schedule(lead_id)
    if schedule and schedule.get('confirmed_at'):
        return  # Already confirmed

    # Send last-chance reminder
    scheduler.send_last_chance_reminder(lead_id, event_id)
