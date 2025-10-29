"""
Industry Configuration System Integration Examples

This file demonstrates how to use the industry configuration system
for multi-industry lead qualification and management.
"""

import json
import os
import sys
from typing import Dict, Any, List

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.industry_configs import (
    IndustryConfigManager,
    IndustryType,
    get_industry_config,
    detect_industry,
    get_industry_config_manager
)


def example_basic_usage():
    """Example of basic industry configuration usage."""
    print("=== Basic Industry Configuration Usage ===")
    
    # Get configuration for real estate
    real_estate_config = get_industry_config(IndustryType.REAL_ESTATE.value)
    print(f"Real Estate Conversion Threshold: {real_estate_config.conversion_threshold}")
    print(f"Real Estate Scoring Weights: {real_estate_config.scoring_weights}")
    print(f"Real Estate Value Props: {real_estate_config.value_props}")
    
    # Get configuration for fitness
    fitness_config = get_industry_config(IndustryType.FITNESS.value)
    print(f"Fitness Conversion Threshold: {fitness_config.conversion_threshold}")
    print(f"Fitness Required Touches: {fitness_config.required_touches}")
    print()


def example_industry_detection():
    """Example of automatic industry detection."""
    print("=== Industry Detection Examples ===")
    
    # Example messages and their expected industries
    test_cases = [
        {
            "message": "I'm looking for a 3-bedroom house in the downtown area with a budget of $500k",
            "extracted_info": {"property_type": "house", "bedrooms": 3, "budget": 500000},
            "expected": IndustryType.REAL_ESTATE.value
        },
        {
            "message": "I want to join a gym and need a personal trainer for weight loss",
            "extracted_info": {"fitness_goals": "weight_loss", "experience_level": "beginner"},
            "expected": IndustryType.FITNESS.value
        },
        {
            "message": "I need to make a reservation for 8 people for my birthday dinner",
            "extracted_info": {"party_size": 8, "occasion": "birthday"},
            "expected": IndustryType.RESTAURANT.value
        },
        {
            "message": "I need to book a suite for next weekend, checking in on Friday",
            "extracted_info": {"room_type": "suite", "check_in": "2024-01-12"},
            "expected": IndustryType.HOTEL.value
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        detected = detect_industry(
            test_case["message"],
            test_case["extracted_info"]
        )
        
        print(f"Test Case {i}:")
        print(f"  Message: {test_case['message']}")
        print(f"  Expected: {test_case['expected']}")
        print(f"  Detected: {detected}")
        print(f"  Match: {'✓' if detected == test_case['expected'] else '✗'}")
        print()


def example_configuration_updates():
    """Example of runtime configuration updates."""
    print("=== Runtime Configuration Updates ===")
    
    manager = get_industry_config_manager()
    
    # Get original real estate config
    original_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"Original conversion threshold: {original_config.conversion_threshold}")
    
    # Update configuration
    updates = {
        "conversion_threshold": 0.75,
        "required_touches": 10,
        "value_props": ["market_insights", "property_recommendations", "investment_analysis", "virtual_tours"]
    }
    
    success = manager.update_config(IndustryType.REAL_ESTATE.value, updates)
    print(f"Update successful: {success}")
    
    # Get updated config
    updated_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"Updated conversion threshold: {updated_config.conversion_threshold}")
    print(f"Updated required touches: {updated_config.required_touches}")
    print(f"Updated value props: {updated_config.value_props}")
    
    # Reset to defaults
    manager.reset_to_defaults(IndustryType.REAL_ESTATE.value)
    reset_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"Reset conversion threshold: {reset_config.conversion_threshold}")
    print()


