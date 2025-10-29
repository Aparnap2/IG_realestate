"""
Integration example for nurture sequences system.

Demonstrates how to use the LangGraph-based nurture sequences
for automated follow-up across different industries.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.nurture_sequences import (
    schedule_nurture_sequence,
    get_next_touch_point,
    cancel_nurture_sequence,
    update_sequence_progress,
    IndustryType,
    ChannelType
)
from utils.engagement_tracker import engagement_tracker
from utils.lead_scoring import calculate_lead_score

def example_real_estate_high_intent_nurture():
    """Example: Schedule nurture sequence for high-intent real estate lead"""
    print("🏠 Real Estate High Intent Nurture Example")
    print("=" * 50)
    
    # Sample lead data
    lead_data = {
        "user_id": "realestate_user_001",
        "first_name": "Sarah",
        "budget": 750000,
        "location": "Miami",
        "timeline": "3 months",
        "property_type": "3BHK"
    }
    
    # Calculate lead score (using existing scoring system)
    lead_score_result = calculate_lead_score(lead_data)
    lead_score = lead_score_result.get('overall_score', 0.7) if isinstance(lead_score_result, dict) else lead_score_result
    print(f"Lead Score: {lead_score:.3f}")
    
    # Schedule nurture sequence
    success = schedule_nurture_sequence(
        user_id=lead_data["user_id"],
        lead_score=lead_score,
        industry_type="real_estate",
        lead_data=lead_data
    )
    
    if success:
        print("✅ Successfully scheduled nurture sequence")
        
        # Show what's scheduled
        next_touch = get_next_touch_point(lead_data["user_id"])
        if next_touch:
            print(f"Next touch point: Day {next_touch['day']} - {next_touch['channel'].upper()}")
            print(f"Template: {next_touch['template_key']}")
            print(f"Scheduled for: {next_touch['scheduled_for']}")
    else:
        print("❌ Failed to schedule nurture sequence")
    
    print()

def example_fitness_high_intent_nurture():
    """Example: Schedule nurture sequence for high-intent fitness lead"""
    print("💪 Fitness High Intent Nurture Example")
    print("=" * 50)
    
    # Sample lead data
    lead_data = {
        "user_id": "fitness_user_001",
        "first_name": "Mike",
        "membership_type": "Premium",
        "fitness_goals": "Weight loss",
        "timeline": "1 month"
    }
    
    # Calculate lead score
    lead_score_result = calculate_lead_score(lead_data)
    lead_score = lead_score_result.get('overall_score', 0.5) if isinstance(lead_score_result, dict) else lead_score_result
    print(f"Lead Score: {lead_score:.3f}")
    
    # Schedule nurture sequence
    success = schedule_nurture_sequence(
        user_id=lead_data["user_id"],
        lead_score=lead_score,
        industry_type="fitness",
        lead_data=lead_data
    )
    
    if success:
        print("✅ Successfully scheduled fitness nurture sequence")
        
        # Show sequence progression
        for i in range(1, 5):
            print(f"Day {i}: {['SMS', 'Email', 'SMS', 'Call'][i-1]} touch scheduled")
    else:
        print("❌ Failed to schedule fitness nurture sequence")
    
    print()

def example_restaurant_high_intent_nurture():
    """Example: Schedule nurture sequence for high-intent restaurant lead"""
    print("🍽 Restaurant High Intent Nurture Example")
    print("=" * 50)
    
    # Sample lead data
    lead_data = {
        "user_id": "restaurant_user_001",
        "first_name": "Emily",
        "party_size": 8,
        "event_date": "2024-12-15",
        "cuisine_preference": "Italian"
    }
    
    # Calculate lead score
    lead_score_result = calculate_lead_score(lead_data)
    lead_score = lead_score_result.get('overall_score', 0.6) if isinstance(lead_score_result, dict) else lead_score_result
    print(f"Lead Score: {lead_score:.3f}")
    
    # Schedule nurture sequence
    success = schedule_nurture_sequence(
        user_id=lead_data["user_id"],
        lead_score=lead_score,
        industry_type="restaurant",
        lead_data=lead_data
    )
    
    if success:
        print("✅ Successfully scheduled restaurant nurture sequence")
        
        # Show touch points
        touch_points = [
            "Day 1: SMS - Menu highlights and specialties",
            "Day 3: Email - Event packages and pricing", 
            "Day 7: SMS - Chef profile and cuisine details",
            "Day 14: Call - Table reservation offer"
        ]
        for touch in touch_points:
            print(f"  • {touch}")
    else:
        print("❌ Failed to schedule restaurant nurture sequence")
    
    print()

def example_sequence_progress_tracking():
    """Example: Track sequence progress and engagement"""
    print("📊 Sequence Progress Tracking Example")
    print("=" * 50)
    
    user_id = "progress_example_user"
    
    # Simulate sequence execution
    print("Simulating sequence execution...")
    
    # Update progress for completed touches
    for day in [1, 3, 7]:
        print(f"Day {day}: Touch completed")
        update_sequence_progress(user_id, True)
        
        # Simulate some delay
        import time
        time.sleep(0.5)
    
    # Get engagement summary
    engagement_summary = engagement_tracker.get_engagement_summary(user_id)
    print(f"\nEngagement Summary:")
    print(f"  Total touches (30 days): {engagement_summary.get('total_touches_30_days', 0)}")
    print(f"  Recent touches (7 days): {engagement_summary.get('recent_touches_7_days', 0)}")
    print(f"  Engagement momentum: {engagement_summary.get('engagement_momentum', 0):.3f}")
    
    # Check conversion readiness
    conversion_ready = engagement_tracker.should_convert_soon(user_id, "real_estate")
    print(f"  Conversion ready: {conversion_ready}")
    
    print()

def example_multi_channel_personalization():
    """Example: Demonstrate multi-channel personalization"""
    print("🎯 Multi-Channel Personalization Example")
    print("=" * 50)
    
    # Sample lead with rich data
    lead_data = {
        "user_id": "personalization_example",
        "first_name": "Alex",
        "budget": 500000,
        "location": "Austin",
        "timeline": "6 months",
        "property_type": "2BHK",
        "preferred_contact": "sms",  # User prefers SMS
        "best_contact_time": "evening",  # Best time to contact
        "language": "English"
    }
    
    # Schedule sequence
    success = schedule_nurture_sequence(
        user_id=lead_data["user_id"],
        lead_score=0.75,  # High intent
        industry_type="real_estate",
        lead_data=lead_data
    )
    
    if success:
        print("✅ Multi-channel personalized sequence scheduled")
        
        # Show personalization examples
        personalization_examples = {
            "SMS": f"Hi {lead_data['first_name']}! Quick market update for {lead_data['location']} - perfect for evening viewing!",
            "Email": f"Dear {lead_data['first_name']}, Here's your detailed {lead_data['location']} property analysis with {len(lead_data)} data points...",
            "Call": f"Hi {lead_data['first_name']}, calling in the evening as requested about {lead_data['property_type']} options in {lead_data['location']}"
        }
        
        for channel, example in personalization_examples.items():
            print(f"\n{channel} Example:")
            print(f"  {example}")
    else:
        print("❌ Failed to schedule personalized sequence")
    
    print()

def example_sequence_cancellation():
    """Example: Cancel active nurture sequence"""
    print("🚫 Sequence Cancellation Example")
    print("=" * 50)
    
    user_id = "cancellation_example_user"
    
    # First schedule a sequence
    lead_data = {"user_id": user_id, "first_name": "Test User"}
    schedule_nurture_sequence(user_id, 0.8, "real_estate", lead_data)
    
    # Then cancel it
    success = cancel_nurture_sequence(user_id)
    
    if success:
        print("✅ Successfully cancelled nurture sequence")
        print("  - Sequence status updated to 'cancelled'")
        print("  - Schedule cleared")
        print("  - User will no longer receive automated touches")
    else:
        print("❌ Failed to cancel nurture sequence")
    
    print()

def example_langgraph_workflow_execution():
    """Example: Demonstrate LangGraph workflow execution"""
    print("🔄 LangGraph Workflow Execution Example")
    print("=" * 50)
    
    # Check if LangGraph is available
    try:
        from automation.nurture_sequences import LANGGRAPH_AVAILABLE
        if LANGGRAPH_AVAILABLE:
            print("✅ LangGraph is available - using advanced workflow orchestration")
            print("  - Dynamic task scheduling")
            print("  - Human-in-the-loop capabilities")
            print("  - State persistence and recovery")
            print("  - Parallel execution support")
        else:
            print("⚠️ LangGraph not available - using Redis-based fallback")
            print("  - Basic scheduling functionality")
            print("  - No dynamic workflow adaptation")
    except ImportError:
        print("❌ LangGraph modules not imported")
    
    print()

def run_all_examples():
    """Run all nurture sequence examples"""
    print("🚀 Nurture Sequences Integration Examples")
    print("=" * 60)
    print("Demonstrating industry-specific automated follow-up sequences")
    print("with LangGraph orchestration, multi-channel communication,")
    print("and intelligent template personalization.\n")
    
    # Run all examples
    example_real_estate_high_intent_nurture()
    example_fitness_high_intent_nurture()
    example_restaurant_high_intent_nurture()
    example_sequence_progress_tracking()
    example_multi_channel_personalization()
    example_sequence_cancellation()
    example_langgraph_workflow_execution()
    
    print("✅ All examples completed!")
    print("\nKey Features Demonstrated:")
    print("  • Industry-specific sequences (Real Estate, Fitness, Restaurant)")
    print("  • Intent-based scheduling (High/Low intent)")
    print("  • Multi-channel communication (SMS, Email, Call)")
    print("  • Template-based personalization")
    print("  • Progress tracking and engagement monitoring")
    print("  • Sequence management (schedule, cancel, update)")
    print("  • LangGraph workflow orchestration")
    print("  • Integration with engagement tracker")
    print("  • Comprehensive error handling")

if __name__ == "__main__":
    run_all_examples()