"""
Tests for the industry configuration system.
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from config.industry_configs import (
    IndustryConfigManager,
    IndustryConfig,
    IndustryType,
    get_industry_config_manager,
    get_industry_config,
    detect_industry
)


class TestIndustryConfig:
    """Test the IndustryConfig dataclass."""
    
    def test_industry_config_creation(self):
        """Test creating an IndustryConfig instance."""
        config = IndustryConfig(
            conversion_threshold=0.6,
            nurture_threshold=0.3,
            required_touches=8,
            scoring_weights={"budget": 0.25, "location": 0.20, "timeline": 0.15, "completeness": 0.15, "engagement": 0.25},
            value_props=["market_insights", "property_recommendations"],
            compliance_modules=["fair_housing"],
            nurture_cadence_days=[1, 3, 7],
            max_nurture_duration_days=60,
            booking_triggers=["high_score"],
            booking_windows_days=30,
            preferred_channels=["email", "phone"],
            channel_fallback_order=["email", "sms", "phone"]
        )
        
        assert config.conversion_threshold == 0.6
        assert config.nurture_threshold == 0.3
        assert config.required_touches == 8
        assert len(config.scoring_weights) == 5
        assert sum(config.scoring_weights.values()) == 1.0


class TestIndustryConfigManager:
    """Test the IndustryConfigManager class."""
    
    def test_default_configs_loaded(self):
        """Test that default configurations are loaded correctly."""
        manager = IndustryConfigManager()
        
        # Test all default industries are loaded
        industries = manager.get_all_industries()
        assert IndustryType.REAL_ESTATE.value in industries
        assert IndustryType.FITNESS.value in industries
        assert IndustryType.RESTAURANT.value in industries
        assert IndustryType.HOTEL.value in industries
        
        # Test specific config values
        real_estate_config = manager.get_config(IndustryType.REAL_ESTATE.value)
        assert real_estate_config.conversion_threshold == 0.6
        assert real_estate_config.nurture_threshold == 0.35
        assert real_estate_config.required_touches == 8
        assert "budget" in real_estate_config.scoring_weights
        assert "market_insights" in real_estate_config.value_props
        assert "fair_housing" in real_estate_config.compliance_modules
    
    def test_get_config_unknown_industry(self):
        """Test getting config for unknown industry defaults to real estate."""
        manager = IndustryConfigManager()
        
        config = manager.get_config("unknown_industry")
        assert config.conversion_threshold == 0.6  # Real estate default
    
    def test_detect_industry_real_estate(self):
        """Test industry detection for real estate."""
        manager = IndustryConfigManager()
        
        message = "I'm looking for a 3-bedroom house in the downtown area"
        extracted_info = {"property_type": "house", "bedrooms": 3}
        
        detected = manager.detect_industry_type(message, extracted_info)
        assert detected == IndustryType.REAL_ESTATE.value
    
    def test_detect_industry_fitness(self):
        """Test industry detection for fitness."""
        manager = IndustryConfigManager()
        
        message = "I want to join a gym and need a personal trainer"
        extracted_info = {"fitness_goals": "weight_loss", "experience_level": "beginner"}
        
        detected = manager.detect_industry_type(message, extracted_info)
        assert detected == IndustryType.FITNESS.value
    
    def test_detect_industry_restaurant(self):
        """Test industry detection for restaurant."""
        manager = IndustryConfigManager()
        
        message = "I need to make a reservation for 8 people for dinner"
        extracted_info = {"party_size": 8, "occasion": "birthday"}
        
        detected = manager.detect_industry_type(message, extracted_info)
        assert detected == IndustryType.RESTAURANT.value
    
    def test_detect_industry_hotel(self):
        """Test industry detection for hotel."""
        manager = IndustryConfigManager()
        
        message = "I need to book a room for next weekend, check-in Friday"
        extracted_info = {"room_type": "suite", "check_in": "2024-01-12"}
        
        detected = manager.detect_industry_type(message, extracted_info)
        assert detected == IndustryType.HOTEL.value
    
    def test_detect_industry_with_history(self):
        """Test industry detection with conversation history."""
        manager = IndustryConfigManager()
        
        message = "What are your membership options?"
        conversation_history = [
            {"content": "I'm interested in getting fit"},
            {"content": "Do you have yoga classes?"}
        ]
        
        detected = manager.detect_industry_type(message, {}, conversation_history)
        assert detected == IndustryType.FITNESS.value
    
    def test_detect_industry_fallback(self):
        """Test industry detection fallback to real estate."""
        manager = IndustryConfigManager()
        
        message = "I need some information about your services"
        extracted_info = {}
        
        detected = manager.detect_industry_type(message, extracted_info)
        assert detected == IndustryType.REAL_ESTATE.value
    
    def test_update_config_success(self):
        """Test successful configuration update."""
        manager = IndustryConfigManager()
        
        updates = {
            "conversion_threshold": 0.7,
            "required_touches": 10
        }
        
        result = manager.update_config(IndustryType.REAL_ESTATE.value, updates)
        assert result is True
        
        updated_config = manager.get_config(IndustryType.REAL_ESTATE.value)
        assert updated_config.conversion_threshold == 0.7
        assert updated_config.required_touches == 10
    
    def test_update_config_invalid(self):
        """Test invalid configuration update."""
        manager = IndustryConfigManager()
        
        updates = {
            "conversion_threshold": 1.5,  # Invalid > 1.0
            "required_touches": -1  # Invalid negative
        }
        
        result = manager.update_config(IndustryType.REAL_ESTATE.value, updates)
        assert result is False
    
    def test_validate_config_success(self):
        """Test successful configuration validation."""
        manager = IndustryConfigManager()
        
        config = {
            "conversion_threshold": 0.6,
            "nurture_threshold": 0.3,
            "required_touches": 8,
            "scoring_weights": {"budget": 0.5, "location": 0.5},
            "value_props": ["test_prop"],
            "compliance_modules": ["test_compliance"],
            "nurture_cadence_days": [1, 3, 7],
            "max_nurture_duration_days": 60,
            "booking_triggers": ["test_trigger"],
            "booking_windows_days": 30,
            "preferred_channels": ["email"],
            "channel_fallback_order": ["email"]
        }
        
        result = manager.validate_config("test_industry", config)
        assert result is True
    
    def test_validate_config_missing_field(self):
        """Test configuration validation with missing field."""
        manager = IndustryConfigManager()
        
        config = {
            "conversion_threshold": 0.6,
            "nurture_threshold": 0.3,
            # Missing required_touches
            "scoring_weights": {"budget": 0.5, "location": 0.5},
            "value_props": ["test_prop"],
            "compliance_modules": ["test_compliance"],
            "nurture_cadence_days": [1, 3, 7],
            "max_nurture_duration_days": 60,
            "booking_triggers": ["test_trigger"],
            "booking_windows_days": 30,
            "preferred_channels": ["email"],
            "channel_fallback_order": ["email"]
        }
        
        result = manager.validate_config("test_industry", config)
        assert result is False
    
    def test_validate_config_invalid_thresholds(self):
        """Test configuration validation with invalid thresholds."""
        manager = IndustryConfigManager()
        
        config = {
            "conversion_threshold": 1.5,  # Invalid > 1.0
            "nurture_threshold": 0.3,
            "required_touches": 8,
            "scoring_weights": {"budget": 0.5, "location": 0.5},
            "value_props": ["test_prop"],
            "compliance_modules": ["test_compliance"],
            "nurture_cadence_days": [1, 3, 7],
            "max_nurture_duration_days": 60,
            "booking_triggers": ["test_trigger"],
            "booking_windows_days": 30,
            "preferred_channels": ["email"],
            "channel_fallback_order": ["email"]
        }
        
        result = manager.validate_config("test_industry", config)
        assert result is False
    
    def test_validate_config_scoring_weights_sum(self):
        """Test configuration validation with scoring weights not summing to 1.0."""
        manager = IndustryConfigManager()
        
        config = {
            "conversion_threshold": 0.6,
            "nurture_threshold": 0.3,
            "required_touches": 8,
            "scoring_weights": {"budget": 0.7, "location": 0.5},  # Sum = 1.2
            "value_props": ["test_prop"],
            "compliance_modules": ["test_compliance"],
            "nurture_cadence_days": [1, 3, 7],
            "max_nurture_duration_days": 60,
            "booking_triggers": ["test_trigger"],
            "booking_windows_days": 30,
            "preferred_channels": ["email"],
            "channel_fallback_order": ["email"]
        }
        
        result = manager.validate_config("test_industry", config)
        assert result is False
    
    def test_save_and_load_configs(self):
        """Test saving and loading configurations to/from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_file = f.name
        
        try:
            # Create manager with custom config file
            manager = IndustryConfigManager(config_file)
            
            # Update a config
            manager.update_config(IndustryType.REAL_ESTATE.value, {
                "conversion_threshold": 0.8,
                "required_touches": 12
            })
            
            # Save configs
            result = manager.save_configs()
            assert result is True
            
            # Create new manager to load from file
            manager2 = IndustryConfigManager(config_file)
            
            # Check that the updated config was loaded
            loaded_config = manager2.get_config(IndustryType.REAL_ESTATE.value)
            assert loaded_config.conversion_threshold == 0.8
            assert loaded_config.required_touches == 12
            
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)
    
    def test_reset_to_defaults(self):
        """Test resetting configurations to defaults."""
        manager = IndustryConfigManager()
        
        # Update a config
        manager.update_config(IndustryType.REAL_ESTATE.value, {
            "conversion_threshold": 0.8
        })
        
        # Verify it's updated
        assert manager.get_config(IndustryType.REAL_ESTATE.value).conversion_threshold == 0.8
        
        # Reset to defaults
        manager.reset_to_defaults(IndustryType.REAL_ESTATE.value)
        
        # Verify it's back to default
        assert manager.get_config(IndustryType.REAL_ESTATE.value).conversion_threshold == 0.6
    
    def test_reset_all_to_defaults(self):
        """Test resetting all configurations to defaults."""
        manager = IndustryConfigManager()
        
        # Update multiple configs
        manager.update_config(IndustryType.REAL_ESTATE.value, {
            "conversion_threshold": 0.8
        })
        manager.update_config(IndustryType.FITNESS.value, {
            "conversion_threshold": 0.9
        })
        
        # Reset all
        manager.reset_to_defaults()
        
        # Verify all are back to defaults
        assert manager.get_config(IndustryType.REAL_ESTATE.value).conversion_threshold == 0.6
        assert manager.get_config(IndustryType.FITNESS.value).conversion_threshold == 0.5
    
    @patch.dict(os.environ, {
        'INDUSTRY_REAL_ESTATE_CONVERSION_THRESHOLD': '0.75',
        'INDUSTRY_FITNESS_REQUIRED_TOUCHES': '10',
        'INDUSTRY_RESTAURANT_VALUE_PROPS': '["special_menu", "private_dining"]'
    })
    def test_environment_overrides(self):
        """Test environment variable overrides."""
        manager = IndustryConfigManager()
        
        # Check real estate override
        real_estate_config = manager.get_config(IndustryType.REAL_ESTATE.value)
        assert real_estate_config.conversion_threshold == 0.75
        
        # Check fitness override
        fitness_config = manager.get_config(IndustryType.FITNESS.value)
        assert fitness_config.required_touches == 10
        
        # Check restaurant override
        restaurant_config = manager.get_config(IndustryType.RESTAURANT.value)
        assert "special_menu" in restaurant_config.value_props
        assert "private_dining" in restaurant_config.value_props


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_industry_config_manager_singleton(self):
        """Test that get_industry_config_manager returns singleton."""
        manager1 = get_industry_config_manager()
        manager2 = get_industry_config_manager()
        
        assert manager1 is manager2
    
    def test_get_industry_config(self):
        """Test get_industry_config convenience function."""
        config = get_industry_config(IndustryType.REAL_ESTATE.value)
        
        assert isinstance(config, IndustryConfig)
        assert config.conversion_threshold == 0.6
    
    def test_detect_industry_function(self):
        """Test detect_industry convenience function."""
        message = "I need to book a hotel room for my vacation"
        extracted_info = {"room_type": "suite"}
        
        detected = detect_industry(message, extracted_info)
        
        assert detected == IndustryType.HOTEL.value


