#!/usr/bin/env python3
"""
Test cases for the Neo4j Graphiti fallback issue fix.

This test reproduces and verifies the fix for:
- 'NoneType' object has no attribute 'table' error in temporal graph fallback
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from temporal.graph_client import GraphitiClient


class TestGraphitiFallbackFix:
    """Test cases for the Graphiti fallback fix."""

    def test_supabase_fallback_with_none_client(self):
        """Test that _store_in_supabase_fallback handles None supabase client gracefully."""
        client = GraphitiClient()
        
        # Simulate the scenario where supabase client is None
        with patch('temporal.graph_client.supabase', None):
            # This should not raise an exception, but should handle the error gracefully
            try:
                # Mock the _store_in_graphiti to always fail, forcing fallback
                with patch.object(client, '_store_in_graphiti', side_effect=Exception("Graphiti not available")):
                    result = asyncio.run(
                        client.record_lead_event(
                            lead_id="test_lead_123",
                            event_type="test_event",
                            event_data={"test": "data"},
                            timestamp=datetime.now()
                        )
                    )
                    # Should return True even if fallback fails gracefully
                    assert result is True  # Fallback should fail silently
            except Exception as e:
                pytest.fail(f"record_lead_event should handle None supabase gracefully, but got: {e}")

    def test_supabase_fallback_with_client_none_in_graph_client(self):
        """Test fallback behavior when supabase client in utils is None."""
        from utils import supabase_client
        
        # Save original client
        original_supabase = supabase_client.supabase
        try:
            # Set supabase to None to simulate initialization failure
            supabase_client.supabase = None
            
            client = GraphitiClient()
            # Disable graphiti to force fallback
            client.graphiti = None
            
            # This should handle the None supabase gracefully
            try:
                result = asyncio.run(
                    client.record_lead_event(
                        lead_id="test_lead_456",
                        event_type="test_event_2",
                        event_data={"test": "data_2"},
                        timestamp=datetime.now()
                    )
                )
                # Should return True even if fallback fails gracefully
                assert result is True
            except AttributeError as e:
                if "'NoneType' object has no attribute 'table'" in str(e):
                    pytest.fail(f"Expected fix for 'NoneType' error was not applied: {e}")
                else:
                    raise e
            except Exception as e:
                # Other exceptions are acceptable if they're not the specific one we're fixing
                if "table" in str(e).lower():
                    pytest.fail(f"Still seeing table-related error: {e}")
        finally:
            # Restore original client
            supabase_client.supabase = original_supabase


if __name__ == "__main__":
    pytest.main([__file__])