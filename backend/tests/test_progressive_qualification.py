import pytest
from unittest.mock import patch


def _make_lead(user_id: str, message: str):
    from backend.models.lead import Lead
    return Lead(user_id=user_id, message=message)


@patch('backend.tools.agent_tools.send_instagram_message')
@patch('backend.tools.agent_tools.qualify_lead_with_llm')
def test_progressive_questions_sets_state_and_message(mock_qualify, mock_send):
    from backend.agents.prd_compliant_workflow import QualifierAgent

    # Force a neutral score to avoid scheduler branch
    mock_qualify.invoke.return_value = {"score": 0.5, "reasoning": "test"}

    agent = QualifierAgent()
    state = {
        "lead": _make_lead("u1", "Hi"),
        "messages": []
    }

    result = agent.process(state)

    # Should ask for missing info deterministically and flag requires_more_info
    assert result.get("requires_more_info") is True
    out_msgs = [m[1]["message"] for m in mock_send.invoke.mock_calls]
    assert any("budget" in m.lower() or "location" in m.lower() or "property type" in m.lower() for m in out_msgs)


@patch('backend.tools.agent_tools.send_instagram_message')
@patch('backend.tools.agent_tools.qualify_lead_with_llm')
def test_high_intent_triggers_showcase_and_scheduler(mock_qualify, mock_send):
    from backend.agents.prd_compliant_workflow import QualifierAgent

    # High score to trigger scheduler path and showcase
    mock_qualify.invoke.return_value = {"score": 0.9, "reasoning": "high intent"}

    lead = _make_lead("u2", "Looking for a 3BR condo in Miami, budget 500000")
    lead.budget = 500000
    lead.location = "Miami"
    lead.property_type = "condo"
    lead.desired_bedrooms = 3

    agent = QualifierAgent()
    state = {
        "lead": lead,
        "messages": []
    }

    # Mock properties returned by query tool to enable showcase
    with patch('backend.tools.agent_tools.query_properties_tool') as mock_query:
        mock_query.invoke.return_value = [
            {"property_type": "condo", "location": "Miami", "price": 480000},
            {"property_type": "condo", "location": "Miami", "price": 510000},
            {"property_type": "condo", "location": "Miami", "price": 495000},
        ]
        result = agent.process(state)

    # Should route to scheduler for high intent
    assert result.get("next_agent") in ("scheduler",)
    # Ensure at least one showcase message was sent
    out_msgs = [call.kwargs.get("message", "") for call in mock_send.invoke.mock_calls]
    assert any("here are some examples" in m.lower() for m in out_msgs)
