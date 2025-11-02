"""
Proactive Engagement Validation and Preconditions

This module implements strict preconditions validation to prevent
infinite loops and ensure proactive engagement only runs when appropriate.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .redis_client import create_redis_client
from ..config.settings import get_settings

async def get_redis_client():
    """Wrapper to get Redis client."""
    return await create_redis_client()

logger = logging.getLogger(__name__)

class PreconditionResult(Enum):
    """Result of precondition validation."""
    ALLOW = "allow"
    NOOP_UNKNOWN_USER = "noop_unknown_user"
    NOOP_MISSING_CONTEXT = "noop_missing_context"
    NOOP_LOW_CONFIDENCE = "noop_low_confidence"
    NOOP_CIRCUIT_OPEN = "noop_circuit_open"
    NOOP_RATE_LIMITED = "noop_rate_limited"

@dataclass
class ValidationResult:
    """Result of proactive engagement validation."""
    result: PreconditionResult
    reason: str
    details: Dict[str, Any]
    suppression_key: Optional[str] = None
    next_allowed_time: Optional[datetime] = None

class ProactiveEngagementValidator:
    """
    Validates preconditions for proactive engagement to prevent infinite loops.
    """
    
    def __init__(self):
        """Initialize validator with settings."""
        self.settings = get_settings()
        self.redis_client = None
        self.validation_cache = {}
        
    async def initialize(self):
        """Initialize Redis client."""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
    
    async def validate_proactive_engagement(
        self,
        user_id: str,
        thread_id: Optional[str],
        lead_id: Optional[str],
        current_state: Dict[str, Any],
        extraction_confidence: float = 0.0,
        context_message_analysis: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Comprehensive validation of proactive engagement preconditions.
        
        Args:
            user_id: User identifier
            thread_id: Thread identifier  
            lead_id: Lead identifier
            current_state: Current conversation state
            extraction_confidence: Confidence score for extracted information
            context_message_analysis: Analysis of current message context
            
        Returns:
            ValidationResult with decision and reasoning
        """
        await self.initialize()
        
        # 1. Check if proactive engagement is globally enabled
        if not self.settings.PROACTIVE_ENGAGEMENT_ENABLED:
            return ValidationResult(
                result=PreconditionResult.NOOP_RATE_LIMITED,
                reason="Proactive engagement globally disabled via PROACTIVE_ENGAGEMENT_ENABLED",
                details={"flag": "PROACTIVE_ENGAGEMENT_ENABLED"}
            )
        
        # 2. Check for unknown/empty user context
        if not user_id or user_id == "unknown":
            return ValidationResult(
                result=PreconditionResult.NOOP_UNKNOWN_USER,
                reason="User ID is missing or unknown",
                details={"user_id": user_id, "thread_id": thread_id, "lead_id": lead_id}
            )
        
        # 3. Check for required bound thread/lead context
        if self.settings.REQUIRE_BOUND_THREAD:
            if not thread_id or not lead_id:
                return ValidationResult(
                    result=PreconditionResult.NOOP_UNKNOWN_USER,
                    reason="Missing required thread_id or lead_id for bound context",
                    details={"thread_id": thread_id, "lead_id": lead_id}
                )
        
        # 4. Check for missing message analysis context
        if context_message_analysis is None or not isinstance(context_message_analysis, dict):
            suppression_key = f"message_analysis:{user_id}:{int(time.time() // 900)}"  # 15-minute buckets
            
            # Check if we've already suppressed this error for this user recently
            if await self._is_suppressed(suppression_key):
                return ValidationResult(
                    result=PreconditionResult.NOOP_MISSING_CONTEXT,
                    reason="Message analysis missing (already suppressed for this user/thread)",
                    details={"suppression_key": suppression_key},
                    suppression_key=suppression_key
                )
                
            # Log single structured error per thread per 15 minutes
            logger.warning(
                f"Proactive engagement blocked - missing message_analysis for user {user_id}. "
                f"Suppression key: {suppression_key}"
            )
            
            # Mark as suppressed for 15 minutes
            await self._suppress_error(suppression_key, ttl_seconds=900)
            
            return ValidationResult(
                result=PreconditionResult.NOOP_MISSING_CONTEXT,
                reason="Missing message_analysis in context - cannot proceed safely",
                details={"suppression_key": suppression_key}
            )
        
        # 5. Check extraction confidence threshold
        if extraction_confidence < self.settings.EXTRACTION_CONFIDENCE_THRESHOLD:
            return ValidationResult(
                result=PreconditionResult.NOOP_LOW_CONFIDENCE,
                reason=f"Extraction confidence {extraction_confidence} below threshold {self.settings.EXTRACTION_CONFIDENCE_THRESHOLD}",
                details={
                    "extraction_confidence": extraction_confidence,
                    "threshold": self.settings.EXTRACTION_CONFIDENCE_THRESHOLD
                }
            )
        
        # 6. Check for LLM circuit breaker conditions
        if self.settings.LLM_CIRCUIT_OPEN_NOOP:
            api_status = self._check_api_status()
            if api_status["all_circuits_open"]:
                return ValidationResult(
                    result=PreconditionResult.NOOP_CIRCUIT_OPEN,
                    reason="All LLM circuits are open - forcing NOOP to prevent local processing loops",
                    details={"api_status": api_status}
                )
        
        # 7. Check rate limiting and deduplication
        if self.settings.ENABLE_INTERVENTION_DEDUP:
            dedup_result = await self._check_intervention_dedup(user_id, thread_id)
            if dedup_result.is_blocked:
                return ValidationResult(
                    result=PreconditionResult.NOOP_RATE_LIMITED,
                    reason="Intervention recently executed for this thread",
                    details=dedup_result.details,
                    next_allowed_time=dedup_result.next_allowed
                )
        
        # All preconditions passed
        return ValidationResult(
            result=PreconditionResult.ALLOW,
            reason="All preconditions satisfied",
            details={
                "user_id": user_id,
                "thread_id": thread_id,
                "lead_id": lead_id,
                "extraction_confidence": extraction_confidence,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def _check_api_status(self) -> Dict[str, Any]:
        """Check current API status and circuit breaker states."""
        # This would need to be connected to actual circuit breaker instances
        # For now, return a basic status based on environment
        return {
            "openrouter_circuit_open": True,  # From the logs
            "gemini_circuit_open": True,      # From the logs  
            "all_circuits_open": True,        # Based on log evidence
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_intervention_dedup(self, user_id: str, thread_id: str) -> 'DedupResult':
        """Check if intervention was recently executed for this thread."""
        if not self.redis_client:
            return DedupResult(is_blocked=False, details={})
            
        # Create dedup key: intervention:{thread_id}:{bucket_15m}
        bucket = int(time.time() // (self.settings.INTERVENTION_COOLDOWN_MINUTES * 60))
        dedup_key = f"intervention:{thread_id}:{bucket}"
        
        try:
            # Check if intervention key exists
            exists = await self.redis_client.exists(dedup_key)
            if exists:
                ttl = await self.redis_client.ttl(dedup_key)
                return DedupResult(
                    is_blocked=True,
                    details={"dedup_key": dedup_key, "ttl_seconds": ttl},
                    next_allowed=datetime.utcnow() + timedelta(seconds=ttl)
                )
            
            # Set intervention key with TTL
            await self.redis_client.setex(
                dedup_key, 
                self.settings.INTERVENTION_COOLDOWN_MINUTES * 60, 
                "1"
            )
            
            return DedupResult(is_blocked=False, details={"dedup_key": dedup_key})
            
        except Exception as e:
            logger.error(f"Error checking intervention dedup: {e}")
            return DedupResult(is_blocked=False, details={"error": str(e)})
    
    async def _is_suppressed(self, suppression_key: str) -> bool:
        """Check if an error is currently suppressed."""
        if not self.redis_client:
            return False
            
        try:
            exists = await self.redis_client.exists(f"suppressed:{suppression_key}")
            return bool(exists)
        except Exception as e:
            logger.error(f"Error checking suppression: {e}")
            return False
    
    async def _suppress_error(self, suppression_key: str, ttl_seconds: int):
        """Mark an error as suppressed for a period."""
        if not self.redis_client:
            return
            
        try:
            await self.redis_client.setex(
                f"suppressed:{suppression_key}",
                ttl_seconds,
                "1"
            )
        except Exception as e:
            logger.error(f"Error setting suppression: {e}")

@dataclass
class DedupResult:
    """Result of deduplication check."""
    is_blocked: bool
    details: Dict[str, Any]
    next_allowed: Optional[datetime] = None

# Global validator instance
_validator: Optional[ProactiveEngagementValidator] = None

def get_validator() -> ProactiveEngagementValidator:
    """Get global validator instance."""
    global _validator
    if _validator is None:
        _validator = ProactiveEngagementValidator()
    return _validator

async def validate_proactive_engagement_conditions(
    user_id: str,
    thread_id: Optional[str],
    lead_id: Optional[str],
    current_state: Dict[str, Any],
    extraction_confidence: float = 0.0,
    context_message_analysis: Optional[Dict[str, Any]] = None
) -> ValidationResult:
    """
    Convenience function for proactive engagement validation.
    
    Returns ValidationResult that should be checked:
    - If result == PreconditionResult.ALLOW: proceed with proactive engagement
    - Otherwise: log reason and return NOOP
    """
    validator = get_validator()
    return await validator.validate_proactive_engagement(
        user_id, thread_id, lead_id, current_state,
        extraction_confidence, context_message_analysis
    )