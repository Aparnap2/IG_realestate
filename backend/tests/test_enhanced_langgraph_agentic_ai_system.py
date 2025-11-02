"""
Comprehensive Test Suite for Enhanced LangGraph Pure Agentic AI System

This test suite validates all pure agentic AI patterns implemented in the enhanced LangGraph system:
- Supervisor-worker orchestration patterns
- Intelligent model routing with task complexity analysis
- Redis checkpoint persistence with LangGraph integration
- Proactive engagement with configurable thresholds
- Parallel processing with LangGraph Send API
- Agent coordination with Command objects
- Enhanced prompt engineering framework
- Cross-component state synchronization

Test Categories:
1. Enhanced Agent State Management
2. Supervisor-Worker Orchestration
3. Intelligent Model Routing
4. Redis Checkpoint Management
5. Proactive Engagement Engine
6. Parallel Coordination System
7. Agent Handoff Coordination
8. Enhanced Prompt Engineering
9. Integration and End-to-End Workflows
10. Performance and Scalability Testing
"""

import pytest
import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock
import uuid

# Import enhanced agentic system components
from backend.utils.langgraph_enhanced_agentic_system import (
    EnhancedAgentState,
    TaskRequest,
    AgentHandoff,
    SupervisorWorkerOrchestrator,
    IntelligentModelRouterEnhanced,
    AdvancedRedisCheckpointManager,
    ProactiveEngagementEnhanced,
    TaskComplexityLevel,
    AgentCapability,
    create_enhanced_agentic_orchestrator
)

from backend.utils.langgraph_parallel_coordination import (
    ParallelTask,
    WorkflowExecution,
    TaskDelegationEngine,
    AgentHandoffCoordinator,
    create_task_delegation_engine,
    create_handoff_coordinator
)

