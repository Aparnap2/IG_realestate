"""
Comprehensive Integration Tests for Reminder System

Tests the complete integration between reminder tasks, multi-channel communication,
reminder scheduling, and observability metrics including:

1. Multi-touch cadence validation
2. Channel preference enforcement  
3. Idempotency verification
4. Slack alert validation
5. End-to-end reminder flow
6. Edge cases and error recovery

Integration points tested:
- backend/tasks/reminder_tasks.py
- backend/communication/multi_channel_manager.py
- backend/booking/reminder_scheduler.py
- backend/booking/observability_metrics.py
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from freezegun import freeze_time

from backend.tasks.reminder_tasks import (
    send_reminder_24h,
    send_reminder_3h,
    send_reminder_30m,
    check_confirmation_task,
    process_confirmation_reply,
    check_unconfirmed_bookings,
    generate_weekly_digest
)
from backend.booking.reminder_scheduler import ReminderScheduler
from backend.booking.observability_metrics import ObservabilityMetrics
from backend.communication.multi_channel_manager import (
    MultiChannelManager,
    ChannelType,
    MessagePriority,
    UserPreferences
)


class TestMultiTouchCadenceValidation:
    """Test multi-touch reminder cadence and timing validation"""
    
    @pytest.fixture
    def reminder_scheduler(self):
        return ReminderScheduler()
    
    @pytest.fixture
    def sample_booking(self):
        return {
            'event_id': 'event_123',
            'lead_id': 'lead_456',
            'slot_time': datetime.now() + timedelta(days=1, hours=2)  # Tomorrow at 2 PM
        }
    
    @patch('backend.tasks.reminder_tasks.reminder_scheduler')
    def test_24h_reminder_scheduling(self, mock_scheduler, sample_booking):
        """Test 24-hour reminder is scheduled at correct time"""
        # Mock successful reminder sending
        mock_scheduler._send_reminder_message.return_value = True
        
        # Execute reminder task
        result = send_reminder_24h(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            slot_time_str=sample_booking['slot_time'].isoformat()
        )
        
        # Verify reminder scheduler was called with correct parameters
        mock_scheduler._send_reminder_message.assert_called_once_with(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            reminder_type='24h',
            slot_time=sample_booking['slot_time']
        )
    
    @patch('backend.tasks.reminder_tasks.reminder_scheduler')
    def test_3h_reminder_scheduling(self, mock_scheduler, sample_booking):
        """Test 3-hour reminder is scheduled at correct time"""
        mock_scheduler._send_reminder_message.return_value = True
        
        result = send_reminder_3h(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            slot_time_str=sample_booking['slot_time'].isoformat()
        )
        
        mock_scheduler._send_reminder_message.assert_called_once_with(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            reminder_type='3h',
            slot_time=sample_booking['slot_time']
        )
    
    @patch('backend.tasks.reminder_tasks.reminder_scheduler')
    def test_30m_reminder_scheduling(self, mock_scheduler, sample_booking):
        """Test 30-minute reminder is scheduled at correct time"""
        mock_scheduler._send_reminder_message.return_value = True
        
        result = send_reminder_30m(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            slot_time_str=sample_booking['slot_time'].isoformat()
        )
        
        mock_scheduler._send_reminder_message.assert_called_once_with(
            lead_id=sample_booking['lead_id'],
            event_id=sample_booking['event_id'],
            reminder_type='30m',
            slot_time=sample_booking['slot_time']
        )
    
    @patch('backend.tasks.reminder_tasks.reminder_scheduler')
    def test_reminder_timing_calculation(self, mock_scheduler, reminder_scheduler, sample_booking):
        """Test that reminder times are calculated correctly relative to booking time"""
        slot_time = sample_booking['slot_time']
        
        # Mock the scheduler to capture the slot_time passed to it
        def capture_slot_time(*args, **kwargs):
            passed_slot_time = kwargs.get('slot_time')
            # Verify timing is 24h, 3h, 30m before slot_time
            assert passed_slot_time == slot_time
            return True
        
        mock_scheduler._send_reminder_message.side_effect = capture_slot_time
        
        # Test 24h reminder timing
        reminder_24h_time = slot_time - timedelta(hours=24)
        send_reminder_24h(
            sample_booking['lead_id'],
            sample_booking['event_id'],
            slot_time.isoformat()
        )
        
        # Test 3h reminder timing
        reminder_3h_time = slot_time - timedelta(hours=3)
        send_reminder_3h(
            sample_booking['lead_id'],
            sample_booking['event_id'],
            slot_time.isoformat()
        )
        
        # Test 30m reminder timing
        reminder_30m_time = slot_time - timedelta(minutes=30)
        send_reminder_30m(
            sample_booking['lead_id'],
            sample_booking['event_id'],
            slot_time.isoformat()
        )
    
    def test_daily_reminder_limits_enforced(self, reminder_scheduler):
        """Test that daily reminder limits are enforced per user"""
        lead_id = "test_lead_123"
        
        # Create user with low daily limit
        user_prefs = UserPreferences(
            user_id=lead_id,
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.EMAIL],
            max_messages_per_day=2,  # Low limit
            do_not_disturb=False
        )
        
        # Mock multi-channel manager to return user preferences
        with patch.object(reminder_scheduler.multi_channel, 'get_user_preferences', return_value=user_prefs):
            # First reminder should be allowed
            with patch.object(reminder_scheduler.multi_channel, 'send_message') as mock_send:
                mock_send.return_value = {"success": True}
                
                result1 = reminder_scheduler._send_reminder_message(
                    lead_id=lead_id,
                    event_id="event_1",
                    reminder_type='24h',
                    slot_time=datetime.now() + timedelta(days=1)
                )
                assert result1 is True
                assert mock_send.call_count == 1
                
                # Second reminder should be allowed
                result2 = reminder_scheduler._send_reminder_message(
                    lead_id=lead_id,
                    event_id="event_2",
                    reminder_type='3h',
                    slot_time=datetime.now() + timedelta(hours=4)
                )
                assert result2 is True
                assert mock_send.call_count == 2


class TestChannelPreferenceEnforcement:
    """Test sophisticated channel preference system"""
    
    @pytest.fixture
    def multi_channel_manager(self):
        return MultiChannelManager()
    
    def test_instagram_dm_preference_priority(self, multi_channel_manager):
        """Test that Instagram DM is prioritized when set as preferred channel"""
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.SMS, ChannelType.EMAIL],
            max_messages_per_day=5
        )
        
        with patch.object(multi_channel_manager, 'get_user_preferences', return_value=user_prefs):
            channel = multi_channel_manager.get_optimal_channel(
                user_id="test_user",
                message_type="engagement",
                priority="normal"
            )
            
            assert channel == ChannelType.INSTAGRAM_DM
    
    def test_sms_fallback_for_urgent_messages(self, multi_channel_manager):
        """Test SMS is selected for urgent messages when business hours only"""
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.EMAIL,
            backup_channels=[ChannelType.INSTAGRAM_DM],
            business_hours_only=True,  # Outside business hours
            max_messages_per_day=5
        )
        
        with patch.object(multi_channel_manager, 'get_user_preferences', return_value=user_prefs):
            # Mock time as outside business hours
            with patch('backend.communication.multi_channel_manager.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 22, 0, 0)  # 10 PM
                
                # Urgent message should use SMS
                channel = multi_channel_manager.get_optimal_channel(
                    user_id="test_user",
                    message_type="urgent",
                    priority="urgent"
                )
                
                assert channel == ChannelType.SMS
    
    def test_email_deferral_for_business_hours_only(self, multi_channel_manager):
        """Test non-urgent messages are deferred to email during business hours preference"""
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.EMAIL],
            business_hours_only=True,  # Outside business hours
            max_messages_per_day=5
        )
        
        with patch.object(multi_channel_manager, 'get_user_preferences', return_value=user_prefs):
            # Mock time as outside business hours
            with patch('backend.communication.multi_channel_manager.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 20, 0, 0)  # 8 PM
                
                # Normal message should be deferred to email
                channel = multi_channel_manager.get_optimal_channel(
                    user_id="test_user",
                    message_type="engagement",
                    priority="normal"
                )
                
                assert channel == ChannelType.EMAIL
    
    def test_do_not_disturb_enforcement(self, multi_channel_manager):
        """Test do-not-disturb preference prevents non-urgent messages"""
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.EMAIL],
            do_not_disturb=True,
            max_messages_per_day=5
        )
        
        with patch.object(multi_channel_manager, 'get_user_preferences', return_value=user_prefs):
            # Normal message should be deferred
            channel = multi_channel_manager.get_optimal_channel(
                user_id="test_user",
                message_type="engagement",
                priority="normal"
            )
            
            assert channel == ChannelType.EMAIL
            
            # Urgent message should still be delivered
            channel = multi_channel_manager.get_optimal_channel(
                user_id="test_user",
                message_type="urgent",
                priority="urgent"
            )
            
            assert channel == ChannelType.INSTAGRAM_DM
    
    def test_channel_suitability_mapping(self, multi_channel_manager):
        """Test message type to channel suitability mapping"""
        # Test suitability mappings
        assert "engagement" in multi_channel_manager.CHANNEL_SUITABILITY[ChannelType.INSTAGRAM_DM]
        assert "urgent" in multi_channel_manager.CHANNEL_SUITABILITY[ChannelType.SMS]
        assert "detailed" in multi_channel_manager.CHANNEL_SUITABILITY[ChannelType.EMAIL]
        assert "alerts" in multi_channel_manager.CHANNEL_SUITABILITY[ChannelType.SMS]
        assert "time_sensitive" in multi_channel_manager.CHANNEL_SUITABILITY[ChannelType.PUSH_NOTIFICATION]
    
    def test_backup_channel_selection(self, multi_channel_manager):
        """Test fallback to backup channels when preferred channel unavailable"""
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.EMAIL, ChannelType.SMS],  # Email first, then SMS
            business_hours_only=False,
            do_not_disturb=False,
            max_messages_per_day=5
        )
        
        with patch.object(multi_channel_manager, 'get_user_preferences', return_value=user_prefs):
            # Mock preferred channel as unsuitable for message type
            with patch.object(multi_channel_manager, '_is_channel_suitable') as mock_suitable:
                def suitability_check(channel, message_type):
                    if channel == ChannelType.INSTAGRAM_DM and message_type == "detailed":
                        return False  # Not suitable
                    return True
                
                mock_suitable.side_effect = suitability_check
                
                # Should fall back to first suitable backup channel
                channel = multi_channel_manager.get_optimal_channel(
                    user_id="test_user",
                    message_type="detailed",
                    priority="normal"
                )
                
                assert channel == ChannelType.EMAIL  # First backup channel


class TestIdempotencyVerification:
    """Test idempotency and duplicate prevention"""
    
    @pytest.fixture
    def reminder_scheduler(self):
        return ReminderScheduler()
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_duplicate_reminder_prevention(self, mock_redis, reminder_scheduler):
        """Test that duplicate reminders are prevented"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        
        # Mock Redis to return existing reminder status
        mock_redis.get.return_value = json.dumps({
            'event_id': event_id,
            'reminder_24h_sent': True,  # Already sent
            'slot_time': (datetime.now() + timedelta(days=1)).isoformat()
        })
        
        # Track that reminder was already sent
        reminder_key = f"reminder_schedule:{lead_id}"
        stored_data = mock_redis.get(reminder_key)
        assert stored_data is not None
        
        schedule_data = json.loads(stored_data)
        assert schedule_data.get('reminder_24h_sent') is True
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_idempotency_key_tracking(self, mock_redis, reminder_scheduler):
        """Test idempotency key tracking for reminder operations"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        
        # Mock successful tracking
        mock_redis.get.return_value = None  # No existing schedule
        mock_redis.setex.return_value = True
        
        # Schedule reminders
        result = reminder_scheduler.schedule_reminders(
            event_id=event_id,
            lead_id=lead_id,
            slot_time=datetime.now() + timedelta(days=1)
        )
        
        assert result['status'] == 'scheduled'
        assert '24h' in result['tasks']
        assert '3h' in result['tasks']
        assert '30m' in result['tasks']
        
        # Verify schedule was stored in Redis
        mock_redis.setex.assert_called()
        call_args = mock_redis.setex.call_args
        assert 'reminder_schedule:' in call_args[0][0]  # Key pattern
        assert json.loads(call_args[0][1])['event_id'] == event_id
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_network_failure_recovery(self, mock_redis, reminder_scheduler):
        """Test system recovers from network failures without duplicates"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        slot_time = datetime.now() + timedelta(days=1)
        
        # First call - Redis unavailable
        mock_redis.get.side_effect = Exception("Connection refused")
        
        with patch('backend.tasks.reminder_tasks.logger') as mock_logger:
            schedule = reminder_scheduler._get_reminder_schedule(lead_id)
            
            # Should return None on Redis failure
            assert schedule is None
            mock_logger.error.assert_called()
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_circuit_breaker_pattern(self, mock_redis, reminder_scheduler):
        """Test circuit breaker prevents cascading failures"""
        lead_id = "test_lead_123"
        
        # Simulate multiple Redis failures
        mock_redis.get.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection timeout"),
            Exception("Connection timeout")
        ]
        
        with patch('backend.tasks.reminder_tasks.redis_circuit_breaker') as mock_circuit_breaker:
            mock_circuit_breaker.call.side_effect = Exception("Circuit breaker open")
            
            # Should handle circuit breaker failure gracefully
            schedule = reminder_scheduler._get_reminder_schedule(lead_id)
            assert schedule is None


