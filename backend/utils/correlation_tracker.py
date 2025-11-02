"""
Universal Correlation ID Tracker

Implements comprehensive correlation ID tracking across all agent interactions
and system components to ensure complete event traceability and monitoring.

Addresses: Priority 1 Gap 1.1 - Agent Orchestration Integration Failure
Universal Correlation ID tracking requirement

Key Features:
1. Generate and propagate correlation IDs across all agent interactions
2. Track agent transitions and handoffs with correlation context
3. Maintain correlation context throughout agent lifecycles
4. Integration with audit logging for complete event traceability
5. Support for nested correlation IDs and agent sub-contexts
"""

import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class CorrelationType(Enum):
    """Types of correlation tracking in the system"""
    LEAD_SESSION = "lead_session"
    AGENT_TRANSITION = "agent_transition"
    MESSAGE_DELIVERY = "message_delivery"
    BOOKING_OPERATION = "booking_operation"
    COMPLIANCE_CHECK = "compliance_check"
    AUDIT_EVENT = "audit_event"
    SYSTEM_OPERATION = "system_operation"

@dataclass
class CorrelationContext:
    """Complete correlation context for tracking agent interactions"""
    correlation_id: str
    parent_correlation_id: Optional[str]
    correlation_type: CorrelationType
    lead_id: Optional[str]
    agent_name: Optional[str]
    agent_state: Optional[str]
    session_start: datetime
    trace_path: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    nested_correlations: Set[str] = field(default_factory=set)
    
    def add_to_trace(self, component: str, action: str):
        """Add a step to the trace path"""
        trace_entry = f"{datetime.now(timezone.utc).isoformat()}: {component} -> {action}"
        self.trace_path.append(trace_entry)
        logger.debug(f"Trace added to {self.correlation_id}: {trace_entry}")
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to correlation context"""
        self.metadata[key] = value
    
    def add_nested_correlation(self, nested_id: str):
        """Add a nested correlation ID"""
        self.nested_correlations.add(nested_id)

class BookingAttributionTracker:
    """
    Phase 3: Booking Attribution & Source Tracking System.
    
    Tracks complete lead journey from initial intent to booking with
    full context preservation and ROI attribution tracking.
    """
    
    def __init__(self):
        self.redis_client = redis_client if redis_client else None
        
    async def track_lead_journey_complete(self, lead_id: str, journey_context: Dict[str, Any]) -> str:
        """Track complete lead journey with full attribution"""
        try:
            correlation_id = f"booking_attribution_{lead_id}_{int(datetime.now().timestamp())}"
            
            # Store complete journey context
            journey_data = {
                "correlation_id": correlation_id,
                "lead_id": lead_id,
                "journey_complete": True,
                "intent_analysis": journey_context.get("intent_analysis", {}),
                "qualification_context": journey_context.get("qualification_context", {}),
                "booking_confirmation": journey_context.get("booking_confirmation", {}),
                "source_attribution": journey_context.get("source_attribution", {}),
                "conversion_metrics": journey_context.get("conversion_metrics", {}),
                "phase_3_enhanced": True,
                "completion_timestamp": datetime.now().isoformat()
            }
            
            # Cache journey data for analytics
            await self._cache_journey_data(correlation_id, journey_data)
            
            logger.info(f"📊 Complete lead journey tracked: {correlation_id}")
            return correlation_id
            
        except Exception as e:
            logger.error(f"Error tracking complete lead journey: {str(e)}")
            return ""
    
    async def _cache_journey_data(self, correlation_id: str, journey_data: Dict[str, Any]) -> bool:
        """Cache journey data for reporting and analytics"""
        try:
            if not self.redis_client:
                return False
            
            cache_key = f"journey:{correlation_id}"
            
            def _cache_operation():
                return self.redis_client.setex(
                    cache_key, 
                    86400 * 30,  # 30 days
                    json.dumps(journey_data, default=str)
                )
            
            return redis_circuit_breaker.call(_cache_operation) if redis_circuit_breaker else False
            
        except Exception as e:
            logger.warning(f"Error caching journey data: {str(e)}")
            return False

class UniversalCorrelationTracker:
class UniversalCorrelationTracker:
    """
    Universal Correlation ID Tracker for complete event traceability.
    
    Ensures every agent interaction, message delivery, and system operation
    can be traced and monitored across the entire system.
    """
    
    def __init__(self):
        """Initialize the universal correlation tracker"""
        # Context variable for current correlation context
        self._current_context: ContextVar[Optional[CorrelationContext]] = ContextVar(
            'current_correlation_context', default=None
        )
        
        # Active correlation contexts for monitoring
        self._active_contexts: Dict[str, CorrelationContext] = {}
        
        # Correlation tracking for different types of operations
        self._correlation_registry: Dict[str, List[CorrelationContext]] = {}
        
        logger.info("🔍 Initializing Universal Correlation Tracker")
        logger.info("📊 Complete event traceability enabled")
    
    def generate_correlation_id(self, 
                              correlation_type: CorrelationType,
                              lead_id: Optional[str] = None,
                              parent_correlation_id: Optional[str] = None,
                              agent_name: Optional[str] = None,
                              agent_state: Optional[str] = None) -> str:
        """
        Generate a new correlation ID with complete context.
        
        Args:
            correlation_type: Type of correlation to track
            lead_id: Optional lead ID for session tracking
            parent_correlation_id: Optional parent correlation for nesting
            agent_name: Optional agent name for agent-specific tracking
            agent_state: Optional agent state for state-specific tracking
            
        Returns:
            Unique correlation ID string
        """
        try:
            # Generate unique correlation ID
            correlation_id = f"{correlation_type.value}_{uuid.uuid4().hex[:16]}_{int(datetime.now().timestamp())}"
            
            # Create correlation context
            context = CorrelationContext(
                correlation_id=correlation_id,
                parent_correlation_id=parent_correlation_id,
                correlation_type=correlation_type,
                lead_id=lead_id,
                agent_name=agent_name,
                agent_state=agent_state,
                session_start=datetime.now(timezone.utc)
            )
            
            # Add initial trace entry
            context.add_to_trace("correlation_tracker", f"Created {correlation_type.value}")
            
            # Register correlation context
            self._active_contexts[correlation_id] = context
            
            # Add to registry for type-based tracking
            if correlation_type.value not in self._correlation_registry:
                self._correlation_registry[correlation_type.value] = []
            self._correlation_registry[correlation_type.value].append(context)
            
            # Set as current context
            self.set_current_context(context)
            
            logger.info(f"🔍 Generated correlation ID: {correlation_id}")
            logger.debug(f"📊 Correlation context: {context}")
            
            return correlation_id
            
        except Exception as e:
            logger.error(f"❌ Error generating correlation ID: {str(e)}")
            raise
    
    def set_current_context(self, context: CorrelationContext):
        """Set the current correlation context"""
        try:
            self._current_context.set(context)
            logger.debug(f"📋 Set current context: {context.correlation_id}")
        except Exception as e:
            logger.error(f"❌ Error setting current context: {str(e)}")
    
    def get_current_context(self) -> Optional[CorrelationContext]:
        """Get the current correlation context"""
        try:
            context = self._current_context.get()
            return context
        except Exception as e:
            logger.error(f"❌ Error getting current context: {str(e)}")
            return None
    
    def start_agent_orchestration(self,
                                lead_id: str,
                                initial_agent: str,
                                orchestration_type: str = "standard") -> str:
        """
        Start agent orchestration tracking for a lead session.
        
        Args:
            lead_id: Lead being orchestrated
            initial_agent: Initial agent in the flow
            orchestration_type: Type of orchestration (standard, automated, manual)
            
        Returns:
            Correlation ID for the orchestration session
        """
        try:
            logger.info(f"🎭 Starting agent orchestration for lead {lead_id} with {initial_agent}")
            
            # Generate orchestration correlation ID
            correlation_id = self.generate_correlation_id(
                correlation_type=CorrelationType.LEAD_SESSION,
                lead_id=lead_id,
                agent_name=initial_agent,
                agent_state="orchestration_start"
            )
            
            # Add orchestration metadata
            context = self.get_current_context()
            if context:
                context.add_metadata("orchestration_type", orchestration_type)
                context.add_metadata("initial_agent", initial_agent)
                context.add_to_trace("orchestration", f"Started with {initial_agent}")
            
            logger.info(f"🎭 Agent orchestration started: {correlation_id}")
            return correlation_id
            
        except Exception as e:
            logger.error(f"❌ Error starting agent orchestration: {str(e)}")
            raise
    
    def track_agent_transition(self,
                             from_agent: str,
                             to_agent: str,
                             transition_reason: str,
                             success: bool = True) -> str:
        """
        Track agent transition with correlation context.
        
        Args:
            from_agent: Previous agent
            to_agent: Next agent
            transition_reason: Reason for transition
            success: Whether transition was successful
            
        Returns:
            Transition correlation ID
        """
        try:
            current_context = self.get_current_context()
            if not current_context:
                logger.warning(f"⚠️ No current context for agent transition {from_agent} -> {to_agent}")
                return ""
            
            # Generate transition correlation ID (nested under current)
            transition_id = self.generate_correlation_id(
                correlation_type=CorrelationType.AGENT_TRANSITION,
                parent_correlation_id=current_context.correlation_id,
                agent_name=to_agent,
                agent_state="transition"
            )
            
            # Update contexts
            current_context.add_to_trace("agent_transition", f"{from_agent} -> {to_agent}: {transition_reason}")
            current_context.add_nested_correlation(transition_id)
            
            # Update new agent context
            new_context = self.get_current_context()
            if new_context:
                new_context.add_metadata("previous_agent", from_agent)
                new_context.add_metadata("transition_reason", transition_reason)
                new_context.add_metadata("transition_success", success)
                new_context.agent_name = to_agent
                new_context.add_to_trace("agent_acceptance", f"Received handoff from {from_agent}")
            
            logger.info(f"🔄 Agent transition tracked: {from_agent} -> {to_agent} ({transition_id})")
            return transition_id
            
        except Exception as e:
            logger.error(f"❌ Error tracking agent transition: {str(e)}")
            raise
    
    def track_message_delivery(self,
                             channel: str,
                             recipient: str,
                             message_type: str,
                             delivery_status: str) -> str:
        """
        Track message delivery with correlation context.
        
        Args:
            channel: Delivery channel (whatsapp, email, etc.)
            recipient: Message recipient
            message_type: Type of message
            delivery_status: Delivery status
            
        Returns:
            Message correlation ID
        """
        try:
            current_context = self.get_current_context()
            if not current_context:
                logger.warning(f"⚠️ No current context for message delivery tracking")
                return ""
            
            # Generate message correlation ID
            message_id = self.generate_correlation_id(
                correlation_type=CorrelationType.MESSAGE_DELIVERY,
                parent_correlation_id=current_context.correlation_id
            )
            
            # Update contexts
            current_context.add_nested_correlation(message_id)
            
            # Set message context
            message_context = self.get_current_context()
            if message_context:
                message_context.add_metadata("channel", channel)
                message_context.add_metadata("recipient", recipient)
                message_context.add_metadata("message_type", message_type)
                message_context.add_metadata("delivery_status", delivery_status)
                message_context.add_to_trace("message_delivery", f"{channel} -> {recipient}: {delivery_status}")
            
            logger.info(f"📨 Message delivery tracked: {channel} -> {recipient} ({message_id})")
            return message_id
            
        except Exception as e:
            logger.error(f"❌ Error tracking message delivery: {str(e)}")
            raise
    
    def track_booking_operation(self,
                              operation_type: str,
                              booking_details: Dict[str, Any],
                              success: bool = True) -> str:
        """
        Track booking operation with correlation context.
        
        Args:
            operation_type: Type of booking operation
            booking_details: Details of the booking operation
            success: Whether operation was successful
            
        Returns:
            Booking correlation ID
        """
        try:
            current_context = self.get_current_context()
            if not current_context:
                logger.warning(f"⚠️ No current context for booking operation tracking")
                return ""
            
            # Generate booking correlation ID
            booking_id = self.generate_correlation_id(
                correlation_type=CorrelationType.BOOKING_OPERATION,
                parent_correlation_id=current_context.correlation_id
            )
            
            # Update contexts
            current_context.add_nested_correlation(booking_id)
            
            # Set booking context
            booking_context = self.get_current_context()
            if booking_context:
                booking_context.add_metadata("operation_type", operation_type)
                booking_context.add_metadata("booking_details", booking_details)
                booking_context.add_metadata("booking_success", success)
                booking_context.add_to_trace("booking_operation", f"{operation_type}: {'success' if success else 'failed'}")
            
            logger.info(f"📅 Booking operation tracked: {operation_type} ({booking_id})")
            return booking_id
            
        except Exception as e:
            logger.error(f"❌ Error tracking booking operation: {str(e)}")
            raise
    
    def track_compliance_check(self,
                             compliance_type: str,
                             checked_content: str,
                             violation_detected: bool = False,
                             action_taken: str = "none") -> str:
        """
        Track compliance check with correlation context.
        
        Args:
            compliance_type: Type of compliance check
            checked_content: Content that was checked
            violation_detected: Whether a violation was detected
            action_taken: Action taken as result of check
            
        Returns:
            Compliance correlation ID
        """
        try:
            current_context = self.get_current_context()
            if not current_context:
                logger.warning(f"⚠️ No current context for compliance check tracking")
                return ""
            
            # Generate compliance correlation ID
            compliance_id = self.generate_correlation_id(
                correlation_type=CorrelationType.COMPLIANCE_CHECK,
                parent_correlation_id=current_context.correlation_id
            )
            
            # Update contexts
            current_context.add_nested_correlation(compliance_id)
            
            # Set compliance context
            compliance_context = self.get_current_context()
            if compliance_context:
                compliance_context.add_metadata("compliance_type", compliance_type)
                compliance_context.add_metadata("violation_detected", violation_detected)
                compliance_context.add_metadata("action_taken", action_taken)
                compliance_context.add_to_trace("compliance_check", f"{compliance_type}: {'violation' if violation_detected else 'clear'}")
            
            logger.info(f"⚖️ Compliance check tracked: {compliance_type} ({compliance_id})")
            return compliance_id
            
        except Exception as e:
            logger.error(f"❌ Error tracking compliance check: {str(e)}")
            raise
    
    def get_correlation_context(self, correlation_id: str) -> Optional[CorrelationContext]:
        """
        Get correlation context by ID.
        
        Args:
            correlation_id: Correlation ID to lookup
            
        Returns:
            Correlation context if found
        """
        try:
            return self._active_contexts.get(correlation_id)
        except Exception as e:
            logger.error(f"❌ Error getting correlation context: {str(e)}")
            return None
    
    def get_lead_correlations(self, lead_id: str) -> List[CorrelationContext]:
        """
        Get all correlation contexts for a specific lead.
        
        Args:
            lead_id: Lead ID to lookup
            
        Returns:
            List of correlation contexts for the lead
        """
        try:
            lead_contexts = []
            for context in self._active_contexts.values():
                if context.lead_id == lead_id:
                    lead_contexts.append(context)
            return lead_contexts
        except Exception as e:
            logger.error(f"❌ Error getting lead correlations: {str(e)}")
            return []
    
    def get_agent_correlations(self, agent_name: str) -> List[CorrelationContext]:
        """
        Get all correlation contexts for a specific agent.
        
        Args:
            agent_name: Agent name to lookup
            
        Returns:
            List of correlation contexts for the agent
        """
        try:
            agent_contexts = []
            for context in self._active_contexts.values():
                if context.agent_name == agent_name:
                    agent_contexts.append(context)
            return agent_contexts
        except Exception as e:
            logger.error(f"❌ Error getting agent correlations: {str(e)}")
            return []
    
    def get_correlation_trace(self, correlation_id: str) -> List[str]:
        """
        Get complete trace path for a correlation.
        
        Args:
            correlation_id: Correlation ID to trace
            
        Returns:
            List of trace entries
        """
        try:
            context = self.get_correlation_context(correlation_id)
            if context:
                return context.trace_path
            return []
        except Exception as e:
            logger.error(f"❌ Error getting correlation trace: {str(e)}")
            return []
    
    def cleanup_expired_contexts(self, max_age_hours: int = 24):
        """
        Cleanup expired correlation contexts.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            expired_ids = []
            
            for correlation_id, context in self._active_contexts.items():
                if context.session_start < cutoff_time:
                    expired_ids.append(correlation_id)
            
            for expired_id in expired_ids:
                del self._active_contexts[expired_id]
                logger.debug(f"🧹 Cleaned up expired correlation context: {expired_id}")
            
            if expired_ids:
                logger.info(f"🧹 Cleaned up {len(expired_ids)} expired correlation contexts")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired contexts: {str(e)}")
    
    def get_tracking_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive tracking statistics.
        
        Returns:
            Dictionary of tracking statistics
        """
        try:
            total_contexts = len(self._active_contexts)
            active_leads = len(set(ctx.lead_id for ctx in self._active_contexts.values() if ctx.lead_id))
            active_agents = len(set(ctx.agent_name for ctx in self._active_contexts.values() if ctx.agent_name))
            
            # Count by correlation type
            type_counts = {}
            for correlation_type in CorrelationType:
                count = len(self._correlation_registry.get(correlation_type.value, []))
                type_counts[correlation_type.value] = count
            
            return {
                "total_active_contexts": total_contexts,
                "active_leads": active_leads,
                "active_agents": active_agents,
                "correlation_type_distribution": type_counts,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting tracking statistics: {str(e)}")
            return {"error": str(e)}

# Global correlation tracker instance
correlation_tracker = UniversalCorrelationTracker()

# Global instances
correlation_tracker = UniversalCorrelationTracker()
booking_attribution_tracker = BookingAttributionTracker()

# Convenience functions for Phase 3 booking attribution
async def track_complete_lead_journey(lead_id: str, journey_context: Dict[str, Any]) -> str:
    """Track complete lead journey with full attribution"""
    return await booking_attribution_tracker.track_lead_journey_complete(lead_id, journey_context)
# Convenience functions for common use cases
def start_lead_session(lead_id: str, initial_agent: str = "qualifier") -> str:
    """Start a new lead session with correlation tracking"""
    return correlation_tracker.start_agent_orchestration(lead_id, initial_agent)

def track_agent_handoff(from_agent: str, to_agent: str, reason: str) -> str:
    """Track agent handoff with correlation context"""
    return correlation_tracker.track_agent_transition(from_agent, to_agent, reason)

def track_message(channel: str, recipient: str, message_type: str) -> str:
    """Track message delivery with correlation context"""
    return correlation_tracker.track_message_delivery(channel, recipient, message_type, "sent")

def track_booking(operation_type: str, details: Dict[str, Any]) -> str:
    """Track booking operation with correlation context"""
    return correlation_tracker.track_booking_operation(operation_type, details)

def track_compliance_check(compliance_type: str, content: str) -> str:
    """Track compliance check with correlation context"""
    return correlation_tracker.track_compliance_check(compliance_type, content)

def get_correlation_context(correlation_id: str) -> Optional[CorrelationContext]:
    """Get correlation context by ID"""
    return correlation_tracker.get_correlation_context(correlation_id)

def get_current_correlation() -> Optional[CorrelationContext]:
    """Get current correlation context"""
    return correlation_tracker.get_current_context()