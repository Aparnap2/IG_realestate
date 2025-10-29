"""
Universal Lead Processing Pipeline - Multi-Industry Architecture

This module integrates all Phase 1-3 components into a unified, industry-adaptive
lead processing pipeline that can handle any business type while maintaining specialized
logic needed for high conversion rates.

Key Components:
- Universal Lead Processor: Main orchestration system
- Industry Detection: Auto-detect business type from conversation
- Dynamic Workflow Routing: AI-powered workflow selection
- Multi-Factor Assessment: Comprehensive lead readiness evaluation
- LangGraph Integration: Dynamic workflow orchestration
"""

from .universal_lead_processor import (
    UniversalLeadProcessor,
    universal_lead_processor,
    process_message,
    WorkflowType,
    IndustryType,
    LeadReadinessAssessment,
    ProcessingContext
)

__all__ = [
    "UniversalLeadProcessor",
    "universal_lead_processor", 
    "process_message",
    "WorkflowType",
    "IndustryType",
    "LeadReadinessAssessment",
    "ProcessingContext"
]

__version__ = "1.0.0"
__author__ = "Universal Lead Processing Pipeline"