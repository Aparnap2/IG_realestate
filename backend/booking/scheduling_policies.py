"""
Scheduling Policies for Self-Driving Booking Ops 2.0

Implements buffer policies, conflict resolution, and service-specific scheduling rules
to prevent double-bookings and optimize agent utilization.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from backend.tools.scheduling_utils import find_optimal_tour_slots
from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

@dataclass
class BufferPolicy:
    """Buffer time policy configuration."""
    min_gap_minutes: int = 30
    travel_buffer_by_location: Dict[str, int] = None  # location_pair -> buffer_minutes
    default_duration_minutes: int = 60
    max_daily_bookings: int = 8

    def __post_init__(self):
        if self.travel_buffer_by_location is None:
            self.travel_buffer_by_location = {
                "Miami->Fort_Lauderdale": 45,
                "Fort_Lauderdale->Miami": 45,
                "Miami->West_Palm_Beach": 60,
                "West_Palm_Beach->Miami": 60,
                "Miami->Coral_Gables": 30,
                "Coral_Gables->Miami": 30,
                # Add more city pairs as needed
            }

class SchedulingPolicies:
    """
    Service-specific scheduling policies and conflict resolution.
    
    Implements buffer time enforcement, travel calculations, and
    deterministic replanning for scheduling conflicts.
    """

    def __init__(self):
        self.redis_client = redis_client

        # Default policies by service type
        self.service_policies = {
            'single_property_tour': BufferPolicy(
                min_gap_minutes=15,
                default_duration_minutes=60,
                max_daily_bookings=10
            ),
            'multi_property_tour': BufferPolicy(
                min_gap_minutes=30,
                default_duration_minutes=90,
                max_daily_bookings=6
            ),
            'virtual_tour': BufferPolicy(
                min_gap_minutes=10,
                default_duration_minutes=30,
                max_daily_bookings=12
            ),
            'consultation': BufferPolicy(
                min_gap_minutes=15,
                default_duration_minutes=45,
                max_daily_bookings=8
            ),
            'default': BufferPolicy()  # Use defaults
        }

    def apply_buffer_policy(
        self,
        slots: List[Dict[str, Any]],
        policy: BufferPolicy,
        existing_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply buffer time policy to filter slots that violate buffer constraints.
        
        Args:
            slots: Candidate time slots
            policy: Buffer policy to apply
            existing_events: Existing calendar events
            
        Returns:
            Filtered slots that meet buffer requirements
        """
        try:
            if not slots:
                return []

            # Sort slots and existing events by start time
            sorted_slots = sorted(slots, key=lambda x: x.get('start', datetime.max))
            sorted_events = sorted(existing_events, key=lambda x: x.get('start', datetime.max))

            filtered_slots = []

            for slot in sorted_slots:
                slot_start = slot.get('start')
                slot_end = slot.get('end', slot_start + timedelta(minutes=policy.default_duration_minutes))

                # Check buffer time against all existing events
                violates_buffer = False

                for event in sorted_events:
                    event_start = event.get('start')
                    event_end = event.get('end')

                    if not event_start or not event_end:
                        continue

                    # Calculate required buffer for this event pair
                    required_buffer = self._calculate_required_buffer(
                        slot, event, policy
                    )

                    # Check for buffer violations
                    if self._slots_violate_buffer(slot_start, slot_end, event_start, event_end, required_buffer):
                        violates_buffer = True
                        break

                if not violates_buffer:
                    filtered_slots.append(slot)

            audit_log_event("buffer_policy_applied", {
                "original_slots": len(slots),
                "filtered_slots": len(filtered_slots),
                "policy_min_gap": policy.min_gap_minutes
            })

            return filtered_slots

        except Exception as e:
            logger.error(f"Error applying buffer policy: {e}")
            return slots  # Return original slots on error

    def calculate_travel_buffer(self, location_a: str, location_b: str) -> int:
        """
        Calculate travel buffer time between two locations.
        
        Args:
            location_a: Starting location
            location_b: Ending location
            
        Returns:
            Buffer time in minutes
        """
        try:
            # Normalize location names
            loc_a = location_a.lower().replace(' ', '_')
            loc_b = location_b.lower().replace(' ', '_')

            # Check both directions
            key1 = f"{loc_a}->{loc_b}"
            key2 = f"{loc_b}->{loc_a}"

            # Use hardcoded travel times (in production, integrate with Google Maps)
            travel_times = {
                "miami->fort_lauderdale": 45,
                "fort_lauderdale->miami": 45,
                "miami->west_palm_beach": 60,
                "west_palm_beach->miami": 60,
                "miami->coral_gables": 30,
                "coral_gables->miami": 30,
                "miami->miami_beach": 20,
                "miami_beach->miami": 20,
                "fort_lauderdale->west_palm_beach": 30,
                "west_palm_beach->fort_lauderdale": 30,
                # Add more city pairs
            }

            # Try both directions
            buffer_time = travel_times.get(key1, travel_times.get(key2, 30))  # Default 30 min

            return buffer_time

        except Exception as e:
            logger.warning(f"Error calculating travel buffer: {e}")
            return 30  # Conservative default

    def enforce_conflict_resolution(
        self,
        slot_time: datetime,
        policy: BufferPolicy
    ) -> Dict[str, Any]:
        """
        Enforce conflict resolution by extending time window and requerying.
        
        Args:
            slot_time: Originally requested slot time
            policy: Scheduling policy
            
        Returns:
            Dict with resolution strategy
        """
        try:
            # Extend search window
            extended_window = {
                'original_slot': slot_time.isoformat(),
                'extended_start': (slot_time - timedelta(hours=2)).isoformat(),
                'extended_end': (slot_time + timedelta(hours=2)).isoformat(),
                'alternative_days': 3
            }

            # Generate alternative slots
            alternative_slots = self._generate_alternative_slots(slot_time, policy)

            audit_log_event("conflict_resolution_enforced", {
                "original_slot": slot_time.isoformat(),
                "alternatives_generated": len(alternative_slots),
                "policy_duration": policy.default_duration_minutes
            })

            return {
                "status": "replan_recommended",
                "original_slot": slot_time.isoformat(),
                "alternative_slots": alternative_slots,
                "extended_window": extended_window,
                "resolution_strategy": "extend_window_and_replan"
            }

        except Exception as e:
            logger.error(f"Error enforcing conflict resolution: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_policy_for_service(self, service_type: str) -> BufferPolicy:
        """
        Get scheduling policy for a specific service type.
        
        Args:
            service_type: Service type identifier
            
        Returns:
            BufferPolicy for the service
        """
        return self.service_policies.get(service_type, self.service_policies['default'])

    def validate_daily_capacity(
        self,
        agent_id: str,
        proposed_slot: datetime,
        service_type: str
    ) -> Dict[str, Any]:
        """
        Validate that adding this booking doesn't exceed daily capacity.
        
        Args:
            agent_id: Agent/calendar identifier
            proposed_slot: Proposed slot time
            service_type: Service type
            
        Returns:
            Dict with capacity validation result
        """
        try:
            policy = self.get_policy_for_service(service_type)

            # Get existing bookings for the day
            day_start = proposed_slot.replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)

            # Query existing events (placeholder - would integrate with calendar)
            existing_count = self._get_existing_bookings_count(agent_id, day_start, day_end)

            capacity_ok = existing_count < policy.max_daily_bookings

            return {
                "capacity_ok": capacity_ok,
                "current_bookings": existing_count,
                "max_daily": policy.max_daily_bookings,
                "proposed_slot": proposed_slot.isoformat()
            }

        except Exception as e:
            logger.warning(f"Error validating daily capacity: {e}")
            return {
                "capacity_ok": True,  # Allow on error (fail open)
                "error": str(e)
            }

    def _calculate_required_buffer(
        self,
        slot_a: Dict[str, Any],
        slot_b: Dict[str, Any],
        policy: BufferPolicy
    ) -> int:
        """Calculate required buffer time between two slots."""
        try:
            # Get locations if available
            loc_a = slot_a.get('location', '')
            loc_b = slot_b.get('location', '')

            if loc_a and loc_b and loc_a != loc_b:
                # Different locations - use travel buffer
                return self.calculate_travel_buffer(loc_a, loc_b)
            else:
                # Same location or unknown - use minimum gap
                return policy.min_gap_minutes

        except Exception:
            return policy.min_gap_minutes

    def _slots_violate_buffer(
        self,
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
        required_buffer: int
    ) -> bool:
        """Check if two time slots violate buffer requirements."""
        try:
            # Convert buffer to timedelta
            buffer_delta = timedelta(minutes=required_buffer)

            # Check if slots are too close
            # Slot A ends too close to Slot B start
            if start_b - end_a < buffer_delta:
                return True

            # Slot B ends too close to Slot A start
            if start_a - end_b < buffer_delta:
                return True

            return False

        except Exception:
            # Conservative approach - assume violation on error
            return True

    def _generate_alternative_slots(
        self,
        original_slot: datetime,
        policy: BufferPolicy
    ) -> List[Dict[str, Any]]:
        """Generate alternative slot suggestions."""
        alternatives = []

        try:
            # Generate slots +/- 1-2 hours from original
            time_offsets = [-120, -60, 60, 120]  # minutes

            for offset in time_offsets:
                alt_time = original_slot + timedelta(minutes=offset)

                # Only include business hours (9 AM - 5 PM)
                if 9 <= alt_time.hour <= 17:
                    alternatives.append({
                        'start': alt_time,
                        'end': alt_time + timedelta(minutes=policy.default_duration_minutes),
                        'confidence': 0.8 if abs(offset) <= 60 else 0.6,
                        'reason': f'{"earlier" if offset < 0 else "later"} alternative'
                    })

        except Exception as e:
            logger.warning(f"Error generating alternative slots: {e}")

        return alternatives

    def _get_existing_bookings_count(
        self,
        agent_id: str,
        day_start: datetime,
        day_end: datetime
    ) -> int:
        """Get count of existing bookings for the day."""
        try:
            # Placeholder - would query calendar API
            # For now, return a mock count
            return 3  # Assume some existing bookings

        except Exception:
            return 0  # Conservative approach

    def cache_policy_result(
        self,
        cache_key: str,
        result: Dict[str, Any],
        ttl: int = 300
    ) -> bool:
        """Cache policy evaluation results."""
        if self.redis_client is None:
            return False

        def _cache_operation():
            key = f"policy_cache:{cache_key}"
            self.redis_client.setex(key, ttl, json.dumps(result, default=str))
            return True

        try:
            return redis_circuit_breaker.call(_cache_operation)
        except Exception as e:
            logger.warning(f"Error caching policy result: {e}")
            return False

    def get_cached_policy_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached policy evaluation result."""
        if self.redis_client is None:
            return None

        def _get_operation():
            key = f"policy_cache:{cache_key}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None

        try:
            return redis_circuit_breaker.call(_get_operation)
        except Exception as e:
            logger.warning(f"Error getting cached policy result: {e}")
            return None
