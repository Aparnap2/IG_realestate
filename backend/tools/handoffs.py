from langgraph.types import Command
from langgraph.prebuilt import tool
from ..schemas.state import AgentState
from typing import Annotated

@tool
def handoff_to_scheduler(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="scheduler", update={"next_agent": "scheduler"})

@tool
def handoff_to_followup(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="followup", update={"next_agent": "followup"})

@tool
def handoff_to_end(state: Annotated[AgentState, "InjectedState"], tool_call_id: str) -> Command:
    return Command(goto="end", update={"next_agent": "end"})