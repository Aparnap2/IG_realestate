"""
Tests for qualifier_utils.py - Budget Reconciliation & Multi-Step Reasoning
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from tools.qualifier_utils import (
    reconcile_budget_mismatch,
    _analyze_inventory_by_bedrooms,
    _has_premium_features,
    _get_market_timing_insights,
    _find_nearby_location_alternatives,
    _generate_reconciliation_recommendation,
    _format_reconciliation_message,
    _build_fallback_options,
    calculate_temporal_qualification_adjustments
)


class TestReconcileBudgetMismatch:
    """Test the main reconcile_budget_mismatch function."""
    
    def test_exact_match_available(self):
        """Test when exact matches are available within budget."""
        inventory = [
            {"bedrooms": 3, "price": 400000, "location": "Miami"},
            {"bedrooms": 3, "price": 450000, "location": "Miami"},
            {"bedrooms": 2, "price": 350000, "location": "Miami"}
        ]
        
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=500000,
            inventory=inventory,
            location="Miami"
        )
        
        assert result["has_exact_match"] is True
        assert result["exact_matches"] == 2
        assert result["recommendation"] == "show_exact_matches"
        assert "Great news" in result["message"]
        assert result["alternatives"] == []
    
    def test_no_exact_match_with_alternatives(self):
        """Test when no exact matches but alternatives are available."""
        inventory = [
            {"bedrooms": 2, "price": 400000, "location": "Miami", "amenities": {"pool": True, "gym": True, "concierge": True}},
            {"bedrooms": 3, "price": 550000, "location": "Miami"}  # 10% over budget
        ]
        
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=500000,
            inventory=inventory,
            location="Miami"
        )
        
        assert result["has_exact_match"] is False
        assert result["exact_matches"] == 0
        assert len(result["alternatives"]) > 0
        assert result["recommendation"] in ["premium_alternative", "stretch_budget"]
    
    def test_no_alternatives_fallback(self):
        """Test when no alternatives are available and fallback is needed."""
        inventory = [
            {"bedrooms": 1, "price": 600000, "location": "Miami"}  # Way over budget
        ]
        
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=500000,
            inventory=inventory,
            location="Miami"
        )
        
        assert result["has_exact_match"] is False
        assert result["exact_matches"] == 0
        assert len(result["alternatives"]) > 0  # Should have fallback options
        assert result["recommendation"] == "stretch_budget"
    
    def test_empty_inventory(self):
        """Test with empty inventory."""
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=500000,
            inventory=[],
            location="Miami"
        )
        
        assert result["has_exact_match"] is False
        assert result["exact_matches"] == 0
        assert result["alternatives"] == []
        assert result["recommendation"] == "expand_search"
    
    @patch('tools.qualifier_utils.audit_log_event')
    def test_error_handling(self, mock_audit):
        """Test error handling in reconcile_budget_mismatch."""
        # Pass invalid inventory to trigger an error
        result = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=500000,
            inventory=None,  # This should cause an error
            location="Miami"
        )
        
        assert result["has_exact_match"] is False
        assert result["recommendation"] == "manual_review"
        assert "error" in result["reasoning"].lower()
        mock_audit.assert_called()


class TestAnalyzeInventoryByBedrooms:
    """Test the _analyze_inventory_by_bedrooms helper function."""
    
    def test_basic_analysis(self):
        """Test basic inventory analysis."""
        inventory = [
            {"bedrooms": 2, "price": 300000},
            {"bedrooms": 3, "price": 400000},
            {"bedrooms": 2, "price": 350000},
            {"bedrooms": 3, "price": 450000},
            {"bedrooms": 4, "price": 550000}
        ]
        
        result = _analyze_inventory_by_bedrooms(inventory, budget=400000)
        
        assert result["total_properties"] == 5
        assert result["within_budget"] == 3  # 2BR at 300k, 2BR at 350k, 3BR at 400k
        assert 2 in result["by_bedrooms"]
        assert 3 in result["by_bedrooms"]
        assert 4 in result["by_bedrooms"]
        
        # Check 2BR analysis
        assert result["by_bedrooms"][2]["count"] == 2
        assert result["by_bedrooms"][2]["within_budget"] == 2
        assert result["by_bedrooms"][2]["avg_price"] == 325000
        
        # Check 3BR analysis
        assert result["by_bedrooms"][3]["count"] == 2
        assert result["by_bedrooms"][3]["within_budget"] == 1
        assert result["by_bedrooms"][3]["avg_price"] == 425000
    
    def test_empty_inventory_analysis(self):
        """Test analysis with empty inventory."""
        result = _analyze_inventory_by_bedrooms([], budget=500000)
        
        assert result["total_properties"] == 0
        assert result["within_budget"] == 0
        assert result["by_bedrooms"] == {}


class TestHasPremiumFeatures:
    """Test the _has_premium_features helper function."""
    
    def test_property_with_premium_features(self):
        """Test property with multiple premium features."""
        property_data = {
            "amenities": {
                "pool": True,
                "gym": True,
                "concierge": True
            },
            "details": {
                "year_built": 2021,
                "floor": 12,
                "sqft": 1300
            }
        }
        
        result = _has_premium_features(property_data)
        assert result is True
    
    def test_property_with_few_premium_features(self):
        """Test property with only 1-2 premium features."""
        property_data = {
            "amenities": {
                "pool": True,
                "gym": False,
                "concierge": False
            },
            "details": {
                "year_built": 2019,
                "floor": 5,
                "sqft": 1000
            }
        }
        
        result = _has_premium_features(property_data)
        assert result is False
    
    def test_property_without_premium_features(self):
        """Test property with no premium features."""
        property_data = {
            "amenities": {
                "pool": False,
                "gym": False,
                "concierge": False
            },
            "details": {
                "year_built": 2015,
                "floor": 3,
                "sqft": 800
            }
        }
        
        result = _has_premium_features(property_data)
        assert result is False


class TestMarketTimingInsights:
    """Test the _get_market_timing_insights helper function."""
    
    @patch('tools.qualifier_utils.supabase')
    def test_market_overpriced(self, mock_supabase):
        """Test when market is significantly over budget."""
        # Mock recent sales data
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
            data=[
                {"price": 600000, "created_at": "2023-10-01"},
                {"price": 620000, "created_at": "2023-10-05"},
                {"price": 610000, "created_at": "2023-10-10"}
            ]
        )
        
        result = _get_market_timing_insights("Miami", 3, 500000)
        
        assert result["should_wait"] is True
        assert "timeline" in result
        assert "message" in result
        assert "610,000" in result["message"]
    
    @patch('tools.qualifier_utils.supabase')
    def test_market_within_budget(self, mock_supabase):
        """Test when market is within budget."""
        # Mock recent sales data
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
            data=[
                {"price": 480000, "created_at": "2023-10-01"},
                {"price": 490000, "created_at": "2023-10-05"},
                {"price": 470000, "created_at": "2023-10-10"}
            ]
        )
        
        result = _get_market_timing_insights("Miami", 3, 500000)
        
        assert result["should_wait"] is False
    
    @patch('tools.qualifier_utils.supabase')
    def test_insufficient_data(self, mock_supabase):
        """Test when there's insufficient market data."""
        # Mock insufficient data
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
            data=[
                {"price": 600000, "created_at": "2023-10-01"}
            ]
        )
        
        result = _get_market_timing_insights("Miami", 3, 500000)
        
        assert result["should_wait"] is False
    
    @patch('tools.qualifier_utils.supabase')
    def test_database_error(self, mock_supabase):
        """Test handling of database errors."""
        # Mock database error
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.side_effect = Exception("DB error")
        
        result = _get_market_timing_insights("Miami", 3, 500000)
        
        assert result["should_wait"] is False


