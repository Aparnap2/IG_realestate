"""
Test Compliance Tools - Fair Housing, GDPR, TCPA

Tests the compliance evaluation tools according to PRD specifications.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from tools.compliance import (
    fair_housing_evaluator,
    gdpr_tcpa_tracker,
    validate_tcpa_compliance,
    gdpr_data_minimization_check,
    _detect_pattern_violations,
    _generate_neutral_replacement
)


class TestFairHousingEvaluator:
    """Test Fair Housing Act compliance evaluator."""
    
    @pytest.mark.asyncio
    async def test_safe_message_passes(self, mock_audit):
        """Test that safe messages pass fair housing evaluation."""
        safe_message = "Beautiful 2BR apartment with modern amenities and great location"
        
        result = await fair_housing_evaluator(safe_message)
        
        assert result["passed"] == True
        assert len(result["violations"]) == 0
        assert result["suggested_replacement"] == safe_message
    
    @pytest.mark.asyncio
    async def test_age_discrimination_detected(self, mock_audit):
        """Test detection of age discrimination."""
        violation_message = "Perfect for young professionals"
        
        result = await fair_housing_evaluator(violation_message)
        
        assert result["passed"] == False
        assert len(result["violations"]) > 0
        assert any("age" in v.get("regulation", "").lower() for v in result["violations"])
        assert result["suggested_replacement"] != violation_message
    
    @pytest.mark.asyncio
    async def test_familial_status_discrimination(self, mock_audit):
        """Test detection of familial status discrimination."""
        violation_message = "Adults only building, no kids allowed"
        
        result = await fair_housing_evaluator(violation_message)
        
        assert result["passed"] == False
        assert len(result["violations"]) > 0
        assert any("familial" in v.get("regulation", "").lower() for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_religion_discrimination_detected(self, mock_audit):
        """Test detection of religious discrimination."""
        violation_message = "Great location near the church, perfect for Christian families"
        
        result = await fair_housing_evaluator(violation_message)
        
        assert result["passed"] == False
        assert len(result["violations"]) > 0
        assert any("religion" in v.get("regulation", "").lower() for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_race_proxy_discrimination(self, mock_audit):
        """Test detection of race proxy discrimination."""
        violation_message = "Very safe neighborhood with good schools"
        
        result = await fair_housing_evaluator(violation_message)
        
        assert result["passed"] == False
        assert len(result["violations"]) > 0
        assert any("race" in v.get("regulation", "").lower() for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_multiple_violations_detected(self, mock_audit):
        """Test detection of multiple violations in one message."""
        violation_message = "Perfect for young Christian professionals, adults only building"
        
        result = await fair_housing_evaluator(violation_message)
        
        assert result["passed"] == False
        assert len(result["violations"]) >= 2  # Should detect multiple violations
    
    @pytest.mark.asyncio
    async def test_context_aware_evaluation(self, mock_audit):
        """Test that evaluator considers context."""
        message = "Great property for your needs"
        context = {
            "lead_id": "test_123",
            "budget": 400000,
            "location": "Miami"
        }
        
        result = await fair_housing_evaluator(message, context)
        
        assert result["passed"] == True
        # Verify context was logged
        mock_audit.assert_called()
    
    @pytest.mark.asyncio
    async def test_evaluator_error_handling(self, mock_audit):
        """Test evaluator error handling."""
        # Mock LLM failure
        with patch('tools.compliance.ChatOpenAI') as mock_llm:
            mock_llm.side_effect = Exception("LLM API error")
            
            result = await fair_housing_evaluator("test message")
            
            # Should still work with pattern matching
            assert "passed" in result
            assert "violations" in result


class TestPatternDetection:
    """Test pattern-based violation detection."""
    
    def test_age_pattern_detection(self):
        """Test age discrimination pattern detection."""
        violations = _detect_pattern_violations("Perfect for young professionals")
        
        assert len(violations) > 0
        assert any("age" in v.regulation.lower() for v in violations)
    
    def test_familial_status_patterns(self):
        """Test familial status pattern detection."""
        test_cases = [
            "Adults only",
            "No kids allowed", 
            "Families with children not preferred",
            "Mature tenants only"
        ]
        
        for message in test_cases:
            violations = _detect_pattern_violations(message)
            assert len(violations) > 0, f"Failed to detect violation in: {message}"
    
    def test_religion_patterns(self):
        """Test religion pattern detection."""
        test_cases = [
            "Near the church",
            "Christian community",
            "Close to synagogue",
            "Mosque walking distance"
        ]
        
        for message in test_cases:
            violations = _detect_pattern_violations(message)
            assert len(violations) > 0, f"Failed to detect violation in: {message}"
    
    def test_safe_messages_no_violations(self):
        """Test that safe messages don't trigger false positives."""
        safe_messages = [
            "Beautiful apartment with modern amenities",
            "Great location with easy access to transportation",
            "Spacious 2BR with updated kitchen",
            "Pet-friendly building with outdoor space"
        ]
        
        for message in safe_messages:
            violations = _detect_pattern_violations(message)
            assert len(violations) == 0, f"False positive for safe message: {message}"


