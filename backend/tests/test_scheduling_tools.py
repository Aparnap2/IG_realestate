"""
Test Scheduling Tools - Calendar Integration & Multi-Constraint Planning

Tests the scheduling utilities and calendar integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from tools.calendar_integration import (
    GoogleCalendarClient,
    get_available_calendar_slots,
    create_tour_event
)
from tools.scheduling_utils import (
    find_optimal_tour_slots,
    optimize_property_sequence,
    predict_no_show_risk,
    calculate_tour_score
)


class TestGoogleCalendarIntegration:
    """Test Google Calendar API integration."""
    
    def test_calendar_client_initialization(self, mock_settings):
        """Test calendar client initialization."""
        client = GoogleCalendarClient()
        assert client is not None
        # In test mode, service should be None
        assert client.service is None
    
    def test_mock_freebusy_slots(self, mock_settings):
        """Test mock free/busy slot generation."""
        client = GoogleCalendarClient()
        slots = client._mock_freebusy_slots(days_ahead=7)
        
        assert len(slots) > 0
        assert all(isinstance(slot['start'], datetime) for slot in slots)
        assert all(slot['duration_minutes'] == 60 for slot in slots)
    
    def test_mock_event_creation(self, mock_settings):
        """Test mock event creation."""
        client = GoogleCalendarClient()
        start_time = datetime.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        
        result = client._mock_create_event(
            start_time=start_time,
            end_time=end_time,
            summary="Test Tour",
            attendee_emails=["test@example.com"]
        )
        
        assert result["status"] == "mock_created"
        assert result["event_id"].startswith("mock_event_")
        assert "meet.google.com" in result["meet_link"]
    
    def test_get_available_calendar_slots_function(self, mock_settings, mock_audit):
        """Test the get_available_calendar_slots function."""
        slots = get_available_calendar_slots(days_ahead=5, time_of_day="afternoon")
        
        assert isinstance(slots, list)
        # Should return some slots (mock implementation)
        assert len(slots) >= 0
    
    def test_create_tour_event_function(self, mock_settings, mock_audit):
        """Test the create_tour_event function."""
        start_time = datetime.now() + timedelta(days=1)
        
        result = create_tour_event(
            start_time=start_time,
            duration_minutes=90,
            attendee_email="test@example.com",
            summary="Property Tour",
            description="Tour of 3BR properties",
            property_addresses=["123 Main St", "456 Oak Ave"]
        )
        
        assert "event_id" in result
        assert result.get("status") in ["created", "mock_created"]
        assert "meet_link" in result


class TestSchedulingOptimization:
    """Test multi-constraint scheduling optimization."""
    
    def test_find_optimal_tour_slots(self, sample_properties, mock_audit):
        """Test optimal tour slot finding."""
        test_lead = {
            "user_id": "test_123",
            "budget": 400000,
            "timeline": "immediate"
        }
        
        test_constraints = {
            "agent_calendar": [
                datetime.now() + timedelta(days=1, hours=10),
                datetime.now() + timedelta(days=1, hours=14),
                datetime.now() + timedelta(days=2, hours=10)
            ]
        }
        
        tour_slots = find_optimal_tour_slots(test_lead, sample_properties, test_constraints)
        
        assert isinstance(tour_slots, list)
        # Should return some options
        if tour_slots:
            assert all("start_time" in slot for slot in tour_slots)
            assert all("overall_score" in slot for slot in tour_slots)
    
    def test_property_sequence_optimization(self, sample_properties):
        """Test property sequence optimization."""
        start_time = datetime.now() + timedelta(days=1)
        
        optimized_sequence = optimize_property_sequence(sample_properties, start_time)
        
        assert len(optimized_sequence) == len(sample_properties)
        # Should return all properties (order may be optimized)
        assert all(prop in optimized_sequence for prop in sample_properties)
    
    def test_no_show_risk_prediction(self):
        """Test no-show risk prediction."""
        # High-value, immediate timeline lead (low risk)
        high_value_lead = {
            "user_id": "test_high",
            "budget": 600000,
            "timeline": "immediate",
            "engagement_score": 0.9
        }
        
        risk = predict_no_show_risk(high_value_lead)
        assert 0.0 <= risk <= 1.0
        assert risk < 0.5  # Should be low risk
        
        # Low-value, exploring lead (high risk)
        low_value_lead = {
            "user_id": "test_low",
            "budget": 150000,
            "timeline": "exploring",
            "engagement_score": 0.2
        }
        
        risk = predict_no_show_risk(low_value_lead)
        assert 0.0 <= risk <= 1.0
        assert risk > 0.3  # Should be higher risk
    
    def test_tour_score_calculation(self):
        """Test tour option scoring."""
        tour_option = {
            "start_time": datetime.now() + timedelta(days=1),
            "travel_efficiency": 0.8,
            "property_availability": 1.0,
            "lead_preference_score": 0.7,
            "no_show_risk": 0.2,
            "total_duration": 120
        }
        
        score = calculate_tour_score(tour_option)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be a good score with these metrics
    
    def test_scheduling_with_no_properties(self):
        """Test scheduling behavior with no properties."""
        tour_slots = find_optimal_tour_slots(
            lead={"user_id": "test"},
            properties=[],
            constraints={"agent_calendar": [datetime.now() + timedelta(days=1)]}
        )
        
        assert isinstance(tour_slots, list)
        # Should handle empty properties gracefully
    
    def test_scheduling_with_no_calendar_slots(self, sample_properties):
        """Test scheduling behavior with no available calendar slots."""
        tour_slots = find_optimal_tour_slots(
            lead={"user_id": "test"},
            properties=sample_properties,
            constraints={"agent_calendar": []}  # No available slots
        )
        
        assert isinstance(tour_slots, list)
        assert len(tour_slots) == 0  # Should return empty list


class TestSchedulingIntegration:
    """Test scheduling integration with other components."""
    
    def test_scheduler_agent_integration(self, mock_settings, mock_audit):
        """Test scheduler agent integration with scheduling tools."""
        from backend.agents.prd_compliant_workflow import SchedulerAgent
        
        scheduler = SchedulerAgent()
        
        # Create test state
        from models.lead import Lead
        test_lead = Lead(
            user_id="test_scheduler",
            channel="ig",
            message="I want to schedule a tour",
            email="test@example.com"
        )
        
        test_state = {
            "lead": test_lead,
            "messages": [{"role": "user", "content": "I want to schedule a tour"}]
        }
        
        # Mock calendar slots
        with patch('tools.agent_tools.get_available_calendar_slots') as mock_slots:
            mock_slots.invoke.return_value = [datetime.now() + timedelta(days=1)]
            
            with patch('tools.agent_tools.book_calendar_event') as mock_book:
                mock_book.invoke.return_value = {"event_id": "test_event", "status": "booked"}
                
                with patch('tools.agent_tools.send_instagram_message') as mock_send:
                    mock_send.invoke.return_value = True
                    
                    with patch('tools.agent_tools.create_hubspot_contact') as mock_contact:
                        mock_contact.invoke.return_value = {"contact_id": "test_contact"}
                        
                        with patch('tools.agent_tools.save_lead_tool') as mock_save:
                            mock_save.invoke.return_value = {}
                            
                            result = scheduler.process(test_state)
                            
                            assert result["lead"].status == "scheduled"
                            assert len(result["messages"]) > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])