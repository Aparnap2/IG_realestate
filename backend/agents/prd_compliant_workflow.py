"""
PRD-compliant LangGraph swarm implementation with proper agent communication patterns.

This implementation follows the exact specifications from the PRD:
- Three ReAct agents: Qualifier, Scheduler, FollowUp
- Redis checkpointer with thread_id = user_id
- Proper handoff mechanisms and HITL interrupts
- Database query tools with Redis caching
- Meta API integration for messaging
"""
import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.prebuilt import ToolNode

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schemas.state import AgentState
from models.lead import Lead
from utils.redis_client import redis_client
from utils.llm_client import get_llm_response, extract_lead_info, generate_response_message
from tools.agent_tools import (
    query_properties_tool,
    save_lead_tool,
    get_config_tool,
    qualify_lead_with_llm,
    send_instagram_message,
    send_whatsapp_message,
    get_available_calendar_slots,
    book_calendar_event,
    create_hubspot_contact,
    create_hubspot_deal
)

class QualifierAgent:
    """
    Qualifier Agent - Entry point for lead processing.
    
    Responsibilities:
    - Extract lead information from messages
    - Query properties database with Redis caching
    - Score leads using OpenRouter LLM
    - Decide on handoffs based on score and criteria
    """
    
    def __init__(self):
        self.tools = [
            query_properties_tool,
            qualify_lead_with_llm,
            get_config_tool,
            send_instagram_message,
            send_whatsapp_message
        ]
    
    def process(self, state: AgentState) -> Dict[str, Any]:
        """Process lead through qualification"""
        lead = state["lead"]
        messages = state.get("messages", [])
        
        try:
            # Extract information from message if not already present
            if not all([lead.budget, lead.location, lead.property_type]):
                extracted_info = extract_lead_info(lead.message)
                
                if extracted_info.get("budget"):
                    lead.budget = extracted_info["budget"]
                if extracted_info.get("location"):
                    lead.location = extracted_info["location"]
                if extracted_info.get("property_type"):
                    lead.property_type = extracted_info["property_type"]
                if extracted_info.get("timeline"):
                    lead.timeline = extracted_info["timeline"]
            
            # Query properties database
            db_results = []
            if lead.budget and lead.location and lead.property_type:
                db_results = query_properties_tool.invoke({
                    "budget": lead.budget,
                    "location": lead.location,
                    "property_type": lead.property_type
                })
            
            # Qualify lead using LLM
            qualification_result = qualify_lead_with_llm.invoke({
                "budget": lead.budget,
                "location": lead.location,
                "property_type": lead.property_type,
                "timeline": lead.timeline,
                "db_results": db_results
            })
            
            # Update lead with qualification results
            lead.qualified_score = qualification_result["score"]
            lead.add_history_entry(
                f"Lead qualified with score: {qualification_result['score']}",
                "qualifier",
                qualification_result["reasoning"]
            )
            
            # Generate response message
            if not all([lead.budget, lead.location, lead.property_type]):
                # Ask for missing information
                response_msg = generate_response_message(
                    lead.to_dict(),
                    f"Available properties: {len(db_results)}",
                    "qualifier"
                )
            else:
                # Provide qualification feedback
                if qualification_result["score"] > 0.7:
                    response_msg = f"Great! Based on your criteria, I found {len(db_results)} properties that might interest you. Let me connect you with our scheduler to arrange a viewing."
                else:
                    response_msg = f"Thank you for your interest! I found {len(db_results)} properties in your area. Let me share some options with you."
            
            # Send response
            if lead.channel == "ig":
                send_instagram_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            else:
                send_whatsapp_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            
            # Add response to messages
            messages.append({
                "role": "assistant",
                "content": response_msg
            })
            
            # Determine next agent
            next_agent = "followup"
            interrupt = False
            
            # Check for HITL conditions
            if lead.is_high_value():
                next_agent = "scheduler"
                interrupt = True
                lead.add_history_entry("Flagged for HITL review - high value lead", "qualifier")
            elif lead.should_schedule():
                next_agent = "scheduler"
            
            return {
                "lead": lead,
                "messages": messages,
                "db_results": db_results,
                "next_agent": next_agent,
                "interrupt": interrupt
            }
            
        except Exception as e:
            lead.add_history_entry(f"Error in qualification: {str(e)}", "qualifier")
            return {
                "lead": lead,
                "messages": messages,
                "next_agent": "followup",
                "error_message": str(e)
            }

