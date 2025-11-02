"""
Phase 2: Rules-First Qualification Engine - Transparent Scoring System

This module implements transparent, rules-based qualification with LLM-powered
question mapping and scoring breakdown for the real estate qualification system.

Key Features:
- Transparent scoring rules with clear breakdown
- Real estate specific budget bands (3-5 lakh ranges)
- Question priority and conditional flow using LLM
- Qualification state machine with progressive gates
- Role/use case scoring for decision makers
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import json
import logging

from utils.audit import audit_log_event
from utils.supabase_client import supabase
from utils.llm_client import get_llm_response_sync
from config.industry_configs import get_industry_config

logger = logging.getLogger(__name__)


_LOCATION_ALTERNATIVES: Dict[str, Sequence[str]] = {
    "Miami": ("Coral Gables", "Aventura", "Doral", "Miami Shores"),
    "San Francisco": ("Oakland", "Berkeley", "Daly City"),
    "Austin": ("Round Rock", "Cedar Park", "Georgetown"),
    "New York": ("Brooklyn", "Queens", "Jersey City"),
}

# Real Estate Budget Bands (3-5 Lakh Ranges)
REAL_ESTATE_BUDGET_BANDS = {
    "entry_level": {
        "range": (300000, 500000),
        "description": "Entry Level (3-5 Lakh)",
        "score": 0.6,
        "questions": ["What's your budget for a 2-3 bedroom apartment?", "Are you looking for investment or personal use?"]
    },
    "mid_tier": {
        "range": (500000, 800000),
        "description": "Mid Tier (5-8 Lakh)", 
        "score": 0.7,
        "questions": ["What's your target budget range?", "Timeline for purchase?"]
    },
    "premium": {
        "range": (800000, 1200000),
        "description": "Premium (8-12 Lakh)",
        "score": 0.8,
        "questions": ["What amenities are important to you?", "Are you working with a specific location?"]
    },
    "luxury": {
        "range": (1200000, float('inf')),
        "description": "Luxury (12+ Lakh)",
        "score": 0.9,
        "questions": ["What luxury features do you prioritize?", "Do you have preferred developments?"]
    }
}

# Qualification State Machine States
QUALIFICATION_STATES = {
    "initial_contact": {
        "description": "First message - establishing interest",
        "threshold_score": 0.2,
        "next_state": "basic_qualification",
        "questions": 1
    },
    "basic_qualification": {
        "description": "Gathering budget, location, timeline",
        "threshold_score": 0.4,
        "next_state": "detailed_qualification", 
        "questions": 3
    },
    "detailed_qualification": {
        "description": "Role, use case, urgency assessment",
        "threshold_score": 0.6,
        "next_state": "scheduler_ready",
        "questions": 2
    },
    "scheduler_ready": {
        "description": "Ready for scheduling handover",
        "threshold_score": 0.75,
        "next_state": "scheduler",
        "questions": 0
    }
}

def generate_transparent_scoring_breakdown(
    lead_data: Dict[str, Any],
    industry_type: str = "real_estate"
) -> Dict[str, Any]:
    """
    Generate transparent scoring breakdown with LLM-powered analysis.
    
    Args:
        lead_data: Lead information dictionary
        industry_type: Industry for scoring context
        
    Returns:
        Transparent scoring breakdown with reasoning
    """
    try:
        # Get industry configuration
        industry_config = get_industry_config(industry_type)
        
        # Build scoring context for LLM
        scoring_context = {
            "lead_data": lead_data,
            "industry_config": industry_config.__dict__,
            "budget_bands": REAL_ESTATE_BUDGET_BANDS,
            "timestamp": datetime.now().isoformat()
        }
        
        # LLM-powered transparent scoring
        prompt = f"""
        Analyze this real estate lead with TRANSPARENT scoring rules:
        
        Lead Data: {json.dumps(lead_data, indent=2)}
        Budget Bands: {json.dumps(REAL_ESTATE_BUDGET_BANDS, indent=2)}
        
        Calculate score (0-1) using these TRANSPARENT rules:
        1. Budget Alignment (40%): How well budget matches real estate ranges
        2. Role Clarity (25%): Decision maker vs browser identification  
        3. Urgency Score (20%): Timeline and need level
        4. Use Case Clarity (10%): Personal vs investment clarity
        5. Engagement Quality (5%): Response specificity
        
        Return JSON with:
        {{
            "total_score": 0.75,
            "scoring_breakdown": {{
                "budget_score": 0.8,
                "role_clarity_score": 0.6, 
                "urgency_score": 0.7,
                "use_case_score": 0.8,
                "engagement_score": 0.6
            }},
            "budget_band_analysis": {{
                "detected_band": "mid_tier",
                "confidence": 0.9,
                "range_alignment": "good"
            }},
            "role_analysis": {{
                "identified_role": "buyer_decision_maker",
                "confidence": 0.7,
                "signals": ["mentioned budget", "specific timeline"]
            }},
            "scoring_explanation": "Clear reasoning for each score component",
            "qualification_state": "basic_qualification",
            "next_actions": ["Ask about timeline", "Confirm role"]
        }}
        """
        
        response = get_llm_response_sync(prompt)
        
        try:
            scoring_result = json.loads(response)
        except json.JSONDecodeError:
            # Fallback parsing
            scoring_result = _fallback_scoring_calculation(lead_data)
        
        # Add audit logging
        audit_log_event("transparent_scoring_calculated", {
            "lead_id": lead_data.get("user_id", "unknown"),
            "score": scoring_result.get("total_score", 0.5),
            "state": scoring_result.get("qualification_state", "unknown"),
            "budget_band": scoring_result.get("budget_band_analysis", {}).get("detected_band", "unknown"),
            "role": scoring_result.get("role_analysis", {}).get("identified_role", "unknown")
        })
        
        return {
            "success": True,
            "scoring_result": scoring_result,
            "timestamp": datetime.now().isoformat(),
            "audit_trail": "transparent_scoring_calculated"
        }
        
    except Exception as e:
        logger.error(f"Transparent scoring failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallback_score": _calculate_fallback_score(lead_data),
            "timestamp": datetime.now().isoformat()
        }

def _fallback_scoring_calculation(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback scoring when LLM analysis fails."""
    budget = lead_data.get("budget", 0)
    timeline = lead_data.get("timeline", "")
    role = lead_data.get("role", "")
    
    # Basic fallback scoring
    budget_score = 0.6 if budget >= 500000 else 0.4
    timeline_score = 0.7 if "immediate" in timeline.lower() else 0.5
    role_score = 0.8 if "buyer" in role.lower() else 0.5
    
    total_score = (budget_score * 0.4 + timeline_score * 0.3 + role_score * 0.3)
    
    return {
        "total_score": round(total_score, 2),
        "scoring_breakdown": {
            "budget_score": budget_score,
            "role_clarity_score": role_score,
            "urgency_score": timeline_score,
            "use_case_score": 0.5,
            "engagement_score": 0.5
        },
        "budget_band_analysis": {
            "detected_band": "mid_tier" if budget >= 500000 else "entry_level",
            "confidence": 0.6,
            "range_alignment": "partial"
        },
        "role_analysis": {
            "identified_role": "prospective_buyer",
            "confidence": 0.5,
            "signals": ["basic_inquiry"]
        },
        "scoring_explanation": "Fallback scoring due to LLM analysis failure",
        "qualification_state": "basic_qualification",
        "next_actions": ["Confirm timeline", "Gather more details"]
    }

