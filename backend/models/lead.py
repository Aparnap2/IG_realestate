from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class Lead(BaseModel):
    """
    Lead model according to PRD specifications.
    
    This model represents a real estate lead with all necessary fields
    for qualification, scheduling, and tracking.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str = Field(..., description="Channel: 'ig'")
    user_id: str = Field(..., description="Meta PSID")
    message: str = Field(..., description="Initial inquiry message")
    qualified_score: Optional[float] = Field(None, ge=0, le=1, description="Qualification score (0-1)")
    budget: Optional[int] = Field(None, description="Budget in USD (e.g., 300000)")
    location: Optional[str] = Field(None, description="Desired location (e.g., 'Miami')")
    property_type: Optional[str] = Field(None, description="Property type (e.g., '2BHK', 'Condo')")
    timeline: Optional[str] = Field(None, description="Timeline (e.g., '3 months')")
    desired_bedrooms: Optional[int] = Field(None, description="Preferred bedroom count")
    name: Optional[str] = Field(None, description="Lead's name")
    email: Optional[str] = Field(None, description="Lead's email")
    meeting_slot: Optional[datetime] = Field(None, description="Scheduled meeting time")
    status: str = Field(default="new", description="Status: new/qualified/scheduled/booked")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    last_interaction_at: Optional[datetime] = Field(None, description="Timestamp of last interaction")
    tcpa_opt_in: Optional[bool] = Field(None, description="TCPA opt-in status")
    consent_timestamp: Optional[datetime] = Field(None, description="Timestamp of latest consent update")
    notes: Optional[str] = Field(None, description="Unstructured notes captured during processing")
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_history_entry(self, message: str, agent: str, details: Optional[str] = None):
        """Add an entry to the conversation history"""
        entry = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "agent": agent
        }
        if details:
            entry["details"] = details
        self.history.append(entry)
    
    def is_high_value(self) -> bool:
        """Check if this is a high-value lead requiring HITL"""
        return (self.budget and self.budget > 500000) or (self.qualified_score and self.qualified_score > 0.9)
    
    def should_schedule(self) -> bool:
        """Check if lead should be handed off to scheduler"""
        return self.qualified_score and self.qualified_score > 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return self.model_dump()