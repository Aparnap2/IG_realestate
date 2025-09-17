from typing import Annotated, TypedDict
from pydantic import BaseModel
from datetime import datetime
from operator import add
from .lead import Lead

class AgentState(TypedDict):
    lead: Lead
    messages: Annotated[list[dict[str, str]], add]  # [{"role": "user", "content": "..."}, ...]
    human_feedback: str | None  # HITL input
    next_agent: str  # "qualifier", "scheduler", "followup"