class TestNearbyLocationAlternatives:
    """Test the _find_nearby_location_alternatives helper function."""
    
    @patch('tools.qualifier_utils.supabase')
    def test_miami_alternatives(self, mock_supabase):
        """Test finding alternatives near Miami."""
        # Mock available properties in alternative locations
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = MagicMock(
            data=[
                {"price": 450000, "bedrooms": 3},
                {"price": 480000, "bedrooms": 3}
            ]
        )
        
        result = _find_nearby_location_alternatives("Miami", 3, 500000)
        
        assert len(result) > 0
        assert any(loc in ["Coral Gables", "Aventura", "Doral"] for loc in result)
    
    @patch('tools.qualifier_utils.supabase')
    def test_no_alternatives(self, mock_supabase):
        """Test when no alternatives are available."""
        # Mock no available properties
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        result = _find_nearby_location_alternatives("Miami", 3, 500000)
        
        assert len(result) == 0
    
    @patch('tools.qualifier_utils.supabase')
    def test_unknown_location(self, mock_supabase):
        """Test when location is not in the mapping."""
        result = _find_nearby_location_alternatives("Unknown City", 3, 500000)
        
        assert len(result) == 0
    
    @patch('tools.qualifier_utils.supabase')
    def test_database_error(self, mock_supabase):
        """Test handling of database errors."""
        # Mock database error
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.side_effect = Exception("DB error")
        
        result = _find_nearby_location_alternatives("Miami", 3, 500000)
        
        assert len(result) == 0


