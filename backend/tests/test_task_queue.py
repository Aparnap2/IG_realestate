import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.lead import Lead
from utils.task_queue import queue_lead_for_processing

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

@patch('utils.task_queue.process_lead_task')
def test_queue_lead_for_processing(mock_process, sample_lead):
    # Mock the Celery task
    mock_task = MagicMock()
    mock_task.id = "task_123"
    mock_process.delay.return_value = mock_task
    
    # Call the function
    task_id = queue_lead_for_processing(sample_lead)
    
    # Assertions
    assert task_id == "task_123"
    mock_process.delay.assert_called_once()