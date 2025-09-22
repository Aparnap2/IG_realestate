"""
Human-in-the-Loop (HITL) API endpoints for lead review and approval.

This module provides endpoints for human agents to review and approve
high-value leads that have been interrupted in the workflow.
"""
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from tasks.lead_processing import resume_interrupted_lead
except ImportError:
    # Fallback for testing
    def resume_interrupted_lead(lead_id, feedback):
        class MockTask:
            def __init__(self):
                self.id = f"mock_task_{lead_id}"
        return MockTask()

from utils.supabase_client import supabase
from utils.redis_client import get_thread_state, get_temporary_data, store_temporary_data
from middleware.jwt_auth import verify_supabase_jwt
from utils.observability import track_performance, metrics_collector

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HITLReviewRequest(BaseModel):
    """Request model for HITL review"""
    lead_id: str
    action: str  # "approve", "reject", "modify"
    feedback: str
    modifications: Optional[Dict[str, Any]] = None

class HITLLeadResponse(BaseModel):
    """Response model for HITL lead data"""
    lead_id: str
    user_id: str
    channel: str
    message: str
    qualified_score: Optional[float]
    budget: Optional[int]
    location: Optional[str]
    property_type: Optional[str]
    timeline: Optional[str]
    name: Optional[str]
    email: Optional[str]
    status: str
    history: List[Dict[str, Any]]
    created_at: str
    interrupt_reason: Optional[str]

@app.get("/human/pending", response_model=List[HITLLeadResponse])
@track_performance
async def get_pending_leads():
    """
    Get all leads pending HITL review.
    
    Returns:
        List of leads waiting for human review
    """
    try:
        # Query leads that are interrupted and pending review
        response = supabase.table("leads").select("*").eq("status", "interrupted").execute()
        
        pending_leads = []
        for lead_data in response.data:
            # Get thread state to check for interrupt
            thread_state = get_thread_state(lead_data["user_id"])
            
            if thread_state and thread_state.get("interrupt"):
                # Determine interrupt reason
                interrupt_reason = "High-value lead"
                if lead_data.get("budget") and lead_data["budget"] > 500000:
                    interrupt_reason = f"High budget: ${lead_data['budget']:,}"
                elif lead_data.get("qualified_score") and lead_data["qualified_score"] > 0.9:
                    interrupt_reason = f"High qualification score: {lead_data['qualified_score']:.2f}"
                
                pending_leads.append(HITLLeadResponse(
                    lead_id=lead_data["id"],
                    user_id=lead_data["user_id"],
                    channel=lead_data["channel"],
                    message=lead_data["message"],
                    qualified_score=lead_data.get("qualified_score"),
                    budget=lead_data.get("budget"),
                    location=lead_data.get("location"),
                    property_type=lead_data.get("property_type"),
                    timeline=lead_data.get("timeline"),
                    name=lead_data.get("name"),
                    email=lead_data.get("email"),
                    status=lead_data["status"],
                    history=lead_data.get("history", []),
                    created_at=lead_data["created_at"],
                    interrupt_reason=interrupt_reason
                ))
        
        # Update metrics
        metrics_collector.record_gauge("pending_hitl_leads", len(pending_leads))
        
        return pending_leads
        
    except Exception as e:
        logger.error(f"Error getting pending leads: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pending leads")

