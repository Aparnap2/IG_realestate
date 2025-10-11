"""
Revenue Intelligence & Analytics

Implements PRD Section 2.5: Revenue Intelligence & Attribution.

Key Features:
- Lead-to-close attribution with temporal causality
- Agent performance metrics and optimization insights
- Inventory performance analysis
- Conversion funnel analytics
- ROI and revenue tracking
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import statistics

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import get_settings
from utils.audit import audit_log_event, query_audit_events
from utils.supabase_client import supabase

settings = get_settings()

def calculate_lead_attribution(
    lead_id: str,
    time_window_days: int = 90
) -> Dict[str, Any]:
    """
    Calculate revenue attribution for a specific lead through agent actions.
    
    Args:
        lead_id: Lead identifier
        time_window_days: Time window for attribution analysis
        
    Returns:
        Dictionary with attribution analysis
    """
    try:
        # Get lead's journey from audit logs
        cutoff_date = datetime.now() - timedelta(days=time_window_days)
        
        lead_events = query_audit_events(
            entity_id=lead_id,
            start_date=cutoff_date,
            limit=1000
        )
        
        if not lead_events:
            return {
                "lead_id": lead_id,
                "attribution_score": 0,
                "journey_stages": [],
                "agent_contributions": {},
                "conversion_events": [],
                "total_interactions": 0
            }
        
        # Analyze journey stages
        journey_stages = _analyze_journey_stages(lead_events)
        
        # Calculate agent contributions
        agent_contributions = _calculate_agent_contributions(lead_events)
        
        # Identify conversion events
        conversion_events = _identify_conversion_events(lead_events)
        
        # Calculate attribution score
        attribution_score = _calculate_attribution_score(
            journey_stages, agent_contributions, conversion_events
        )
        
        result = {
            "lead_id": lead_id,
            "attribution_score": attribution_score,
            "journey_stages": journey_stages,
            "agent_contributions": agent_contributions,
            "conversion_events": conversion_events,
            "total_interactions": len(lead_events),
            "analysis_date": datetime.now().isoformat()
        }
        
        audit_log_event("attribution_calculated", {
            "lead_id": lead_id,
            "attribution_score": attribution_score,
            "total_interactions": len(lead_events)
        })
        
        return result
        
    except Exception as e:
        audit_log_event("attribution_calculation_error", {
            "error": str(e),
            "lead_id": lead_id
        })
        return {
            "lead_id": lead_id,
            "attribution_score": 0,
            "error": str(e)
        }

def analyze_agent_performance(
    time_period_days: int = 30,
    agent_type: str = None
) -> Dict[str, Any]:
    """
    Analyze agent performance metrics.
    
    Args:
        time_period_days: Analysis time period
        agent_type: Specific agent type to analyze (optional)
        
    Returns:
        Agent performance analysis
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=time_period_days)
        
        # Get agent events
        agent_events = query_audit_events(
            agent_type=agent_type,
            start_date=cutoff_date,
            limit=10000
        )
        
        if not agent_events:
            return {"error": "No agent events found"}
        
        # Group by agent type
        agent_metrics = {}
        
        for event in agent_events:
            agent = event.get("agent_type", "unknown")
            
            if agent not in agent_metrics:
                agent_metrics[agent] = {
                    "total_actions": 0,
                    "successful_actions": 0,
                    "response_times": [],
                    "conversion_events": 0,
                    "error_rate": 0,
                    "unique_leads": set()
                }
            
            metrics = agent_metrics[agent]
            metrics["total_actions"] += 1
            metrics["unique_leads"].add(event.get("entity_id"))
            
            # Analyze event success
            payload = event.get("payload", {})
            if _is_successful_action(event):
                metrics["successful_actions"] += 1
            
            # Track conversion events
            if _is_conversion_event(event):
                metrics["conversion_events"] += 1
            
            # Calculate response time (simplified)
            if "response_time" in payload:
                metrics["response_times"].append(payload["response_time"])
        
        # Calculate final metrics
        performance_summary = {}
        
        for agent, metrics in agent_metrics.items():
            metrics["unique_leads"] = len(metrics["unique_leads"])
            metrics["success_rate"] = (
                metrics["successful_actions"] / metrics["total_actions"]
                if metrics["total_actions"] > 0 else 0
            )
            metrics["conversion_rate"] = (
                metrics["conversion_events"] / metrics["unique_leads"]
                if metrics["unique_leads"] > 0 else 0
            )
            metrics["avg_response_time"] = (
                statistics.mean(metrics["response_times"])
                if metrics["response_times"] else 0
            )
            
            performance_summary[agent] = metrics
        
        # Rank agents by performance
        ranked_agents = sorted(
            performance_summary.items(),
            key=lambda x: x[1]["conversion_rate"],
            reverse=True
        )
        
        return {
            "analysis_period": f"{time_period_days} days",
            "agent_performance": performance_summary,
            "ranked_agents": ranked_agents,
            "total_events_analyzed": len(agent_events),
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        audit_log_event("agent_performance_error", {"error": str(e)})
        return {"error": str(e)}

def analyze_inventory_performance(
    time_period_days: int = 60
) -> Dict[str, Any]:
    """
    Analyze property inventory performance.
    
    Args:
        time_period_days: Analysis time period
        
    Returns:
        Inventory performance analysis
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=time_period_days)
        
        # Get all properties
        properties_response = supabase.table("properties").select("*").execute()
        properties = properties_response.data or []
        
        # Get lead qualification events
        qualification_events = query_audit_events(
            event_type="lead_qualified",
            start_date=cutoff_date,
            limit=5000
        )
        
        # Analyze property interest patterns
        property_metrics = {}
        
        for prop in properties:
            prop_id = prop["id"]
            location = prop.get("location", "unknown")
            property_type = prop.get("property_type", "unknown")
            price = prop.get("price", 0)
            
            # Count qualified leads interested in similar properties
            interested_leads = 0
            for event in qualification_events:
                payload = event.get("payload", {})
                if (payload.get("location") == location and 
                    payload.get("property_type") == property_type and
                    abs(payload.get("budget", 0) - price) <= price * 0.2):  # Within 20%
                    interested_leads += 1
            
            property_metrics[prop_id] = {
                "property_id": prop_id,
                "location": location,
                "property_type": property_type,
                "price": price,
                "qualified_leads": interested_leads,
                "interest_score": interested_leads / max(1, len(qualification_events)) * 100,
                "amenities": prop.get("amenities", {}),
                "created_at": prop.get("created_at")
            }
        
        # Rank properties by performance
        ranked_properties = sorted(
            property_metrics.values(),
            key=lambda x: x["interest_score"],
            reverse=True
        )
        
        # Analyze trends by location and type
        location_performance = _analyze_location_performance(property_metrics)
        type_performance = _analyze_property_type_performance(property_metrics)
        
        return {
            "analysis_period": f"{time_period_days} days",
            "total_properties": len(properties),
            "total_qualified_leads": len(qualification_events),
            "top_performing_properties": ranked_properties[:10],
            "location_performance": location_performance,
            "property_type_performance": type_performance,
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        audit_log_event("inventory_performance_error", {"error": str(e)})
        return {"error": str(e)}

def generate_conversion_funnel_analysis(
    time_period_days: int = 30
) -> Dict[str, Any]:
    """
    Generate conversion funnel analysis.
    
    Args:
        time_period_days: Analysis time period
        
    Returns:
        Conversion funnel metrics
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=time_period_days)
        
        # Get all relevant events
        all_events = query_audit_events(
            start_date=cutoff_date,
            limit=10000
        )
        
        # Define funnel stages
        funnel_stages = {
            "leads_captured": set(),
            "leads_qualified": set(),
            "tours_scheduled": set(),
            "tours_completed": set(),
            "deals_closed": set()
        }
        
        # Categorize events by funnel stage
        for event in all_events:
            entity_id = event.get("entity_id")
            event_type = event.get("event_type")
            
            if event_type in ["instagram_message_received", "lead_created"]:
                funnel_stages["leads_captured"].add(entity_id)
            elif event_type == "lead_qualified":
                funnel_stages["leads_qualified"].add(entity_id)
            elif event_type in ["tour_scheduled", "calendar_event_created"]:
                funnel_stages["tours_scheduled"].add(entity_id)
            elif event_type == "tour_completed":
                funnel_stages["tours_completed"].add(entity_id)
            elif event_type == "deal_closed":
                funnel_stages["deals_closed"].add(entity_id)
        
        # Calculate conversion rates
        total_leads = len(funnel_stages["leads_captured"])
        
        funnel_metrics = {
            "leads_captured": {
                "count": total_leads,
                "percentage": 100.0
            }
        }
        
        previous_count = total_leads
        stage_order = ["leads_qualified", "tours_scheduled", "tours_completed", "deals_closed"]
        
        for stage in stage_order:
            count = len(funnel_stages[stage])
            percentage = (count / total_leads * 100) if total_leads > 0 else 0
            conversion_from_previous = (count / previous_count * 100) if previous_count > 0 else 0
            
            funnel_metrics[stage] = {
                "count": count,
                "percentage": percentage,
                "conversion_from_previous": conversion_from_previous
            }
            
            previous_count = count
        
        # Calculate overall conversion rate
        overall_conversion = (
            len(funnel_stages["deals_closed"]) / total_leads * 100
            if total_leads > 0 else 0
        )
        
        return {
            "analysis_period": f"{time_period_days} days",
            "funnel_metrics": funnel_metrics,
            "overall_conversion_rate": overall_conversion,
            "total_leads_analyzed": total_leads,
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        audit_log_event("funnel_analysis_error", {"error": str(e)})
        return {"error": str(e)}

def calculate_roi_metrics(
    time_period_days: int = 90
) -> Dict[str, Any]:
    """
    Calculate ROI and revenue metrics.
    
    Args:
        time_period_days: Analysis time period
        
    Returns:
        ROI analysis
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=time_period_days)
        
        # Get closed deals (mock data for now)
        closed_deals = query_audit_events(
            event_type="deal_closed",
            start_date=cutoff_date,
            limit=1000
        )
        
        # Calculate revenue metrics
        total_revenue = 0
        deal_values = []
        
        for deal in closed_deals:
            payload = deal.get("payload", {})
            deal_value = payload.get("deal_value", 0)
            if deal_value > 0:
                total_revenue += deal_value
                deal_values.append(deal_value)
        
        # Calculate costs (simplified)
        # In production, this would include actual operational costs
        estimated_costs = {
            "platform_hosting": 50 * (time_period_days / 30),  # $50/month
            "llm_api_costs": len(query_audit_events(start_date=cutoff_date)) * 0.01,  # $0.01 per API call
            "agent_time": len(closed_deals) * 2 * 50,  # 2 hours per deal at $50/hour
        }
        
        total_costs = sum(estimated_costs.values())
        
        # Calculate ROI
        roi = ((total_revenue - total_costs) / total_costs * 100) if total_costs > 0 else 0
        
        # Calculate averages
        avg_deal_value = statistics.mean(deal_values) if deal_values else 0
        median_deal_value = statistics.median(deal_values) if deal_values else 0
        
        return {
            "analysis_period": f"{time_period_days} days",
            "total_revenue": total_revenue,
            "total_costs": total_costs,
            "roi_percentage": roi,
            "deals_closed": len(closed_deals),
            "avg_deal_value": avg_deal_value,
            "median_deal_value": median_deal_value,
            "cost_breakdown": estimated_costs,
            "revenue_per_lead": total_revenue / max(1, len(closed_deals)),
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        audit_log_event("roi_calculation_error", {"error": str(e)})
        return {"error": str(e)}

# Helper functions

def _analyze_journey_stages(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze lead journey stages from events."""
    stages = []
    
    # Sort events by timestamp
    sorted_events = sorted(events, key=lambda x: x.get("timestamp", ""))
    
    current_stage = None
    stage_start = None
    
    for event in sorted_events:
        event_type = event.get("event_type")
        timestamp = event.get("timestamp")
        
        # Determine stage based on event type
        if event_type in ["instagram_message_received", "router_invoked"]:
            new_stage = "initial_contact"
        elif event_type == "lead_qualified":
            new_stage = "qualification"
        elif event_type in ["tour_scheduled", "calendar_event_created"]:
            new_stage = "scheduling"
        elif event_type == "nurture_action":
            new_stage = "nurturing"
        else:
            continue
        
        # If stage changed, record the previous stage
        if current_stage and new_stage != current_stage:
            stages.append({
                "stage": current_stage,
                "start_time": stage_start,
                "end_time": timestamp,
                "duration_hours": _calculate_duration_hours(stage_start, timestamp)
            })
        
        if new_stage != current_stage:
            current_stage = new_stage
            stage_start = timestamp
    
    # Add final stage
    if current_stage:
        stages.append({
            "stage": current_stage,
            "start_time": stage_start,
            "end_time": sorted_events[-1].get("timestamp"),
            "duration_hours": _calculate_duration_hours(stage_start, sorted_events[-1].get("timestamp"))
        })
    
    return stages

def _calculate_agent_contributions(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate each agent's contribution to the lead journey."""
    contributions = {}
    
    for event in events:
        agent_type = event.get("agent_type")
        if not agent_type:
            continue
        
        if agent_type not in contributions:
            contributions[agent_type] = {
                "total_actions": 0,
                "successful_actions": 0,
                "conversion_events": 0,
                "first_interaction": event.get("timestamp"),
                "last_interaction": event.get("timestamp")
            }
        
        contrib = contributions[agent_type]
        contrib["total_actions"] += 1
        contrib["last_interaction"] = event.get("timestamp")
        
        if _is_successful_action(event):
            contrib["successful_actions"] += 1
        
        if _is_conversion_event(event):
            contrib["conversion_events"] += 1
    
    # Calculate contribution scores
    for agent, contrib in contributions.items():
        contrib["success_rate"] = (
            contrib["successful_actions"] / contrib["total_actions"]
            if contrib["total_actions"] > 0 else 0
        )
        contrib["contribution_score"] = (
            contrib["conversion_events"] * 0.5 + 
            contrib["successful_actions"] * 0.3 + 
            contrib["total_actions"] * 0.2
        )
    
    return contributions

def _identify_conversion_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify key conversion events in the lead journey."""
    conversion_events = []
    
    conversion_event_types = [
        "lead_qualified",
        "tour_scheduled", 
        "calendar_event_created",
        "deal_closed"
    ]
    
    for event in events:
        if event.get("event_type") in conversion_event_types:
            conversion_events.append({
                "event_type": event.get("event_type"),
                "timestamp": event.get("timestamp"),
                "agent_type": event.get("agent_type"),
                "payload": event.get("payload", {})
            })
    
    return conversion_events

def _calculate_attribution_score(
    journey_stages: List[Dict[str, Any]],
    agent_contributions: Dict[str, Any],
    conversion_events: List[Dict[str, Any]]
) -> float:
    """Calculate overall attribution score for the lead."""
    try:
        score = 0.0
        
        # Stage completion bonus
        score += len(journey_stages) * 0.1
        
        # Agent contribution bonus
        for agent, contrib in agent_contributions.items():
            score += contrib["contribution_score"] * 0.2
        
        # Conversion events bonus
        score += len(conversion_events) * 0.3
        
        # Journey efficiency bonus (faster journey = higher score)
        total_duration = sum(stage.get("duration_hours", 0) for stage in journey_stages)
        if total_duration > 0 and total_duration < 168:  # Less than 1 week
            score += 0.2
        
        return min(score, 1.0)  # Cap at 1.0
        
    except Exception:
        return 0.5

def _is_successful_action(event: Dict[str, Any]) -> bool:
    """Determine if an event represents a successful action."""
    payload = event.get("payload", {})
    
    # Check for success indicators
    if payload.get("success") is True:
        return True
    
    if payload.get("error") or event.get("event_type") == "error":
        return False
    
    # Default to successful for most events
    return True

def _is_conversion_event(event: Dict[str, Any]) -> bool:
    """Determine if an event represents a conversion."""
    conversion_types = [
        "lead_qualified",
        "tour_scheduled",
        "calendar_event_created", 
        "deal_closed"
    ]
    
    return event.get("event_type") in conversion_types

def _calculate_duration_hours(start_time: str, end_time: str) -> float:
    """Calculate duration between two timestamps in hours."""
    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = end - start
        return duration.total_seconds() / 3600
    except Exception:
        return 0.0

def _analyze_location_performance(property_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze performance by location."""
    location_stats = {}
    
    for prop_id, metrics in property_metrics.items():
        location = metrics["location"]
        
        if location not in location_stats:
            location_stats[location] = {
                "total_properties": 0,
                "total_qualified_leads": 0,
                "avg_interest_score": 0,
                "avg_price": 0
            }
        
        stats = location_stats[location]
        stats["total_properties"] += 1
        stats["total_qualified_leads"] += metrics["qualified_leads"]
        stats["avg_interest_score"] += metrics["interest_score"]
        stats["avg_price"] += metrics["price"]
    
    # Calculate averages
    for location, stats in location_stats.items():
        if stats["total_properties"] > 0:
            stats["avg_interest_score"] /= stats["total_properties"]
            stats["avg_price"] /= stats["total_properties"]
    
    return location_stats

def _analyze_property_type_performance(property_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze performance by property type."""
    type_stats = {}
    
    for prop_id, metrics in property_metrics.items():
        prop_type = metrics["property_type"]
        
        if prop_type not in type_stats:
            type_stats[prop_type] = {
                "total_properties": 0,
                "total_qualified_leads": 0,
                "avg_interest_score": 0,
                "avg_price": 0
            }
        
        stats = type_stats[prop_type]
        stats["total_properties"] += 1
        stats["total_qualified_leads"] += metrics["qualified_leads"]
        stats["avg_interest_score"] += metrics["interest_score"]
        stats["avg_price"] += metrics["price"]
    
    # Calculate averages
    for prop_type, stats in type_stats.items():
        if stats["total_properties"] > 0:
            stats["avg_interest_score"] /= stats["total_properties"]
            stats["avg_price"] /= stats["total_properties"]
    
    return type_stats