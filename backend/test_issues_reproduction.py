#!/usr/bin/env python3
"""
Simple test to verify the Neo4j Graphiti fallback issue exists.
"""

import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_graphiti_supabase_none_issue():
    """Test to reproduce the 'NoneType' object has no attribute 'table' issue."""
    from temporal.graph_client import GraphitiClient
    
    # Create a GraphitiClient instance
    client = GraphitiClient()
    
    # Force the graphiti client to be None to trigger fallback
    client.graphiti = None
    
    # Temporarily set the supabase client to None to reproduce the issue
    from utils import supabase_client
    original_supabase = supabase_client.supabase
    
    try:
        supabase_client.supabase = None
        
        print("Testing the fallback scenario where supabase is None...")
        
        # This should trigger the error when _store_in_supabase_fallback tries to access supabase.table
        try:
            import asyncio
            result = asyncio.run(
                client.record_lead_event(
                    lead_id="test_lead_123",
                    event_type="test_event",
                    event_data={"test": "data"},
                    timestamp=datetime.now()
                )
            )
            print(f"Result: {result}")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'table'" in str(e):
                print(f"✓ Reproduced the issue: {e}")
                return True
            else:
                print(f"✗ Different AttributeError: {e}")
                return False
        except Exception as e:
            print(f"✗ Different error: {e}")
            return False
            
    finally:
        # Restore original supabase client
        supabase_client.supabase = original_supabase
    
    return False

def test_multitenant_company_id_issue():
    """Test to reproduce the multi-tenant isolation issue."""
    print("\nTesting multi-tenant company_id issue...")
    
    from utils.supabase_client import save_or_update_lead
    
    test_instagram_id = "test_user_123"
    lead_data = {
        "instagram_id": test_instagram_id,
        "name": "Test User",
        "message": "Hello, I'm interested in properties",
        "channel": "ig"
    }
    
    # Mock the supabase client to avoid actual database calls
    import unittest.mock
    from utils.supabase_client import _ensure_supabase
    
    with unittest.mock.patch('utils.supabase_client._ensure_supabase') as mock_ensure:
        mock_supabase = unittest.mock.MagicMock()
        mock_result = unittest.mock.MagicMock()
        mock_result.data = [{"id": "test-uuid-123", "is_new": True}]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = mock_result
        mock_ensure.return_value = mock_supabase
        
        print("Saving lead without company_id...")
        result = save_or_update_lead(test_instagram_id, lead_data)
        
        # Check if the upsert was called with company_id
        upsert_call_args = mock_supabase.table.return_value.upsert.call_args[0][0]
        if "company_id" not in upsert_call_args:
            print("✓ Reproduced: Lead saved without company_id (violates multi-tenant isolation)")
            return True
        else:
            print("✗ company_id was found in the data")
            return False

if __name__ == "__main__":
    print("Testing the reported issues...")
    
    issue1_reproduced = test_graphiti_supabase_none_issue()
    issue2_reproduced = test_multitenant_company_id_issue()
    
    print(f"\nIssue 1 (Graphiti fallback): {'✓ Reproduced' if issue1_reproduced else '✗ Not reproduced'}")
    print(f"Issue 2 (Multi-tenant isolation): {'✓ Reproduced' if issue2_reproduced else '✗ Not reproduced'}")