class SchedulerAgent:
    """
    Scheduler Agent - Handles meeting scheduling for qualified leads.
    
    Responsibilities:
    - Query Google Calendar for available slots
    - Book calendar events
    - Log to HubSpot CRM
    - Handle HITL approvals
    """
    
    def __init__(self):
        self.tools = [
            get_available_calendar_slots,
            book_calendar_event,
            create_hubspot_contact,
            create_hubspot_deal,
            send_instagram_message,
            send_whatsapp_message
        ]
    
    def process(self, state: AgentState) -> Dict[str, Any]:
        """Process lead through scheduling"""
        lead = state["lead"]
        messages = state.get("messages", [])
        human_feedback = state.get("human_feedback")
        
        try:
            # Check for HITL approval if needed
            if lead.is_high_value() and not human_feedback:
                # Wait for human approval
                lead.add_history_entry("Waiting for HITL approval", "scheduler")
                return {
                    "lead": lead,
                    "messages": messages,
                    "interrupt": True
                }
            
            # Get available calendar slots
            available_slots = get_available_calendar_slots.invoke({"days_ahead": 7})
            
            # For demo purposes, auto-book the first available slot
            if available_slots and lead.email:
                selected_slot = available_slots[0]
                
                # Book calendar event
                event_result = book_calendar_event.invoke({
                    "start_time": selected_slot,
                    "duration_minutes": 60,
                    "attendee_email": lead.email,
                    "summary": f"Property Tour - {lead.name or lead.user_id}",
                    "description": f"Property tour for {lead.property_type} in {lead.location}, budget: ${lead.budget}"
                })
                
                if "error" not in event_result:
                    lead.meeting_slot = selected_slot
                    lead.status = "scheduled"
                    
                    # Create HubSpot contact and deal
                    contact_result = create_hubspot_contact.invoke({
                        "email": lead.email,
                        "first_name": lead.name or "",
                        "phone": lead.user_id,
                        "lifecycle_stage": "opportunity"
                    })
                    
                    if "error" not in contact_result:
                        deal_result = create_hubspot_deal.invoke({
                            "contact_id": contact_result["contact_id"],
                            "deal_name": f"Property Tour - {lead.user_id}",
                            "amount": lead.budget or 0,
                            "deal_stage": "appointmentscheduled"
                        })
                    
                    # Send confirmation message
                    response_msg = f"Perfect! I've scheduled your property tour for {selected_slot.strftime('%B %d, %Y at %I:%M %p')}. You'll receive a calendar invitation shortly. Looking forward to showing you some great properties!"
                    
                    lead.add_history_entry("Meeting scheduled successfully", "scheduler")
                else:
                    response_msg = "I apologize, but there was an issue scheduling your appointment. Let me connect you with our team to arrange this manually."
                    lead.add_history_entry(f"Scheduling error: {event_result.get('error')}", "scheduler")
            else:
                # Ask for email or provide available slots
                if not lead.email:
                    response_msg = "To schedule your property tour, I'll need your email address. Could you please provide it?"
                else:
                    slots_text = "\n".join([f"- {slot.strftime('%B %d, %Y at %I:%M %p')}" for slot in available_slots[:3]])
                    response_msg = f"Here are some available times for your property tour:\n{slots_text}\n\nWhich time works best for you?"
            
            # Send response
            if lead.channel == "ig":
                send_instagram_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            else:
                send_whatsapp_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            
            # Add response to messages
            messages.append({
                "role": "assistant",
                "content": response_msg
            })
            
            # Save lead
            save_lead_tool.invoke({"lead_data": lead.to_dict()})
            
            return {
                "lead": lead,
                "messages": messages,
                "available_slots": available_slots,
                "next_agent": "END"
            }
            
        except Exception as e:
            lead.add_history_entry(f"Error in scheduling: {str(e)}", "scheduler")
            return {
                "lead": lead,
                "messages": messages,
                "next_agent": "followup",
                "error_message": str(e)
            }

