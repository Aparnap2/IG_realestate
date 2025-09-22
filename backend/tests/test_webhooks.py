import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.api.webhooks import process_instagram_message, process_whatsapp_message

def test_instagram_message_processing():
    """Test Instagram message processing flow"""
    # Sample Instagram webhook data
    instagram_data = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "sender_123"},
                        "message": {
                            "mid": "message_456",
                            "text": "2BHK in Miami, $300k"
                        }
                    }
                ]
            }
        ]
    }
    
    with patch('backend.api.webhooks.save_lead') as mock_save, \
         patch('backend.api.webhooks.queue_lead_for_processing') as mock_queue, \
         patch('backend.api.webhooks.is_duplicate_message') as mock_duplicate:
        
        # Mock duplicate check to return False
        mock_duplicate.return_value = False
        
        # Process the message
        process_instagram_message(instagram_data)
        
        # Verify mocks were called
        mock_duplicate.assert_called_once_with("message_456")
        mock_save.assert_called_once()
        mock_queue.assert_called_once()

def test_whatsapp_message_processing():
    """Test WhatsApp message processing flow"""
    # Sample WhatsApp webhook data
    whatsapp_data = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "sender_123",
                                    "id": "message_456",
                                    "type": "text",
                                    "text": {
                                        "body": "2BHK in Miami, $300k"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    with patch('backend.api.webhooks.save_lead') as mock_save, \
         patch('backend.api.webhooks.queue_lead_for_processing') as mock_queue, \
         patch('backend.api.webhooks.is_duplicate_message') as mock_duplicate:
        
        # Mock duplicate check to return False
        mock_duplicate.return_value = False
        
        # Process the message
        process_whatsapp_message(whatsapp_data)
        
        # Verify mocks were called
        mock_duplicate.assert_called_once_with("message_456")
        mock_save.assert_called_once()
        mock_queue.assert_called_once()

def test_duplicate_message_filtering():
    """Test that duplicate messages are filtered out"""
    # Sample Instagram webhook data with duplicate message ID
    instagram_data = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "sender_123"},
                        "message": {
                            "mid": "duplicate_message_456",
                            "text": "2BHK in Miami, $300k"
                        }
                    }
                ]
            }
        ]
    }
    
    with patch('backend.api.webhooks.save_lead') as mock_save, \
         patch('backend.api.webhooks.queue_lead_for_processing') as mock_queue, \
         patch('backend.api.webhooks.is_duplicate_message') as mock_duplicate:
        
        # Mock duplicate check to return True
        mock_duplicate.return_value = True
        
        # Process the message
        process_instagram_message(instagram_data)
        
        # Verify that save and queue were not called
        mock_save.assert_not_called()
        mock_queue.assert_not_called()

def test_error_handling_in_processing():
    """Test error handling in message processing"""
    # Sample Instagram webhook data
    instagram_data = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "sender_123"},
                        "message": {
                            "mid": "message_456",
                            "text": "2BHK in Miami, $300k"
                        }
                    }
                ]
            }
        ]
    }
    
    with patch('backend.api.webhooks.save_lead') as mock_save, \
         patch('backend.api.webhooks.queue_lead_for_processing') as mock_queue, \
         patch('backend.api.webhooks.is_duplicate_message') as mock_duplicate:
        
        # Mock duplicate check to return False
        mock_duplicate.return_value = False
        
        # Mock save_lead to raise an exception
        mock_save.side_effect = Exception("Database error")
        
        # Process the message - should not raise an exception
        process_instagram_message(instagram_data)
        
        # Verify that queue_lead_for_processing was still called
        # (in a real implementation, we might want to handle this differently)
        mock_queue.assert_called_once()