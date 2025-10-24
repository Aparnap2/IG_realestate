"""
Qualifier utilities for lead qualification scoring.
Minimal implementation to restore working functionality.
"""

from typing import Dict, Any

def reconcile_budget_mismatch(extracted_budget: int, properties: list, context: dict) -> Dict[str, Any]:
    """Reconcile budget mismatch between extracted info and available properties"""
    return {
        "adjusted_budget": extracted_budget,
        "qualified": extracted_budget > 0,
        "adjustment_reason": "not adjusted" if extracted_budget > 0 else "no budget specified"
    }

def calculate_temporal_qualification_adjustments(conversation_history: list) -> Dict[str, Any]:
    """Calculate qualification adjustments based on conversation history"""
    adjustments = {
        "score_adjustment": 0.0,
        "reasoning": "No history available"
    }
    
    if conversation_history:
        message_count = len(conversation_history)
        if message_count >= 3:
            adjustments["score_adjustment"] = 0.1
            adjustments["reasoning"] = "Engaged user with multiple messages"
        elif message_count >= 2:
            adjustments["score_adjustment"] = 0.05
            adjustments["reasoning"] = "User responded to follow-up"
    
    return adjustments
