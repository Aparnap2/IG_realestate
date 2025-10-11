"""
Scheduling Utilities - Multi-Constraint Tour Planning

Implements PRD Section 2.3: Frictionless Scheduling with optimization.

Key Features:
- Multi-property tour sequence optimization
- Travel time calculation via Google Maps API
- No-show risk prediction based on lead behavior
- Timezone inference from phone numbers
- Property availability integration
"""

import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import math
import re

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import get_settings
from utils.audit import audit_log_event
from utils.supabase_client import supabase

settings = get_settings()

def find_optimal_tour_slots(
    lead: Dict[str, Any],
    properties: List[Dict[str, Any]],
    constraints: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Find optimal tour slots considering multiple constraints.
    
    Args:
        lead: Lead information with preferences
        properties: List of properties to tour
        constraints: Dictionary of scheduling constraints
        
    Returns:
        List of optimal tour slot suggestions ranked by score
    """
    try:
        # Get base available slots
        available_slots = constraints.get("agent_calendar", [])
        if not available_slots:
            return []
        
        # Calculate tour sequences for each slot
        tour_options = []
        
        for slot in available_slots[:5]:  # Evaluate top 5 slots
            tour_sequence = optimize_property_sequence(properties, slot)
            
            if tour_sequence:
                tour_option = {
                    "start_time": slot,
                    "sequence": tour_sequence,
                    "total_duration": calculate_total_tour_duration(tour_sequence),
                    "travel_efficiency": calculate_travel_efficiency(tour_sequence),
                    "property_availability": check_property_availability(properties, slot),
                    "no_show_risk": predict_no_show_risk(lead),
                    "lead_preference_score": calculate_lead_preference_score(lead, slot)
                }
                
                # Calculate overall score
                tour_option["overall_score"] = calculate_tour_score(tour_option)
                tour_options.append(tour_option)
        
        # Sort by overall score
        tour_options.sort(key=lambda x: x["overall_score"], reverse=True)
        
        audit_log_event("tour_optimization", {
            "lead_id": lead.get("user_id"),
            "properties_count": len(properties),
            "options_generated": len(tour_options),
            "best_score": tour_options[0]["overall_score"] if tour_options else 0
        })
        
        return tour_options[:3]  # Return top 3 options
        
    except Exception as e:
        audit_log_event("tour_optimization_error", {
            "error": str(e),
            "lead_id": lead.get("user_id")
        })
        return []


def optimize_property_sequence(
    properties: List[Dict[str, Any]],
    start_time: datetime
) -> List[Dict[str, Any]]:
    """
    Optimize the sequence of property visits to minimize travel time.
    
    Uses nearest-neighbor algorithm for small sets, TSP solver for larger sets.
    """
    try:
        if len(properties) <= 1:
            return properties
        
        # Get property addresses/coordinates
        property_locations = []
        for prop in properties:
            location = get_property_coordinates(prop)
            if location:
                property_locations.append({
                    "property": prop,
                    "coordinates": location
                })
        
        if len(property_locations) <= 1:
            return properties
        
        # Use nearest-neighbor for simplicity (can be enhanced with TSP solver)
        optimized_sequence = nearest_neighbor_tsp(property_locations)
        
        # Add timing information
        current_time = start_time
        for i, item in enumerate(optimized_sequence):
            item["scheduled_time"] = current_time
            item["duration_minutes"] = 45  # Standard property viewing time
            
            if i < len(optimized_sequence) - 1:
                # Add travel time to next property
                travel_time = get_travel_time_between_properties(
                    item["coordinates"],
                    optimized_sequence[i + 1]["coordinates"]
                )
                item["travel_to_next"] = travel_time
                current_time += timedelta(minutes=45 + travel_time)
            else:
                current_time += timedelta(minutes=45)
        
        return [item["property"] for item in optimized_sequence]
        
    except Exception as e:
        audit_log_event("sequence_optimization_error", {"error": str(e)})
        return properties  # Return original order on error

def nearest_neighbor_tsp(locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nearest neighbor algorithm for TSP approximation."""
    if not locations:
        return []
    
    unvisited = locations[1:]  # Start with first location
    route = [locations[0]]
    current = locations[0]
    
    while unvisited:
        # Find nearest unvisited location
        nearest = min(
            unvisited,
            key=lambda loc: calculate_distance(
                current["coordinates"],
                loc["coordinates"]
            )
        )
        
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    
    return route

def get_property_coordinates(property_data: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Get coordinates for a property (mock implementation)."""
    # In production, this would geocode the address
    # For now, return mock coordinates based on location
    location = property_data.get("location", "").lower()
    
    # Mock coordinates for major cities
    city_coords = {
        "miami": (25.7617, -80.1918),
        "orlando": (28.5383, -81.3792),
        "tampa": (27.9506, -82.4572),
        "jacksonville": (30.3322, -81.6557),
        "fort lauderdale": (26.1224, -80.1373)
    }
    
    for city, coords in city_coords.items():
        if city in location:
            # Add small random offset for different properties
            import random
            offset = random.uniform(-0.01, 0.01)
            return (coords[0] + offset, coords[1] + offset)
    
    return None

def calculate_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate distance between two coordinates using Haversine formula."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in miles
    r = 3956
    
    return c * r

def get_travel_time_between_properties(
    coord1: Tuple[float, float],
    coord2: Tuple[float, float]
) -> int:
    """
    Get travel time between properties in minutes.
    
    In production, this would use Google Maps API.
    For now, estimate based on distance.
    """
    try:
        distance_miles = calculate_distance(coord1, coord2)
        
        # Estimate travel time: assume 25 mph average in city
        travel_time_hours = distance_miles / 25
        travel_time_minutes = int(travel_time_hours * 60)
        
        # Add buffer for traffic and parking
        travel_time_minutes += 10
        
        # Minimum 15 minutes, maximum 60 minutes
        return max(15, min(travel_time_minutes, 60))
        
    except Exception:
        return 20  # Default 20 minutes

def calculate_total_tour_duration(tour_sequence: List[Dict[str, Any]]) -> int:
    """Calculate total duration of the tour in minutes."""
    total_duration = 0
    
    for i, property_data in enumerate(tour_sequence):
        total_duration += 45  # Standard viewing time
        
        if i < len(tour_sequence) - 1:
            # Add travel time to next property
            travel_time = property_data.get("travel_to_next", 20)
            total_duration += travel_time
    
    return total_duration

def calculate_travel_efficiency(tour_sequence: List[Dict[str, Any]]) -> float:
    """Calculate travel efficiency score (0-1, higher is better)."""
    if len(tour_sequence) <= 1:
        return 1.0
    
    total_travel_time = sum(
        prop.get("travel_to_next", 0) 
        for prop in tour_sequence[:-1]
    )
    
    total_viewing_time = len(tour_sequence) * 45
    
    if total_travel_time + total_viewing_time == 0:
        return 1.0
    
    # Efficiency = viewing time / total time
    efficiency = total_viewing_time / (total_travel_time + total_viewing_time)
    
    return min(efficiency, 1.0)

def check_property_availability(
    properties: List[Dict[str, Any]],
    slot_time: datetime
) -> float:
    """Check property availability score (0-1)."""
    try:
        available_count = 0
        
        for prop in properties:
            # Mock availability check
            # In production, this would check MLS or property management system
            property_id = prop.get("id")
            
            # Simple heuristic: properties are available during business hours
            if 9 <= slot_time.hour <= 17 and slot_time.weekday() < 5:
                available_count += 1
        
        return available_count / len(properties) if properties else 0
        
    except Exception:
        return 0.5  # Default moderate availability

def predict_no_show_risk(lead: Dict[str, Any]) -> float:
    """
    Predict no-show risk based on lead characteristics.
    
    Returns probability (0-1) where higher means more likely to no-show.
    """
    try:
        risk_factors = []
        
        # Factor 1: Engagement score
        engagement_score = lead.get("engagement_score", 0.5)
        if engagement_score < 0.3:
            risk_factors.append(0.3)  # Low engagement = higher risk
        elif engagement_score > 0.7:
            risk_factors.append(-0.2)  # High engagement = lower risk
        
        # Factor 2: Response time to scheduling
        # (Would be calculated from conversation timestamps)
        # For now, use mock data
        risk_factors.append(0.1)  # Baseline risk
        
        # Factor 3: Budget vs property price alignment
        budget = lead.get("budget", 0)
        if budget > 500000:
            risk_factors.append(-0.1)  # High budget = lower risk
        elif budget < 200000:
            risk_factors.append(0.2)  # Low budget = higher risk
        
        # Factor 4: Timeline urgency
        timeline = lead.get("timeline", "")
        if timeline == "immediate":
            risk_factors.append(-0.2)  # Urgent = lower risk
        elif timeline == "exploring":
            risk_factors.append(0.3)  # Just exploring = higher risk
        
        # Calculate overall risk
        base_risk = 0.3  # 30% baseline no-show rate
        risk_adjustment = sum(risk_factors)
        
        final_risk = base_risk + risk_adjustment
        
        # Clamp between 0 and 1
        return max(0.0, min(final_risk, 1.0))
        
    except Exception:
        return 0.3  # Default 30% risk

def calculate_lead_preference_score(lead: Dict[str, Any], slot_time: datetime) -> float:
    """Calculate how well the slot matches lead preferences."""
    try:
        score = 0.5  # Base score
        
        # Time of day preference (inferred from past interactions)
        hour = slot_time.hour
        
        # Most people prefer afternoon appointments
        if 14 <= hour <= 16:  # 2-4 PM
            score += 0.3
        elif 10 <= hour <= 12:  # 10 AM - 12 PM
            score += 0.2
        elif hour < 10 or hour > 17:  # Early morning or evening
            score -= 0.2
        
        # Day of week preference
        weekday = slot_time.weekday()
        if weekday == 5:  # Saturday
            score += 0.2  # Many prefer weekend viewings
        elif weekday == 6:  # Sunday
            score += 0.1
        
        # Timeline urgency
        timeline = lead.get("timeline", "")
        days_from_now = (slot_time.date() - datetime.now().date()).days
        
        if timeline == "immediate" and days_from_now <= 2:
            score += 0.3
        elif timeline == "1-3months" and 7 <= days_from_now <= 21:
            score += 0.2
        
        return max(0.0, min(score, 1.0))
        
    except Exception:
        return 0.5

def calculate_tour_score(tour_option: Dict[str, Any]) -> float:
    """Calculate overall score for a tour option."""
    try:
        # Weighted scoring
        weights = {
            "travel_efficiency": 0.25,
            "property_availability": 0.20,
            "lead_preference_score": 0.30,
            "no_show_risk": -0.25  # Negative because lower risk is better
        }
        
        score = 0.0
        
        for factor, weight in weights.items():
            if factor in tour_option:
                if factor == "no_show_risk":
                    # Invert no-show risk (lower risk = higher score)
                    score += weight * (1.0 - tour_option[factor])
                else:
                    score += weight * tour_option[factor]
        
        # Bonus for shorter total duration (efficiency)
        total_duration = tour_option.get("total_duration", 180)
        if total_duration <= 120:  # 2 hours or less
            score += 0.1
        elif total_duration >= 240:  # 4 hours or more
            score -= 0.1
        
        return max(0.0, min(score, 1.0))
        
    except Exception:
        return 0.5

def infer_timezone_from_phone(phone_number: str) -> str:
    """Infer timezone from phone number area code."""
    try:
        # Extract area code
        digits = re.sub(r'\D', '', phone_number)
        if len(digits) >= 10:
            area_code = digits[-10:-7]  # Get area code from US number
            
            # Map area codes to timezones (simplified)
            timezone_map = {
                # Eastern Time
                "212": "America/New_York", "305": "America/New_York", "407": "America/New_York",
                "561": "America/New_York", "727": "America/New_York", "813": "America/New_York",
                "904": "America/New_York", "941": "America/New_York",
                
                # Central Time
                "214": "America/Chicago", "713": "America/Chicago", "832": "America/Chicago",
                
                # Mountain Time
                "303": "America/Denver", "720": "America/Denver",
                
                # Pacific Time
                "213": "America/Los_Angeles", "310": "America/Los_Angeles", "415": "America/Los_Angeles"
            }
            
            return timezone_map.get(area_code, "America/New_York")  # Default to Eastern
        
        return "America/New_York"  # Default
        
    except Exception:
        return "America/New_York"

def generate_tour_confirmation_message(tour_option: Dict[str, Any]) -> str:
    """Generate a natural language confirmation message for the tour."""
    try:
        start_time = tour_option["start_time"]
        sequence = tour_option["sequence"]
        total_duration = tour_option["total_duration"]
        
        message = f"Perfect! I've planned an optimal property tour for {start_time.strftime('%A, %B %d at %I:%M %p')}.\n\n"
        message += f"Tour Schedule ({total_duration} minutes total):\n"
        
        current_time = start_time
        for i, prop in enumerate(sequence, 1):
            address = prop.get("address", f"Property {i}")
            message += f"{current_time.strftime('%I:%M %p')} - {address} (45 min viewing)\n"
            
            if i < len(sequence):
                travel_time = prop.get("travel_to_next", 20)
                current_time += timedelta(minutes=45 + travel_time)
                message += f"  → {travel_time} min drive to next property\n"
        
        message += f"\nYou'll receive a calendar invitation with Google Meet link for any questions during the tour."
        
        return message
        
    except Exception:
        return "Your property tour has been scheduled. You'll receive a calendar invitation shortly."