"""
Example: Integrating Response Time Tracking with Lead Scoring System

This example demonstrates how to use the response time tracking system
to enhance lead qualification scoring with industry-standard response time metrics.
"""

from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.response_tracker import (
    track_first_response,
    calculate_urgency_score,
    get_response_time_minutes,
    get_urgency_stats
)
from utils.lead_scoring import calculate_lead_score


def example_lead_workflow():
    """
    Example workflow demonstrating response time tracking integration.
    """
    # Example lead data
    user_id = "instagram_user_12345"
    lead_data = {
        'name': 'John Doe',
        'email': 'john.doe@example.com',
        'message': 'Looking for a 2-bedroom apartment in downtown Austin with budget around $300k',
        'budget': 300000,
        'location': 'downtown Austin',
        'timeline': '3-6 months',
        'property_type': 'apartment',
        'desired_bedrooms': 2
    }
    
    print("=== Lead Response Time Tracking Example ===\n")
    
    # Step 1: Track first contact (when lead first reaches out)
    first_contact_time = datetime.now() - timedelta(minutes=8)
    success = track_first_response(user_id, first_contact_time)
    
    if success:
        print(f"✓ First contact tracked for user {user_id}")
        print(f"  Contact time: {first_contact_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"✗ Failed to track first contact for user {user_id}")
        return
    
    # Step 2: Calculate initial lead score (without response time)
    initial_score = calculate_lead_score(lead_data)
    print(f"\n📊 Initial Lead Score: {initial_score['final_score']:.3f}")
    print(f"  Routing: {initial_score['routing_recommendation']['next_agent']}")
    print(f"  Stage: {initial_score['qualification_stage']}")
    
    # Step 3: Get current urgency stats (before response)
    urgency_stats = get_urgency_stats(user_id)
    print(f"\n⏰ Urgency Stats (Pre-Response):")
    print(f"  Response Time: {urgency_stats['response_time_minutes']:.1f} minutes")
    print(f"  Urgency Score: {urgency_stats['urgency_score']:.1f}")
    print(f"  Category: {urgency_stats['urgency_category']}")
    print(f"  Industry Standard Met: {urgency_stats['industry_standard_met']}")
    print(f"  Qualification Impact: {urgency_stats['qualification_impact_factor']}")
    
    # Step 4: Simulate response time and update
    response_time = datetime.now() - timedelta(minutes=3)  # 3-minute response
    print(f"\n📝 Response sent at: {response_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 5: Calculate enhanced lead score with response time factor
    urgency_score = calculate_urgency_score(user_id)
    
    # Apply response time impact to lead score
    base_score = initial_score['final_score']
    impact_factor = urgency_stats['qualification_impact_factor']
    enhanced_score = base_score * impact_factor
    
    print(f"\n📈 Enhanced Lead Scoring:")
    print(f"  Base Score: {base_score:.3f}")
    print(f"  Response Time Score: {urgency_score:.1f}")
    print(f"  Impact Factor: {impact_factor}")
    print(f"  Enhanced Score: {enhanced_score:.3f}")
    
    # Step 6: Determine final routing based on enhanced score
    if enhanced_score >= 0.75:
        final_routing = 'scheduler'
        priority = 'high'
    elif enhanced_score >= 0.4:
        final_routing = 'followup'
        priority = 'medium'
    else:
        final_routing = 'offramp'
        priority = 'low'
    
    print(f"\n🎯 Final Recommendation:")
    print(f"  Route to: {final_routing}")
    print(f"  Priority: {priority}")
    print(f"  Reason: Enhanced score {enhanced_score:.3f} with response time consideration")


def example_response_time_scenarios():
    """
    Example showing different response time scenarios and their impact.
    """
    print("\n=== Response Time Impact Scenarios ===\n")
    
    scenarios = [
        (2, "Excellent - 2 minutes"),
        (8, "Good - 8 minutes"),
        (30, "Acceptable - 30 minutes"),
        (180, "Poor - 3 hours"),
        (480, "Very Poor - 8 hours")
    ]
    
    base_lead_score = 0.65  # Example base score
    
    for response_minutes, description in scenarios:
        user_id = f"scenario_user_{response_minutes}"
        first_contact = datetime.now() - timedelta(minutes=response_minutes)
        
        # Track first contact
        track_first_response(user_id, first_contact)
        
        # Get urgency stats
        stats = get_urgency_stats(user_id)
        
        # Calculate impact
        impact_factor = stats['qualification_impact_factor']
        enhanced_score = base_lead_score * impact_factor
        
        print(f"📊 {description}:")
        print(f"   Response Time: {response_minutes} minutes")
        print(f"   Urgency Score: {stats['urgency_score']:.1f}")
        print(f"   Impact Factor: {impact_factor}")
        print(f"   Base Score: {base_lead_score:.3f}")
        print(f"   Enhanced Score: {enhanced_score:.3f}")
        print(f"   Industry Standard: {'✓' if stats['industry_standard_met'] else '✗'}")
        print()


if __name__ == "__main__":
    # Run example workflow
    example_lead_workflow()
    
    # Show different scenarios
    example_response_time_scenarios()
    
    print("\n=== Key Takeaways ===")
    print("• Response time ≤ 5 minutes: No impact on qualification (1.0x factor)")
    print("• Response time 5-15 minutes: Minor impact (0.8x factor)")
    print("• Response time 15-60 minutes: Moderate impact (0.6x factor)")
    print("• Response time 1-4 hours: Significant impact (0.4x factor)")
    print("• Response time > 4 hours: Severe impact (0.1x factor - 10x drop)")
    print("\n• Industry standard is 5-minute response time for maximum conversion")
    print("• Response time tracking should be integrated into lead scoring for optimal results")