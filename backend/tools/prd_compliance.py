import re
import hashlib
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import supabase

class FairHousingViolation(BaseModel):
    """Individual fair housing violation"""
    pattern: str
    violation_type: str
    text: str
    position: int
    severity: str  # "high" | "medium" | "low"

class FairHousingEvaluation(BaseModel):
    """Result of fair housing compliance check"""
    passed: bool
    violations: List[FairHousingViolation]
    suggested_replacement: Optional[str] = None
    risk_score: float = 0.0  # 0-1, higher = more risky
    confidence: float = 1.0
    disclaimer_added: bool = False
    
    def audit_log_data(self) -> Dict[str, Any]:
        """Prepare data for audit logging"""
        return {
            "violations_count": len(self.violations),
            "violation_types": list(set(v.violation_type for v in self.violations)),
            "risk_score": self.risk_score,
            "high_severity_violations": len([v for v in self.violations if v.severity == "high"]),
            "passed": self.passed
        }

class PRDComplianceEvaluator:
    """PRD-compliant Fair Housing Act evaluator with enhanced detection"""
    
    # Enhanced prohibited patterns with severity levels
    PROHIBITED_PATTERNS = [
        # High severity (direct violations)
        (r'no (kids|children|families?)', 'familial_status', 'high'),
        (r'(adults? only|adult community)', 'age', 'high'),
        (r'(white|black|hispanic|asian|indian|african|latino) (neighborhood|area)', 'race', 'high'),
        (r'(church|synagogue|mosque|temple) nearby', 'religion', 'high'),
        
        # Medium severity (indirect proxies)
        (r'safe (neighborhood|area|community)', 'race_proxy', 'medium'),
        (r'dangerous (neighborhood|area|community)', 'race_proxy', 'medium'),
        (r'perfect for (young|elderly|senior)s?', 'age', 'medium'),
        (r'(quiet|peaceful|family) neighborhood', 'familial_status_proxy', 'medium'),
        
        # Low severity (potential issues)
        (r'(good|great) schools?', 'familial_status_proxy', 'low'),
        (r'(walk|bike) to (church|synagogue|mosque|temple)', 'religion_proxy', 'low'),
        (r'near (church|synagogue|mosque|temple)', 'religion_proxy', 'low'),
        (r'family (room|rooms?)', 'familial_status', 'low'),
    ]
    
    # Required disclaimer for all communications
    REQUIRED_DISCLAIMER = "Equal Housing Opportunity. All properties shown without regard to race, color, religion, sex, handicap, familial status, or national origin."
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), violation_type, severity)
            for pattern, violation_type, severity in self.PROHIBITED_PATTERNS
        ]
    
    def evaluate_message(self, message: str, lead_context: Optional[Dict] = None) -> FairHousingEvaluation:
        """Comprehensive fair housing evaluation
        
        Args:
            message: Message to evaluate
            lead_context: Optional lead information for context-aware evaluation
            
        Returns:
            FairHousingEvaluation with detailed violations and suggestions
        """
        violations = []
        modified_message = message
        risk_score = 0.0
        
        # Check all prohibited patterns
        for pattern, violation_type, severity in self.compiled_patterns:
            for match in pattern.finditer(message):
                violation = FairHousingViolation(
                    pattern=pattern.pattern,
                    violation_type=violation_type,
                    text=match.group(),
                    position=match.start(),
                    severity=severity
                )
                violations.append(violation)
                
                # Calculate risk contribution
                severity_weights = {'high': 0.4, 'medium': 0.2, 'low': 0.1}
                risk_score += severity_weights.get(severity, 0.1)
        
        # Cap risk score at 1.0
        risk_score = min(risk_score, 1.0)
        
        # Generate suggested replacement if violations found
        suggested_replacement = None
        if violations:
            suggested_replacement = self._generate_compliant_alternative(message, violations)
        
        # Determine if evaluation passed
        if self.strict_mode:
            passed = len(violations) == 0
        else:
            # In non-strict mode, allow low-severity violations
            passed = len([v for v in violations if v.severity in ['high', 'medium']]) == 0
        
        # Check if disclaimer is needed
        disclaimer_added = False
        if not any(disclaimer in message.lower() for disclaimer in ['equal housing', 'fair housing']):
            if suggested_replacement and not suggested_replacement.endswith(self.REQUIRED_DISCLAIMER):
                suggested_replacement += f"\n\n{self.REQUIRED_DISCLAIMER}"
                disclaimer_added = True
        
        return FairHousingEvaluation(
            passed=passed,
            violations=violations,
            suggested_replacement=suggested_replacement,
            risk_score=risk_score,
            disclaimer_added=disclaimer_added,
            confidence=0.9 if passed else 0.8
        )
    
    def _generate_compliant_alternative(self, message: str, violations: List[FairHousingViolation]) -> str:
        """Generate a compliant alternative message"""
        alternative = message
        
        # Apply pattern-specific replacements
        replacements = {
            r'safe (neighborhood|area|community)': 'well-maintained area',
            r'dangerous (neighborhood|area|community)': 'up-and-coming area',
            r'perfect for (young|elderly|senior)s?': 'suitable for',
            r'(white|black|hispanic|asian|indian|african|latino) (neighborhood|area)': r'\2',
            r'(church|synagogue|mosque|temple) nearby': 'places of worship nearby',
            r'no (kids|children|families?)': '',
            r'adults? only': '',
            r'(quiet|peaceful|family) neighborhood': 'residential neighborhood',
        }
        
        for pattern, replacement in replacements.items():
            alternative = re.sub(pattern, replacement, alternative, flags=re.IGNORECASE)
        
        # Clean up extra spaces and improve readability
        alternative = re.sub(r'\s+', ' ', alternative).strip()
        
        # Add disclaimer if not present
        if not any(disclaimer in alternative.lower() for disclaimer in ['equal housing', 'fair housing']):
            alternative += f"\n\n{self.REQUIRED_DISCLAIMER}"
        
        return alternative
    
    async def log_evaluation(self, evaluation: FairHousingEvaluation, lead_id: str, original_message: str, agent_type: str) -> bool:
        """Log compliance evaluation to audit trail
        
        Args:
            evaluation: Fair housing evaluation result
            lead_id: Lead identifier
            original_message: Original message that was evaluated
            agent_type: Type of agent sending the message
            
        Returns:
            True if logging successful
        """
        try:
            # Create audit log entry
            audit_data = {
                "event_type": "compliance_check",
                "entity_type": "lead",
                "entity_id": lead_id,
                "agent_type": agent_type,
                "agent_action": "message_evaluation",
                "state_before": {"message": original_message},
                "state_after": evaluation.audit_log_data(),
                "policy_checks": {
                    "fair_housing": {
                        "violations": [v.model_dump() for v in evaluation.violations],
                        "risk_score": evaluation.risk_score,
                        "passed": evaluation.passed
                    }
                },
                "compliance_flags": ["fair_housing_evaluated"],
                "hash_signature": hashlib.sha256(
                    f"{lead_id}{original_message}{datetime.now().isoformat()}".encode()
                ).hexdigest(),
                "event_data": {
                    "original_message": original_message,
                    "suggested_replacement": evaluation.suggested_replacement,
                    "disclaimer_added": evaluation.disclaimer_added
                }
            }
            
            # Insert into audit_logs table
            result = supabase.table("audit_logs").insert(audit_data).execute()
            
            if result.data:
                print(f"✅ Compliance evaluation logged for lead {lead_id}")
                return True
            else:
                print(f"❌ Failed to log compliance evaluation for lead {lead_id}")
                return False
                
        except Exception as e:
            print(f"⚠️ Error logging compliance evaluation: {e}")
            return False


