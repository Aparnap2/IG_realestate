"""
Lead Warm-up Agent for Instagram DM Automation.

This agent handles the initial warm-up sequence for comment-triggered leads,
focusing on rapport building and lead magnet delivery before qualification.
"""

import sys
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

# Add parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.schemas.state import AgentState
from backend.tools.agent_tools import send_instagram_message, fetch_lead_magnet
from backend.utils.redis_client import get_conversation_state, set_conversation_state
from backend.utils.audit import audit_log_event
from backend.utils.supabase_client import supabase
from backend.models.lead import Lead

logger = logging.getLogger(__name__)

class LeadWarmupAgent:
    """
    Lead Warm-up Agent for comment-triggered DM funnel.
    
    Key Features:
    - Rapport building with personalized messaging
    - Lead magnet delivery (PDF guides, videos)
    - Progressive engagement before qualification
    - Conversation state management in Redis
    """
    
    def __init__(self):
        # Initialize LLM for message generation
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=300
        )
        
        # Warm-up conversation flow
        self.warmup_stages = [
            "initial_contact",
            "lead_magnet_offer",
            "lead_magnet_delivery",
            "value_building",
            "qualification_transition"
        ]
        
        # Lead magnet keywords
        self.lead_magnet_keywords = ["guide", "yes", "send", "want", "interested", "sure"]
        
        # Transition keywords to qualification
        self.transition_keywords = ["ready", "qualify", "questions", "help", "buy", "property"]
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """
        Process warm-up conversation based on current stage and user response.
        
        Flow:
        1. Get conversation state from Redis
        2. Determine current warm-up stage
        3. Generate appropriate response
        4. Update conversation state
        5. Handle lead magnet delivery
        6. Transition to qualification when ready
        
        Args:
            state: Current conversation state with lead and message history
            
        Returns:
            Updated state with warm-up response
        """
        lead = state["lead"]
        messages = state.get("messages", [])
        
        # Log warm-up agent invocation
        audit_log_event("warmup_agent_invoked", {
            "lead_id": lead.id,
            "message_count": len(messages)
        })
        
        try:
            # Get conversation state from Redis
            conversation_state = get_conversation_state(lead.user_id) or {}
            
            # Determine current stage
            current_stage = conversation_state.get("current_step", "initial_contact")
            
            # Get latest user message
            latest_message = ""
            if messages and messages[-1].get("role") == "user":
                latest_message = messages[-1]["content"]
            
            # Process based on current stage
            if current_stage == "initial_contact":
                response = await self._handle_initial_contact(lead, latest_message, conversation_state)
            elif current_stage == "lead_magnet_offer":
                response = await self._handle_lead_magnet_response(lead, latest_message, conversation_state)
            elif current_stage == "lead_magnet_delivery":
                response = await self._handle_post_delivery(lead, latest_message, conversation_state)
            elif current_stage == "value_building":
                response = await self._handle_value_building(lead, latest_message, conversation_state)
            else:
                response = await self._handle_transition_to_qualification(lead, latest_message, conversation_state)
            
            # Update conversation state
            updated_state = self._update_conversation_state(lead.user_id, conversation_state, response)
            
            # Update lead record
            self._update_lead_record(lead.id, response)
            
            # Add response to conversation history
            state["messages"].append({
                "role": "assistant",
                "content": response["message"],
                "metadata": {
                    "agent": "warmup",
                    "stage": response.get("stage", current_stage),
                    "lead_magnet_sent": response.get("lead_magnet_sent", False)
                }
            })
            
            # Update state with agent decision
            state["agent_decision"] = {
                "agent_type": "warmup",
                "stage": response.get("stage", current_stage),
                "action": response.get("action", "continue_warmup"),
                "next_agent": response.get("next_agent", "warmup"),
                "lead_magnet_sent": response.get("lead_magnet_sent", False)
            }
            
            # Set next agent if transitioning
            if response.get("next_agent") == "qualifier":
                state["current_agent"] = "qualifier"
            
            return state
            
        except Exception as e:
            logger.error(f"Error in warm-up agent processing: {e}")
            return self._handle_warmup_error(state, e)
    
    async def _handle_initial_contact(
        self, 
        lead: Lead, 
        message: str, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle initial contact after comment trigger.
        
        This stage was already handled in comment_intake.py, so we just
        acknowledge and wait for lead magnet response.
        """
        # Check if user is responding to lead magnet offer
        if self._contains_lead_magnet_intent(message):
            return await self._deliver_lead_magnet(lead, conversation_state)
        
        # Send gentle reminder about lead magnet
        reminder_message = f"""Hey {lead.name or 'there'}! 👋

Just checking in - did you want my free "5 Essential Tips for First-Time Home Buyers" guide?

It's completely free and packed with valuable insights that could save you thousands on your first home purchase.

Just reply "guide" and I'll send it right over! 📚"""
        
        return {
            "message": reminder_message,
            "stage": "lead_magnet_offer",
            "action": "remind_lead_magnet",
            "next_agent": "warmup"
        }
    
    async def _handle_lead_magnet_response(
        self, 
        lead: Lead, 
        message: str, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle response to lead magnet offer.
        """
        if self._contains_lead_magnet_intent(message):
            return await self._deliver_lead_magnet(lead, conversation_state)
        
        # Handle objections or questions
        if self._contains_objection(message):
            return await self._handle_lead_magnet_objection(lead, conversation_state)
        
        # Gentle reminder
        reminder = f"""No problem at all! The guide is completely free and takes just 2 minutes to read.

It covers:
✅ How to avoid common first-time buyer mistakes
✅ Tips for getting pre-approved
✅ What to look for in property inspections
✅ Negotiation strategies that work
✅ Hidden costs to watch out for

Worth a quick look? Just say "guide"! 🏠"""
        
        return {
            "message": reminder,
            "stage": "lead_magnet_offer",
            "action": "address_objection",
            "next_agent": "warmup"
        }
    
    async def _deliver_lead_magnet(
        self, 
        lead: Lead, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deliver lead magnet to lead.
        """
        try:
            # Fetch lead magnet from Supabase Storage
            lead_magnet = fetch_lead_magnet("first_time_buyer_guide")
            
            if not lead_magnet:
                logger.error("Failed to fetch lead magnet")
                return await self._handle_lead_magnet_error(lead, conversation_state)
            
            # Send lead magnet delivery message
            delivery_message = f"""Perfect! Here's your free guide: 📚

🏠 "5 Essential Tips for First-Time Home Buyers"

{lead_magnet.get('delivery_text', 'Check your DMs for the complete guide!')}

This guide has helped hundreds of first-time buyers save thousands and avoid common pitfalls.

After you've had a chance to look it over, I'd love to help you find your perfect property.
What type of property are you most interested in? 🏡🏢🏘️"""
            
            # Send message
            message_sent = send_instagram_message(lead.user_id, delivery_message)
            
            if message_sent:
                # Update conversation state
                conversation_state["current_step"] = "lead_magnet_delivery"
                conversation_state["lead_magnet_sent"] = True
                conversation_state["lead_magnet_sent_at"] = datetime.now().isoformat()
                
                set_conversation_state(lead.user_id, conversation_state, ttl=86400)
                
                # Log successful delivery
                audit_log_event("lead_magnet_delivered", {
                    "lead_id": lead.id,
                    "user_id": lead.user_id,
                    "lead_magnet_type": "first_time_buyer_guide",
                    "timestamp": datetime.now().isoformat()
                })
                
                return {
                    "message": delivery_message,
                    "stage": "lead_magnet_delivery",
                    "action": "deliver_lead_magnet",
                    "lead_magnet_sent": True,
                    "next_agent": "warmup"
                }
            else:
                return await self._handle_lead_magnet_error(lead, conversation_state)
                
        except Exception as e:
            logger.error(f"Error delivering lead magnet: {e}")
            return await self._handle_lead_magnet_error(lead, conversation_state)
    
    async def _handle_post_delivery(
        self, 
        lead: Lead, 
        message: str, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle responses after lead magnet delivery.
        """
        # Check if user is ready to discuss properties
        if self._contains_transition_intent(message):
            return await self._transition_to_qualification(lead, conversation_state)
        
        # Continue value building
        value_message = f"""Great! I'm glad you found the guide helpful. 🎉

Many of our clients start with that same guide and end up finding their dream home within 3-6 months.

The real estate market moves fast, especially for first-time buyers. Having a clear strategy makes all the difference.

Are you currently:
🏠 Looking to buy in the next 3 months?
🏡 Just starting to explore options?
🏢 Need to sell first?

Understanding your timeline helps me provide the most relevant guidance!"""
        
        return {
            "message": value_message,
            "stage": "value_building",
            "action": "build_value",
            "next_agent": "warmup"
        }
    
    async def _handle_value_building(
        self, 
        lead: Lead, 
        message: str, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle value building stage.
        """
        # Check for transition readiness
        if self._contains_transition_intent(message):
            return await self._transition_to_qualification(lead, conversation_state)
        
        # Continue engagement based on their response
        engagement_message = f"""That's really helpful context, thanks for sharing! 🙏

Based on what you've told me, I think we can definitely help you find the right property.

Here's what I can do for you:
🔍 Find properties that match your exact criteria
📊 Send you market insights and trends
🏡 Schedule viewings for properties you like
💰 Connect you with trusted lenders
📋 Guide you through the entire process

Would you like to start by looking at some properties, or do you have specific questions about the buying process?"""
        
        return {
            "message": engagement_message,
            "stage": "qualification_transition",
            "action": "prepare_transition",
            "next_agent": "warmup"
        }
    
    async def _handle_transition_to_qualification(
        self, 
        lead: Lead, 
        message: str, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle transition to qualification phase.
        """
        transition_message = f"""Perfect! You're ready to take the next step. 🚀

Let me ask you a few quick questions to help find your perfect property:

1️⃣ What's your budget range?
2️⃣ What areas are you interested in?
3️⃣ What type of property are you looking for?

Once I understand your preferences, I can show you some great options that match what you're looking for.

What's your budget range to start? 💰"""
        
        # Update conversation state for qualification
        conversation_state["current_step"] = "qualification_started"
        conversation_state["qualification_started"] = True
        conversation_state["stage"] = "qualification"
        
        set_conversation_state(lead.user_id, conversation_state, ttl=86400)
        
        # Update lead status
        self._update_lead_status(lead.id, "qualification")
        
        return {
            "message": transition_message,
            "stage": "qualification_started",
            "action": "transition_to_qualification",
            "next_agent": "qualifier"
        }
    
    async def _handle_lead_magnet_objection(
        self, 
        lead: Lead, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle objections to lead magnet.
        """
        objection_message = f"""I totally understand - you're probably busy! ⏰

The guide is just 2 pages and takes 2 minutes to read. It's designed specifically for first-time buyers in your area.

Even if you're not planning to buy immediately, it's good information to have. Knowledge is power when it comes to real estate! 💪

No pressure at all - I'm here to help whenever you're ready. Just say "guide" if you change your mind!"""
        
        return {
            "message": objection_message,
            "stage": "lead_magnet_offer",
            "action": "handle_objection",
            "next_agent": "warmup"
        }
    
    async def _handle_lead_magnet_error(
        self, 
        lead: Lead, 
        conversation_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle lead magnet delivery error.
        """
        error_message = f"""I apologize, but I'm having technical difficulties sending the guide right now. 🛠️

Let me help you directly instead! Here are the key points from the guide:

✅ Get pre-approved before house hunting
✅ Save 20% for down payment + closing costs
✅ Check your credit score 6 months in advance
✅ Don't skip home inspections
✅ Budget for maintenance and repairs

I'd love to discuss your specific situation and help you find the perfect property. What's your budget range? 💰"""
        
        return {
            "message": error_message,
            "stage": "qualification_transition",
            "action": "fallback_to_qualification",
            "next_agent": "qualifier"
        }
    
    def _contains_lead_magnet_intent(self, message: str) -> bool:
        """Check if message contains intent to receive lead magnet."""
        if not message:
            return False
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.lead_magnet_keywords)
    
    def _contains_transition_intent(self, message: str) -> bool:
        """Check if message contains intent to transition to qualification."""
        if not message:
            return False
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.transition_keywords)
    
    def _contains_objection(self, message: str) -> bool:
        """Check if message contains objection."""
        if not message:
            return False
        
        objection_keywords = ["no", "not", "busy", "don't", "can't", "unable", "later"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in objection_keywords)
    
    def _update_conversation_state(
        self, 
        user_id: str, 
        conversation_state: Dict[str, Any], 
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update conversation state in Redis."""
        try:
            conversation_state["current_step"] = response.get("stage", conversation_state.get("current_step"))
            conversation_state["last_interaction"] = datetime.now().isoformat()
            
            if response.get("lead_magnet_sent"):
                conversation_state["lead_magnet_sent"] = True
                conversation_state["lead_magnet_sent_at"] = datetime.now().isoformat()
            
            set_conversation_state(user_id, conversation_state, ttl=86400)
            return conversation_state
            
        except Exception as e:
            logger.error(f"Error updating conversation state: {e}")
            return conversation_state
    
    def _update_lead_record(self, lead_id: str, response: Dict[str, Any]):
        """Update lead record with warm-up progress."""
        try:
            update_data = {
                "last_dm_sent": datetime.now(),
                "qualification_stage": response.get("stage", "warmup")
            }
            
            if response.get("lead_magnet_sent"):
                update_data["lead_magnet_sent_at"] = datetime.now()
            
            supabase.table("leads").update(update_data).eq("id", lead_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating lead record: {e}")
    
    def _update_lead_status(self, lead_id: str, status: str):
        """Update lead status."""
        try:
            supabase.table("leads").update({
                "status": status,
                "last_interaction_at": datetime.now()
            }).eq("id", lead_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
    
    def _handle_warmup_error(self, state: AgentState, error: Exception) -> Dict[str, Any]:
        """Handle warm-up agent errors with graceful degradation."""
        lead = state["lead"]
        
        audit_log_event("warmup_agent_error", {
            "lead_id": lead.id,
            "error": str(error),
            "timestamp": datetime.now().isoformat()
        })
        
        # Fallback message
        fallback_message = f"""I apologize for the technical difficulty. 

I'm here to help you find your perfect property! Let me ask you a few quick questions:

What's your budget range? 💰

Once I know your preferences, I can show you some great options!"""
        
        state["messages"].append({
            "role": "assistant",
            "content": fallback_message,
            "metadata": {
                "agent": "warmup",
                "error": True,
                "fallback": True
            }
        })
        
        state["current_agent"] = "qualifier"
        state["error"] = str(error)
        
        return state