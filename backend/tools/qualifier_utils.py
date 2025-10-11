"""
Qualifier Utilities - Budget Reconciliation & Multi-Step Reasoning

Implements PRD Section 2.2: Adaptive Lead Qualification with budget/needs reconciliation.

Key Features:
- Budget vs. needs mismatch handling ("wants 3BR on 2BR budget")
- Inventory analysis and alternative suggestions
- Temporal context integration for qualification scoring
- Market-aware pricing recommendations
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import supabase
from utils.audit import audit_log_event

def reconcile_budget_mismatch(
    desired_bedrooms: int,
    budget: int,
    inventory: List[Dict[str, Any]],
    location: str = None
) -> Dict[str, Any]:
    """
    Handle budget vs. needs mismatches with intelligent alternatives.
    
    Analyzes available inventory and proposes value-based alternatives
    when lead's desired bedrooms exceed what their budget can afford.
    
    Args:
        desired_bedrooms: Number of bedrooms lead wants
        budget: Lead's maximum budget
        inventory: Available properties from database
        location: Lead's preferred location
        
    Returns:
        Dictionary with reconciliation options and reasoning
    """
    try:
        # Analyze inventory by bedroom count and price
        inventory_analysis = _analyze_inventory_by_bedrooms(inventory, budget)
        
        # Check if exact match exists
        exact_matches = [
            prop for prop in inventory 
            if prop.get("bedrooms", 0) == desired_bedrooms and prop.get("price", 0) <= budget
        ]
        
        if exact_matches:
            return {
                "has_exact_match": True,
                "exact_matches": len(exact_matches),
                "recommendation": "show_exact_matches",
                "message": f"Great news! I found {len(exact_matches)} {desired_bedrooms}BR properties within your ${budget:,} budget.",
                "alternatives": [],
                "reasoning": "Perfect match available within budget"
            }
        
        # Generate reconciliation options
        options = []
        
        # Option 1: Lower bedroom count in premium location/features
        lower_br_premium = [
            prop for prop in inventory
            if prop.get("bedrooms", 0) == desired_bedrooms - 1 
            and prop.get("price", 0) <= budget
            and _has_premium_features(prop)
        ]
        
        if lower_br_premium:
            options.append({
                "type": "premium_alternative",
                "bedrooms": desired_bedrooms - 1,
                "count": len(lower_br_premium),
                "value_prop": "Premium features and location",
                "message": f"Consider {desired_bedrooms-1}BR properties with premium amenities - often better value than older {desired_bedrooms}BR units"
            })
        
        # Option 2: Desired bedrooms slightly over budget
        over_budget_matches = [
            prop for prop in inventory
            if prop.get("bedrooms", 0) == desired_bedrooms
            and prop.get("price", 0) <= budget * 1.1  # 10% over budget
        ]
        
        if over_budget_matches:
            avg_overage = sum(prop.get("price", 0) for prop in over_budget_matches) / len(over_budget_matches) - budget
            options.append({
                "type": "stretch_budget",
                "bedrooms": desired_bedrooms,
                "count": len(over_budget_matches),
                "avg_overage": avg_overage,
                "value_prop": "Exact bedroom count with slight budget stretch",
                "message": f"{len(over_budget_matches)} {desired_bedrooms}BR properties available for ${avg_overage:,.0f} more - may be worth the investment"
            })
        
        # Option 3: Market timing recommendation
        market_insights = _get_market_timing_insights(location, desired_bedrooms, budget)
        if market_insights.get("should_wait"):
            options.append({
                "type": "market_timing",
                "recommendation": "wait_for_market",
                "timeline": market_insights.get("timeline", "3-6 months"),
                "message": market_insights.get("message", "Market conditions may improve for your criteria")
            })
        
        # Option 4: Expand location search
        if location:
            nearby_options = _find_nearby_location_alternatives(location, desired_bedrooms, budget)
            if nearby_options:
                options.append({
                    "type": "location_expansion",
                    "locations": nearby_options,
                    "message": f"Expanding search to nearby areas could unlock {desired_bedrooms}BR options within budget"
                })
        
        # Generate final recommendation
        recommendation = _generate_reconciliation_recommendation(options, desired_bedrooms, budget)
        
        # Log reconciliation analysis
        audit_log_event("budget_reconciliation", {
            "desired_bedrooms": desired_bedrooms,
            "budget": budget,
            "inventory_count": len(inventory),
            "exact_matches": len(exact_matches),
            "options_generated": len(options),
            "recommendation": recommendation
        })
        
        return {
            "has_exact_match": False,
            "exact_matches": 0,
            "alternatives": options,
            "recommendation": recommendation,
            "message": _format_reconciliation_message(options, desired_bedrooms, budget),
            "reasoning": f"Budget-bedroom mismatch resolved with {len(options)} alternative strategies"
        }
        
    except Exception as e:
        audit_log_event("reconciliation_error", {
            "error": str(e),
            "desired_bedrooms": desired_bedrooms,
            "budget": budget
        })
        
        return {
            "has_exact_match": False,
            "exact_matches": 0,
            "alternatives": [],
            "recommendation": "manual_review",
            "message": "Let me connect you with our team to explore all available options for your criteria.",
            "reasoning": f"Reconciliation failed: {str(e)}"
        }

def _analyze_inventory_by_bedrooms(inventory: List[Dict[str, Any]], budget: int) -> Dict[str, Any]:
    """Analyze inventory distribution by bedroom count and price ranges."""
    analysis = {
        "total_properties": len(inventory),
        "within_budget": len([p for p in inventory if p.get("price", 0) <= budget]),
        "by_bedrooms": {},
        "price_ranges": {}
    }
    
    for prop in inventory:
        bedrooms = prop.get("bedrooms", 0)
        price = prop.get("price", 0)
        
        # Count by bedrooms
        if bedrooms not in analysis["by_bedrooms"]:
            analysis["by_bedrooms"][bedrooms] = {"count": 0, "avg_price": 0, "within_budget": 0}
        
        analysis["by_bedrooms"][bedrooms]["count"] += 1
        if price <= budget:
            analysis["by_bedrooms"][bedrooms]["within_budget"] += 1
    
    # Calculate average prices
    for bedrooms in analysis["by_bedrooms"]:
        bedroom_props = [p for p in inventory if p.get("bedrooms", 0) == bedrooms]
        if bedroom_props:
            analysis["by_bedrooms"][bedrooms]["avg_price"] = sum(p.get("price", 0) for p in bedroom_props) / len(bedroom_props)
    
    return analysis

def _has_premium_features(property_data: Dict[str, Any]) -> bool:
    """Check if property has premium features that justify lower bedroom count."""
    amenities = property_data.get("amenities", {})
    details = property_data.get("details", {})
    
    premium_indicators = [
        amenities.get("pool", False),
        amenities.get("gym", False),
        amenities.get("concierge", False),
        amenities.get("balcony", False),
        details.get("year_built", 0) >= 2020,  # New construction
        details.get("floor", 0) >= 10,  # High floor
        details.get("sqft", 0) >= 1200  # Spacious
    ]
    
    return sum(premium_indicators) >= 3  # At least 3 premium features

def _get_market_timing_insights(location: str, bedrooms: int, budget: int) -> Dict[str, Any]:
    """Get market timing insights for the specific criteria."""
    try:
        # Query recent price trends (simplified - would use real market data)
        recent_sales = supabase.table("properties")\
            .select("price, created_at")\
            .eq("location", location)\
            .eq("bedrooms", bedrooms)\
            .gte("created_at", (datetime.now() - timedelta(days=90)).isoformat())\
            .execute()
        
        if not recent_sales.data or len(recent_sales.data) < 3:
            return {"should_wait": False}
        
        prices = [prop["price"] for prop in recent_sales.data]
        avg_recent_price = sum(prices) / len(prices)
        
        # Simple trend analysis
        if avg_recent_price > budget * 1.2:  # 20% over budget
            return {
                "should_wait": True,
                "timeline": "3-6 months",
                "message": f"Recent {bedrooms}BR sales in {location} average ${avg_recent_price:,.0f}. Market may cool in coming months.",
                "current_avg": avg_recent_price
            }
        
        return {"should_wait": False}
        
    except Exception:
        return {"should_wait": False}

def _find_nearby_location_alternatives(location: str, bedrooms: int, budget: int) -> List[str]:
    """Find nearby locations with better inventory for the criteria."""
    try:
        # Simplified nearby location mapping (would use real geographic data)
        location_alternatives = {
            "Miami": ["Coral Gables", "Aventura", "Doral"],
            "Orlando": ["Winter Park", "Altamonte Springs", "Lake Mary"],
            "Tampa": ["St. Petersburg", "Clearwater", "Brandon"]
        }
        
        nearby_locations = location_alternatives.get(location, [])
        viable_alternatives = []
        
        for alt_location in nearby_locations:
            # Check if alternative location has inventory
            alt_inventory = supabase.table("properties")\
                .select("*")\
                .eq("location", alt_location)\
                .eq("bedrooms", bedrooms)\
                .lte("price", budget)\
                .execute()
            
            if alt_inventory.data and len(alt_inventory.data) >= 2:
                viable_alternatives.append(alt_location)
        
        return viable_alternatives[:2]  # Return top 2 alternatives
        
    except Exception:
        return []

def _generate_reconciliation_recommendation(
    options: List[Dict[str, Any]], 
    desired_bedrooms: int, 
    budget: int
) -> str:
    """Generate the best reconciliation recommendation based on available options."""
    if not options:
        return "expand_search"
    
    # Priority order for recommendations
    option_priorities = {
        "premium_alternative": 1,  # Best value proposition
        "stretch_budget": 2,       # Meets exact needs with small compromise
        "location_expansion": 3,   # Geographic flexibility
        "market_timing": 4         # Temporal strategy
    }
    
    # Sort options by priority
    sorted_options = sorted(options, key=lambda x: option_priorities.get(x["type"], 5))
    
    return sorted_options[0]["type"]

def _format_reconciliation_message(
    options: List[Dict[str, Any]], 
    desired_bedrooms: int, 
    budget: int
) -> str:
    """Format a natural language message explaining reconciliation options."""
    if not options:
        return f"I don't see {desired_bedrooms}BR properties within your ${budget:,} budget right now, but let me explore some alternatives for you."
    
    message_parts = [
        f"I understand you're looking for {desired_bedrooms}BR within ${budget:,}. Here are some great alternatives:"
    ]
    
    for i, option in enumerate(options[:2], 1):  # Show top 2 options
        if option["type"] == "premium_alternative":
            message_parts.append(
                f"{i}. {option['count']} premium {option['bedrooms']}BR properties with high-end amenities - often better value than older {desired_bedrooms}BR units"
            )
        elif option["type"] == "stretch_budget":
            message_parts.append(
                f"{i}. {option['count']} {desired_bedrooms}BR properties for about ${option['avg_overage']:,.0f} more - may be worth the investment"
            )
        elif option["type"] == "location_expansion":
            locations = ", ".join(option["locations"])
            message_parts.append(
                f"{i}. Expanding to nearby areas like {locations} could unlock more {desired_bedrooms}BR options"
            )
        elif option["type"] == "market_timing":
            message_parts.append(
                f"{i}. Market timing suggests waiting {option['timeline']} might bring better {desired_bedrooms}BR inventory"
            )
    
    message_parts.append("Which approach interests you most?")
    
    return "\n\n".join(message_parts)

def calculate_temporal_qualification_adjustments(
    lead_data: Dict[str, Any],
    base_score: float
) -> Dict[str, Any]:
    """
    Calculate temporal adjustments to qualification score based on engagement history.
    
    Args:
        lead_data: Lead information including engagement history
        base_score: Base qualification score before temporal adjustments
        
    Returns:
        Dictionary with adjusted score and reasoning
    """
    try:
        adjustments = []
        adjusted_score = base_score
        
        # Adjustment 1: Re-engagement after long absence
        last_interaction = lead_data.get("last_interaction_at")
        if last_interaction:
            days_since = (datetime.now() - datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))).days
            if days_since > 30:
                adjustment = 0.15
                adjusted_score += adjustment
                adjustments.append(f"Re-engaged after {days_since} days (+{adjustment})")
        
        # Adjustment 2: Multiple prior showings with higher budget properties
        prior_showings = lead_data.get("prior_interests", [])
        if len(prior_showings) > 2:
            avg_viewed_price = sum(interest.get("price", 0) for interest in prior_showings) / len(prior_showings)
            current_budget = lead_data.get("budget", 0)
            
            if avg_viewed_price > current_budget:
                adjustment = 0.2
                adjusted_score += adjustment
                adjustments.append(f"Upsell potential - viewed higher priced properties (+{adjustment})")
        
        # Adjustment 3: Engagement trajectory
        trajectory = lead_data.get("engagement_trajectory", "stable")
        if trajectory == "escalating":
            adjustment = 0.1
            adjusted_score += adjustment
            adjustments.append(f"Escalating engagement (+{adjustment})")
        elif trajectory == "cooling":
            adjustment = -0.1
            adjusted_score += adjustment
            adjustments.append(f"Cooling engagement ({adjustment})")
        
        # Adjustment 4: High-value lead indicators
        budget = lead_data.get("budget", 0)
        if budget > 500000:
            adjustment = 0.15
            adjusted_score += adjustment
            adjustments.append(f"High-value lead (${budget:,}) (+{adjustment})")
        
        # Adjustment 5: Timeline urgency
        timeline = lead_data.get("timeline", "")
        if timeline == "immediate":
            adjustment = 0.2
            adjusted_score += adjustment
            adjustments.append(f"Immediate timeline (+{adjustment})")
        elif timeline == "1-3months":
            adjustment = 0.1
            adjusted_score += adjustment
            adjustments.append(f"Near-term timeline (+{adjustment})")
        
        # Cap the score at 1.0
        adjusted_score = min(adjusted_score, 1.0)
        
        # Log temporal adjustments
        audit_log_event("temporal_qualification_adjustment", {
            "lead_id": lead_data.get("user_id"),
            "base_score": base_score,
            "adjusted_score": adjusted_score,
            "adjustments": adjustments,
            "total_adjustment": adjusted_score - base_score
        })
        
        return {
            "adjusted_score": adjusted_score,
            "base_score": base_score,
            "total_adjustment": adjusted_score - base_score,
            "adjustments": adjustments,
            "reasoning": f"Applied {len(adjustments)} temporal adjustments: {'; '.join(adjustments)}"
        }
        
    except Exception as e:
        audit_log_event("temporal_adjustment_error", {
            "error": str(e),
            "lead_data": lead_data,
            "base_score": base_score
        })
        
        return {
            "adjusted_score": base_score,
            "base_score": base_score,
            "total_adjustment": 0,
            "adjustments": [],
            "reasoning": f"Temporal adjustment failed: {str(e)}"
        }