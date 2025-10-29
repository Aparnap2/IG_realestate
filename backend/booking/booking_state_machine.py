"""
Booking State Machine for Self-Driving Booking Ops 2.0

Implements deterministic state transitions for the booking flow with Redis-backed state persistence.
States: INTAKE → QUALIFY → PROPOSE_SLOT → CONFIRM → WRITE → REMINDERS → (RESCHEDULE | NO_SHOW | WAITLIST_BACKFILL)
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from backend.utils.redis_client import redis_client, redis_circuit_breaker

logger = logging.getLogger(__name__)

class BookingStateMachine:
    """
    State machine orchestrator for booking flow with deterministic transitions.
    
    States:
    - INTAKE: Initial lead intake and qualification start
    - QUALIFY: Progressive Q&A to gather requirements
    - PROPOSE_SLOT: Generate and propose time slots
    - CONFIRM: User confirms selected slot
    - WRITE: Idempotent calendar write operation
    - REMINDERS: Multi-touch reminder scheduling
    - RESCHEDULE: Handle reschedule requests
    - NO_SHOW: Predicted no-show handling
    - WAITLIST_BACKFILL: Waitlist backfill for no-shows
    """

    STATES = {
        'INTAKE',
        'QUALIFY', 
        'PROPOSE_SLOT',
        'CONFIRM',
        'WRITE',
        'REMINDERS',
        'RESCHEDULE',
        'NO_SHOW',
        'WAITLIST_BACKFILL'
    }

    # Deterministic state transitions
    TRANSITIONS = {
        'INTAKE': {'QUALIFY'},
        'QUALIFY': {'PROPOSE_SLOT'},
        'PROPOSE_SLOT': {'CONFIRM', 'PROPOSE_SLOT'},  # Can replan
        'CONFIRM': {'WRITE', 'PROPOSE_SLOT'},  # Can go back on conflict
        'WRITE': {'REMINDERS', 'PROPOSE_SLOT'},  # Can replan on conflict
        'REMINDERS': {'RESCHEDULE', 'NO_SHOW'},
        'RESCHEDULE': {'PROPOSE_SLOT'},
        'NO_SHOW': {'WAITLIST_BACKFILL'},
        'WAITLIST_BACKFILL': set()  # Terminal state
    }

    def __init__(self):
        self.redis_client = redis_client

    def transition(self, lead_id: str, current_state: str, event: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Execute deterministic state transition based on current state and event.
        
        Args:
            lead_id: Lead identifier
            current_state: Current booking state
            event: Transition event trigger
            context: State context data
            
        Returns:
            Tuple of (next_state, actions_dict)
        """
        if current_state not in self.STATES:
            logger.error(f"Invalid current state: {current_state}")
            return current_state, {}

        # Determine next state based on event
        next_state = self._determine_next_state(current_state, event, context)
        
        if next_state not in self.TRANSITIONS.get(current_state, set()):
            logger.warning(f"Invalid transition from {current_state} to {next_state} for event {event}")
            return current_state, {}

        # Generate actions for the transition
        actions = self._generate_actions(current_state, next_state, context)
        
        # Update state in Redis
        self.set_state(lead_id, next_state, context)
        
        logger.info(f"Booking state transition: {lead_id} {current_state} → {next_state}")
        return next_state, actions

    def _determine_next_state(self, current_state: str, event: str, context: Dict[str, Any]) -> str:
        """Determine next state based on event and context."""
        if event == 'qualify_complete':
            return 'PROPOSE_SLOT'
        elif event == 'slots_proposed':
            return 'CONFIRM'
        elif event == 'slot_confirmed':
            return 'WRITE'
        elif event == 'write_success':
            return 'REMINDERS'
        elif event == 'conflict_detected':
            return 'PROPOSE_SLOT'  # Replan
        elif event == 'reschedule_request':
            return 'RESCHEDULE'
        elif event == 'no_show_predicted':
            return 'NO_SHOW'
        elif event == 'backfill_triggered':
            return 'WAITLIST_BACKFILL'
        
        return current_state

    def _generate_actions(self, from_state: str, to_state: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate actions required for state transition."""
        actions = {}
        
        if to_state == 'PROPOSE_SLOT':
            actions['cache_slots'] = True
        elif to_state == 'WRITE':
            actions['generate_idempotency_key'] = True
            actions['validate_availability'] = True
        elif to_state == 'REMINDERS':
            actions['schedule_reminders'] = True
        elif to_state == 'PROPOSE_SLOT' and from_state in ['CONFIRM', 'WRITE']:
            actions['invalidate_cache'] = True  # Replan actions
        elif to_state == 'NO_SHOW':
            actions['trigger_backfill'] = True
            
        return actions

    def get_state(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current booking state from Redis.
        
        Args:
            lead_id: Lead identifier
            
        Returns:
            State dict with current_state and context, or None if not found
        """
        if self.redis_client is None:
            logger.debug("Redis unavailable - cannot get booking state")
            return None

        def _get_operation():
            key = f"booking_state:{lead_id}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None

        try:
            return redis_circuit_breaker.call(_get_operation)
        except Exception as e:
            logger.warning(f"Error getting booking state for {lead_id}: {e}")
            return None

    def set_state(self, lead_id: str, state: str, context: Dict[str, Any], ttl: int = 604800) -> bool:
        """
        Set booking state in Redis with TTL.
        
        Args:
            lead_id: Lead identifier
            state: New state
            context: State context data
            ttl: Time to live in seconds (default: 7 days)
            
        Returns:
            True if successful, False otherwise
        """
        if self.redis_client is None:
            logger.debug("Redis unavailable - cannot set booking state")
            return False

        if state not in self.STATES:
            logger.error(f"Invalid state: {state}")
            return False

        def _set_operation():
            key = f"booking_state:{lead_id}"
            state_data = {
                'current_state': state,
                'context': context,
                'last_transition_at': datetime.now().isoformat()
            }
            self.redis_client.setex(key, ttl, json.dumps(state_data, default=str))
            return True

        try:
            return redis_circuit_breaker.call(_set_operation)
        except Exception as e:
            logger.warning(f"Error setting booking state for {lead_id}: {e}")
            return False

    def validate_transition(self, current_state: str, next_state: str) -> bool:
        """
        Validate if a state transition is allowed.
        
        Args:
            current_state: Current state
            next_state: Proposed next state
            
        Returns:
            True if transition is valid, False otherwise
        """
        if current_state not in self.STATES or next_state not in self.STATES:
            return False
            
        return next_state in self.TRANSITIONS.get(current_state, set())
