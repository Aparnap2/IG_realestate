import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from backend.agents.prd_compliant_workflow import SchedulerAgent


def test_normalize_slots_accepts_dict_and_datetime():
    agent = SchedulerAgent()
    raw_slots = [
        {
            "start": datetime(2024, 1, 1, 10, 0),
            "end": datetime(2024, 1, 1, 11, 0)
        },
        datetime(2024, 1, 2, 15, 0)
    ]

    normalized = agent._normalize_slots(raw_slots)

    assert len(normalized) == 2
    assert all("start" in slot for slot in normalized)
    assert isinstance(normalized[0]["start"], datetime)


def test_normalize_slots_filters_invalid_entries():
    agent = SchedulerAgent()
    raw_slots = [
        {"start": "not-a-date"},
        {"start": "2024-01-01T12:00:00"}
    ]

    normalized = agent._normalize_slots(raw_slots)

    assert len(normalized) == 1
    assert normalized[0]["start"].isoformat().startswith("2024-01-01T12:00:00")


class TestSchedulerTourOptimization:
    """Test Scheduler Agent tour optimization features per PRD requirements."""
    
    @pytest.fixture
    def scheduler_agent(self, mock_settings):
        """Create a Scheduler Agent instance for testing."""
        return SchedulerAgent()
    
    @pytest.fixture 
    def sample_properties(self):
        """Sample properties for tour optimization testing."""
        return [
            {
                "id": "prop1",
                "address": "123 Main St, Miami, FL 33101",
                "lat": 25.7617,
                "lng": -80.1918,
                "price": 350000,
                "bedrooms": 3
            },
            {
                "id": "prop2", 
                "address": "456 Ocean Ave, Miami Beach, FL 33139",
                "lat": 25.7907,
                "lng": -80.1300,
                "price": 425000,
                "bedrooms": 2
            },
            {
                "id": "prop3",
                "address": "789 Downtown Blvd, Miami, FL 33128", 
                "lat": 25.7617,
                "lng": -80.1918,
                "price": 280000,
                "bedrooms": 3
            }
        ]
    
    def test_tour_optimization_by_travel_time(self, scheduler_agent, sample_properties):
        """Test tour optimization by travel time between properties."""
        # Available slots for testing
        slots = [
            {"start": datetime(2024, 1, 15, 10, 0), "end": datetime(2024, 1, 15, 12, 0)},
            {"start": datetime(2024, 1, 15, 14, 0), "end": datetime(2024, 1, 15, 16, 0)}
        ]
        
        result = scheduler_agent.optimize_tour_sequence(
            properties=sample_properties,
            time_slots=slots,
            start_location="Downtown Miami"
        )
        
        # Should return optimized tour sequence
        assert "optimized_sequence" in result
        assert "total_travel_time" in result
        assert "estimated_tour_duration" in result
        assert len(result["optimized_sequence"]) == len(sample_properties)
        assert result["total_travel_time"] > 0
    
    def test_buffer_slots_between_tours(self, scheduler_agent):
        """Test buffer slot management between consecutive tours."""
        slots = [
            {"start": datetime(2024, 1, 15, 10, 0), "end": datetime(2024, 1, 15, 11, 30)},
            {"start": datetime(2024, 1, 15, 11, 45), "end": datetime(2024, 1, 15, 13, 15)},  # No buffer
            {"start": datetime(2024, 1, 15, 13, 30), "end": datetime(2024, 1, 15, 15, 0)}   # With buffer
        ]
        
        filtered_slots = scheduler_agent.apply_buffer_times(slots, buffer_minutes=30)
        
        # Should filter out slots without adequate buffer
        assert len(filtered_slots) == 2
        assert filtered_slots[0]["start"] == datetime(2024, 1, 15, 10, 0)
        assert filtered_slots[1]["start"] == datetime(2024, 1, 15, 13, 30)
    
    def test_multi_property_tour_creation(self, scheduler_agent, sample_properties, agent_state):
        """Test creation of multi-property tour events."""
        agent_state["lead"].email = "test@example.com"
        selected_slot = {
            "start": datetime(2024, 1, 15, 10, 0),
            "end": datetime(2024, 1, 15, 12, 0)
        }
        
        result = scheduler_agent.create_optimized_tour_event(
                lead=agent_state["lead"],
                properties=sample_properties[:2],  # 2 properties
                time_slot=selected_slot
            )
            
            # Should create optimization result with property addresses
            assert result["success"] == True
            assert "property_addresses" in result
            assert len(result["property_addresses"]) == 2
            assert "optimized_properties" in result
            assert len(result["optimized_properties"]) == 2
    
    def test_tour_duration_calculation(self, scheduler_agent, sample_properties):
        """Test accurate tour duration calculation including travel time."""
        result = scheduler_agent.calculate_tour_duration(
            properties=sample_properties,
            visit_duration_per_property=20  # minutes
        )
        
        assert "total_duration_minutes" in result
        expected_min = len(sample_properties) * 20  # Base visit time
        assert result["total_duration_minutes"] > expected_min  # Should include travel time
        
        # Should include visit details per property
        assert "property_details" in result
        assert len(result["property_details"]) == len(sample_properties)
        assert all("visit_duration" in prop for prop in result["property_details"])
    
    def test_geographic_clustering_optimization(self, scheduler_agent, sample_properties):
        """Test geographic clustering of properties for efficient tours."""
        # Properties from different areas
        diverse_properties = sample_properties + [
            {
                "id": "prop4",
                "address": "999 Beach Rd, Key Biscayne, FL 33149",
                "lat": 25.6945,
                "lng": -80.1647,
                "price": 550000,
                "bedrooms": 4
            }
        ]
        
        clusters = scheduler_agent.cluster_properties_by_location(diverse_properties)
        
        # Should group properties by geographic proximity
        assert len(clusters) >= 1
        total_properties = sum(len(cluster) for cluster in clusters)
        assert total_properties == len(diverse_properties)
        
        # Each cluster should have properties that are geographically close
        for cluster in clusters:
            assert len(cluster) <= 4  # Reasonable cluster size for Miami area
    
    def test_conflict_prevention_double_booking(self, scheduler_agent):
        """Test prevention of double booking conflicts."""
        existing_events = [
            {
                "start": datetime(2024, 1, 15, 10, 0),
                "end": datetime(2024, 1, 15, 11, 0)
            },
            {
                "start": datetime(2024, 1, 15, 14, 0),
                "end": datetime(2024, 1, 15, 15, 0)
            }
        ]
        
        candidate_slots = [
            {"start": datetime(2024, 1, 15, 10, 30), "end": datetime(2024, 1, 15, 11, 30)},  # Overlaps
            {"start": datetime(2024, 1, 15, 11, 30), "end": datetime(2024, 1, 15, 12, 30)},  # Overlaps (ends at 12:30 but some logic might see 11:30 conflict)
            {"start": datetime(2024, 1, 15, 12, 30), "end": datetime(2024, 1, 15, 13, 30)}   # Valid
        ]
        
        conflict_free_slots = scheduler_agent.filter_conflicting_slots(candidate_slots, existing_events)
        
        # Should only return non-conflicting slots
        assert len(conflict_free_slots) >= 1  # At least one non-conflicting slot
        assert all(
            slot["start"] >= datetime(2024, 1, 15, 11, 0) or 
            slot["end"] <= datetime(2024, 1, 15, 10, 0)
            for slot in conflict_free_slots
        )