class TestIndustrySpecificConfigurations:
    """Test industry-specific configuration details."""
    
    def test_real_estate_config(self):
        """Test real estate specific configuration."""
        manager = IndustryConfigManager()
        config = manager.get_config(IndustryType.REAL_ESTATE.value)
        
        # Test thresholds
        assert config.conversion_threshold == 0.6
        assert config.nurture_threshold == 0.35
        assert config.required_touches == 8
        
        # Test scoring weights
        assert config.scoring_weights["budget"] == 0.25
        assert config.scoring_weights["location"] == 0.20
        assert config.scoring_weights["timeline"] == 0.15
        assert config.scoring_weights["property_type"] == 0.10
        assert config.scoring_weights["completeness"] == 0.15
        assert config.scoring_weights["engagement"] == 0.15
        
        # Test value props
        assert "market_insights" in config.value_props
        assert "property_recommendations" in config.value_props
        assert "investment_analysis" in config.value_props
        
        # Test compliance modules
        assert "fair_housing" in config.compliance_modules
        assert "disclosure_requirements" in config.compliance_modules
    
    def test_fitness_config(self):
        """Test fitness specific configuration."""
        manager = IndustryConfigManager()
        config = manager.get_config(IndustryType.FITNESS.value)
        
        # Test thresholds
        assert config.conversion_threshold == 0.5
        assert config.nurture_threshold == 0.3
        assert config.required_touches == 6
        
        # Test scoring weights
        assert config.scoring_weights["goals"] == 0.25
        assert config.scoring_weights["timeline"] == 0.20
        assert config.scoring_weights["budget"] == 0.15
        assert config.scoring_weights["experience"] == 0.15
        assert config.scoring_weights["availability"] == 0.15
        assert config.scoring_weights["engagement"] == 0.10
        
        # Test value props
        assert "class_schedules" in config.value_props
        assert "facility_tours" in config.value_props
        assert "progress_tracking" in config.value_props
        
        # Test compliance modules
        assert "health_safety" in config.compliance_modules
        assert "liability_waivers" in config.compliance_modules
    
    def test_restaurant_config(self):
        """Test restaurant specific configuration."""
        manager = IndustryConfigManager()
        config = manager.get_config(IndustryType.RESTAURANT.value)
        
        # Test thresholds
        assert config.conversion_threshold == 0.55
        assert config.nurture_threshold == 0.35
        assert config.required_touches == 7
        
        # Test scoring weights
        assert config.scoring_weights["party_size"] == 0.25
        assert config.scoring_weights["occasion"] == 0.20
        assert config.scoring_weights["budget"] == 0.15
        assert config.scoring_weights["cuisine"] == 0.15
        assert config.scoring_weights["timing"] == 0.15
        assert config.scoring_weights["engagement"] == 0.10
        
        # Test value props
        assert "menu_highlights" in config.value_props
        assert "chef_profile" in config.value_props
        assert "event_packages" in config.value_props
        
        # Test compliance modules
        assert "food_safety" in config.compliance_modules
        assert "capacity_limits" in config.compliance_modules
    
    def test_hotel_config(self):
        """Test hotel specific configuration."""
        manager = IndustryConfigManager()
        config = manager.get_config(IndustryType.HOTEL.value)
        
        # Test thresholds
        assert config.conversion_threshold == 0.65
        assert config.nurture_threshold == 0.4
        assert config.required_touches == 10
        
        # Test scoring weights
        assert config.scoring_weights["room_type"] == 0.25
        assert config.scoring_weights["dates"] == 0.20
        assert config.scoring_weights["budget"] == 0.15
        assert config.scoring_weights["amenities"] == 0.15
        assert config.scoring_weights["group_size"] == 0.15
        assert config.scoring_weights["engagement"] == 0.10
        
        # Test value props
        assert "room_features" in config.value_props
        assert "amenities" in config.value_props
        assert "event_packages" in config.value_props
        
        # Test compliance modules
        assert "hospitality_standards" in config.compliance_modules
        assert "accessibility" in config.compliance_modules


if __name__ == "__main__":
    pytest.main([__file__])