TCPA_PATTERNS = [
    r'\b\d{10}\b',  # 10-digit phone numbers
    r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Formatted phone numbers
    r'(text|call|message|phone|mobile)',  # Communication method keywords
]

def check_tcpa_compliance(message: str, has_consent: bool = False) -> Dict[str, Any]:
    """Check TCPA compliance for SMS communications
    
    Args:
        message: Message to evaluate
        has_consent: Whether TCPA consent has been obtained
        
    Returns:
        TCPA compliance evaluation
    """
    contains_phone = any(re.search(pattern, message, re.IGNORECASE) for pattern in TCPA_PATTERNS)
    
    # TCPA requires explicit consent for marketing messages
    tcpa_compliant = not contains_phone or has_consent
    
    return {
        "compliant": tcpa_compliant,
        "contains_phone_number": contains_phone,
        "has_consent": has_consent,
        "disclaimer_needed": contains_phone and not has_consent,
        "disclaimer_text": "Msg & data rates may apply. Reply STOP to unsubscribe." if contains_phone else None
    }


# Global evaluator instance (PRD-compliant)
prd_compliance_evaluator = PRDComplianceEvaluator(strict_mode=True)


async def fair_housing_evaluator(message: str, lead_context: Dict) -> Dict[str, Any]:
    """PRD-compliant fair housing evaluation with logging
    
    Args:
        message: Message to evaluate
        lead_context: Lead context containing lead_id and agent information
        
    Returns:
        Compliance evaluation result
    """
    lead_id = lead_context.get("lead_id", "unknown")
    agent_type = lead_context.get("agent_type", "unknown")
    
    # Evaluate message
    evaluation = prd_compliance_evaluator.evaluate_message(message, lead_context)
    
    # Log evaluation to audit trail
    await prd_compliance_evaluator.log_evaluation(
        evaluation=evaluation,
        lead_id=lead_id,
        original_message=message,
        agent_type=agent_type
    )
    
    return {
        "passed": evaluation.passed,
        "violations": [v.model_dump() for v in evaluation.violations],
        "suggested_replacement": evaluation.suggested_replacement,
        "risk_score": evaluation.risk_score,
        "disclaimer_added": evaluation.disclaimer_added,
        "confidence": evaluation.confidence
    }


def fair_housing_check(message: str) -> Dict[str, Any]:
    """Legacy fair housing check for backward compatibility
    
    Args:
        message: Message to evaluate
        
    Returns:
        Simplified compliance result
    """
    evaluation = prd_compliance_evaluator.evaluate_message(message)
    
    return {
        "compliant": evaluation.passed,
        "violations": [f"{v.violation_type}: '{v.text}'" for v in evaluation.violations],
        "suggested_alternative": evaluation.suggested_replacement,
        "confidence": evaluation.confidence,
        "disclaimer_required": not any(disclaimer in message.lower() for disclaimer in ['equal housing', 'fair housing'])
    }
