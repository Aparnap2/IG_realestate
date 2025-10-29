"""
Standalone test script for industry configuration system.
This script tests the industry configs without requiring external dependencies.
"""

import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the industry configs module directly
from config.industry_configs import (
    IndustryConfigManager,
    IndustryConfig,
    IndustryType
)


def test_basic_functionality():
    """Test basic functionality of industry configuration system."""
    print("=== Testing Basic Functionality ===")
    
    # Test manager initialization
    manager = IndustryConfigManager()
    print("✓ IndustryConfigManager initialized successfully")
    
    # Test getting all industries
    industries = manager.get_all_industries()
    print(f"✓ Found {len(industries)} industries: {industries}")
    
    # Test getting specific configs
    for industry in industries:
        config = manager.get_config(industry)
        print(f"✓ {industry} config loaded - Conversion threshold: {config.conversion_threshold}")
    
    print()


def test_industry_detection():
    """Test industry detection functionality."""
    print("=== Testing Industry Detection ===")
    
    manager = IndustryConfigManager()
    
    test_cases = [
        {
            "message": "I'm looking for a 3-bedroom house in downtown",
            "extracted_info": {"property_type": "house", "bedrooms": 3},
            "expected": IndustryType.REAL_ESTATE.value
        },
        {
            "message": "I want to join a gym for weight loss",
            "extracted_info": {"fitness_goals": "weight_loss"},
            "expected": IndustryType.FITNESS.value
        },
        {
            "message": "I need a reservation for 8 people",
            "extracted_info": {"party_size": 8},
            "expected": IndustryType.RESTAURANT.value
        },
        {
            "message": "I need to book a hotel room for weekend",
            "extracted_info": {"room_type": "suite"},
            "expected": IndustryType.HOTEL.value
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        detected = manager.detect_industry_type(
            test_case["message"],
            test_case["extracted_info"]
        )
        
        match = detected == test_case["expected"]
        status = "✓" if match else "✗"
        
        print(f"Test {i}: {status} Expected {test_case['expected']}, got {detected}")
    
    print()


def test_configuration_updates():
    """Test configuration update functionality."""
    print("=== Testing Configuration Updates ===")
    
    manager = IndustryConfigManager()
    
    # Get original config
    original_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    original_threshold = original_config.conversion_threshold
    print(f"Original conversion threshold: {original_threshold}")
    
    # Update configuration
    updates = {
        "conversion_threshold": 0.75,
        "required_touches": 10
    }
    
    success = manager.update_config(IndustryType.REAL_ESTATE.value, updates)
    print(f"✓ Update successful: {success}")
    
    # Verify update
    updated_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"✓ Updated conversion threshold: {updated_config.conversion_threshold}")
    print(f"✓ Updated required touches: {updated_config.required_touches}")
    
    # Reset to defaults
    manager.reset_to_defaults(IndustryType.REAL_ESTATE.value)
    reset_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"✓ Reset conversion threshold: {reset_config.conversion_threshold}")
    
    print()


def test_configuration_validation():
    """Test configuration validation."""
    print("=== Testing Configuration Validation ===")
    
    manager = IndustryConfigManager()
    
    # Valid configuration
    valid_config = {
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
    
    is_valid = manager.validate_config("test_industry", valid_config)
    print(f"✓ Valid configuration validation: {is_valid}")
    
    # Invalid configuration (threshold > 1.0)
    invalid_config = valid_config.copy()
    invalid_config["conversion_threshold"] = 1.5
    
    is_invalid = manager.validate_config("test_industry", invalid_config)
    print(f"✓ Invalid configuration validation: {not is_invalid}")
    
    # Invalid configuration (scoring weights don't sum to 1.0)
    invalid_config2 = valid_config.copy()
    invalid_config2["scoring_weights"] = {"budget": 0.7, "location": 0.5}
    
    is_invalid2 = manager.validate_config("test_industry", invalid_config2)
    print(f"✓ Invalid scoring weights validation: {not is_invalid2}")
    
    print()


def test_industry_specific_configs():
    """Test industry-specific configuration details."""
    print("=== Testing Industry-Specific Configurations ===")
    
    manager = IndustryConfigManager()
    
    # Real Estate
    real_estate = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"✓ Real Estate - Conversion: {real_estate.conversion_threshold}, Required touches: {real_estate.required_touches}")
    print(f"  Scoring weights: {real_estate.scoring_weights}")
    print(f"  Value props: {real_estate.value_props}")
    
    # Fitness
    fitness = manager.get_config(IndustryType.FITNESS.value)
    print(f"✓ Fitness - Conversion: {fitness.conversion_threshold}, Required touches: {fitness.required_touches}")
    print(f"  Scoring weights: {fitness.scoring_weights}")
    print(f"  Value props: {fitness.value_props}")
    
    # Restaurant
    restaurant = manager.get_config(IndustryType.RESTAURANT.value)
    print(f"✓ Restaurant - Conversion: {restaurant.conversion_threshold}, Required touches: {restaurant.required_touches}")
    print(f"  Scoring weights: {restaurant.scoring_weights}")
    print(f"  Value props: {restaurant.value_props}")
    
    # Hotel
    hotel = manager.get_config(IndustryType.HOTEL.value)
    print(f"✓ Hotel - Conversion: {hotel.conversion_threshold}, Required touches: {hotel.required_touches}")
    print(f"  Scoring weights: {hotel.scoring_weights}")
    print(f"  Value props: {hotel.value_props}")
    
    print()


def test_file_operations():
    """Test file-based configuration operations."""
    print("=== Testing File Operations ===")
    
    import tempfile
    import json
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_file = f.name
        
        custom_configs = {
            "real_estate": {
                "conversion_threshold": 0.7,
                "required_touches": 9
            }
        }
        
        json.dump(custom_configs, f)
    
    try:
        # Create manager with custom config file
        manager = IndustryConfigManager(config_file)
        
        # Check that custom config was loaded
        config = manager.get_config(IndustryType.REAL_ESTATE.value)
        print(f"✓ Custom conversion threshold: {config.conversion_threshold}")
        print(f"✓ Custom required touches: {config.required_touches}")
        
        # Test saving configs
        save_success = manager.save_configs()
        print(f"✓ Save configs successful: {save_success}")
        
    finally:
        # Clean up
        if os.path.exists(config_file):
            os.remove(config_file)
    
    print()


def run_all_tests():
    """Run all tests."""
    print("Industry Configuration System - Standalone Tests")
    print("=" * 50)
    print()
    
    try:
        test_basic_functionality()
        test_industry_detection()
        test_configuration_updates()
        test_configuration_validation()
        test_industry_specific_configs()
        test_file_operations()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()