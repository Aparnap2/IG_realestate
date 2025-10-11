"""
Test Suite for Phase 1 Implementation

Tests Router Agent, Compliance Gates, and Audit Logging
according to PRD specifications.
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.router import RouterAgent, route_to_agent
from tools.compliance import fair_housing_evaluator, gdpr_tcpa_tracker
from utils.audit import audit_log_event, verify_audit_chain
from schemas.state import AgentState
from models.lead import Lead

class TestRouterAgent:
    """Test Router Agent functionality"""
    
    @pytest.fixture
    def sample_lead(self):
        """Create a sample lead for testing"""
        lead = Lead(
            user_id="test_user_123",
            channel="ig",
            message="I'm looking for a 3BR house under $400k in Miami"
        )
        return lead
    
    @pytest.fixture
    def sample_state(self, sample_lead):
        """Create a sample agent state"""
        return {
            "lead": sample_lead,
            "messages": [
                {"role": "user", "content": "I'm looking for a 3BR house under $400k in Miami"}
            ],
            "current_agent": None,
            "requires_human_review": False
        }
    
    @pytest.mark.asyncio
    async def test_router_intent_classification(self, sample_state):
        """Test that Router correctly classifies user intent"""
        router = RouterAgent()
        
        # Mock LLM response
        with patch.object(router, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=Mock(
                intent="new_inquiry",
                confidence=0.9,
                requires_qualification=True,
                next_agent="qualifier",
                reasoning="User expressing interest in property purchase",
                urgency_level="medium"
            ))
            
            result = await router.process(sample_state)
            
            assert result["current_agent"] == "qualifier"
            assert result["agent_decision"]["intent"] == "new_inquiry"
            assert result["agent_decision"]["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_router_compliance_gate(self, sample_state):
        """Test that Router blocks messages with compliance violations"""
        router = RouterAgent()
        
        # Test message with fair housing violation
        sample_state["messages"] = [
            {"role": "user", "content": "Do you have properties perfect for young professionals?"}
        ]
        
        with patch('tools.compliance.fair_housing_evaluator') as mock_evaluator:
            mock_evaluator.return_value = {
                "passed": False,
                "violations": [{"pattern": "age discrimination", "risk_level": "high"}],
                "suggested_replacement": "I can help you find properties that match your needs."
            }
            
            result = await router.process(sample_state)
            
            assert result["requires_human_review"] == True
            assert "compliance_flags" in result
            assert len(result["messages"]) > 1  # Neutral response added
    
    def test_route_to_agent_function(self, sample_state):
        """Test the conditional edge routing function"""
        # Test normal routing
        sample_state["current_agent"] = "qualifier"
        assert route_to_agent(sample_state) == "qualifier"
        
        # Test human review flag
        sample_state["requires_human_review"] = True
        assert route_to_agent(sample_state) == "human"
        
        # Test error state
        sample_state["error"] = "Some error"
        assert route_to_agent(sample_state) == "error_handler"
        
        # Test invalid agent fallback
        sample_state = {"current_agent": "invalid_agent"}
        assert route_to_agent(sample_state) == "qualifier"

class TestComplianceTools:
    """Test compliance evaluation tools"""
    
    @pytest.mark.asyncio
    async def test_fair_housing_pattern_detection(self):
        """Test pattern-based fair housing violation detection"""
        
        # Test age discrimination
        result = await fair_housing_evaluator("Perfect for young professionals")
        assert not result["passed"]
        assert any("age" in v.get("regulation", "").lower() for v in result["violations"])
        
        # Test familial status discrimination  
        result = await fair_housing_evaluator("Adults only building")
        assert not result["passed"]
        assert any("familial" in v.get("regulation", "").lower() for v in result["violations"])
        
        # Test safe message
        result = await fair_housing_evaluator("Beautiful 2BR apartment with modern amenities")
        assert result["passed"]
        assert len(result["violations"]) == 0
    
    def test_gdpr_tcpa_tracking(self):
        """Test GDPR/TCPA consent event tracking"""
        
        # Mock audit logging
        with patch('utils.audit.audit_log_event') as mock_audit:
            gdpr_tcpa_tracker(
                lead_id="test_lead_123",
                event="opt_in",
                metadata={"method": "instagram_dm", "timestamp": datetime.now().isoformat()}
            )
            
            # Verify audit event was logged
            mock_audit.assert_called()
            call_args = mock_audit.call_args[0]
            assert call_args[0] == "consent_tracking"
            assert "lead_id" in call_args[1]
    
    def test_neutral_message_generation(self):
        """Test generation of neutral alternatives for blocked content"""
        
        # Test with age discrimination
        message = "Perfect for young professionals in a quiet building"
        
        # This would be called internally by fair_housing_evaluator
        from tools.compliance import _generate_neutral_replacement, _detect_pattern_violations
        
        violations = _detect_pattern_violations(message)
        neutral = _generate_neutral_replacement(message, violations)
        
        assert "young" not in neutral.lower()
        assert "professionals" not in neutral.lower()
        assert len(neutral) > 20  # Should be a meaningful replacement

class TestAuditLogging:
    """Test immutable audit logging system"""
    
    def test_audit_event_creation(self):
        """Test creation of audit events with proper hashing"""
        
        with patch('utils.supabase_client.supabase') as mock_supabase:
            mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(data=[{"id": "test"}])
            
            event_id = audit_log_event(
                "test_event",
                {"test_data": "value"},
                entity_type="lead",
                entity_id="test_lead_123"
            )
            
            assert event_id != "audit_failed"
            mock_supabase.table.assert_called_with("audit_logs")
    
    def test_audit_chain_verification(self):
        """Test audit log chain integrity verification"""
        
        # Mock database response with valid chain
        mock_events = [
            {
                "id": "event1",
                "hash": "hash1", 
                "prev_hash": None,
                "timestamp": "2024-01-01T00:00:00Z",
                "event_type": "test",
                "entity_type": "system",
                "entity_id": "test",
                "payload": {}
            },
            {
                "id": "event2",
                "hash": "hash2",
                "prev_hash": "hash1", 
                "timestamp": "2024-01-01T00:01:00Z",
                "event_type": "test",
                "entity_type": "system", 
                "entity_id": "test",
                "payload": {}
            }
        ]
        
        with patch('utils.supabase_client.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = Mock(data=mock_events)
            
            # Mock hash verification to pass
            with patch('utils.audit._verify_event_hash', return_value=True):
                result = verify_audit_chain()
                
                assert result["valid"] == True
                assert result["events_checked"] == 2
                assert len(result["errors"]) == 0

class TestWorkflowIntegration:
    """Test workflow integration with Router Agent"""
    
    def test_workflow_creation_with_router(self):
        """Test that workflow can be created with Router Agent enabled"""
        
        with patch('utils.redis_client.test_redis_connection', return_value=True):
            with patch('config.get_settings') as mock_settings:
                mock_settings.return_value.ENABLE_ROUTER_AGENT = True
                
                from workflow import create_workflow
                
                # Should not raise an exception
                workflow = create_workflow()
                assert workflow is not None
    
    def test_workflow_validation(self):
        """Test workflow configuration validation"""
        
        from workflow import validate_workflow_config
        
        with patch('utils.redis_client.test_redis_connection', return_value=True):
            with patch('config.validate_instagram_config', return_value=True):
                with patch('config.validate_neo4j_config', return_value=True):
                    
                    result = validate_workflow_config()
                    
                    assert "redis_connection" in result
                    assert "router_enabled" in result
                    assert "compliance_enabled" in result
                    assert "overall_health" in result

class TestEndToEndFlow:
    """Test end-to-end flow from Instagram message to agent response"""
    
    @pytest.mark.asyncio
    async def test_compliant_message_flow(self):
        """Test full flow for compliant message"""
        
        # Create test state
        lead = Lead(
            user_id="test_user_e2e",
            channel="ig", 
            message="I'm interested in 2BR apartments under $300k"
        )
        
        state = {
            "lead": lead,
            "messages": [
                {"role": "user", "content": "I'm interested in 2BR apartments under $300k"}
            ]
        }
        
        router = RouterAgent()
        
        # Mock all external dependencies
        with patch.object(router, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=Mock(
                intent="new_inquiry",
                confidence=0.8,
                requires_qualification=True,
                next_agent="qualifier",
                reasoning="Clear property interest",
                urgency_level="medium"
            ))
            
            with patch('tools.compliance.fair_housing_evaluator') as mock_compliance:
                mock_compliance.return_value = {"passed": True, "violations": []}
                
                with patch('utils.audit.audit_log_event') as mock_audit:
                    
                    result = await router.process(state)
                    
                    # Verify successful routing
                    assert result["current_agent"] == "qualifier"
                    assert not result.get("requires_human_review", False)
                    
                    # Verify compliance check was called
                    mock_compliance.assert_called()
                    
                    # Verify audit logging
                    mock_audit.assert_called()
    
    @pytest.mark.asyncio 
    async def test_violation_message_flow(self):
        """Test full flow for message with compliance violation"""
        
        lead = Lead(
            user_id="test_user_violation",
            channel="ig",
            message="Do you have properties perfect for young couples?"
        )
        
        state = {
            "lead": lead,
            "messages": [
                {"role": "user", "content": "Do you have properties perfect for young couples?"}
            ]
        }
        
        router = RouterAgent()
        
        with patch('tools.compliance.fair_housing_evaluator') as mock_compliance:
            mock_compliance.return_value = {
                "passed": False,
                "violations": [{"pattern": "age", "risk_level": "medium"}],
                "suggested_replacement": "I can help you find properties that match your needs."
            }
            
            with patch('utils.audit.audit_log_event') as mock_audit:
                
                result = await router.process(state)
                
                # Verify human escalation
                assert result["requires_human_review"] == True
                assert result["current_agent"] == "human"
                assert "compliance_flags" in result
                
                # Verify neutral message was added
                assert len(result["messages"]) > 1
                neutral_message = result["messages"][-1]
                assert neutral_message["role"] == "assistant"
                assert "compliance_blocked" in neutral_message.get("metadata", {})

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])