from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Lead(BaseModel):
    id: str
    channel: str  # "ig" or "whatsapp"
    user_id: str
    message: str
    qualified_score: Optional[float] = None
    budget: Optional[int] = None  # e.g., 300000
    location: Optional[str] = None  # e.g., "Miami"
    property_type: Optional[str] = None  # e.g., "2BHK"
    timeline: Optional[str] = None  # e.g., "3 months"
    name: Optional[str] = None
    email: Optional[str] = None
    meeting_slot: Optional[datetime] = None
    status: str = "new"  # new, qualified, scheduled, booked