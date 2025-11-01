"""
Pytest configuration and fixtures for the Real Estate AI Platform tests.

This file provides shared fixtures and configuration for all tests.
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Add repository paths to module search
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REPO_DIR = os.path.abspath(os.path.join(BACKEND_DIR, '..'))

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from config import TestingSettings
    
    with patch('config.get_settings') as mock_get_settings:
        settings = TestingSettings()
        # Override with test values
        settings.SUPABASE_URL = "http://localhost:54321"
        settings.SUPABASE_KEY = "test_key"
        settings.REDIS_URL = "redis://localhost:6380"
        settings.OPENROUTER_API_KEY = "test_key"
        settings.INSTAGRAM_PAGE_ACCESS_TOKEN = "test_token"
        settings.INSTAGRAM_VERIFY_TOKEN = "test_verify"
        settings.INSTAGRAM_APP_SECRET = "test_secret"
        settings.INSTAGRAM_PAGE_ID = "test_page_id"
        
        mock_get_settings.return_value = settings
        yield settings

@pytest.fixture
def sample_lead():
    """Create a sample lead for testing."""
    from models.lead import Lead
    
    return Lead(
        user_id="test_user_123",
        channel="ig",
        message="I'm looking for a 3BR house under $400k in Miami",
        budget=400000,
        location="Miami",
        property_type="3BHK",
        timeline="1-3months",
        name="Test User",
        email="test@example.com"
    )

@pytest.fixture
def sample_properties():
    """Create sample properties for testing."""
    return [
        {
            "id": "prop_1",
            "price": 350000,
            "location": "Miami",
            "property_type": "3BHK",
            "bedrooms": 3,
            "amenities": {"pool": True, "gym": True},
            "details": {"sqft": 1500, "year_built": 2020}
        },
        {
            "id": "prop_2", 
            "price": 380000,
            "location": "Miami",
            "property_type": "3BHK",
            "bedrooms": 3,
            "amenities": {"pool": True, "gym": False},
            "details": {"sqft": 1600, "year_built": 2019}
        },
        {
            "id": "prop_3",
            "price": 320000,
            "location": "Miami",
            "property_type": "2BHK",
            "bedrooms": 2,
            "amenities": {"pool": True, "gym": True, "balcony": True},
            "details": {"sqft": 1200, "year_built": 2021}
        }
    ]

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    mock_client = Mock()
    mock_table = Mock()
    mock_client.table.return_value = mock_table
    
    # Mock common operations
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = Mock(data=[])
    
    with patch('utils.supabase_client.supabase', mock_client):
        yield mock_client

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_client = Mock()
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.ping.return_value = True
    
    with patch('utils.redis_client.redis_client', mock_client):
        yield mock_client

@pytest.fixture
def mock_llm():
    """Mock LLM client for testing."""
    mock_response = {
        "score": 0.8,
        "reasoning": "High budget and specific location indicate serious buyer"
    }
    
    with patch('utils.llm_client.get_llm_response_sync', return_value='{"score": 0.8, "reasoning": "Test reasoning"}'):
        yield mock_response

@pytest.fixture
def mock_audit():
    """Mock audit logging for testing."""
    with patch('utils.audit.audit_log_event', return_value="test_event_id") as mock_audit:
        yield mock_audit

@pytest.fixture
def mock_compliance():
    """Mock compliance tools for testing."""
    async def mock_fair_housing_evaluator(message, context=None):
        # Mock safe message
        if "young professionals" in message.lower():
            return {
                "passed": False,
                "violations": [{"pattern": "age", "risk_level": "high"}],
                "suggested_replacement": "I can help you find properties that match your needs."
            }
        return {
            "passed": True,
            "violations": [],
            "suggested_replacement": message
        }
    
    with patch('tools.compliance.fair_housing_evaluator', side_effect=mock_fair_housing_evaluator):
        yield mock_fair_housing_evaluator

@pytest.fixture
def mock_temporal_graph():
    """Mock temporal graph client for testing."""
    mock_client = Mock()
    mock_client.record_lead_event = AsyncMock(return_value=True)
    mock_client.get_lead_history = AsyncMock(return_value=[])
    mock_client.get_engagement_trajectory = AsyncMock(return_value={
        "trajectory": "stable",
        "confidence": 0.7,
        "trend": "moderately_engaged",
        "recent_activity": 2
    })
    
    with patch('temporal.graph_client.GraphClient') as mock_graph_client:
        mock_graph_client.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    mock_client = Mock()
    
    # Mock common Supabase operations
    mock_table = Mock()
    mock_client.table.return_value = mock_table
    
    # Chain table methods
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.single.return_value = mock_table
    mock_table.execute.return_value = Mock(data=[], error=None)
    
    with patch('utils.supabase_client.create_client') as mock_create_client:
        mock_create_client.return_value = mock_client
        with patch('utils.supabase_client.supabase', mock_client):
            yield mock_client

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_client = Mock()
    
    # Mock common Redis operations
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.setex.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 0
    mock_client.ping.return_value = True
    mock_client.flushdb.return_value = True
    mock_client.close.return_value = None
    
    # Mock pipeline operations
    mock_pipeline = Mock()
    mock_pipeline.execute.return_value = []
    mock_client.pipeline.return_value = mock_pipeline
    
    with patch('utils.redis_client.create_redis_client') as mock_create_client:
        mock_create_client.return_value = mock_client
        with patch('utils.redis_client.redis_client', mock_client):
            yield mock_client

@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    mock_client = Mock()
    mock_client.generate_response = AsyncMock(return_value={
        "content": "Test response",
        "confidence": 0.8
    })
    mock_client.analyze_intent = AsyncMock(return_value={
        "intent": "booking_interest",
        "confidence": 0.9
    })
    mock_client.score_lead = AsyncMock(return_value=0.8)
    
    with patch('utils.llm_client.LLMClient') as mock_llm_client_class:
        mock_llm_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_router_agent():
    """Mock router agent."""
    mock_agent = Mock()
    mock_agent.route_lead = AsyncMock(return_value={
        "lead": None,
        "messages": [],
        "next_agent": "qualifier",
        "requires_human_review": False
    })
    return mock_agent

@pytest.fixture
def mock_qualifier_agent():
    """Mock qualifier agent."""
    mock_agent = Mock()
    mock_agent.process_lead = AsyncMock(return_value={
        "lead": None,
        "messages": [],
        "next_agent": "scheduler",
        "requires_human_review": False,
        "qualified_score": 0.8
    })
    return mock_agent

@pytest.fixture
def mock_value_delivery_agent():
    """Mock value delivery agent."""
    mock_agent = Mock()
    mock_agent.deliver_value = AsyncMock(return_value={
        "lead": None,
        "messages": [],
        "next_agent": "qualifier",
        "requires_human_review": False
    })
    return mock_agent

@pytest.fixture
def mock_followup_agent():
    """Mock followup agent."""
    mock_agent = Mock()
    mock_agent.nurture_lead = AsyncMock(return_value={
        "lead": None,
        "messages": [],
        "next_agent": "value_delivery",
        "requires_human_review": False
    })
    return mock_agent

@pytest.fixture
def agent_state(sample_lead):
    """Create a sample agent state for testing."""
    return {
        "lead": sample_lead,
        "messages": [
            {"role": "user", "content": sample_lead.message}
        ],
        "current_agent": None,
        "requires_human_review": False,
        "db_results": [],
        "next_agent": None,
        "interrupt": False
    }