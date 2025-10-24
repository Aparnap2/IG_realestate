"""
Tests for Instagram lead deduplication functionality.
This test suite ensures that duplicate prospect creation is prevented
and that the temporal knowledge graph maintains data integrity.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Import the functions we're testing
from utils.supabase_client import save_or_update_lead, save_lead
from tasks.production_lead_processing import ProductionLeadProcessor, process_lead_message


class TestLeadDeduplication:
    """Test suite for lead deduplication functionality"""

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client for testing"""
        mock_client = Mock()
        mock_table = Mock()
        mock_client.table.return_value = mock_table
        return mock_client, mock_table

    @pytest.fixture
    def sample_lead_data(self):
        """Sample lead data for testing"""
        return {
            "channel": "ig",
            "message": "Hi, I'm looking for a 2BHK condo in Miami with budget $500k",
            "status": "new",
            "budget": 500000,
            "location": "Miami",
            "property_type": "Condo",
            "name": "John Doe",
            "email": "john@example.com",
            "last_interaction_at": datetime.now().isoformat(),
            "history": [
                {
                    "message": "Hi, I'm looking for a 2BHK condo in Miami with budget $500k",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "user",
                    "details": "Initial message received"
                }
            ]
        }

    @pytest.fixture
    def production_processor(self):
        """Create a ProductionLeadProcessor instance for testing"""
        return ProductionLeadProcessor()

    @pytest.mark.asyncio
    async def test_save_or_update_lead_creates_new_lead(self, mock_supabase_client, sample_lead_data):
        """Test that save_or_update_lead creates a new lead when one doesn't exist"""
        mock_client, mock_table = mock_supabase_client
        
        # Mock no existing lead found
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        
        # Mock successful insert
        mock_response_data = {
            "id": "test-lead-id-123",
            "instagram_id": "PSID_test_user_123",
            "created_at": datetime.now().isoformat()
        }
        mock_table.upsert.return_value.execute.return_value.data = [mock_response_data]
        
        with patch('utils.supabase_client._ensure_supabase', return_value=mock_client):
            result = save_or_update_lead("PSID_test_user_123", sample_lead_data)
        
        # Verify results
        assert result["id"] == "test-lead-id-123"
        assert result["instagram_id"] == "PSID_test_user_123"
        assert result["is_new"] is True
        
        # Verify database calls
        mock_table.select.assert_called_once()
        mock_table.upsert.assert_called_once()
        
        # Verify the upsert data includes instagram_id
        call_args = mock_table.upsert.call_args[0][0]
        assert call_args["instagram_id"] == "PSID_test_user_123"
        assert call_args["user_id"] == "PSID_test_user_123"

    @pytest.mark.asyncio
    async def test_save_or_update_lead_updates_existing_lead(self, mock_supabase_client, sample_lead_data):
        """Test that save_or_update_lead updates an existing lead"""
        mock_client, mock_table = mock_supabase_client
        
        # Mock existing lead found
        existing_lead = {
            "id": "existing-lead-id-456",
            "instagram_id": "PSID_test_user_123",
            "status": "existing",
            "history": [
                {
                    "message": "Previous message",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "agent": "user"
                }
            ],
            "created_at": "2024-01-01T09:00:00Z"
        }
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [existing_lead]
        
        # Mock successful update
        mock_response_data = {
            "id": "existing-lead-id-456",
            "instagram_id": "PSID_test_user_123",
            "status": "updated",
            "created_at": "2024-01-01T09:00:00Z",
            "updated_at": datetime.now().isoformat()
        }
        mock_table.upsert.return_value.execute.return_value.data = [mock_response_data]
        
        with patch('utils.supabase_client._ensure_supabase', return_value=mock_client):
            result = save_or_update_lead("PSID_test_user_123", sample_lead_data)
        
        # Verify results
        assert result["id"] == "existing-lead-id-456"
        assert result["instagram_id"] == "PSID_test_user_123"
        assert result["is_new"] is False
        
        # Verify database calls
        mock_table.select.assert_called_once()
        mock_table.upsert.assert_called_once()
        
        # Verify the upsert data includes existing fields
        call_args = mock_table.upsert.call_args[0][0]
        assert call_args["id"] == "existing-lead-id-456"
        assert call_args["created_at"] == "2024-01-01T09:00:00Z"  # Preserved
        assert "updated_at" in call_args  # Added for update

    @pytest.mark.asyncio
    async def test_save_or_update_lead_merges_history(self, mock_supabase_client, sample_lead_data):
        """Test that history is properly merged without duplicates"""
        mock_client, mock_table = mock_supabase_client
        
        # Mock existing lead with history
        existing_lead = {
            "id": "existing-lead-id-789",
            "instagram_id": "PSID_test_user_123",
            "status": "existing",
            "history": [
                {
                    "message": "Existing message 1",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "agent": "user"
                },
                {
                    "message": "Existing message 2",
                    "timestamp": "2024-01-01T11:00:00Z",
                    "agent": "assistant"
                }
            ]
        }
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [existing_lead]
        
        # Add new history to sample data (including one duplicate)
        sample_lead_data["history"] = [
            {
                "message": "Existing message 1",  # Duplicate
                "timestamp": "2024-01-01T10:00:00Z",
                "agent": "user"
            },
            {
                "message": "New message",  # New unique message
                "timestamp": datetime.now().isoformat(),
                "agent": "customer"
            }
        ]
        
        mock_table.upsert.return_value.execute.return_value.data = [existing_lead]
        
        with patch('utils.supabase_client._ensure_supabase', return_value=mock_client):
            result = save_or_update_lead("PSID_test_user_123", sample_lead_data)
        
        # Verify merged history
        call_args = mock_table.upsert.call_args[0][0]
        merged_history = call_args["history"]
        
        # Should have 3 unique history entries (2 existing + 1 new)
        assert len(merged_history) == 3
        
        # Verify new message is present
        new_message_present = any(
            entry["message"] == "New message" for entry in merged_history
        )
        assert new_message_present
        
        # Verify duplicates were removed
        duplicate_count = sum(
            1 for entry in merged_history 
            if entry["message"] == "Existing message 1" and entry["timestamp"] == "2024-01-01T10:00:00Z"
        )
        assert duplicate_count == 1

    @pytest.mark.asyncio
    async def test_production_processor_uses_deduplication(self, production_processor, sample_lead_data):
        """Test that the production processor uses the deduplication logic"""
        instagram_id = "PSID_integration_test_123"
        message = "Hello, I'm looking for a property"
        
        # Mock the save_or_update_lead function
        mock_saved_lead = {
            "id": "integration-test-lead",
            "instagram_id": instagram_id,
            "is_new": True
        }
        
        with patch('tasks.production_lead_processing.save_or_update_lead', return_value=mock_saved_lead), \
             patch.object(production_processor, 'extract_lead_info', return_value={}), \
             patch.object(production_processor, '_query_properties_with_llm', return_value=[]), \
             patch.object(production_processor, 'qualify_lead', return_value={"score": 0.8, "reasoning": "Good lead"}), \
             patch.object(production_processor, 'determine_next_agent', return_value="scheduler"), \
             patch.object(production_processor, 'generate_response_message', return_value="Thanks for your inquiry!"), \
             patch.object(production_processor, '_apply_compliance_guardrails', return_value=("Safe response", {"passed": True})), \
             patch.object(production_processor, 'check_hitl_interrupt', return_value=False), \
             patch.object(production_processor, '_record_temporal_event', new_callable=AsyncMock), \
             patch('tasks.production_lead_processing.redis_client'):
            
            result = await production_processor.process_lead_message(
                user_id=instagram_id,
                message=message,
                channel="ig",
                user_name="Test User"
            )
        
        # Verify deduplication function was called with correct parameters
        save_or_update_lead.assert_called_once_with(instagram_id, ANY)
        
        # Verify result includes lead information
        assert result["user_id"] == instagram_id
        assert result["lead_id"] == "integration-test-lead"
        assert result["status"] == "success"

    @pytest.mark.asyncio  
    async def test_duplicate_message_prevention(self, production_processor):
        """Test that duplicate messages from the same Instagram user don't create duplicate leads"""
        instagram_id = "PSID_duplicate_test_123"
        message = "Looking for a condo in Miami"
        
        # First call - should create new lead
        mock_saved_lead_first = {
            "id": "first-lead",
            "instagram_id": instagram_id,
            "is_new": True
        }
        
        # Second call - should update existing lead
        mock_saved_lead_second = {
            "id": "first-lead",  # Same ID
            "instagram_id": instagram_id,
            "is_new": False  # Not new duplicate
        }
        
        with patch('tasks.production_lead_processing.save_or_update_lead') as mock_save_lead, \
             patch.object(production_processor, 'extract_lead_info', return_value={}), \
             patch.object(production_processor, '_query_properties_with_llm', return_value=[]), \
             patch.object(production_processor, 'qualify_lead', return_value={"score": 0.8, "reasoning": "Good lead"}), \
             patch.object(production_processor, 'determine_next_agent', return_value="scheduler"), \
             patch.object(production_processor, 'generate_response_message', return_value="Thanks for your inquiry!"), \
             patch.object(production_processor, '_apply_compliance_guardrails', return_value=("Safe response", {"passed": True})), \
             patch.object(production_processor, 'check_hitl_interrupt', return_value=False), \
             patch.object(production_processor, '_record_temporal_event', new_callable=AsyncMock), \
             patch('tasks.production_lead_processing.redis_client'):
            
            # Configure mock to return different results for first and second call
            mock_save_lead.side_effect = [mock_saved_lead_first, mock_saved_lead_second]
            
            # Process first message
            result1 = await production_processor.process_lead_message(
                user_id=instagram_id,
                message=message,
                channel="ig"
            )
            
            # Process second message (same user)
            result2 = await production_processor.process_lead_message(
                user_id=instagram_id,
                message=message + " again",  # Slightly different message
                channel="ig"
            )
        
        # Verify both calls used deduplication
        assert mock_save_lead.call_count == 2
        assert mock_save_lead.call_args_list[0][0] == (instagram_id, ANY)
        assert mock_save_lead.call_args_list[1][0] == (instagram_id, ANY)
        
        # Verify first call created new lead
        assert result1["lead_id"] == "first-lead"
        
        # Verify second call updated existing lead (same lead_id)
        assert result2["lead_id"] == "first-lead"  # Same lead ID

    @pytest.mark.asyncio
    async def test_backward_compatibility_with_save_lead(self, mock_supabase_client, sample_lead_data):
        """Test that legacy save_lead function still works and sets instagram_id"""
        mock_client, mock_table = mock_supabase_client
        
        # Mock no existing lead found for backward compatibility check
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        
        # Mock successful insert
        mock_response_data = {
            "id": "legacy-test-lead",
            "instagram_id": "PSID_legacy_user_456",
            "user_id": "PSID_legacy_user_456"  # Both should be set
        }
        mock_table.upsert.return_value.execute.return_value.data = [mock_response_data]
        
        # Call with legacy save_lead function
        sample_lead_data["user_id"] = "PSID_legacy_user_456"
        
        with patch('utils.supabase_client._ensure_supabase', return_value=mock_client):
            result = save_lead(sample_lead_data)
        
        # Verify both instagram_id and user_id are set
        assert result["instagram_id"] == "PSID_legacy_user_456"
        assert result["user_id"] == "PSID_legacy_user_456"


# Integration test with real database (can be run in staging)
@pytest.mark.integration
async def test_end_to_end_deduplication():
    """
    Integration test that verifies end-to-end deduplication with a real database.
    This test should only be run in a staging environment.
    """
    # This would require actual database setup
    # For now, we'll skip this in unit tests
    pytest.skip("Integration test - requires database setup")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
