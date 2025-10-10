import pytest
from unittest.mock import patch, MagicMock
import sys
import os


from backend.models.lead import Lead
from backend.agents.qualifier import qualifier_node
from backend.schemas.state import AgentState

@pytest.fixture
def sample_lead():
    return Lead(
        id="test_lead_123",
        channel="ig",
        user_id="user_456",
        message="2BHK in Miami, $300k",
        budget=300000,
        location="Miami",
        property_type="2BHK"
    )

@pytest.fixture
def sample_state(sample_lead):
    return AgentState(
        lead=sample_lead,
        messages=[{"role": "user", "content": sample_lead.message}],
        human_feedback=None,
        next_agent="qualifier"
    )

@patch('agents.qualifier.get_config', side_effect=lambda key, default: default)
@patch('agents.qualifier.query_properties_db')
@patch('agents.qualifier.get_llm_response')
@patch('agents.qualifier.cache_query_result')
def test_qualifier_node(mock_cache, mock_llm, mock_db, mock_get_config, sample_state):
    # Mock the database response
    mock_db.return_value = [
        {
            "id": "prop_1",
            "price": 250000,
            "location": "Miami",
            "property_type": "2BHK"
        }
    ]
    
    # Mock the LLM response
    mock_llm.return_value = "0.8"
    
    # Call the qualifier node
    result = qualifier_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "scheduler"
    assert result["lead"].qualified_score == 0.8
    
    # Verify mocks were called
    mock_db.assert_called_once()
    mock_llm.assert_called_once()
    mock_cache.assert_called_once()

@patch('agents.qualifier.get_config')
@patch('agents.qualifier.query_properties_db')
@patch('agents.qualifier.get_llm_response')
@patch('agents.qualifier.cache_query_result')
def test_qualifier_node_with_dynamic_threshold(mock_cache, mock_llm, mock_db, mock_get_config, sample_state):
    # Mock the database response
    mock_db.return_value = [
        {
            "id": "prop_1",
            "price": 250000,
            "location": "Miami",
            "property_type": "2BHK"
        }
    ]
    
    # Mock the LLM response
    mock_llm.return_value = "0.8"
    
    # Mock get_config to return a dynamic threshold
    mock_get_config.side_effect = lambda key, default: "0.9" if key == "scheduler_threshold" else default
    
    # Call the qualifier node
    result = qualifier_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "followup"
    assert result["lead"].qualified_score == 0.8
