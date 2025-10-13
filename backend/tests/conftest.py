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
    from config import Settings
    
    settings = Settings(
        ENVIRONMENT="testing",
        DEBUG=True,
        SUPABASE_URL="http://localhost:54321",
        SUPABASE_KEY="test_key",
        REDIS_URL="redis://localhost:6380",
        OPENROUTER_API_KEY="test_key",
        INSTAGRAM_PAGE_ACCESS_TOKEN="test_token",
        INSTAGRAM_VERIFY_TOKEN="test_verify",
        INSTAGRAM_APP_SECRET="test_secret",
        SECRET_KEY="test_secret_key",
        AUDIT_SALT="test_audit_salt",
        ENABLE_ROUTER_AGENT=True,
        ENABLE_COMPLIANCE_CHECKS=True,
        ENABLE_AUDIT_LOGGING=True,
        ENABLE_REAL_INSTAGRAM_API=False,
        ENABLE_TEMPORAL_GRAPH=False,
        ENABLE_GOOGLE_CALENDAR=False
    )
    
    with patch('config.get_settings', return_value=settings):
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
    
    with patch('temporal.graph_client.get_graphiti_client', return_value=mock_client):
        yield mock_client


@pytest.fixture
def qualifier_agent(mock_settings, mock_supabase, mock_compliance, mock_audit, mock_temporal_graph):
    """Provide a QualifierAgent with dependencies mocked."""
    from backend.agents.prd_compliant_workflow import QualifierAgent
    return QualifierAgent()


@pytest.fixture
def router_agent(mock_settings, mock_supabase, mock_compliance, mock_audit, mock_temporal_graph):
    """Provide a RouterAgent with dependencies mocked."""
    from backend.agents.router import RouterAgent
    return RouterAgent()

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