def _calculate_fallback_score(lead_data: Dict[str, Any]) -> float:
    """Calculate basic fallback score."""
    score = 0.3  # Base score
    
    if lead_data.get("budget"):
        score += 0.2
    if lead_data.get("location"):
        score += 0.2
    if lead_data.get("timeline"):
        score += 0.2
        
    return min(score, 0.7)

def prioritize_questions_llm(
    lead_data: Dict[str, Any],
    asked_questions: List[str],
    current_state: str = "initial_contact"
) -> List[Dict[str, Any]]:
    """
    Use LLM to intelligently prioritize qualification questions.
    
    Args:
        lead_data: Current lead information
        asked_questions: Questions already asked
        current_state: Current qualification state
        
    Returns:
        Prioritized list of questions with reasoning
    """
    try:
        # Build question prioritization context
        context = {
            "lead_data": lead_data,
            "asked_questions": asked_questions,
            "current_state": current_state,
            "qualification_states": QUALIFICATION_STATES,
            "budget_bands": REAL_ESTATE_BUDGET_BANDS
        }
        
        prompt = f"""
        Prioritize qualification questions for this real estate lead:
        
        Lead Data: {json.dumps(lead_data, indent=2)}
        Asked Questions: {asked_questions}
        Current State: {current_state}
        
        Available question categories:
        1. BUDGET (High Priority) - Budget bands, price range
        2. LOCATION (High Priority) - Specific area, neighborhood
        3. TIMELINE (Medium Priority) - When looking to buy
        4. ROLE (Medium Priority) - Decision maker, first-time buyer
        5. USE CASE (Medium Priority) - Investment vs personal
        6. URGENCY (Low Priority) - How urgent is need
        7. PROPERTY_TYPE (Low Priority) - House, condo, etc.
        
        Based on current state "{current_state}", return 2-3 most important next questions:
        
        Return JSON:
        {{
            "prioritized_questions": [
                {{
                    "category": "budget",
                    "question": "What's your target budget range?",
                    "priority": 1,
                    "reasoning": "Need budget to show relevant properties",
                    "expected_impact": 0.3
                }}
            ],
            "state_transition": {{
                "from": "{current_state}",
                "to": "basic_qualification",
                "requirements": ["budget", "location"]
            }}
        }}
        """
        
        response = get_llm_response_sync(prompt)
        
        try:
            question_priorities = json.loads(response)
        except json.JSONDecodeError:
            question_priorities = _fallback_question_prioritization(lead_data, asked_questions)
        
        return question_priorities
        
    except Exception as e:
        logger.error(f"Question prioritization failed: {e}")
        return _fallback_question_prioritization(lead_data, asked_questions)

