"""Utility helpers supporting PRD-compliant qualifier flows."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from utils.audit import audit_log_event
from utils.supabase_client import supabase


_LOCATION_ALTERNATIVES: Dict[str, Sequence[str]] = {
    "Miami": ("Coral Gables", "Aventura", "Doral", "Miami Shores"),
    "San Francisco": ("Oakland", "Berkeley", "Daly City"),
    "Austin": ("Round Rock", "Cedar Park", "Georgetown"),
    "New York": ("Brooklyn", "Queens", "Jersey City"),
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
    "reconcile_budget_mismatch",
    "calculate_temporal_qualification_adjustments",
    "_analyze_inventory_by_bedrooms",
    "_has_premium_features",
    "_get_market_timing_insights",
    "_find_nearby_location_alternatives",
    "_generate_reconciliation_recommendation",
    "_format_reconciliation_message",
    "_build_fallback_options",
]
