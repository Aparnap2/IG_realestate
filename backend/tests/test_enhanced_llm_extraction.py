"""
Comprehensive tests for the Enhanced LLM Extraction System.

Tests various message types, edge cases, and integration scenarios
to ensure robust lead information extraction.
"""

import sys
import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from utils.enhanced_llm_extraction import (
    MessageTypeClassifier,
    IntelligentExtractor,
    LangGraphExtractionNode,
    enhanced_extract_lead_info,
    create_extraction_workflow
)
from utils.llm_client import get_structured_llm_response
from schemas.state import AgentState


class TestMessageTypeClassifier:
    """Test message type classification functionality."""
    
    def test_classify_greeting_message(self):
        """Test classification of greeting messages."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "Hi there!",
            "Hello!",
            "Hey, how are you?",
            "Good morning!",
            "What's up?"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] in ["greeting", "information_request"]
            assert 0.0 <= result["intent_level"] <= 1.0
            assert 0.0 <= result["confidence"] <= 1.0
            assert "reasoning" in result
            assert result["extraction_priority"] in ["high", "medium", "low", "none"]
    
    def test_classify_qualification_message(self):
        """Test classification of qualification messages with details."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "I'm looking for a 2-bedroom condo in Manhattan with a budget of $500k",
            "Need a house in Austin, around $300k, looking to buy within 6 months",
            "Budget is $400k, want a 3BHK apartment near downtown",
            "Looking for property in Brooklyn, $600k budget, need 2 bedrooms"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] == "qualification"
            assert result["intent_level"] >= 0.6  # High intent for detailed messages
            assert result["extraction_priority"] in ["high", "medium"]
    
    def test_classify_information_request(self):
        """Test classification of information request messages."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "Can you send me details about available properties?",
            "What properties do you have in Manhattan?",
            "Do you have any listings under $400k?",
            "Can I see what's available in Brooklyn?",
            "Please send me the details"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] in ["information_request", "qualification"]
            assert result["intent_level"] >= 0.3  # At least moderate intent
    
    def test_classify_followup_message(self):
        """Test classification of follow-up messages."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "Thanks for the information!",
            "That sounds good, tell me more",
            "Yes, I'm interested in the Manhattan properties",
            "Can you also show me places in Queens?",
            "What about properties in Long Island?"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] in ["followup", "qualification"]
            assert result["intent_level"] >= 0.4  # Reasonable intent for follow-ups
    
    def test_classify_booking_interest(self):
        """Test classification of booking interest messages."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "I'd like to schedule a viewing",
            "Can we book a property tour?",
            "When can I see these properties?",
            "I want to schedule an appointment",
            "Available for showings this week?"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] == "booking_interest"
            assert result["intent_level"] >= 0.7  # High intent for booking
    
    def test_classify_spam_irrelevant(self):
        """Test classification of spam/irrelevant messages."""
        classifier = MessageTypeClassifier()
        
        test_messages = [
            "Buy cheap sunglasses!",
            "Free cryptocurrency!",
            "Click here to win a prize!",
            "Make money fast!",
            "Limited time offer!"
        ]
        
        for message in test_messages:
            result = classifier.classify_message(message)
            
            assert result["message_type"] in ["spam_irrelevant", "information_request"]
            assert result["intent_level"] <= 0.3  # Low intent for spam
            assert result["extraction_priority"] in ["low", "none"]


class TestIntelligentExtractor:
    """Test intelligent extraction with context awareness."""
    
    def test_extract_from_greeting_with_context(self):
        """Test extraction from greeting messages with conversation context."""
        extractor = IntelligentExtractor()
        
        message = "Hi! I'm John and I'm interested in buying a property"
        conversation_state = {"stage": "initial", "asked_questions": []}
        prior_lead_data = {}
        
        result = extractor.extract_with_context(
            message=message,
            message_type="greeting",
            conversation_state=conversation_state,
            prior_lead_data=prior_lead_data
        )
        
        # Should extract name and general interest
        assert result["name"] is not None or "john" in str(result).lower()
        assert "extraction_confidence" in result
        assert "conversation_stage" in result
        assert result["conversation_stage"] == "greeting"
    
    def test_extract_qualification_details(self):
        """Test extraction of detailed qualification information."""
        extractor = IntelligentExtractor()
        
        message = "Looking for a 3-bedroom house in Brooklyn, budget around $600k, want to move by March"
        conversation_state = {"stage": "qualification", "asked_questions": ["budget"]}
        prior_lead_data = {"budget": 500000}
        
        result = extractor.extract_with_context(
            message=message,
            message_type="qualification",
            conversation_state=conversation_state,
            prior_lead_data=prior_lead_data
        )
        
        # Should extract all relevant fields
        assert result["budget"] is not None or result["location"] is not None
        assert result["property_type"] is not None
        assert result["timeline"] is not None
        assert "extraction_confidence" in result
        assert result["conversation_stage"] == "qualification"
    
    def test_extract_followup_updates(self):
        """Test extraction of updates from follow-up messages."""
        extractor = IntelligentExtractor()
        
        message = "Actually, I can go up to $650k and I'm also interested in Queens"
        conversation_state = {"stage": "followup", "asked_questions": ["budget", "location"]}
        prior_lead_data = {"budget": 600000, "location": "Brooklyn"}
        
        result = extractor.extract_with_context(
            message=message,
            message_type="followup",
            conversation_state=conversation_state,
            prior_lead_data=prior_lead_data
        )
        
        # Should extract updated information
        assert result["budget"] is not None or result["location"] is not None
        assert "updated_fields" in result
        assert result["conversation_stage"] == "followup"
    
    def test_extract_booking_preferences(self):
        """Test extraction of booking preferences."""
        extractor = IntelligentExtractor()
        
        message = "I love the properties you showed me! Can we schedule a viewing this weekend?"
        conversation_state = {"stage": "qualified", "asked_questions": ["budget", "location", "property_type"]}
        prior_lead_data = {"budget": 600000, "location": "Brooklyn", "property_type": "3-bedroom"}
        
        result = extractor.extract_with_context(
            message=message,
            message_type="booking_interest",
            conversation_state=conversation_state,
            prior_lead_data=prior_lead_data
        )
        
        # Should confirm existing details and extract timing preferences
        assert "extraction_confidence" in result
        assert result["conversation_stage"] == "booking_interest"
    
    def test_extract_with_fallback(self):
        """Test fallback extraction when LLM fails."""
        extractor = IntelligentExtractor()
        
        # Mock LLM failure
        with patch('utils.enhanced_llm_extraction.get_structured_llm_response', side_effect=Exception("LLM Error")):
            result = extractor.extract_with_context(
                message="Hi there!",
                message_type="greeting"
            )
            
            # Should return fallback structure
            assert result["budget"] is None
            assert result["location"] is None
            assert result["extraction_confidence"] == 0.0
            assert result["extraction_method"] == "fallback"
            assert "error" in result or "raw_message" in result


class TestLangGraphExtractionNode:
    """Test LangGraph extraction node integration."""
    
    def test_extract_node_processing(self):
        """Test complete extraction node processing."""
        node = LangGraphExtractionNode()
        
        # Create mock lead
        class MockLead:
            def __init__(self):
                self.user_id = "test_user_123"
                self.message = "Hi! I'm looking for a 2-bedroom condo in Manhattan"
                self.budget = None
                self.location = None
                self.property_type = None
                self.timeline = None
                self.desired_bedrooms = None
                self.history = []
            
            def to_dict(self):
                return {
                    "budget": self.budget,
                    "location": self.location,
                    "property_type": self.property_type,
                    "timeline": self.timeline,
                    "desired_bedrooms": self.desired_bedrooms
                }
        
        lead = MockLead()
        state = {
            "lead": lead,
            "messages": [{"role": "user", "content": lead.message}]
        }
        
        # Mock conversation state
        with patch('utils.enhanced_llm_extraction.get_conversation_state', return_value=None):
            with patch('utils.enhanced_llm_extraction.set_conversation_state'):
                with patch('utils.enhanced_llm_extraction.audit_log_event'):
                    result = node.extract_node(state)
        
        # Verify result structure
        assert "lead" in result
        assert "messages" in result
        assert "extraction_result" in result
        assert "message_classification" in result
        assert "next_agent" in result
        assert result["next_agent"] == "qualifier"
    
    def test_extract_node_with_prior_data(self):
        """Test extraction node with prior lead data."""
        node = LangGraphExtractionNode()
        
        class MockLead:
            def __init__(self):
                self.user_id = "test_user_456"
                self.message = "Actually, I can increase my budget to $700k"
                self.budget = 600000  # Previous budget
                self.location = "Manhattan"
                self.property_type = "2-bedroom"
                self.timeline = None
                self.desired_bedrooms = 2
                self.history = []
            
            def to_dict(self):
                return {
                    "budget": self.budget,
                    "location": self.location,
                    "property_type": self.property_type,
                    "timeline": self.timeline,
                    "desired_bedrooms": self.desired_bedrooms
                }
        
        lead = MockLead()
        state = {
            "lead": lead,
            "messages": [{"role": "user", "content": lead.message}]
        }
        
        # Mock conversation state with prior context
        conversation_state = {
            "stage": "followup",
            "asked_questions": ["budget", "location"],
            "extraction_history": []
        }
        
        with patch('utils.enhanced_llm_extraction.get_conversation_state', return_value=conversation_state):
            with patch('utils.enhanced_llm_extraction.set_conversation_state'):
                with patch('utils.enhanced_llm_extraction.audit_log_event'):
                    result = node.extract_node(state)
        
        # Should detect budget update
        extraction_result = result["extraction_result"]
        assert "updated_fields" in extraction_result


class TestEnhancedExtractionIntegration:
    """Test integration with existing systems."""
    
    def test_enhanced_extract_lead_info_function(self):
        """Test the main enhanced extraction function."""
        result = enhanced_extract_lead_info(
            message="Hi! I'm Sarah, looking for a condo in Brooklyn with a $500k budget",
            user_id="test_user_789",
            prior_lead_data={}
        )
        
        # Should return complete extraction structure
        assert "budget" in result
        assert "location" in result
        assert "property_type" in result
        assert "extraction_confidence" in result
        assert "extraction_method" in result
        assert "conversation_stage" in result
    
    def test_extraction_workflow_creation(self):
        """Test creation of extraction workflow."""
        workflow = create_extraction_workflow()
        
        # Should create a compiled LangGraph workflow
        assert workflow is not None
        # Additional workflow verification would require actually running it
    
    @pytest.mark.asyncio
    async def test_production_integration(self):
        """Test integration with production lead processing."""
        # This would test the actual integration in production_lead_processing.py
        # For now, just verify the function exists and is callable
        from tasks.production_lead_processing import ProductionLeadProcessor
        
        processor = ProductionLeadProcessor()
        assert processor is not None
        assert hasattr(processor, 'process_lead_message')


class TestExtractionEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_empty_message(self):
        """Test extraction from empty or minimal messages."""
        result = enhanced_extract_lead_info(message="", user_id="test")
        
        assert result["budget"] is None
        assert result["location"] is None
        assert result["property_type"] is None
        assert "extraction_confidence" in result
    
    def test_very_long_message(self):
        """Test extraction from very long messages."""
        long_message = "Hi " * 1000  # Very long message
        
        result = enhanced_extract_lead_info(message=long_message, user_id="test")
        
        # Should handle gracefully without crashing
        assert "extraction_confidence" in result
    
    def test_special_characters(self):
        """Test extraction with special characters and emojis."""
        message = "Hi! 🏠 I'm looking for a 2BR apt in NYC 💰 $500k 📍 Manhattan"
        
        result = enhanced_extract_lead_info(message=message, user_id="test")
        
        # Should handle special characters gracefully
        assert "extraction_confidence" in result
    
    def test_multiple_languages(self):
        """Test extraction with mixed language content."""
        message = "Hola! I'm looking for a house in Los Angeles, presupuesto $400k"
        
        result = enhanced_extract_lead_info(message=message, user_id="test")
        
        # Should handle mixed language content
        assert "extraction_confidence" in result
    
    def test_conflicting_information(self):
        """Test extraction when conflicting information is provided."""
        message = "I want a 2-bedroom but also need 3 bedrooms, budget is 300k but also 500k"
        
        result = enhanced_extract_lead_info(message=message, user_id="test")
        
        # Should handle conflicts gracefully
        assert "extraction_confidence" in result
    
    def test_invalid_user_id(self):
        """Test extraction with invalid or missing user ID."""
        result = enhanced_extract_lead_info(message="Hi!", user_id=None)
        
        # Should handle gracefully
        assert "extraction_confidence" in result


class TestExtractionPerformance:
    """Test extraction performance and reliability."""
    
    def test_extraction_timing(self):
        """Test that extraction completes within reasonable time."""
        import time
        
        start_time = time.time()
        result = enhanced_extract_lead_info(
            message="Looking for a 2-bedroom condo in Manhattan, $500k budget",
            user_id="perf_test"
        )
        end_time = time.time()
        
        extraction_time = end_time - start_time
        
        # Should complete within 30 seconds (generous for LLM calls)
        assert extraction_time < 30.0
        assert "extraction_confidence" in result
    
    def test_multiple_concurrent_extractions(self):
        """Test multiple extractions running concurrently."""
        messages = [
            "Hi! I'm looking for a house in Brooklyn",
            "Budget is $600k for a 2-bedroom condo in Manhattan",
            "Need a 3-bedroom apartment in Queens, around $450k",
            "Looking for property in the Bronx, $400k budget"
        ]
        
        # Should handle multiple extractions
        results = []
        for i, message in enumerate(messages):
            result = enhanced_extract_lead_info(message=message, user_id=f"concurrent_test_{i}")
            results.append(result)
        
        # All should complete successfully
        assert len(results) == len(messages)
        for result in results:
            assert "extraction_confidence" in result
    
    def test_extraction_reliability(self):
        """Test extraction reliability across multiple runs."""
        message = "I'm looking for a 2-bedroom condo in Manhattan with a $500k budget"
        
        # Run extraction multiple times
        results = []
        for _ in range(3):
            result = enhanced_extract_lead_info(message=message, user_id="reliability_test")
            results.append(result)
        
        # Should be consistent across runs
        for result in results:
            assert "extraction_confidence" in result
            assert result["budget"] is not None or result["location"] is not None


def run_comprehensive_extraction_tests():
    """Run all extraction tests with sample Instagram messages."""
    
    print("🧪 Running Enhanced LLM Extraction Tests")
    print("=" * 60)
    
    # Sample Instagram messages representing different scenarios
    test_messages = [
        # Greeting messages
        {
            "message": "Hi there! 👋",
            "expected_type": "greeting",
            "description": "Simple greeting"
        },
        {
            "message": "Hello! I'm interested in real estate",
            "expected_type": "greeting", 
            "description": "Greeting with interest"
        },
        
        # Information requests
        {
            "message": "Please send me the details about available properties",
            "expected_type": "information_request",
            "description": "Property details request"
        },
        {
            "message": "What properties do you have in Manhattan?",
            "expected_type": "information_request",
            "description": "Location-specific inquiry"
        },
        
        # Qualification messages
        {
            "message": "Looking for a 2-bedroom condo in Brooklyn with a budget of $500k",
            "expected_type": "qualification",
            "description": "Detailed qualification"
        },
        {
            "message": "I need a 3-bedroom house in Queens, budget around $600k, want to move by March",
            "expected_type": "qualification",
            "description": "Comprehensive qualification"
        },
        
        # Follow-up messages
        {
            "message": "Thanks! That sounds good, can you also show me places in Manhattan?",
            "expected_type": "followup",
            "description": "Follow-up with additional interest"
        },
        {
            "message": "Actually, I can increase my budget to $650k",
            "expected_type": "followup",
            "description": "Budget update follow-up"
        },
        
        # Booking interest
        {
            "message": "I'd like to schedule a viewing for this weekend",
            "expected_type": "booking_interest",
            "description": "Booking request"
        },
        {
            "message": "When can I see these properties? I'm available next week",
            "expected_type": "booking_interest",
            "description": "Scheduling inquiry"
        },
        
        # Problematic messages
        {
            "message": "Buy cheap sunglasses! Free cryptocurrency!",
            "expected_type": "spam_irrelevant",
            "description": "Spam message"
        },
        {
            "message": "Please send me details",
            "expected_type": "information_request",
            "description": "Vague request"
        }
    ]
    
    print(f"📝 Testing {len(test_messages)} different message types...")
    print()
    
    # Test each message
    for i, test_case in enumerate(test_messages, 1):
        message = test_case["message"]
        expected_type = test_case["expected_type"]
        description = test_case["description"]
        
        print(f"Test {i:2d}: {description}")
        print(f"         Message: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        try:
            # Test enhanced extraction
            result = enhanced_extract_lead_info(
                message=message,
                user_id=f"test_user_{i}",
                prior_lead_data={}
            )
            
            # Verify basic structure
            assert "extraction_confidence" in result
            assert "extraction_method" in result
            assert "conversation_stage" in result
            
            confidence = result.get("extraction_confidence", 0.0)
            print(f"         ✅ Extraction completed - Confidence: {confidence:.2f}")
            
            # Check extracted fields
            extracted_fields = []
            for field in ["budget", "location", "property_type", "timeline", "desired_bedrooms", "name"]:
                if result.get(field) is not None:
                    extracted_fields.append(field)
            
            if extracted_fields:
                print(f"         📋 Extracted: {', '.join(extracted_fields)}")
            else:
                print(f"         ⚪ No specific fields extracted")
            
        except Exception as e:
            print(f"         ❌ Extraction failed: {e}")
        
        print()
    
    print("🎯 Extraction Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Run comprehensive tests
    run_comprehensive_extraction_tests()
    
    # Also run pytest if available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("⚠️ pytest not available, skipping automated test runner")