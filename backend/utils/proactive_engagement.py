"""
LangGraph-Enhanced Proactive Engagement System

This module provides sophisticated proactive engagement capabilities for conversation
management, including context analysis, intervention generation, and execution with
LangGraph state management integration.

Features:
- Intelligent conversation context analysis
- Six distinct proactive engagement strategies
- LangGraph state management integration
- Fallback mechanisms for when LangGraph is unavailable
- Response monitoring and effectiveness analysis
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import re

# Optional LangGraph imports with graceful fallback
try:
    from langgraph import StateGraph, END
    from langgraph.checkpoint.redis import RedisSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = None
    RedisSaver = None
    LANGGRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)

class EngagementStrategy(Enum):
    """Available proactive engagement strategies."""
    INACTIVITY_REENGAGEMENT = "inactivity_reengagement"
    PROGRESSIVE_DISCLOSURE = "progressive_disclosure"
    CONTEXT_AWARE_SUGGESTION = "context_aware_suggestion"
    PERSONALIZED_FOLLOWUP = "personalized_followup"
    AMBIGUITY_CLARIFICATION = "ambiguity_clarification"
    MOMENTUM_OPTIMIZATION = "momentum_optimization"

class EngagementState(Enum):
    """Conversation states for proactive engagement."""
    INITIAL = "initial"
    ACTIVE = "active"
    INACTIVE = "inactive"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    FOLLOWING_UP = "following_up"
    CLOSING = "closing"

@dataclass
class ProactiveEngagementConfig:
    """Configuration for proactive engagement system."""
    # Core thresholds
    inactivity_threshold_minutes: int = 30
    reengagement_attempts: int = 3
    max_questions_per_session: int = 5
    
    # Re-engagement timing (hours between attempts)
    reengagement_delay_hours: List[int] = field(default_factory=lambda: [1, 24, 72])
    
    # Progressive disclosure levels
    disclosure_levels: List[str] = field(
        default_factory=lambda: ["basic", "detailed", "comprehensive", "full"]
    )
    
    # Personalization features
    personalization_features: List[str] = field(
        default_factory=lambda: ["greeting_style", "question_format", "follow_up_timing", "content_style", "engagement_approach"]
    )
    
    # Conversation limits
    conversation_history_limit: int = 50
    context_window_messages: int = 10
    
    # LangGraph integration
    checkpoint_retention_days: int = 7
    state_update_frequency: str = "real_time"
    human_in_the_loop_enabled: bool = True
    
    # Engagement patterns for different scenarios
    engagement_patterns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default engagement patterns."""
        if not self.engagement_patterns:
            self.engagement_patterns = self._create_default_patterns()
    
    def _create_default_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Create default engagement patterns."""
        return {
            "inactivity_patterns": {
                "short_gap": {
                    "duration_hours": (0.5, 2),
                    "approach": "gentle_reminder",
                    "message_style": "warm",
                    "urgency": "low"
                },
                "medium_gap": {
                    "duration_hours": (2, 24),
                    "approach": "value_reminder",
                    "message_style": "helpful",
                    "urgency": "medium"
                },
                "long_gap": {
                    "duration_hours": (24, float('inf')),
                    "approach": "renewed_engagement",
                    "message_style": "enthusiastic",
                    "urgency": "high"
                }
            },
            "ambiguity_patterns": {
                "unclear_request": {
                    "triggers": ["not sure", "maybe", "perhaps", "kind of", "sort of"],
                    "approach": "clarification",
                    "style": "clarifying"
                },
                "partial_information": {
                    "triggers": ["around", "approximately", "roughly", "somewhat"],
                    "approach": "progressive_disclosure",
                    "style": "guidance"
                }
            },
            "momentum_patterns": {
                "high_engagement": {
                    "indicators": ["quick_responses", "detailed_questions"],
                    "approach": "accelerate",
                    "style": "dynamic"
                },
                "low_engagement": {
                    "indicators": ["slow_responses", "short_messages"],
                    "approach": "energize",
                    "style": "motivating"
                },
                "declining_engagement": {
                    "indicators": ["increasing_gaps", "vague_responses"],
                    "approach": "recapture",
                    "style": "reassuring"
                }
            },
            "personalization_factors": {
                "time_based": {
                    "morning": {"greeting": "Good morning!", "energy": "high"},
                    "afternoon": {"greeting": "Good afternoon!", "energy": "medium"},
                    "evening": {"greeting": "Good evening!", "energy": "calm"}
                },
                "engagement_level": {
                    "high": {"questions_per_session": 3, "delay_minutes": 5},
                    "medium": {"questions_per_session": 2, "delay_minutes": 10},
                    "low": {"questions_per_session": 1, "delay_minutes": 15}
                }
            }
        }

class LangGraphProactiveEngagement:
    """
    Main proactive engagement engine with LangGraph integration.
    
    This class provides comprehensive proactive engagement capabilities including:
    - Conversation context analysis
    - Proactive intervention generation
    - Intervention execution with LangGraph state management
    - Response monitoring and optimization
    """
    
    def __init__(self, config: ProactiveEngagementConfig):
        """Initialize the proactive engagement engine."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.conversation_contexts = {}
        self.intervention_history = {}
        self.redis_client = None
        # Make engagement patterns accessible for tests
        self.engagement_patterns = config.engagement_patterns
        self._initialize_langgraph_components()
    
    def _initialize_langgraph_components(self):
        """Initialize LangGraph components if available."""
        if LANGGRAPH_AVAILABLE:
            try:
                # Initialize checkpointer for Redis
                self.redis_client = RedisSaver(redis_url="redis://localhost:6379/0")
                self.checkpointer = self.redis_client
                self.logger.info("✅ LangGraph checkpointer initialized successfully")
            except Exception as e:
                self.logger.warning(f"⚠️ LangGraph initialization failed: {str(e)}")
                self.checkpointer = None
        else:
            self.logger.info("📦 LangGraph not available - using fallback mode")
            self.checkpointer = None
    
    async def analyze_conversation_context(
        self,
        user_id: str,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze conversation context to determine proactive engagement opportunities.
        
        This method performs comprehensive analysis of the conversation context
        including temporal patterns, engagement momentum, information completeness,
        and recommendation of appropriate proactive strategies.
        
        Args:
            user_id: Unique identifier for the user
            current_state: Current conversation state
            conversation_history: Optional conversation history for context
            
        Returns:
            Comprehensive context analysis with recommendations
        """
        try:
            # Store context for future reference
            self.conversation_contexts[user_id] = {
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "current_state": current_state,
                "conversation_history": conversation_history or []
            }
            
            # Perform temporal analysis
            temporal_analysis = await self._analyze_temporal_patterns(
                current_state, conversation_history
            )
            
            # Analyze engagement momentum
            momentum_analysis = await self._analyze_engagement_momentum(
                current_state, conversation_history
            )
            
            # Assess information completeness
            completeness_analysis = await self._analyze_information_completeness(
                current_state, conversation_history
            )
            
            # Determine recommended strategy
            recommended_strategy = self._determine_recommended_strategy(
                temporal_analysis, momentum_analysis, completeness_analysis
            )
            
            # Calculate confidence score with robust error handling
            try:
                confidence_score = self._calculate_confidence_score(
                    temporal_analysis, momentum_analysis, completeness_analysis
                )
            except Exception as e:
                self.logger.error(f"Error calculating confidence score: {str(e)}")
                confidence_score = 0.5  # Safe default
            
            context_analysis = {
                "user_id": user_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "temporal_analysis": temporal_analysis,
                "momentum_analysis": momentum_analysis,
                "completeness_analysis": completeness_analysis,
                "recommended_strategy": recommended_strategy,
                "confidence_score": confidence_score,
                "fallback_mode": not LANGGRAPH_AVAILABLE
            }
            
            self.logger.info(f"📊 Context analysis completed for user {user_id}: "
                           f"strategy={recommended_strategy.value}, confidence={confidence_score:.2f}")
            
            return context_analysis
            
        except Exception as e:
            self.logger.error(f"Error in conversation context analysis: {str(e)}")
            # Return fallback analysis
            return await self._create_fallback_analysis(user_id, current_state)
    
    async def generate_proactive_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate proactive intervention based on context analysis.
        
        Args:
            user_id: Unique identifier for the user
            context_analysis: Context analysis results
            current_state: Current conversation state
            
        Returns:
            Proactive intervention configuration
        """
        try:
            strategy = context_analysis.get("recommended_strategy", EngagementStrategy.CONTEXT_AWARE_SUGGESTION)
            
            if strategy == EngagementStrategy.INACTIVITY_REENGAGEMENT:
                return await self._generate_inactivity_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.PROGRESSIVE_DISCLOSURE:
                return await self._generate_progressive_disclosure_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.CONTEXT_AWARE_SUGGESTION:
                return await self._generate_context_aware_suggestion_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.PERSONALIZED_FOLLOWUP:
                return await self._generate_personalized_followup_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.AMBIGUITY_CLARIFICATION:
                return await self._generate_ambiguity_clarification_intervention(user_id, context_analysis, current_state)
            elif strategy == EngagementStrategy.MOMENTUM_OPTIMIZATION:
                return await self._generate_momentum_optimization_intervention(user_id, context_analysis, current_state)
            else:
                return await self._generate_context_aware_suggestion_intervention(user_id, context_analysis, current_state)
                
        except Exception as e:
            self.logger.error(f"Error generating proactive intervention: {str(e)}")
            return await self._generate_fallback_intervention(user_id, context_analysis, current_state)
    
    async def execute_intervention_with_langgraph(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute intervention using LangGraph state management.
        
        Args:
            user_id: Unique identifier for the user
            intervention: Intervention configuration
            current_state: Current conversation state
            
        Returns:
            Execution result with status and updated state
        """
        try:
            # Create intervention checkpoint
            checkpoint_id = await self._create_intervention_checkpoint(user_id, intervention, current_state)
            
            # Execute the intervention strategy
            intervention_result = await self._execute_intervention_strategy(
                user_id, intervention, current_state
            )
            
            # Update LangGraph state
            updated_state = await self._update_langgraph_state(
                user_id, intervention, intervention_result, current_state
            )
            
            return {
                "execution_status": "success",
                "checkpoint_id": checkpoint_id,
                "intervention_result": intervention_result,
                "updated_state": updated_state,
                "execution_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error executing intervention: {str(e)}")
            return await self._handle_intervention_failure(user_id, intervention, current_state, str(e))
    
    async def monitor_intervention_response(
        self,
        user_id: str,
        intervention_id: str,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Monitor and analyze intervention response effectiveness.
        
        Args:
            user_id: Unique identifier for the user
            intervention_id: ID of the intervention to monitor
            response_data: User response data
            
        Returns:
            Response analysis and effectiveness metrics
        """
        try:
            # Retrieve intervention checkpoint
            checkpoint_state = await self._retrieve_intervention_checkpoint(user_id, intervention_id)
            
            # Analyze response effectiveness
            response_analysis = await self._analyze_response_effectiveness(
                response_data, checkpoint_state
            )
            
            # Update monitoring state
            await self._update_langgraph_monitoring_state(
                user_id, intervention_id, response_data, response_analysis
            )
            
            return {
                "user_id": user_id,
                "intervention_id": intervention_id,
                "response_analysis": response_analysis,
                "adjustment_needed": response_analysis.get("adjustment_needed", False),
                "monitoring_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error monitoring intervention response: {str(e)}")
            return {
                "user_id": user_id,
                "intervention_id": intervention_id,
                "response_analysis": {"error": str(e)},
                "adjustment_needed": True,
                "monitoring_timestamp": datetime.utcnow().isoformat()
            }
    
    # Analysis helper methods
    async def _analyze_temporal_patterns(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze temporal patterns in the conversation."""
        try:
            now = datetime.utcnow()
            history = conversation_history or current_state.get("conversation_history", [])
            
            if not history:
                return {
                    "inactivity_duration_hours": 0,
                    "pattern": "new_conversation",
                    "last_interaction_time": None,
                    "frequency_score": 0.0,
                    "temporal_signals": []
                }
            
            # Calculate inactivity duration
            last_interaction = None
            for msg in reversed(history):
                if "timestamp" in msg:
                    try:
                        last_interaction = datetime.fromisoformat(msg["timestamp"])
                        break
                    except (ValueError, TypeError):
                        continue
            
            if last_interaction:
                inactivity_duration = (now - last_interaction).total_seconds() / 3600
                # Ensure non-negative value
                inactivity_duration = max(0, inactivity_duration)
            else:
                inactivity_duration = 0
            
            # Determine temporal pattern
            if inactivity_duration < 0.5:  # 30 minutes
                pattern = "active"
            elif inactivity_duration < 2:
                pattern = "short_gap"
            elif inactivity_duration < 24:
                pattern = "medium_gap"
            else:
                pattern = "long_gap"
            
            # Calculate response frequency
            response_times = []
            for i in range(1, len(history)):
                if "timestamp" in history[i] and "timestamp" in history[i-1]:
                    try:
                        time_diff = (datetime.fromisoformat(history[i]["timestamp"]) - 
                                   datetime.fromisoformat(history[i-1]["timestamp"])).total_seconds()
                        response_times.append(time_diff)
                    except (ValueError, TypeError):
                        continue
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            frequency_score = min(1.0, 3600 / max(avg_response_time, 1))  # Normalize to 0-1
            
            # Identify temporal signals
            temporal_signals = []
            if inactivity_duration > self.config.inactivity_threshold_minutes / 60:
                temporal_signals.append("high_inactivity")
            if frequency_score > 0.7:
                temporal_signals.append("high_frequency")
            elif frequency_score < 0.3:
                temporal_signals.append("low_frequency")
            
            return {
                "inactivity_duration_hours": inactivity_duration,
                "pattern": pattern,
                "last_interaction_time": last_interaction.isoformat() if last_interaction else None,
                "frequency_score": frequency_score,
                "temporal_signals": temporal_signals,
                "response_time_analysis": {
                    "average_response_time_hours": avg_response_time / 3600,
                    "response_variance": self._calculate_variance(response_times) if response_times else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in temporal pattern analysis: {str(e)}")
            return {
                "inactivity_duration_hours": 0,
                "pattern": "unknown",
                "frequency_score": 0.0,
                "temporal_signals": []
            }
    
    async def _analyze_engagement_momentum(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze engagement momentum and patterns."""
        try:
            history = conversation_history or current_state.get("conversation_history", [])
            
            if len(history) < 3:
                return {
                    "engagement_level": "insufficient_data",
                    "current_stage": "initial",
                    "momentum_direction": "unknown",
                    "engagement_score": 0.0
                }
            
            # Analyze recent messages for engagement indicators
            recent_messages = history[-10:] if len(history) > 10 else history
            
            # Calculate message characteristics
            user_messages = [msg for msg in recent_messages if msg.get("sender") == "user"]
            assistant_messages = [msg for msg in recent_messages if msg.get("sender") == "assistant"]
            
            # Engagement indicators
            message_lengths = [len(msg.get("message", "")) for msg in user_messages]
            avg_user_message_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0
            
            # Response time analysis
            response_times = []
            for i in range(1, len(recent_messages)):
                if "timestamp" in recent_messages[i] and "timestamp" in recent_messages[i-1]:
                    try:
                        time_diff = (datetime.fromisoformat(recent_messages[i]["timestamp"]) - 
                                   datetime.fromisoformat(recent_messages[i-1]["timestamp"])).total_seconds()
                        response_times.append(time_diff)
                    except (ValueError, TypeError):
                        continue
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Question frequency
            question_count = sum(1 for msg in user_messages if "?" in msg.get("message", ""))
            question_ratio = question_count / len(user_messages) if user_messages else 0
            
            # Determine engagement level
            engagement_score = 0
            if avg_user_message_length > 50:  # Substantial messages
                engagement_score += 0.3
            if avg_response_time < 3600:  # Response within 1 hour
                engagement_score += 0.3
            if question_ratio > 0.3:  # High question frequency
                engagement_score += 0.2
            if len(user_messages) > 5:  # Multiple exchanges
                engagement_score += 0.2
            
            if engagement_score > 0.7:
                engagement_level = "high"
            elif engagement_score > 0.4:
                engagement_level = "medium"
            else:
                engagement_level = "low"
            
            # Determine conversation stage
            current_stage = self._determine_conversation_stage(
                current_state, len(user_messages), engagement_score
            )
            
            # Determine momentum direction
            momentum_direction = self._analyze_momentum_direction(recent_messages)
            
            return {
                "engagement_level": engagement_level,
                "current_stage": current_stage,
                "momentum_direction": momentum_direction,
                "engagement_score": engagement_score,
                "message_analysis": {
                    "total_messages": len(recent_messages),
                    "user_message_count": len(user_messages),
                    "average_user_message_length": avg_user_message_length,
                    "question_ratio": question_ratio,
                    "average_response_time_hours": avg_response_time / 3600
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in engagement momentum analysis: {str(e)}")
            return {
                "engagement_level": "unknown",
                "current_stage": "unknown",
                "momentum_direction": "unknown",
                "engagement_score": 0.0
            }
    
    async def _analyze_information_completeness(
        self,
        current_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze information completeness for qualification."""
        try:
            lead_info = current_state.get("lead", {})
            
            # Define required fields for real estate qualification
            required_fields = [
                "budget", "location", "property_type", "timeline", "desired_bedrooms"
            ]
            
            # Check completeness
            completeness_scores = {}
            critical_missing = []
            all_missing = []
            
            for field in required_fields:
                value = lead_info.get(field)
                if value is None or value == "" or value == "None":
                    all_missing.append(field)
                    if field in ["budget", "location", "timeline"]:  # Critical fields
                        critical_missing.append(field)
                    completeness_scores[field] = 0
                else:
                    completeness_scores[field] = 1
            
            # Calculate overall completeness
            filled_fields = len(required_fields) - len(all_missing)
            overall_completeness = filled_fields / len(required_fields)
            
            # Identify information gaps
            information_gaps = []
            for field in critical_missing:
                information_gaps.append({
                    "field": field,
                    "priority": "critical",
                    "impact": "high"
                })
            
            for field in [f for f in all_missing if f not in critical_missing]:
                information_gaps.append({
                    "field": field,
                    "priority": "low",
                    "impact": "medium"
                })
            
            return {
                "completeness_score": overall_completeness,
                "critical_missing": critical_missing,
                "all_missing": all_missing,
                "information_gaps": information_gaps,
                "field_scores": completeness_scores,
                "qualification_readiness": self._assess_qualification_readiness(
                    overall_completeness, critical_missing
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error in information completeness analysis: {str(e)}")
            return {
                "completeness_score": 0.0,
                "critical_missing": [],
                "all_missing": [],
                "information_gaps": []
            }
    
    # Intervention generation methods
    async def _generate_inactivity_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate inactivity re-engagement intervention."""
        temporal = context_analysis["temporal_analysis"]
        pattern = temporal["pattern"]
        
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.INACTIVITY_REENGAGEMENT.value,
            "approach": f"{pattern}_reengagement",
            "message_style": "warm_reengagement",
            "content_type": "reengagement",
            "urgency": "medium",
            "immediate_value": False,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": f"inactivity_pattern_{pattern}",
            "pattern_specific": self.config.engagement_patterns["inactivity_patterns"][pattern]
        }
    
    async def _generate_progressive_disclosure_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate progressive disclosure intervention."""
        completeness = context_analysis["completeness_analysis"]
        critical_missing = completeness["critical_missing"]
        
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.PROGRESSIVE_DISCLOSURE.value,
            "approach": "guided_disclosure",
            "message_style": "helpful_guidance",
            "content_type": "progressive_questions",
            "disclosure_sequence": [
                {"field": field, "priority": "critical", "question": self._generate_question_for_field(field)}
                for field in critical_missing[:3]  # Max 3 questions
            ],
            "questions_per_session": min(3, len(critical_missing)),
            "immediate_value": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "information_gaps",
            "progression_approach": "step_by_step"
        }
    
    async def _generate_context_aware_suggestion_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate context-aware suggestion intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.CONTEXT_AWARE_SUGGESTION.value,
            "approach": "smart_suggestions",
            "message_style": "helpful",
            "content_type": "suggestions",
            "immediate_value": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "context_aware",
            "suggestion_type": "next_best_action"
        }
    
    async def _generate_personalized_followup_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate personalized follow-up intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.PERSONALIZED_FOLLOWUP.value,
            "approach": "personalized_touch",
            "message_style": "personalized",
            "content_type": "follow_up",
            "immediate_value": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "qualified_lead_follow_up"
        }
    
    async def _generate_ambiguity_clarification_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate ambiguity clarification intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.AMBIGUITY_CLARIFICATION.value,
            "approach": "clarification_help",
            "message_style": "clarifying",
            "content_type": "clarification",
            "immediate_value": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "ambiguity_detected"
        }
    
    async def _generate_momentum_optimization_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate momentum optimization intervention."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.MOMENTUM_OPTIMIZATION.value,
            "approach": "momentum_boost",
            "message_style": "energizing",
            "content_type": "momentum_optimization",
            "immediate_value": True,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "momentum_declining"
        }
    
    async def _generate_fallback_intervention(
        self,
        user_id: str,
        context_analysis: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate fallback intervention when strategy generation fails."""
        return {
            "user_id": user_id,
            "strategy": EngagementStrategy.CONTEXT_AWARE_SUGGESTION.value,
            "approach": "fallback",
            "message_style": "helpful",
            "content_type": "fallback",
            "immediate_value": False,
            "intervention_timestamp": datetime.utcnow().isoformat(),
            "trigger_reason": "fallback_generation"
        }
    
    # LangGraph integration methods
    async def _create_intervention_checkpoint(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> str:
        """Create intervention checkpoint for state management."""
        checkpoint_id = f"intervention_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        try:
            if self.checkpointer:
                checkpoint_data = {
                    "intervention": intervention,
                    "state": current_state,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checkpoint_type": "proactive_intervention"
                }
                # Store in Redis
                if self.redis_client:
                    await self.redis_client.aput(checkpoint_id, checkpoint_data)
            
            self.logger.info(f"✅ Created intervention checkpoint: {checkpoint_id}")
            return checkpoint_id
            
        except Exception as e:
            self.logger.error(f"Error creating intervention checkpoint: {str(e)}")
            return f"fallback_checkpoint_{user_id}_{int(datetime.utcnow().timestamp())}"
    
    async def _execute_intervention_strategy(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the specific intervention strategy."""
        try:
            strategy = intervention.get("strategy", "")
            approach = intervention.get("approach", "")
            
            # Store intervention in history
            if user_id not in self.intervention_history:
                self.intervention_history[user_id] = []
            
            self.intervention_history[user_id].append({
                "intervention": intervention,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "executed"
            })
            
            return {
                "strategy_executed": strategy,
                "approach_used": approach,
                "execution_status": "completed",
                "results": {
                    "message_generated": True,
                    "state_updated": True,
                    "follow_up_scheduled": intervention.get("immediate_value", False)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error executing intervention strategy: {str(e)}")
            return {
                "strategy_executed": intervention.get("strategy", "unknown"),
                "approach_used": intervention.get("approach", "unknown"),
                "execution_status": "failed",
                "error": str(e)
            }
    
    async def _update_langgraph_state(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        intervention_result: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update LangGraph state after intervention execution."""
        try:
            updated_state = current_state.copy()
            
            # Add intervention tracking
            updated_state["last_proactive_intervention"] = {
                "strategy": intervention.get("strategy"),
                "timestamp": intervention.get("intervention_timestamp"),
                "approach": intervention.get("approach"),
                "result": intervention_result
            }
            
            # Increment intervention count
            updated_state["proactive_intervention_count"] = updated_state.get("proactive_intervention_count", 0) + 1
            
            # Update state with intervention-specific data
            if intervention.get("strategy") == EngagementStrategy.PROGRESSIVE_DISCLOSURE.value:
                updated_state["progressive_disclosure_step"] = updated_state.get("progressive_disclosure_step", 0) + 1
            
            self.logger.info(f"✅ Updated LangGraph state for user {user_id}")
            return updated_state
            
        except Exception as e:
            self.logger.error(f"Error updating LangGraph state: {str(e)}")
            return current_state
    
    async def _retrieve_intervention_checkpoint(
        self,
        user_id: str,
        intervention_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve intervention checkpoint data."""
        try:
            if self.checkpointer and self.redis_client:
                checkpoint_data = await self.redis_client.aget(intervention_id)
                if checkpoint_data:
                    return checkpoint_data
            
            # Fallback to stored history
            if user_id in self.intervention_history:
                for intervention_record in reversed(self.intervention_history[user_id]):
                    if intervention_record.get("intervention", {}).get("checkpoint_id") == intervention_id:
                        return intervention_record
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving intervention checkpoint: {str(e)}")
            return None
    
    async def _analyze_response_effectiveness(
        self,
        response_data: Dict[str, Any],
        checkpoint_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze the effectiveness of a user response to intervention."""
        try:
            # Calculate effectiveness metrics
            engagement_improved = response_data.get("engagement_improved", False)
            questions_answered = response_data.get("questions_answered", 0)
            user_sentiment = response_data.get("sentiment", "neutral")
            
            # Determine effectiveness score
            effectiveness_score = 0.0
            if engagement_improved:
                effectiveness_score += 0.5
            if questions_answered > 0:
                effectiveness_score += 0.3
            if user_sentiment == "positive":
                effectiveness_score += 0.2
            
            # Determine if adjustment is needed
            adjustment_needed = effectiveness_score < 0.6
            
            return {
                "effectiveness_score": effectiveness_score,
                "adjustment_needed": adjustment_needed,
                "metrics": {
                    "engagement_improved": engagement_improved,
                    "questions_answered": questions_answered,
                    "user_sentiment": user_sentiment
                },
                "recommendations": self._generate_adjustment_recommendations(effectiveness_score, response_data)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing response effectiveness: {str(e)}")
            return {
                "effectiveness_score": 0.0,
                "adjustment_needed": True,
                "error": str(e)
            }
    
    async def _update_langgraph_monitoring_state(
        self,
        user_id: str,
        intervention_id: str,
        response_data: Dict[str, Any],
        response_analysis: Dict[str, Any]
    ) -> None:
        """Update LangGraph monitoring state after response analysis."""
        try:
            if user_id not in self.conversation_contexts:
                return
            
            # Update intervention history with response analysis
            if user_id in self.intervention_history:
                for intervention_record in reversed(self.intervention_history[user_id]):
                    if intervention_record.get("intervention", {}).get("checkpoint_id") == intervention_id:
                        intervention_record["response_analysis"] = response_analysis
                        intervention_record["response_timestamp"] = datetime.utcnow().isoformat()
                        break
            
            self.logger.info(f"✅ Updated monitoring state for user {user_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating monitoring state: {str(e)}")
    
    async def _handle_intervention_failure(
        self,
        user_id: str,
        intervention: Dict[str, Any],
        current_state: Dict[str, Any],
        error_message: str
    ) -> Dict[str, Any]:
        """Handle intervention execution failure gracefully."""
        self.logger.error(f"Intervention failure for user {user_id}: {error_message}")
        
        return {
            "execution_status": "failed",
            "error": error_message,
            "fallback_executed": True,
            "user_id": user_id,
            "original_intervention": intervention,
            "failure_timestamp": datetime.utcnow().isoformat(),
            "recovery_action": "fallback_to_standard_processing"
        }
    
    # Utility methods
    def _determine_recommended_strategy(
        self,
        temporal_analysis: Dict[str, Any],
        momentum_analysis: Dict[str, Any],
        completeness_analysis: Dict[str, Any]
    ) -> EngagementStrategy:
        """Determine the recommended proactive engagement strategy."""
        try:
            # Check for inactivity trigger
            if temporal_analysis["inactivity_duration_hours"] > self.config.inactivity_threshold_minutes / 60:
                return EngagementStrategy.INACTIVITY_REENGAGEMENT
            
            # Check for information gaps
            if len(completeness_analysis["critical_missing"]) >= 2:
                return EngagementStrategy.PROGRESSIVE_DISCLOSURE
            
            # Check for ambiguity patterns
            if momentum_analysis["engagement_level"] == "low" and completeness_analysis["completeness_score"] < 0.5:
                return EngagementStrategy.AMBIGUITY_CLARIFICATION
            
            # Check for declining momentum
            if momentum_analysis["momentum_direction"] == "declining":
                return EngagementStrategy.MOMENTUM_OPTIMIZATION
            
            # Check for partial qualification
            if completeness_analysis["qualification_readiness"] == "partial":
                return EngagementStrategy.CONTEXT_AWARE_SUGGESTION
            
            # Default to personalized follow-up for qualified leads
            if completeness_analysis["qualification_readiness"] == "qualified":
                return EngagementStrategy.PERSONALIZED_FOLLOWUP
            
            # Default strategy
            return EngagementStrategy.CONTEXT_AWARE_SUGGESTION
            
        except Exception as e:
            self.logger.error(f"Error determining recommended strategy: {str(e)}")
            return EngagementStrategy.CONTEXT_AWARE_SUGGESTION
    
    def _calculate_confidence_score(
        self,
        temporal_analysis: Dict[str, Any],
        momentum_analysis: Dict[str, Any],
        completeness_analysis: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the analysis with robust error handling."""
        try:
            confidence = 0.0
            
            # Temporal confidence (based on data availability)
            if temporal_analysis.get("last_interaction_time"):
                confidence += 0.3
            
            # Momentum confidence (based on message history) - with safe access
            message_analysis = momentum_analysis.get("message_analysis", {})
            total_messages = message_analysis.get("total_messages", 0)
            if isinstance(total_messages, (int, float)) and total_messages > 5:
                confidence += 0.3
            
            # Completeness confidence (based on available lead info)
            completeness_score = completeness_analysis.get("completeness_score", 0)
            if isinstance(completeness_score, (int, float)) and completeness_score > 0:
                confidence += 0.4
            
            return min(1.0, confidence)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.5  # Default confidence
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _determine_conversation_stage(
        self,
        current_state: Dict[str, Any],
        message_count: int,
        engagement_score: float
    ) -> str:
        """Determine current conversation stage."""
        qualification = current_state.get("qualification", {})
        qualification_status = qualification.get("status", "unknown")
        
        if qualification_status == "qualified":
            return "qualified"
        elif qualification_status == "disqualified":
            return "disqualified"
        elif message_count < 3:
            return "greeting"
        elif engagement_score < 0.3:
            return "struggling"
        elif qualification_status == "partial_qualification":
            return "qualifying"
        else:
            return "exploring"
    
    def _analyze_momentum_direction(self, recent_messages: List[Dict[str, Any]]) -> str:
        """Analyze momentum direction from recent messages."""
        if len(recent_messages) < 4:
            return "unknown"
        
        # Analyze message lengths and response times for momentum
        user_messages = [msg for msg in recent_messages if msg.get("sender") == "user"]
        
        if len(user_messages) < 3:
            return "stable"
        
        # Look for declining patterns
        recent_3 = user_messages[-3:]
        message_lengths = [len(msg.get("message", "")) for msg in recent_3]
        
        if len(message_lengths) >= 3:
            if message_lengths[-1] < message_lengths[0] * 0.7:  # 30% decline
                return "declining"
            elif message_lengths[-1] > message_lengths[0] * 1.3:  # 30% increase
                return "increasing"
        
        return "stable"
    
    def _assess_qualification_readiness(
        self,
        completeness_score: float,
        critical_missing: List[str]
    ) -> str:
        """Assess qualification readiness."""
        if completeness_score >= 0.8 and len(critical_missing) == 0:
            return "qualified"
        elif completeness_score >= 0.4 and len(critical_missing) <= 2:
            return "partial"
        else:
            return "insufficient"
    
    def _generate_question_for_field(self, field: str) -> str:
        """Generate appropriate question for a missing field."""
        questions = {
            "budget": "What's your budget range for this property?",
            "location": "Which area or neighborhood are you most interested in?",
            "timeline": "When are you looking to move or make a purchase?",
            "property_type": "What type of property are you looking for?",
            "desired_bedrooms": "How many bedrooms do you need?"
        }
        return questions.get(field, f"What information can you share about {field}?")
    
    def _generate_adjustment_recommendations(
        self,
        effectiveness_score: float,
        response_data: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations for strategy adjustments."""
        recommendations = []
        
        if effectiveness_score < 0.4:
            recommendations.append("Consider switching to a different engagement strategy")
            recommendations.append("Reduce intervention frequency")
        elif effectiveness_score < 0.7:
            recommendations.append("Optimize intervention content and timing")
            recommendations.append("Personalize approach based on user preferences")
        else:
            recommendations.append("Current strategy is effective - continue")
            recommendations.append("Consider expanding successful patterns")
        
        return recommendations
    
    async def _create_fallback_analysis(
        self,
        user_id: str,
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create fallback analysis when main analysis fails."""
        return {
            "user_id": user_id,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "temporal_analysis": {
                "inactivity_duration_hours": 0,
                "pattern": "unknown",
                "frequency_score": 0.0,
                "temporal_signals": []
            },
            "momentum_analysis": {
                "engagement_level": "unknown",
                "current_stage": "unknown",
                "momentum_direction": "unknown",
                "engagement_score": 0.0
            },
            "completeness_analysis": {
                "completeness_score": 0.0,
                "critical_missing": [],
                "all_missing": [],
                "information_gaps": [],
                "qualification_readiness": "insufficient"
            },
            "recommended_strategy": EngagementStrategy.CONTEXT_AWARE_SUGGESTION,
            "confidence_score": 0.3,
            "fallback_mode": True,
            "analysis_error": "fallback_analysis_used"
        }

# Global convenience function for easy integration
async def analyze_conversation_context(
    user_id: str,
    current_state: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    config: Optional[ProactiveEngagementConfig] = None
) -> Dict[str, Any]:
    """Convenience function for conversation context analysis."""
    config = config or ProactiveEngagementConfig()
    engine = LangGraphProactiveEngagement(config)
    return await engine.analyze_conversation_context(user_id, current_state, conversation_history)

async def generate_proactive_intervention(
    user_id: str,
    context_analysis: Dict[str, Any],
    current_state: Dict[str, Any],
    config: Optional[ProactiveEngagementConfig] = None
) -> Dict[str, Any]:
    """Convenience function for proactive intervention generation."""
    config = config or ProactiveEngagementConfig()
    engine = LangGraphProactiveEngagement(config)
    return await engine.generate_proactive_intervention(user_id, context_analysis, current_state)

async def execute_intervention_with_langgraph(
    user_id: str,
    intervention: Dict[str, Any],
    current_state: Dict[str, Any],
    config: Optional[ProactiveEngagementConfig] = None
) -> Dict[str, Any]:
    """Convenience function for intervention execution."""
    config = config or ProactiveEngagementConfig()
    engine = LangGraphProactiveEngagement(config)
    return await engine.execute_intervention_with_langgraph(user_id, intervention, current_state)

# Export key classes and functions
__all__ = [
    "ProactiveEngagementConfig",
    "LangGraphProactiveEngagement",
    "EngagementStrategy",
    "EngagementState",
    "analyze_conversation_context",
    "generate_proactive_intervention",
    "execute_intervention_with_langgraph",
    "LANGGRAPH_AVAILABLE"
]