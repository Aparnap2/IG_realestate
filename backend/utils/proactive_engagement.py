"""
Simplified Proactive Engagement System - Pure Agentic AI Version

This module provides proactive engagement capabilities using simple rule-based patterns
instead of complex ML-like sentiment analysis and pattern recognition.

Features:
- Simple rule-based conversation analysis
- Basic proactive engagement strategies
- LangGraph state management integration
- Rule-based threshold monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

class EngagementStrategy(Enum):
    """Simple proactive engagement strategies."""
    INACTIVITY_REENGAGEMENT = "inactivity_reengagement"
    BASIC_FOLLOWUP = "basic_followup"
    SIMPLE_CLARIFICATION = "simple_clarification"

class ProactiveEngagementConfig:
    """Configuration for simplified proactive engagement."""
    
    def __init__(self):
        # Simple thresholds
        self.inactivity_threshold_minutes = 30
        self.max_followups_per_hour = 2
        
        # Simple re-engagement delays
        self.reengagement_delay_hours = [1, 24, 72]
        
        # Conversation limits
        self.conversation_history_limit = 20
        self.context_window_messages = 5
        
        # Engagement patterns (simplified)
        self.engagement_patterns = {
            "inactivity_patterns": {
                "short_gap": {"threshold_hours": 2, "approach": "gentle_reminder"},
                "medium_gap": {"threshold_hours": 24, "approach": "value_reminder"},
                "long_gap": {"threshold_hours": float('inf'), "approach": "renewed_engagement"}
            },
            "simple_triggers": {
                "no_response": "ask_followup_question",
                "incomplete_info": "request_missing_info",
                "stalled_conversation": "offer_help"
            }
        }

class SimpleProactiveEngagement:
    """
    Simplified proactive engagement engine using rule-based patterns.
    
    Pure agentic AI approach - no ML or complex sentiment analysis.
    """
    
    def __init__(self, config: ProactiveEngagementConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.followup_counts = {}  # Track followup attempts
        self.conversation_contexts = {}
        
    async def analyze_conversation_context(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Simple conversation context analysis using basic rules.
        
        Args:
            user_id: Unique identifier for the user
            current_state: Current conversation state
            conversation_history: Optional conversation history
            
        Returns:
            Simple context analysis with recommendations
        """
        try:
            # Store context
            self.conversation_contexts[user_id] = {
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "current_state": current_state,
                "conversation_history": conversation_history or []
            }
            
            # Simple temporal analysis
            temporal_analysis = await self._simple_temporal_analysis(current_state, conversation_history)
            
            # Simple engagement analysis
            engagement_analysis = await self._simple_engagement_analysis(current_state, conversation_history)
            
            # Simple completeness analysis
            completeness_analysis = await self._simple_completeness_analysis(current_state, conversation_history)
            
            # Simple strategy recommendation
            strategy = self._determine_simple_strategy(temporal_analysis, engagement_analysis, completeness_analysis)
            
            context_analysis = {
                "user_id": user_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "temporal_analysis": temporal_analysis,
                "engagement_analysis": engagement_analysis,
                "completeness_analysis": completeness_analysis,
                "recommended_strategy": strategy,
                "simple_mode": True
            }
            
            self.logger.info(f"Simple context analysis for user {user_id}: strategy={strategy.value}")
            
            return context_analysis
            
        except Exception as e:
            self.logger.error(f"Error in simple conversation analysis: {str(e)}")
            return await self._create_simple_fallback_analysis(user_id, current_state)
    
    async def generate_proactive_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate simple proactive intervention.
        
        Args:
            user_id: Unique identifier for the user
            context_analysis: Context analysis results
            current_state: Current conversation state
            
        Returns:
            Simple intervention configuration
        """
        try:
            strategy = context_analysis.get("recommended_strategy", EngagementStrategy.BASIC_FOLLOWUP)
            
            if strategy == EngagementStrategy.INACTIVITY_REENGAGEMENT:
                return await self._generate_simple_inactivity_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.SIMPLE_CLARIFICATION:
                return await self._generate_simple_clarification_intervention(user_id, context_analysis, current_state)
            else:
                return await self._generate_simple_followup_intervention(user_id, context_analysis, current_state)
                
        except Exception as e:
            self.logger.error(f"Error generating simple intervention: {str(e)}")
            return {
                "user_id": user_id,
                "strategy": EngagementStrategy.BASIC_FOLLOWUP.value,
                "approach": "simple_fallback",
                "intervention_timestamp": datetime.utcnow().isoformat(),
                "trigger_reason": "fallback_generation"
            }
    
    async def execute_simple_intervention(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute simple intervention with basic monitoring.
        
        Args:
            user_id: Unique identifier for the user
            intervention: Intervention configuration
            current_state: Current conversation state
            
        Returns:
            Execution result
        """
        try:
            # Simple intervention tracking
            if user_id not in self.followup_counts:
                self.followup_counts[user_id] = 0
            
            self.followup_counts[user_id] += 1
            
            # Simple execution
            intervention_result = {
                "executed": True,
                "intervention_type": intervention.get("strategy", "unknown"),
                "timestamp": datetime.utcnow().isoformat(),
                "followup_attempt": self.followup_counts[user_id]
            }
            
            # Simple state update
            updated_state = current_state.copy()
            updated_state["simple_intervention_executed"] = {
                "strategy": intervention.get("strategy"),
                "timestamp": intervention.get("intervention_timestamp"),
                "attempt_count": self.followup_counts[user_id]
            }
            
            return {
                "execution_status": "success",
                "intervention_result": intervention_result,
                "updated_state": updated_state,
                "simple_mode": True
            }
            
        except Exception as e:
            self.logger.error(f"Error executing simple intervention: {str(e)}")
            return {
                "execution_status": "failed",
                "error": str(e),
                "simple_mode": True
            }
    
    # Simple analysis methods
    async def _simple_temporal_analysis(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Simple temporal analysis using basic rules."""
        try:
            history = conversation_history or []
            
            if not history:
                return {
                    "inactivity_hours": 0,
                    "pattern": "new_conversation",
                    "needs_followup": False
                }
            
            # Find last user message
            last_user_message = None
            for msg in reversed(history):
                if msg.get("role") == "user" and msg.get("timestamp"):
                    try:
                        last_user_message = datetime.fromisoformat(msg["timestamp"])
                        break
                    except (ValueError, TypeError):
                        continue
            
            if last_user_message:
                hours_since = (datetime.utcnow() - last_user_message).total_seconds() / 3600
                hours_since = max(0, hours_since)
            else:
                hours_since = 0
            
            # Simple pattern determination
            if hours_since < 1:
                pattern = "recent"
                needs_followup = False
            elif hours_since < 24:
                pattern = "short_gap"
                needs_followup = hours_since > (self.config.inactivity_threshold_minutes / 60)
            else:
                pattern = "long_gap"
                needs_followup = True
            
            return {
                "inactivity_hours": hours_since,
                "pattern": pattern,
                "needs_followup": needs_followup
            }
            
        except Exception as e:
            self.logger.error(f"Error in simple temporal analysis: {str(e)}")
            return {
                "inactivity_hours": 0,
                "pattern": "unknown",
                "needs_followup": False
            }
    
    async def _simple_engagement_analysis(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Simple engagement analysis using basic rules."""
        try:
            history = conversation_history or []
            
            user_messages = [msg for msg in history if msg.get("role") == "user"]
            message_count = len(user_messages)
            
            # Simple engagement scoring
            engagement_score = 0
            
            if message_count >= 1:
                engagement_score += 0.3  # Base engagement
            if message_count >= 3:
                engagement_score += 0.3  # Multiple interactions
            if message_count >= 5:
                engagement_score += 0.2  # Extended conversation
            
            # Check for questions (indicator of engagement)
            question_count = sum(1 for msg in user_messages if "?" in msg.get("content", ""))
            if question_count > 0:
                engagement_score += 0.2
            
            engagement_score = min(1.0, engagement_score)
            
            # Simple engagement level
            if engagement_score >= 0.7:
                engagement_level = "high"
            elif engagement_score >= 0.4:
                engagement_level = "medium"
            else:
                engagement_level = "low"
            
            return {
                "engagement_score": engagement_score,
                "engagement_level": engagement_level,
                "message_count": message_count,
                "question_count": question_count
            }
            
        except Exception as e:
            self.logger.error(f"Error in simple engagement analysis: {str(e)}")
            return {
                "engagement_score": 0.0,
                "engagement_level": "unknown",
                "message_count": 0,
                "question_count": 0
            }
    
    async def _simple_completeness_analysis(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Simple completeness analysis using basic rules."""
        try:
            lead_info = current_state.get("lead", {})
            
            # Simple required fields
            required_fields = ["budget", "location", "timeline"]
            provided_fields = []
            
            for field in required_fields:
                value = lead_info.get(field)
                if value is not None and value != "" and value != "None":
                    provided_fields.append(field)
            
            completeness_score = len(provided_fields) / len(required_fields)
            
            # Simple gaps identification
            missing_critical = [field for field in required_fields if field not in provided_fields]
            
            return {
                "completeness_score": completeness_score,
                "missing_critical": missing_critical,
                "fields_provided": provided_fields,
                "needs_info": len(missing_critical) > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error in simple completeness analysis: {str(e)}")
            return {
                "completeness_score": 0.0,
                "missing_critical": [],
                "needs_info": True
            }
    
    def _determine_simple_strategy(
        self,
        temporal_analysis: Dict[str, Any],
        engagement_analysis: Dict[str, Any],
        completeness_analysis: Dict[str, Any]
    ) -> EngagementStrategy:
        """Determine simple strategy using basic rules."""
        try:
            # Check followup limits
            user_id = temporal_analysis.get("user_id", "unknown")
            if user_id in self.followup_counts:
                if self.followup_counts[user_id] >= self.config.max_followups_per_hour:
                    return EngagementStrategy.BASIC_FOLLOWUP  # Limit reached
            
            # Inactivity-based strategy
            if temporal_analysis.get("needs_followup", False):
                return EngagementStrategy.INACTIVITY_REENGAGEMENT
            
            # Information completion strategy
            if completeness_analysis.get("needs_info", False):
                return EngagementStrategy.SIMPLE_CLARIFICATION
            
            # Default to basic followup
            return EngagementStrategy.BASIC_FOLLOWUP
            
        except Exception as e:
            self.logger.error(f"Error determining simple strategy: {str(e)}")
            return EngagementStrategy.BASIC_FOLLOWUP
    
    # Simple intervention generators
    async def _generate_simple_inactivity_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate simple inactivity intervention."""
        temporal = context_analysis.get("temporal_analysis", {})
        pattern = temporal.get("pattern", "unknown")
        
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.INACTIVITY_REENGAGEMENT.value,
            "approach": f"{pattern}_reengagement",
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": f"inactivity_{pattern}",
            "simple_mode": True
        }
    
    async def _generate_simple_clarification_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate simple clarification intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.SIMPLE_CLARIFICATION.value,
            "approach": "request_missing_info",
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "missing_information",
            "simple_mode": True
        }
    
    async def _generate_simple_followup_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate simple followup intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.BASIC_FOLLOWUP.value,
            "approach": "simple_followup",
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "basic_followup",
            "simple_mode": True
        }
    
    async def _create_simple_fallback_analysis(
        self,
        user_id: str,
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create simple fallback analysis."""
        return {
            "user_id": user_id,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "temporal_analysis": {
                "inactivity_hours": 0,
                "pattern": "unknown",
                "needs_followup": False
            },
            "engagement_analysis": {
                "engagement_score": 0.0,
                "engagement_level": "unknown",
                "message_count": 0
            },
            "completeness_analysis": {
                "completeness_score": 0.0,
                "missing_critical": [],
                "needs_info": True
            },
            "recommended_strategy": EngagementStrategy.BASIC_FOLLOWUP,
            "simple_mode": True,
            "fallback": True
        }

# Global simple proactive engagement instance
def get_simple_proactive_engine(config: Optional[ProactiveEngagementConfig] = None) -> SimpleProactiveEngagement:
    """Get simple proactive engagement engine."""
    config = config or ProactiveEngagementConfig()
    return SimpleProactiveEngagement(config)

# Export key functions
__all__ = [
    "SimpleProactiveEngagement",
    "ProactiveEngagementConfig", 
    "EngagementStrategy",
    "get_simple_proactive_engine"
]