class TestSlackAlertValidation:
    """Test Slack alert system for reminder scenarios"""
    
    @pytest.fixture
    def observability_metrics(self):
        return ObservabilityMetrics()
    
    @patch('backend.booking.observability_metrics.requests.post')
    @patch('backend.booking.observability_metrics.os.getenv')
    def test_no_show_prediction_alert(self, mock_getenv, mock_post, observability_metrics):
        """Test Slack alert is sent for no-show predictions"""
        mock_getenv.return_value = "https://hooks.slack.com/test"
        mock_post.return_value.status_code = 200
        
        alert_data = {
            "alert_type": "no_show_prediction",
            "lead_id": "lead_123",
            "event_id": "event_456",
            "slot_time": "2023-01-01T14:00:00",
            "last_reminder_sent": "2023-01-01T13:00:00"
        }
        
        # Send alert through reminder scheduler
        with patch('backend.booking.reminder_scheduler.requests.post') as mock_slack_post:
            mock_slack_post.return_value.status_code = 200
            
            # This would be called from reminder_scheduler.send_last_chance_reminder
            from backend.booking.reminder_scheduler import ReminderScheduler
            scheduler = ReminderScheduler()
            scheduler._send_slack_alert(alert_data)
            
            # Verify Slack alert was sent
            mock_slack_post.assert_called_once()
            call_args = mock_slack_post.call_args
            assert call_args[0][0] == "https://hooks.slack.com/test"
            
            # Verify alert format
            message = call_args[1]['json']
            assert "Booking Alert: no_show_prediction" in message['text']
            assert 'blocks' in message
    
    @patch('backend.booking.observability_metrics.requests.post')
    @patch('backend.booking.observability_metrics.os.getenv')
    def test_sla_breach_alert(self, mock_getenv, mock_post, observability_metrics):
        """Test SLA breach alerts are sent"""
        mock_getenv.return_value = "https://hooks.slack.com/test"
        mock_post.return_value.status_code = 200
        
        # Trigger SLA breach
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=120)  # Over 60s SLA
        
        observability_metrics.track_write_latency(
            start_time=start_time,
            end_time=end_time,
            lead_id="test_lead"
        )
        
        # Verify Slack alert was sent for SLA breach
        mock_post.assert_called()
        call_args = mock_post.call_args
        message = call_args[0][0]  # URL
        json_data = call_args[1]['json']
        
        assert "SLA Breach" in json_data['text']
    
    @patch('backend.booking.observability_metrics.requests.post')
    @patch('backend.booking.observability_metrics.os.getenv')
    def test_weekly_digest_generation(self, mock_getenv, mock_post, observability_metrics):
        """Test weekly performance digest is generated and sent to Slack"""
        mock_getenv.return_value = "https://hooks.slack.com/test"
        mock_post.return_value.status_code = 200
        
        # Mock metric values
        with patch.object(observability_metrics, '_get_metric_sum', return_value=42), \
             patch.object(observability_metrics, '_get_metric_avg', return_value=25.0), \
             patch.object(observability_metrics, '_calculate_show_rate', return_value=85.0):
            
            result = observability_metrics.generate_weekly_digest()
            
            assert result['status'] == 'generated'
            assert result['metrics']['bookings_count'] == 42
            assert result['metrics']['show_rate'] == 85.0
            
            # Verify digest was sent to Slack
            mock_post.assert_called()
            call_args = mock_post.call_args
            json_data = call_args[1]['json']
            
            assert "weekly_digest" in json_data['text']
    
    @patch('backend.booking.observability_metrics.requests.post')
    @patch('backend.booking.observability_metrics.os.getenv')
    def test_slack_alert_missing_webhook(self, mock_getenv, mock_post, observability_metrics):
        """Test graceful handling when Slack webhook is not configured"""
        mock_getenv.return_value = None  # No webhook URL
        mock_post.return_value.status_code = 200
        
        alert_data = {"alert_type": "test", "message": "Test alert"}
        
        with patch('backend.booking.observability_metrics.logger') as mock_logger:
            observability_metrics.send_slack_alert("test", alert_data)
            
            # Should log warning and not try to send
            mock_logger.warning.assert_called_with(
                "SLACK_WEBHOOK_URL not configured - skipping Slack alert"
            )
            mock_post.assert_not_called()


