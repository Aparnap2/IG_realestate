"""
Main workflow module for the AAA Real Estate Lead Capture Agentic AI System.

This module provides the entry point for creating the LangGraph workflow
according to PRD specifications.
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.prd_compliant_workflow import create_prd_compliant_workflow
from utils.redis_client import test_redis_connection

def create_workflow():
    """
    Create the main LangGraph workflow for lead processing.
    
    This function creates a PRD-compliant workflow with:
    - Three ReAct agents (Qualifier, Scheduler, FollowUp)
    - Redis checkpointer for state persistence
    - HITL interrupts for high-value leads
    - Proper handoff mechanisms
    - Database query tools with caching
    
    Returns:
        Compiled LangGraph workflow
    """
    # Test Redis connection first
    if not test_redis_connection():
        raise RuntimeError("Redis connection failed. Please ensure Redis is running.")
    
    # Create and return the PRD-compliant workflow
    return create_prd_compliant_workflow()

# For backward compatibility
def get_workflow():
    """Get the workflow instance (alias for create_workflow)"""
    return create_workflow()
