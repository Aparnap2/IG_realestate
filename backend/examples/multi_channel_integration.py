"""
Multi-Channel Communication Manager Integration Example

Demonstrates how to use the multi-channel communication manager
with the existing nurture sequences and engagement tracking systems.
"""

import os
import sys
from datetime import datetime, timedelta

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from communication.multi_channel_manager import (
    multi_channel_manager,
    ChannelType,
    MessagePriority,
    IndustryType
)
from automation.nurture_sequences import nurture_sequence_manager
from utils.engagement_tracker import engagement_tracker
from utils.response_tracker import response_tracker


def setup_test_user_preferences():
    """Set up test user preferences for demonstration"""
    user_id = "demo_user_123"
    
    # Update user preferences
    preferences = {
        "preferred_channel": "instagram_dm",  # Primary channel
        "backup_channels": ["sms", "email"],
        "business_hours_only": True,
        "max_messages_per_day": 5,
        "do_not_disturb": False,
        "timezone": "US/Eastern",
        "industry_type": "real_estate"
    }
    
    success = multi_channel_manager.update_channel_preferences(user_id, preferences)
    print(f"✅ Updated user preferences: {success}")
    
    return user_id


def demonstrate_intelligent_channel_selection():
    """Demonstrate intelligent channel selection based on different scenarios"""
    print("\n🎯 Intelligent Channel Selection Demo")
    print("=" * 50)
    
    user_id = setup_test_user_preferences()
    
    # Test different message types and priorities
    test_scenarios = [
        {
            "message_type": "engagement",
            "priority": "normal",
            "description": "Regular engagement message"
        },
        {
            "message_type": "urgent",
            "priority": "urgent",
            "description": "Urgent property alert"
        },
        {
            "message_type": "detailed",
            "priority": "normal",
            "description": "Detailed property information"
        },
        {
            "message_type": "booking",
            "priority": "high",
            "description": "Booking confirmation"
        }
    ]
    
    for scenario in test_scenarios:
        optimal_channel = multi_channel_manager.get_optimal_channel(
            user_id=user_id,
            message_type=scenario["message_type"],
            priority=scenario["priority"]
        )
        
        print(f"\n📋 {scenario['description']}")
        print(f"   Message Type: {scenario['message_type']}")
        print(f"   Priority: {scenario['priority']}")
        print(f"   Optimal Channel: {optimal_channel.value}")


def demonstrate_message_formatting():
    """Demonstrate channel-specific message formatting"""
    print("\n📝 Message Formatting Demo")
    print("=" * 50)
    
    test_message = "Hi! I found some great properties that match your criteria. Would you like to schedule a viewing this weekend?"
    
    channels = [
        (ChannelType.INSTAGRAM_DM, "Instagram DM"),
        (ChannelType.SMS, "SMS"),
        (ChannelType.EMAIL, "Email"),
        (ChannelType.PUSH_NOTIFICATION, "Push Notification"),
        (ChannelType.WHATSAPP, "WhatsApp")
    ]
    
    for channel, channel_name in channels:
        formatted = multi_channel_manager.format_message_for_channel(
            message=test_message,
            channel=channel,
            message_type="engagement"
        )
        
        print(f"\n📱 {channel_name}:")
        if isinstance(formatted, dict):
            print(f"   Title: {formatted.get('title', 'N/A')}")
            print(f"   Body: {formatted.get('body', str(formatted))}")
        else:
            print(f"   Content: {formatted[:100]}{'...' if len(formatted) > 100 else ''}")


