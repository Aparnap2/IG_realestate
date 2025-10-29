"""
Example demonstrating dynamic configuration capabilities of the nurture system.

This example shows how to:
- Load configurations from different sources
- Update sequences and templates dynamically
- Use environment variables for configuration
- Save and reload configurations
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.nurture_sequences import (
    NurtureSequenceManager,
    IndustryType,
    ChannelType
)
from automation.nurture_config import (
    SequenceConfig,
    TemplateConfig,
    TouchPointConfig,
    nurture_config_loader
)

def example_basic_dynamic_usage():
    """Example: Basic usage with dynamic configuration"""
    print("🔧 Basic Dynamic Configuration Example")
    print("=" * 50)
    
    manager = NurtureSequenceManager()
    
    # Get configuration summary
    summary = manager.get_configuration_summary()
    print(f"Loaded {summary['total_sequences']} sequences for {len(summary['industries'])} industries")
    print(f"Config source: {summary['config_source']}")
    print(f"LangGraph available: {summary['langgraph_available']}")
    
    # Show industry details
    for industry, details in summary['industry_details'].items():
        print(f"\n📊 {industry.title()}:")
        print(f"  Intent levels: {details['intent_levels']}")
        print(f"  Templates: {len(details['templates'])}")
        print(f"  Total touch points: {details['total_touch_points']}")
    
    print()

def example_environment_variable_override():
    """Example: Override configuration using environment variables"""
    print("🌍 Environment Variable Override Example")
    print("=" * 50)
    
    # Set environment variables
    os.environ['NURTURE_REAL_ESTATE_HIGH_INTENT_THRESHOLD'] = '0.7'
    os.environ['NURTURE_TEMPLATE_REAL_ESTATE_MARKET_INSIGHTS'] = 'Hi {first_name}! Custom market insights for {target_area}: {market_data}'
    
    # Reload configurations
    manager = NurtureSequenceManager()
    success = manager.reload_configurations()
    
    if success:
        print("✅ Successfully reloaded configurations with environment overrides")
        
        # Check updated threshold
        real_estate_sequences = manager.sequences.get(IndustryType.REAL_ESTATE, {})
        high_intent = real_estate_sequences.get('high_intent')
        if high_intent:
            print(f"Updated threshold: {high_intent.intent_threshold}")
        
        # Check updated template
        real_estate_templates = manager.templates.get(IndustryType.REAL_ESTATE, {})
        market_template = real_estate_templates.get('market_insights')
        if market_template:
            print(f"Updated template: {market_template['template']}")
    
    print()

def example_dynamic_sequence_update():
    """Example: Update sequence configuration dynamically"""
    print("🔄 Dynamic Sequence Update Example")
    print("=" * 50)
    
    manager = NurtureSequenceManager()
    
    # Create new sequence configuration for hotel industry
    hotel_sequence = SequenceConfig(
        intent_threshold=0.7,
        touch_points=[
            TouchPointConfig(1, "sms", "welcome_message"),
            TouchPointConfig(2, "email", "room_options"),
            TouchPointConfig(5, "sms", "booking_reminder"),
            TouchPointConfig(10, "call", "concierge_service")
        ],
        total_duration_days=10,
        ab_test_enabled=True
    )
    
    # Update sequence
    success = manager.update_sequence_config("hotel", "high_intent", hotel_sequence)
    
    if success:
        print("✅ Successfully added hotel high intent sequence")
        
        # Verify it was added
        hotel_sequences = manager.sequences.get(IndustryType.HOTEL, {})
        if hotel_sequences and 'high_intent' in hotel_sequences:
            sequence = hotel_sequences['high_intent']
            print(f"Hotel sequence has {len(sequence.touch_points)} touch points")
            print(f"Intent threshold: {sequence.intent_threshold}")
            print(f"A/B testing enabled: {sequence.ab_test_enabled}")
    
    print()

def example_dynamic_template_update():
    """Example: Update template configuration dynamically"""
    print("📝 Dynamic Template Update Example")
    print("=" * 50)
    
    manager = NurtureSequenceManager()
    
    # Create new template for hotel industry
    hotel_template = TemplateConfig(
        template="Hi {first_name}! Welcome to {hotel_name}. Your room {room_number} is ready. {check_in_info}",
        personalization_fields=["first_name", "hotel_name", "room_number", "check_in_info"],
        compliance_required=True,
        channel_specific=False,
        a_b_test_variants=[
            "Hello {first_name}! Your {hotel_name} room {room_number} awaits. {check_in_info}",
            "Greetings {first_name}! Welcome to {hotel_name}. Room {room_number} ready. {check_in_info}"
        ]
    )
    
    # Update template
    success = manager.update_template_config("hotel", "welcome_message", hotel_template)
    
    if success:
        print("✅ Successfully added hotel welcome template")
        
        # Verify it was added
        hotel_templates = manager.templates.get(IndustryType.HOTEL, {})
        if hotel_templates and 'welcome_message' in hotel_templates:
            template = hotel_templates['welcome_message']
            print(f"Template: {template['template']}")
            print(f"Personalization fields: {template['personalization_fields']}")
            print(f"A/B test variants: {len(template['a_b_test_variants'] or [])}")
    
    print()

def example_save_configurations():
    """Example: Save current configurations to file"""
    print("💾 Save Configuration Example")
    print("=" * 50)
    
    # Save current configurations
    success = nurture_config_loader.save_configurations()
    
    if success:
        print("✅ Successfully saved configurations to file")
        print(f"Config file: {nurture_config_loader.config_path}")
    else:
        print("❌ Failed to save configurations")
    
    print()

def example_schedule_with_dynamic_config():
    """Example: Schedule sequence using dynamic configuration"""
    print("📅 Schedule with Dynamic Config Example")
    print("=" * 50)
    
    manager = NurtureSequenceManager()
    
    # Sample hotel lead data
    lead_data = {
        "user_id": "hotel_user_001",
        "first_name": "James",
        "hotel_name": "Grand Plaza",
        "room_number": "304",
        "check_in_date": "2024-12-15"
    }
    
    # Schedule sequence (will use the dynamically added hotel sequence)
    success = manager.schedule_nurture_sequence(
        user_id=lead_data["user_id"],
        lead_score=0.8,  # Above 0.7 threshold
        industry_type="hotel",
        lead_data=lead_data
    )
    
    if success:
        print("✅ Successfully scheduled hotel nurture sequence")
        
        # Get next touch point
        next_touch = manager.get_next_touch_point(lead_data["user_id"])
        if next_touch:
            print(f"Next touch: Day {next_touch['day']} - {next_touch['channel'].upper()}")
            print(f"Template: {next_touch['template_key']}")
    else:
        print("❌ Failed to schedule hotel sequence (hotel sequence may not be configured)")
    
    print()

def run_all_dynamic_examples():
    """Run all dynamic configuration examples"""
    print("🚀 Dynamic Configuration Examples")
    print("=" * 60)
    print("Demonstrating flexible configuration management")
    print("for nurture sequences without code changes.\n")
    
    # Run all examples
    example_basic_dynamic_usage()
    example_environment_variable_override()
    example_dynamic_sequence_update()
    example_dynamic_template_update()
    example_save_configurations()
    example_schedule_with_dynamic_config()
    
    print("✅ All dynamic configuration examples completed!")
    print("\nKey Features Demonstrated:")
    print("  • Dynamic configuration loading from JSON files")
    print("  • Environment variable overrides")
    print("  • Runtime sequence and template updates")
    print("  • Configuration persistence and reloading")
    print("  • A/B testing support")
    print("  • Multi-source configuration (file, env, database)")
    print("  • Industry extensibility without code changes")

if __name__ == "__main__":
    run_all_dynamic_examples()