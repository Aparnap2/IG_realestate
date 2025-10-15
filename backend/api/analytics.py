"""Analytics API endpoints exposing revenue intelligence features."""
from fastapi import APIRouter, HTTPException
from utils.analytics import (
    calculate_lead_attribution,
    analyze_agent_performance,
    analyze_inventory_performance,
    generate_conversion_funnel_analysis,
    calculate_roi_metrics
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/lead/{lead_id}")
def get_lead_attribution(lead_id: str, days: int = 90):
    try:
        return calculate_lead_attribution(lead_id=lead_id, time_window_days=days)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents")
def get_agent_performance(days: int = 30, agent_type: str = None):
    try:
        return analyze_agent_performance(time_period_days=days, agent_type=agent_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/inventory")
def get_inventory_performance(days: int = 60):
    try:
        return analyze_inventory_performance(time_period_days=days)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/funnel")
def get_conversion_funnel(days: int = 30):
    try:
        return generate_conversion_funnel_analysis(time_period_days=days)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/roi")
def get_roi_metrics(days: int = 90, operational_cost: float = None):
    try:
        return calculate_roi_metrics(time_period_days=days, operational_cost=operational_cost)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