def demonstrate_compliance_checking():
    """Demonstrate industry-specific compliance checking"""
    print("\n⚖️ Compliance Checking Demo")
    print("=" * 50)
    
    # Test messages for different industries
    test_cases = [
        {
            "industry": IndustryType.REAL_ESTATE,
            "compliant": "We have several properties available in your preferred area. All listings comply with fair housing laws.",
            "non_compliant": "Guaranteed returns on all real estate investments!"
        },
        {
            "industry": IndustryType.FITNESS,
            "compliant": "Our certified trainers can help you achieve your fitness goals. Please consult with a doctor before starting.",
            "non_compliant": "Lose 20 pounds in 2 weeks guaranteed!"
        },
        {
            "industry": IndustryType.RESTAURANT,
            "compliant": "Try our new menu items! All ingredients are sourced from local farms.",
            "non_compliant": "Our food cures all diseases!"
        }
    ]
    
    for case in test_cases:
        print(f"\n🏢 {case['industry'].value.title()}:")
        
        # Test compliant message
        compliant_result = multi_channel_manager.check_compliance(
            user_id="test_user",
            message=case["compliant"],
            channel=ChannelType.EMAIL,
            industry_type=case["industry"]
        )
        print(f"   ✅ Compliant Message: {compliant_result}")
        
        # Test non-compliant message
        non_compliant_result = multi_channel_manager.check_compliance(
            user_id="test_user",
            message=case["non_compliant"],
            channel=ChannelType.EMAIL,
            industry_type=case["industry"]
        )
        print(f"   ❌ Non-Compliant Message: {non_compliant_result}")


def demonstrate_nurture_sequence_integration():
    """Demonstrate integration with nurture sequences"""
    print("\n🔄 Nurture Sequence Integration Demo")
    print("=" * 50)
    
    user_id = "demo_user_456"
    lead_score = 0.75  # High intent lead
    industry_type = "real_estate"
    
    # Set up user preferences
    preferences = {
        "preferred_channel": "instagram_dm",
        "backup_channels": ["sms", "email"],
        "business_hours_only": False,
        "industry_type": industry_type
    }
    multi_channel_manager.update_channel_preferences(user_id, preferences)
    
    # Schedule nurture sequence
    lead_data = {
        "name": "John Doe",
        "budget": 500000,
        "location": "Austin, TX",
        "property_type": "3BHK"
    }
    
    success = nurture_sequence_manager.schedule_nurture_sequence(
        user_id=user_id,
        lead_score=lead_score,
        industry_type=industry_type,
        lead_data=lead_data
    )
    
    print(f"✅ Nurture sequence scheduled: {success}")
    
    # Get next touch point
    next_touch = nurture_sequence_manager.get_next_touch_point(user_id)
    if next_touch:
        print(f"📅 Next touch point: Day {next_touch['day']} via {next_touch['channel']}")
        
        # Send message via multi-channel manager
        message = f"Hi {lead_data['name']}! I found some great {lead_data['property_type']} properties in {lead_data['location']} within your budget of ${lead_data['budget']}."
        
        result = multi_channel_manager.send_message(
            user_id=user_id,
            message=message,
            channel="auto",
            priority="normal",
            message_type="engagement"
        )
        
        print(f"📤 Message sent: {result['success']}")
        print(f"   Channel used: {result['channel']}")
        print(f"   Selection reason: {result.get('selection_reason', 'N/A')}")
        print(f"   Message ID: {result.get('message_id', 'N/A')}")


def demonstrate_engagement_tracking():
    """Demonstrate engagement tracking integration"""
    print("\n📊 Engagement Tracking Demo")
    print("=" * 50)
    
    user_id = "demo_user_789"
    
    # Record some touch points
    touch_points = [
        {"type": "instagram_dm", "content": "Initial contact via Instagram DM"},
        {"type": "email", "content": "Property details sent via email"},
        {"type": "sms", "content": "Viewing confirmation via SMS"},
        {"type": "instagram_dm", "content": "Follow-up message via Instagram DM"}
    ]
    
    for i, touch in enumerate(touch_points, 1):
        engagement_tracker.record_touch_point(
            user_id=user_id,
            touch_type=touch["type"],
            content=touch["content"],
            metadata={
                "sequence_step": i,
                "automated": True
            }
        )
        print(f"📝 Recorded touch point {i}: {touch['type']}")
    
    # Get engagement summary
    summary = engagement_tracker.get_engagement_summary(user_id)
    
    print(f"\n📈 Engagement Summary for {user_id}:")
    print(f"   Total touches (30 days): {summary['total_touches_30_days']}")
    print(f"   Recent touches (7 days): {summary['recent_touches_7_days']}")
    print(f"   Engagement momentum: {summary['engagement_momentum']:.3f}")
    
    print(f"\n📱 Touch Type Breakdown:")
    for touch_type, count in summary['touch_type_breakdown'].items():
        print(f"   {touch_type}: {count}")
    
    # Check conversion readiness
    should_convert = engagement_tracker.should_convert_soon(user_id, "real_estate")
    print(f"\n🎯 Conversion Readiness: {'Yes' if should_convert else 'No'}")


