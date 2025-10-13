import pytest
from unittest.mock import AsyncMock, patch

from backend.tasks.production_lead_processing import ProductionLeadProcessor


@pytest.mark.asyncio
async def test_apply_compliance_guardrails_replaces_message(monkeypatch):
    fake_graph = AsyncMock()
    monkeypatch.setattr(
        'backend.tasks.production_lead_processing.get_graphiti_client',
        lambda: fake_graph
    )

    processor = ProductionLeadProcessor()

    async def fake_evaluator(*_args, **_kwargs):
        return {
            "passed": False,
            "violations": [{"explanation": "Age restriction"}],
            "suggested_replacement": "We welcome applicants from all backgrounds.",
            "evaluator_version": "1.0"
        }

    with patch('backend.tasks.production_lead_processing.fair_housing_evaluator', new=fake_evaluator):
        safe_message, metadata = await processor._apply_compliance_guardrails(
            lead_identifier="lead123",
            user_id="user123",
            message="Perfect for young professionals",
            lead_snapshot={"budget": 300000, "location": "Miami", "channel": "ig"}
        )

    assert safe_message == "We welcome applicants from all backgrounds."
    assert metadata["passed"] is False
    assert metadata["violations"]
