"""
Test Analytics & Revenue Intelligence

Tests the revenue attribution and analytics functionality.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from utils.analytics import (
    calculate_lead_attribution,
    analyze_agent_performance,
    analyze_inventory_performance,
    generate_conversion_funnel_analysis,
    calculate_roi_metrics,
    _analyze_journey_stages,
    _calculate_agent_contributions,
    _identify_conversion_events
)


class TestLeadAttribution:
    """Test lead attribution calculation."""
    
    def test_calculate_lead_attribution_with_events(self, mock_audit):
        """Test lead attribution calculation with event history."""
        # Mock audit events for a lead journey
        mock_events = [
            {
                "event_type": "instagram_message_received",
                "timestamp": "2024-01-01T10:00:00Z",
                "agent_type": "router",
                "payload": {"message": "Looking for 3BR house"}
            },
            {
                "event_type": "lead_qualified",
                "timestamp": "2024-01-01T10:15:00Z",
                "agent_type": "qualifier",
                "payload": {"score": 0.8, "budget": 400000}
            },
            {
                "event_type": "tour_scheduled",
                "timestamp": "2024-01-01T11:00:00Z",
                "agent_type": "scheduler",
                "payload": {"tour_date": "2024-01-03T14:00:00Z"}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            attribution = calculate_lead_attribution("test_lead_123")
            
            assert attribution["lead_id"] == "test_lead_123"
            assert attribution["attribution_score"] > 0
            assert len(attribution["journey_stages"]) > 0
            assert len(attribution["agent_contributions"]) > 0
            assert attribution["total_interactions"] == 3
    
    def test_calculate_lead_attribution_no_events(self, mock_audit):
        """Test lead attribution with no event history."""
        with patch('utils.analytics.query_audit_events', return_value=[]):
            attribution = calculate_lead_attribution("test_lead_no_events")
            
            assert attribution["lead_id"] == "test_lead_no_events"
            assert attribution["attribution_score"] == 0
            assert len(attribution["journey_stages"]) == 0
            assert attribution["total_interactions"] == 0
    
    def test_calculate_lead_attribution_error_handling(self, mock_audit):
        """Test lead attribution error handling."""
        with patch('utils.analytics.query_audit_events', side_effect=Exception("Query error")):
            attribution = calculate_lead_attribution("test_lead_error")
            
            assert attribution["lead_id"] == "test_lead_error"
            assert attribution["attribution_score"] == 0
            assert "error" in attribution


class TestAgentPerformance:
    """Test agent performance analysis."""
    
    def test_analyze_agent_performance_with_data(self, mock_audit):
        """Test agent performance analysis with event data."""
        mock_events = [
            {
                "agent_type": "qualifier",
                "entity_id": "lead_1",
                "event_type": "lead_qualified",
                "payload": {"success": True, "score": 0.8}
            },
            {
                "agent_type": "qualifier",
                "entity_id": "lead_2",
                "event_type": "lead_qualified",
                "payload": {"success": True, "score": 0.7}
            },
            {
                "agent_type": "scheduler",
                "entity_id": "lead_1",
                "event_type": "tour_scheduled",
                "payload": {"success": True}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            performance = analyze_agent_performance(time_period_days=30)
            
            assert "agent_performance" in performance
            assert "qualifier" in performance["agent_performance"]
            assert "scheduler" in performance["agent_performance"]
            
            qualifier_metrics = performance["agent_performance"]["qualifier"]
            assert qualifier_metrics["total_actions"] == 2
            assert qualifier_metrics["unique_leads"] == 2
            assert qualifier_metrics["success_rate"] == 1.0
    
    def test_analyze_agent_performance_no_data(self, mock_audit):
        """Test agent performance analysis with no data."""
        with patch('utils.analytics.query_audit_events', return_value=[]):
            performance = analyze_agent_performance()
            
            assert "error" in performance
    
    def test_analyze_agent_performance_specific_agent(self, mock_audit):
        """Test agent performance analysis for specific agent type."""
        mock_events = [
            {
                "agent_type": "qualifier",
                "entity_id": "lead_1",
                "event_type": "lead_qualified",
                "payload": {"success": True}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            performance = analyze_agent_performance(agent_type="qualifier")
            
            assert "agent_performance" in performance
            assert "qualifier" in performance["agent_performance"]


class TestInventoryPerformance:
    """Test inventory performance analysis."""
    
    def test_analyze_inventory_performance_with_data(self, mock_supabase, mock_audit):
        """Test inventory performance analysis with property and lead data."""
        # Mock properties
        mock_supabase.table.return_value.select.return_value.execute.return_value = Mock(
            data=[
                {
                    "id": "prop_1",
                    "location": "Miami",
                    "property_type": "3BHK",
                    "price": 400000,
                    "amenities": {"pool": True},
                    "created_at": "2024-01-01T00:00:00Z"
                },
                {
                    "id": "prop_2",
                    "location": "Orlando",
                    "property_type": "2BHK",
                    "price": 300000,
                    "amenities": {"gym": True},
                    "created_at": "2024-01-02T00:00:00Z"
                }
            ]
        )
        
        # Mock qualification events
        mock_qualification_events = [
            {
                "payload": {
                    "location": "Miami",
                    "property_type": "3BHK",
                    "budget": 420000
                }
            },
            {
                "payload": {
                    "location": "Miami",
                    "property_type": "3BHK",
                    "budget": 380000
                }
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_qualification_events):
            performance = analyze_inventory_performance()
            
            assert "total_properties" in performance
            assert "total_qualified_leads" in performance
            assert "top_performing_properties" in performance
            assert "location_performance" in performance
            assert "property_type_performance" in performance
            
            assert performance["total_properties"] == 2
            assert performance["total_qualified_leads"] == 2
    
    def test_analyze_inventory_performance_no_data(self, mock_supabase, mock_audit):
        """Test inventory performance analysis with no data."""
        mock_supabase.table.return_value.select.return_value.execute.return_value = Mock(data=[])
        
        with patch('utils.analytics.query_audit_events', return_value=[]):
            performance = analyze_inventory_performance()
            
            assert performance["total_properties"] == 0
            assert performance["total_qualified_leads"] == 0


class TestConversionFunnel:
    """Test conversion funnel analysis."""
    
    def test_generate_conversion_funnel_analysis(self, mock_audit):
        """Test conversion funnel analysis with sample data."""
        mock_events = [
            {"entity_id": "lead_1", "event_type": "instagram_message_received"},
            {"entity_id": "lead_1", "event_type": "lead_qualified"},
            {"entity_id": "lead_1", "event_type": "tour_scheduled"},
            {"entity_id": "lead_2", "event_type": "instagram_message_received"},
            {"entity_id": "lead_2", "event_type": "lead_qualified"},
            {"entity_id": "lead_3", "event_type": "instagram_message_received"}
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            funnel = generate_conversion_funnel_analysis()
            
            assert "funnel_metrics" in funnel
            assert "overall_conversion_rate" in funnel
            assert "total_leads_analyzed" in funnel
            
            metrics = funnel["funnel_metrics"]
            assert "leads_captured" in metrics
            assert "leads_qualified" in metrics
            assert "tours_scheduled" in metrics
            
            # Check conversion rates
            assert metrics["leads_captured"]["count"] == 3
            assert metrics["leads_qualified"]["count"] == 2
            assert metrics["tours_scheduled"]["count"] == 1
    
    def test_generate_conversion_funnel_no_data(self, mock_audit):
        """Test conversion funnel analysis with no data."""
        with patch('utils.analytics.query_audit_events', return_value=[]):
            funnel = generate_conversion_funnel_analysis()
            
            assert funnel["total_leads_analyzed"] == 0
            assert "funnel_metrics" in funnel
            assert funnel["funnel_metrics"]["leads_captured"]["count"] == 0


class TestROIMetrics:
    """Test ROI metrics calculation."""
    
    def test_calculate_roi_metrics_with_conversions(self, mock_audit):
        """Test ROI calculation with conversion data."""
        mock_events = [
            {
                "entity_id": "lead_1",
                "event_type": "tour_scheduled",
                "payload": {"property_value": 400000}
            },
            {
                "entity_id": "lead_2", 
                "event_type": "tour_scheduled",
                "payload": {"property_value": 350000}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            roi = calculate_roi_metrics(
                operational_cost=5000,
                time_period_days=30
            )
            
            assert "total_potential_revenue" in roi
            assert "operational_cost" in roi
            assert "roi_ratio" in roi
            assert "conversion_count" in roi
            
            assert roi["total_potential_revenue"] == 750000  # 400k + 350k
            assert roi["operational_cost"] == 5000
            assert roi["conversion_count"] == 2
    
    def test_calculate_roi_metrics_no_conversions(self, mock_audit):
        """Test ROI calculation with no conversions."""
        with patch('utils.analytics.query_audit_events', return_value=[]):
            roi = calculate_roi_metrics(operational_cost=5000)
            
            assert roi["total_potential_revenue"] == 0
            assert roi["roi_ratio"] == -1.0  # Loss
            assert roi["conversion_count"] == 0


class TestAnalyticsUtilities:
    """Test analytics utility functions."""
    
    def test_analyze_journey_stages(self):
        """Test journey stage analysis."""
        events = [
            {"event_type": "instagram_message_received", "timestamp": "2024-01-01T10:00:00Z"},
            {"event_type": "lead_qualified", "timestamp": "2024-01-01T10:15:00Z"},
            {"event_type": "tour_scheduled", "timestamp": "2024-01-01T11:00:00Z"}
        ]
        
        stages = _analyze_journey_stages(events)
        
        assert len(stages) == 3
        assert stages[0]["stage"] == "initial_contact"
        assert stages[1]["stage"] == "qualification"
        assert stages[2]["stage"] == "scheduling"
        
        # Check time between stages
        assert stages[1]["time_from_previous"] == 15  # 15 minutes
        assert stages[2]["time_from_previous"] == 45  # 45 minutes
    
    def test_calculate_agent_contributions(self):
        """Test agent contribution calculation."""
        events = [
            {"agent_type": "router", "event_type": "message_routed"},
            {"agent_type": "qualifier", "event_type": "lead_qualified"},
            {"agent_type": "qualifier", "event_type": "lead_scored"},
            {"agent_type": "scheduler", "event_type": "tour_scheduled"}
        ]
        
        contributions = _calculate_agent_contributions(events)
        
        assert "router" in contributions
        assert "qualifier" in contributions
        assert "scheduler" in contributions
        
        assert contributions["qualifier"]["action_count"] == 2
        assert contributions["router"]["action_count"] == 1
        assert contributions["scheduler"]["action_count"] == 1
    
    def test_identify_conversion_events(self):
        """Test conversion event identification."""
        events = [
            {"event_type": "instagram_message_received"},
            {"event_type": "lead_qualified"},
            {"event_type": "tour_scheduled"},
            {"event_type": "property_viewed"},
            {"event_type": "offer_made"}
        ]
        
        conversions = _identify_conversion_events(events)
        
        # Should identify key conversion milestones
        assert "lead_qualified" in [e["event_type"] for e in conversions]
        assert "tour_scheduled" in [e["event_type"] for e in conversions]
        assert len(conversions) >= 2


class TestAnalyticsIntegration:
    """Test analytics integration with other components."""
    
    def test_integration_with_audit_system(self, mock_audit):
        """Test analytics integration with audit system."""
        # This tests that analytics can properly query audit events
        mock_events = [
            {
                "entity_id": "integration_test_lead",
                "agent_type": "qualifier",
                "event_type": "lead_qualified",
                "timestamp": datetime.now().isoformat(),
                "payload": {"score": 0.8}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            attribution = calculate_lead_attribution("integration_test_lead")
            
            assert attribution["lead_id"] == "integration_test_lead"
            assert attribution["total_interactions"] == 1
    
    def test_analytics_error_resilience(self, mock_audit):
        """Test analytics error handling and resilience."""
        # Test various error scenarios
        test_cases = [
            ("database_error", Exception("Database connection failed")),
            ("invalid_data", ValueError("Invalid event data")),
            ("timeout_error", TimeoutError("Query timeout"))
        ]
        
        for error_type, exception in test_cases:
            with patch('utils.analytics.query_audit_events', side_effect=exception):
                # All analytics functions should handle errors gracefully
                attribution = calculate_lead_attribution(f"test_{error_type}")
                performance = analyze_agent_performance()
                funnel = generate_conversion_funnel_analysis()
                
                # Should return error indicators, not crash
                assert "error" in attribution or attribution["attribution_score"] == 0
                assert "error" in performance or len(performance) == 0
                assert "error" in funnel or funnel["total_leads_analyzed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])