def _fallback_question_prioritization(lead_data: Dict[str, Any], asked_questions: List[str]) -> Dict[str, Any]:
    """Fallback question prioritization."""
    # Basic prioritization logic
    available_questions = [
        {
            "category": "budget",
            "question": "What's your approximate budget for this property?",
            "priority": 1,
            "reasoning": "Essential for property matching",
            "expected_impact": 0.3
        },
        {
            "category": "location", 
            "question": "What area or neighborhood are you interested in?",
            "priority": 2,
            "reasoning": "Needed for location-based searches",
            "expected_impact": 0.25
        },
        {
            "category": "timeline",
            "question": "When are you planning to make this purchase?",
            "priority": 3,
            "reasoning": "Urgency affects qualification score",
            "expected_impact": 0.2
        }
    ]
    
    # Filter out already asked questions
    filtered_questions = [
        q for q in available_questions
        if q["category"] not in asked_questions
    ][:3]
    
    return {
        "prioritized_questions": filtered_questions,
        "state_transition": {
            "from": "initial_contact",
            "to": "basic_qualification",
            "requirements": ["budget", "location"]
        }
    }

def assess_qualification_readiness(
    lead_data: Dict[str, Any],
    current_score: float,
    asked_questions: List[str]
) -> Dict[str, Any]:
    """
    Assess if lead is ready for scheduler handoff using rules-based gates.
    
    Args:
        lead_data: Lead information
        current_score: Current qualification score
        asked_questions: Questions already asked
        
    Returns:
        Readiness assessment with transparent criteria
    """
    try:
        # Calculate essential criteria
        essential_criteria = {
            "budget_known": bool(lead_data.get("budget") and lead_data.get("budget") > 0),
            "location_known": bool(lead_data.get("location") and lead_data.get("location").strip()),
            "timeline_known": bool(lead_data.get("timeline") and lead_data.get("timeline").strip()),
            "role_clarified": bool(lead_data.get("role") and lead_data.get("role").strip()),
            "use_case_clear": bool(lead_data.get("use_case") and lead_data.get("use_case").strip())
        }
        
        # Calculate completion percentage
        completed_criteria = sum(essential_criteria.values())
        total_criteria = len(essential_criteria)
        completion_percentage = (completed_criteria / total_criteria) * 100
        
        # LLM-powered readiness assessment
        readiness_context = {
            "lead_data": lead_data,
            "current_score": current_score,
            "essential_criteria": essential_criteria,
            "completion_percentage": completion_percentage,
            "asked_questions_count": len(asked_questions)
        }
        
        prompt = f"""
        Assess readiness for real estate scheduler handoff:
        
        Lead Data: {json.dumps(lead_data, indent=2)}
        Score: {current_score}
        Completion: {completion_percentage:.1f}%
        Essential Criteria: {json.dumps(essential_criteria, indent=2)}
        
        Qualification Gates:
        - Minimum Score: 0.75
        - Essential Info: Budget + Location + Timeline (80% criteria)
        - Quality Check: Clear role/use case
        
        Return JSON:
        {{
            "ready_for_scheduler": false,
            "readiness_score": 0.6,
            "blocking_factors": ["missing_role_clarity"],
            "missing_critical_info": ["role"],
            "next_steps": ["Clarify decision maker role", "Confirm use case"],
            "transparency_report": {{
                "score_threshold_met": false,
                "essential_info_complete": false,
                "quality_gate_passed": false,
                "overall_readiness": "partial"
            }}
        }}
        """
        
        response = get_llm_response_sync(prompt)
        
        try:
            readiness_assessment = json.loads(response)
        except json.JSONDecodeError:
            readiness_assessment = _fallback_readiness_assessment(lead_data, current_score, essential_criteria)
        
        return readiness_assessment
        
    except Exception as e:
        logger.error(f"Readiness assessment failed: {e}")
        return _fallback_readiness_assessment(lead_data, current_score, essential_criteria)