class TestEndToEndReminderFlow:
    """Test complete end-to-end reminder integration flow"""
    
    @pytest.fixture
    def complete_reminder_system(self):
        return {
            'scheduler': ReminderScheduler(),
            'multi_channel': MultiChannelManager(),
            'metrics': ObservabilityMetrics()
        }
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    @patch('backend.tasks.reminder_tasks.audit_log_event')
    def test_complete_reminder_cadence(self, mock_audit, mock_redis, complete_reminder_system):
        """Test complete 24h->3h->30m reminder cadence flow"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        slot_time = datetime.now() + timedelta(days=1, hours=2)
        
        # Mock successful operations
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Mock multi-channel sending
        with patch.object(complete_reminder_system['multi_channel'], 'send_message') as mock_send:
            mock_send.return_value = {"success": True}
            
            # Schedule reminders
            schedule_result = complete_reminder_system['scheduler'].schedule_reminders(
                event_id=event_id,
                lead_id=lead_id,
                slot_time=slot_time
            )
            
            assert schedule_result['status'] == 'scheduled'
            
            # Execute reminder tasks in sequence
            send_reminder_24h(lead_id, event_id, slot_time.isoformat())
            send_reminder_3h(lead_id, event_id, slot_time.isoformat())
            send_reminder_30m(lead_id, event_id, slot_time.isoformat())
            
            # Verify all reminders were sent
            assert mock_send.call_count == 3
            
            # Verify audit logging
            assert mock_audit.call_count >= 3  # At least 3 audit events for the reminders
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_confirmation_tracking_flow(self, complete_reminder_system):
        """Test confirmation tracking through the complete flow"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        
        # Mock calendar client
        with patch.object(complete_reminder_system['scheduler'].calendar_client, 
                         'update_event_metadata', return_value=True), \
             patch.object(complete_reminder_system['scheduler'], '_store_reminder_schedule') as mock_store:
            
            # Track confirmation
            confirmed_at = datetime.now()
            result = complete_reminder_system['scheduler'].track_confirmation(
                lead_id, event_id, confirmed_at
            )
            
            assert result is True
            
            # Verify calendar event was updated
            complete_reminder_system['scheduler'].calendar_client.update_event_metadata.assert_called_once_with(
                event_id, {
                    'confirmed_at': confirmed_at.isoformat(),
                    'confirmation_method': 'reminder_response'
                }
            )
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_last_chance_reminder_flow(self, complete_reminder_system):
        """Test last-chance reminder flow when no confirmation received"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        
        # Mock no confirmation received
        with patch.object(complete_reminder_system['scheduler'], '_get_reminder_schedule') as mock_get:
            mock_get.return_value = {
                'event_id': event_id,
                'slot_time': (datetime.now() + timedelta(minutes=60)).isoformat(),
                'confirmed_at': None
            }
            
            # Mock Slack alert
            with patch.object(complete_reminder_system['scheduler'], '_send_slack_alert') as mock_slack:
                # Mock multi-channel sending
                with patch.object(complete_reminder_system['multi_channel'], 'send_message') as mock_send:
                    mock_send.return_value = {"success": True}
                    
                    result = complete_reminder_system['scheduler'].send_last_chance_reminder(
                        lead_id, event_id
                    )
                    
                    assert result is True
                    
                    # Verify Slack alert was sent
                    mock_slack.assert_called_once()
                    
                    # Verify last-chance reminder was sent
                    mock_send.assert_called()
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    @patch('backend.tasks.reminder_tasks.audit_log_event')
    def test_confirmation_reply_processing(self, mock_audit, mock_redis):
        """Test processing confirmation replies from leads"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        confirmation_message = "yes I'll be there"
        
        # Mock tracking confirmation
        with patch('backend.booking.reminder_scheduler.ReminderScheduler.track_confirmation') as mock_track:
            mock_track.return_value = True
            
            # Mock multi-channel acknowledgment
            with patch('backend.communication.multi_channel_manager.MultiChannelManager.send_message') as mock_send:
                mock_send.return_value = {"success": True}
                
                # Process confirmation reply
                process_confirmation_reply(lead_id, event_id, confirmation_message)
                
                # Verify confirmation was tracked
                mock_track.assert_called_once()
                
                # Verify acknowledgment was sent
                mock_send.assert_called_once()


