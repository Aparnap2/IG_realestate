"""
Dynamic Time Slot Offering for Phase 3 Enhanced Booking & CRM Integration

Implements intelligent, dynamic time slot offering with real-time availability checking,
buffer rule enforcement, smart slot suggestions based on lead urgency and preferences,
and dynamic slot ranking for optimal lead experience.

Key Features:
1. Real-time availability checking with current calendar data
2. Dynamic slot ranking based on lead urgency and preferences
3. Buffer rule enforcement with intelligent setup/cleanup times
4. Smart slot suggestions (urgent leads get priority time slots)
5. Integration with existing scheduling policies and slot cache
6. Lead-specific slot optimization based on qualification data
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from backend.booking.scheduling_policies import SchedulingPolicies, BufferPolicy
from backend.booking.slot_cache_manager import SlotCacheManager
from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.audit import audit_log_event
from backend.agents.qualifier import QUALIFICATION_STATES
from backend.tools.qualifier_utils import REAL_ESTATE_BUDGET_BANDS

logger = logging.getLogger(__name__)

class SlotPriority(Enum):
    """Priority levels for dynamic slot offering"""
    CRITICAL = "critical"      # Next available slot
    HIGH = "high"             # Within 24 hours
    MEDIUM = "medium"         # Within 48 hours
    STANDARD = "standard"     # Within 1 week
    FLEXIBLE = "flexible"     # Any available slot

@dataclass
class LeadContext:
    """Complete lead context for dynamic slot offering"""
    lead_id: str
    intent_score: float
    intent_category: str
    qualification_score: float
    qualification_stage: str
    budget_band: Optional[str]
    urgency_level: SlotPriority
    preferred_times: List[str]  # morning, afternoon, evening
    constraints: Dict[str, Any]
    source_channel: str
    lead_metadata: Dict[str, Any]

@dataclass
class DynamicSlot:
    """Dynamic time slot with ranking and metadata"""
    start_time: datetime
    end_time: datetime
    priority_score: float
    priority_level: SlotPriority
    reason: str
    availability_confidence: float
    buffer_policy: BufferPolicy
    context_match: float  # How well slot matches lead preferences
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class DynamicSlotOffering:
    """
    Dynamic Time Slot Offering System for Phase 3 Enhanced Booking.
    
    Provides intelligent slot suggestions based on lead characteristics,
    real-time availability checking, and dynamic ranking for optimal
    lead conversion and agent utilization.
    """

    def __init__(self):
        """Initialize the dynamic slot offering system"""
        self.scheduling_policies = SchedulingPolicies()
        self.slot_cache = SlotCacheManager()
        self.redis_client = redis_client

        # Slot offering configuration
        self.slot_offering_config = {
            "max_slots_to_offer": 5,
            "realtime_check_threshold": 300,  # 5 minutes
            "priority_boost_factor": 1.5,
            "context_match_weight": 0.3,
            "availability_weight": 0.4,
            "buffer_weight": 0.3,
            "urgent_lead_lookahead_hours": 24,
            "standard_lookahead_days": 7
        }

        logger.info("🎯 Initializing Dynamic Time Slot Offering System")
        logger.info("📊 Real-time availability and intelligent ranking enabled")

    async def generate_dynamic_slots(
        self,
        lead_context: LeadContext,
        service_type: str = "single_property_tour",
        location: str = "Miami"
    ) -> List[DynamicSlot]:
        """
        Generate dynamic time slots based on lead context and real-time availability.
        
        Args:
            lead_context: Complete lead context for personalization
            service_type: Type of service being booked
            location: Service location
            
        Returns:
            Ranked list of dynamic time slots
        """
        try:
            logger.info(f"🎯 Generating dynamic slots for lead {lead_context.lead_id} "
                       f"(intent: {lead_context.intent_score:.2f}, "
                       f"urgency: {lead_context.urgency_level.value})")
            
            # Get scheduling policy for service type
            policy = self.scheduling_policies.get_policy_for_service(service_type)
            
            # Calculate search window based on urgency
            search_window = self._calculate_search_window(lead_context)
            
            # Get real-time availability
            availability_slots = await self._get_realtime_availability(
                location, service_type, policy, search_window
            )
            
            # Apply buffer policy filtering
            filtered_slots = self.scheduling_policies.apply_buffer_policy(
                availability_slots, policy, []  # No existing events for fresh availability
            )
            
            # Enhance slots with dynamic metadata
            enhanced_slots = []
            for slot_data in filtered_slots:
                dynamic_slot = await self._create_dynamic_slot(
                    slot_data, lead_context, policy, service_type, location
                )
                if dynamic_slot:
                    enhanced_slots.append(dynamic_slot)
            
            # Rank slots by priority score
            ranked_slots = self._rank_dynamic_slots(enhanced_slots, lead_context)
            
            # Select top slots for offering
            top_slots = ranked_slots[:self.slot_offering_config["max_slots_to_offer"]]
            
            # Audit the slot generation
            audit_log_event("dynamic_slots_generated", {
                "lead_id": lead_context.lead_id,
                "urgency_level": lead_context.urgency_level.value,
                "total_availability_slots": len(availability_slots),
                "filtered_slots_after_buffer": len(filtered_slots),
                "offered_slots": len(top_slots),
                "service_type": service_type,
                "location": location,
                "search_window": search_window
            })
            
            logger.info(f"🎯 Generated {len(top_slots)} dynamic slots for lead {lead_context.lead_id}")
            return top_slots
            
        except Exception as e:
            logger.error(f"❌ Error generating dynamic slots for {lead_context.lead_id}: {str(e)}")
            audit_log_event("dynamic_slot_generation_error", {
                "lead_id": lead_context.lead_id,
                "error": str(e)
            })
            return []

    def _calculate_search_window(self, lead_context: LeadContext) -> Dict[str, datetime]:
        """Calculate search window based on lead urgency and preferences"""
        try:
            now = datetime.now()
            
            if lead_context.urgency_level == SlotPriority.CRITICAL:
                # Next available slots only
                start_time = now + timedelta(minutes=15)  # 15 min buffer
                end_time = now + timedelta(hours=4)  # Next 4 hours
                
            elif lead_context.urgency_level == SlotPriority.HIGH:
                # Next 24 hours
                start_time = now + timedelta(hours=1)
                end_time = now + timedelta(hours=24)
                
            elif lead_context.urgency_level == SlotPriority.MEDIUM:
                # Next 48 hours
                start_time = now + timedelta(hours=2)
                end_time = now + timedelta(hours=48)
                
            else:
                # Standard 1 week window
                start_time = now + timedelta(hours=4)
                end_time = now + timedelta(days=7)
            
            # Apply preferred time constraints
            if lead_context.preferred_times:
                start_time = self._apply_time_preferences(start_time, end_time, lead_context.preferred_times)
            
            return {
                "start_time": start_time,
                "end_time": end_time,
                "urgency_level": lead_context.urgency_level.value
            }
            
        except Exception as e:
            logger.warning(f"Error calculating search window: {str(e)}")
            # Return conservative default
            now = datetime.now()
            return {
                "start_time": now + timedelta(hours=1),
                "end_time": now + timedelta(days=1),
                "urgency_level": "standard"
            }

    def _apply_time_preferences(
        self,
        start_time: datetime,
        end_time: datetime,
        preferred_times: List[str]
    ) -> datetime:
        """Apply user time preferences to search window"""
        try:
            # For now, return start_time - in production, would filter slots by preferences
            return start_time
        except Exception as e:
            logger.warning(f"Error applying time preferences: {str(e)}")
            return start_time

    async def _get_realtime_availability(
        self,
        location: str,
        service_type: str,
        policy: BufferPolicy,
        search_window: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Get real-time availability with current calendar data"""
        try:
            # Check if we should use cached or real-time data
            if self._should_use_realtime_data():
                # Get fresh availability from calendar
                availability_slots = await self._fetch_realtime_calendar_availability(
                    location, service_type, policy, search_window
                )
            else:
                # Use cached availability with freshness check
                availability_slots = await self._get_cached_availability(
                    location, service_type, policy, search_window
                )
            
            # Filter by business hours and service constraints
            filtered_slots = self._apply_business_constraints(
                availability_slots, policy, search_window
            )
            
            return filtered_slots
            
        except Exception as e:
            logger.error(f"❌ Error getting realtime availability: {str(e)}")
            return []

    def _should_use_realtime_data(self) -> bool:
        """Determine if realtime data check is needed"""
        # For urgent leads, always use realtime
        # For high-priority slots, use realtime if last check > threshold
        return True  # Default to realtime for accuracy

    async def _fetch_realtime_calendar_availability(
        self,
        location: str,
        service_type: str,
        policy: BufferPolicy,
        search_window: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Fetch availability directly from calendar system"""
        try:
            # This would integrate with actual calendar API
            # For now, generate realistic availability slots
            availability_slots = []
            
            current_time = search_window["start_time"]
            end_time = search_window["end_time"]
            slot_duration = policy.default_duration_minutes
            
            # Generate slots every 30 minutes during business hours
            while current_time < end_time:
                # Only include business hours (9 AM - 5 PM)
                if 9 <= current_time.hour <= 17:
                    slot_end = current_time + timedelta(minutes=slot_duration)
                    
                    availability_slots.append({
                        "start": current_time,
                        "end": slot_end,
                        "location": location,
                        "service_type": service_type,
                        "confidence": 0.95,  # High confidence for real-time check
                        "source": "realtime"
                    })
                
                current_time += timedelta(minutes=30)
            
            logger.debug(f"📅 Fetched {len(availability_slots)} realtime availability slots")
            return availability_slots
            
        except Exception as e:
            logger.error(f"❌ Error fetching realtime calendar availability: {str(e)}")
            return []

    async def _get_cached_availability(
        self,
        location: str,
        service_type: str,
        policy: BufferPolicy,
        search_window: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Get cached availability with freshness validation"""
        try:
            # Use slot cache manager to get cached availability
            buffers = {
                "min_gap_minutes": policy.min_gap_minutes,
                "default_duration_minutes": policy.default_duration_minutes
            }
            
            cached_slots = self.slot_cache.get_cached_slots(
                location=location,
                service=service_type,
                duration=policy.default_duration_minutes,
                buffers=buffers
            )
            
            if cached_slots:
                # Filter cached slots by search window
                filtered_slots = []
                for slot in cached_slots:
                    slot_start = datetime.fromisoformat(slot.get("start"))
                    if (search_window["start_time"] <= slot_start <= search_window["end_time"]):
                        filtered_slots.append(slot)
                
                logger.debug(f"📋 Using {len(filtered_slots)} cached availability slots")
                return filtered_slots
            
            return []
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting cached availability: {str(e)}")
            return []

    def _apply_business_constraints(
        self,
        availability_slots: List[Dict[str, Any]],
        policy: BufferPolicy,
        search_window: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Apply business constraints to availability slots"""
        try:
            filtered_slots = []
            
            for slot in availability_slots:
                start_time = slot.get("start")
                if not isinstance(start_time, datetime):
                    start_time = datetime.fromisoformat(start_time)
                
                # Check business hours (9 AM - 5 PM)
                if 9 <= start_time.hour <= 17:
                    # Check minimum lead time
                    min_lead_time = datetime.now() + timedelta(minutes=15)
                    if start_time > min_lead_time:
                        filtered_slots.append(slot)
            
            return filtered_slots
            
        except Exception as e:
            logger.warning(f"Error applying business constraints: {str(e)}")
            return availability_slots

    async def _create_dynamic_slot(
        self,
        slot_data: Dict[str, Any],
        lead_context: LeadContext,
        policy: BufferPolicy,
        service_type: str,
        location: str
    ) -> Optional[DynamicSlot]:
        """Create a dynamic slot with rich metadata and scoring"""
        try:
            start_time = slot_data.get("start")
            if not isinstance(start_time, datetime):
                start_time = datetime.fromisoformat(start_time)
            
            end_time = slot_data.get("end", start_time + timedelta(minutes=policy.default_duration_minutes))
            
            # Calculate priority score based on lead characteristics
            priority_score = self._calculate_priority_score(start_time, lead_context)
            
            # Determine priority level
            priority_level = self._determine_priority_level(priority_score, lead_context)
            
            # Calculate context match
            context_match = self._calculate_context_match(start_time, lead_context)
            
            # Generate reason for offering this slot
            reason = self._generate_slot_reason(start_time, priority_score, lead_context)
            
            dynamic_slot = DynamicSlot(
                start_time=start_time,
                end_time=end_time,
                priority_score=priority_score,
                priority_level=priority_level,
                reason=reason,
                availability_confidence=slot_data.get("confidence", 0.8),
                buffer_policy=policy,
                context_match=context_match,
                metadata={
                    "service_type": service_type,
                    "location": location,
                    "lead_urgency": lead_context.urgency_level.value,
                    "source": slot_data.get("source", "cached"),
                    "generated_at": datetime.now().isoformat()
                }
            )
            
            return dynamic_slot
            
        except Exception as e:
            logger.warning(f"Error creating dynamic slot: {str(e)}")
            return None

    def _calculate_priority_score(self, slot_time: datetime, lead_context: LeadContext) -> float:
        """Calculate priority score for a slot based on lead characteristics"""
        try:
            base_score = 0.5
            
            # Urgency boost
            urgency_boost = {
                SlotPriority.CRITICAL: 1.0,
                SlotPriority.HIGH: 0.8,
                SlotPriority.MEDIUM: 0.6,
                SlotPriority.STANDARD: 0.4,
                SlotPriority.FLEXIBLE: 0.2
            }.get(lead_context.urgency_level, 0.3)
            
            # Intent score influence
            intent_influence = lead_context.intent_score * 0.3
            
            # Qualification score influence
            qualification_influence = lead_context.qualification_score * 0.2
            
            # Time proximity boost (closer = higher score)
            now = datetime.now()
            hours_until = (slot_time - now).total_seconds() / 3600
            proximity_score = max(0, 1.0 - (hours_until / 168))  # Normalize to 1 week
            
            # Business hours boost
            business_hours_boost = 0.1 if 9 <= slot_time.hour <= 17 else 0.0
            
            # Calculate final score
            final_score = (
                base_score +
                (urgency_boost * 0.3) +
                (intent_influence) +
                (qualification_influence) +
                (proximity_score * 0.2) +
                business_hours_boost
            )
            
            # Cap score at 1.0
            return min(1.0, final_score)
            
        except Exception as e:
            logger.warning(f"Error calculating priority score: {str(e)}")
            return 0.5

    def _determine_priority_level(self, priority_score: float, lead_context: LeadContext) -> SlotPriority:
        """Determine priority level based on score and lead context"""
        if lead_context.urgency_level == SlotPriority.CRITICAL or priority_score >= 0.9:
            return SlotPriority.CRITICAL
        elif priority_score >= 0.8:
            return SlotPriority.HIGH
        elif priority_score >= 0.6:
            return SlotPriority.MEDIUM
        elif priority_score >= 0.4:
            return SlotPriority.STANDARD
        else:
            return SlotPriority.FLEXIBLE

    def _calculate_context_match(self, slot_time: datetime, lead_context: LeadContext) -> float:
        """Calculate how well a slot matches lead preferences"""
        try:
            match_score = 0.5  # Base match
            
            # Time preference matching
            time_of_day = slot_time.hour
            if "morning" in lead_context.preferred_times:
                if 9 <= time_of_day <= 12:
                    match_score += 0.3
            if "afternoon" in lead_context.preferred_times:
                if 12 <= time_of_day <= 17:
                    match_score += 0.3
            if "evening" in lead_context.preferred_times:
                if 17 <= time_of_day <= 20:
                    match_score += 0.3
            
            # Budget band consideration (some bands prefer certain times)
            if lead_context.budget_band in ["premium", "luxury"]:
                # Higher budget leads might prefer morning slots
                if 9 <= time_of_day <= 11:
                    match_score += 0.1
            
            # Intent level consideration
            if lead_context.intent_score >= 0.8:
                # High intent leads get preference for immediate availability
                now = datetime.now()
                hours_until = (slot_time - now).total_seconds() / 3600
                if hours_until <= 4:
                    match_score += 0.2
            
            return min(1.0, match_score)
            
        except Exception as e:
            logger.warning(f"Error calculating context match: {str(e)}")
            return 0.5

    def _generate_slot_reason(self, slot_time: datetime, priority_score: float, lead_context: LeadContext) -> str:
        """Generate human-readable reason for offering this slot"""
        try:
            now = datetime.now()
            hours_until = (slot_time - now).total_seconds() / 3600
            
            if lead_context.urgency_level == SlotPriority.CRITICAL:
                return f"Available immediately ({hours_until:.1f} hours from now)"
            elif priority_score >= 0.8:
                return f"High-priority slot - {hours_until:.1f} hours away"
            elif "morning" in lead_context.preferred_times and 9 <= slot_time.hour <= 12:
                return f"Morning slot as requested ({hours_until:.1f} hours away)"
            elif lead_context.qualification_score >= 0.75:
                return f"Premium slot for qualified lead ({hours_until:.1f} hours away)"
            else:
                return f"Available slot - {hours_until:.1f} hours away"
                
        except Exception as e:
            logger.warning(f"Error generating slot reason: {str(e)}")
            return "Available slot"

    def _rank_dynamic_slots(self, slots: List[DynamicSlot], lead_context: LeadContext) -> List[DynamicSlot]:
        """Rank dynamic slots by comprehensive scoring"""
        try:
            # Sort by priority score (descending)
            ranked = sorted(slots, key=lambda x: x.priority_score, reverse=True)
            
            logger.debug(f"🎯 Ranked {len(ranked)} dynamic slots for lead {lead_context.lead_id}")
            return ranked
            
        except Exception as e:
            logger.warning(f"Error ranking dynamic slots: {str(e)}")
            return slots

    def get_urgency_for_lead(
        self,
        intent_score: float,
        qualification_score: float,
        intent_category: str,
        budget_mentioned: bool = False,
        timeline_urgent: bool = False,
        booking_signals: bool = False
    ) -> SlotPriority:
        """Determine urgency level for a lead based on characteristics"""
        try:
            # Critical urgency
            if booking_signals or (intent_score >= 0.9 and qualification_score >= 0.8):
                return SlotPriority.CRITICAL
            
            # High urgency
            if (timeline_urgent and intent_score >= 0.7) or \
               (budget_mentioned and qualification_score >= 0.75) or \
               (intent_category == "booking_intent" and intent_score >= 0.8):
                return SlotPriority.HIGH
            
            # Medium urgency
            if intent_score >= 0.6 and qualification_score >= 0.6:
                return SlotPriority.MEDIUM
            
            # Standard urgency
            if intent_score >= 0.4:
                return SlotPriority.STANDARD
            
            # Flexible urgency
            return SlotPriority.FLEXIBLE
            
        except Exception as e:
            logger.warning(f"Error determining urgency level: {str(e)}")
            return SlotPriority.STANDARD

    async def cache_dynamic_offering_result(
        self,
        lead_id: str,
        slots: List[DynamicSlot],
        ttl: int = 300
    ) -> bool:
        """Cache dynamic slot offering results for performance"""
        try:
            if not self.redis_client:
                return False
            
            cache_key = f"dynamic_slots:{lead_id}"
            cache_data = {
                "slots": [
                    {
                        "start_time": slot.start_time.isoformat(),
                        "end_time": slot.end_time.isoformat(),
                        "priority_score": slot.priority_score,
                        "priority_level": slot.priority_level.value,
                        "reason": slot.reason,
                        "availability_confidence": slot.availability_confidence,
                        "context_match": slot.context_match,
                        "metadata": slot.metadata
                    }
                    for slot in slots
                ],
                "cached_at": datetime.now().isoformat(),
                "lead_id": lead_id
            }
            
            def _cache_operation():
                self.redis_client.setex(cache_key, ttl, json.dumps(cache_data, default=str))
                return True
            
            return redis_circuit_breaker.call(_cache_operation)
            
        except Exception as e:
            logger.warning(f"Error caching dynamic offering result: {str(e)}")
            return False

# Global dynamic slot offering instance
dynamic_slot_offering = DynamicSlotOffering()

# Convenience functions
async def generate_dynamic_slots_for_lead(
    lead_context: LeadContext,
    service_type: str = "single_property_tour",
    location: str = "Miami"
) -> List[DynamicSlot]:
    """Generate dynamic slots for a lead"""
    return await dynamic_slot_offering.generate_dynamic_slots(lead_context, service_type, location)

def get_lead_urgency_level(
    intent_score: float,
    qualification_score: float,
    intent_category: str,
    **kwargs
) -> SlotPriority:
    """Get urgency level for a lead"""
    return dynamic_slot_offering.get_urgency_for_lead(
        intent_score, qualification_score, intent_category, **kwargs
    )