def example_environment_overrides():
    """Example of environment variable overrides."""
    print("=== Environment Variable Overrides ===")
    
    # Set environment variables
    os.environ['INDUSTRY_REAL_ESTATE_CONVERSION_THRESHOLD'] = '0.8'
    os.environ['INDUSTRY_FITNESS_REQUIRED_TOUCHES'] = '12'
    os.environ['INDUSTRY_RESTAURANT_VALUE_PROPS'] = '["special_menu", "private_dining", "catering"]'
    
    # Create new manager to pick up env vars
    manager = IndustryConfigManager()
    
    # Check overridden values
    real_estate_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"Overridden real estate conversion threshold: {real_estate_config.conversion_threshold}")
    
    fitness_config = manager.get_config(IndustryType.FITNESS.value)
    print(f"Overridden fitness required touches: {fitness_config.required_touches}")
    
    restaurant_config = manager.get_config(IndustryType.RESTAURANT.value)
    print(f"Overridden restaurant value props: {restaurant_config.value_props}")
    
    # Clean up environment variables
    del os.environ['INDUSTRY_REAL_ESTATE_CONVERSION_THRESHOLD']
    del os.environ['INDUSTRY_FITNESS_REQUIRED_TOUCHES']
    del os.environ['INDUSTRY_RESTAURANT_VALUE_PROPS']
    print()


def example_file_based_configs():
    """Example of file-based configuration management."""
    print("=== File-Based Configuration Management ===")
    
    # Create a custom configuration file
    custom_config_file = "backend/config/custom_industry_configs.json"
    
    custom_configs = {
        "real_estate": {
            "conversion_threshold": 0.7,
            "required_touches": 9,
            "scoring_weights": {
                "budget": 0.30,
                "location": 0.25,
                "timeline": 0.15,
                "property_type": 0.10,
                "completeness": 0.10,
                "engagement": 0.10
            }
        },
        "fitness": {
            "conversion_threshold": 0.45,
            "nurture_threshold": 0.25,
            "required_touches": 5
        }
    }
    
    # Save custom configs to file
    with open(custom_config_file, 'w') as f:
        json.dump(custom_configs, f, indent=2)
    
    # Create manager with custom config file
    manager = IndustryConfigManager(custom_config_file)
    
    # Check that custom configs were loaded
    real_estate_config = manager.get_config(IndustryType.REAL_ESTATE.value)
    print(f"Custom real estate conversion threshold: {real_estate_config.conversion_threshold}")
    print(f"Custom real estate scoring weights: {real_estate_config.scoring_weights}")
    
    fitness_config = manager.get_config(IndustryType.FITNESS.value)
    print(f"Custom fitness conversion threshold: {fitness_config.conversion_threshold}")
    print(f"Custom fitness nurture threshold: {fitness_config.nurture_threshold}")
    
    # Clean up
    if os.path.exists(custom_config_file):
        os.remove(custom_config_file)
    print()


def example_lead_scoring_integration():
    """Example of integrating with lead scoring system."""
    print("=== Lead Scoring Integration ===")
    
    # Simulate lead data for different industries
    lead_examples = [
        {
            "industry": IndustryType.REAL_ESTATE.value,
            "data": {
                "budget": 0.8,
                "location": 0.9,
                "timeline": 0.7,
                "property_type": 0.6,
                "completeness": 0.8,
                "engagement": 0.7
            }
        },
        {
            "industry": IndustryType.FITNESS.value,
            "data": {
                "goals": 0.9,
                "timeline": 0.6,
                "budget": 0.7,
                "experience": 0.5,
                "availability": 0.8,
                "engagement": 0.9
            }
        }
    ]
    
    for lead in lead_examples:
        industry = lead["industry"]
        lead_data = lead["data"]
        
        # Get industry-specific configuration
        config = get_industry_config(industry)
        
        # Calculate weighted score
        score = sum(
            lead_data[factor] * weight 
            for factor, weight in config.scoring_weights.items()
        )
        
        # Determine qualification status
        if score >= config.conversion_threshold:
            status = "Ready for Conversion"
        elif score >= config.nurture_threshold:
            status = "Nurture Required"
        else:
            status = "Not Qualified"
        
        print(f"{industry.title()} Lead:")
        print(f"  Score: {score:.3f}")
        print(f"  Status: {status}")
        print(f"  Conversion Threshold: {config.conversion_threshold}")
        print(f"  Nurture Threshold: {config.nurture_threshold}")
        print()