class FollowUpAgent:
    """
    FollowUp Agent - Nurtures low-scoring leads and provides ongoing support.
    
    Responsibilities:
    - Send nurturing messages
    - Provide property suggestions
    - Keep leads engaged for future opportunities
    """
    
    def __init__(self):
        self.tools = [
            query_properties_tool,
            send_instagram_message,
            send_whatsapp_message
        ]
    
    def process(self, state: AgentState) -> Dict[str, Any]:
        """Process lead through follow-up"""
        lead = state["lead"]
        messages = state.get("messages", [])
        db_results = state.get("db_results", [])
        
        try:
            # Generate follow-up message
            if db_results:
                # Share property suggestions
                property_suggestions = []
                for prop in db_results[:2]:  # Limit to 2 properties
                    property_suggestions.append(
                        f"• {prop['property_type']} in {prop['location']} - ${prop['price']:,}"
                    )
                
                response_msg = f"Here are some properties that might interest you:\n\n" + "\n".join(property_suggestions) + "\n\nWould you like more details about any of these, or shall I look for other options?"
            else:
                # General follow-up
                response_msg = generate_response_message(
                    lead.to_dict(),
                    "No specific properties found",
                    "followup"
                )
            
            # Send response
            if lead.channel == "ig":
                send_instagram_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            else:
                send_whatsapp_message.invoke({
                    "user_id": lead.user_id,
                    "message": response_msg
                })
            
            # Add response to messages
            messages.append({
                "role": "assistant",
                "content": response_msg
            })
            
            # Update lead status
            lead.status = "nurtured"
            lead.add_history_entry("Follow-up message sent", "followup")
            
            # Save lead
            save_lead_tool.invoke({"lead_data": lead.to_dict()})
            
            return {
                "lead": lead,
                "messages": messages,
                "next_agent": "END"
            }
            
        except Exception as e:
            lead.add_history_entry(f"Error in follow-up: {str(e)}", "followup")
            return {
                "lead": lead,
                "messages": messages,
                "next_agent": "END",
                "error_message": str(e)
            }

def create_prd_compliant_workflow():
    """
    Create the PRD-compliant LangGraph workflow with proper agent communication.
    
    Returns:
        Compiled LangGraph workflow with Redis checkpointer
    """
    # Initialize agents
    qualifier = QualifierAgent()
    scheduler = SchedulerAgent()
    followup = FollowUpAgent()
    
    # Create Redis checkpointer
    checkpointer = RedisSaver(redis_client)
    
    # Define agent nodes
    def qualifier_node(state: AgentState) -> Dict[str, Any]:
        """Qualifier agent node"""
        return qualifier.process(state)
    
    def scheduler_node(state: AgentState) -> Dict[str, Any]:
        """Scheduler agent node"""
        return scheduler.process(state)
    
    def followup_node(state: AgentState) -> Dict[str, Any]:
        """Follow-up agent node"""
        return followup.process(state)
    
    def interrupt_node(state: AgentState) -> Dict[str, Any]:
        """HITL interrupt node"""
        lead = state["lead"]
        lead.add_history_entry("Interrupted for HITL review", "system")
        return {
            "lead": lead,
            "interrupt": True
        }
    
    # Create the workflow graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("qualifier", qualifier_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("followup", followup_node)
    workflow.add_node("interrupt", interrupt_node)
    
    # Define routing logic
    def route_after_qualifier(state: AgentState) -> str:
        """Route based on qualifier results"""
        if state.get("interrupt", False):
            return "interrupt"
        elif state.get("next_agent") == "scheduler":
            return "scheduler"
        else:
            return "followup"
    
    def route_after_interrupt(state: AgentState) -> str:
        """Route after HITL interrupt"""
        human_feedback = state.get("human_feedback")
        if human_feedback and "approve" in human_feedback.lower():
            return "scheduler"
        else:
            return "followup"
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "qualifier",
        route_after_qualifier,
        {
            "scheduler": "scheduler",
            "followup": "followup",
            "interrupt": "interrupt"
        }
    )
    
    workflow.add_conditional_edges(
        "interrupt",
        route_after_interrupt,
        {
            "scheduler": "scheduler",
            "followup": "followup"
        }
    )
    
    # Add edges to END
    workflow.add_edge("scheduler", END)
    workflow.add_edge("followup", END)
    
    # Set entry point
    workflow.set_entry_point("qualifier")
    
    # Compile with checkpointer and interrupts
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["scheduler"]  # Interrupt before scheduler for HITL
    )
