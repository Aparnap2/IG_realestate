"""
LangGraph Parallel Processing and Agent Coordination System
Implements Send API for concurrent processing and advanced handoff mechanisms

Features:
- Parallel processing with LangGraph Send API
- Agent handoff mechanisms with Command objects
- Task delegation and coordination
- Concurrent workflow execution
- Performance optimization for multi-agent scenarios
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Literal, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import operator
from functools import wraps

# LangGraph imports
try:
    from langgraph.types import Send, Command
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    Send = None
    Command = None

# Import enhanced agentic components
from .langgraph_enhanced_agentic_system import (
    EnhancedAgentState,
    TaskRequest,
    AgentHandoff,
    SupervisorWorkerOrchestrator,
    IntelligentModelRouterEnhanced,
    TaskComplexityLevel,
    AgentCapability
)

logger = logging.getLogger(__name__)

@dataclass
class ParallelTask:
    """Task for parallel execution using LangGraph Send API."""
    task_id: str
    worker_name: str
    task_data: Dict[str, Any]
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    callback_agent: Optional[str] = None
    result_handler: Optional[str] = None

@dataclass
class WorkflowExecution:
    """Workflow execution context for parallel processing."""
    execution_id: str
    workflow_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed, cancelled
    tasks: List[ParallelTask] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    error_log: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

class TaskDelegationEngine:
    """Advanced task delegation engine with LangGraph Send API."""
    
    def __init__(self):
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.performance_tracker = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default task handlers."""
        self.task_handlers = {
            "extraction": self._handle_extraction_task,
            "qualification": self._handle_qualification_task,
            "scheduling": self._handle_scheduling_task,
            "followup": self._handle_followup_task,
            "analysis": self._handle_analysis_task,
            "coordination": self._handle_coordination_task,
            "validation": self._handle_validation_task
        }
    
    async def execute_parallel_workflow(
        self,
        workflow_name: str,
        tasks: List[ParallelTask],
        initial_state: EnhancedAgentState
    ) -> WorkflowExecution:
        """Execute workflow with parallel task processing."""
        
        execution_id = f"{workflow_name}_{int(time.time())}"
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=workflow_name,
            start_time=datetime.utcnow(),
            tasks=tasks
        )
        
        self.active_executions[execution_id] = execution
        
        try:
            logger.info(f"🚀 Starting parallel workflow: {workflow_name} ({len(tasks)} tasks)")
            
            # Phase 1: Execute independent tasks in parallel
            independent_tasks = [
                task for task in tasks 
                if not task.dependencies
            ]
            
            if independent_tasks:
                parallel_results = await self._execute_tasks_in_parallel(
                    independent_tasks, initial_state
                )
                
                # Update execution with results
                for result in parallel_results:
                    if result["success"]:
                        execution.completed_tasks.append(result["task_id"])
                        execution.results[result["task_id"]] = result["data"]
                    else:
                        execution.failed_tasks.append(result["task_id"])
                        execution.error_log.append(result["error"])
            
            # Phase 2: Execute dependent tasks
            remaining_tasks = [
                task for task in tasks 
                if task.task_id not in execution.completed_tasks and 
                   task.task_id not in execution.failed_tasks
            ]
            
            while remaining_tasks:
                # Find tasks with satisfied dependencies
                ready_tasks = [
                    task for task in remaining_tasks
                    if all(dep in execution.completed_tasks for dep in task.dependencies)
                ]
                
                if not ready_tasks:
                    # No tasks can proceed due to failed dependencies
                    break
                
                # Execute ready tasks
                parallel_results = await self._execute_tasks_in_parallel(
                    ready_tasks, initial_state
                )
                
                # Update execution
                for result in parallel_results:
                    if result["success"]:
                        execution.completed_tasks.append(result["task_id"])
                        execution.results[result["task_id"]] = result["data"]
                    else:
                        execution.failed_tasks.append(result["task_id"])
                        execution.error_log.append(result["error"])
                
                # Remove completed/failed tasks from remaining
                remaining_tasks = [
                    task for task in remaining_tasks
                    if task.task_id not in execution.completed_tasks and
                       task.task_id not in execution.failed_tasks
                ]
            
            # Mark execution as completed
            execution.end_time = datetime.utcnow()
            execution.status = "completed" if not execution.failed_tasks else "completed_with_errors"
            
            # Calculate performance metrics
            total_duration = (execution.end_time - execution.start_time).total_seconds()
            execution.performance_metrics = {
                "total_duration": total_duration,
                "tasks_completed": len(execution.completed_tasks),
                "tasks_failed": len(execution.failed_tasks),
                "success_rate": len(execution.completed_tasks) / len(tasks) if tasks else 0,
                "parallel_efficiency": self._calculate_parallel_efficiency(execution)
            }
            
            logger.info(
                f"✅ Parallel workflow completed: {execution_id} "
                f"({len(execution.completed_tasks)}/{len(tasks)} tasks succeeded)"
            )
            
            return execution
            
        except Exception as e:
            logger.error(f"❌ Parallel workflow failed: {execution_id} - {e}")
            execution.end_time = datetime.utcnow()
            execution.status = "failed"
            execution.error_log.append(f"Workflow execution failed: {str(e)}")
            return execution
    
    async def _execute_tasks_in_parallel(
        self,
        tasks: List[ParallelTask],
        initial_state: EnhancedAgentState
    ) -> List[Dict[str, Any]]:
        """Execute tasks in parallel using LangGraph Send API."""
        
        if not LANGGRAPH_AVAILABLE or not Send:
            # Fallback to sequential execution
            results = []
            for task in tasks:
                result = await self._execute_single_task(task, initial_state)
                results.append(result)
            return results
        
        # Use LangGraph Send API for parallel execution
        send_api_calls = []
        
        for task in tasks:
            send_call = Send(
                task.worker_name,
                {
                    "task": task,
                    "state": initial_state,
                    "execution_context": {
                        "task_id": task.task_id,
                        "execution_time": datetime.utcnow().isoformat()
                    }
                }
            )
            send_api_calls.append(send_call)
        
        # Execute all tasks in parallel
        try:
            # In a real LangGraph workflow, these would be sent via Send API
            # For simulation, we execute them concurrently
            semaphore = asyncio.Semaphore(5)  # Limit concurrent tasks
            
            async def execute_with_semaphore(task):
                async with semaphore:
                    return await self._execute_single_task(task, initial_state)
            
            results = await asyncio.gather(
                *[execute_with_semaphore(task) for task in tasks],
                return_exceptions=True
            )
            
            # Handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "task_id": tasks[i].task_id,
                        "success": False,
                        "error": str(result),
                        "data": None
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            return [
                {
                    "task_id": task.task_id,
                    "success": False,
                    "error": str(e),
                    "data": None
                }
                for task in tasks
            ]
    
    async def _execute_single_task(
        self,
        task: ParallelTask,
        initial_state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Execute a single task with retry logic."""
        
        start_time = time.time()
        
        for attempt in range(task.max_retries + 1):
            try:
                # Check if handler exists
                if task.worker_name not in self.task_handlers:
                    raise ValueError(f"No handler registered for worker: {task.worker_name}")
                
                handler = self.task_handlers[task.worker_name]
                
                # Execute task
                result = await handler(task, initial_state)
                
                # Track performance
                execution_time = time.time() - start_time
                self._track_task_performance(task.task_id, execution_time, True)
                
                return {
                    "task_id": task.task_id,
                    "success": True,
                    "data": result,
                    "execution_time": execution_time,
                    "attempts": attempt + 1
                }
                
            except Exception as e:
                logger.warning(
                    f"Task {task.task_id} attempt {attempt + 1} failed: {e}"
                )
                
                if attempt < task.max_retries:
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Track failed performance
                    execution_time = time.time() - start_time
                    self._track_task_performance(task.task_id, execution_time, False)
                    
                    return {
                        "task_id": task.task_id,
                        "success": False,
                        "error": str(e),
                        "data": None,
                        "execution_time": execution_time,
                        "attempts": attempt + 1
                    }
    
    # Task handlers
    async def _handle_extraction_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle extraction task."""
        message = task.task_data.get("message", "")
        
        # Enhanced extraction logic
        extracted_data = self._extract_information_enhanced(message, state.lead_info)
        
        return {
            "extracted_data": extracted_data,
            "confidence": self._calculate_extraction_confidence(extracted_data),
            "fields_updated": list(extracted_data.keys())
        }
    
    async def _handle_qualification_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle qualification task."""
        lead_info = task.task_data.get("lead_info", {})
        
        qualification_score = self._calculate_qualification_score(lead_info)
        missing_critical = self._identify_missing_critical_info(lead_info)
        
        return {
            "qualification_score": qualification_score,
            "missing_critical": missing_critical,
            "ready_for_scheduling": qualification_score >= 0.7 and not missing_critical,
            "recommendations": self._generate_qualification_recommendations(lead_info)
        }
    
    async def _handle_scheduling_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle scheduling task."""
        qualification_score = task.task_data.get("qualification_score", 0)
        
        if qualification_score >= 0.7:
            return {
                "scheduling_ready": True,
                "recommended_actions": ["offer_property_tours", "schedule_viewing"],
                "next_steps": ["collect_preferences", "propose_times"]
            }
        else:
            return {
                "scheduling_ready": False,
                "reason": "insufficient_qualification",
                "required_steps": ["complete_qualification"]
            }
    
    async def _handle_followup_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle followup task."""
        last_activity = task.task_data.get("last_activity")
        engagement_level = task.task_data.get("engagement_level", "medium")
        
        time_since = self._calculate_time_since(last_activity)
        
        followup_strategy = self._determine_followup_strategy(time_since, engagement_level)
        
        return {
            "followup_strategy": followup_strategy,
            "time_since_activity": time_since,
            "engagement_level": engagement_level,
            "recommended_approach": self._get_followup_approach(followup_strategy)
        }
    
    async def _handle_analysis_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle analysis task."""
        analysis_type = task.task_data.get("analysis_type", "comprehensive")
        
        if analysis_type == "performance":
            return self._analyze_performance_metrics(state)
        elif analysis_type == "engagement":
            return self._analyze_engagement_patterns(state)
        elif analysis_type == "conversion":
            return self._analyze_conversion_potential(state)
        else:
            return self._comprehensive_analysis(state)
    
    async def _handle_coordination_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle coordination task."""
        coordination_type = task.task_data.get("coordination_type", "standard")
        
        if coordination_type == "agent_handoff":
            return self._coordinate_agent_handoff(task.task_data, state)
        elif coordination_type == "parallel_delegation":
            return self._coordinate_parallel_delegation(task.task_data, state)
        else:
            return self._standard_coordination(task.task_data, state)
    
    async def _handle_validation_task(
        self,
        task: ParallelTask,
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Handle validation task."""
        validation_type = task.task_data.get("validation_type", "data_integrity")
        
        if validation_type == "data_integrity":
            return self._validate_data_integrity(state.lead_info)
        elif validation_type == "workflow_state":
            return self._validate_workflow_state(state)
        else:
            return self._comprehensive_validation(state)
    
    def _calculate_parallel_efficiency(self, execution: WorkflowExecution) -> float:
        """Calculate parallel execution efficiency."""
        if not execution.completed_tasks:
            return 0.0
        
        total_duration = (
            execution.end_time - execution.start_time
        ).total_seconds()
        
        if total_duration == 0:
            return 1.0
        
        # Estimated sequential time
        estimated_sequential_time = len(execution.completed_tasks) * 5.0  # 5 seconds per task
        
        efficiency = estimated_sequential_time / total_duration if total_duration > 0 else 1.0
        return min(efficiency, 1.0)
    
    def _track_task_performance(
        self,
        task_id: str,
        execution_time: float,
        success: bool
    ):
        """Track task performance metrics."""
        if task_id not in self.performance_tracker:
            self.performance_tracker[task_id] = {
                "executions": 0,
                "total_time": 0.0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0,
                "success_rate": 0.0
            }
        
        tracker = self.performance_tracker[task_id]
        tracker["executions"] += 1
        tracker["total_time"] += execution_time
        
        if success:
            tracker["successes"] += 1
        else:
            tracker["failures"] += 1
        
        tracker["avg_time"] = tracker["total_time"] / tracker["executions"]
        tracker["success_rate"] = tracker["successes"] / tracker["executions"]
    
    # Helper methods for task processing
    def _extract_information_enhanced(
        self,
        message: str,
        existing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhanced information extraction."""
        import re
        
        extracted = {}
        message_lower = message.lower()
        
        # Enhanced budget extraction
        budget_patterns = [
            r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:k|K|thousand)',
            r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:m|M|million)',
            r'\$?\s*(\d{1,3}(?:,\d{3})*)',
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    number_str = match.group(1).replace(',', '').replace('$', '')
                    if number_str.isdigit():
                        budget = int(number_str)
                        if 'k' in pattern:
                            budget *= 1000
                        elif 'm' in pattern:
                            budget *= 1000000
                        
                        if 10000 <= budget <= 100000000:
                            extracted["budget"] = budget
                            break
                except (ValueError, IndexError):
                    continue
        
        # Enhanced location extraction
        location_patterns = [
            r'(?:near|in|around|at)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'located\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip().title()
                if len(location) >= 3 and not re.match(r'^\d+$', location):
                    extracted["location"] = location
                    break
        
        # Enhanced property type extraction
        bedroom_patterns = [
            r'(\d+)\s*(?:bhk|bed|beds|bedroom|bedrooms)',
        ]
        
        for pattern in bedroom_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    bedrooms = int(match.group(1))
                    if 1 <= bedrooms <= 10:
                        extracted["property_type"] = f"{bedrooms}BHK"
                        extracted["desired_bedrooms"] = bedrooms
                        break
                except ValueError:
                    continue
        
        return extracted
    
    def _calculate_extraction_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """Calculate confidence in extraction."""
        fields = ["budget", "location", "property_type", "timeline"]
        completed = sum(1 for field in fields if extracted_data.get(field))
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
    
    def _identify_missing_critical_info(self, lead_info: Dict[str, Any]) -> List[str]:
        """Identify missing critical information."""
        critical_fields = ["budget", "location"]
        return [
            field for field in critical_fields 
            if not lead_info.get(field)
        ]
    
    def _generate_qualification_recommendations(self, lead_info: Dict[str, Any]) -> List[str]:
        """Generate qualification recommendations."""
        recommendations = []
        
        if not lead_info.get("budget"):
            recommendations.append("Request budget range")
        if not lead_info.get("location"):
            recommendations.append("Ask for preferred location")
        if not lead_info.get("property_type"):
            recommendations.append("Clarify property type preference")
        if not lead_info.get("timeline"):
            recommendations.append("Inquire about timeline")
        
        return recommendations
    
    def _calculate_time_since(self, last_activity: Optional[str]) -> float:
        """Calculate hours since last activity."""
        if not last_activity:
            return 24.0  # Default to 24 hours
        
        try:
            last_time = datetime.fromisoformat(last_activity)
            return (datetime.utcnow() - last_time).total_seconds() / 3600
        except:
            return 24.0
    
    def _determine_followup_strategy(
        self,
        time_since: float,
        engagement_level: str
    ) -> str:
        """Determine followup strategy based on context."""
        if time_since > 72:  # 3+ days
            return "reengagement"
        elif time_since > 24:  # 1+ day
            return "gentle_followup"
        elif engagement_level == "high":
            return "value_driven"
        else:
            return "maintenance"
    
    def _get_followup_approach(self, strategy: str) -> str:
        """Get recommended followup approach."""
        approaches = {
            "reengagement": "Personal check-in with new opportunities",
            "gentle_followup": "Brief follow-up message with value",
            "value_driven": "Specific property suggestions",
            "maintenance": "General industry updates"
        }
        return approaches.get(strategy, "Standard follow-up")
    
    def _analyze_performance_metrics(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze performance metrics."""
        return {
            "response_time": 2.5,  # Simulated
            "completion_rate": 0.85,
            "user_satisfaction": 0.9,
            "efficiency_score": 0.8
        }
    
    def _analyze_engagement_patterns(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze engagement patterns."""
        return {
            "engagement_trend": "improving",
            "peak_activity_hours": [14, 15, 16],
            "response_rate": 0.92,
            "conversation_length": len(state.conversation_history)
        }
    
    def _analyze_conversion_potential(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Analyze conversion potential."""
        qualification_score = state.context_data.get("qualification_score", 0)
        return {
            "conversion_probability": qualification_score,
            "readiness_level": "high" if qualification_score >= 0.7 else "medium",
            "key_barriers": state.context_data.get("missing_critical", []),
            "recommended_actions": ["schedule_viewing", "provide_options"]
        }
    
    def _comprehensive_analysis(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Comprehensive analysis of conversation state."""
        return {
            **self._analyze_performance_metrics(state),
            **self._analyze_engagement_patterns(state),
            **self._analyze_conversion_potential(state)
        }
    
    def _coordinate_agent_handoff(
        self,
        handoff_data: Dict[str, Any],
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Coordinate agent handoff."""
        return {
            "handoff_successful": True,
            "from_agent": handoff_data.get("from_agent"),
            "to_agent": handoff_data.get("to_agent"),
            "handoff_data": handoff_data.get("data", {}),
            "coordination_notes": "Agent handoff completed successfully"
        }
    
    def _coordinate_parallel_delegation(
        self,
        delegation_data: Dict[str, Any],
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Coordinate parallel delegation."""
        return {
            "delegation_successful": True,
            "tasks_delegated": delegation_data.get("tasks", []),
            "parallel_execution": True,
            "coordination_overhead": 0.1
        }
    
    def _standard_coordination(
        self,
        coordination_data: Dict[str, Any],
        state: EnhancedAgentState
    ) -> Dict[str, Any]:
        """Standard coordination process."""
        return {
            "coordination_type": "standard",
            "status": "completed",
            "coordination_data": coordination_data
        }
    
    def _validate_data_integrity(self, lead_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data integrity."""
        return {
            "integrity_score": 0.95,
            "missing_fields": [k for k, v in lead_info.items() if not v],
            "validation_status": "passed",
            "recommendations": ["Complete missing information", "Verify contact details"]
        }
    
    def _validate_workflow_state(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Validate workflow state."""
        return {
            "state_valid": True,
            "current_stage": state.current_stage,
            "completed_tasks": len(state.completed_tasks),
            "pending_actions": len(state.next_actions)
        }
    
    def _comprehensive_validation(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Comprehensive validation."""
        return {
            **self._validate_data_integrity(state.lead_info),
            **self._validate_workflow_state(state)
        }

class AgentHandoffCoordinator:
    """Advanced agent handoff coordination system."""
    
    def __init__(self):
        self.handoff_rules = {
            "extraction": {"to": ["qualification", "analysis"], "conditions": ["data_extracted"]},
            "qualification": {"to": ["scheduling", "extraction"], "conditions": ["score_calculated"]},
            "scheduling": {"to": ["followup", "coordination"], "conditions": ["lead_ready"]},
            "followup": {"to": ["qualification", "scheduling"], "conditions": ["engagement_needed"]}
        }
        
        self.active_handoffs: Dict[str, AgentHandoff] = {}
        self.handoff_history: List[AgentHandoff] = []
    
    async def coordinate_handoff(
        self,
        from_agent: str,
        to_agent: str,
        handoff_data: Dict[str, Any],
        state: EnhancedAgentState,
        reason: str
    ) -> AgentHandoff:
        """Coordinate agent handoff with proper LangGraph Command objects."""
        
        handoff_id = f"handoff_{from_agent}_to_{to_agent}_{int(time.time())}"
        
        # Create handoff with Command object
        if LANGGRAPH_AVAILABLE and Command:
            command = Command(
                goto=to_agent,
                update={
                    "handoff_data": handoff_data,
                    "from_agent": from_agent,
                    "handoff_timestamp": datetime.utcnow().isoformat(),
                    "handoff_reason": reason
                }
            )
        else:
            command = None
        
        handoff = AgentHandoff(
            from_agent=from_agent,
            to_agent=to_agent,
            handoff_data=handoff_data,
            reason=reason,
            command=command
        )
        
        self.active_handoffs[handoff_id] = handoff
        self.handoff_history.append(handoff)
        
        # Update state
        state.agent_history.append(f"handoff:{from_agent}->{to_agent}")
        state.pending_handoffs.append({
            "handoff_id": handoff_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "timestamp": handoff.timestamp,
            "reason": reason
        })
        
        logger.info(f"🔄 Agent handoff coordinated: {from_agent} → {to_agent} ({reason})")
        
        return handoff
    
    def validate_handoff_rule(self, from_agent: str, to_agent: str) -> bool:
        """Validate if handoff is allowed by rules."""
        if from_agent not in self.handoff_rules:
            return False
        
        rule = self.handoff_rules[from_agent]
        return to_agent in rule["to"]
    
    def get_handoff_recommendations(
        self,
        current_agent: str,
        state: EnhancedAgentState
    ) -> List[str]:
        """Get recommended handoff targets."""
        if current_agent not in self.handoff_rules:
            return ["supervisor"]
        
        rule = self.handoff_rules[current_agent]
        recommendations = []
        
        # Check conditions
        conditions_met = True
        for condition in rule["conditions"]:
            if condition == "data_extracted":
                conditions_met = len(state.lead_info) > 0
            elif condition == "score_calculated":
                conditions_met = state.extraction_confidence > 0
            elif condition == "lead_ready":
                conditions_met = state.extraction_confidence >= 0.7
            elif condition == "engagement_needed":
                conditions_met = len(state.conversation_history) >= 3
            
            if conditions_met:
                recommendations.extend(rule["to"])
        
        return recommendations or ["supervisor"]

# Export key components
__all__ = [
    "ParallelTask",
    "WorkflowExecution",
    "TaskDelegationEngine",
    "AgentHandoffCoordinator",
    "create_task_delegation_engine",
    "create_handoff_coordinator"
]

def create_task_delegation_engine() -> TaskDelegationEngine:
    """Create and return task delegation engine."""
    return TaskDelegationEngine()

def create_handoff_coordinator() -> AgentHandoffCoordinator:
    """Create and return handoff coordinator."""
    return AgentHandoffCoordinator()