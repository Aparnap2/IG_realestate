"""
Booking Flow Manager for Instagram DM Automation

Handles the complete booking workflow:
- Email and phone capture before booking
- Calendar availability checking
- Meeting slot offering and confirmation
- Google Meet link generation
- Booking confirmation DMs
- Fallback handling for booking failures
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

# Add parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_or_update_lead
from utils.redis_client import get_temporary_data, store_temporary_data
from utils.audit import audit_log_event
from tools.calendar_integration import get_available_calendar_slots, create_tour_event, reschedule_tour_event, cancel_tour_event
from tools.agent_tools import send_instagram_message, book_calendar_event
from utils.llm_client import get_llm_response_sync

logger = logging.getLogger(__name__)

class BookingFlowManager:
    """
    Manages the complete booking workflow for qualified leads.
    
    Key Features:
    - Email capture with Redis confirmation pattern
    - Calendar availability checking
    - Meeting slot presentation
    - Google Meet link generation
    - Booking confirmation via DM
    - Fallback handling for conflicts
    """
    
    def __init__(self):
        self.confirm_ttl = 7200  # 2 hours for confirmation
        self.email_ttl = 3600  # 1 hour for email capture
    
    async def initiate_booking_flow(
        self,
        user_id: str,
        lead_data: Dict[str, Any],
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Initiate the booking flow for a qualified lead.
        
        Args:
            user_id: Instagram user ID
            lead_data: Lead information including budget, location, etc.
            user_name: Lead's name for personalization
            
        Returns:
            Dictionary with booking flow result
        """
        try:
            logger.info(f"🗓️ BOOKING FLOW: Starting booking process for {user_id}")
            
            # Check if we already have email
            confirm_key = f"confirm:{user_id}"
            existing_confirm = get_temporary_data(confirm_key) or {}
            
            if lead_data.get("email"):
                # Email already available, proceed to slot selection
                return await self._offer_time_slots(user_id, lead_data, user_name)
            else:
                # Need to capture email first
                if not existing_confirm.get("awaiting_email"):
                    # Send email request
                    email_request_msg = self._generate_email_request_message(user_name, lead_data)
                    
                    # Store state
                    store_temporary_data(confirm_key, {"awaiting_email": True}, ttl=self.email_ttl)
                    
                    # Send DM
                    sent = send_instagram_message.invoke({
                        "user_id": user_id,
                        "message": email_request_msg
                    })
                    
                    audit_log_event("booking_email_request_sent", {
                        "user_id": user_id,
                        "lead_data": lead_data,
                        "message_sent": email_request_msg[:100] + "..."
                    })
                    
                    return {
                        "status": "email_capture_required",
                        "message": email_request_msg,
                        "next_step": "await_email"
                    }
                else:
                    # Already awaiting email, send reminder
                    reminder_msg = self._generate_email_reminder_message(user_name)
                    sent = send_instagram_message.invoke({
                        "user_id": user_id,
                        "message": reminder_msg
                    })
                    
                    return {
                        "status": "email_reminder_sent",
                        "message": reminder_msg,
                        "next_step": "await_email"
                    }
                    
        except Exception as e:
            logger.error(f"Error in booking flow initiation: {e}")
            audit_log_event("booking_flow_error", {
                "user_id": user_id,
                "error": str(e),
                "stage": "initiation"
            })
            
            return {
                "status": "error",
                "error": str(e),
                "message": "I'm having trouble with the booking process. Let me connect you with an agent directly."
            }
    
    async def process_email_response(
        self,
        user_id: str,
        message: str,
        lead_data: Dict[str, Any],
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Process email response and proceed to slot selection.
        
        Args:
            user_id: Instagram user ID
            message: User's message containing email
            lead_data: Lead information
            user_name: Lead's name
            
        Returns:
            Dictionary with email processing result
        """
        try:
            logger.info(f"📧 EMAIL PROCESSING: Processing email from {user_id}")
            
            # Extract email from message
            email = self._extract_email_from_message(message)
            
            if not email:
                # Invalid email, send correction request
                correction_msg = self._generate_email_correction_message(user_name)
                sent = send_instagram_message.invoke({
                    "user_id": user_id,
                    "message": correction_msg
                })
                
                return {
                    "status": "invalid_email",
                    "message": correction_msg,
                    "next_step": "await_valid_email"
                }
            
            # Update lead data with email
            lead_data["email"] = email
            
            # Save updated lead
            save_or_update_lead(user_id, lead_data)
            
            # Clear email awaiting state
            confirm_key = f"confirm:{user_id}"
            store_temporary_data(confirm_key, {"email_captured": email}, ttl=self.confirm_ttl)
            
            audit_log_event("booking_email_captured", {
                "user_id": user_id,
                "email": email,
                "lead_data": lead_data
            })
            
            # Proceed to slot offering
            return await self._offer_time_slots(user_id, lead_data, user_name)
            
        except Exception as e:
            logger.error(f"Error processing email response: {e}")
            audit_log_event("booking_email_error", {
                "user_id": user_id,
                "error": str(e),
                "message": message[:100]
            })
            
            return {
                "status": "error",
                "error": str(e),
                "message": "I had trouble processing your email. Could you please provide it again?"
            }
    
    async def _offer_time_slots(
        self,
        user_id: str,
        lead_data: Dict[str, Any],
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Offer available time slots to the lead.
        
        Args:
            user_id: Instagram user ID
            lead_data: Lead information
            user_name: Lead's name
            
        Returns:
            Dictionary with slot offering result
        """
        try:
            logger.info(f"🕐 SLOT OFFERING: Getting available slots for {user_id}")
            
            # Get available slots from calendar
            available_slots = get_available_calendar_slots(days_ahead=7, time_of_day="any")
            
            if not available_slots:
                # No slots available, send fallback
                fallback_msg = self._generate_no_slots_message(user_name)
                sent = send_instagram_message.invoke({
                    "user_id": user_id,
                    "message": fallback_msg
                })
                
                return {
                    "status": "no_slots_available",
                    "message": fallback_msg,
                    "next_step": "manual_scheduling"
                }
            
            # Format slots for presentation
            slot_options = self._format_slot_options(available_slots[:5])  # Offer top 5 slots
            
            # Generate slot selection message
            slot_msg = self._generate_slot_selection_message(user_name, slot_options, lead_data)
            
            # Store slots for later confirmation
            confirm_key = f"confirm:{user_id}"
            store_temporary_data(confirm_key, {
                "email_captured": lead_data.get("email"),
                "available_slots": available_slots[:5],
                "awaiting_slot_selection": True
            }, ttl=self.confirm_ttl)
            
            # Send slot options
            sent = send_instagram_message.invoke({
                "user_id": user_id,
                "message": slot_msg
            })
            
            audit_log_event("booking_slots_offered", {
                "user_id": user_id,
                "slots_count": len(available_slots[:5]),
                "lead_data": lead_data
            })
            
            return {
                "status": "slots_offered",
                "message": slot_msg,
                "next_step": "await_slot_selection",
                "available_slots": available_slots[:5]
            }
            
        except Exception as e:
            logger.error(f"Error offering time slots: {e}")
            audit_log_event("booking_slots_error", {
                "user_id": user_id,
                "error": str(e)
            })
            
            return {
                "status": "error",
                "error": str(e),
                "message": "I'm having trouble finding available times. Let me connect you with an agent."
            }
    
    async def process_slot_selection(
        self,
        user_id: str,
        message: str,
        lead_data: Dict[str, Any],
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Process slot selection and book the meeting.
        
        Args:
            user_id: Instagram user ID
            message: User's slot selection
            lead_data: Lead information
            user_name: Lead's name
            
        Returns:
            Dictionary with booking result
        """
        try:
            logger.info(f"📅 SLOT SELECTION: Processing slot selection from {user_id}")
            
            # Get stored slots
            confirm_key = f"confirm:{user_id}"
            confirm_state = get_temporary_data(confirm_key) or {}
            available_slots = confirm_state.get("available_slots", [])
            
            if not available_slots:
                # Slots expired, regenerate
                return await self._offer_time_slots(user_id, lead_data, user_name)
            
            # Parse user selection
            selected_slot = self._parse_slot_selection(message, available_slots)
            
            if not selected_slot:
                # Invalid selection, send clarification
                clarification_msg = self._generate_slot_clarification_message(user_name, available_slots)
                sent = send_instagram_message.invoke({
                    "user_id": user_id,
                    "message": clarification_msg
                })
                
                return {
                    "status": "invalid_slot_selection",
                    "message": clarification_msg,
                    "next_step": "await_valid_selection"
                }
            
            # Book the selected slot
            booking_result = await self._book_meeting_slot(
                user_id, selected_slot, lead_data, user_name
            )
            
            return booking_result
            
        except Exception as e:
            logger.error(f"Error processing slot selection: {e}")
            audit_log_event("booking_selection_error", {
                "user_id": user_id,
                "error": str(e),
                "message": message[:100]
            })
            
            return {
                "status": "error",
                "error": str(e),
                "message": "I had trouble booking that time. Could you select another option?"
            }
    
    async def _book_meeting_slot(
        self,
        user_id: str,
        selected_slot: datetime,
        lead_data: Dict[str, Any],
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Book the selected meeting slot.
        
        Args:
            user_id: Instagram user ID
            selected_slot: Selected datetime slot
            lead_data: Lead information
            user_name: Lead's name
            
        Returns:
            Dictionary with booking result
        """
        try:
            logger.info(f"🎯 BOOKING: Attempting to book slot for {user_id}")
            
            email = lead_data.get("email")
            if not email:
                return {
                    "status": "error",
                    "error": "Email required for booking",
                    "message": "I need your email address to book the meeting."
                }
            
            # Create calendar event
            event_result = create_tour_event(
                start_time=selected_slot,
                duration_minutes=30,
                attendee_email=email,
                summary=f"Real Estate Consultation with {user_name or 'Client'}",
                description=f"Consultation for {lead_data.get('property_type', 'property')} in {lead_data.get('location', 'your area')}. Scheduled via Instagram DM automation.",
                property_addresses=[]
            )
            
            if "error" in event_result:
                # Booking failed, offer alternative
                return await self._handle_booking_failure(user_id, lead_data, user_name, event_result.get("error"))
            
            # Success - update lead with booking info
            lead_data.update({
                "meeting_slot": selected_slot,
                "calendar_event_id": event_result.get("event_id"),
                "meeting_link": event_result.get("meet_link"),
                "status": "scheduled",
                "booking_confirmed_at": datetime.now()
            })
            
            # Save updated lead
            save_or_update_lead(user_id, lead_data)
            
            # Generate confirmation message
            confirmation_msg = self._generate_booking_confirmation_message(
                user_name, selected_slot, event_result
            )
            
            # Send confirmation
            sent = send_instagram_message.invoke({
                "user_id": user_id,
                "message": confirmation_msg
            })
            
            # Clear booking state
            confirm_key = f"confirm:{user_id}"
            store_temporary_data(confirm_key, {}, ttl=60)  # Clear quickly
            
            audit_log_event("booking_confirmed", {
                "user_id": user_id,
                "event_id": event_result.get("event_id"),
                "meeting_time": selected_slot.isoformat(),
                "meet_link": event_result.get("meet_link"),
                "email": email
            })
            
            return {
                "status": "booking_confirmed",
                "message": confirmation_msg,
                "event_id": event_result.get("event_id"),
                "meeting_link": event_result.get("meet_link"),
                "meeting_time": selected_slot,
                "next_step": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error booking meeting slot: {e}")
            audit_log_event("booking_error", {
                "user_id": user_id,
                "error": str(e),
                "selected_slot": selected_slot.isoformat() if selected_slot else None
            })
            
            return {
                "status": "error",
                "error": str(e),
                "message": "I had trouble confirming your booking. Let me connect you with an agent."
            }
    
    async def _handle_booking_failure(
        self,
        user_id: str,
        lead_data: Dict[str, Any],
        user_name: str = None,
        error: str = None
    ) -> Dict[str, Any]:
        """
        Handle booking failure with fallback options.
        
        Args:
            user_id: Instagram user ID
            lead_data: Lead information
            user_name: Lead's name
            error: Error message from booking attempt
            
        Returns:
            Dictionary with fallback result
        """
        try:
            logger.info(f"⚠️ BOOKING FAILURE: Handling booking failure for {user_id}")
            
            # Offer alternative slots or manual scheduling
            fallback_msg = self._generate_booking_fallback_message(user_name, error)
            
            sent = send_instagram_message.invoke({
                "user_id": user_id,
                "message": fallback_msg
            })
            
            return {
                "status": "booking_failed",
                "message": fallback_msg,
                "next_step": "manual_scheduling",
                "error": error
            }
            
        except Exception as e:
            logger.error(f"Error handling booking failure: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "I'm experiencing technical difficulties. An agent will contact you shortly."
            }
    
    def _extract_email_from_message(self, message: str) -> Optional[str]:
        """Extract email address from user message."""
        import re
        
        # Simple email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, message.lower())
        
        return matches[0] if matches else None
    
    def _parse_slot_selection(self, message: str, available_slots: List[datetime]) -> Optional[datetime]:
        """Parse user's slot selection from message."""
        import re
        
        message_lower = message.lower().strip()
        
        # Try to match number patterns (1, 2, 3, etc.)
        number_match = re.search(r'\b([1-9])\b', message_lower)
        if number_match:
            slot_index = int(number_match.group(1)) - 1  # Convert to 0-based index
            if 0 <= slot_index < len(available_slots):
                return available_slots[slot_index]
        
        # Try to match time patterns (2pm, 3:30, etc.)
        time_patterns = [
            r'(\d{1,2})\s*([ap]m)',  # 2pm, 3:30am
            r'(\d{1,2}):(\d{2})\s*([ap]m)',  # 2:30, 3:00pm
            r'(\d{1,2})\s*o\'\s*clock',  # 2 o'clock
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, message_lower)
            if time_match:
                try:
                    if len(time_match.groups()) == 3:
                        hour, minute, period = time_match.groups()
                        hour = int(hour)
                        minute = int(minute) if minute else 0
                    elif len(time_match.groups()) == 2:
                        hour, period = time_match.groups()
                        hour = int(hour)
                        minute = 0
                    else:
                        continue
                    
                    # Convert to 24-hour format
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    # Find matching slot
                    for slot in available_slots:
                        if (slot.hour == hour and slot.minute >= minute - 15 and 
                            slot.minute <= minute + 15):
                            return slot
                except ValueError:
                    continue
        
        return None
    
    def _format_slot_options(self, slots: List[datetime]) -> List[Dict[str, Any]]:
        """Format time slots for presentation."""
        formatted_slots = []
        
        for i, slot in enumerate(slots, 1):
            formatted_slots.append({
                "option": i,
                "time": slot.strftime("%I:%M %p"),
                "date": slot.strftime("%A, %B %d"),
                "datetime": slot
            })
        
        return formatted_slots
    
    def _generate_email_request_message(self, user_name: str, lead_data: Dict[str, Any]) -> str:
        """Generate email request message."""
        name = user_name or "there"
        
        return f"""Hi {name}! 🎉

Great news! Based on what you've shared about your {lead_data.get('property_type', 'property')} search in {lead_data.get('location', 'your area')}, you're qualified for a personalized consultation.

To book your meeting, I just need your email address to send the calendar invite.

What's the best email to reach you at? 📧"""
    
    def _generate_email_reminder_message(self, user_name: str) -> str:
        """Generate email reminder message."""
        name = user_name or "there"
        
        return f"""Hi {name}! 👋

Just following up on your consultation booking. I still need your email address to send you the calendar invite with all the details.

Could you please share your email so we can get your meeting scheduled? 📅"""
    
    def _generate_email_correction_message(self, user_name: str) -> str:
        """Generate email correction message."""
        name = user_name or "there"
        
        return f"""Hi {name}! 😊

I didn't quite catch that email address. Could you please provide it in this format:

name@domain.com

Once I have your correct email, I can get your consultation booked right away! 📧"""
    
    def _generate_slot_selection_message(self, user_name: str, slot_options: List[Dict], lead_data: Dict[str, Any]) -> str:
        """Generate slot selection message."""
        name = user_name or "there"
        
        slots_text = "\n".join([
            f"{slot['option']}. {slot['date']} at {slot['time']}"
            for slot in slot_options
        ])
        
        return f"""Perfect {name}! 🎯

I found some great time slots for your consultation. Please select the one that works best for you:

{slots_text}

Just reply with the number (1, 2, 3, etc.) or tell me a specific time that works for you! ⏰"""
    
    def _generate_slot_clarification_message(self, user_name: str, available_slots: List[datetime]) -> str:
        """Generate slot clarification message."""
        name = user_name or "there"
        
        slots_text = "\n".join([
            f"{i+1}. {slot.strftime('%A, %B %d at %I:%M %p')}"
            for i, slot in enumerate(available_slots[:5])
        ])
        
        return f"""Hi {name}! 🤔

I didn't quite catch that selection. Could you please choose from these available times:

{slots_text}

You can reply with the number (1-5) or tell me a specific day and time that works for you! 📅"""
    
    def _generate_no_slots_message(self, user_name: str) -> str:
        """Generate no slots available message."""
        name = user_name or "there"
        
        return f"""Hi {name}! 📅

I'm not seeing any available slots in my calendar for the next week, but I definitely want to connect with you.

Let me have one of our senior agents reach out to you directly within the next 2 hours to find a perfect time that works for your schedule.

They'll help you with:
• Personalized property recommendations
• Market insights for your area
• Financing options
• Tour scheduling

Talk to you soon! 🏠"""
    
    def _generate_booking_confirmation_message(self, user_name: str, selected_slot: datetime, event_result: Dict[str, Any]) -> str:
        """Generate booking confirmation message."""
        name = user_name or "there"
        meeting_time = selected_slot.strftime("%A, %B %d at %I:%M %p")
        meet_link = event_result.get("meet_link", "")
        
        return f"""🎉 BOOKING CONFIRMED! 

Hi {name}! Your consultation is all set!

📅 **When:** {meeting_time}
🔗 **Google Meet:** {meet_link}
📧 **Calendar Invite:** Sent to your email

You'll receive a calendar invitation shortly with all the details and the Google Meet link. The meeting will last about 30 minutes.

Looking forward to helping you find your perfect property! 🏠✨"""
    
    def _generate_booking_fallback_message(self, user_name: str, error: str = None) -> str:
        """Generate booking fallback message."""
        name = user_name or "there"
        
        return f"""Hi {name}! ⚠️

I'm having a bit of trouble with the automatic booking right now, but I definitely want to connect with you.

One of our senior agents will reach out to you directly within the next 2 hours to get your consultation scheduled manually.

They'll have all your information and can help you with:
• Property recommendations based on your criteria
• Market insights for your target area
• Financing guidance
• Tour scheduling

We'll make sure you get the personalized attention you deserve! 🏠💼"""

# Global instance for easy access
_booking_manager = None

def get_booking_manager() -> BookingFlowManager:
    """Get or create global booking manager instance."""
    global _booking_manager
    if _booking_manager is None:
        _booking_manager = BookingFlowManager()
    return _booking_manager