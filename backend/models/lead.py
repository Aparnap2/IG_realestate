from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class Lead(BaseModel):
    """
    Lead model according to PRD specifications.

    This model represents a real estate lead with all necessary fields
    for qualification, scheduling, and tracking.
    """
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
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
    status: str = Field(default="new", description="Status: new/qualified/nurturing/disqualified/scheduled/booked")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    last_interaction_at: Optional[datetime] = Field(None, description="Timestamp of last interaction")
    tcpa_opt_in: Optional[bool] = Field(None, description="TCPA opt-in status")
    consent_timestamp: Optional[datetime] = Field(None, description="Timestamp of latest consent update")
    notes: Optional[str] = Field(None, description="Unstructured notes captured during processing")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw LLM response data")
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Enhanced qualification fields
    qualified_score: Optional[float] = Field(None, ge=0, le=1, description="Current qualification score (0-1)")
    previous_score: Optional[float] = Field(None, ge=0, le=1, description="Previous qualification score for delta calculation")
    score_delta: Optional[float] = Field(None, description="Change in qualification score")
    qualification_stage: Optional[str] = Field(None, description="Current qualification stage (warmup, qualification, nurturing, qualified, disqualified)")
    last_question_sent: Optional[str] = Field(None, description="Last qualification question sent to lead")
    asked_questions: List[str] = Field(default_factory=list, description="List of qualification questions already asked")
    
    # Value delivery and off-ramp fields
    lead_magnet_sent_at: Optional[datetime] = Field(None, description="Timestamp when lead magnet was sent")
    lead_magnet_type: Optional[str] = Field(None, description="Type of lead magnet sent")
    property_info_delivered: Optional[bool] = Field(False, description="Whether property information has been delivered")
    market_insights_sent: Optional[bool] = Field(False, description="Whether market insights have been sent")
    offramp_sent_at: Optional[datetime] = Field(None, description="Timestamp when polite off-ramp message was sent")
    offramp_reason: Optional[str] = Field(None, description="Reason for off-ramp (low_score, no_match, etc.)")
    newsletter_opt_in: Optional[bool] = Field(None, description="Newsletter subscription preference")
    # Instagram DM automation fields
    last_dm_sent: Optional[datetime] = Field(None, description="Timestamp of last DM sent to lead")
    dm_count: Optional[int] = Field(0, description="Number of DMs sent to lead")
    response_count: Optional[int] = Field(0, description="Number of responses received from lead")
    
    # Booking automation fields
    calendar_event_id: Optional[str] = Field(None, description="Google Calendar event ID for booked meetings")
    meeting_link: Optional[str] = Field(None, description="Google Meet link for scheduled meetings")
    booking_confirmed_at: Optional[datetime] = Field(None, description="Timestamp when meeting was booked and confirmed")
    rescheduled_count: Optional[int] = Field(0, description="Number of times this meeting has been rescheduled")

    # Self-Driving Booking Ops 2.0 fields
    booking_idempotency_key: Optional[str] = Field(None, description="KSUID for idempotent booking operations")
    booking_etag: Optional[str] = Field(None, description="ETag from last calendar operation")
    booking_attempt_count: Optional[int] = Field(0, description="Number of booking attempts")
    booking_state: Optional[str] = Field(None, description="Current booking state machine state")
    reminder_24h_sent: Optional[bool] = Field(False, description="24-hour reminder sent")
    reminder_3h_sent: Optional[bool] = Field(False, description="3-hour reminder sent")
    reminder_30m_sent: Optional[bool] = Field(False, description="30-minute reminder sent")
    reminder_confirmed_at: Optional[datetime] = Field(None, description="Timestamp of reminder confirmation")
    no_show_predicted: Optional[bool] = Field(False, description="No-show prediction flag")
    waitlist_added_at: Optional[datetime] = Field(None, description="Timestamp when added to waitlist")
    parent_booking_key: Optional[str] = Field(None, description="Parent booking key for reschedule lineage")

    # HubSpot CRM integration fields
    hubspot_contact_id: Optional[str] = Field(None, description="HubSpot contact ID for CRM synchronization")
    hubspot_deal_id: Optional[str] = Field(None, description="HubSpot deal ID for booked meetings")
    hubspot_sync_status: Optional[str] = Field("pending", description="Status of HubSpot synchronization (pending, synced, failed)")
    hubspot_last_synced_at: Optional[datetime] = Field(None, description="Timestamp of last successful HubSpot sync")
    
    
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

    def generate_idempotency_key(self) -> str:
        """Generate a KSUID-based unique key for idempotent operations"""
        # Using UUID4 as approximation - replace with proper KSUID library if needed
        return str(uuid.uuid4())

    def is_booking_confirmed(self) -> bool:
        """Check if booking has been confirmed via reminder system"""
        return self.reminder_confirmed_at is not None