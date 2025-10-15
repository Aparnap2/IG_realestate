"""
Test Analytics API Endpoints

Tests the analytics API endpoints to ensure they provide
proper attribution by agent action and funnel metrics.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json
from datetime import datetime, timedelta

# Import the main app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


class TestAnalyticsAPI:
    """Test analytics API endpoints."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_get_lead_attribution_endpoint(self):
        """Test the lead attribution endpoint."""
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
            response = self.client.get("/api/analytics/lead/test_lead_123")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify attribution structure
            assert "lead_id" in data
            assert "attribution_score" in data
            assert "journey_stages" in data
            assert "agent_contributions" in data
            assert "conversion_events" in data
            assert "total_interactions" in data
            
            # Verify data content
            assert data["lead_id"] == "test_lead_123"
            assert data["attribution_score"] > 0
            assert len(data["journey_stages"]) > 0
            assert len(data["agent_contributions"]) > 0
            assert data["total_interactions"] == 3
            
            # Verify agent contributions include router, qualifier, scheduler
            contributions = data["agent_contributions"]
            assert "router" in contributions
            assert "qualifier" in contributions
            assert "scheduler" in contributions
    
    def test_get_agent_performance_endpoint(self):
        """Test the agent performance endpoint."""
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
            response = self.client.get("/api/analytics/agents")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify performance structure
            assert "analysis_period" in data
            assert "agent_performance" in data
            assert "ranked_agents" in data
            assert "total_events_analyzed" in data
            
            # Verify agent metrics
            performance = data["agent_performance"]
            assert "qualifier" in performance
            assert "scheduler" in performance
            
            qualifier_metrics = performance["qualifier"]
            assert qualifier_metrics["total_actions"] == 2
            assert qualifier_metrics["unique_leads"] == 2
            assert qualifier_metrics["success_rate"] == 1.0
            assert "conversion_rate" in qualifier_metrics
            assert "avg_response_time" in qualifier_metrics
    
    def test_get_inventory_performance_endpoint(self):
        """Test the inventory performance endpoint."""
        # Mock properties
        mock_properties = [
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
        
        with patch('utils.supabase_client.supabase') as mock_supabase, \
             patch('utils.analytics.query_audit_events', return_value=mock_qualification_events):
            
            mock_supabase.table.return_value.select.return_value.execute.return_value = Mock(
                data=mock_properties
            )
            
            response = self.client.get("/api/analytics/inventory")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify inventory structure
            assert "total_properties" in data
            assert "total_qualified_leads" in data
            assert "top_performing_properties" in data
            assert "location_performance" in data
            assert "property_type_performance" in data
            
            # Verify data content
            assert data["total_properties"] == 2
            assert data["total_qualified_leads"] == 2
            assert len(data["top_performing_properties"]) > 0
    
    def test_get_conversion_funnel_endpoint(self):
        """Test the conversion funnel endpoint."""
        mock_events = [
            {"entity_id": "lead_1", "event_type": "instagram_message_received"},
            {"entity_id": "lead_1", "event_type": "lead_qualified"},
            {"entity_id": "lead_1", "event_type": "tour_scheduled"},
            {"entity_id": "lead_2", "event_type": "instagram_message_received"},
            {"entity_id": "lead_2", "event_type": "lead_qualified"},
            {"entity_id": "lead_3", "event_type": "instagram_message_received"}
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            response = self.client.get("/api/analytics/funnel")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify funnel structure
            assert "funnel_metrics" in data
            assert "overall_conversion_rate" in data
            assert "total_leads_analyzed" in data
            
            # Verify funnel metrics
            metrics = data["funnel_metrics"]
            assert "leads_captured" in metrics
            assert "leads_qualified" in metrics
            assert "tours_scheduled" in metrics
            
            # Check conversion rates
            assert metrics["leads_captured"]["count"] == 3
            assert metrics["leads_qualified"]["count"] == 2
            assert metrics["tours_scheduled"]["count"] == 1
            
            # Verify conversion percentages
            assert metrics["leads_captured"]["percentage"] == 100.0
            assert metrics["leads_qualified"]["percentage"] > 0
            assert metrics["tours_scheduled"]["percentage"] > 0
    
    def test_get_roi_metrics_endpoint(self):
        """Test the ROI metrics endpoint."""
        mock_events = [
            {
                "entity_id": "lead_1",
                "event_type": "deal_closed",
                "payload": {"deal_value": 20000, "property_value": 400000}
            },
            {
                "entity_id": "lead_2", 
                "event_type": "deal_closed",
                "payload": {"deal_value": 15000, "property_value": 350000}
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            response = self.client.get("/api/analytics/roi?operational_cost=5000")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify ROI structure
            assert "total_revenue" in data
            assert "total_potential_revenue" in data
            assert "total_costs" in data
            assert "roi_percentage" in data
            assert "roi_ratio" in data
            assert "deals_closed" in data
            assert "operational_cost" in data
            
            # Verify data content
            assert data["total_revenue"] == 35000  # 20000 + 15000
            assert data["total_potential_revenue"] == 750000  # 400000 + 350000
            assert data["operational_cost"] == 5000
            assert data["deals_closed"] == 2
            assert data["roi_ratio"] > 0  # Should be profitable
    
    def test_analytics_endpoint_error_handling(self):
        """Test analytics endpoint error handling."""
        with patch('utils.analytics.query_audit_events', side_effect=Exception("Database error")):
            response = self.client.get("/api/analytics/lead/error_lead")
            
            assert response.status_code == 200
            data = response.json()
            assert "error" in data
            assert "lead_id" in data
            assert data["attribution_score"] == 0
    
    def test_analytics_endpoint_with_custom_time_window(self):
        """Test analytics endpoints with custom time windows."""
        mock_events = [
            {
                "event_type": "instagram_message_received",
                "timestamp": datetime.now().isoformat(),
                "agent_type": "router"
            }
        ]
        
        with patch('utils.analytics.query_audit_events', return_value=mock_events):
            # Test with custom days parameter
            response = self.client.get("/api/analytics/lead/test_lead?days=60")
            
            assert response.status_code == 200
            data = response.json()
            assert "lead_id" in data
            assert "total_interactions" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])