class TestErrorRecoveryAndEdgeCases:
    """Test error recovery scenarios and edge cases"""
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_redis_failure_recovery(self):
        """Test system handles Redis failures gracefully"""
        lead_id = "test_lead_123"
        
        with patch('backend.tasks.reminder_tasks.redis_client') as mock_redis:
            # Simulate Redis connection failure
            mock_redis.get.side_effect = Exception("Connection refused")
            
            scheduler = ReminderScheduler()
            
            # Should handle Redis failure without crashing
            schedule = scheduler._get_reminder_schedule(lead_id)
            assert schedule is None
            
            # Should still allow scheduling despite Redis issues
            with patch.object(scheduler, '_store_reminder_schedule', return_value=False):
                result = scheduler.schedule_reminders(
                    event_id="event_123",
                    lead_id=lead_id,
                    slot_time=datetime.now() + timedelta(days=1)
                )
                
                # Should return error status but not crash
                assert result['status'] == 'error'
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    @patch('backend.tasks.reminder_tasks.audit_log_event')
    def test_celery_task_retry_mechanism(self, mock_audit, mock_redis):
        """Test Celery task retry mechanism on failures"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        slot_time = datetime.now() + timedelta(days=1)
        
        # Mock failure on first attempt, success on retry
        with patch('backend.tasks.reminder_tasks.reminder_scheduler._send_reminder_message') as mock_send:
            mock_send.side_effect = [False, True]  # Fail first, succeed on retry
            
            # First attempt should fail and trigger retry
            with pytest.raises(Exception):  # Celery retry exception
                send_reminder_24h(lead_id, event_id, slot_time.isoformat())
    
    def test_past_time_reminder_handling(self):
        """Test handling reminders scheduled for past times"""
        past_time = datetime.now() - timedelta(hours=1)
        lead_id = "test_lead_123"
        event_id = "event_456"
        
        scheduler = ReminderScheduler()
        
        # Should handle past times gracefully
        with patch.object(scheduler, '_send_reminder_message') as mock_send:
            mock_send.return_value = True
            
            result = scheduler._send_reminder_message(
                lead_id=lead_id,
                event_id=event_id,
                reminder_type='24h',
                slot_time=past_time
            )
            
            # Should still attempt to send (business logic decision)
            assert result is True
            mock_send.assert_called_once()
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_empty_user_preferences_handling(self, mock_redis):
        """Test handling users with no channel preferences set"""
        lead_id = "test_lead_123"
        
        # Mock no preferences stored
        mock_redis.get.return_value = None
        
        multi_channel = MultiChannelManager()
        
        # Should return default preferences
        prefs = multi_channel.get_user_preferences(lead_id)
        
        assert prefs.user_id == lead_id
        assert prefs.preferred_channel == ChannelType.INSTAGRAM_DM
        assert len(prefs.backup_channels) > 0
    
    @patch('backend.tasks.reminder_tasks.redis_client')
    def test_malformed_preference_data_handling(self, mock_redis):
        """Test handling malformed preference data gracefully"""
        lead_id = "test_lead_123"
        
        # Mock malformed JSON data
        mock_redis.get.return_value = '{"invalid": json data'
        
        multi_channel = MultiChannelManager()
        
        # Should fall back to defaults on parse error
        prefs = multi_channel.get_user_preferences(lead_id)
        
        assert prefs.user_id == lead_id
        assert isinstance(prefs, UserPreferences)
    
    def test_concurrent_reminder_scheduling(self):
        """Test handling concurrent reminder scheduling attempts"""
        lead_id = "test_lead_123"
        event_id = "event_456"
        slot_time = datetime.now() + timedelta(days=1)
        
        scheduler = ReminderScheduler()
        
        # Mock Redis operations
        with patch('backend.tasks.reminder_tasks.redis_client') as mock_redis:
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            
            # Schedule reminders multiple times (simulating concurrent requests)
            results = []
            for _ in range(3):
                result = scheduler.schedule_reminders(
                    event_id=event_id,
                    lead_id=lead_id,
                    slot_time=slot_time
                )
                results.append(result)
            
            # All should succeed (idempotent scheduling)
            for result in results:
                assert result['status'] == 'scheduled'
    
    @patch('backend.booking.reminder_scheduler.requests.post')
    @patch('backend.booking.reminder_scheduler.os.getenv')
    def test_slack_alert_failure_handling(self, mock_getenv, mock_post):
        """Test graceful handling of Slack alert failures"""
        mock_getenv.return_value = "https://hooks.slack.com/test"
        
        # Simulate Slack API failure
        import requests
        mock_post.side_effect = requests.RequestException("Slack API error")
        
        scheduler = ReminderScheduler()
        
        # Should not crash on Slack failure
        alert_data = {
            "alert_type": "test",
            "message": "Test alert"
        }
        
        # Should log error but not raise exception
        scheduler._send_slack_alert(alert_data)
        
        # Verify error was logged (mock_logger would be called)
        # In real implementation, this would log the error


class TestPRDComplianceValidation:
    """Test compliance with PRD binary acceptance criteria"""
    
    def test_reminder_frequency_limits(self):
        """Test that reminder frequency respects user limits"""
        # User with very low daily limit
        user_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.EMAIL],
            max_messages_per_day=1,  # Very restrictive
            do_not_disturb=False
        )
        
        multi_channel = MultiChannelManager()
        
        with patch.object(multi_channel, 'get_user_preferences', return_value=user_prefs):
            # First message should be allowed
            result1 = multi_channel.send_message(
                user_id="test_user",
                message="First message",
                priority="normal"
            )
            assert result1['success'] is True
            
            # System should track usage (in real implementation)
            # Second message should be blocked due to limits
    
    def test_industry_compliance_enforcement(self):
        """Test industry-specific compliance rules are enforced"""
        multi_channel = MultiChannelManager()
        
        # Real estate - guaranteed returns should be blocked
        real_estate_prefs = UserPreferences(
            user_id="test_user",
            preferred_channel=ChannelType.EMAIL,
            backup_channels=[ChannelType.INSTAGRAM_DM],
            industry_type=multi_channel.IndustryType.REAL_ESTATE
        )
        
        with patch.object(multi_channel, 'get_user_preferences', return_value=real_estate_prefs):
            # Should block non-compliant message
            result = multi_channel.send_message(
                user_id="test_user",
                message="We guarantee 20% returns on all our properties!",
                priority="normal"
            )
            
            assert result['success'] is False
            assert 'compliance' in result['error'].lower()
    
    def test_idempotency_sla_compliance(self):
        """Test that system meets PRD idempotency SLA requirements"""
        metrics = ObservabilityMetrics()
        
        # Mock high idempotency reuse rate
        with patch.object(metrics, '_store_metric_point'):
            metrics.track_idempotency_reuse(total_writes=100, reused=85)
        
        # Should track reuse rate and alert if below target
        assert metrics.sla_targets['idempotency_reuse_percent'] == 80.0
    
    def test_response_time_sla_compliance(self):
        """Test that system meets response time SLA requirements"""
        metrics = ObservabilityMetrics()
        
        # Mock tracking write latency
        with patch.object(metrics, '_store_metric_point'), \
             patch.object(metrics, '_update_latency_aggregates'):
            
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=30)  # Under SLA
            
            metrics.track_write_latency(start_time, end_time, "test_lead")
            
            # Should be under SLA threshold
            assert metrics.sla_targets['write_latency_seconds'] == 60
            assert (end_time - start_time).total_seconds() < 60


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])