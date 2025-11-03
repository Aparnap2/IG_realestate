import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from langgraph.types import Command
from langgraph.prebuilt import tool_node
from backend.schemas.state import AgentState
from typing import Annotated

def handoff_to_scheduler(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="scheduler", update={"next_agent": "scheduler"})

def handoff_to_followup(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="followup", update={"next_agent": "followup"})

def handoff_to_end(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="end", update={"next_agent": "end"})