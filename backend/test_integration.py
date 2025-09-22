#!/usr/bin/env python3

import sys
import os
from unittest.mock import patch, MagicMock

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the OpenAI, Supabase, and Redis clients before importing our modules
mock_redis_client = MagicMock()
mock_redis_client.keys.return_value = []
with patch('openai.OpenAI'), patch('supabase.create_client'), patch('redis.from_url', return_value=mock_redis_client):
    from backend.models.lead import Lead
    from backend.schemas.state import AgentState
    from backend.workflow import create_workflow

def test_workflow_creation():
    """Test that we can create the workflow with Redis checkpointer"""
    try:
        workflow = create_workflow()
        print("✓ Workflow creation successful")
        return True
    except Exception as e:
        print(f"✗ Workflow creation failed: {e}")
        return False

def test_lead_model():
    """Test that we can create a Lead model"""
    try:
        lead = Lead(
            id="test_lead_123",
            channel="ig",
            user_id="user_456",
            message="2BHK in Miami, $300k",
            budget=300000,
            location="Miami",
            property_type="2BHK"
        )
        print("✓ Lead model creation successful")
        return True
    except Exception as e:
        print(f"✗ Lead model creation failed: {e}")
        return False

def test_state_schema():
    """Test that we can create an AgentState"""
    try:
        lead = Lead(
            id="test_lead_123",
            channel="ig",
            user_id="user_456",
            message="2BHK in Miami, $300k",
            budget=300000,
            location="Miami",
            property_type="2BHK"
        )
        
        state = AgentState(
            lead=lead,
            messages=[{"role": "user", "content": lead.message}],
            human_feedback=None,
            next_agent="qualifier",
            interrupt=False
        )
        print("✓ AgentState creation successful")
        return True
    except Exception as e:
        print(f"✗ AgentState creation failed: {e}")
        return False

if __name__ == "__main__":
    print("Running basic integration tests...")
    
    tests = [
        test_lead_model,
        test_state_schema,
        test_workflow_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! ✓")
        sys.exit(0)
    else:
        print("Some tests failed! ✗")
        sys.exit(1)