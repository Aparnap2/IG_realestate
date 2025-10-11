"""
Compliance Tools - Fair Housing, GDPR, TCPA Evaluators

Implements PRD Section 2.6: Compliance-by-Design with policy gates and audit trails.

Key Features:
- Fair Housing Act violation detection with pattern matching + LLM
- GDPR/CCPA data minimization and consent tracking
- TCPA opt-in verification for SMS communications
- Immutable audit logging of all compliance decisions
- Suggested neutral alternatives for blocked content
"""

import sys
import os
import re
from typing import Dict, Any, List
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.audit import audit_log_event
from config import get_settings

settings = get_settings()

class FairHousingViolation(BaseModel):
    """Structured representation of Fair Housing Act violation"""
    pattern: str = Field(description="Regex pattern that matched")
    matched_text: str = Field(description="Actual text that violated policy")
    regulation: str = Field(description="Specific Fair Housing Act section")
    risk_level: str = Field(description="low, medium, high, critical")
    explanation: str = Field(description="Why this violates fair housing")

class ComplianceResult(BaseModel):
    """Structured compliance evaluation result"""
    passed: bool = Field(description="Whether content passes all compliance checks")
    violations: List[FairHousingViolation] = Field(default_factory=list)
    suggested_replacement: str = Field(description="Neutral alternative message")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in evaluation")
    evaluator_version: str = Field(default="1.0")

# Fair Housing Act Protected Classes and Prohibited Patterns
FAIR_HOUSING_PATTERNS = {
    # Familial Status (families with children)
    "familial_status": [
        r"\b(no\s+)?(kids?|children|families\s+with\s+children)\b",
        r"\b(adult[s]?\s+only|adults?\s+preferred)\b",
        r"\b(quiet\s+building|no\s+noise)\b",  # Often code for no children
        r"\b(mature\s+tenants?|responsible\s+adults?)\b"
    ],
    
    # Religion
    "religion": [
        r"\b(church|synagogue|mosque|temple|cathedral)\s+(nearby|close|walking\s+distance)\b",
        r"\b(christian|jewish|muslim|hindu|buddhist)\s+(community|neighborhood)\b",
        r"\b(kosher|halal)\s+(nearby|available)\b"
    ],
    
    # Race/National Origin (indirect proxies)
    "race_proxies": [
        r"\b(safe|dangerous|rough|sketchy)\s+(neighborhood|area|district)\b",
        r"\b(good|bad)\s+(schools?|area|neighborhood)\b",
        r"\b(urban|inner\s+city|suburban)\s+(feel|vibe|atmosphere)\b",
        r"\b(diverse|homogeneous)\s+(community|neighborhood)\b"
    ],
    
    # Age
    "age": [
        r"\b(perfect\s+for\s+)?(young|elderly|senior|retired)\s+(people|professionals?|couples?)\b",
        r"\b(starter\s+home|retirement\s+community)\b",
        r"\b(age\s+)?(restricted|limited|55\+|over\s+55)\b"
    ],
    
    # Disability (indirect references)
    "disability": [
        r"\b(no\s+)?(wheelchair|handicap|disabled)\s+(access|accessible)\b",
        r"\b(able\s+bodied|physically\s+fit)\s+(tenants?|residents?)\b",
        r"\b(stairs\s+only|no\s+elevator)\b"  # When used to exclude
    ],
    
    # Gender/Sex
    "gender": [
        r"\b(female|male|women|men)\s+(only|preferred|roommate)\b",
        r"\b(no\s+)?(couples?|married)\s+(allowed|preferred)\b"
    ]
}

# Neutral replacement templates
NEUTRAL_REPLACEMENTS = {
    "familial_status": "This property offers comfortable living spaces suitable for various household sizes.",
    "religion": "The property is conveniently located near various community amenities and services.",
    "race_proxies": "This property is located in a well-established neighborhood with local amenities.",
    "age": "This property offers features that many residents find appealing.",
    "disability": "The property includes standard accessibility features as required by law.",
    "gender": "This property welcomes qualified applicants who meet our standard criteria."
}

