"""
Integration examples for the engagement tracker system.
Demonstrates real-world usage patterns and best practices.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.utils.engagement_tracker import engagement_tracker, INDUSTRY_TOUCH_REQUIREMENTS

def simulate_user_journey(user_id: str, industry_type: str = "real_estate"):
    """
    Simulate a complete user journey with various touch points.
    
    Args:
        user_id: Unique user identifier
        industry_type: Industry type for conversion prediction
    """
    logger.info(f"Starting user journey simulation for {user_id} in {industry_type}")
    
    # Day 1: Initial contact
    logger.info("Day 1: Initial contact")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="website_visit",
        content="User visited property listing page",
        metadata={"property_id": "prop_123", "stage": "initial_contact", "source": "organic_search"}
    )
    
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="form_submission",
        content="User submitted contact form",
        metadata={"property_id": "prop_123", "stage": "initial_contact", "form_type": "property_inquiry"}
    )
    
    # Day 2: Follow-up
    logger.info("Day 2: Follow-up communication")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="email",
        content="Automated welcome email with property details",
        metadata={"property_id": "prop_123", "stage": "qualification", "email_type": "automated"}
    )
    
    # Simulate user response
    time.sleep(0.1)  # Small delay to simulate response time
    engagement_tracker.mark_response_received(
        user_id=user_id,
        touch_timestamp=datetime.utcnow() - timedelta(days=1),
        response_time_seconds=7200  # 2 hours
    )
    
    # Day 3: Property viewing
    logger.info("Day 3: Property viewing")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="property_view",
        content="User scheduled property viewing",
        metadata={"property_id": "prop_123", "stage": "consideration", "viewing_type": "in_person"}
    )
    
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="call",
        content="Phone call to confirm viewing details",
        metadata={"property_id": "prop_123", "stage": "consideration", "call_duration": 300}
    )
    
    # Day 5: Additional engagement
    logger.info("Day 5: Additional engagement")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="text",
        content="SMS reminder about property viewing",
        metadata={"property_id": "prop_123", "stage": "consideration", "message_type": "reminder"}
    )
    
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="social_engagement",
        content="User liked property on social media",
        metadata={"property_id": "prop_123", "stage": "consideration", "platform": "instagram"}
    )
    
    # Day 7: Booking attempt
    logger.info("Day 7: Booking attempt")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="booking_attempt",
        content="User attempted to book property viewing",
        metadata={"property_id": "prop_123", "stage": "intent", "booking_status": "pending"}
    )
    
    # Day 10: Final follow-up
    logger.info("Day 10: Final follow-up")
    engagement_tracker.record_touch_point(
        user_id=user_id,
        touch_type="email",
        content="Personalized follow-up with similar properties",
        metadata={"property_id": "prop_123", "stage": "decision", "email_type": "personalized"}
    )
    
    # Get engagement summary
    summary = engagement_tracker.get_engagement_summary(user_id)
    logger.info(f"Engagement Summary for {user_id}:")
    logger.info(f"  Total touches (30 days): {summary['total_touches_30_days']}")
    logger.info(f"  Recent touches (7 days): {summary['recent_touches_7_days']}")
    logger.info(f"  Engagement momentum: {summary['engagement_momentum']:.3f}")
    logger.info(f"  Conversion ready ({industry_type}): {summary['conversion_predictions'].get(industry_type, False)}")
    
    return summary

def demonstrate_industry_differences():
    """Demonstrate how touch requirements differ by industry."""
    logger.info("\n=== Industry Touch Requirements ===")
    
    for industry, required_touches in INDUSTRY_TOUCH_REQUIREMENTS.items():
        logger.info(f"{industry.title()}: {required_touches} touches required for conversion")
        
        # Simulate a user with exactly the required touches
        user_id = f"demo_user_{industry}"
        simulate_user_with_exact_touches(user_id, industry, required_touches)
        
        # Check conversion readiness
        should_convert = engagement_tracker.should_convert_soon(user_id, industry)
        momentum = engagement_tracker.calculate_engagement_momentum(user_id)
        
        logger.info(f"  Conversion ready: {should_convert}")
        logger.info(f"  Engagement momentum: {momentum:.3f}")
        logger.info("")

def simulate_user_with_exact_touches(user_id: str, industry: str, required_touches: int):
    """Simulate a user with exactly the required number of touches."""
    touch_types = ["email", "call", "text", "property_view", "website_visit", "social_engagement"]
    
    for i in range(required_touches):
        touch_type = touch_types[i % len(touch_types)]
        days_ago = (required_touches - i)  # Spread touches over time
        
        engagement_tracker.record_touch_point(
            user_id=user_id,
            touch_type=touch_type,
            content=f"Touch point {i+1} for {industry} user",
            metadata={
                "stage": "consideration",
                "industry": industry,
                "touch_number": i + 1
            }
        )
        
        # Simulate some responses
        if i % 3 == 0:
            engagement_tracker.mark_response_received(
                user_id=user_id,
                touch_timestamp=datetime.utcnow() - timedelta(days=days_ago),
                response_time_seconds=3600 * (i % 24 + 1)  # 1-24 hours
            )

def demonstrate_engagement_momentum_factors():
    """Demonstrate how different factors affect engagement momentum."""
    logger.info("\n=== Engagement Momentum Factors ===")
    
    # Create different user scenarios
    scenarios = {
        "high_engagement": {
            "description": "High engagement: recent, frequent, diverse touches",
            "touches": [
                ("email", 0, "consideration"),
                ("call", 1, "qualification"),
                ("property_view", 2, "consideration"),
                ("text", 3, "intent"),
                ("booking_attempt", 4, "decision"),
                ("social_engagement", 5, "consideration"),
                ("website_visit", 6, "initial_contact"),
                ("form_submission", 7, "qualification")
            ]
        },
        "low_engagement": {
            "description": "Low engagement: old, infrequent, single-type touches",
            "touches": [
                ("email", 20, "initial_contact"),
                ("email", 25, "initial_contact"),
                ("email", 28, "initial_contact")
            ]
        },
        "medium_engagement": {
            "description": "Medium engagement: moderate recency and diversity",
            "touches": [
                ("website_visit", 10, "initial_contact"),
                ("email", 12, "qualification"),
                ("call", 14, "consideration"),
                ("text", 16, "consideration"),
                ("property_view", 18, "intent")
            ]
        }
    }
    
    for scenario_name, scenario_data in scenarios.items():
        logger.info(f"\n{scenario_data['description']}")
        
        user_id = f"scenario_{scenario_name}"
        
        # Record touches
        for touch_type, days_ago, stage in scenario_data["touches"]:
            engagement_tracker.record_touch_point(
                user_id=user_id,
                touch_type=touch_type,
                content=f"{touch_type} touch for {scenario_name}",
                metadata={"stage": stage, "scenario": scenario_name}
            )
            
            # Simulate responses for some touches
            if touch_type in ["email", "text", "call"]:
                engagement_tracker.mark_response_received(
                    user_id=user_id,
                    touch_timestamp=datetime.utcnow() - timedelta(days=days_ago),
                    response_time_seconds=3600 * (days_ago % 8 + 1)
                )
        
        # Calculate metrics
        momentum = engagement_tracker.calculate_engagement_momentum(user_id)
        touch_count = engagement_tracker.get_touch_count(user_id, days=30)
        should_convert = engagement_tracker.should_convert_soon(user_id, "real_estate")
        
        logger.info(f"  Total touches: {touch_count}")
        logger.info(f"  Engagement momentum: {momentum:.3f}")
        logger.info(f"  Conversion ready: {should_convert}")

def demonstrate_touch_history_analysis():
    """Demonstrate touch history analysis and insights."""
    logger.info("\n=== Touch History Analysis ===")
    
    user_id = "history_analysis_user"
    
    # Create a realistic touch pattern over 30 days
    touch_pattern = [
        (1, "website_visit", "initial_contact", "User discovered property via search"),
        (2, "property_view", "initial_contact", "Viewed 3 property listings"),
        (3, "form_submission", "qualification", "Submitted contact form"),
        (5, "email", "qualification", "Automated welcome email"),
        (7, "call", "consideration", "Phone consultation with agent"),
        (10, "property_view", "consideration", "In-person property tour"),
        (12, "text", "consideration", "SMS follow-up with additional photos"),
        (15, "social_engagement", "consideration", "Liked property on Instagram"),
        (18, "email", "intent", "Personalized property recommendations"),
        (20, "booking_attempt", "intent", "Attempted to schedule second viewing"),
        (22, "call", "decision", "Discussion about financing options"),
        (25, "email", "decision", "Sending application documents"),
        (28, "form_submission", "decision", "Submitted rental application")
    ]
    
    # Record touches with realistic timing
    for days_ago, touch_type, stage, content in touch_pattern:
        engagement_tracker.record_touch_point(
            user_id=user_id,
            touch_type=touch_type,
            content=content,
            metadata={
                "stage": stage,
                "days_since_first_contact": days_ago,
                "property_interest": "prop_123"
            }
        )
        
        # Simulate responses for outreach touches
        if touch_type in ["email", "call", "text"]:
            response_delay = 3600 * (days_ago % 6 + 2)  # 2-8 hours
            engagement_tracker.mark_response_received(
                user_id=user_id,
                touch_timestamp=datetime.utcnow() - timedelta(days=days_ago),
                response_time_seconds=response_delay
            )
    
    # Analyze touch history
    history = engagement_tracker.get_touch_history(user_id, limit=50)
    logger.info(f"Total touch points recorded: {len(history)}")
    
    # Show progression through stages
    stage_progression = {}
    for touch in history:
        stage = touch.get("metadata", {}).get("stage", "unknown")
        if stage not in stage_progression:
            stage_progression[stage] = 0
        stage_progression[stage] += 1
    
    logger.info("Stage progression:")
    for stage, count in stage_progression.items():
        logger.info(f"  {stage}: {count} touches")
    
    # Show touch type diversity
    touch_types = {}
    for touch in history:
        touch_type = touch.get("touch_type", "unknown")
        if touch_type not in touch_types:
            touch_types[touch_type] = 0
        touch_types[touch_type] += 1
    
    logger.info("Touch type diversity:")
    for touch_type, count in touch_types.items():
        logger.info(f"  {touch_type}: {count} touches")
    
    # Get final engagement summary
    summary = engagement_tracker.get_engagement_summary(user_id)
    logger.info(f"\nFinal engagement metrics:")
    logger.info(f"  Engagement momentum: {summary['engagement_momentum']:.3f}")
    logger.info(f"  Conversion ready (real_estate): {summary['conversion_predictions']['real_estate']}")
    logger.info(f"  Conversion ready (fitness): {summary['conversion_predictions']['fitness']}")
    logger.info(f"  Conversion ready (hotel): {summary['conversion_predictions']['hotel']}")

def demonstrate_real_time_tracking():
    """Demonstrate real-time tracking capabilities."""
    logger.info("\n=== Real-time Tracking Demo ===")
    
    user_id = "real_time_user"
    
    # Simulate real-time interactions
    interactions = [
        ("website_visit", "User landed on homepage"),
        ("property_view", "Viewed luxury apartment listing"),
        ("property_view", "Viewed penthouse suite"),
        ("form_submission", "Requested more information"),
        ("email", "Instant automated response"),
        ("call", "Agent called user within 5 minutes")
    ]
    
    logger.info("Simulating real-time user interactions...")
    
    for i, (touch_type, content) in enumerate(interactions):
        logger.info(f"Interaction {i+1}: {touch_type} - {content}")
        
        # Record the touch point
        engagement_tracker.record_touch_point(
            user_id=user_id,
            touch_type=touch_type,
            content=content,
            metadata={
                "real_time": True,
                "interaction_number": i + 1,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Simulate immediate response for some interactions
        if touch_type in ["email", "call"]:
            time.sleep(0.1)  # Small delay
            engagement_tracker.mark_response_received(
                user_id=user_id,
                touch_timestamp=datetime.utcnow(),
                response_time_seconds=300  # 5 minutes
            )
            logger.info(f"  -> User responded within 5 minutes")
        
        # Show updated metrics after each interaction
        momentum = engagement_tracker.calculate_engagement_momentum(user_id)
        touch_count = engagement_tracker.get_touch_count(user_id, days=1)
        should_convert = engagement_tracker.should_convert_soon(user_id, "real_estate")
        
        logger.info(f"  Current momentum: {momentum:.3f}")
        logger.info(f"  Today's touches: {touch_count}")
        logger.info(f"  Conversion ready: {should_convert}")
        logger.info("")
        
        time.sleep(0.5)  # Brief pause between interactions

def main():
    """Run all engagement tracker demonstrations."""
    logger.info("Engagement Tracker Integration Examples")
    logger.info("=" * 50)
    
    try:
        # Basic user journey simulation
        logger.info("\n1. Basic User Journey Simulation")
        simulate_user_journey("demo_user_001", "real_estate")
        
        # Industry differences
        logger.info("\n2. Industry-Specific Requirements")
        demonstrate_industry_differences()
        
        # Engagement momentum factors
        logger.info("\n3. Engagement Momentum Factors")
        demonstrate_engagement_momentum_factors()
        
        # Touch history analysis
        logger.info("\n4. Touch History Analysis")
        demonstrate_touch_history_analysis()
        
        # Real-time tracking
        logger.info("\n5. Real-time Tracking")
        demonstrate_real_time_tracking()
        
        logger.info("\n" + "=" * 50)
        logger.info("All demonstrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during demonstration: {e}")
        raise

if __name__ == "__main__":
    main()