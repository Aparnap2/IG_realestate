"""
Slot Cache Manager for Self-Driving Booking Ops 2.0

Implements Redis-backed slot caching with ETag invalidation for efficient
calendar availability queries and optimistic hold management.
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.tools.calendar_integration import GoogleCalendarClient
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

class SlotCacheManager:
    """
    Redis-backed slot cache with ETag invalidation and optimistic locking.
    
    Caches calendar availability slots with automatic invalidation on changes,
    optimistic holds for race condition prevention, and multi-calendar merging.
    """

    def __init__(self):
        self.redis_client = redis_client
        self.calendar_client = GoogleCalendarClient()

    def get_cached_slots(
        self,
        location: str,
        service: str,
        duration: int,
        buffers: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached available slots with ETag validation.
        
        Args:
            location: Service location
            service: Service type
            duration: Slot duration in minutes
            buffers: Buffer policy parameters
            
        Returns:
            Cached slots list or None if cache miss
        """
        try:
            cache_key = self._generate_cache_key(location, service, duration, buffers)
            current_etag = self._get_calendar_etag(location)

            def _get_cache_operation():
                key = f"slots:{cache_key}"
                cached_data = self.redis_client.get(key)

                if not cached_data:
                    return None

                cache_entry = json.loads(cached_data)
                cached_etag = cache_entry.get('etag')

                # Check if cache is still valid
                if cached_etag and current_etag and cached_etag == current_etag:
                    audit_log_event("slot_cache_hit", {
                        "cache_key": cache_key,
                        "location": location,
                        "service": service,
                        "slots_count": len(cache_entry.get('slots', []))
                    })
                    return cache_entry['slots']
                else:
                    # Cache invalid - delete stale entry
                    self.redis_client.delete(key)
                    audit_log_event("slot_cache_invalidated", {
                        "cache_key": cache_key,
                        "reason": "etag_mismatch",
                        "cached_etag": cached_etag,
                        "current_etag": current_etag
                    })
                    return None

            result = redis_circuit_breaker.call(_get_cache_operation)
            return result

        except Exception as e:
            logger.warning(f"Error getting cached slots: {e}")
            return None

    def cache_slots(
        self,
        location: str,
        service: str,
        duration: int,
        buffers: Dict[str, Any],
        slots: List[Dict[str, Any]]
    ) -> bool:
        """
        Cache slots with current ETag.
        
        Args:
            location: Service location
            service: Service type
            duration: Slot duration in minutes
            buffers: Buffer policy parameters
            slots: Slots to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(location, service, duration, buffers)
            current_etag = self._get_calendar_etag(location)

            def _cache_operation():
                key = f"slots:{cache_key}"
                cache_entry = {
                    'slots': slots,
                    'etag': current_etag,
                    'cached_at': datetime.now().isoformat(),
                    'metadata': {
                        'location': location,
                        'service': service,
                        'duration': duration,
                        'buffers': buffers
                    }
                }

                # Cache for 5 minutes
                self.redis_client.setex(key, 300, json.dumps(cache_entry, default=str))
                return True

            success = redis_circuit_breaker.call(_cache_operation)

            if success:
                audit_log_event("slots_cached", {
                    "cache_key": cache_key,
                    "location": location,
                    "service": service,
                    "slots_count": len(slots),
                    "ttl_seconds": 300
                })

            return success

        except Exception as e:
            logger.error(f"Error caching slots: {e}")
            return False

    def invalidate_cache(self, calendar_id: str) -> bool:
        """
        Invalidate all cached slots for a calendar by updating ETag.
        
        Args:
            calendar_id: Calendar identifier
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            # Generate new ETag
            new_etag = self._generate_etag()

            def _invalidate_operation():
                etag_key = f"calendar_etag:{calendar_id}"
                # No TTL - ETags persist until manually invalidated
                self.redis_client.set(etag_key, new_etag)
                return True

            success = redis_circuit_breaker.call(_invalidate_operation)

            if success:
                audit_log_event("cache_invalidated", {
                    "calendar_id": calendar_id,
                    "new_etag": new_etag,
                    "reason": "manual_invalidation"
                })

            return success

        except Exception as e:
            logger.error(f"Error invalidating cache for {calendar_id}: {e}")
            return False

    def merge_provider_calendars(
        self,
        calendar_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Merge free slots from multiple provider calendars.
        
        Args:
            calendar_ids: List of calendar IDs to merge
            
        Returns:
            Union of free slots across all calendars
        """
        try:
            all_slots = []

            for calendar_id in calendar_ids:
                # Get freebusy for this calendar
                freebusy = self.calendar_client.get_freebusy(
                    calendar_id=calendar_id,
                    days_ahead=7
                )

                # Convert freebusy to slots (placeholder logic)
                calendar_slots = self._freebusy_to_slots(freebusy)
                all_slots.extend(calendar_slots)

            # Remove duplicates and sort
            unique_slots = self._deduplicate_slots(all_slots)
            unique_slots.sort(key=lambda x: x.get('start', datetime.max))

            audit_log_event("calendars_merged", {
                "calendar_count": len(calendar_ids),
                "total_slots": len(all_slots),
                "unique_slots": len(unique_slots)
            })

            return unique_slots

        except Exception as e:
            logger.error(f"Error merging provider calendars: {e}")
            return []

    def optimistic_hold(
        self,
        lead_id: str,
        slot_time: datetime
    ) -> bool:
        """
        Create optimistic hold on a slot to prevent race conditions.
        
        Args:
            lead_id: Lead identifier
            slot_time: Slot time to hold
            
        Returns:
            True if hold created successfully, False otherwise
        """
        try:
            def _hold_operation():
                hold_key = f"slot_hold:{lead_id}"
                hold_data = {
                    'slot_time': slot_time.isoformat(),
                    'created_at': datetime.now().isoformat(),
                    'lead_id': lead_id
                }

                # Hold for 15 minutes
                success = self.redis_client.setnx(hold_key, json.dumps(hold_data))
                if success:
                    self.redis_client.expire(hold_key, 900)  # 15 minutes
                return success

            success = redis_circuit_breaker.call(_hold_operation)

            if success:
                audit_log_event("slot_hold_created", {
                    "lead_id": lead_id,
                    "slot_time": slot_time.isoformat(),
                    "hold_duration_minutes": 15
                })

            return success

        except Exception as e:
            logger.error(f"Error creating optimistic hold for {lead_id}: {e}")
            return False

    def validate_hold(self, lead_id: str, slot_time: datetime) -> bool:
        """
        Validate that a slot hold is still active.
        
        Args:
            lead_id: Lead identifier
            slot_time: Expected slot time
            
        Returns:
            True if hold is valid, False otherwise
        """
        try:
            def _validate_operation():
                hold_key = f"slot_hold:{lead_id}"
                hold_data = self.redis_client.get(hold_key)

                if not hold_data:
                    return False

                hold_info = json.loads(hold_data)
                held_slot = datetime.fromisoformat(hold_info['slot_time'])

                # Check if slot times match (within 1 minute tolerance)
                time_diff = abs((held_slot - slot_time).total_seconds())
                return time_diff < 60

            return redis_circuit_breaker.call(_validate_operation) or False

        except Exception as e:
            logger.warning(f"Error validating hold for {lead_id}: {e}")
            return False

    def release_hold(self, lead_id: str) -> bool:
        """
        Release slot hold.
        
        Args:
            lead_id: Lead identifier
            
        Returns:
            True if released successfully, False otherwise
        """
        try:
            def _release_operation():
                hold_key = f"slot_hold:{lead_id}"
                deleted = self.redis_client.delete(hold_key)
                return deleted > 0

            success = redis_circuit_breaker.call(_release_operation)

            if success:
                audit_log_event("slot_hold_released", {
                    "lead_id": lead_id
                })

            return success

        except Exception as e:
            logger.error(f"Error releasing hold for {lead_id}: {e}")
            return False

    def revalidate_on_accept(self, slot_time: datetime) -> bool:
        """
        Revalidate slot availability immediately before write.
        
        Args:
            slot_time: Slot time to revalidate
            
        Returns:
            True if slot is still available, False otherwise
        """
        try:
            # Query calendar freebusy for immediate validation
            freebusy = self.calendar_client.get_freebusy(
                time_min=slot_time.replace(hour=0, minute=0, second=0),
                time_max=slot_time.replace(hour=23, minute=59, second=59),
                days_ahead=1
            )

            # Check if slot_time fits in any free slot
            slot_duration = 60  # Assume 60 minutes
            slot_end = slot_time + timedelta(minutes=slot_duration)

            for free_slot in freebusy:
                free_start = free_slot.get('start')
                free_end = free_slot.get('end')

                if (isinstance(free_start, datetime) and isinstance(free_end, datetime) and
                    free_start <= slot_time and free_end >= slot_end):
                    return True

            # Slot no longer available
            audit_log_event("slot_revalidation_failed", {
                "slot_time": slot_time.isoformat(),
                "reason": "no_longer_available"
            })

            return False

        except Exception as e:
            logger.warning(f"Error revalidating slot {slot_time}: {e}")
            return False  # Conservative approach

    def _generate_cache_key(
        self,
        location: str,
        service: str,
        duration: int,
        buffers: Dict[str, Any]
    ) -> str:
        """Generate deterministic cache key for slots."""
        key_components = {
            'location': location,
            'service': service,
            'duration': duration,
            'buffers': json.dumps(buffers, sort_keys=True)
        }

        key_string = json.dumps(key_components, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_calendar_etag(self, calendar_id: str) -> str:
        """Get current ETag for calendar invalidation tracking."""
        try:
            def _get_etag_operation():
                etag_key = f"calendar_etag:{calendar_id}"
                etag = self.redis_client.get(etag_key)

                if not etag:
                    # Generate initial ETag
                    etag = self._generate_etag()
                    self.redis_client.set(etag_key, etag)

                return etag

            return redis_circuit_breaker.call(_get_etag_operation) or self._generate_etag()

        except Exception:
            # Return default ETag on error
            return self._generate_etag()

    def _generate_etag(self) -> str:
        """Generate a new ETag for cache invalidation."""
        return hashlib.md5(f"{datetime.now().timestamp()}".encode()).hexdigest()

    def _freebusy_to_slots(self, freebusy_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert freebusy data to slot format."""
        # Placeholder - would convert freebusy periods to available slots
        return freebusy_data  # Assume already in slot format

    def _deduplicate_slots(self, slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate slots from merged calendar data."""
        seen = set()
        unique_slots = []

        for slot in slots:
            # Create hash of slot start/end times
            slot_hash = f"{slot.get('start')}_{slot.get('end')}"

            if slot_hash not in seen:
                seen.add(slot_hash)
                unique_slots.append(slot)

        return unique_slots
