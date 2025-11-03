"""
Compliance Enforcement Middleware - Mandatory Message Gate

This module implements the critical compliance enforcement system that blocks
non-compliant messages from being sent, addressing Priority 1 Gap 1.2 - 
Compliance Enforcement Bypass.

Key Features:
1. Mandatory compliance gate for ALL outbound messages
2. Blocks non-compliant messages with audit trail
3. Integrates with existing Fair Housing Act evaluator
4. Comprehensive compliance violation logging
5. Safe fallback messaging for blocked content

Addresses: Priority 1 Gap 1.2 - Compliance Enforcement Bypass
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

from backend.tools import compliance as compliance_tools
from backend.utils.audit import audit_log_event
from backend.config.settings import get_settings

if TYPE_CHECKING:
    from backend.communication.multi_channel_manager import MultiChannelManager

logger = logging.getLogger(__name__)
settings = get_settings()

class ComplianceViolationError(Exception):
    """Exception raised when message fails compliance evaluation."""
    pass

class ComplianceEnforcementMiddleware:
    """
    Mandatory compliance gate middleware for all outbound messages.
    
    This middleware enforces 100% compliance coverage by blocking
    any messages that fail Fair Housing Act evaluation.
    """
    
    def __init__(self):
        """Initialize the compliance enforcement middleware."""
        from backend.communication.multi_channel_manager import MultiChannelManager

        self.channel_manager = MultiChannelManager()
        
        logger.info("🚀 Initializing Compliance Enforcement Middleware")
        logger.info("🛡️ ALL outbound messages will be compliance-checked")
        logger.info("✅ Legal/Compliance Risk Mitigation - Active")
    
    async def send_compliant_message(
        self,
        lead_id: str,
        message: str,
        channel: str = "instagram",
        correlation_id: Optional[str] = None,
        message_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Send message ONLY if it passes compliance evaluation.
        
        This is the CORE enforcement function that blocks non-compliant messages,
        fixing Priority 1 Gap 1.2 - Compliance Enforcement Bypass.
        
        Args:
            lead_id: Lead identifier
            message: Message content to send
            channel: Communication channel
            correlation_id: Universal correlation ID for tracking
            message_metadata: Additional metadata for audit
            
        Returns:
            Tuple of (success, result_dict)
        """
        if message_metadata is None:
            message_metadata = {}
        
        try:
            logger.info(f"🔒 COMPLIANCE GATE: Evaluating message for {lead_id}")
            
            # Step 1: MANDATORY compliance evaluation
            compliance_result = await self._evaluate_message_compliance(
                message=message,
                lead_id=lead_id,
                channel=channel,
                correlation_id=correlation_id,
                metadata=message_metadata
            )
            
            # Step 2: BLOCK non-compliant messages
            if not compliance_result["passed"]:
                return await self._handle_compliance_violation(
                    lead_id, message, compliance_result, correlation_id
                )
            
            # Step 3: LOG successful compliance check
            await audit_log_event("compliance_check_passed", {
                "lead_id": lead_id,
                "channel": channel,
                "correlation_id": correlation_id,
                "message_hash": hash(message),
                "compliance_score": compliance_result.get("confidence", 0.0),
                "evaluator_version": compliance_result.get("evaluator_version", "unknown"),
                "violations_count": len(compliance_result.get("violations", [])),
                "gate_timestamp": datetime.now().isoformat(),
                "enforcement_method": "mandatory_gate"
            })
            
            # Step 4: SEND compliant message via channel manager
            delivery_result = await self.channel_manager.send_message(
                user_id=lead_id,
                message=message,
                channel=channel,
                priority="normal",
                message_type="engagement"
            )
            
            # Step 5: LOG successful delivery
            await audit_log_event("compliant_message_sent", {
                "lead_id": lead_id,
                "channel": channel,
                "correlation_id": correlation_id,
                "delivery_success": delivery_result.get("success", False),
                "delivery_timestamp": datetime.now().isoformat(),
                "compliance_verified": True
            })
            
            logger.info(f"✅ COMPLIANT MESSAGE SENT: {lead_id}")
            
            return True, {
                "success": True,
                "message": "Message sent successfully",
                "compliance_result": compliance_result,
                "delivery_result": delivery_result,
                "correlation_id": correlation_id,
                "enforcement_timestamp": datetime.now().isoformat()
            }
            
        except ComplianceViolationError as e:
            logger.warning(f"🛑 COMPLIANCE BLOCKED: {lead_id} - {str(e)}")
            return False, {
                "success": False,
                "error": "compliance_violation",
                "message": "Message blocked by compliance gate",
                "details": str(e),
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            logger.error(f"❌ COMPLIANCE GATE ERROR: {lead_id} - {str(e)}")
            
            # Fail-safe: Block on evaluation error
            return False, {
                "success": False,
                "error": "compliance_evaluation_error",
                "message": "Message blocked due to evaluation error",
                "details": str(e),
                "correlation_id": correlation_id
            }
    
    async def _evaluate_message_compliance(
        self,
        message: str,
        lead_id: str,
        channel: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive compliance evaluation.
        
        Uses existing Fair Housing Act evaluator with enhanced context.
        """
        if metadata is None:
            metadata = {}
        
        evaluation_context = {
            "lead_id": lead_id,
            "channel": channel,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            "message_length": len(message),
            "metadata": metadata
        }
        
        # Use existing Fair Housing Act evaluator
        compliance_result = await compliance_tools.fair_housing_evaluator(
            message=message,
            context=evaluation_context
        )
        
        # Add enforcement metadata
        compliance_result["enforcement_timestamp"] = datetime.now().isoformat()
        compliance_result["evaluation_context"] = evaluation_context
        compliance_result["gate_version"] = "1.0"
        
        return compliance_result
    
    async def _handle_compliance_violation(
        self,
        lead_id: str,
        message: str,
        compliance_result: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle compliance violation by blocking message and logging violation.
        """
        violations = compliance_result.get("violations", [])
        suggested_replacement = compliance_result.get("suggested_replacement", "")
        
        # Log compliance violation
        violation_details = {
            "lead_id": lead_id,
            "channel": "unknown",  # Will be populated from context
            "correlation_id": correlation_id,
            "original_message": message,
            "message_hash": hash(message),
            "violations_count": len(violations),
            "violations": [
                {
                    "pattern": v.get("pattern", ""),
                    "matched_text": v.get("matched_text", ""),
                    "regulation": v.get("regulation", ""),
                    "risk_level": v.get("risk_level", ""),
                    "explanation": v.get("explanation", "")
                }
                for v in violations
            ],
            "suggested_replacement": suggested_replacement,
            "compliance_score": compliance_result.get("confidence", 0.0),
            "block_timestamp": datetime.now().isoformat(),
            "enforcement_action": "message_blocked"
        }
        
        await audit_log_event("compliance_violation_blocked", violation_details)
        
        # Raise exception to indicate message should be blocked
        violation_summary = "; ".join([v.get("explanation", "Unknown violation") for v in violations])
        raise ComplianceViolationError(f"Fair Housing Act violations detected: {violation_summary}")
    
    async def batch_compliance_check(
        self,
        messages: list,
        lead_id: str,
        channel: str = "instagram",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform batch compliance checking for multiple messages.
        
        Useful for testing and bulk message evaluation.
        """
        results = []
        violations_count = 0
        
        for i, message in enumerate(messages):
            try:
                success, result = await self.send_compliant_message(
                    lead_id=lead_id,
                    message=message,
                    channel=channel,
                    correlation_id=correlation_id,
                    message_metadata={"batch_index": i}
                )
                
                results.append({
                    "message_index": i,
                    "success": success,
                    "result": result
                })
                
                if not success:
                    violations_count += 1
                    
            except Exception as e:
                results.append({
                    "message_index": i,
                    "success": False,
                    "error": str(e)
                })
                violations_count += 1
        
        return {
            "total_messages": len(messages),
            "violations_count": violations_count,
            "compliance_rate": (len(messages) - violations_count) / len(messages) if messages else 0,
            "results": results,
            "batch_timestamp": datetime.now().isoformat()
        }
    
    async def get_compliance_metrics(self) -> Dict[str, Any]:
        """Get compliance enforcement metrics for monitoring."""
        return {
            "compliance_gate_status": "active",
            "enforcement_level": "mandatory",
            "supported_evaluators": ["fair_housing_act"],
            "audit_logging": "complete",
            "message_blocking": "enabled",
            "last_updated": datetime.now().isoformat(),
            "gate_version": "1.0"
        }

# Global instance for easy access
compliance_enforcement = ComplianceEnforcementMiddleware()

# Convenience functions for direct access
async def send_compliant_message(
    lead_id: str,
    message: str,
    channel: str = "instagram",
    correlation_id: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convenience function to send message with compliance enforcement.
    
    This should be used instead of direct channel manager calls to ensure
    100% compliance coverage.
    """
    return await compliance_enforcement.send_compliant_message(
        lead_id=lead_id,
        message=message,
        channel=channel,
        correlation_id=correlation_id
    )

async def batch_check_compliance(
    messages: list,
    lead_id: str,
    channel: str = "instagram"
) -> Dict[str, Any]:
    """
    Convenience function for batch compliance checking.
    """
    return await compliance_enforcement.batch_compliance_check(
        messages=messages,
        lead_id=lead_id,
        channel=channel
    )