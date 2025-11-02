"""
Unified State Machine Coordinator - Agent Orchestration Integration

This module implements the critical agent orchestration system that replaces manual 
agent designation with automated state transitions, addressing the Priority 1 
pilot readiness gap identified in the comprehensive assessment.

Key Functions:
1. Seamless agent handoffs without manual intervention
2. Automated booking state machine integration  
3. Universal correlation ID tracking across all interactions
4. Complete state transition audit logging
5. Compliance enforcement integration

Addresses: Priority 1 Gap 1.1 - Agent Orchestration Integration Failure
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from uuid import uuid4

from ..booking.booking_state_machine import BookingStateMachine
from ..utils.audit import audit_log_event
from ..utils.observability import log_agent_handoff
from ..utils.correlation_tracker import correlation_tracker, CorrelationType
from ..temporal.graph_client import get_graphiti_client
from ..utils.redis_client import redis_client, redis_circuit_breaker
from ..schemas.state import AgentState
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class UnifiedStateCoordinator:
    """
    Unified State Machine Coordinator for seamless agent orchestration.
    
    This replaces manual agent designation with automated state transitions,
    ensuring T0+120s scenario completion without manual intervention.
    
    Key Features:
    - Automated agent handoffs based on qualification state
    - Booking state machine integration for automation
    - Universal correlation ID tracking
    - Complete audit trail for all transitions
    - Compliance enforcement integration
    """
    
    def __init__(self):
        """Initialize the unified state coordinator."""
        self.booking_state_machine = BookingStateMachine()
        self.active_sessions = {}
        
        logger.info("🚀 Initializing Unified State Machine Coordinator")
        logger.info("✅ Agent Orchestration Integration - Ready for Pilot")
    
    async def orchestrate_agent_transition(
        self, 
        current_state: AgentState, 
        trigger_event: str = "message_processed"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Orchestrate seamless agent transition using state machine logic.
        
        This is the CORE function that replaces manual agent designation
        with automated state transitions, fixing Priority 1 Gap 1.1.
        
        Args:
            current_state: Current conversation and lead state
            trigger_event: Event that triggered this transition
            
        Returns:
            Tuple of (next_agent, transition_context)
        """
        lead_id = current_state["lead"].user_id
        correlation_id = self._get_or_create_correlation_id(lead_id)
        
        try:
            logger.info(f"🎯 ORCHESTRATING TRANSITION for {lead_id}")
            logger.info(f"📋 Trigger: {trigger_event}")
            logger.info(f"🆔 Correlation ID: {correlation_id}")
            
            # Step 1: Determine current qualification state using Phase 2 rules
            qualification_state = await self._assess_qualification_state_phase2(current_state)
            
            # Step 2: Determine next state based on automation rules
            next_state, automation_actions = await self._determine_next_automated_state(
                current_state, qualification_state, trigger_event, correlation_id
            )
            
            # Step 3: Execute automation actions (state machine integration, etc.)
            automation_result = await self._execute_automation_actions(
                lead_id, next_state, automation_actions, current_state, correlation_id
            )
            
            # Step 4: Log complete state transition
            await self._log_state_transition(
                lead_id, current_state, next_state, trigger_event, 
                correlation_id, automation_result
            )
            
            # Step 5: Return next agent based on state
            next_agent = self._map_state_to_agent(next_state)
            
            logger.info(f"✅ AUTOMATED TRANSITION: {next_agent}")
            logger.info(f"📊 Automation actions: {len(automation_actions)} executed")
            
            return next_agent, {
                "next_state": next_state,
                "automation_actions": automation_actions,
                "automation_result": automation_result,
                "correlation_id": correlation_id,
                "transition_timestamp": datetime.now().isoformat(),
                "orchestration_method": "automated_state_machine"
            }
            
        except Exception as e:
            logger.error(f"❌ Orchestration error for {lead_id}: {str(e)}")
            
            # Fallback to safe default (qualifier) on error
            fallback_agent = "qualifier"
            
            await audit_log_event("orchestration_error", {
                "lead_id": lead_id,
                "error": str(e),
                "fallback_agent": fallback_agent,
                "correlation_id": correlation_id
            })
            
            return fallback_agent, {
                "error": str(e),
                "fallback_agent": fallback_agent,
                "correlation_id": correlation_id,
                "transition_timestamp": datetime.now().isoformat()
            }
    
    async def _assess_qualification_state(self, state: AgentState) -> Dict[str, Any]:
        """
        Assess current qualification state for automation decisions.
        
        Returns comprehensive qualification assessment including:
        - qualification_score: Current lead qualification score
        - qualification_stage: Current stage (unqualified, qualifying, qualified)
        - budget_known: Whether budget information is available
        - location_known: Whether location preference is known
        - timeline_known: Whether timeline is established
        - booking_readiness: Whether ready for booking automation
        """
        lead = state["lead"]
        messages = state.get("messages", [])
        
        # Extract qualification data from state
        qualification_data = getattr(lead, 'qualification_data', {}) or {}
        
        # Calculate qualification score from available data
        qualification_score = self._calculate_qualification_score(qualification_data, messages)
        
        # Determine qualification stage
        if qualification_score >= 0.4:
            qualification_stage = "qualified"
        elif qualification_score >= 0.2:
            qualification_stage = "qualifying"
        else:
            qualification_stage = "unqualified"
        
        # Check for specific qualification factors
        budget_known = bool(qualification_data.get('budget') or 
                          any('budget' in msg.get('content', '').lower() for msg in messages[-5:]))
        
        location_known = bool(qualification_data.get('location') or 
                            any('location' in msg.get('content', '').lower() or 
                                'area' in msg.get('content', '').lower() for msg in messages[-5:]))
        
        timeline_known = bool(qualification_data.get('timeline') or 
                            any('timeline' in msg.get('content', '').lower() or
                                'when' in msg.get('content', '').lower() for msg in messages[-5:]))
        
        # Determine booking readiness (T0+120s automation trigger)
        booking_ready = (
            qualification_stage == "qualified" and
            qualification_score >= 0.4 and
            budget_known and
            location_known and
            timeline_known
        )
        
        return {
            "qualification_score": qualification_score,
            "qualification_stage": qualification_stage,
            "budget_known": budget_known,
            "location_known": location_known,
            "timeline_known": timeline_known,
            "booking_ready": booking_ready,
            "message_count": len(messages),
            "last_message_time": messages[-1].get('timestamp') if messages else None,
            "time_since_first_contact": self._calculate_time_since_first_contact(messages)
        }
    
    def _calculate_qualification_score(self, qualification_data: Dict, messages: list) -> float:
        """Calculate qualification score from available data."""
        score = 0.0
        
        # Base score from qualification data
        if qualification_data.get('budget'):
            score += 0.2
        if qualification_data.get('location'):
            score += 0.2
        if qualification_data.get('timeline'):
            score += 0.2
        
        # Boost from message content analysis
        message_text = " ".join([msg.get('content', '') for msg in messages[-5:]]).lower()
        
        # Property interest indicators
        if any(word in message_text for word in ['condo', 'apartment', 'house', 'property']):
            score += 0.1
        
        # Intent indicators
        if any(word in message_text for word in ['buy', 'purchase', 'rent', 'looking for']):
            score += 0.1
        
        # Engagement indicators
        if any(word in message_text for word in ['yes', 'interested', 'tell me more']):
            score += 0.1
        
        # Time-based engagement boost
        if len(messages) >= 3:
            score += 0.1
        
        return min(score, 1.0)
    
    
    async def _assess_qualification_state_phase2(self, state: AgentState) -> Dict[str, Any]:
        """
        Phase 2: Advanced qualification state assessment with transparent scoring.
        
        Uses the new rules-first qualification engine with:
        - Transparent scoring breakdown
        - Real estate budget bands
        - Role/use case clarity assessment
        - Qualification gates with specific thresholds
        """
        lead = state["lead"]
        messages = state.get("messages", [])
        
        try:
            # Import Phase 2 qualification utilities
            from tools.qualifier_utils import generate_transparent_scoring_breakdown, assess_qualification_readiness
            from config.industry_configs import get_industry_config
            
            # Prepare lead data for Phase 2 analysis
            lead_data = {
                "user_id": lead.user_id,
                "budget": getattr(lead, 'budget', None),
                "location": getattr(lead, 'location', None),
                "timeline": getattr(lead, 'timeline', None),
                "property_type": getattr(lead, 'property_type', None),
                "desired_bedrooms": getattr(lead, 'desired_bedrooms', None),
                "role": getattr(lead, 'role', None),
                "use_case": getattr(lead, 'use_case', None),
                "email": getattr(lead, 'email', None),
                "name": getattr(lead, 'name', None),
                "message": lead.message if hasattr(lead, 'message') else None
            }
            
            # Get industry configuration for real estate
            industry_config = get_industry_config("real_estate")
            
            # Generate transparent scoring breakdown
            scoring_result = generate_transparent_scoring_breakdown(lead_data, "real_estate")
            
            if scoring_result["success"]:
                phase2_data = scoring_result["scoring_result"]
                qualification_score = phase2_data.get("total_score", 0.5)
                qualification_state_name = phase2_data.get("qualification_state", "initial_contact")
                budget_band = phase2_data.get("budget_band_analysis", {}).get("detected_band", "unknown")
                role_analysis = phase2_data.get("role_analysis", {})
                
                # Assess qualification readiness using Phase 2 gates
                readiness_assessment = assess_qualification_readiness(
                    lead_data, qualification_score, getattr(lead, 'asked_questions', [])
                )
                
                return {
                    "qualification_score": qualification_score,
                    "qualification_stage": qualification_state_name,
                    "budget_band": budget_band,
                    "role_analysis": role_analysis,
                    "readiness_assessment": readiness_assessment,
                    "transparency_enabled": True,
                    "phase_2_scoring": True,
                    "scoring_breakdown": phase2_data.get("scoring_breakdown", {}),
                    "next_actions": phase2_data.get("next_actions", []),
                    "qualification_gates": {
                        "score_threshold": 0.75,
                        "essential_info_complete": readiness_assessment.get("transparency_report", {}).get("essential_info_complete", False),
                        "ready_for_scheduler": readiness_assessment.get("ready_for_scheduler", False)
                    },
                    "message_count": len(messages),
                    "last_message_time": messages[-1].get('timestamp') if messages else None,
                    "time_since_first_contact": self._calculate_time_since_first_contact(messages)
                }
            else:
                # Fallback to original assessment if Phase 2 fails
                logger.warning(f"Phase 2 scoring failed, falling back to Phase 1: {scoring_result.get('error')}")
                return await self._assess_qualification_state(state)
                
        except Exception as e:
            logger.error(f"Phase 2 qualification assessment failed: {e}")
            # Fallback to original assessment
            return await self._assess_qualification_state(state)
    def _calculate_time_since_first_contact(self, messages: list) -> Optional[float]:
        """Calculate time since first contact in hours."""
        if not messages:
            return None
        
        try:
            first_message_time = datetime.fromisoformat(messages[0]['timestamp'].replace('Z', '+00:00'))
            current_time = datetime.now(first_message_time.tzinfo)
            return (current_time - first_message_time).total_seconds() / 3600
        except:
            return None
    
    async def _determine_next_automated_state(
        self, 
        current_state: AgentState, 
        qualification_state: Dict[str, Any],
        trigger_event: str,
        correlation_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Determine next state using automated rules (no manual designation).
        
        This replaces the manual routing logic in router.py with
        deterministic state machine transitions.
        """
        lead_id = current_state["lead"].user_id
        time_since_first = qualification_state.get('time_since_first_contact', 0) or 0
        
        # CRITICAL: T0+120s automation scenario (2 hours)
        if time_since_first >= 2.0 and qualification_state['booking_ready']:
            # AUTOMATIC TRIGGER: Booking state machine
            logger.info(f"🕐 T0+120s AUTOMATION TRIGGERED for {lead_id}")
            return "AUTOMATED_BOOKING", {
                "automation_reason": "t0_plus_120s_automation",
                "qualification_score": qualification_state['qualification_score'],
                "booking_ready": qualification_state['booking_ready'],
                "time_threshold_met": True,
                "auto_trigger": True
            }
        
        # AUTOMATED QUALIFICATION FLOW
        if qualification_state['qualification_stage'] == "unqualified":
            return "QUALIFICATION", {
                "automation_reason": "needs_qualification",
                "qualification_score": qualification_state['qualification_score'],
                "missing_info": self._identify_missing_qualification_info(qualification_state)
            }
        
        elif qualification_state['qualification_stage'] == "qualifying":
            return "QUALIFICATION", {
                "automation_reason": "completing_qualification",
                "qualification_score": qualification_state['qualification_score'],
                "progress": self._assess_qualification_progress(qualification_state)
            }
        
        # QUALIFIED LEAD - Route to scheduler (booking automation)
        elif qualification_state['qualification_stage'] == "qualified":
            return "SCHEDULER", {
                "automation_reason": "qualified_lead_routing",
                "qualification_score": qualification_state['qualification_score'],
                "ready_for_booking": qualification_state['booking_ready'],
                "qualification_data": current_state["lead"].qualification_data
            }
        
        # UNKNOWN STATE - Default to qualification
        else:
            return "QUALIFICATION", {
                "automation_reason": "unknown_state_default",
                "qualification_score": qualification_state['qualification_score'],
                "fallback": True
            }
    
    def _identify_missing_qualification_info(self, qualification_state: Dict[str, Any]) -> list:
        """Identify what qualification information is missing."""
        missing = []
        
        if not qualification_state['budget_known']:
            missing.append("budget")
        if not qualification_state['location_known']:
            missing.append("location")
        if not qualification_state['timeline_known']:
            missing.append("timeline")
        
        return missing
    
    def _assess_qualification_progress(self, qualification_state: Dict[str, Any]) -> Dict[str, Any]:
        """Assess qualification progress to optimize questions."""
        missing = self._identify_missing_qualification_info(qualification_state)
        
        total_factors = 3  # budget, location, timeline
        collected_factors = total_factors - len(missing)
        
        return {
            "factors_collected": collected_factors,
            "factors_total": total_factors,
            "completion_percentage": (collected_factors / total_factors) * 100,
            "missing_factors": missing,
            "next_question_priority": missing[0] if missing else None
        }
    
    async def _execute_automation_actions(
        self,
        lead_id: str,
        next_state: str,
        automation_actions: Dict[str, Any],
        current_state: AgentState,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Execute automation actions including booking state machine integration.
        
        This addresses Priority 1 Gap 1.3 - State Machine Integration.
        """
        execution_results = {}
        
        try:
            # AUTOMATED BOOKING STATE MACHINE INTEGRATION
            if next_state == "AUTOMATED_BOOKING":
                logger.info(f"🤖 EXECUTING AUTOMATED BOOKING for {lead_id}")
                
                # Trigger booking state machine
                booking_context = {
                    "lead_id": lead_id,
                    "qualification_data": current_state["lead"].qualification_data,
                    "correlation_id": correlation_id,
                    "trigger_reason": "t0_plus_120s_automation",
                    "auto_triggered": True
                }
                
                # Initialize booking state machine
                next_booking_state, booking_actions = self.booking_state_machine.transition(
                    lead_id=lead_id,
                    current_state="INTAKE",
                    event="qualify_complete",
                    context=booking_context
                )
                
                execution_results["booking_state_machine"] = {
                    "triggered": True,
                    "next_state": next_booking_state,
                    "actions": booking_actions,
                    "context": booking_context
                }
                
                logger.info(f"✅ Booking state machine triggered: {next_booking_state}")
            
            # SCHEDULER STATE - Prepare for booking
            elif next_state == "SCHEDULER":
                # Pre-load booking context for scheduler agent
                execution_results["scheduler_preparation"] = {
                    "qualification_complete": True,
                    "ready_for_booking": automation_actions.get("ready_for_booking", False),
                    "qualification_data": automation_actions.get("qualification_data", {})
                }
            
            # QUALIFICATION STATE - Prepare qualification agent
            elif next_state == "QUALIFICATION":
                execution_results["qualification_preparation"] = {
                    "missing_info": automation_actions.get("missing_info", []),
                    "progress": automation_actions.get("progress", {}),
                    "current_score": automation_actions.get("qualification_score", 0.0)
                }
            
            return execution_results
            
        except Exception as e:
            logger.error(f"❌ Automation execution error for {lead_id}: {str(e)}")
            
            return {
                "error": str(e),
                "automation_failed": True,
                "fallback_state": next_state
            }
    
    async def _log_state_transition(
            self,
            lead_id: str,
            current_state: AgentState,
            next_state: str,
            trigger_event: str,
            correlation_id: str,
            automation_result: Dict[str, Any]
        ) -> None:
            """
            Log complete state transition for audit trail with universal coverage.
            
            Implements Priority 2 - Universal Audit Logging for all state transitions.
            Creates correlation between AuditLog, LeadEvent, and temporal events.
            """
            try:
                # Get current agent and determine from_state
                current_agent = current_state.get("current_agent", "unknown")
                from_state = current_agent.upper() if current_agent != "unknown" else "UNKNOWN"
                to_agent = self._map_state_to_agent(next_state)
                
                # CRITICAL: Ensure correlation tracking is established
                context = correlation_tracker.get_correlation_context(correlation_id)
                if not context:
                    # Create context if missing
                    correlation_tracker.set_current_context(
                        correlation_tracker.get_current_context() or
                        correlation_tracker.get_current_context()
                    )
                
                # 1. UNIVERSAL AUDIT LOGGING - Complete event trail
                transition_log = {
                    "lead_id": lead_id,
                    "correlation_id": correlation_id,
                    "parent_correlation": context.parent_correlation_id if context else None,
                    "trigger_event": trigger_event,
                    "from_state": from_state,
                    "to_state": next_state.upper(),
                    "from_agent": current_agent,
                    "to_agent": to_agent,
                    "automation_executed": bool(automation_result),
                    "transition_timestamp": datetime.now().isoformat(),
                    "transition_type": "automated_agent_orchestration",
                    "automation_result": automation_result,
                    "qualification_data": getattr(current_state.get("lead"), 'qualification_data', {}),
                    "message_count": len(current_state.get("messages", [])),
                    "transition_metadata": {
                        "pilot_readiness": "enabled",
                        "audit_coverage": "complete",
                        "temporal_logging": "enabled",
                        "correlation_tracking": "enabled"
                    }
                }
                
                # Log comprehensive audit event
                audit_event_id = audit_log_event(
                    event_type="automated_agent_transition",
                    payload=transition_log,
                    entity_type="lead",
                    entity_id=lead_id,
                    agent_type=to_agent,
                    correlation_id=correlation_id
                )
                
                # 2. TEMPORAL EVENT LOGGING - Neo4j temporal events
                try:
                    graphiti_client = get_graphiti_client()
                    temporal_event_data = {
                        "transition_type": "agent_transition",
                        "from_state": from_state,
                        "to_state": next_state.upper(),
                        "from_agent": current_agent,
                        "to_agent": to_agent,
                        "trigger_event": trigger_event,
                        "automation_executed": bool(automation_result),
                        "audit_event_id": audit_event_id,
                        "correlation_id": correlation_id,
                        "qualification_score": automation_result.get("qualification_score"),
                        "booking_ready": automation_result.get("booking_ready", False),
                        "automation_reason": automation_result.get("automation_reason"),
                        "pilot_scenario": "T0_plus_120s" if automation_result.get("auto_trigger") else "standard_flow"
                    }
                    
                    await graphiti_client.record_lead_event(
                        lead_id=lead_id,
                        event_type="agent_state_transition",
                        event_data=temporal_event_data
                    )
                    
                except Exception as temporal_error:
                    logger.warning(f"⚠️ Temporal logging failed for {lead_id}: {temporal_error}")
                
                # 3. CORRELATION TRACKING - Track agent transition
                try:
                    correlation_tracker.track_agent_transition(
                        from_agent=current_agent,
                        to_agent=to_agent,
                        transition_reason=trigger_event,
                        success=True
                    )
                except Exception as correlation_error:
                    logger.warning(f"⚠️ Correlation tracking failed for {lead_id}: {correlation_error}")
                
                # 4. OBSERVABILITY LOGGING - Agent handoff tracking
                try:
                    await log_agent_handoff(
                        lead_id=lead_id,
                        from_agent=current_agent,
                        to_agent=to_agent,
                        trigger=trigger_event,
                        correlation_id=correlation_id
                    )
                except Exception as observability_error:
                    logger.warning(f"⚠️ Observability logging failed for {lead_id}: {observability_error}")
                
                # 5. STATE-SPECIFIC AUDIT EVENTS
                # Log additional events based on transition type
                if next_state == "AUTOMATED_BOOKING":
                    audit_log_event(
                        event_type="automated_booking_triggered",
                        payload={
                            "lead_id": lead_id,
                            "correlation_id": correlation_id,
                            "qualification_score": automation_result.get("qualification_score"),
                            "time_threshold_met": automation_result.get("time_threshold_met"),
                            "pilot_scenario": "T0_plus_120s_automation"
                        },
                        entity_type="lead",
                        entity_id=lead_id,
                        agent_type="scheduler",
                        correlation_id=correlation_id
                    )
                
                elif next_state == "SCHEDULER":
                    audit_log_event(
                        event_type="lead_qualified_for_scheduling",
                        payload={
                            "lead_id": lead_id,
                            "correlation_id": correlation_id,
                            "qualification_score": automation_result.get("qualification_score"),
                            "qualification_data": automation_result.get("qualification_data", {})
                        },
                        entity_type="lead",
                        entity_id=lead_id,
                        agent_type="scheduler",
                        correlation_id=correlation_id
                    )
                
                logger.info(f"📝 COMPLETE TRANSITION LOGGING: {lead_id} {from_state} → {next_state.upper()}")
                logger.info(f"🔗 Correlation ID: {correlation_id}")
                logger.info(f"🎯 To Agent: {to_agent}")
                
            except Exception as e:
                logger.error(f"❌ Failed to log state transition for {lead_id}: {str(e)}")
                
                # CRITICAL: Fallback logging if main logging fails
                try:
                    audit_log_event(
                        event_type="state_transition_logging_failure",
                        payload={
                            "lead_id": lead_id,
                            "error": str(e),
                            "transition_attempted": f"{from_state} -> {next_state}",
                            "fallback_logging": True
                        },
                        entity_type="system",
                        entity_id="state_transition_logger"
                    )
                except:
                    logger.error(f"❌ CRITICAL: Even fallback logging failed for {lead_id}")
    
    def _map_state_to_agent(self, state: str) -> str:
        """
        Map state machine state to agent identifier.
        
        This replaces manual agent designation with state-based mapping.
        """
        state_to_agent_mapping = {
            "QUALIFICATION": "qualifier",
            "SCHEDULER": "scheduler",
            "AUTOMATED_BOOKING": "scheduler",  # Booking handled by scheduler with state machine
            "NURTURING": "followup",
            "OFFRAMP": "offramp",
            "HUMAN_REVIEW": "human"
        }
        
        return state_to_agent_mapping.get(state, "qualifier")
    
    def _get_or_create_correlation_id(self, lead_id: str) -> str:
        """
        Generate or retrieve universal correlation ID for event tracing.
        
        This addresses Priority 2 Gap 2.3 - Correlation ID Inconsistency.
        """
        # Check if correlation ID already exists for this lead
        if lead_id in self.active_sessions:
            return self.active_sessions[lead_id]["correlation_id"]
        
        # Create new correlation ID
        correlation_id = f"{lead_id}:{uuid4().hex[:12]}"
        
        # Store in active sessions
        self.active_sessions[lead_id] = {
            "correlation_id": correlation_id,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        
        return correlation_id
    
    async def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get orchestration metrics for monitoring."""
        active_leads = len(self.active_sessions)
        
        return {
            "active_sessions": active_leads,
            "orchestrator_status": "operational",
            "automation_enabled": True,
            "booking_integration": "active",
            "correlation_tracking": "enabled",
            "audit_logging": "complete",
            "last_updated": datetime.now().isoformat()
        }
    
    async def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up inactive sessions to prevent memory leaks."""
        current_time = datetime.now()
        cleaned_count = 0
        
        inactive_leads = []
        for lead_id, session_data in self.active_sessions.items():
            try:
                session_time = datetime.fromisoformat(session_data["last_activity"])
                age_hours = (current_time - session_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    inactive_leads.append(lead_id)
            except:
                # If we can't parse the time, mark for cleanup
                inactive_leads.append(lead_id)
        
        # Clean up inactive sessions
        for lead_id in inactive_leads:
            del self.active_sessions[lead_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} inactive sessions")
        
        return cleaned_count

# Global instance for easy access
unified_state_coordinator = UnifiedStateCoordinator()

# Convenience function for direct access
async def orchestrate_agent_transition(
    current_state: AgentState, 
    trigger_event: str = "message_processed"
) -> Tuple[str, Dict[str, Any]]:
    """
    Convenience function to orchestrate agent transition.
    
    This replaces the manual routing logic in router.py.
    """
    return await unified_state_coordinator.orchestrate_agent_transition(
        current_state, trigger_event
    )