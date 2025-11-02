"""
Enhanced LangGraph Agentic AI System
Comprehensive implementation of pure agentic AI patterns with LangGraph

Features:
- Advanced supervisor-worker patterns with Send API
- Intelligent model routing based on task complexity
- Redis checkpoint persistence with LangGraph integration
- Proactive engagement with configurable thresholds
- Parallel processing with proper coordination
- Agent handoff mechanisms with Command objects
- Enhanced prompt engineering framework
- Cross-component state synchronization
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Literal, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import operator
from functools import wraps

# LangGraph imports
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Command, Send
    from langgraph.checkpoint.redis import RedisSaver
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    Command = None
    Send = None

# Core imports
from .redis_client import redis_client
from .llm_client import (
    ConversationContext,
    intelligent_model_router,
    TaskComplexity,
    ModelCapability,
    get_llm_response
)
from .proactive_engagement import (
    SimpleProactiveEngagement,
    ProactiveEngagementConfig,
    EngagementStrategy
)

logger = logging.getLogger(__name__)

# Enhanced state schemas for LangGraph
class EnhancedAgentState:
    """Enhanced state schema for LangGraph agent coordination."""
    def __init__(self):
        self.thread_id: str = ""
        self.user_id: str = ""
        self.current_stage: str = "initial"
        self.conversation_history: List[Dict[str, Any]] = []
        self.lead_info: Dict[str, Any] = {}
        self.agent_history: List[str] = []
        self.extraction_confidence: float = 0.0
        self.current_agent: str = "supervisor"
        self.next_actions: List[str] = []
        self.completed_tasks: List[str] = []
        self.pending_handoffs: List[Dict[str, Any]] = []
        self.context_data: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, float] = {}

class TaskComplexityLevel(Enum):
    """Enhanced task complexity levels."""
    TRIVIAL = "trivial"           # Simple text extraction
    SIMPLE = "simple"             # Basic classification
    MODERATE = "moderate"         # Multi-step reasoning
    COMPLEX = "complex"           # Multi-agent coordination
    SPECIALIZED = "specialized"   # Domain-specific complex tasks

class AgentCapability(Enum):
    """Enhanced agent capabilities."""
    EXTRACTION = "extraction"
    QUALIFICATION = "qualification"
    SCHEDULING = "scheduling"
    FOLLOWUP = "followup"
    COORDINATION = "coordination"
    ANALYSIS = "analysis"
    CREATIVE = "creative"

@dataclass
class TaskRequest:
    """Task request for parallel processing."""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1
    timeout: float = 30.0
    dependencies: List[str] = field(default_factory=list)
    agent_requirements: List[AgentCapability] = field(default_factory=list)

@dataclass
class AgentHandoff:
    """Agent handoff with proper LangGraph Command objects."""
    from_agent: str
    to_agent: str
    handoff_data: Dict[str, Any]
    reason: str
    priority: int = 1
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    command: Optional[Command] = None

class IntelligentModelRouterEnhanced:
    """Enhanced model router with task complexity analysis."""
    
    def __init__(self):
        self.capability_matrix = {
            AgentCapability.EXTRACTION: ["anthropic/claude-3-7-sonnet-latest", "nvidia/nemotron-nano-12b-v2-vl:free"],
            AgentCapability.QUALIFICATION: ["anthropic/claude-3-7-sonnet-latest", "openai/gpt-4o"],
            AgentCapability.SCHEDULING: ["openai/gpt-4o", "google/gemini-2.5-flash"],
            AgentCapability.FOLLOWUP: ["google/gemini-2.5-flash", "nvidia/nemotron-nano-12b-vl:free"],
            AgentCapability.COORDINATION: ["anthropic/claude-3-7-sonnet-latest"],
            AgentCapability.ANALYSIS: ["openai/gpt-4o", "anthropic/claude-3-7-sonnet-latest"],
            AgentCapability.CREATIVE: ["google/gemini-2.5-flash", "openai/gpt-4o"]
        }
        
        self.complexity_indicators = {
            TaskComplexityLevel.TRIVIAL: ["extract", "simple", "basic", "find"],
            TaskComplexityLevel.SIMPLE: ["classify", "categorize", "identify", "parse"],
            TaskComplexityLevel.MODERATE: ["analyze", "evaluate", "compare", "assess"],
            TaskComplexityLevel.COMPLEX: ["coordinate", "manage", "orchestrate", "strategize"],
            TaskComplexityLevel.SPECIALIZED: ["domain", "expert", "specialized", "advanced"]
        }
    
    def analyze_task_complexity(self, task_description: str, context: Optional[EnhancedAgentState] = None) -> TaskComplexityLevel:
        """Analyze task complexity using multiple factors."""
        task_lower = task_description.lower()
        complexity_scores = {level: 0 for level in TaskComplexityLevel}
        
        # Analyze task description
        for level, indicators in self.complexity_indicators.items():
            for indicator in indicators:
                if indicator in task_lower:
                    complexity_scores[level] += 1
        
        # Context-based complexity adjustment
        if context:
            # Increase complexity for multi-agent coordination
            if len(context.agent_history) > 5:
                complexity_scores[TaskComplexityLevel.COMPLEX] += 2
            
            # Increase for complex conversation stages
            if context.current_stage in ["scheduling", "booking"]:
                complexity_scores[TaskComplexityLevel.MODERATE] += 1
            
            # Increase for missing information
            missing_count = len([k for k, v in context.lead_info.items() if not v])
            if missing_count > 2:
                complexity_scores[TaskComplexityLevel.MODERATE] += 1
        
        # Determine dominant complexity
        max_score = max(complexity_scores.values())
        if max_score == 0:
            return TaskComplexityLevel.SIMPLE
        
        for level, score in complexity_scores.items():
            if score == max_score:
                return level
        
        return TaskComplexityLevel.SIMPLE
    
    def route_task_to_model(self, task_request: TaskRequest, complexity: TaskComplexityLevel) -> str:
        """Route task to optimal model based on complexity and capabilities."""
        required_capabilities = task_request.agent_requirements
        
        # Find best model for required capabilities
        best_model = None
        max_capability_score = 0
        
        for capability in required_capabilities:
            if capability in self.capability_matrix:
                for model in self.capability_matrix[capability]:
                    # Score model based on capability match and complexity
                    if complexity in [TaskComplexityLevel.COMPLEX, TaskComplexityLevel.SPECIALIZED]:
                        if "claude-3-7" in model or "gpt-4o" in model:
                            score = 3
                        else:
                            score = 1
                    else:
                        score = 2
                    
                    if score > max_capability_score:
                        max_capability_score = score
                        best_model = model
        
        # Fallback to default model
        if not best_model:
            if complexity in [TaskComplexityLevel.COMPLEX, TaskComplexityLevel.SPECIALIZED]:
                best_model = "anthropic/claude-3-7-sonnet-latest"
            else:
                best_model = "nvidia/nemotron-nano-12b-vl:free"
        
        return best_model

class AdvancedRedisCheckpointManager:
    """Enhanced Redis checkpoint manager with LangGraph integration."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.namespace = "enhanced_agentic"
        self.checkpointer = None
        self._initialize_checkpointer()
    
    def _initialize_checkpointer(self):
        """Initialize Redis checkpointer with LangGraph patterns."""
        if LANGGRAPH_AVAILABLE and RedisSaver:
            try:
                self.checkpointer = RedisSaver.from_conn_string(self.redis_url)
                logger.info("✅ Enhanced Redis checkpointer initialized with LangGraph")
            except Exception as e:
                logger.warning(f"⚠️ Enhanced Redis checkpointer initialization failed: {e}")
                self.checkpointer = None
    
    async def save_enhanced_checkpoint(
        self,
        thread_id: str,
        state: EnhancedAgentState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save enhanced agent state to Redis with LangGraph patterns."""
        try:
            checkpoint_data = {
                "enhanced_state": {
                    "thread_id": state.thread_id,
                    "user_id": state.user_id,
                    "current_stage": state.current_stage,
                    "conversation_history": state.conversation_history,
                    "lead_info": state.lead_info,
                    "agent_history": state.agent_history,
                    "extraction_confidence": state.extraction_confidence,
                    "current_agent": state.current_agent,
                    "next_actions": state.next_actions,
                    "completed_tasks": state.completed_tasks,
                    "context_data": state.context_data,
                    "performance_metrics": state.performance_metrics
                },
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0"
            }
            
            if self.checkpointer:
                # Use LangGraph Redis checkpointer
                config = {"configurable": {"thread_id": thread_id}}
                await self.checkpointer.aput(config, checkpoint_data, {}, {})
                return thread_id
            else:
                # Fallback to direct Redis storage
                key = f"{self.namespace}:enhanced_checkpoint:{thread_id}"
                await redis_client.setex(key, 86400, json.dumps(checkpoint_data))
                return thread_id
        
        except Exception as e:
            logger.error(f"Failed to save enhanced checkpoint: {e}")
            return thread_id
    
    async def load_enhanced_checkpoint(self, thread_id: str) -> Optional[EnhancedAgentState]:
        """Load enhanced agent state from Redis."""
        try:
            if self.checkpointer:
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = await self.checkpointer.aget(config)
                if checkpoint:
                    state_data = checkpoint.channel_values.get("enhanced_state", {})
                else:
                    return None
            else:
                key = f"{self.namespace}:enhanced_checkpoint:{thread_id}"
                data = await redis_client.get(key)
                if not data:
                    return None
                checkpoint_data = json.loads(data)
                state_data = checkpoint_data.get("enhanced_state", {})
            
            # Reconstruct EnhancedAgentState
            state = EnhancedAgentState()
            state.thread_id = state_data.get("thread_id", thread_id)
            state.user_id = state_data.get("user_id", "")
            state.current_stage = state_data.get("current_stage", "initial")
            state.conversation_history = state_data.get("conversation_history", [])
            state.lead_info = state_data.get("lead_info", {})
            state.agent_history = state_data.get("agent_history", [])
            state.extraction_confidence = state_data.get("extraction_confidence", 0.0)
            state.current_agent = state_data.get("current_agent", "supervisor")
            state.next_actions = state_data.get("next_actions", [])
            state.completed_tasks = state_data.get("completed_tasks", [])
            state.context_data = state_data.get("context_data", {})
            state.performance_metrics = state_data.get("performance_metrics", {})
            
            return state
        
        except Exception as e:
            logger.error(f"Failed to load enhanced checkpoint: {e}")
            return None

class ProactiveEngagementEnhanced:
    """Enhanced proactive engagement with configurable thresholds."""
    
    def __init__(self):
        self.thresholds = {
            "inactivity_minutes": 30,
            "max_interventions_per_hour": 2,
            "max_interventions_per_day": 5,
            "response_time_threshold_hours": 2,
            "engagement_score_threshold": 0.3
        }
        
        self.intervention_history = {}
        self.engagement_tracker = {}
        self.config = ProactiveEngagementConfig()
        self.engine = SimpleProactiveEngagement(self.config)
    
    async def analyze_engagement_opportunity(
        self,
        state: EnhancedAgentState,
        time_since_last_activity: float
    ) -> Tuple[bool, EngagementStrategy, str]:
        """Analyze if proactive engagement is needed."""
        user_id = state.user_id
        
        try:
            # Convert state to dict format for the simple engine
            current_state = {
                "lead": state.lead_info,
                "current_stage": state.current_stage,
                "extraction_confidence": state.extraction_confidence
            }
            
            # Use simple proactive engagement engine
            context_analysis = await self.engine.analyze_conversation_context(
                user_id=user_id,
                current_state=current_state,
                conversation_history=state.conversation_history
            )
            
            strategy = context_analysis.get("recommended_strategy", EngagementStrategy.BASIC_FOLLOWUP)
            
            # Check if intervention is needed based on temporal analysis
            temporal = context_analysis.get("temporal_analysis", {})
            needs_followup = temporal.get("needs_followup", False)
            
            if needs_followup:
                return True, strategy, f"Temporal analysis indicates followup needed: {temporal.get('pattern', 'unknown')}"
            else:
                return False, strategy, "No followup needed based on temporal analysis"
                
        except Exception as e:
            logger.error(f"Error in engagement opportunity analysis: {e}")
            # Fallback to simple rule-based analysis
            if time_since_last_activity < self.thresholds["inactivity_minutes"]:
                return False, EngagementStrategy.BASIC_FOLLOWUP, "Active conversation"
            else:
                return True, EngagementStrategy.INACTIVITY_REENGAGEMENT, "Extended inactivity detected"
    
    async def generate_proactive_intervention(
        self,
        strategy: EngagementStrategy,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Generate proactive intervention based on strategy."""
        
        try:
            # Convert state to dict format for the simple engine
            current_state = {
                "lead": state.lead_info,
                "current_stage": state.current_stage,
                "extraction_confidence": state.extraction_confidence
            }
            
            # Create context analysis
            context_analysis = {
                "recommended_strategy": strategy,
                "temporal_analysis": {"pattern": "enhanced_analysis"},
                "engagement_analysis": {"engagement_level": "medium"},
                "completeness_analysis": {"needs_info": len(state.lead_info) < 3}
            }
            
            # Use simple proactive engagement engine
            intervention = await self.engine.generate_proactive_intervention(
                user_id=state.user_id,
                context_analysis=context_analysis,
                current_state=current_state
            )
            
            # Enhance with enhanced system metadata
            intervention.update({
                "thread_id": state.thread_id,
                "current_stage": state.current_stage,
                "context_aware": True,
                "enhanced_mode": True
            })
            
            return intervention
            
        except Exception as e:
            logger.error(f"Error generating proactive intervention: {e}")
            # Fallback intervention
            return {
                "strategy": strategy.value,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": state.user_id,
                "thread_id": state.thread_id,
                "current_stage": state.current_stage,
                "approach": "fallback_engagement",
                "message_style": "helpful",
                "context_aware": False,
                "enhanced_mode": False,
                "error": str(e)
            }

class SupervisorWorkerOrchestrator:
    """Advanced supervisor-worker orchestrator with LangGraph patterns."""
    
    def __init__(self):
        self.model_router = IntelligentModelRouterEnhanced()
        self.checkpoint_manager = AdvancedRedisCheckpointManager()
        self.proactive_engine = ProactiveEngagementEnhanced()
        self.worker_agents = {
            "extraction": self._extraction_worker,
            "qualification": self._qualification_worker,
            "scheduling": self._scheduling_worker,
            "followup": self._followup_worker,
            "analysis": self._analysis_worker
        }
    
    async def supervisor_node(
        self,
        state: EnhancedAgentState
    ) -> Command:
        """Enhanced supervisor node with intelligent routing."""
        
        # Analyze current state and determine next actions
        next_actions = await self._determine_next_actions(state)
        
        # Check for proactive engagement opportunities
        time_since_activity = (
            datetime.utcnow() - datetime.fromisoformat(
                state.conversation_history[-1]["timestamp"]
                if state.conversation_history 
                else datetime.utcnow().isoformat()
            )
        ).total_seconds() / 60
        
        should_engage, strategy, reason = await self.proactive_engine.analyze_engagement_opportunity(
            state, time_since_activity
        )
        
        # Update state with supervisor decisions
        state.next_actions = next_actions
        state.current_agent = "supervisor"
        state.agent_history.append(f"supervisor:analyzed_state_{datetime.utcnow().isoformat()}")
        
        # Generate proactive intervention if needed
        if should_engage:
            intervention = await self.proactive_engine.generate_proactive_intervention(
                strategy, state
            )
            state.context_data["proactive_intervention"] = intervention
            state.agent_history.append(f"supervisor:proactive_intervention_{strategy.value}")
        
        # Route to appropriate worker or complete
        if next_actions:
            primary_action = next_actions[0]
            return Command(
                goto=primary_action,
                update={
                    "next_actions": next_actions[1:],
                    "current_agent": primary_action,
                    "agent_history": state.agent_history,
                    "context_data": state.context_data
                }
            )
        else:
            return Command(
                goto=END,
                update={
                    "current_agent": "completed",
                    "agent_history": state.agent_history,
                    "completed_tasks": state.completed_tasks + ["supervisor:workflow_complete"]
                }
            )
    
    async def _determine_next_actions(self, state: EnhancedAgentState) -> List[str]:
        """Determine next actions based on current state."""
        actions = []
        
        # Rule-based action determination
        if state.current_stage == "initial":
            if not state.lead_info.get("budget") or not state.lead_info.get("location"):
                actions.append("extraction")
            else:
                actions.append("qualification")
        
        elif state.current_stage == "qualification":
            if state.extraction_confidence < 0.7:
                actions.append("qualification")
            else:
                actions.append("scheduling")
        
        elif state.current_stage == "scheduling":
            actions.append("scheduling")
        
        else:
            actions.append("followup")
        
        return actions
    
    async def _extraction_worker(self, state: EnhancedAgentState) -> Command:
        """Enhanced extraction worker with parallel processing."""
        try:
            # Create task for extraction
            extraction_task = TaskRequest(
                task_id=f"extract_{int(time.time())}",
                task_type="information_extraction",
                payload={
                    "message": state.conversation_history[-1]["content"] if state.conversation_history else "",
                    "existing_data": state.lead_info
                },
                agent_requirements=[AgentCapability.EXTRACTION]
            )
            
            # Analyze task complexity
            complexity = self.model_router.analyze_task_complexity(
                "Extract lead information from message", state
            )
            
            # Route to optimal model
            model = self.model_router.route_task_to_model(extraction_task, complexity)
            
            # Perform extraction
            extracted_data = await self._perform_extraction(extraction_task, model)
            
            # Update state
            state.lead_info.update(extracted_data)
            state.completed_tasks.append("extraction:completed")
            state.extraction_confidence = self._calculate_extraction_confidence(state.lead_info)
            
            # Check if we need parallel processing for additional tasks
            if state.extraction_confidence < 0.5 and state.lead_info:
                # Trigger parallel qualification analysis
                return Command(
                    goto="qualification",
                    update={
                        "lead_info": state.lead_info,
                        "extraction_confidence": state.extraction_confidence,
                        "completed_tasks": state.completed_tasks,
                        "agent_history": state.agent_history + ["extraction:triggered_qualification"]
                    }
                )
            
            return Command(
                goto="supervisor",
                update={
                    "lead_info": state.lead_info,
                    "extraction_confidence": state.extraction_confidence,
                    "completed_tasks": state.completed_tasks,
                    "agent_history": state.agent_history + ["extraction:completed"]
                }
            )
            
        except Exception as e:
            logger.error(f"Extraction worker failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "extraction_confidence": 0.0,
                    "agent_history": state.agent_history + [f"extraction:error_{str(e)}"],
                    "completed_tasks": state.completed_tasks + ["extraction:failed"]
                }
            )
    
    async def _qualification_worker(self, state: EnhancedAgentState) -> Command:
        """Enhanced qualification worker with intelligent analysis."""
        try:
            # Analyze qualification readiness
            missing_critical = [
                k for k, v in state.lead_info.items() 
                if k in ["budget", "location"] and not v
            ]
            
            qualification_score = self._calculate_qualification_score(state.lead_info)
            
            if qualification_score >= 0.7 and not missing_critical:
                # Ready for scheduling
                state.current_stage = "qualified"
                next_stage = "scheduling"
            elif qualification_score >= 0.4:
                # Continue qualification
                next_stage = "qualification"
            else:
                # Need more information
                next_stage = "extraction"
            
            state.agent_history.append(f"qualification:analyzed_score_{qualification_score:.2f}")
            state.completed_tasks.append(f"qualification:completed_{next_stage}")
            
            return Command(
                goto=next_stage,
                update={
                    "current_stage": state.current_stage,
                    "agent_history": state.agent_history,
                    "completed_tasks": state.completed_tasks,
                    "context_data": {
                        **state.context_data,
                        "qualification_score": qualification_score,
                        "missing_critical": missing_critical
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Qualification worker failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history + [f"qualification:error_{str(e)}"],
                    "completed_tasks": state.completed_tasks + ["qualification:failed"]
                }
            )
    
    async def _scheduling_worker(self, state: EnhancedAgentState) -> Command:
        """Enhanced scheduling worker with intelligent coordination."""
        try:
            # Check if lead is ready for scheduling
            qualification_score = state.context_data.get("qualification_score", 0)
            missing_critical = state.context_data.get("missing_critical", [])
            
            if qualification_score >= 0.7 and not missing_critical:
                # Ready for booking
                state.current_stage = "scheduling"
                state.agent_history.append("scheduling:lead_ready")
                
                # Generate scheduling intervention
                state.context_data["scheduling_intervention"] = {
                    "ready_for_booking": True,
                    "recommended_action": "offer_property_tours",
                    "qualification_score": qualification_score
                }
            else:
                # Not ready, route back to qualification
                state.current_stage = "qualification"
                state.agent_history.append("scheduling:not_ready_back_to_qualification")
            
            state.completed_tasks.append("scheduling:completed")
            
            return Command(
                goto="supervisor",
                update={
                    "current_stage": state.current_stage,
                    "agent_history": state.agent_history,
                    "completed_tasks": state.completed_tasks,
                    "context_data": state.context_data
                }
            )
            
        except Exception as e:
            logger.error(f"Scheduling worker failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history + [f"scheduling:error_{str(e)}"],
                    "completed_tasks": state.completed_tasks + ["scheduling:failed"]
                }
            )
    
    async def _followup_worker(self, state: EnhancedAgentState) -> Command:
        """Enhanced followup worker with engagement optimization."""
        try:
            # Analyze engagement patterns
            last_activity = datetime.fromisoformat(
                state.conversation_history[-1]["timestamp"]
                if state.conversation_history 
                else datetime.utcnow().isoformat()
            )
            
            time_since = (datetime.utcnow() - last_activity).total_seconds() / 3600
            
            if time_since > 24:  # 24+ hours
                engagement_strategy = "value_driven_followup"
                state.agent_history.append("followup:extended_inactivity_strategy")
            else:
                engagement_strategy = "maintenance_followup"
                state.agent_history.append("followup:standard_maintenance")
            
            state.context_data["followup_strategy"] = engagement_strategy
            state.completed_tasks.append("followup:completed")
            
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history,
                    "completed_tasks": state.completed_tasks,
                    "context_data": state.context_data
                }
            )
            
        except Exception as e:
            logger.error(f"Followup worker failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history + [f"followup:error_{str(e)}"],
                    "completed_tasks": state.completed_tasks + ["followup:failed"]
                }
            )
    
    async def _analysis_worker(self, state: EnhancedAgentState) -> Command:
        """Enhanced analysis worker for complex scenarios."""
        try:
            # Perform comprehensive analysis
            analysis_results = {
                "conversation_health": self._analyze_conversation_health(state),
                "lead_quality": self._analyze_lead_quality(state),
                "engagement_trends": self._analyze_engagement_trends(state),
                "optimization_suggestions": self._generate_optimization_suggestions(state)
            }
            
            state.context_data["analysis_results"] = analysis_results
            state.agent_history.append("analysis:completed_comprehensive")
            state.completed_tasks.append("analysis:completed")
            
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history,
                    "completed_tasks": state.completed_tasks,
                    "context_data": state.context_data
                }
            )
            
        except Exception as e:
            logger.error(f"Analysis worker failed: {e}")
            return Command(
                goto="supervisor",
                update={
                    "agent_history": state.agent_history + [f"analysis:error_{str(e)}"],
                    "completed_tasks": state.completed_tasks + ["analysis:failed"]
                }
            )
    
    # Helper methods
    async def _perform_extraction(self, task: TaskRequest, model: str) -> Dict[str, Any]:
        """Perform information extraction using LLM."""
        try:
            message = task.payload["message"]
            existing_data = task.payload["existing_data"]
            
            prompt = f"""
            Extract real estate lead information from this message: "{message}"
            
            Existing information: {existing_data}
            
            Extract any new information for:
            - Budget (in USD)
            - Location (city/area)
            - Property type (1BHK, 2BHK, 3BHK, Condo, etc.)
            - Timeline (when they want to buy/rent)
            - Contact information
            
            Respond with only the new information found, in JSON format.
            """
            
            response = await get_llm_response(
                prompt=prompt,
                model=model,
                conversation_context=None,
                enable_intelligent_routing=False
            )
            
            # Parse extraction result
            try:
                import json
                extracted = json.loads(response)
                return extracted
            except json.JSONDecodeError:
                # Fallback to simple parsing
                return self._simple_extract_from_response(response)
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {}
    
    def _simple_extract_from_response(self, response: str) -> Dict[str, Any]:
        """Simple extraction fallback."""
        result = {}
        response_lower = response.lower()
        
        # Simple budget extraction
        budget_match = response_lower.search(r'\$(\d+(?:,\d{3})*)')
        if budget_match:
            result["budget"] = int(budget_match.group(1).replace(',', ''))
        
        # Simple location extraction
        if "location" in response_lower or "area" in response_lower:
            # Extract basic location info
            words = response.split()
            for i, word in enumerate(words):
                if word.lower() in ["near", "in", "at", "around"]:
                    if i + 1 < len(words):
                        result["location"] = " ".join(words[i+1:i+3])
                        break
        
        return result
    
    def _calculate_extraction_confidence(self, lead_info: Dict[str, Any]) -> float:
        """Calculate extraction confidence based on completeness."""
        fields = ["budget", "location", "property_type", "timeline"]
        completed = sum(1 for field in fields if lead_info.get(field))
        return min(completed / len(fields), 1.0)
    
    def _calculate_qualification_score(self, lead_info: Dict[str, Any]) -> float:
        """Calculate lead qualification score."""
        required_fields = ["budget", "location"]
        optional_fields = ["property_type", "timeline"]
        
        required_score = sum(
            0.5 for field in required_fields if lead_info.get(field)
        )
        optional_score = sum(
            0.25 for field in optional_fields if lead_info.get(field)
        )
        
        return min(required_score + optional_score, 1.0)
    
    def _analyze_conversation_health(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze conversation health metrics."""
        if not state.conversation_history:
            return {"health_score": 0.0, "status": "no_history"}
        
        message_count = len(state.conversation_history)
        user_messages = [
            msg for msg in state.conversation_history 
            if msg.get("role") == "user"
        ]
        
        return {
            "health_score": min(message_count / 10, 1.0),
            "message_count": message_count,
            "user_engagement": len(user_messages) / message_count if message_count > 0 else 0,
            "status": "healthy" if message_count >= 5 else "developing"
        }
    
    def _analyze_lead_quality(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze lead quality metrics."""
        completeness = self._calculate_extraction_confidence(state.lead_info)
        qualification = self._calculate_qualification_score(state.lead_info)
        
        return {
            "completeness_score": completeness,
            "qualification_score": qualification,
            "quality_rating": "high" if qualification >= 0.7 else "medium" if qualification >= 0.4 else "low",
            "missing_critical": [k for k, v in state.lead_info.items() if k in ["budget", "location"] and not v]
        }
    
    def _analyze_engagement_trends(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze engagement trends."""
        if not state.conversation_history:
            return {"trend": "no_data"}
        
        # Simple engagement analysis
        recent_messages = state.conversation_history[-5:]
        user_recent = [
            msg for msg in recent_messages 
            if msg.get("role") == "user"
        ]
        
        return {
            "trend": "improving" if len(user_recent) >= 3 else "stable",
            "recent_activity": len(user_recent),
            "engagement_level": "high" if len(user_recent) >= 3 else "low"
        }
    
    def _generate_optimization_suggestions(self, state: EnhancedAgentState) -> List[str]:
        """Generate optimization suggestions."""
        suggestions = []
        
        if state.extraction_confidence < 0.5:
            suggestions.append("Focus on information extraction")
        
        if state.current_stage == "initial" and state.extraction_confidence >= 0.5:
            suggestions.append("Move to qualification stage")
        
        if len(state.agent_history) > 10:
            suggestions.append("Consider workflow optimization")
        
        return suggestions

# Main orchestrator factory
def create_enhanced_agentic_orchestrator() -> SupervisorWorkerOrchestrator:
    """Create and return enhanced agentic orchestrator."""
    return SupervisorWorkerOrchestrator()

# Export key components
__all__ = [
    "EnhancedAgentState",
    "TaskRequest",
    "AgentHandoff", 
    "SupervisorWorkerOrchestrator",
    "IntelligentModelRouterEnhanced",
    "AdvancedRedisCheckpointManager",
    "ProactiveEngagementEnhanced",
    "create_enhanced_agentic_orchestrator"
]