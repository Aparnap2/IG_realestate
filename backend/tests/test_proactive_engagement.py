"""
Test Suite: LangGraph-Enhanced Proactive Engagement System

Tests for the proactive engagement system integration with LangGraph workflows,
including conversation context analysis, intervention generation, and execution.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Import the modules we're testing
from utils.proactive_engagement import (
    ProactiveEngagementConfig,
    LangGraphProactiveEngagement,
    EngagementStrategy,
    EngagementState
)

from utils.proactive_integration import (
    ProactiveLeadProcessor,
    ProactiveConversationManager,
    process_lead_with_proactive_engagement,
    manage_proactive_conversation_flow
)

class TestProactiveEngagementConfig:
    """Test the proactive engagement configuration."""
    
    def test_default_config_values(self):
        """Test default configuration values."""
        config = ProactiveEngagementConfig()
        
        assert config.inactivity_threshold_minutes == 30
        assert config.reengagement_attempts == 3
        assert config.reengagement_delay_hours == [1, 24, 72]
        assert config.max_questions_per_session == 5
        assert len(config.disclosure_levels) == 4
        assert len(config.personalization_features) == 5
        assert config.conversation_history_limit == 50
        assert config.context_window_messages == 10
    
    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = ProactiveEngagementConfig()
        config.inactivity_threshold_minutes = 45
        config.max_questions_per_session = 3
        
        assert config.inactivity_threshold_minutes == 45
        assert config.max_questions_per_session == 3

class TestLangGraphProactiveEngagement:
    """Test the main proactive engagement engine."""
    
    @pytest.fixture
    def proactive_engine(self):
        """Create a proactive engagement engine for testing."""
        config = ProactiveEngagementConfig()
        config.inactivity_threshold_minutes = 30
        return LangGraphProactiveEngagement(config)
    
    @pytest.fixture
    def sample_conversation_history(self):
        """Sample conversation history for testing."""
        return [
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "sender": "user",
                "message": "Hi, I'm interested in buying a condo",
                "response_time": 300
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=1, minutes=30)).isoformat(),
                "sender": "assistant",
                "message": "I'd be happy to help you find a condo! What's your budget range?",
                "response_time": 45
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "sender": "user",
                "message": "I'm thinking around $300k-400k",
                "response_time": 1800
            }
        ]
    
    @pytest.fixture
    def sample_current_state(self):
        """Sample current state for testing."""
        return {
            "user_id": "test_user_123",
            "lead": {
                "budget": "300000-400000",
                "property_type": "condo",
                "name": "John Doe",
                "phone": "555-0123",
                "email": "john@example.com",
                "timeline": None,
                "location": None,
                "desired_bedrooms": None
            },
            "conversation_history": [],
            "qualification": {
                "score": 0.5,
                "status": "partial_qualification"
            },
            "proactive_intervention_count": 0
        }
    
    @pytest.mark.asyncio
    async def test_analyze_conversation_context_basic(self, proactive_engine, sample_current_state):
        """Test basic conversation context analysis."""
        result = await proactive_engine.analyze_conversation_context(
            "test_user_123", sample_current_state
        )
        
        assert "user_id" in result
        assert "temporal_analysis" in result
        assert "momentum_analysis" in result
        assert "completeness_analysis" in result
        assert "recommended_strategy" in result
        assert "confidence_score" in result
        assert result["confidence_score"] >= 0.0
        assert result["confidence_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_analyze_conversation_context_with_history(self, proactive_engine, sample_current_state, sample_conversation_history):
        """Test conversation context analysis with historical data."""
        sample_current_state["conversation_history"] = sample_conversation_history
        
        result = await proactive_engine.analyze_conversation_context(
            "test_user_123", sample_current_state, sample_conversation_history
        )
        
        temporal = result["temporal_analysis"]
        assert "inactivity_duration_hours" in temporal
        assert "pattern" in temporal
        assert temporal["inactivity_duration_hours"] >= 0
    
    @pytest.mark.asyncio
    async def test_analyze_conversation_context_inactivity_detection(self, proactive_engine, sample_current_state):
        """Test inactivity detection in conversation analysis."""
        # Create old conversation history to trigger inactivity detection
        old_history = [
            {
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "sender": "user",
                "message": "Hello",
                "response_time": 120
            }
        ]
        sample_current_state["conversation_history"] = old_history
        
        result = await proactive_engine.analyze_conversation_context(
            "test_user_123", sample_current_state
        )
        
        temporal = result["temporal_analysis"]
        assert temporal["inactivity_duration_hours"] >= 24  # Should detect multi-day gap
    
    @pytest.mark.asyncio
    async def test_generate_proactive_intervention_inactivity(self, proactive_engine, sample_current_state):
        """Test proactive intervention generation for inactivity."""
        # Create context analysis with inactivity
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 25, "pattern": "long_gap"},
            "momentum_analysis": {"engagement_level": "low", "current_stage": "unknown"},
            "completeness_analysis": {"completeness_score": 0.3, "critical_missing": ["budget"]},
            "recommended_strategy": EngagementStrategy.INACTIVITY_REENGAGEMENT
        }
        
        result = await proactive_engine.generate_proactive_intervention(
            "test_user_123", context_analysis, sample_current_state
        )
        
        assert result["user_id"] == "test_user_123"
        assert result["strategy"] == EngagementStrategy.INACTIVITY_REENGAGEMENT.value
        assert "approach" in result
        assert "message_style" in result
        assert "intervention_timestamp" in result
    
    @pytest.mark.asyncio
    async def test_generate_proactive_intervention_progressive_disclosure(self, proactive_engine, sample_current_state):
        """Test proactive intervention generation for progressive disclosure."""
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 0.5},
            "momentum_analysis": {"engagement_level": "medium"},
            "completeness_analysis": {
                "completeness_score": 0.3,
                "critical_missing": ["budget", "location", "timeline"]
            },
            "recommended_strategy": EngagementStrategy.PROGRESSIVE_DISCLOSURE
        }
        
        result = await proactive_engine.generate_proactive_intervention(
            "test_user_123", context_analysis, sample_current_state
        )
        
        assert result["strategy"] == EngagementStrategy.PROGRESSIVE_DISCLOSURE.value
        assert "disclosure_sequence" in result
        assert "questions_per_session" in result
        assert result["questions_per_session"] <= len(context_analysis["completeness_analysis"]["critical_missing"])
    
    @pytest.mark.asyncio
    async def test_execute_intervention_with_langgraph(self, proactive_engine, sample_current_state):
        """Test intervention execution with LangGraph state management."""
        intervention = {
            "strategy": EngagementStrategy.CONTEXT_AWARE_SUGGESTION.value,
            "approach": "test_intervention",
            "message_style": "helpful",
            "content_type": "clarification"
        }
        
        with patch.object(proactive_engine, '_create_intervention_checkpoint', return_value="test_checkpoint_123"):
            with patch.object(proactive_engine, '_execute_intervention_strategy', return_value={"status": "executed"}):
                with patch.object(proactive_engine, '_update_langgraph_state'):
                    result = await proactive_engine.execute_intervention_with_langgraph(
                        "test_user_123", intervention, sample_current_state
                    )
        
        assert result["execution_status"] == "success"
        assert "checkpoint_id" in result
        assert "intervention_result" in result
        assert "updated_state" in result
    
    @pytest.mark.asyncio
    async def test_monitor_intervention_response(self, proactive_engine):
        """Test intervention response monitoring."""
        intervention_id = "test_checkpoint_123"
        response_data = {
            "user_response": "Thanks for the suggestion",
            "engagement_improved": True,
            "questions_answered": 2
        }
        
        checkpoint_state = {
            "intervention": {"strategy": "test_strategy"},
            "state": {"test": "data"}
        }
        
        with patch.object(proactive_engine, '_retrieve_intervention_checkpoint', return_value=checkpoint_state):
            with patch.object(proactive_engine, '_analyze_response_effectiveness', return_value={
                "effectiveness_score": 0.8,
                "adjustment_needed": False
            }):
                with patch.object(proactive_engine, '_update_langgraph_monitoring_state'):
                    result = await proactive_engine.monitor_intervention_response(
                        "test_user_123", intervention_id, response_data
                    )
        
        assert result["user_id"] == "test_user_123"
        assert result["intervention_id"] == intervention_id
        assert "response_analysis" in result
        assert "adjustment_needed" in result

class TestProactiveLeadProcessor:
    """Test the proactive lead processor integration."""
    
    @pytest.fixture
    def lead_processor(self):
        """Create a proactive lead processor for testing."""
        return ProactiveLeadProcessor()
    
    @pytest.fixture
    def sample_state_with_history(self):
        """Sample state with conversation history."""
        return {
            "user_id": "test_user_456",
            "lead": {
                "budget": "250000",
                "property_type": "house",
                "name": "Jane Smith",
                "location": "Downtown",
                "timeline": "3 months",
                "desired_bedrooms": 3
            },
            "conversation_history": [
                {
                    "timestamp": (datetime.now() - timedelta(minutes=45)).isoformat(),
                    "sender": "user",
                    "message": "I'm ready to make an offer",
                    "response_time": 90
                },
                {
                    "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
                    "sender": "assistant",
                    "message": "Great! Let me help you with that process",
                    "response_time": 30
                }
            ],
            "qualification": {
                "score": 0.8,
                "status": "qualified"
            },
            "proactive_intervention_count": 1
        }
    
    @pytest.mark.asyncio
    async def test_process_lead_with_proactive_engagement_basic(self, lead_processor, sample_state_with_history):
        """Test basic lead processing with proactive engagement."""
        result = await lead_processor.process_lead_with_proactive_engagement(
            "test_user_456", sample_state_with_history
        )
        
        assert "user_id" in result
        assert "processing_timestamp" in result
        assert "context_analysis" in result
        assert "proactive_intervention_triggered" in result
        assert "standard_processing" in result
        assert result["standard_processing"] is True
    
    @pytest.mark.asyncio
    async def test_process_lead_with_proactive_engagement_intervention_triggered(self, lead_processor, sample_state_with_history):
        """Test lead processing when proactive intervention is triggered."""
        # Mock the should_trigger_proactive_intervention to return True
        with patch.object(lead_processor, '_should_trigger_proactive_intervention', return_value=True):
            with patch('utils.proactive_engagement.generate_proactive_intervention') as mock_generate:
                with patch('utils.proactive_engagement.execute_intervention_with_langgraph') as mock_execute:
                    mock_generate.return_value = {
                        "strategy": "inactivity_reengagement",
                        "immediate_value": False
                    }
                    mock_execute.return_value = {
                        "execution_status": "success",
                        "checkpoint_id": "test_checkpoint"
                    }
                    
                    result = await lead_processor.process_lead_with_proactive_engagement(
                        "test_user_456", sample_state_with_history
                    )
        
        assert result["proactive_intervention_triggered"] is True
        assert "proactive_intervention" in result
        assert "intervention_execution" in result
        assert "proactive_processing" in result
    
    def test_should_trigger_proactive_intervention_inactivity(self, lead_processor):
        """Test intervention trigger for inactivity."""
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 1.5},
            "completeness_analysis": {"critical_missing": []},
            "momentum_analysis": {"engagement_level": "medium"}
        }
        current_state = {"proactive_intervention_count": 0}
        
        should_trigger = lead_processor._should_trigger_proactive_intervention(
            context_analysis, current_state
        )
        
        assert should_trigger is True  # 1.5 hours > 0.5 hours threshold
    
    def test_should_trigger_proactive_intervention_missing_info(self, lead_processor):
        """Test intervention trigger for missing information."""
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 0.2},
            "completeness_analysis": {"critical_missing": ["budget", "location", "timeline"]},
            "momentum_analysis": {"engagement_level": "medium"}
        }
        current_state = {"proactive_intervention_count": 0}
        
        should_trigger = lead_processor._should_trigger_proactive_intervention(
            context_analysis, current_state
        )
        
        assert should_trigger is True  # 3 critical missing > threshold of 2
    
    def test_should_trigger_proactive_intervention_low_engagement(self, lead_processor):
        """Test intervention trigger for low engagement."""
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 0.1},
            "completeness_analysis": {"critical_missing": []},
            "momentum_analysis": {"engagement_level": "low"}
        }
        current_state = {"proactive_intervention_count": 0}
        
        should_trigger = lead_processor._should_trigger_proactive_intervention(
            context_analysis, current_state
        )
        
        assert should_trigger is True  # Low engagement level
    
    def test_should_not_trigger_intervention_frequency_limit(self, lead_processor):
        """Test that intervention is not triggered due to frequency limits."""
        context_analysis = {
            "temporal_analysis": {"inactivity_duration_hours": 2.0},
            "completeness_analysis": {"critical_missing": ["budget", "location"]},
            "momentum_analysis": {"engagement_level": "medium"}
        }
        current_state = {"proactive_intervention_count": 5}  # At default limit
        
        should_trigger = lead_processor._should_trigger_proactive_intervention(
            context_analysis, current_state
        )
        
        assert should_trigger is False  # Frequency limit reached
    
    def test_detect_ambiguity_in_message(self, lead_processor):
        """Test ambiguity detection in user messages."""
        ambiguous_messages = [
            "I'm not sure what I want",
            "Maybe around that price range",
            "Kind of like that style",
            "What do you think about this?",
            "I'm not really sure"
        ]
        
        for message in ambiguous_messages:
            assert lead_processor._detect_ambiguity_in_recent_messages({"conversation_history": [{"message": message}]}) is True
        
        clear_messages = [
            "I want a 3-bedroom house",
            "My budget is $300,000",
            "I'm looking in downtown area",
            "I need to move within 2 months"
        ]
        
        for message in clear_messages:
            assert lead_processor._detect_ambiguity_in_recent_messages({"conversation_history": [{"message": message}]}) is False

class TestProactiveConversationManager:
    """Test the proactive conversation manager."""
    
    @pytest.fixture
    def conversation_manager(self):
        """Create a conversation manager for testing."""
        return ProactiveConversationManager()
    
    @pytest.fixture
    def sample_conversation_state(self):
        """Sample conversation state."""
        return {
            "user_id": "test_user_789",
            "conversation_history": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "sender": "user",
                    "message": "Hello",
                    "response_time": 120
                }
            ],
            "qualification": {"score": 0.6, "status": "partial_qualification"},
            "proactive_intervention_count": 0
        }
    
    @pytest.mark.asyncio
    async def test_manage_conversation_flow_message_received(self, conversation_manager, sample_conversation_state):
        """Test conversation flow management for message received event."""
        event_data = {"message": "Hi, I need help finding a property"}
        
        with patch('utils.proactive_integration.process_lead_with_proactive_engagement') as mock_process:
            mock_process.return_value = {
                "proactive_intervention_triggered": False,
                "context_analysis": {"test": "analysis"}
            }
            
            result = await conversation_manager.manage_conversation_flow(
                "test_user_789", sample_conversation_state, "message_received", event_data
            )
        
        assert result["event_handled"] == "message_received"
        assert "processing_result" in result
        assert "state_updates" in result
        assert "last_interaction" in result["state_updates"]
    
    @pytest.mark.asyncio
    async def test_manage_conversation_flow_inactivity_detected(self, conversation_manager, sample_conversation_state):
        """Test conversation flow management for inactivity detected event."""
        with patch('utils.proactive_engagement.analyze_conversation_context') as mock_analyze:
            with patch('utils.proactive_engagement.generate_proactive_intervention') as mock_generate:
                with patch('utils.proactive_engagement.execute_intervention_with_langgraph') as mock_execute:
                    mock_analyze.return_value = {"test": "analysis"}
                    mock_generate.return_value = {"strategy": "inactivity_reengagement"}
                    mock_execute.return_value = {"execution_status": "success"}
                    
                    result = await conversation_manager.manage_conversation_flow(
                        "test_user_789", sample_conversation_state, "inactivity_detected"
                    )
        
        assert result["event_handled"] == "inactivity_detected"
        assert "inactivity_intervention" in result
        assert "execution_result" in result
        assert "state_updates" in result
    
    @pytest.mark.asyncio
    async def test_manage_conversation_flow_qualification_update(self, conversation_manager, sample_conversation_state):
        """Test conversation flow management for qualification update event."""
        event_data = {
            "old_status": "partial_qualification",
            "new_status": "qualified"
        }
        
        with patch('utils.proactive_engagement.analyze_conversation_context') as mock_analyze:
            with patch('utils.proactive_engagement.generate_proactive_intervention') as mock_generate:
                with patch('utils.proactive_engagement.execute_intervention_with_langgraph') as mock_execute:
                    mock_analyze.return_value = {"test": "analysis"}
                    mock_generate.return_value = {
                        "strategy": "context_aware_suggestion",
                        "qualification_complete": True
                    }
                    mock_execute.return_value = {"execution_status": "success"}
                    
                    result = await conversation_manager.manage_conversation_flow(
                        "test_user_789", sample_conversation_state, "qualification_update", event_data
                    )
        
        assert result["event_handled"] == "qualification_update"
        assert "status_change" in result
        assert "follow_up_intervention" in result
        assert result["follow_up_intervention"]["qualification_complete"] is True

class TestIntegrationFunctions:
    """Test the convenience integration functions."""
    
    @pytest.mark.asyncio
    async def test_process_lead_with_proactive_engagement_function(self):
        """Test the convenience function for proactive lead processing."""
        user_id = "test_user_integration"
        current_state = {
            "user_id": user_id,
            "lead": {"budget": "300000"},
            "conversation_history": [],
            "proactive_intervention_count": 0
        }
        new_message = "I'm looking for a house"
        
        with patch('utils.proactive_integration.proactive_lead_processor.process_lead_with_proactive_engagement') as mock_process:
            mock_process.return_value = {"test": "result"}
            
            result = await process_lead_with_proactive_engagement(user_id, current_state, new_message)
        
        assert result == {"test": "result"}
    
    @pytest.mark.asyncio
    async def test_manage_proactive_conversation_flow_function(self):
        """Test the convenience function for proactive conversation management."""
        user_id = "test_user_flow"
        current_state = {"user_id": user_id}
        trigger_event = "message_received"
        event_data = {"message": "test message"}
        
        with patch('utils.proactive_integration.proactive_conversation_manager.manage_conversation_flow') as mock_manage:
            mock_manage.return_value = {"test": "flow_result"}
            
            result = await manage_proactive_conversation_flow(user_id, current_state, trigger_event, event_data)
        
        assert result == {"test": "flow_result"}

class TestErrorHandling:
    """Test error handling and fallback scenarios."""
    
    @pytest.mark.asyncio
    async def test_fallback_analysis_when_langgraph_unavailable(self):
        """Test fallback analysis when LangGraph is not available."""
        config = ProactiveEngagementConfig()
        engine = LangGraphProactiveEngagement(config)
        
        # Simulate LangGraph unavailability by patching the imports
        with patch('utils.proactive_engagement.LANGGRAPH_AVAILABLE', False):
            result = await engine.analyze_conversation_context("test_user", {})
        
        assert result["fallback_mode"] is True
        assert "temporal_analysis" in result
        assert "momentum_analysis" in result
        assert "completeness_analysis" in result
    
    @pytest.mark.asyncio
    async def test_error_handling_in_processing(self):
        """Test error handling in lead processing."""
        from utils.proactive_integration import ProactiveLeadProcessor
        lead_processor = ProactiveLeadProcessor()
        user_id = "test_user_error"
        current_state = {"user_id": user_id}

        # Simulate an error by making the analysis raise an exception
        with patch('utils.proactive_engagement.analyze_conversation_context', side_effect=Exception("Test error")):
            result = await lead_processor.process_lead_with_proactive_engagement(user_id, current_state)

        assert result["processing_status"] == "error"
        assert "error" in result
        assert "fallback_processing" in result
        assert result["fallback_processing"] is True

class TestProactiveEngagementPatterns:
    """Test proactive engagement patterns and strategies."""
    
    def test_engagement_patterns_loading(self):
        """Test that engagement patterns are properly loaded."""
        config = ProactiveEngagementConfig()
        engine = LangGraphProactiveEngagement(config)
        
        patterns = engine.engagement_patterns
        
        assert "inactivity_patterns" in patterns
        assert "ambiguity_patterns" in patterns
        assert "momentum_patterns" in patterns
        
        # Check inactivity patterns structure
        inactivity = patterns["inactivity_patterns"]
        assert "short_gap" in inactivity
        assert "medium_gap" in inactivity
        assert "long_gap" in inactivity
        
        # Check ambiguity patterns structure
        ambiguity = patterns["ambiguity_patterns"]
        assert "unclear_request" in ambiguity
        assert "partial_information" in ambiguity
        
        # Check momentum patterns structure
        momentum = patterns["momentum_patterns"]
        assert "high_engagement" in momentum
        assert "low_engagement" in momentum
        assert "declining_engagement" in momentum

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])