def example_nurture_sequence_integration():
    """Example of integrating with nurture sequences."""
    print("=== Nurture Sequence Integration ===")
    
    # Get nurture configuration for each industry
    industries = [IndustryType.REAL_ESTATE.value, IndustryType.FITNESS.value, 
                  IndustryType.RESTAURANT.value, IndustryType.HOTEL.value]
    
    for industry in industries:
        config = get_industry_config(industry)
        
        print(f"{industry.title()} Nurture Configuration:")
        print(f"  Required Touches: {config.required_touches}")
        print(f"  Nurture Cadence (days): {config.nurture_cadence_days}")
        print(f"  Max Duration (days): {config.max_nurture_duration_days}")
        print(f"  Preferred Channels: {config.preferred_channels}")
        print()


def example_booking_integration():
    """Example of integrating with booking system."""
    print("=== Booking System Integration ===")
    
    # Simulate booking triggers for different industries
    booking_scenarios = [
        {
            "industry": IndustryType.REAL_ESTATE.value,
            "trigger": "high_score",
            "context": "Lead scored 0.85 with strong budget and location preferences"
        },
        {
            "industry": IndustryType.FITNESS.value,
            "trigger": "tour_request",
            "context": "Lead requested facility tour"
        },
        {
            "industry": IndustryType.RESTAURANT.value,
            "trigger": "reservation_request",
            "context": "Party of 6 for anniversary dinner"
        },
        {
            "industry": IndustryType.HOTEL.value,
            "trigger": "date_availability",
            "context": "Checking availability for weekend stay"
        }
    ]
    
    for scenario in booking_scenarios:
        industry = scenario["industry"]
        trigger = scenario["trigger"]
        context = scenario["context"]
        
        config = get_industry_config(industry)
        
        print(f"{industry.title()} Booking Scenario:")
        print(f"  Trigger: {trigger}")
        print(f"  Context: {context}")
        print(f"  Valid Triggers: {config.booking_triggers}")
        print(f"  Booking Window: {config.booking_windows_days} days")
        print(f"  Should Trigger Booking: {'✓' if trigger in config.booking_triggers else '✗'}")
        print()


def example_compliance_integration():
    """Example of compliance module integration."""
    print("=== Compliance Module Integration ===")
    
    for industry in [IndustryType.REAL_ESTATE.value, IndustryType.FITNESS.value, 
                     IndustryType.RESTAURANT.value, IndustryType.HOTEL.value]:
        config = get_industry_config(industry)
        
        print(f"{industry.title()} Compliance Requirements:")
        print(f"  Required Modules: {config.compliance_modules}")
        
        # Simulate compliance checks
        for module in config.compliance_modules:
            # In a real implementation, this would call the actual compliance module
            compliance_status = "✓ Passed" if module != "test_module" else "✗ Failed"
            print(f"    {module}: {compliance_status}")
        print()


def example_multi_channel_integration():
    """Example of multi-channel communication integration."""
    print("=== Multi-Channel Communication Integration ===")
    
    for industry in [IndustryType.REAL_ESTATE.value, IndustryType.FITNESS.value, 
                     IndustryType.RESTAURANT.value, IndustryType.HOTEL.value]:
        config = get_industry_config(industry)
        
        print(f"{industry.title()} Channel Configuration:")
        print(f"  Preferred Channels: {config.preferred_channels}")
        print(f"  Fallback Order: {config.channel_fallback_order}")
        
        # Simulate channel selection
        available_channels = ["email", "sms", "phone"]
        selected_channel = None
        
        for channel in config.preferred_channels:
            if channel in available_channels:
                selected_channel = channel
                break
        
        if not selected_channel:
            for channel in config.channel_fallback_order:
                if channel in available_channels:
                    selected_channel = channel
                    break
        
        print(f"  Selected Channel: {selected_channel or 'None available'}")
        print()


def run_all_examples():
    """Run all integration examples."""
    print("Industry Configuration System Integration Examples")
    print("=" * 60)
    print()
    
    example_basic_usage()
    example_industry_detection()
    example_configuration_updates()
    example_environment_overrides()
    example_file_based_configs()
    example_lead_scoring_integration()
    example_nurture_sequence_integration()
    example_booking_integration()
    example_compliance_integration()
    example_multi_channel_integration()
    
    print("All examples completed successfully!")


if __name__ == "__main__":
    run_all_examples()