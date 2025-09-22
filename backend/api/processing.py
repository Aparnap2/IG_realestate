"""
Processing API endpoints for lead management and workflow operations.

This module provides endpoints for managing lead processing, workflow
status, and system operations.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import uuid

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from tasks.lead_processing import process_lead, health_check
except ImportError:
    # Fallback for testing
    def process_lead(data):
        class MockTask:
            def __init__(self):
                self.id = str(uuid.uuid4())
        return MockTask()
    
    def health_check():
        return {"status": "healthy", "timestamp": str(uuid.uuid4())}

from utils.supabase_client import supabase
from utils.redis_client import get_thread_state, redis_health_check
from utils.observability import track_performance, metrics_collector

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadProcessingRequest(BaseModel):
    """Request model for lead processing"""
    channel: str
    user_id: str
    message: str
    name: Optional[str] = None
    email: Optional[str] = None

class LeadStatusResponse(BaseModel):
    """Response model for lead status"""
    lead_id: str
    user_id: str
    status: str
    qualified_score: Optional[float]
    next_agent: Optional[str]
    interrupt: Optional[bool]
    created_at: str

@app.post("/process/lead")
@track_performance
async def process_lead_endpoint(request: LeadProcessingRequest):
    """
    Process a lead through the workflow.
    
    Args:
        request: Lead processing request
        
    Returns:
        Processing result
    """
    try:
        # Create lead data
        lead_data = {
            "id": str(uuid.uuid4()),
            "channel": request.channel,
            "user_id": request.user_id,
            "message": request.message,
            "name": request.name,
            "email": request.email,
            "status": "new"
        }
        
        # Queue for processing
        task_result = process_lead(lead_data)
        
        logger.info(f"Lead processing queued: {lead_data['id']} -> {task_result.id}")
        
        return {
            "success": True,
            "lead_id": lead_data["id"],
            "task_id": task_result.id,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Error processing lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to process lead")

@app.get("/process/status/{user_id}")
@track_performance
async def get_lead_status(user_id: str):
    """
    Get the current status of a lead by user ID.
    
    Args:
        user_id: User identifier
        
    Returns:
        Lead status information
    """
    try:
        # Get lead from database
        response = supabase.table("leads").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_data = response.data[0]
        
        # Get thread state for additional context
        thread_state = get_thread_state(user_id)
        
        return LeadStatusResponse(
            lead_id=lead_data["id"],
            user_id=lead_data["user_id"],
            status=lead_data["status"],
            qualified_score=lead_data.get("qualified_score"),
            next_agent=thread_state.get("next_agent") if thread_state else None,
            interrupt=thread_state.get("interrupt") if thread_state else None,
            created_at=lead_data["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lead status")

@app.get("/process/leads")
@track_performance
async def get_all_leads(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    Get all leads with optional filtering.
    
    Args:
        limit: Maximum number of leads to return
        offset: Number of leads to skip
        status: Optional status filter
        
    Returns:
        List of leads
    """
    try:
        query = supabase.table("leads").select("*")
        
        if status:
            query = query.eq("status", status)
        
        response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {
            "leads": response.data,
            "count": len(response.data),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve leads")

@app.get("/process/metrics")
@track_performance
async def get_processing_metrics():
    """
    Get processing metrics and statistics.
    
    Returns:
        Processing metrics
    """
    try:
        # Get lead counts by status
        total_response = supabase.table("leads").select("id", count="exact").execute()
        total_leads = total_response.count or 0
        
        new_response = supabase.table("leads").select("id", count="exact").eq("status", "new").execute()
        new_leads = new_response.count or 0
        
        qualified_response = supabase.table("leads").select("id", count="exact").eq("status", "qualified").execute()
        qualified_leads = qualified_response.count or 0
        
        scheduled_response = supabase.table("leads").select("id", count="exact").eq("status", "scheduled").execute()
        scheduled_leads = scheduled_response.count or 0
        
        # Get average qualification score
        scores_response = supabase.table("leads").select("qualified_score").not_.is_("qualified_score", "null").execute()
        scores = [lead["qualified_score"] for lead in scores_response.data if lead["qualified_score"] is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "qualified_leads": qualified_leads,
            "scheduled_leads": scheduled_leads,
            "average_qualification_score": round(avg_score, 2),
            "conversion_rate": round((qualified_leads / total_leads * 100) if total_leads > 0 else 0, 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")

@app.delete("/process/lead/{lead_id}")
@track_performance
async def delete_lead(lead_id: str):
    """
    Delete a lead from the system.
    
    Args:
        lead_id: Lead identifier
        
    Returns:
        Deletion result
    """
    try:
        # Delete from database
        response = supabase.table("leads").delete().eq("id", lead_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        logger.info(f"Lead deleted: {lead_id}")
        
        return {
            "success": True,
            "lead_id": lead_id,
            "message": "Lead deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete lead")

@app.get("/process/health")
async def processing_health():
    """Health check for processing service"""
    try:
        # Test task queue
        task_result = health_check()
        
        # Test Redis
        redis_health = redis_health_check()
        
        # Test database
        db_response = supabase.table("leads").select("id").limit(1).execute()
        db_healthy = True
        
        return {
            "status": "healthy",
            "task_queue": task_result.get("status", "unknown"),
            "redis": redis_health.get("status", "unknown"),
            "database": "healthy" if db_healthy else "unhealthy",
            "service": "processing"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "service": "processing"
        }

# Test endpoint for development
@app.post("/process/test")
async def test_processing(test_data: Dict[str, Any]):
    """
    Test endpoint for processing pipeline during development.
    
    This endpoint allows testing the processing pipeline
    without requiring actual webhook integration.
    """
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        # Create test lead
        lead_request = LeadProcessingRequest(
            channel=test_data.get("channel", "test"),
            user_id=test_data.get("user_id", f"test_user_{uuid.uuid4()}"),
            message=test_data.get("message", "Test message for processing"),
            name=test_data.get("name"),
            email=test_data.get("email")
        )
        
        # Process the test lead
        result = await process_lead_endpoint(lead_request)
        
        return {
            "status": "success",
            "test_data": test_data,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error processing test lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))