async def fair_housing_evaluator(message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Comprehensive Fair Housing Act compliance evaluator.
    
    Uses both pattern matching and LLM evaluation for comprehensive coverage.
    
    Args:
        message: Outbound message content to evaluate
        context: Additional context (lead info, property details)
        
    Returns:
        Dictionary with compliance result and suggested alternatives
    """
    if context is None:
        context = {}
    
    try:
        # Phase 1: Pattern-based detection (fast, deterministic)
        pattern_violations = _detect_pattern_violations(message)
        
        # Phase 2: LLM-based evaluation (contextual, nuanced)
        llm_evaluation = await _llm_fair_housing_check(message, context)
        
        # Combine results
        all_violations = pattern_violations + llm_evaluation.violations
        
        # Generate result
        result = ComplianceResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
            suggested_replacement=_generate_neutral_replacement(message, all_violations),
            confidence=llm_evaluation.confidence if llm_evaluation else 0.8,
            evaluator_version="1.0"
        )
        
        # Log compliance check
        audit_log_event("fair_housing_check", {
            "message_hash": hash(message),
            "violations_count": len(all_violations),
            "passed": result.passed,
            "evaluator_version": result.evaluator_version,
            "context": context
        })
        
        return result.model_dump()
        
    except Exception as e:
        # Fail-safe: Block on evaluation error
        audit_log_event("compliance_evaluation_error", {
            "error": str(e),
            "message_hash": hash(message),
            "action": "blocked_for_safety"
        })
        
        return {
            "passed": False,
            "violations": [{
                "pattern": "evaluation_error",
                "matched_text": "System error",
                "regulation": "Safety fallback",
                "risk_level": "high",
                "explanation": f"Compliance evaluation failed: {str(e)}"
            }],
            "suggested_replacement": "Thank you for your interest. A team member will contact you shortly with property information.",
            "confidence": 0.0,
            "evaluator_version": "1.0"
        }

def _detect_pattern_violations(message: str) -> List[FairHousingViolation]:
    """
    Detect Fair Housing violations using regex patterns.
    
    Fast, deterministic detection of common violation patterns.
    """
    violations = []
    message_lower = message.lower()
    
    for category, patterns in FAIR_HOUSING_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, message_lower, re.IGNORECASE)
            for match in matches:
                violations.append(FairHousingViolation(
                    pattern=pattern,
                    matched_text=match.group(),
                    regulation=f"Fair Housing Act - {category.replace('_', ' ').title()}",
                    risk_level=_assess_risk_level(category, match.group()),
                    explanation=_get_violation_explanation(category)
                ))
    
    return violations

async def _llm_fair_housing_check(message: str, context: Dict[str, Any]) -> ComplianceResult:
    """
    LLM-based Fair Housing compliance check for nuanced evaluation.
    
    Catches subtle violations that pattern matching might miss.
    """
    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.0,  # Deterministic for compliance
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        ).with_structured_output(ComplianceResult)
        
        system_prompt = """You are a Fair Housing Act compliance expert. Analyze the message for potential violations.

PROTECTED CLASSES (cannot discriminate based on):
- Race, Color, National Origin
- Religion  
- Sex/Gender
- Familial Status (families with children)
- Disability
- Age (in some jurisdictions)

VIOLATION EXAMPLES:
- "Perfect for young professionals" (age discrimination)
- "Quiet building" (often code for no children)
- "Safe neighborhood" (can be race proxy)
- "Near good schools" (can be familial status proxy)
- "Church nearby" (religion)

CONTEXT MATTERS:
- Describing factual amenities is OK ("school district boundaries")
- Expressing preferences is NOT OK ("prefer mature tenants")
- Neutral language is safe ("suitable for various lifestyles")

Analyze this message for Fair Housing violations. Be strict but fair."""

        user_prompt = f"""
Message to analyze: "{message}"

Context: {context}

Identify any Fair Housing Act violations, even subtle ones. Consider both explicit discrimination and coded language that could exclude protected classes.
"""

        result = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        return result
        
    except Exception as e:
        # Fallback on LLM error
        return ComplianceResult(
            passed=True,  # Don't block on LLM error, rely on pattern matching
            violations=[],
            suggested_replacement=message,
            confidence=0.5,
            evaluator_version="1.0"
        )

def _assess_risk_level(category: str, matched_text: str) -> str:
    """Assess risk level of Fair Housing violation."""
    high_risk_categories = ["familial_status", "race_proxies", "religion"]
    explicit_terms = ["no kids", "adults only", "christian community", "safe neighborhood"]
    
    if category in high_risk_categories:
        return "high"
    
    if any(term in matched_text.lower() for term in explicit_terms):
        return "critical"
    
    return "medium"

def _get_violation_explanation(category: str) -> str:
    """Get explanation for why this category violates Fair Housing."""
    explanations = {
        "familial_status": "Cannot discriminate against families with children under 18",
        "religion": "Cannot discriminate based on religious beliefs or practices",
        "race_proxies": "Terms like 'safe' or 'good schools' can be proxies for racial discrimination",
        "age": "Cannot discriminate based on age (except in senior housing)",
        "disability": "Cannot discriminate against people with disabilities",
        "gender": "Cannot discriminate based on sex or gender identity"
    }
    return explanations.get(category, "Potential Fair Housing Act violation")

def _generate_neutral_replacement(message: str, violations: List[FairHousingViolation]) -> str:
    """
    Generate neutral alternative message that removes violations.
    
    Preserves the intent while removing discriminatory language.
    """
    if not violations:
        return message
    
    # Start with original message
    neutral_message = message
    
    # Replace each violation with neutral alternative
    for violation in violations:
        category = violation.regulation.split(" - ")[-1].lower().replace(" ", "_")
        neutral_replacement = NEUTRAL_REPLACEMENTS.get(category, "")
        
        if neutral_replacement:
            # Simple replacement strategy - can be enhanced with more sophisticated NLP
            neutral_message = re.sub(
                violation.pattern, 
                neutral_replacement, 
                neutral_message, 
                flags=re.IGNORECASE
            )
    
    # Fallback: Generic neutral message if replacements don't work well
    if len(violations) > 2 or len(neutral_message) < 20:
        return "Thank you for your interest! I'd be happy to share information about properties that match your criteria. What specific features are most important to you?"
    
    return neutral_message.strip()

def gdpr_tcpa_tracker(lead_id: str, event: str, metadata: Dict[str, Any]) -> None:
    """
    Track GDPR/CCPA/TCPA consent events for compliance.
    
    Args:
        lead_id: Unique identifier for the lead
        event: Type of consent event (message_received, opt_in, opt_out, data_request)
        metadata: Additional event metadata
    """
    try:
        consent_event = {
            "lead_id": lead_id,
            "event_type": event,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "compliance_framework": ["GDPR", "CCPA", "TCPA"]
        }
        
        # Log to immutable audit trail
        audit_log_event("consent_tracking", consent_event)
        
        # Update lead consent status in database if needed
        if event in ["opt_in", "opt_out"]:
            _update_lead_consent_status(lead_id, event, metadata)
            
    except Exception as e:
        audit_log_event("consent_tracking_error", {
            "lead_id": lead_id,
            "event": event,
            "error": str(e)
        })

def _update_lead_consent_status(lead_id: str, event: str, metadata: Dict[str, Any]) -> None:
    """Update lead consent status in database."""
    try:
        from utils.supabase_client import supabase
        
        consent_data = {
            "tcpa_opt_in": event == "opt_in",
            "consent_timestamp": datetime.now().isoformat(),
            "consent_method": metadata.get("method", "instagram_dm"),
            "consent_ip": metadata.get("ip_address", "unknown")
        }
        
        supabase.table("leads").update(consent_data).eq("user_id", lead_id).execute()
        
    except Exception as e:
        audit_log_event("consent_update_error", {
            "lead_id": lead_id,
            "error": str(e)
        })

def validate_tcpa_compliance(lead_id: str, message_type: str = "sms") -> bool:
    """
    Validate TCPA compliance before sending SMS/calls.
    
    Args:
        lead_id: Lead identifier
        message_type: Type of communication (sms, call, email)
        
    Returns:
        True if communication is TCPA compliant
    """
    try:
        from utils.supabase_client import supabase
        
        # Check opt-in status
        response = supabase.table("leads").select("tcpa_opt_in, consent_timestamp").eq("user_id", lead_id).execute()
        
        if not response.data:
            return False
        
        lead_data = response.data[0]
        
        # TCPA requires explicit opt-in for SMS/calls
        if message_type in ["sms", "call"] and not lead_data.get("tcpa_opt_in"):
            return False
        
        # Check if consent is recent (within 18 months for TCPA)
        consent_timestamp = lead_data.get("consent_timestamp")
        if consent_timestamp:
            from datetime import datetime, timedelta
            consent_date = datetime.fromisoformat(consent_timestamp.replace('Z', '+00:00'))
            if datetime.now() - consent_date > timedelta(days=547):  # 18 months
                return False
        
        return True
        
    except Exception as e:
        audit_log_event("tcpa_validation_error", {
            "lead_id": lead_id,
            "error": str(e)
        })
        return False  # Fail-safe: deny if validation fails

def gdpr_data_minimization_check(data_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check data collection against GDPR data minimization principle.
    
    Args:
        data_fields: Dictionary of data fields being collected
        
    Returns:
        Dictionary with allowed fields and warnings
    """
    # Define necessary fields for real estate lead processing
    necessary_fields = {
        "budget", "location", "property_type", "timeline", 
        "email", "phone", "name", "user_id"
    }
    
    # Define sensitive fields requiring explicit consent
    sensitive_fields = {
        "race", "religion", "political_views", "health_data",
        "financial_details", "family_composition"
    }
    
    allowed_fields = {}
    warnings = []
    
    for field, value in data_fields.items():
        if field in necessary_fields:
            allowed_fields[field] = value
        elif field in sensitive_fields:
            warnings.append(f"Sensitive field '{field}' requires explicit consent")
        else:
            warnings.append(f"Field '{field}' may not be necessary for service provision")
    
    audit_log_event("gdpr_data_minimization", {
        "requested_fields": list(data_fields.keys()),
        "allowed_fields": list(allowed_fields.keys()),
        "warnings": warnings
    })
    
    return {
        "allowed_fields": allowed_fields,
        "warnings": warnings,
        "compliant": len(warnings) == 0
    }