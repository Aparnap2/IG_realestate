import pytest
from datetime import datetime

from backend.agents.prd_compliant_workflow import SchedulerAgent


def test_normalize_slots_accepts_dict_and_datetime():
    agent = SchedulerAgent()
    raw_slots = [
        {
            "start": datetime(2024, 1, 1, 10, 0),
            "end": datetime(2024, 1, 1, 11, 0)
        },
        datetime(2024, 1, 2, 15, 0)
    ]

    normalized = agent._normalize_slots(raw_slots)

    assert len(normalized) == 2
    assert all("start" in slot for slot in normalized)
    assert isinstance(normalized[0]["start"], datetime)


def test_normalize_slots_filters_invalid_entries():
    agent = SchedulerAgent()
    raw_slots = [
        {"start": "not-a-date"},
        {"start": "2024-01-01T12:00:00"}
    ]

    normalized = agent._normalize_slots(raw_slots)

    assert len(normalized) == 1
    assert normalized[0]["start"].isoformat().startswith("2024-01-01T12:00:00")
