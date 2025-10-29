from typing import Annotated, TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from operator import add
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.lead import Lead

class AgentState(TypedDict):
    """
    State definition for the LangGraph swarm according to PRD specifications.

    This state is shared across all agents in the swarm and persisted
    using Redis checkpointer with thread_id = user_id.
    """
    lead: Lead
    messages: Annotated[List[Dict[str, str]], add]  # [{"role": "user", "content": "..."}, ...]
    human_feedback: Optional[str]  # HITL input
    next_agent: str  # "qualifier", "scheduler", "followup"
    interrupt: Optional[bool]  # Whether to interrupt for HITL
    db_results: Optional[List[Dict[str, Any]]]  # Cached DB query results
    available_slots: Optional[List[datetime]]  # Available calendar slots
    error_message: Optional[str]  # Error handling
    retry_count: Optional[int]  # Retry counter for error handling

    # Self-Driving Booking Ops 2.0 fields
    booking_state: Optional[Dict[str, Any]]  # State machine context
    message_uuid: Optional[str]  # Message deduplication tracking
    booking_metrics: Optional[Dict[str, Any]]  # Latency/conflict tracking
