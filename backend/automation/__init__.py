"""
Automation module for progressive nurture sequences using LangGraph.

This module implements industry-specific automated follow-up sequences
with dynamic scheduling, multi-channel communication, and intelligent template-based messaging.
"""

from .nurture_sequences import (
    NurtureSequenceManager,
    schedule_nurture_sequence,
    get_next_touch_point,
    cancel_nurture_sequence,
    update_sequence_progress,
    IndustryType,
    ChannelType,
    LANGGRAPH_AVAILABLE
)

from .nurture_config import (
    NurtureConfigLoader,
    SequenceConfig,
    TemplateConfig,
    TouchPointConfig,
    nurture_config_loader
)

__all__ = [
    "NurtureSequenceManager",
    "schedule_nurture_sequence",
    "get_next_touch_point", 
    "cancel_nurture_sequence",
    "update_sequence_progress",
    "IndustryType",
    "ChannelType",
    "LANGGRAPH_AVAILABLE",
    "NurtureConfigLoader",
    "SequenceConfig",
    "TemplateConfig",
    "TouchPointConfig",
    "nurture_config_loader"
]