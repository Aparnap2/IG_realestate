import pytest
from unittest.mock import patch, MagicMock
import sys
import os


from backend.models.lead import Lead
from backend.agents.qualifier import qualifier_node
from backend.agents.scheduler import scheduler_node
from backend.agents.followup import followup_node
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
        next_agent="qualifier",
        interrupt=False
    )

@patch('backend.agents.qualifier.get_config', side_effect=lambda key, default: default)
@patch('backend.agents.qualifier.query_properties_db')
@patch('backend.agents.qualifier.get_llm_response')
@patch('backend.agents.qualifier.cache_query_result')
@patch('backend.agents.qualifier.save_lead')
def test_qualifier_to_scheduler_flow(mock_save, mock_cache, mock_llm, mock_db, mock_get_config, sample_state):
    """Test the flow from qualifier to scheduler agent"""
    # Mock the database response
    mock_db.return_value = [
        {
            "id": "prop_1",
            "price": 250000,
            "location": "Miami",
            "property_type": "2BHK"
        }
    ]
    
    # Mock the LLM response with a high score to trigger scheduler
    mock_llm.return_value = '{"score": 0.8, "reasoning": "Good match"}'
    
    # Call the qualifier node
    result = qualifier_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "scheduler"
    assert result["lead"].qualified_score == 0.8
    assert not result.get("interrupt", False)  # Should not interrupt for score 0.8
    
    # Verify mocks were called
    mock_db.assert_called_once()
    mock_llm.assert_called_once()
    mock_cache.assert_called_once()

@patch('backend.agents.qualifier.query_properties_db')
@patch('backend.agents.qualifier.get_llm_response')
@patch('backend.agents.qualifier.cache_query_result')
@patch('backend.agents.qualifier.save_lead')
def test_qualifier_to_followup_flow(mock_save, mock_cache, mock_llm, mock_db, sample_state):
    """Test the flow from qualifier to followup agent"""
    # Mock the database response
    mock_db.return_value = []
    
    # Mock the LLM response with a low score to trigger followup
    mock_llm.return_value = '{"score": 0.3, "reasoning": "Poor match"}'
    
    # Call the qualifier node
    result = qualifier_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "followup"
    assert result["lead"].qualified_score == 0.3
    
    # Verify mocks were called
    mock_db.assert_called_once()
    mock_llm.assert_called_once()
    mock_cache.assert_called_once()

@patch('backend.agents.qualifier.query_properties_db')
@patch('backend.agents.qualifier.get_llm_response')
@patch('backend.agents.qualifier.cache_query_result')
@patch('backend.agents.qualifier.save_lead')
def test_qualifier_to_hitl_flow(mock_save, mock_cache, mock_llm, mock_db):
    """Test the flow from qualifier to HITL interrupt"""
    # Create a lead with high budget to trigger HITL
    lead = Lead(
        id="test_lead_123",
        channel="ig",
        user_id="user_456",
        message="Luxury property in Miami, $600k",
        budget=600000,  # High budget to trigger HITL
        location="Miami",
        property_type="Luxury"
    )
    
    state = AgentState(
        lead=lead,
        messages=[{"role": "user", "content": lead.message}],
        human_feedback=None,
        next_agent="qualifier",
        interrupt=False
    )
    
    # Mock the database response
    mock_db.return_value = [
        {
            "id": "prop_1",
            "price": 550000,
            "location": "Miami",
            "property_type": "Luxury"
        }
    ]
    
    # Mock the LLM response
    mock_llm.return_value = '{"score": 0.95, "reasoning": "High value lead"}'
    
    # Call the qualifier node
    result = qualifier_node(state)
    
    # Assertions
    assert result["next_agent"] == "scheduler"
    assert result["lead"].qualified_score == 0.95
    assert result.get("interrupt", False)  # Should interrupt for high value lead
    
    # Verify mocks were called
    mock_db.assert_called_once()
    mock_llm.assert_called_once()
    mock_cache.assert_called_once()

@patch('backend.agents.scheduler.get_available_slots_from_google_calendar')
@patch('backend.agents.scheduler.book_calendar_event')
@patch('backend.agents.scheduler.log_to_hubspot')
@patch('backend.agents.scheduler.save_lead')
def test_scheduler_flow(mock_save, mock_hubspot, mock_book, mock_slots, sample_state):
    """Test the scheduler agent flow"""
    # Modify state to simulate qualifier output
    sample_state["next_agent"] = "scheduler"
    sample_state["lead"].qualified_score = 0.8
    
    # Mock available slots
    from datetime import datetime, timedelta
    mock_slots.return_value = [datetime.now() + timedelta(days=1, hours=10)]
    
    # Mock booking response
    mock_book.return_value = "event_123"
    
    # Call the scheduler node
    result = scheduler_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "followup"
    assert result["lead"].meeting_slot is not None
    
    # Verify mocks were called
    mock_slots.assert_called_once()
    mock_book.assert_called_once()
    mock_hubspot.assert_called_once()
    mock_save.assert_called_once()

@patch('backend.agents.followup.save_lead')
def test_followup_flow(mock_save, sample_state):
    """Test the followup agent flow"""
    # Modify state to simulate qualifier output
    sample_state["next_agent"] = "followup"
    sample_state["lead"].qualified_score = 0.3
    
    # Call the followup node
    result = followup_node(sample_state)
    
    # Assertions
    assert result["next_agent"] == "end"
    assert len(result["lead"].history) > 0
    
    # Verify mocks were called
    mock_save.assert_called_once()

def test_lead_history_persistence(sample_lead):
    """Test that lead history is properly maintained across agents"""
    # Initial state
    state = AgentState(
        lead=sample_lead,
        messages=[{"role": "user", "content": sample_lead.message}],
        human_feedback=None,
        next_agent="qualifier",
        interrupt=False
    )
    
    initial_history_count = len(state["lead"].history)
    
    # Simulate qualifier processing
    with patch('backend.agents.qualifier.query_properties_db') as mock_db, \
         patch('backend.agents.qualifier.get_llm_response') as mock_llm, \
         patch('backend.agents.qualifier.cache_query_result') as mock_cache, \
         patch('backend.agents.qualifier.save_lead') as mock_save:
        
        mock_db.return_value = [
            {
                "id": "prop_1",
                "price": 250000,
                "location": "Miami",
                "property_type": "2BHK"
            }
        ]
        mock_llm.return_value = '{"score": 0.8, "reasoning": "Good match"}'
        
        result = qualifier_node(state)
        
        # Check that history was updated
        assert len(result["lead"].history) > initial_history_count
        assert any(entry["agent"] == "qualifier" for entry in result["lead"].history)
    
    # Simulate scheduler processing
    with patch('backend.agents.scheduler.get_available_slots_from_google_calendar') as mock_slots, \
         patch('backend.agents.scheduler.book_calendar_event') as mock_book, \
         patch('backend.agents.scheduler.log_to_hubspot') as mock_hubspot, \
         patch('backend.agents.scheduler.save_lead') as mock_save:
        
        from datetime import datetime, timedelta
        mock_slots.return_value = [datetime.now() + timedelta(days=1, hours=10)]
        mock_book.return_value = "event_123"
        
        scheduler_result = scheduler_node(result)
        
        # Check that history was updated
        assert len(scheduler_result["lead"].history) > len(result["lead"].history)
        assert any(entry["agent"] == "scheduler" for entry in scheduler_result["lead"].history)