@app.get("/human/lead/{lead_id}", response_model=HITLLeadResponse)
@track_performance
async def get_lead_details(lead_id: str):
    """
    Get detailed information about a specific lead.
    
    Args:
        lead_id: Lead identifier
        
    Returns:
        Detailed lead information
    """
    try:
        # Get lead from database
        response = supabase.table("leads").select("*").eq("id", lead_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_data = response.data[0]
        
        # Get thread state for additional context
        thread_state = get_thread_state(lead_data["user_id"])
        
        # Determine interrupt reason
        interrupt_reason = None
        if thread_state and thread_state.get("interrupt"):
            interrupt_reason = "High-value lead"
            if lead_data.get("budget") and lead_data["budget"] > 500000:
                interrupt_reason = f"High budget: ${lead_data['budget']:,}"
            elif lead_data.get("qualified_score") and lead_data["qualified_score"] > 0.9:
                interrupt_reason = f"High qualification score: {lead_data['qualified_score']:.2f}"
        
        return HITLLeadResponse(
            lead_id=lead_data["id"],
            user_id=lead_data["user_id"],
            channel=lead_data["channel"],
            message=lead_data["message"],
            qualified_score=lead_data.get("qualified_score"),
            budget=lead_data.get("budget"),
            location=lead_data.get("location"),
            property_type=lead_data.get("property_type"),
            timeline=lead_data.get("timeline"),
            name=lead_data.get("name"),
            email=lead_data.get("email"),
            status=lead_data["status"],
            history=lead_data.get("history", []),
            created_at=lead_data["created_at"],
            interrupt_reason=interrupt_reason
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lead details")

@app.post("/human/review")
@track_performance
async def review_lead(review_request: HITLReviewRequest):
    """
    Review and take action on a lead.
    
    Args:
        review_request: Review request with action and feedback
        
    Returns:
        Review result
    """
    try:
        lead_id = review_request.lead_id
        action = review_request.action
        feedback = review_request.feedback
        
        # Validate action
        if action not in ["approve", "reject", "modify"]:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        # Get lead from database
        response = supabase.table("leads").select("*").eq("id", lead_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_data = response.data[0]
        
        # Process based on action
        if action == "approve":
            # Resume workflow with approval
            task_result = resume_interrupted_lead(
                lead_data["user_id"],  # Using user_id as thread_id
                f"APPROVED: {feedback}"
            )
            
            # Update lead status
            supabase.table("leads").update({
                "status": "approved",
                "history": lead_data.get("history", []) + [{
                    "message": f"HITL approved by admin",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "human",
                    "details": feedback
                }]
            }).eq("id", lead_id).execute()
            
            result_message = "Lead approved and workflow resumed"
            
        elif action == "reject":
            # Update lead status to rejected
            supabase.table("leads").update({
                "status": "rejected",
                "history": lead_data.get("history", []) + [{
                    "message": f"HITL rejected by admin",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "human",
                    "details": feedback
                }]
            }).eq("id", lead_id).execute()
            
            result_message = "Lead rejected"
            
        elif action == "modify":
            # Apply modifications and resume workflow
            if review_request.modifications:
                # Update lead with modifications
                update_data = review_request.modifications.copy()
                update_data["history"] = lead_data.get("history", []) + [{
                    "message": f"HITL modified by admin",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "human",
                    "details": f"Modifications: {review_request.modifications}, Feedback: {feedback}"
                }]
                
                supabase.table("leads").update(update_data).eq("id", lead_id).execute()
            
            # Resume workflow with modifications
            task_result = resume_interrupted_lead(
                lead_data["user_id"],
                f"MODIFIED: {feedback}"
            )
            
            result_message = "Lead modified and workflow resumed"
        
        # Update metrics
        metrics_collector.increment_counter(f"hitl_actions_{action}")
        metrics_collector.increment_counter("hitl_reviews_completed")
        
        # Log the action
        logger.info(f"HITL action taken: {action} on lead {lead_id}")
        
        return {
            "success": True,
            "action": action,
            "lead_id": lead_id,
            "message": result_message,
            "task_id": task_result.id if action in ["approve", "modify"] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing lead: {e}")
        metrics_collector.increment_counter("hitl_review_errors")
        raise HTTPException(status_code=500, detail="Failed to process review")

@app.get("/human/stats")
@track_performance
async def get_hitl_stats():
    """
    Get HITL statistics and metrics.
    
    Returns:
        HITL statistics
    """
    try:
        # Get pending leads count
        pending_response = supabase.table("leads").select("id", count="exact").eq("status", "interrupted").execute()
        pending_count = pending_response.count or 0
        
        # Get approved leads count (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        
        approved_response = supabase.table("leads").select("id", count="exact").eq("status", "approved").gte("created_at", yesterday).execute()
        approved_count = approved_response.count or 0
        
        # Get rejected leads count (last 24 hours)
        rejected_response = supabase.table("leads").select("id", count="exact").eq("status", "rejected").gte("created_at", yesterday).execute()
        rejected_count = rejected_response.count or 0
        
        # Get average response time (placeholder)
        avg_response_time = "2.5 hours"  # TODO: Calculate actual average
        
        return {
            "pending_reviews": pending_count,
            "approved_today": approved_count,
            "rejected_today": rejected_count,
            "total_processed_today": approved_count + rejected_count,
            "average_response_time": avg_response_time
        }
        
    except Exception as e:
        logger.error(f"Error getting HITL stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

# Health check
@app.get("/human/health")
async def hitl_health():
    """Health check for HITL service"""
    try:
        return {
            "status": "healthy",
            "service": "hitl"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "service": "hitl"
        }