class TestGenerateReconciliationRecommendation:
    """Test the _generate_reconciliation_recommendation helper function."""
    
    def test_priority_ordering(self):
        """Test that options are prioritized correctly."""
        options = [
            {"type": "market_timing"},
            {"type": "premium_alternative"},
            {"type": "location_expansion"},
            {"type": "stretch_budget"}
        ]
        
        result = _generate_reconciliation_recommendation(options, 3, 500000)
        
        assert result == "premium_alternative"  # Highest priority
    
    def test_empty_options(self):
        """Test with empty options list."""
        result = _generate_reconciliation_recommendation([], 3, 500000)
        
        assert result == "expand_search"
    
    def test_unknown_option_type(self):
        """Test with unknown option type."""
        options = [{"type": "unknown_type"}]
        
        result = _generate_reconciliation_recommendation(options, 3, 500000)
        
        assert result == "unknown_type"


class TestFormatReconciliationMessage:
    """Test the _format_reconciliation_message helper function."""
    
    def test_format_premium_alternative(self):
        """Test formatting premium alternative message."""
        options = [
            {
                "type": "premium_alternative",
                "count": 3,
                "bedrooms": 2
            }
        ]
        
        result = _format_reconciliation_message(options, 3, 500000)
        
        assert "looking for 3BR within $500,000" in result
        assert "premium 2BR properties" in result
        assert "high-end amenities" in result
    
    def test_format_stretch_budget(self):
        """Test formatting stretch budget message."""
        options = [
            {
                "type": "stretch_budget",
                "count": 2,
                "avg_overage": 25000
            }
        ]
        
        result = _format_reconciliation_message(options, 3, 500000)
        
        assert "looking for 3BR within $500,000" in result
        assert "3BR properties for about $25,000" in result
        assert "worth the investment" in result
    
    def test_format_location_expansion(self):
        """Test formatting location expansion message."""
        options = [
            {
                "type": "location_expansion",
                "locations": ["Coral Gables", "Aventura"]
            }
        ]
        
        result = _format_reconciliation_message(options, 3, 500000)
        
        assert "looking for 3BR within $500,000" in result
        assert "Coral Gables, Aventura" in result
        assert "nearby areas" in result
    
    def test_format_market_timing(self):
        """Test formatting market timing message."""
        options = [
            {
                "type": "market_timing",
                "timeline": "3-6 months"
            }
        ]
        
        result = _format_reconciliation_message(options, 3, 500000)
        
        assert "looking for 3BR within $500,000" in result
        assert "3-6 months" in result
        assert "Market timing suggests" in result
    
    def test_empty_options(self):
        """Test formatting with empty options."""
        result = _format_reconciliation_message([], 3, 500000)
        
        assert "don't see 3BR properties within your $500,000 budget" in result
        assert "explore some alternatives" in result


