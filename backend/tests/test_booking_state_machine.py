"""
Test suite for Self-Driving Booking Ops 2.0 State Machine

Tests the deterministic booking flow orchestration with Redis state persistence.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from backend.booking.booking_state_machine import BookingStateMachine


class TestBookingStateMachine:
    """Test cases for booking state machine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = BookingStateMachine()

    def test_state_machine_initialization(self):
        """Test state machine initializes correctly."""
        assert self.sm is not None
        assert hasattr(self.sm, 'transition')
        assert hasattr(self.sm, 'get_state')
        assert hasattr(self.sm, 'set_state')

    @patch('backend.booking.booking_state_machine.redis_client')
    def test_get_state_no_redis(self, mock_redis):
        """Test get_state when Redis is unavailable."""
        mock_redis.get.return_value = None

        result = self.sm.get_state("test_lead_123")
        assert result is None

    @patch('backend.booking.booking_state_machine.redis_client')
    @patch('backend.booking.booking_state_machine.redis_circuit_breaker')
    def test_get_state_with_data(self, mock_circuit_breaker, mock_redis):
        """Test get_state with valid Redis data."""
        import json
        state_data = {
            'current_state': 'QUALIFY',
            'context': {'attempt_count': 1},
            'last_transition_at': datetime.now().isoformat()
        }
        mock_redis.get.return_value = json.dumps(state_data)
        mock_circuit_breaker.call.return_value = state_data

        result = self.sm.get_state("test_lead_123")
        assert result is not None
        assert result['current_state'] == 'QUALIFY'
        assert result['context']['attempt_count'] == 1

    @patch('backend.booking.booking_state_machine.redis_client')
    @patch('backend.booking.booking_state_machine.redis_circuit_breaker')
    def test_set_state(self, mock_circuit_breaker, mock_redis):
        """Test set_state stores data correctly."""
        mock_redis.setex.return_value = True
        mock_circuit_breaker.call.return_value = True

        result = self.sm.set_state("test_lead_123", "QUALIFY", {"test": "data"})
        assert result is True

        # Verify Redis was called
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "booking_state:test_lead_123"
        assert call_args[0][1] == 604800  # 7 days

    def test_transition_qualify_to_propose_slot(self):
        """Test transition from QUALIFY to PROPOSE_SLOT."""
        current_state = "QUALIFY"
        event = "qualify_complete"
        context = {"lead_data": {"budget": 300000}}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "PROPOSE_SLOT"
        assert "cache_slots" in actions

    def test_transition_confirm_to_write(self):
        """Test transition from CONFIRM to WRITE."""
        current_state = "CONFIRM"
        event = "slot_confirmed"
        context = {"selected_slot": datetime.now()}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "WRITE"
        assert "generate_idempotency_key" in actions
        assert "validate_availability" in actions

    def test_transition_write_to_reminders(self):
        """Test successful write transition to REMINDERS."""
        current_state = "WRITE"
        event = "write_success"
        context = {"event_id": "calendar_123"}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "REMINDERS"
        assert "schedule_reminders" in actions

    def test_transition_conflict_replan(self):
        """Test conflict detection triggers replan."""
        current_state = "CONFIRM"  # From CONFIRM state, not WRITE
        event = "conflict_detected"
        context = {"conflict_reason": "double_booking"}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "PROPOSE_SLOT"
        assert "invalidate_cache" in actions

    def test_transition_reschedule_request(self):
        """Test reschedule request handling."""
        current_state = "REMINDERS"
        event = "reschedule_request"
        context = {"new_slot": datetime.now()}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "RESCHEDULE"
        # RESCHEDULE state should transition to PROPOSE_SLOT when ready
        next_state, actions = self.sm.transition("test_lead", "RESCHEDULE", "qualify_complete", context)
        assert next_state == "PROPOSE_SLOT"

    def test_no_show_to_backfill(self):
        """Test no-show triggers waitlist backfill."""
        current_state = "REMINDERS"
        event = "no_show_predicted"
        context = {"slot_time": datetime.now()}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        assert next_state == "NO_SHOW"
        # Should transition to WAITLIST_BACKFILL
        next_state, actions = self.sm.transition("test_lead", "NO_SHOW", "backfill_triggered", context)
        assert next_state == "WAITLIST_BACKFILL"

    def test_invalid_transition(self):
        """Test invalid state transitions are rejected."""
        current_state = "INTAKE"
        event = "invalid_event"
        context = {}

        next_state, actions = self.sm.transition("test_lead", current_state, event, context)

        # Should stay in current state for invalid transitions
        assert next_state == current_state
        assert actions == {}

    def test_validate_transition(self):
        """Test transition validation logic."""
        # Valid transitions
        assert self.sm.validate_transition("INTAKE", "QUALIFY") is True
        assert self.sm.validate_transition("QUALIFY", "PROPOSE_SLOT") is True
        assert self.sm.validate_transition("PROPOSE_SLOT", "CONFIRM") is True

        # Invalid transitions
        assert self.sm.validate_transition("INTAKE", "WRITE") is False
        assert self.sm.validate_transition("REMINDERS", "INTAKE") is False

        # Invalid states
        assert self.sm.validate_transition("INVALID_STATE", "QUALIFY") is False
        assert self.sm.validate_transition("INTAKE", "INVALID_STATE") is False