def demonstrate_response_tracking():
    """Demonstrate response time tracking integration"""
    print("\n⏱️ Response Time Tracking Demo")
    print("=" * 50)
    
    user_id = "demo_user_101"
    
    # Track first response
    first_contact_time = datetime.utcnow() - timedelta(minutes=3)
    success = response_tracker.track_first_response(user_id, first_contact_time)
    print(f"✅ First response tracked: {success}")
    
    # Get urgency statistics
    urgency_stats = response_tracker.get_urgency_stats(user_id)
    
    print(f"\n📊 Urgency Statistics for {user_id}:")
    print(f"   Response time: {urgency_stats['response_time_minutes']:.2f} minutes")
    print(f"   Urgency score: {urgency_stats['urgency_score']:.3f}")
    print(f"   Urgency category: {urgency_stats['urgency_category']}")
    print(f"   Category description: {urgency_stats['category_description']}")
    print(f"   Industry standard met: {urgency_stats['industry_standard_met']}")
    print(f"   Qualification impact factor: {urgency_stats['qualification_impact_factor']}")


def demonstrate_channel_performance():
    """Demonstrate channel performance monitoring"""
    print("\n📈 Channel Performance Demo")
    print("=" * 50)
    
    # Send some test messages to generate performance data
    test_messages = [
        {"user_id": "user1", "channel": "instagram_dm", "message": "Test IG message 1"},
        {"user_id": "user2", "channel": "instagram_dm", "message": "Test IG message 2"},
        {"user_id": "user3", "channel": "sms", "message": "Test SMS message"},
        {"user_id": "user4", "channel": "email", "message": "Test email message"}
    ]
    
    for msg in test_messages:
        result = multi_channel_manager.send_message(
            user_id=msg["user_id"],
            message=msg["message"],
            channel=msg["channel"],
            priority="normal",
            message_type="engagement"
        )
        print(f"📤 Sent {msg['channel']} message to {msg['user_id']}: {result['success']}")
    
    # Get performance metrics
    channels = [ChannelType.INSTAGRAM_DM, ChannelType.SMS, ChannelType.EMAIL]
    
    print(f"\n📊 Channel Performance Metrics:")
    for channel in channels:
        performance = multi_channel_manager.get_channel_performance(channel)
        
        print(f"\n📱 {channel.value.title()}:")
        print(f"   Total sent: {performance.get('total_sent', 0)}")
        print(f"   Successful: {performance.get('successful', 0)}")
        print(f"   Failed: {performance.get('failed', 0)}")
        print(f"   Success rate: {performance.get('success_rate', 0):.1f}%")


def main():
    """Run all demonstration scenarios"""
    print("🚀 Multi-Channel Communication Manager Integration Demo")
    print("=" * 60)
    
    try:
        # Run all demonstration scenarios
        demonstrate_intelligent_channel_selection()
        demonstrate_message_formatting()
        demonstrate_compliance_checking()
        demonstrate_nurture_sequence_integration()
        demonstrate_engagement_tracking()
        demonstrate_response_tracking()
        demonstrate_channel_performance()
        
        print("\n✅ All demonstrations completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()