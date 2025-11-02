"""
Proactive Engagement Integration Layer

This module provides integration layers for the proactive engagement system
with the existing lead processing and conversation management workflows.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from .proactive_engagement import (
    LangGraphProactiveEngagement,
    EngagementStrategy,
    EngagementState,
    ProactiveEngagementConfig
)

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Types of conversation events that can trigger proactive engagement."""
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    INACTIVITY_DETECTED = "inactivity_detected"
    QUALIFICATION_UPDATE = "qualification_update"
    ENGAGEMENT_DROP = "engagement_drop"
    INFORMATION_SHARED = "information_shared"
    INTERVENTION_RESPONSE = "intervention_response"

class ProactiveLeadProcessor:
    """
    Integration layer for proactive engagement with lead processing workflows.
    
    This class seamlessly integrates proactive engagement capabilities with
    existing lead processing systems while maintaining compatibility with
    the current LangGraph infrastructure.
    """
    
    def __init__(self, config: Optional[ProactiveEngagementConfig] = None):
        """Initialize the proactive lead processor."""
        self.config = config or ProactiveEngagementConfig()
        self.proactive_engine = LangGraphProactiveEngagement(self.config)
        self.processing_stats = {
            "total_processed": 0,
            "interventions_triggered": 0,
            "successful_interventions": 0,
            "fallback_activations": 0
        }
    
    async def process_lead_with_proactive_engagement(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        new_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process lead with proactive engagement capabilities.
        
        This method extends the standard lead processing workflow with
        proactive engagement features that can trigger based on context
        analysis and conversation patterns.
        
        Args:
            user_id: Unique identifier for the user
            current_state: Current conversation state
            new_message: Optional new message content
            
        Returns:
            Enhanced processing result with proactive engagement data
        """
        try:
            logger.info(f"Processing lead with proactive engagement for user {user_id}")
            self.processing_stats["total_processed"] += 1
            
            # Step 1: Analyze conversation context for proactive opportunities
            context_analysis = await self.proactive_engine.analyze_conversation_context(
                user_id, current_state
            )
            
            # Step 2: Check if proactive intervention should be triggered
            should_intervene = self._should_trigger_proactive_intervention(
                context_analysis, current_state
            )
            
            processing_result = {
                "user_id": user_id,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "context_analysis": context_analysis,
                "proactive_intervention_triggered": should_intervene,
                "standard_processing": True,
                "processing_stats": self.processing_stats.copy()
            }
            
            # Step 3: Generate and execute proactive intervention if needed
            if should_intervene:
                intervention = await self.proactive_engine.generate_proactive_intervention(
                    user_id, context_analysis, current_state
                )
                
                # Execute the intervention using LangGraph
                execution_result = await self.proactive_engine.execute_intervention_with_langgraph(
                    user_id, intervention, current_state
                )
                
                self.processing_stats["interventions_triggered"] += 1
                if execution_result.get("execution_status") == "success":
                    self.processing_stats["successful_interventions"] += 1
                
                processing_result.update({
                    "proactive_intervention": intervention,
                    "intervention_execution": execution_result,
                    "proactive_processing": True
                })
                
                logger.info(
                    f"Proactive intervention executed for user {user_id}: "
                    f"strategy={intervention.get('strategy')}, "
                    f"status={execution_result.get('execution_status')}"
                )
            else:
                processing_result["proactive_processing"] = False
            
            # Step 4: Update the state with new processing information
            updated_state = await self._update_state_with_proactive_data(
                current_state, context_analysis, processing_result
            )
            processing_result["updated_state"] = updated_state
            
            return processing_result
            
        except Exception as e:
            logger.error(f"Error in proactive lead processing for user {user_id}: {str(e)}")
            self.processing_stats["fallback_activations"] += 1
            
            # Return fallback processing result
            return {
                "user_id": user_id,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "fallback_processing": True,
                "context_analysis": None,
                "proactive_intervention_triggered": False,
                "standard_processing": True,
                "proactive_processing": False
            }
    
    def _should_trigger_proactive_intervention(
        self,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> bool:
        """
        Determine if proactive intervention should be triggered.
        
        This method implements intelligent decision logic for when to
        trigger proactive interventions based on context analysis.
        """
        # Check frequency limits first - this should prevent triggering if limit reached
        intervention_count = current_state.get("proactive_intervention_count", 0)
        max_interventions = self.config.max_questions_per_session  # Conservative limit
        
        if intervention_count >= max_interventions:
            logger.debug(f"Not triggering intervention - frequency limit reached: {intervention_count} >= {max_interventions}")
            return False
        
        # Check other conditions only if frequency limit is not reached
        temporal = context_analysis.get("temporal_analysis", {})
        completeness = context_analysis.get("completeness_analysis", {})
        momentum = context_analysis.get("momentum_analysis", {})
        
        # Check inactivity thresholds
        inactivity_hours = temporal.get("inactivity_duration_hours", 0)
        inactivity_threshold = self.config.inactivity_threshold_minutes / 60
        
        if inactivity_hours > inactivity_threshold:
            logger.debug(f"Triggering intervention due to inactivity: {inactivity_hours}h > {inactivity_threshold}h")
            return True
        
        # Check information completeness gaps
        critical_missing = completeness.get("critical_missing", [])
        missing_threshold = 2  # Trigger if 2+ critical fields missing
        
        if len(critical_missing) >= missing_threshold:
            logger.debug(f"Triggering intervention due to missing information: {len(critical_missing)} critical fields")
            return True
        
        # Check engagement momentum
        engagement_level = momentum.get("engagement_level", "unknown")
        
        if engagement_level == "low":
            logger.debug("Triggering intervention due to low engagement")
            return True
        
        # Check for ambiguity in recent messages
        if self._detect_ambiguity_in_recent_messages(current_state):
            logger.debug("Triggering intervention due to message ambiguity")
            return True
        
        # Check conversation stage transitions
        current_stage = momentum.get("current_stage", "unknown")
        if current_stage in ["greeting", "qualifying"] and len(critical_missing) >= 1:
            logger.debug(f"Triggering intervention for early stage conversation: {current_stage}")
            return True
        
        return False
    
    def _detect_ambiguity_in_recent_messages(self, current_state: Dict[str, Any]) -> bool:
        """Detect ambiguity patterns in recent user messages."""
        conversation_history = current_state.get("conversation_history", [])
        
        # Look at the last few messages for ambiguity indicators
        recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        
        ambiguity_indicators = [
            "maybe", "perhaps", "not sure", "not really", "not certain",
            "kind of", "sort of", "somewhat", "possibly", "probably",
            "what do you think", "i'm not sure", "maybe around",
            "not entirely sure", "not really sure", "not really certain"
        ]
        
        for message_entry in recent_messages:
            if isinstance(message_entry, dict):
                message_text = message_entry.get("message", "").lower()
                for indicator in ambiguity_indicators:
                    if indicator in message_text:
                        return True
        
        return False
    
    async def _update_state_with_proactive_data(
        self,
        current_state: Dict[str, Any],
        context_analysis: Dict[str, Any],
        processing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update state with proactive engagement data."""
        updated_state = current_state.copy()
        
        # Add context analysis to state
        updated_state["proactive_context_analysis"] = context_analysis
        updated_state["last_proactive_processing"] = datetime.utcnow().isoformat()
        
        # Increment intervention count if intervention was triggered
        if processing_result.get("proactive_intervention_triggered"):
            current_count = updated_state.get("proactive_intervention_count", 0)
            updated_state["proactive_intervention_count"] = current_count + 1
        
        # Add recommended next actions
        if "recommended_strategy" in context_analysis:
            updated_state["recommended_proactive_strategy"] = context_analysis["recommended_strategy"]
        
        # Add confidence score
        if "confidence_score" in context_analysis:
            updated_state["proactive_confidence"] = context_analysis["confidence_score"]
        
        return updated_state

class ProactiveConversationManager:
    """
    Conversation flow manager with proactive engagement capabilities.
    
    This class provides event-driven conversation management with
    automatic proactive intervention capabilities.
    """
    
    def __init__(self, config: Optional[ProactiveEngagementConfig] = None):
        """Initialize the proactive conversation manager."""
        self.config = config or ProactiveEngagementConfig()
        self.proactive_engine = LangGraphProactiveEngagement(self.config)
        self.lead_processor = ProactiveLeadProcessor(self.config)
        self.conversation_stats = {
            "events_processed": 0,
            "proactive_responses_sent": 0,
            "human_handoffs": 0,
            "successful_engagements": 0
        }
    
    async def manage_conversation_flow(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        trigger_event: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Manage conversation flow with proactive engagement capabilities.
        
        This method handles various conversation events and automatically
        triggers appropriate proactive interventions when needed.
        
        Args:
            user_id: Unique identifier for the user
            current_state: Current conversation state
            trigger_event: Event type that triggered the flow
            event_data: Additional data about the event
            
        Returns:
            Management result with proactive engagement actions
        """
        try:
            logger.info(f"Managing conversation flow for user {user_id}: event={trigger_event}")
            self.conversation_stats["events_processed"] += 1
            
            event_data = event_data or {}
            
            # Route to appropriate event handler
            if trigger_event == EventType.MESSAGE_RECEIVED.value:
                return await self._handle_message_received(user_id, current_state, event_data)
            elif trigger_event == EventType.INACTIVITY_DETECTED.value:
                return await self._handle_inactivity_detected(user_id, current_state, event_data)
            elif trigger_event == EventType.QUALIFICATION_UPDATE.value:
                return await self._handle_qualification_update(user_id, current_state, event_data)
            elif trigger_event == EventType.ENGAGEMENT_DROP.value:
                return await self._handle_engagement_drop(user_id, current_state, event_data)
            elif trigger_event == EventType.INFORMATION_SHARED.value:
                return await self._handle_information_shared(user_id, current_state, event_data)
            elif trigger_event == EventType.INTERVENTION_RESPONSE.value:
                return await self._handle_intervention_response(user_id, current_state, event_data)
            else:
                logger.warning(f"Unknown conversation event: {trigger_event}")
                return {
                    "event_handled": trigger_event,
                    "status": "unknown_event",
                    "user_id": user_id
                }
                
        except Exception as e:
            logger.error(f"Error in conversation flow management for user {user_id}: {str(e)}")
            return {
                "event_handled": trigger_event,
                "status": "error",
                "error": str(e),
                "user_id": user_id
            }
    
    async def _handle_message_received(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle message received event with proactive engagement."""
        message = event_data.get("message", "")
        
        # Update conversation history
        updated_history = current_state.get("conversation_history", [])
        updated_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "sender": "user",
            "message": message,
            "response_time": event_data.get("response_time", None)
        })
        
        # Limit history size
        if len(updated_history) > self.config.conversation_history_limit:
            updated_history = updated_history[-self.config.conversation_history_limit:]
        
        # Process the lead with proactive engagement
        processing_result = await self.lead_processor.process_lead_with_proactive_engagement(
            user_id, current_state, message
        )
        
        # Prepare result
        result = {
            "event_handled": EventType.MESSAGE_RECEIVED.value,
            "user_id": user_id,
            "processing_result": processing_result,
            "state_updates": {
                "conversation_history": updated_history,
                "last_interaction": datetime.utcnow().isoformat()
            }
        }
        
        return result
    
    async def _handle_inactivity_detected(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle inactivity detection with proactive re-engagement."""
        inactivity_duration = event_data.get("inactivity_duration_hours", 1.0)
        
        # Analyze conversation context for re-engagement opportunities
        context_analysis = await self.proactive_engine.analyze_conversation_context(
            user_id, current_state
        )
        
        # Generate re-engagement intervention
        if context_analysis.get("recommended_strategy") == EngagementStrategy.INACTIVITY_REENGAGEMENT:
            intervention = await self.proactive_engine.generate_proactive_intervention(
                user_id, context_analysis, current_state
            )
            
            # Execute the intervention
            execution_result = await self.proactive_engine.execute_intervention_with_langgraph(
                user_id, intervention, current_state
            )
            
            self.conversation_stats["proactive_responses_sent"] += 1
            
            return {
                "event_handled": EventType.INACTIVITY_DETECTED.value,
                "user_id": user_id,
                "inactivity_duration_hours": inactivity_duration,
                "inactivity_intervention": intervention,
                "execution_result": execution_result,
                "state_updates": {
                    "last_reengagement_attempt": datetime.utcnow().isoformat(),
                    "proactive_intervention_count": current_state.get("proactive_intervention_count", 0) + 1
                }
            }
        else:
            return {
                "event_handled": EventType.INACTIVITY_DETECTED.value,
                "user_id": user_id,
                "inactivity_duration_hours": inactivity_duration,
                "intervention_required": False,
                "reason": "context_analysis_did_not_recommend_reengagement"
            }
    
    async def _handle_qualification_update(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle qualification status updates with proactive follow-up."""
        old_status = event_data.get("old_status")
        new_status = event_data.get("new_status")
        
        # Generate follow-up intervention if qualification improved
        if old_status != new_status:
            context_analysis = await self.proactive_engine.analyze_conversation_context(
                user_id, current_state
            )
            
            # Generate appropriate follow-up based on new status
            if new_status == "qualified":
                intervention = await self._generate_qualification_complete_intervention(
                    user_id, context_analysis, current_state
                )
            elif new_status == "disqualified":
                intervention = await self._generate_qualification_improvement_intervention(
                    user_id, context_analysis, current_state
                )
            else:
                intervention = await self.proactive_engine.generate_proactive_intervention(
                    user_id, context_analysis, current_state
                )
            
            # Execute intervention if appropriate
            if intervention and intervention.get("should_execute", True):
                execution_result = await self.proactive_engine.execute_intervention_with_langgraph(
                    user_id, intervention, current_state
                )
                
                self.conversation_stats["successful_engagements"] += 1
                
                return {
                    "event_handled": EventType.QUALIFICATION_UPDATE.value,
                    "user_id": user_id,
                    "status_change": {"old": old_status, "new": new_status},
                    "follow_up_intervention": intervention,
                    "execution_result": execution_result,
                    "state_updates": {
                        "qualification_status": new_status,
                        "last_qualification_update": datetime.utcnow().isoformat()
                    }
                }
        
        return {
            "event_handled": EventType.QUALIFICATION_UPDATE.value,
            "user_id": user_id,
            "status_change": {"old": old_status, "new": new_status},
            "intervention_required": False
        }
    
    async def _handle_engagement_drop(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle engagement drop with proactive momentum optimization."""
        drop_magnitude = event_data.get("drop_magnitude", 0.3)
        
        # Analyze context for engagement recovery
        context_analysis = await self.proactive_engine.analyze_conversation_context(
            user_id, current_state
        )
        
        # Generate momentum optimization intervention
        intervention = await self.proactive_engine.generate_proactive_intervention(
            user_id, context_analysis, current_state
        )
        
        if intervention.get("strategy") == EngagementStrategy.MOMENTUM_OPTIMIZATION.value:
            execution_result = await self.proactive_engine.execute_intervention_with_langgraph(
                user_id, intervention, current_state
            )
            
            self.conversation_stats["proactive_responses_sent"] += 1
            
            return {
                "event_handled": EventType.ENGAGEMENT_DROP.value,
                "user_id": user_id,
                "drop_magnitude": drop_magnitude,
                "momentum_intervention": intervention,
                "execution_result": execution_result,
                "state_updates": {
                    "last_momentum_optimization": datetime.utcnow().isoformat()
                }
            }
        
        return {
            "event_handled": EventType.ENGAGEMENT_DROP.value,
            "user_id": user_id,
            "drop_magnitude": drop_magnitude,
            "intervention_required": False
        }
    
    async def _handle_information_shared(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle new information sharing with proactive next steps."""
        shared_information = event_data.get("information", {})
        information_type = event_data.get("type", "unknown")
        
        # Generate context-aware suggestions based on new information
        context_analysis = await self.proactive_engine.analyze_conversation_context(
            user_id, current_state
        )
        
        if information_type in ["budget", "location", "timeline", "property_type"]:
            # Generate next-step suggestions
            intervention = await self.proactive_engine.generate_proactive_intervention(
                user_id, context_analysis, current_state
            )
            
            if intervention.get("strategy") == EngagementStrategy.CONTEXT_AWARE_SUGGESTION.value:
                execution_result = await self.proactive_engine.execute_intervention_with_langgraph(
                    user_id, intervention, current_state
                )
                
                return {
                    "event_handled": EventType.INFORMATION_SHARED.value,
                    "user_id": user_id,
                    "information_type": information_type,
                    "suggestion_intervention": intervention,
                    "execution_result": execution_result
                }
        
        return {
            "event_handled": EventType.INFORMATION_SHARED.value,
            "user_id": user_id,
            "information_type": information_type,
            "intervention_required": False
        }
    
    async def _handle_intervention_response(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle user responses to proactive interventions."""
        intervention_id = event_data.get("intervention_id")
        user_response = event_data.get("response")
        engagement_improved = event_data.get("engagement_improved", False)
        
        # Monitor the intervention response
        response_monitoring_result = await self.proactive_engine.monitor_intervention_response(
            user_id, intervention_id, event_data
        )
        
        # Update engagement statistics
        if engagement_improved:
            self.conversation_stats["successful_engagements"] += 1
        
        return {
            "event_handled": EventType.INTERVENTION_RESPONSE.value,
            "user_id": user_id,
            "intervention_id": intervention_id,
            "response_monitoring": response_monitoring_result,
            "engagement_improved": engagement_improved
        }
    
    async def _generate_qualification_complete_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate intervention for qualification completion."""
        return {
            "user_id": user_id,
            "strategy": "qualification_complete",
            "approach": "celebration_and_next_steps",
            "message_style": "enthusiastic",
            "immediate_value": True,
            "content_type": "qualification_complete",
            "qualification_complete": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "qualification_complete",
            "should_execute": True
        }
    
    async def _generate_qualification_improvement_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate intervention for qualification improvement."""
        return {
            "strategy": "qualification_improvement",
            "approach": "encouragement_and_guidance",
            "message_style": "supportive",
            "immediate_value": True,
            "action_type": "qualification_improvement",
            "should_execute": True
        }

# Global instances for convenience
proactive_lead_processor = ProactiveLeadProcessor()
proactive_conversation_manager = ProactiveConversationManager()

# Convenience functions for easy integration
async def process_lead_with_proactive_engagement(
    user_id: str,
    current_state: Dict[str, Any],
    new_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for processing leads with proactive engagement.
    
    This function provides a simple interface for integrating proactive
    engagement with existing lead processing workflows.
    """
    return await proactive_lead_processor.process_lead_with_proactive_engagement(
        user_id, current_state, new_message
    )

async def manage_proactive_conversation_flow(
    user_id: str,
    current_state: Dict[str, Any],
    trigger_event: str,
    event_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function for managing conversation flow with proactive engagement.
    
    This function provides a simple interface for handling various conversation
    events with automatic proactive intervention capabilities.
    """
    return await proactive_conversation_manager.manage_conversation_flow(
        user_id, current_state, trigger_event, event_data
    )

async def get_proactive_engagement_stats() -> Dict[str, Any]:
    """
    Get comprehensive proactive engagement statistics.
    
    Returns statistics from both the lead processor and conversation manager
    to provide insights into proactive engagement effectiveness.
    """
    return {
        "lead_processor_stats": proactive_lead_processor.processing_stats,
        "conversation_manager_stats": proactive_conversation_manager.conversation_stats,
        "combined_metrics": {
            "total_interventions": (
                proactive_lead_processor.processing_stats["interventions_triggered"] +
                proactive_conversation_manager.conversation_stats["proactive_responses_sent"]
            ),
            "successful_interventions": (
                proactive_lead_processor.processing_stats["successful_interventions"] +
                proactive_conversation_manager.conversation_stats["successful_engagements"]
            ),
            "fallback_rate": (
                proactive_lead_processor.processing_stats["fallback_activations"] /
                max(proactive_lead_processor.processing_stats["total_processed"], 1)
            )
        }
    }

# Export key classes and functions
__all__ = [
    "ProactiveLeadProcessor",
    "ProactiveConversationManager",
    "process_lead_with_proactive_engagement",
    "manage_proactive_conversation_flow",
    "get_proactive_engagement_stats",
    "EventType"
]