def _fallback_readiness_assessment(
    lead_data: Dict[str, Any], 
    current_score: float, 
    essential_criteria: Dict[str, bool]
) -> Dict[str, Any]:
    """Fallback readiness assessment."""
    completion_percentage = (sum(essential_criteria.values()) / len(essential_criteria)) * 100
    
    # Basic readiness logic
    score_ready = current_score >= 0.75
    info_ready = completion_percentage >= 80
    
    ready_for_scheduler = score_ready and info_ready
    
    missing_info = [k for k, v in essential_criteria.items() if not v]
    
    return {
        "ready_for_scheduler": ready_for_scheduler,
        "readiness_score": min(current_score, completion_percentage / 100),
        "blocking_factors": missing_info if not ready_for_scheduler else [],
        "missing_critical_info": missing_info,
        "next_steps": ["Complete missing information"] if missing_info else ["Ready for scheduling"],
        "transparency_report": {
            "score_threshold_met": score_ready,
            "essential_info_complete": info_ready,
            "quality_gate_passed": bool(lead_data.get("role") and lead_data.get("use_case")),
            "overall_readiness": "ready" if ready_for_scheduler else "partial"
        }
    }


def reconcile_budget_mismatch(
    *,
    desired_bedrooms: int,
    budget: Optional[int],
    inventory: Optional[Iterable[Dict[str, Any]]],
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Diagnose inventory vs. budget gaps and suggest recovery options."""

    budget_value = budget or 0

    if inventory is None:
        audit_log_event("qualifier_budget_reconciliation_error", {
            "error": "inventory_missing",
            "desired_bedrooms": desired_bedrooms,
            "budget": budget_value,
            "location": location,
        })
        return {
            "has_exact_match": False,
            "exact_matches": 0,
            "alternatives": [],
            "analysis": {"total_properties": 0, "within_budget": 0, "by_bedrooms": {}},
            "recommendation": "manual_review",
            "message": "Inventory data was unavailable. Let's review options together manually.",
            "reasoning": "error: inventory data missing",
        }

    inventory_list = list(inventory or [])

    try:
        analysis = _analyze_inventory_by_bedrooms(inventory_list, budget_value)
        exact_matches = [
            item
            for item in inventory_list
            if item.get("bedrooms") == desired_bedrooms
            and _safe_price(item) <= budget_value
            and _safe_price(item) > 0
        ]

        if exact_matches:
            message = (
                f"Great news! We found {len(exact_matches)} properties that match your "
                f"{desired_bedrooms}BR request within your ${budget_value:,.0f} budget."
            )
            return {
                "has_exact_match": True,
                "exact_matches": len(exact_matches),
                "alternatives": [],
                "analysis": analysis,
                "recommendation": "show_exact_matches",
                "message": message,
                "reasoning": "exact_match_found",
            }

        fallback_options = _build_fallback_options(inventory_list, desired_bedrooms, budget_value)

        if location:
            location_options = _find_nearby_location_alternatives(location, desired_bedrooms, budget_value)
            if location_options:
                fallback_options.append({
                    "type": "location_expansion",
                    "locations": location_options,
                })

        market_insights = _get_market_timing_insights(location, desired_bedrooms, budget_value)
        if market_insights.get("should_wait"):
            fallback_options.append({
                "type": "market_timing",
                "timeline": market_insights.get("timeline", "3-6 months"),
                "insights": market_insights,
            })

        recommendation = _generate_reconciliation_recommendation(fallback_options, desired_bedrooms, budget_value)
        message = _format_reconciliation_message(fallback_options, desired_bedrooms, budget_value)

        return {
            "has_exact_match": False,
            "exact_matches": 0,
            "alternatives": fallback_options,
            "analysis": analysis,
            "recommendation": recommendation,
            "message": message,
            "market_insights": market_insights,
            "reasoning": recommendation,
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        audit_log_event("qualifier_budget_reconciliation_error", {
            "error": str(exc),
            "desired_bedrooms": desired_bedrooms,
            "budget": budget_value,
            "location": location,
        })
        return {
            "has_exact_match": False,
            "exact_matches": 0,
            "alternatives": [],
            "analysis": {"total_properties": 0, "within_budget": 0, "by_bedrooms": {}},
            "recommendation": "manual_review",
            "message": "We could not reconcile the current listings. Let's review together manually.",
        }


def _analyze_inventory_by_bedrooms(inventory: Iterable[Dict[str, Any]], budget: int) -> Dict[str, Any]:
    """Generate bedroom-level statistics for available inventory."""

    inventory_list = list(inventory or [])
    analysis: Dict[str, Any] = {
        "total_properties": len(inventory_list),
        "within_budget": 0,
        "by_bedrooms": {},
    }

    for item in inventory_list:
        bedrooms = int(item.get("bedrooms") or 0)
        price = _safe_price(item)

        bucket = analysis["by_bedrooms"].setdefault(bedrooms, {
            "count": 0,
            "within_budget": 0,
            "prices": [],
        })
        bucket["count"] += 1
        if price:
            bucket["prices"].append(price)
            if price <= budget:
                bucket["within_budget"] += 1
                analysis["within_budget"] += 1

    for bedrooms, bucket in analysis["by_bedrooms"].items():
        prices = bucket["prices"]
        bucket["avg_price"] = mean(prices) if prices else 0
        bucket["min_price"] = min(prices) if prices else 0
        bucket["max_price"] = max(prices) if prices else 0
        bucket.pop("prices", None)

    return analysis


def _has_premium_features(property_data: Dict[str, Any]) -> bool:
    """Check if a property offers premium amenities or finishes."""

    amenities = (property_data or {}).get("amenities") or {}
    premium_flags = [
        amenities.get("pool"),
        amenities.get("gym"),
        amenities.get("concierge"),
        amenities.get("rooftop"),
    ]
    premium_score = sum(1 for flag in premium_flags if flag)

    details = (property_data or {}).get("details") or {}
    year_built = details.get("year_built") or property_data.get("year_built")
    floor = details.get("floor") or property_data.get("floor")
    sqft = details.get("sqft") or property_data.get("sqft")

    if year_built and isinstance(year_built, int) and year_built >= 2020:
        premium_score += 1
    if floor and isinstance(floor, int) and floor >= 10:
        premium_score += 1
    if sqft and isinstance(sqft, (int, float)) and sqft >= 1200:
        premium_score += 1

    return premium_score >= 2


def _get_market_timing_insights(
    location: Optional[str],
    bedrooms: int,
    budget: int,
) -> Dict[str, Any]:
    """Gather market pricing context to advise whether to wait."""

    if not location:
        return {"should_wait": False}

    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        query = (
            supabase
            .table("market_sales")
            .select("price, created_at")
            .eq("location", location)
            .eq("bedrooms", bedrooms)
            .gte("created_at", cutoff_date)
        )
        response = query.execute()
        rows = (response.data or []) if hasattr(response, "data") else (response or [])
        if len(rows) < 2:
            return {"should_wait": False}

        prices = [_safe_price(row) for row in rows if _safe_price(row)]
        if not prices:
            return {"should_wait": False}

        average_price = mean(prices)
        should_wait = average_price > budget * 1.05
        return {
            "should_wait": should_wait,
            "average_price": average_price,
            "sample_size": len(prices),
            "timeline": "3-6 months" if should_wait else "now",
            "message": (
                "Market timing suggests waiting ~3-6 months. Recent comparable sales "
                f"averaged ${average_price:,.0f} for {bedrooms}BR homes in {location}."
            ),
        }

    except Exception as exc:  # pragma: no cover - defensive path
        audit_log_event("market_insight_error", {"error": str(exc), "location": location})
        return {"should_wait": False}


def _find_nearby_location_alternatives(
    location: str,
    bedrooms: int,
    budget: int,
) -> List[str]:
    """Suggest nearby locations that have inventory within budget."""

    alternatives = list(_LOCATION_ALTERNATIVES.get(location, ()))
    if not alternatives:
        return []

    available: List[str] = []
    for alt in alternatives:
        try:
            query = (
                supabase
                .table("properties")
                .select("price, bedrooms")
                .eq("location", alt)
                .eq("bedrooms", bedrooms)
                .lte("price", budget)
            )
            response = query.execute()
            rows = (response.data or []) if hasattr(response, "data") else (response or [])
            if rows:
                available.append(alt)
        except Exception as exc:  # pragma: no cover - defensive path
            audit_log_event("location_alternative_error", {"error": str(exc), "location": location})
            return []

    return available


def _generate_reconciliation_recommendation(
    options: Sequence[Dict[str, Any]],
    bedrooms: int,
    budget: int,
) -> str:
    """Rank recovery strategies and return the top pick."""

    if not options:
        return "expand_search"

    priority = {
        "premium_alternative": 0,
        "stretch_budget": 1,
        "location_expansion": 2,
        "market_timing": 3,
    }

    sorted_options = sorted(options, key=lambda opt: priority.get(opt.get("type"), 99))
    return sorted_options[0]["type"]


def _format_reconciliation_message(
    options: Sequence[Dict[str, Any]],
    bedrooms: int,
    budget: int,
) -> str:
    """Craft a personable message summarizing reconciliation options."""

    budget_str = f"${budget:,.0f}"
    intro = f"I don't see {bedrooms}BR properties within your {budget_str} budget right now"

    if not options:
        return f"{intro}, but we can explore some alternatives together."

    option = options[0]
    opt_type = option.get("type")

    if opt_type == "premium_alternative":
        alt_bedrooms = option.get("bedrooms", bedrooms - 1)
        return (
            f"While you’re looking for {bedrooms}BR within {budget_str}, I found premium {alt_bedrooms}BR properties "
            "with high-end amenities that might surprise you."
        )

    if opt_type == "stretch_budget":
        overage = option.get("avg_overage", 0)
        overage_str = f"${overage:,.0f}"
        return (
            f"Since you’re looking for {bedrooms}BR within {budget_str}, the closest matches are {bedrooms}BR properties "
            f"for about {overage_str} over your target. They could be worth the investment."
        )

    if opt_type == "location_expansion":
        locations = ", ".join(option.get("locations", []))
        return (
            f"You're looking for {bedrooms}BR within {budget_str}. Let's explore nearby areas like {locations} that already "
            "have inventory fitting your budget."
        )

    if opt_type == "market_timing":
        timeline = option.get("timeline", "3-6 months")
        return (
            f"You’re looking for {bedrooms}BR within {budget_str}. Market timing suggests waiting {timeline} "
            "could unlock better opportunities."
        )

    return f"{intro}, so let's explore some alternatives."  # Fallback


def _build_fallback_options(
    inventory: Iterable[Dict[str, Any]],
    desired_bedrooms: int,
    budget: int,
) -> List[Dict[str, Any]]:
    """Assemble alternative strategies when exact matches are unavailable."""

    inventory_list = list(inventory or [])
    if not inventory_list:
        return []

    options: List[Dict[str, Any]] = []

    # Stretch budget option based on closest affordable listing
    closest = min(
        inventory_list,
        key=lambda item: (
            max(0, _safe_price(item) - budget),
            abs(desired_bedrooms - int(item.get("bedrooms") or 0)),
            _safe_price(item) or math.inf,
        ),
    )
    closest_price = _safe_price(closest)
    options.append({
        "type": "stretch_budget",
        "count": len(inventory_list),
        "bedrooms": int(closest.get("bedrooms") or desired_bedrooms),
        "avg_overage": max(0, closest_price - budget),
    })

    # Premium alternatives (smaller units with strong amenities or pricing signals)
    premium_candidates = [
        item
        for item in inventory_list
        if int(item.get("bedrooms") or 0) < desired_bedrooms
        and (
            _has_premium_features(item)
            or 0 < budget < _safe_price(item) <= budget * 1.15
        )
    ]
    if premium_candidates:
        best = max(premium_candidates, key=lambda item: _safe_price(item))
        options.append({
            "type": "premium_alternative",
            "count": len(premium_candidates),
            "bedrooms": int(best.get("bedrooms") or desired_bedrooms - 1),
        })

    return options


def calculate_temporal_qualification_adjustments(
    lead_data: Optional[Dict[str, Any]],
    base_score: float,
) -> Dict[str, Any]:
    """Apply temporal and contextual adjustments to a qualifier score."""

    if lead_data is None:
        audit_log_event("temporal_adjustment_error", {"error": "lead_data_none"})
        return {
            "adjusted_score": base_score,
            "total_adjustment": 0,
            "adjustments": [],
            "reasoning": "error: lead data unavailable",
        }

    adjustments: List[str] = []
    total_delta = 0.0

    try:
        last_seen = lead_data.get("last_interaction_at")
        if last_seen:
            try:
                last_dt = datetime.fromisoformat(str(last_seen))
                days_since = (datetime.now() - last_dt).days
                if days_since >= 30:
                    total_delta += 0.15
                    adjustments.append(f"Re-engaged after {days_since} days (+0.15)")
            except ValueError:
                pass

        prior_interests = lead_data.get("prior_interests") or []
        budget = lead_data.get("budget") or 0
        if isinstance(prior_interests, list) and prior_interests:
            high_value = [item for item in prior_interests if _safe_price(item) > budget and _safe_price(item) > 0]
            if len(high_value) >= 2:
                total_delta += 0.2
                adjustments.append("Upsell potential from prior tours (+0.2)")

        trajectory = (lead_data.get("engagement_trajectory") or "").lower()
        if trajectory == "escalating":
            total_delta += 0.1
            adjustments.append("Escalating engagement trend (+0.1)")
        elif trajectory == "cooling":
            total_delta -= 0.1
            adjustments.append("Cooling engagement trend (-0.1)")

        if budget and budget >= 550_000:
            total_delta += 0.15
            adjustments.append("High-value lead budget (+0.15)")

        timeline = (lead_data.get("timeline") or "").lower()
        if timeline in {"immediate", "asap", "now"}:
            total_delta += 0.2
            adjustments.append("Immediate timeline (+0.2)")

        adjusted = min(1.0, max(0.0, base_score + total_delta))
        reasoning = ", ".join(adjustments) if adjustments else "No temporal adjustments applied"

        return {
            "adjusted_score": adjusted,
            "total_adjustment": round(total_delta, 4),
            "adjustments": adjustments,
            "reasoning": reasoning,
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        audit_log_event("temporal_adjustment_error", {"error": str(exc)})
        return {
            "adjusted_score": base_score,
            "total_adjustment": 0,
            "adjustments": [],
            "reasoning": "error: temporal adjustment failed",
        }


def _safe_price(item: Dict[str, Any]) -> int:
    price = item.get("price")
    if isinstance(price, (int, float)):
        return int(price)
    try:
        return int(float(price))
    except Exception:
        return 0


__all__ = [
    # Phase 1: Original functions
    "reconcile_budget_mismatch",
    "calculate_temporal_qualification_adjustments",
    "_analyze_inventory_by_bedrooms",
    "_has_premium_features",
    "_get_market_timing_insights",
    "_find_nearby_location_alternatives",
    "_generate_reconciliation_recommendation",
    "_format_reconciliation_message",
    "_build_fallback_options",
    # Phase 2: Transparent scoring system
    "REAL_ESTATE_BUDGET_BANDS",
    "QUALIFICATION_STATES", 
    "generate_transparent_scoring_breakdown",
    "prioritize_questions_llm",
    "assess_qualification_readiness",
    "_fallback_scoring_calculation",
    "_fallback_question_prioritization",
    "_fallback_readiness_assessment",
]