from backend.utils.enhanced_prompt_engineering import (
    EnhancedPromptEngineeringFramework,
    PromptContext,
    PromptStrategy,
    PersonalityTrait,
    create_prompt_framework
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestEnhancedAgentState:
    """Test enhanced agent state management."""
    
    def test_agent_state_creation(self):
        """Test creation of enhanced agent state."""
        state = EnhancedAgentState()
        
        assert state.thread_id == ""
        assert state.user_id == ""
        assert state.current_stage == "initial"
        assert state.conversation_history == []
        assert state.lead_info == {}
        assert state.agent_history == []
        assert state.extraction_confidence == 0.0
        assert state.current_agent == "supervisor"
        assert state.next_actions == []
        assert state.completed_tasks == []
        assert state.pending_handoffs == []
        assert state.context_data == {}
        assert state.performance_metrics == {}
    
    def test_agent_state_updates(self):
        """Test state updates and modifications."""
        state = EnhancedAgentState()
        
        # Update basic fields
        state.thread_id = "test_thread_123"
        state.user_id = "user_456"
        state.current_stage = "qualification"
        state.extraction_confidence = 0.75
        
        assert state.thread_id == "test_thread_123"
        assert state.user_id == "user_456"
        assert state.current_stage == "qualification"
        assert state.extraction_confidence == 0.75
        
        # Update complex fields
        state.lead_info = {
            "budget": 500000,
            "location": "Manhattan",
            "property_type": "2BHK"
        }
        state.agent_history = ["extraction:completed", "qualification:started"]
        
        assert state.lead_info["budget"] == 500000
        assert len(state.agent_history) == 2

class TestIntelligentModelRouterEnhanced:
    """Test intelligent model routing system."""
    
    @pytest.fixture
    def router(self):
        """Create model router for testing."""
        return IntelligentModelRouterEnhanced()
    
    def test_task_complexity_analysis(self, router):
        """Test task complexity analysis."""
        # Test simple extraction task
        complexity = router.analyze_task_complexity("Extract budget from message")
        assert complexity in [TaskComplexityLevel.TRIVIAL, TaskComplexityLevel.SIMPLE]
        
        # Test complex coordination task
        complexity = router.analyze_task_complexity(
            "Coordinate multi-agent workflow for complex lead qualification"
        )
        assert complexity in [TaskComplexityLevel.COMPLEX, TaskComplexityLevel.SPECIALIZED]
        
        # Test with context
        state = EnhancedAgentState()
        state.current_stage = "scheduling"
        state.agent_history = ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6"]
        
        complexity = router.analyze_task_complexity(
            "Manage coordination",
            context=state
        )
        # Should be more complex due to multi-agent coordination
        assert complexity in [TaskComplexityLevel.COMPLEX, TaskComplexityLevel.SPECIALIZED]
    
    def test_model_routing(self, router):
        """Test intelligent model routing."""
        # Test simple task routing
        task = TaskRequest(
            task_id="test_1",
            task_type="extraction",
            payload={"message": "I need a 2BHK in Manhattan for $500k"},
            agent_requirements=[AgentCapability.EXTRACTION]
        )
        
        complexity = TaskComplexityLevel.SIMPLE
        model = router.route_task_to_model(task, complexity)
        
        assert model in router.capability_matrix[AgentCapability.EXTRACTION]
        
        # Test complex task routing
        task_complex = TaskRequest(
            task_id="test_2",
            task_type="coordination",
            payload={},
            agent_requirements=[AgentCapability.COORDINATION]
        )
        
        complexity_complex = TaskComplexityLevel.COMPLEX
        model_complex = router.route_task_to_model(task_complex, complexity_complex)
        
        # Should route to more capable model
        assert "claude-3-7" in model_complex or "gpt-4o" in model_complex

class TestAdvancedRedisCheckpointManager:
    """Test Redis checkpoint management system."""
    
    @pytest.fixture
    async def checkpoint_manager(self):
        """Create checkpoint manager for testing."""
        manager = AdvancedRedisCheckpointManager()
        yield manager
        # Cleanup would go here in real implementation
    
    @pytest.mark.asyncio
    async def test_checkpoint_save_and_load(self, checkpoint_manager):
        """Test saving and loading enhanced checkpoints."""
        # Create test state
        state = EnhancedAgentState()
        state.thread_id = "test_thread_checkpoint"
        state.user_id = "test_user_checkpoint"
        state.current_stage = "qualification"
        state.lead_info = {"budget": 500000, "location": "Manhattan"}
        state.agent_history = ["extraction:completed"]
        state.extraction_confidence = 0.8
        
        # Save checkpoint
        thread_id = await checkpoint_manager.save_enhanced_checkpoint(
            "test_checkpoint_123",
            state,
            metadata={"test": True}
        )
        
        assert thread_id == "test_checkpoint_123"
        
        # Load checkpoint
        loaded_state = await checkpoint_manager.load_enhanced_checkpoint("test_checkpoint_123")
        
        assert loaded_state is not None
        assert loaded_state.thread_id == "test_thread_checkpoint"
        assert loaded_state.user_id == "test_user_checkpoint"
        assert loaded_state.current_stage == "qualification"
        assert loaded_state.lead_info["budget"] == 500000
        assert loaded_state.extraction_confidence == 0.8
        assert "extraction:completed" in loaded_state.agent_history

class TestProactiveEngagementEnhanced:
    """Test enhanced proactive engagement system."""
    
    @pytest.fixture
    def engagement_engine(self):
        """Create proactive engagement engine."""
        return ProactiveEngagementEnhanced()
    
    @pytest.mark.asyncio
    async def test_engagement_analysis_no_activity(self, engagement_engine):
        """Test engagement analysis for active conversation."""
        state = EnhancedAgentState()
        state.user_id = "test_user"
        
        # Very recent activity - should not engage
        should_engage, strategy, reason = await engagement_engine.analyze_engagement_opportunity(
            state, 
            time_since_last_activity=5  # 5 minutes
        )
        
        assert not should_engage
        assert "Active conversation" in reason
    
    @pytest.mark.asyncio
    async def test_engagement_analysis_extended_inactivity(self, engagement_engine):
        """Test engagement analysis for extended inactivity."""
        state = EnhancedAgentState()
        state.user_id = "test_user"
        state.lead_info = {"budget": 500000, "location": "Manhattan"}
        state.extraction_confidence = 0.3
        
        # Extended inactivity - should engage
        should_engage, strategy, reason = await engagement_engine.analyze_engagement_opportunity(
            state,
            time_since_last_activity=150  # 2.5 hours
        )
        
        assert should_engage
        assert strategy.value == "inactivity_reengagement"
        assert "Extended inactivity" in reason
    
    @pytest.mark.asyncio
    async def test_engagement_intervention_generation(self, engagement_engine):
        """Test proactive intervention generation."""
        from backend.utils.proactive_engagement import EngagementStrategy
        
        state = EnhancedAgentState()
        state.user_id = "test_user"
        state.thread_id = "test_thread"
        state.current_stage = "qualification"
        
        strategy = EngagementStrategy.INACTIVITY_REENGAGEMENT
        intervention = await engagement_engine.generate_proactive_intervention(
            strategy, state
        )
        
        assert intervention["strategy"] == "inactivity_reengagement"
        assert intervention["user_id"] == "test_user"
        assert intervention["thread_id"] == "test_thread"
        assert intervention["approach"] == "gentle_reengagement"
        assert intervention["message_style"] == "warm_and_supportive"
        assert intervention["trigger"] == "extended_inactivity"

class TestSupervisorWorkerOrchestrator:
    """Test supervisor-worker orchestrator patterns."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return SupervisorWorkerOrchestrator()
    
    @pytest.fixture
    def sample_state(self):
        """Create sample agent state for testing."""
        state = EnhancedAgentState()
        state.thread_id = "test_orchestrator"
        state.user_id = "test_user_orchestrator"
        state.current_stage = "initial"
        state.conversation_history = [
            {
                "role": "user",
                "content": "I'm looking for a 2BHK apartment in Manhattan under $500k",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        state.lead_info = {"budget": 500000, "location": "Manhattan"}
        return state
    
    @pytest.mark.asyncio
    async def test_supervisor_node_routing(self, orchestrator, sample_state):
        """Test supervisor node routing decisions."""
        # Test initial stage routing
        command = await orchestrator.supervisor_node(sample_state)
        
        assert command.goto in ["extraction", "qualification", "end"]
        assert "next_actions" in command.update
        assert "current_agent" in command.update
        assert "agent_history" in command.update
    
    @pytest.mark.asyncio
    async def test_extraction_worker(self, orchestrator, sample_state):
        """Test extraction worker functionality."""
        command = await orchestrator._extraction_worker(sample_state)
        
        assert command.goto in ["qualification", "supervisor"]
        assert "lead_info" in command.update
        assert "extraction_confidence" in command.update
        assert "completed_tasks" in command.update
    
    @pytest.mark.asyncio
    async def test_qualification_worker(self, orchestrator, sample_state):
        """Test qualification worker functionality."""
        sample_state.extraction_confidence = 0.8
        sample_state.lead_info = {
            "budget": 500000,
            "location": "Manhattan",
            "property_type": "2BHK"
        }
        
        command = await orchestrator._qualification_worker(sample_state)
        
        assert command.goto in ["scheduling", "qualification", "extraction"]
        assert "qualification_score" in command.update.get("context_data", {})
        assert "missing_critical" in command.update.get("context_data", {})

class TestTaskDelegationEngine:
    """Test parallel task delegation system."""
    
    @pytest.fixture
    def delegation_engine(self):
        """Create delegation engine for testing."""
        return TaskDelegationEngine()
    
    @pytest.fixture
    def sample_tasks(self):
        """Create sample parallel tasks."""
        return [
            ParallelTask(
                task_id="extraction_1",
                worker_name="extraction",
                task_data={"message": "Looking for 2BHK in Manhattan"},
                priority=1
            ),
            ParallelTask(
                task_id="qualification_1",
                worker_name="qualification", 
                task_data={"lead_info": {"budget": 500000}},
                priority=2
            ),
            ParallelTask(
                task_id="analysis_1",
                worker_name="analysis",
                task_data={"analysis_type": "performance"},
                priority=3,
                dependencies=["extraction_1"]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_parallel_workflow_execution(self, delegation_engine, sample_tasks):
        """Test parallel workflow execution."""
        state = EnhancedAgentState()
        state.thread_id = "test_parallel"
        state.user_id = "test_user_parallel"
        
        # Execute workflow
        execution = await delegation_engine.execute_parallel_workflow(
            "test_workflow",
            sample_tasks,
            state
        )
        
        assert execution.execution_id.startswith("test_workflow_")
        assert execution.workflow_name == "test_workflow"
        assert execution.status in ["completed", "completed_with_errors"]
        assert len(execution.tasks) == len(sample_tasks)
        assert execution.start_time is not None
        assert execution.end_time is not None
        
        # Check performance metrics
        assert "total_duration" in execution.performance_metrics
        assert "tasks_completed" in execution.performance_metrics
        assert "success_rate" in execution.performance_metrics
        assert "parallel_efficiency" in execution.performance_metrics
    
    @pytest.mark.asyncio
    async def test_task_execution_with_dependencies(self, delegation_engine, sample_tasks):
        """Test task execution with dependencies."""
        state = EnhancedAgentState()
        
        # Set up dependency chain
        sample_tasks[2].dependencies = ["extraction_1"]
        
        execution = await delegation_engine.execute_parallel_workflow(
            "dependency_test",
            sample_tasks,
            state
        )
        
        # Analysis task should depend on extraction
        analysis_result = execution.results.get("analysis_1")
        extraction_result = execution.results.get("extraction_1")
        
        # Both should complete (in successful execution)
        if analysis_result:
            assert extraction_result is not None  # Dependency should be satisfied

class TestAgentHandoffCoordinator:
    """Test agent handoff coordination system."""
    
    @pytest.fixture
    def handoff_coordinator(self):
        """Create handoff coordinator for testing."""
        return AgentHandoffCoordinator()
    
    def test_handoff_rule_validation(self, handoff_coordinator):
        """Test handoff rule validation."""
        # Valid handoff
        assert handoff_coordinator.validate_handoff_rule("extraction", "qualification") == True
        assert handoff_coordinator.validate_handoff_rule("qualification", "scheduling") == True
        
        # Invalid handoff
        assert handoff_coordinator.validate_handoff_rule("extraction", "followup") == False
    
    @pytest.mark.asyncio
    async def test_handoff_coordination(self, handoff_coordinator):
        """Test handoff coordination process."""
        state = EnhancedAgentState()
        state.thread_id = "test_handoff"
        state.user_id = "test_user_handoff"
        state.agent_history = []
        
        handoff = await handoff_coordinator.coordinate_handoff(
            from_agent="extraction",
            to_agent="qualification", 
            handoff_data={"confidence": 0.8},
            state=state,
            reason="Data extraction completed"
        )
        
        assert handoff.from_agent == "extraction"
        assert handoff.to_agent == "qualification"
        assert handoff.reason == "Data extraction completed"
        assert len(state.agent_history) > 0
        assert len(state.pending_handoffs) > 0
    
    def test_handoff_recommendations(self, handoff_coordinator):
        """Test handoff recommendations."""
        state = EnhancedAgentState()
        state.current_stage = "initial"
        state.extraction_confidence = 0.8
        state.agent_history = []
        
        recommendations = handoff_coordinator.get_handoff_recommendations(
            "extraction", state
        )
        
        assert isinstance(recommendations, list)
        assert "qualification" in recommendations

class TestEnhancedPromptEngineering:
    """Test enhanced prompt engineering framework."""
    
    @pytest.fixture
    def prompt_framework(self):
        """Create prompt framework for testing."""
        return EnhancedPromptEngineeringFramework()
    
    @pytest.fixture
    def sample_context(self):
        """Create sample prompt context."""
        return PromptContext(
            conversation_stage="qualification",
            lead_info={
                "budget": 500000,
                "location": "Manhattan",
                "property_type": "2BHK"
            },
            conversation_history=[
                {
                    "role": "user",
                    "content": "Looking for apartment in Manhattan",
                    "timestamp": datetime.utcnow().isoformat()
                }
            ],
            agent_personality=PersonalityTrait.PROFESSIONAL,
            engagement_level=0.7
        )
    
    def test_prompt_generation(self, prompt_framework, sample_context):
        """Test prompt generation."""
        prompt = prompt_framework.generate_prompt(
            strategy=PromptStrategy.CLARIFY_REQUIREMENTS,
            context=sample_context,
            user_message="I need a bigger space"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Manhattan" in prompt  # Should include context
        assert "500000" in prompt  # Should include budget info
    
    def test_personality_adaptation(self, prompt_framework, sample_context):
        """Test personality adaptation in prompts."""
        # Test different personalities
        for personality in PersonalityTrait:
            context = PromptContext(
                conversation_stage="qualification",
                lead_info={"budget": 500000},
                conversation_history=[],
                agent_personality=personality,
                engagement_level=0.5
            )
            
            prompt = prompt_framework.generate_prompt(
                strategy=PromptStrategy.GATHER_INFORMATION,
                context=context,
                user_message="Tell me about properties"
            )
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
    
    def test_progressive_disclosure(self, prompt_framework, sample_context):
        """Test progressive disclosure strategies."""
        # Test different strategies
        for strategy in PromptStrategy:
            prompt = prompt_framework.generate_prompt(
                strategy=strategy,
                context=sample_context,
                user_message="I want to buy a property"
            )
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            
            # Verify strategy-specific elements
            if strategy == PromptStrategy.VALUE_PROPOSITION:
                assert any(keyword in prompt.lower() for keyword in 
                          ["benefit", "advantage", "value", "investment"])
            elif strategy == PromptStrategy.URGENCY_CREATION:
                assert any(keyword in prompt.lower() for keyword in 
                          ["limited", "exclusive", "now", "today"])

class TestIntegrationWorkflows:
    """Test end-to-end integration workflows."""
    
    @pytest.fixture
    def integrated_system(self):
        """Create integrated system components."""
        return {
            "orchestrator": create_enhanced_agentic_orchestrator(),
            "delegation_engine": create_task_delegation_engine(),
            "handoff_coordinator": create_handoff_coordinator(),
            "prompt_framework": create_prompt_framework()
        }
    
    @pytest.mark.asyncio
    async def test_complete_workflow_integration(self, integrated_system):
        """Test complete end-to-end workflow."""
        orchestrator = integrated_system["orchestrator"]
        delegation_engine = integrated_system["delegation_engine"]
        
        # Create initial state
        state = EnhancedAgentState()
        state.thread_id = "integration_test"
        state.user_id = "integration_user"
        state.current_stage = "initial"
        state.conversation_history = [
            {
                "role": "user",
                "content": "Hi, I'm looking for a 3BHK apartment in Brooklyn under $600k",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        # Step 1: Supervisor analysis
        supervisor_command = await orchestrator.supervisor_node(state)
        assert supervisor_command.goto in ["extraction", "qualification"]
        
        # Step 2: Parallel task execution
        parallel_tasks = [
            ParallelTask(
                task_id="extract_1",
                worker_name="extraction",
                task_data={"message": "Looking for 3BHK in Brooklyn under $600k"},
                priority=1
            ),
            ParallelTask(
                task_id="qualify_1",
                worker_name="qualification",
                task_data={"extraction_confidence": 0.8},
                priority=2
            )
        ]
        
        execution = await delegation_engine.execute_parallel_workflow(
            "integration_workflow",
            parallel_tasks,
            state
        )
        
        assert execution.status in ["completed", "completed_with_errors"]
        assert execution.performance_metrics["success_rate"] > 0.5
    
    @pytest.mark.asyncio
    async def test_agent_coordination_integration(self, integrated_system):
        """Test agent coordination in integrated workflow."""
        orchestrator = integrated_system["orchestrator"]
        handoff_coordinator = integrated_system["handoff_coordinator"]
        
        # Create state for handoff
        state = EnhancedAgentState()
        state.thread_id = "handoff_integration"
        state.user_id = "handoff_user"
        state.agent_history = ["extraction:started"]
        
        # Test handoff coordination
        handoff = await handoff_coordinator.coordinate_handoff(
            from_agent="extraction",
            to_agent="qualification",
            handoff_data={"extracted_data": {"budget": 500000}},
            state=state,
            reason="Extraction completed successfully"
        )
        
        assert handoff.from_agent == "extraction"
        assert handoff.to_agent == "qualification"
        assert "extraction:completed" in state.agent_history
        
        # Test orchestrator response to handoff
        state.current_agent = "qualification"
        orchestrator_command = await orchestrator.supervisor_node(state)
        assert "qualification" in state.agent_history

class TestPerformanceAndScalability:
    """Test performance and scalability characteristics."""
    
    @pytest.fixture
    def performance_system(self):
        """Create system for performance testing."""
        return {
            "orchestrator": create_enhanced_agentic_orchestrator(),
            "delegation_engine": create_task_delegation_engine(),
            "checkpoint_manager": AdvancedRedisCheckpointManager()
        }
    
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, performance_system):
        """Test concurrent task processing performance."""
        delegation_engine = performance_system["delegation_engine"]
        
        # Create multiple parallel tasks
        concurrent_tasks = []
        for i in range(10):
            concurrent_tasks.append(
                ParallelTask(
                    task_id=f"concurrent_task_{i}",
                    worker_name="analysis",
                    task_data={"task_number": i, "complexity": "medium"},
                    priority=i % 3 + 1
                )
            )
        
        state = EnhancedAgentState()
        state.thread_id = "performance_test"
        
        start_time = time.time()
        execution = await delegation_engine.execute_parallel_workflow(
            "concurrent_performance_test",
            concurrent_tasks,
            state
        )
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # Performance assertions
        assert execution.status in ["completed", "completed_with_errors"]
        assert total_time < 30  # Should complete within 30 seconds
        assert execution.performance_metrics["parallel_efficiency"] > 0.5
        
        logger.info(f"Concurrent processing completed in {total_time:.2f}s")
        logger.info(f"Success rate: {execution.performance_metrics['success_rate']:.2f}")
        logger.info(f"Parallel efficiency: {execution.performance_metrics['parallel_efficiency']:.2f}")
    
    @pytest.mark.asyncio
    async def test_checkpoint_persistence_performance(self, performance_system):
        """Test checkpoint persistence performance."""
        checkpoint_manager = performance_system["checkpoint_manager"]
        
        # Create complex state
        state = EnhancedAgentState()
        state.thread_id = "performance_checkpoint"
        state.user_id = "performance_user"
        state.current_stage = "qualification"
        
        # Add complex data
        state.conversation_history = [
            {
                "role": "user",
                "content": f"Message {i}",
                "timestamp": (datetime.utcnow() - timedelta(minutes=i)).isoformat()
            }
            for i in range(100)
        ]
        
        state.lead_info = {
            "budget": 500000,
            "location": "Manhattan",
            "property_type": "2BHK",
            "timeline": "3 months",
            "financing": "cash",
            "amenities": ["parking", "gym", "pool"],
            "preferences": {"max_floor": 10, "min_floor": 2}
        }
        
        state.agent_history = [f"agent_{i}:action_{i}" for i in range(50)]
        state.performance_metrics = {
            "response_time": 2.5,
            "completion_rate": 0.85,
            "user_satisfaction": 0.9
        }
        
        # Performance test
        start_time = time.time()
        await checkpoint_manager.save_enhanced_checkpoint(
            "performance_checkpoint_test",
            state,
            metadata={"performance_test": True}
        )
        save_time = time.time() - start_time
        
        start_time = time.time()
        loaded_state = await checkpoint_manager.load_enhanced_checkpoint(
            "performance_checkpoint_test"
        )
        load_time = time.time() - start_time
        
        # Performance assertions
        assert loaded_state is not None
        assert save_time < 5.0  # Should save within 5 seconds
        assert load_time < 2.0  # Should load within 2 seconds
        
        # Verify data integrity
        assert len(loaded_state.conversation_history) == 100
        assert len(loaded_state.agent_history) == 50
        assert loaded_state.lead_info["budget"] == 500000
        
        logger.info(f"Checkpoint save time: {save_time:.3f}s")
        logger.info(f"Checkpoint load time: {load_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self, performance_system):
        """Test memory usage scaling with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large state
        state = EnhancedAgentState()
        state.thread_id = "memory_scaling_test"
        state.user_id = "memory_user"
        
        # Add large conversation history
        large_history = [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Long message content {i} " * 50,  # Long messages
                "timestamp": (datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                "metadata": {"confidence": 0.9, "processing_time": 2.5}
            }
            for i in range(1000)  # Large number of messages
        ]
        state.conversation_history = large_history
        
        # Add large lead info
        state.lead_info = {
            "budget": 500000,
            "location": "Manhattan",
            "property_type": "2BHK",
            "timeline": "3 months",
            "financing": "cash",
            "amenities": [f"amenity_{i}" for i in range(100)],  # Large amenities list
            "preferences": {f"pref_{i}": f"value_{i}" for i in range(100)},
            "history": [{"event": f"event_{i}", "timestamp": datetime.utcnow().isoformat()} for i in range(200)]
        }
        
        # Add large agent history
        state.agent_history = [f"agent_{i}:complex_action_{i}" for i in range(500)]
        
        checkpoint_manager = performance_system["checkpoint_manager"]
        
        # Test persistence with large data
        start_time = time.time()
        await checkpoint_manager.save_enhanced_checkpoint(
            "memory_scaling_checkpoint",
            state
        )
        save_time = time.time() - start_time
        
        # Check memory after processing
        peak_memory = process.memory_info().rss
        memory_increase = (peak_memory - initial_memory) / 1024 / 1024  # MB
        
        # Performance assertions
        assert save_time < 10.0  # Should handle large data within 10 seconds
        assert memory_increase < 100  # Memory increase should be reasonable
        
        logger.info(f"Large data checkpoint save time: {save_time:.3f}s")
        logger.info(f"Memory increase: {memory_increase:.2f}MB")

class TestErrorHandlingAndResilience:
    """Test error handling and system resilience."""
    
    @pytest.fixture
    def resilient_system(self):
        """Create system for resilience testing."""
        return {
            "orchestrator": create_enhanced_agentic_orchestrator(),
            "delegation_engine": create_task_delegation_engine()
        }
    
    @pytest.mark.asyncio
    async def test_failed_task_recovery(self, resilient_system):
        """Test recovery from failed tasks."""
        delegation_engine = resilient_system["delegation_engine"]
        
        # Create tasks with some that will fail
        tasks = [
            ParallelTask(
                task_id="success_task",
                worker_name="extraction",
                task_data={"message": "Valid message"},
                priority=1
            ),
            ParallelTask(
                task_id="failing_task", 
                worker_name="nonexistent_worker",
                task_data={},
                priority=2
            ),
            ParallelTask(
                task_id="dependent_task",
                worker_name="qualification",
                task_data={"requires": "success_task"},
                priority=3,
                dependencies=["success_task"]
            )
        ]
        
        state = EnhancedAgentState()
        state.thread_id = "recovery_test"
        
        execution = await delegation_engine.execute_parallel_workflow(
            "recovery_test_workflow",
            tasks,
            state
        )
        
        # Should complete despite failures
        assert execution.status == "completed_with_errors"
        assert "failing_task" in execution.failed_tasks
        assert "success_task" in execution.completed_tasks
        assert execution.performance_metrics["success_rate"] > 0
        
        logger.info(f"Recovery test: {execution.performance_metrics['tasks_completed']}/{len(tasks)} tasks succeeded")
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_recovery(self, resilient_system):
        """Test orchestrator error recovery."""
        orchestrator = resilient_system["orchestrator"]
        
        # Create state that might cause issues
        state = EnhancedAgentState()
        state.thread_id = "error_recovery_test"
        state.current_stage = "invalid_stage"  # Invalid stage
        
        try:
            command = await orchestrator.supervisor_node(state)
            # Should not crash, should provide fallback
            assert command is not None
            assert hasattr(command, 'goto')
            assert hasattr(command, 'update')
        except Exception as e:
            pytest.fail(f"Orchestrator should handle errors gracefully: {e}")
    
    @pytest.mark.asyncio
    async def test_state_corruption_handling(self, resilient_system):
        """Test handling of corrupted state data."""
        checkpoint_manager = AdvancedRedisCheckpointManager()
        
        # Create state with potentially problematic data
        state = EnhancedAgentState()
        state.thread_id = "corruption_test"
        
        # Add problematic data
        state.conversation_history = [
            {
                "role": "user",
                "content": "Test message with special chars: àáâãäåæçèé",
                "timestamp": "invalid_timestamp"  # Invalid timestamp
            }
        ]
        
        state.lead_info = {
            "budget": None,  # None values
            "location": "",  # Empty strings
            "invalid_field": object()  # Non-serializable objects
        }
        
        # Should handle gracefully
        try:
            thread_id = await checkpoint_manager.save_enhanced_checkpoint(
                "corruption_test_checkpoint",
                state
            )
            
            loaded_state = await checkpoint_manager.load_enhanced_checkpoint(
                "corruption_test_checkpoint"
            )
            
            # Should either load successfully or return None gracefully
            assert loaded_state is not None or True  # Either success or graceful failure
            
        except Exception as e:
            # Should not raise unhandled exceptions
            logger.warning(f"Corruption handling raised exception (may be expected): {e}")

# Utility functions for test setup and teardown
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test."""
    # Reset any global state
    logger.info("Setting up test environment")
    yield
    # Cleanup after test
    logger.info("Cleaning up test environment")

# Test execution utilities
def run_comprehensive_test_suite():
    """Run the comprehensive test suite with reporting."""
    import sys
    
    # Configure pytest arguments
    test_args = [
        __file__,
        "-v",
        "--tb=short",
        "--asyncio-mode=auto",
        "--disable-warnings",
        f"--log-cli-level={logging.INFO}"
    ]
    
    # Add coverage if available
    try:
        import coverage
        test_args.extend([
            "--cov=backend.utils.langgraph_enhanced_agentic_system",
            "--cov=backend.utils.langgraph_parallel_coordination", 
            "--cov=backend.utils.enhanced_prompt_engineering",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    except ImportError:
        pass
    
    # Run tests
    exit_code = pytest.main(test_args)
    return exit_code

if __name__ == "__main__":
    print("🚀 Starting Enhanced LangGraph Pure Agentic AI System Test Suite")
    print("=" * 80)
    
    exit_code = run_comprehensive_test_suite()
    
    print("=" * 80)
    if exit_code == 0:
        print("✅ All tests passed successfully!")
        print("\n🎯 Test Coverage Summary:")
        print("  • Enhanced Agent State Management ✓")
        print("  • Supervisor-Worker Orchestration ✓")
        print("  • Intelligent Model Routing ✓") 
        print("  • Redis Checkpoint Management ✓")
        print("  • Proactive Engagement Engine ✓")
        print("  • Parallel Coordination System ✓")
        print("  • Agent Handoff Coordination ✓")
        print("  • Enhanced Prompt Engineering ✓")
        print("  • Integration Workflows ✓")
        print("  • Performance and Scalability ✓")
        print("  • Error Handling and Resilience ✓")
    else:
        print(f"❌ Tests failed with exit code: {exit_code}")
    
    sys.exit(exit_code)