class TestBuildFallbackOptions:
    """Test the _build_fallback_options helper function."""
    
    def test_with_inventory(self):
        """Test building fallback options with available inventory."""
        inventory = [
            {"bedrooms": 2, "price": 600000},
            {"bedrooms": 1, "price": 400000}
        ]
        
        result = _build_fallback_options(inventory, 3, 500000)
        
        assert len(result) > 0
        assert result[0]["type"] == "stretch_budget"
        assert result[0]["bedrooms"] == 1  # Cheapest option (1BR at $400k)
        assert result[0]["avg_overage"] == 0  # Within budget
    
    def test_with_smaller_units(self):
        """Test building fallback options with smaller units available."""
        inventory = [
            {"bedrooms": 2, "price": 600000},
            {"bedrooms": 2, "price": 550000},
            {"bedrooms": 1, "price": 400000}
        ]
        
        result = _build_fallback_options(inventory, 3, 500000)
        
        # Should have both stretch_budget and premium_alternative options
        option_types = [opt["type"] for opt in result]
        assert "stretch_budget" in option_types
        assert "premium_alternative" in option_types
    
    def test_with_empty_inventory(self):
        """Test building fallback options with empty inventory."""
        result = _build_fallback_options([], 3, 500000)
        
        assert len(result) == 0
    
    def test_with_single_bedroom_request(self):
        """Test building fallback when requesting 1 bedroom (no smaller options)."""
        inventory = [
            {"bedrooms": 2, "price": 600000}
        ]
        
        result = _build_fallback_options(inventory, 1, 500000)
        
        # Should only have stretch_budget option since no smaller units
        assert len(result) == 1
        assert result[0]["type"] == "stretch_budget"


class TestCalculateTemporalQualificationAdjustments:
    """Test the calculate_temporal_qualification_adjustments function."""
    
    def test_re_engagement_adjustment(self):
        """Test adjustment for re-engagement after long absence."""
        lead_data = {
            "user_id": "test123",
            "last_interaction_at": (datetime.now() - timedelta(days=45)).isoformat()
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] > 0.5
        assert "Re-engaged after" in result["reasoning"]
        assert "+0.15" in result["adjustments"][0]
    
    def test_prior_showings_adjustment(self):
        """Test adjustment for multiple prior showings with higher budget."""
        lead_data = {
            "user_id": "test123",
            "prior_interests": [
                {"price": 600000},
                {"price": 650000},
                {"price": 700000}
            ],
            "budget": 500000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] > 0.5
        assert "Upsell potential" in result["reasoning"]
        assert "+0.2" in result["adjustments"][0]
    
    def test_escalating_engagement(self):
        """Test adjustment for escalating engagement."""
        lead_data = {
            "user_id": "test123",
            "engagement_trajectory": "escalating"
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] > 0.5
        assert "Escalating engagement" in result["reasoning"]
        assert "+0.1" in result["adjustments"][0]
    
    def test_cooling_engagement(self):
        """Test adjustment for cooling engagement."""
        lead_data = {
            "user_id": "test123",
            "engagement_trajectory": "cooling"
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] < 0.5
        assert "Cooling engagement" in result["reasoning"]
        assert "-0.1" in result["adjustments"][0]
    
    def test_high_value_lead(self):
        """Test adjustment for high-value lead."""
        lead_data = {
            "user_id": "test123",
            "budget": 600000
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] > 0.5
        assert "High-value lead" in result["reasoning"]
        assert "+0.15" in result["adjustments"][0]
    
    def test_immediate_timeline(self):
        """Test adjustment for immediate timeline."""
        lead_data = {
            "user_id": "test123",
            "timeline": "immediate"
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.5)
        
        assert result["adjusted_score"] > 0.5
        assert "Immediate timeline" in result["reasoning"]
        assert "+0.2" in result["adjustments"][0]
    
    def test_score_capping(self):
        """Test that score is capped at 1.0."""
        lead_data = {
            "user_id": "test123",
            "last_interaction_at": (datetime.now() - timedelta(days=45)).isoformat(),
            "prior_interests": [
                {"price": 600000},
                {"price": 650000},
                {"price": 700000}
            ],
            "budget": 500000,
            "engagement_trajectory": "escalating",
            "timeline": "immediate"
        }
        
        result = calculate_temporal_qualification_adjustments(lead_data, 0.7)
        
        assert result["adjusted_score"] <= 1.0
    
    @patch('tools.qualifier_utils.audit_log_event')
    def test_error_handling(self, mock_audit):
        """Test error handling in temporal adjustments."""
        # Pass invalid lead data to trigger an error
        result = calculate_temporal_qualification_adjustments(None, 0.5)
        
        assert result["adjusted_score"] == 0.5  # Should return base score
        assert result["total_adjustment"] == 0
        assert "error" in result["reasoning"].lower()
        mock_audit.assert_called()