class TestNeutralReplacement:
    """Test neutral message replacement generation."""
    
    def test_age_violation_replacement(self):
        """Test replacement for age discrimination."""
        from tools.compliance import FairHousingViolation
        
        violations = [FairHousingViolation(
            pattern="young professionals",
            matched_text="young professionals",
            regulation="Fair Housing Act - Age",
            risk_level="high",
            explanation="Age discrimination"
        )]
        
        original = "Perfect for young professionals"
        replacement = _generate_neutral_replacement(original, violations)
        
        assert "young" not in replacement.lower()
        assert "professionals" not in replacement.lower()
        assert len(replacement) > 20  # Should be meaningful
    
    def test_multiple_violations_replacement(self):
        """Test replacement for multiple violations."""
        from tools.compliance import FairHousingViolation
        
        violations = [
            FairHousingViolation(
                pattern="young",
                matched_text="young",
                regulation="Fair Housing Act - Age",
                risk_level="high",
                explanation="Age discrimination"
            ),
            FairHousingViolation(
                pattern="families",
                matched_text="families",
                regulation="Fair Housing Act - Familial Status",
                risk_level="high",
                explanation="Familial status discrimination"
            )
        ]
        
        original = "Perfect for young families"
        replacement = _generate_neutral_replacement(original, violations)
        
        assert "young" not in replacement.lower()
        assert "families" not in replacement.lower()
        assert "property" in replacement.lower() or "criteria" in replacement.lower()


class TestGDPRTCPACompliance:
    """Test GDPR and TCPA compliance tools."""
    
    def test_gdpr_tcpa_tracker(self, mock_audit):
        """Test GDPR/TCPA event tracking."""
        gdpr_tcpa_tracker(
            lead_id="test_lead_123",
            event="opt_in",
            metadata={
                "method": "instagram_dm",
                "timestamp": datetime.now().isoformat(),
                "ip_address": "192.168.1.1"
            }
        )
        
        # Verify audit event was logged
        mock_audit.assert_called()
        call_args = mock_audit.call_args[0]
        assert call_args[0] == "consent_tracking"
        assert "lead_id" in call_args[1]
    
    def test_tcpa_compliance_validation(self, mock_supabase):
        """Test TCPA compliance validation."""
        # Mock lead with valid consent
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[{
                "tcpa_opt_in": True,
                "consent_timestamp": datetime.now().isoformat()
            }]
        )
        
        result = validate_tcpa_compliance("test_lead", "sms")
        assert result == True
        
        # Mock lead without consent
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[{
                "tcpa_opt_in": False,
                "consent_timestamp": None
            }]
        )
        
        result = validate_tcpa_compliance("test_lead", "sms")
        assert result == False
    
    def test_gdpr_data_minimization(self):
        """Test GDPR data minimization check."""
        # Test with necessary fields only
        necessary_data = {
            "budget": 400000,
            "location": "Miami",
            "email": "test@example.com"
        }
        
        result = gdpr_data_minimization_check(necessary_data)
        assert result["compliant"] == True
        assert len(result["warnings"]) == 0
        
        # Test with sensitive fields
        sensitive_data = {
            "budget": 400000,
            "race": "Asian",  # Sensitive field
            "religion": "Christian"  # Sensitive field
        }
        
        result = gdpr_data_minimization_check(sensitive_data)
        assert result["compliant"] == False
        assert len(result["warnings"]) > 0
        assert any("sensitive" in warning.lower() for warning in result["warnings"])


class TestComplianceIntegration:
    """Test compliance tools integration with other components."""
    
    @pytest.mark.asyncio
    async def test_compliance_with_router_agent(self, mock_audit):
        """Test compliance integration with router agent."""
        from agents.router import RouterAgent
        
        router = RouterAgent()
        
        # Test that compliance is called during routing
        test_state = {
            "lead": Mock(user_id="test_123"),
            "messages": [{"role": "user", "content": "Perfect for young professionals"}]
        }
        
        # Mock LLM response
        with patch.object(router.llm, 'ainvoke') as mock_llm:
            mock_llm.return_value = Mock(
                intent="new_inquiry",
                confidence=0.8,
                next_agent="qualifier",
                reasoning="Test",
                urgency_level="medium"
            )
            
            result = await router.process(test_state)
            
            # Should be flagged for human review due to compliance violation
            assert result.get("requires_human_review") == True
    
    def test_compliance_audit_logging(self, mock_audit):
        """Test that compliance checks are properly audited."""
        gdpr_tcpa_tracker("test_lead", "consent_given", {"method": "web_form"})
        
        # Verify audit logging
        mock_audit.assert_called()
        
        # Check audit event structure
        call_args = mock_audit.call_args[0]
        assert call_args[0] == "consent_tracking"
        assert isinstance(call_args[1], dict)
        assert "lead_id" in call_args[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])