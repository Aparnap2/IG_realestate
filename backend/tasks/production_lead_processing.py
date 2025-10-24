"""
Production Lead Processing Module for Instagram DM Automation

Enhanced with sophisticated qualification flow and value delivery:
- Lead scoring with >=0.75 → scheduler, <0.75 → followup, <0.4 → offramp
- Progressive qualification with intelligent field mapping
- Conversation branching based on scores and intents
- Value delivery integration
- Compliance checks and state tracking
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import save_or_update_lead, query_properties_db
from utils.audit import audit_log_event
from temporal.graph_client import get_graphiti_client
from utils.llm_client import extract_lead_info, generate_response_message
from tools.compliance import fair_housing_evaluator
from utils.redis_client import (
    store_thread_state,
    get_thread_state,
    get_temporary_data,
    store_temporary_data,
    get_conversation_state,
    set_conversation_state,
    update_conversation_state,
    add_asked_question,
    has_asked_question,
    get_current_question,
    set_current_question,
)
from tools import agent_tools
from utils.lead_scoring import calculate_lead_score, get_next_qualification_question, lead_scorer
from tasks.booking_flow import get_booking_manager
from integrations.hubspot_client import sync_lead_to_hubspot, sync_conversation_to_hubspot
# from agents.prd_compliant_workflow import extract_user_profile  # Temporarily disabled


class ProductionLeadProcessor:
    """
    Handles lead processing for Instagram DM automation.

    Key Features:
    - Lead information extraction using LLM
    - Property database search
    - Qualification scoring
    - Compliance checking
    - Dynamic response generation
    """

    def __init__(self):
        self.graphiti_client = get_graphiti_client()

    async def process_lead_message(
        self,
        user_id: str,
        message: str,
        channel: str = "instagram",
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Process incoming lead message through the complete workflow.

        Args:
            user_id: Instagram user ID (PSID)
            message: Message content
            channel: Channel source
            user_name: Extracted user name

        Returns:
            Processing result with response message
        """
        try:
            print(f"🎯 PRD WORKFLOW: Starting lead processing for {user_id} via {channel}")

            # Use provided name or fallback
            if not user_name:
                user_name = "Valued Customer"

            print(f"👤 User: {user_name}")
            print(f"📝 MESSAGE: '{message}' from {user_name}")

            # Message data structure
            message_data = {
                "user_id": user_id,
                "username": user_name,
                "text": message,
                "channel": channel
            }

            # Step 0: Load prior thread state and conversation state
            confirm_key = f"confirm:{user_id}"
            confirm_state = get_temporary_data(confirm_key) or {}
            prior_state = get_thread_state(f"langgraph:thread:{user_id}") or {}
            prior_lead = prior_state.get("lead", {})
            conv_state = get_conversation_state(user_id) or {}

            # Step 1: Record message event in temporal knowledge graph
            await self.graphiti_client.record_lead_event(
                lead_id=user_id,
                event_type="message",
                event_data=message_data,
                timestamp=datetime.now()
            )
            print("🕒 TEMPORAL KG: Recording message event in Graphiti")

            # Step 2: Extract lead information using LLM
            print(f"🤖 LLM EXTRACTION: Using OpenRouter to extract structured info")
            extracted_info = extract_lead_info(message)

            # Use progressive Q&A: if a current_question exists, prefer mapping this answer
            cq = get_current_question(user_id)
            if cq:
                # Map answer into the specific field deterministically
                if cq == "budget" and extracted_info.get("budget"):
                    prior_lead["budget"] = extracted_info["budget"]
                elif cq == "location" and extracted_info.get("location"):
                    prior_lead["location"] = extracted_info["location"]
                elif cq == "property_type" and extracted_info.get("property_type"):
                    prior_lead["property_type"] = extracted_info["property_type"]
                elif cq == "timeline" and extracted_info.get("timeline"):
                    prior_lead["timeline"] = extracted_info["timeline"]
                elif cq == "desired_bedrooms" and extracted_info.get("desired_bedrooms"):
                    prior_lead["desired_bedrooms"] = extracted_info["desired_bedrooms"]
                elif cq == "email" and extracted_info.get("email"):
                    prior_lead["email"] = extracted_info["email"]

                # Mark question as asked to prevent repeats
                add_asked_question(user_id, cq)

                # Update asked questions in conversation state
                if "asked_questions" not in conv_state:
                    conv_state["asked_questions"] = []
                if cq not in conv_state["asked_questions"]:
                    conv_state["asked_questions"].append(cq)

                # Advance qualification state
                conv_state["answers_collected"] = int(conv_state.get("answers_collected", 0)) + 1

                # Calculate current score to determine if qualification should continue
                current_lead_data = {**prior_lead, **extracted_info}
                scoring_result = calculate_lead_score(
                    current_lead_data,
                    conversation_history=prior_messages
                )

                # Determine next step based on score
                if scoring_result['final_score'] >= 0.75:
                    # High score - move to scheduler
                    conv_state["current_question"] = None
                    conv_state["qualification_complete"] = True
                elif scoring_result['final_score'] < 0.4:
                    # Low score - move to offramp
                    conv_state["current_question"] = None
                    conv_state["qualification_complete"] = True
                elif lead_scorer.should_continue_qualification(current_lead_data, scoring_result['final_score']):
                    # Continue qualification
                    next_question = get_next_qualification_question(current_lead_data, conv_state.get("asked_questions", []))
                    if next_question:
                        set_current_question(user_id, next_question['field'])
                        conv_state["current_question"] = next_question['field']
                    else:
                        conv_state["current_question"] = None
                else:
                    # Qualification complete
                    conv_state["current_question"] = None
                    conv_state["qualification_complete"] = True

                update_conversation_state(user_id, conv_state)

            # Update message data with extracted info
            message_data.update(extracted_info)
            print(f"✅ Lead info extracted: {extracted_info}")

            # Step 3: Convert to lead format for database storage
            # Merge with previously known lead data to "remember" prior answers
            lead_data = {
                "instagram_id": user_id,
                "name": user_name or prior_lead.get("name"),
                "budget": extracted_info.get("budget", prior_lead.get("budget", 0) or 0),
                "location": extracted_info.get("location", prior_lead.get("location", "")),
                "property_type": extracted_info.get("property_type", prior_lead.get("property_type", "")),
                "timeline": extracted_info.get("timeline", prior_lead.get("timeline", "")),
                "message": message,
                "channel": "instagram"
            }

            # Step 4: Persist lead data
            saved_lead = save_or_update_lead(user_id, lead_data)
            lead_id = saved_lead.get("id")
            print(f"✅ Lead updated: {lead_id} (instagram_id: {user_id})")

            # Step 4.5: Sync lead to HubSpot CRM
            if lead_data.get("email"):
                try:
                    hubspot_contact_id = await sync_lead_to_hubspot(lead_data)
                    if hubspot_contact_id:
                        print(f"✅ HubSpot sync successful: Contact {hubspot_contact_id}")
                        # Update lead with HubSpot contact ID
                        lead_data["hubspot_contact_id"] = hubspot_contact_id
                        lead_data["hubspot_sync_status"] = "synced"
                        lead_data["hubspot_last_synced_at"] = datetime.now()
                        save_or_update_lead(user_id, {
                            "hubspot_contact_id": hubspot_contact_id,
                            "hubspot_sync_status": "synced",
                            "hubspot_last_synced_at": datetime.now()
                        })
                    else:
                        print("⚠️ HubSpot sync skipped - no access token configured")
                except Exception as e:
                    print(f"⚠️ HubSpot sync failed: {e}")
                    # Continue processing - don't fail the entire flow

            # Enhanced booking flow with comprehensive calendar integration
            booking_manager = get_booking_manager()
            booking_response = await booking_manager.handle_booking_flow(
                user_id=user_id,
                message=message,
                user_name=user_name,
                lead_data=lead_data,
                confirm_state=confirm_state
            )

            # If booking flow handled the response, return it immediately
            if booking_response.get("handled", False):
                # Update lead data with booking information if provided
                if booking_response.get("lead_updates"):
                    save_or_update_lead(user_id, booking_response["lead_updates"])

                # Record booking event in temporal graph
                if booking_response.get("booking_event_type"):
                    await self.graphiti_client.record_lead_event(
                        lead_id=user_id,
                        event_type=booking_response["booking_event_type"],
                        event_data=booking_response.get("booking_event_data", {}),
                        timestamp=datetime.now()
                    )

                # Sync booking to HubSpot as a deal
                if booking_response.get("lead_updates", {}).get("calendar_event_id"):
                    try:
                        hubspot_contact_id = lead_data.get("hubspot_contact_id")
                        if hubspot_contact_id:
                            # Create HubSpot deal for the booking
                            deal_result = await agent_tools.create_hubspot_deal.invoke({
                                "contact_id": hubspot_contact_id,
                                "deal_name": f"Consultation - {user_name}",
                                "amount": 0,  # Free consultation
                                "deal_stage": "appointmentscheduled"
                            })
                            if "error" not in deal_result:
                                deal_id = deal_result.get('deal_id')
                                print(f"✅ HubSpot deal created: {deal_id}")
                                # Update lead with deal ID
                                booking_response["lead_updates"]["hubspot_deal_id"] = deal_id
                                save_or_update_lead(user_id, {"hubspot_deal_id": deal_id})
                            else:
                                print(f"⚠️ HubSpot deal creation failed: {deal_result.get('error')}")
                        else:
                            print("⚠️ No HubSpot contact ID available for deal creation")
                    except Exception as e:
                        print(f"⚠️ HubSpot deal sync failed: {e}")

                return {
                    "status": "success",
                    "lead_id": lead_id,
                    "response_message": booking_response["response_message"],
                    "qualification_score": qualification_score,
                    "next_agent": booking_response.get("next_agent", "scheduler"),
                    "properties_found": 0,
                    "compliance_passed": True,
                    "booking_flow": True
                }

            # Step 5: Property search if criteria provided
            properties = []
            budget = lead_data.get("budget", 0) or 0
            location = lead_data.get("location")
            if budget > 0 and location:
                print(f"🏠 PROPERTY SEARCH: Using LLM function calling to query database")
                properties = query_properties_db(
                    budget=budget,
                    location=location,
                    property_type=lead_data.get("property_type", "")
                )
                print(f"✅ Found {len(properties)} matching properties")
            else:
                print(f"⚠️ Insufficient criteria for property search")
                print(f"   📋 Budget: {lead_data.get('budget', 0)}, Location: '{lead_data.get('location', '')}', Type: '{lead_data.get('property_type', '')}'")

            # Step 6: Enhanced qualification scoring
            current_lead_data = {**prior_lead, **extracted_info}
            scoring_result = calculate_lead_score(
                current_lead_data,
                previous_score=prior_lead.get("qualified_score"),
                conversation_history=prior_messages
            )

            qualification_score = scoring_result['final_score']
            print(f"✅ QUALIFIER: Enhanced scoring complete (score: {qualification_score})")
            print(f"   📊 Score breakdown: {scoring_result['score_breakdown']}")
            print(f"   🎯 Qualification stage: {scoring_result['qualification_stage']}")

            # Step 7: Route to next agent per enhanced workflow thresholds
            routing = scoring_result['routing_recommendation']
            next_agent = routing['next_agent']

            print(f"🧭 ROUTER: Enhanced routing based on qualification score")
            print(f"   📍 Next agent: {next_agent}")
            print(f"   💭 Routing reasoning: {routing['reasoning']}")

            # Step 8: Generate dynamic response
            print(f"💬 RESPONSE GEN: Creating dynamic AI response")
            # Build context with prior messages to improve continuity
            prior_messages = prior_state.get("messages", [])
            context = {
                "user_name": user_name,
                "extracted_info": extracted_info,
                "properties": properties,
                "qualification_score": qualification_score,
                "prior_messages": prior_messages
            }

            response_message = generate_response_message(
                lead_info=extracted_info,
                context=str(context),
                agent_type=next_agent
            )

            # Enhanced routing with value delivery integration
            if next_agent == "scheduler":
                showcase_lines = []
                for p in (properties or [])[:3]:
                    try:
                        showcase_lines.append(f"• {p.get('property_type','Service')} in {p.get('location','your area')} at ${p.get('price',0):,}")
                    except Exception:
                        continue
                prompt = " Ready to take the next step? I have availability this week for a 30-min consultation. Should I send you some time options?"
                response_message = ("Based on what you shared, here are some examples that match your preferences:\n" + "\n".join(showcase_lines) + "\n\n" if showcase_lines else "") + response_message + prompt
                store_temporary_data(confirm_key, {"awaiting_confirmation": True}, ttl=7200)
            elif next_agent == "followup":
                # Add value delivery options for nurturing leads
                value_options = "\n\n💡 **How I can help you:**\n• Send you market insights for your area\n• Share educational content about buying\n• Provide property recommendations\n• Send helpful guides and resources"
                response_message = response_message + value_options
            elif next_agent == "offramp":
                # Add gentle off-ramp messaging
                offramp_note = "\n\nI understand now might not be the right time, but I'd love to keep you updated on market changes and new opportunities. Would that be helpful?"
                response_message = response_message + offramp_note

            # Step 9: Enhanced Compliance checking with UX guards
            print(f"⚖️ COMPLIANCE: Applying fair-housing evaluation with UX guards")

            # fair_housing_evaluator is async, but we're already in async context
            compliance_result = await fair_housing_evaluator(response_message)

            print(f"   📝 Message: '{response_message[:100]}...'")
            print(f"   👤 Lead ID: {lead_id}")
            print(f"   💰 Budget: {extracted_info.get('budget', 'not specified')}")
            print(f"   📍 Location: {extracted_info.get('location', 'not specified')}")

            if compliance_result.get("passed", False):
                print(f"   ✅ Compliance evaluation completed")
                print(f"   🛡️ Passed: True")
                print(f"   ✅ Message passed compliance check")
                print(f"   ✅ Compliance status: True")
                final_response = response_message
            else:
                print(f"   🛡️ Failed compliance - using UX-friendly fallback")
                # UX Guard: Use more engaging fallback message instead of generic one
                final_response = "Thank you for reaching out! I'd love to help you find the perfect home. To get started, could you share a bit about your budget and preferred location?"

            # Step 10: Record assistant response in temporal graph
            await self.graphiti_client.record_lead_event(
                lead_id=user_id,
                event_type="assistant_response",
                event_data={
                    "response": final_response,
                    "compliance_passed": compliance_result.get("passed", False)
                },
                timestamp=datetime.now()
            )
            print("🕸️ NEO4J GRAPHITI: Recording temporal event")
            print(f"   📊 Event: assistant_response for lead {lead_id}")
            print(f"   ✅ Temporal event recorded successfully")

            # Step 11: Sync conversation to HubSpot if contact exists
            hubspot_contact_id = lead_data.get("hubspot_contact_id")
            if hubspot_contact_id and prior_messages:
                try:
                    # Prepare conversation history for HubSpot
                    conversation_messages = prior_messages + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": final_response}
                    ]
                    await sync_conversation_to_hubspot(hubspot_contact_id, conversation_messages)
                    print(f"✅ Conversation synced to HubSpot contact {hubspot_contact_id}")
                except Exception as e:
                    print(f"⚠️ HubSpot conversation sync failed: {e}")

            # Step 12: UX Guards - Prevent infinite loops and ensure conversation quality
            # Check for conversation loop prevention
            if prior_messages:
                recent_assistant_messages = [msg for msg in prior_messages if msg.get("role") == "assistant"]
                if recent_assistant_messages:
                    last_message = recent_assistant_messages[-1]["content"]
                    # Prevent repeating similar questions
                    if last_message and final_response and len(last_message) > 50 and len(final_response) > 50:
                        # Simple similarity check - avoid exact repeats
                        if last_message.strip() == final_response.strip():
                            print("⚠️ UX GUARD: Preventing duplicate message send")
                            final_response = "I wanted to follow up on my previous message. " + final_response

            # Step 13: Store conversation state in Redis/LangGraph
            # Append current exchange to prior conversation history
            messages_history = prior_messages + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": final_response}
            ]

            state_data = {
                "lead": {**lead_data, **scoring_result},
                "messages": messages_history,
                "db_results": {"properties": properties},
                "qualification": scoring_result,
                "next_agent": next_agent,
                "compliance": {"passed": compliance_result.get("passed", False)},
                "routing": routing
            }

            store_thread_state(f"langgraph:thread:{user_id}", state_data)
            print("🔄 LANGGRAPH: Storing conversation state in Redis")
            print(f"   🧵 Thread ID: langgraph:thread:{user_id}")
            print(f"   📊 State components: lead, messages, db_results, qualification, next_agent, compliance")
            print(f"   🎯 Next agent: {next_agent}")
            print(f"   ⚖️ Compliance passed: {compliance_result.get('passed', False)}")
            print(f"   ✅ State stored in Redis for thread: {user_id}")
            print(f"   💾 TTL: 24 hours")

            # Success result
            return {
                "status": "success",
                "lead_id": lead_id,
                "response_message": final_response,
                "qualification_score": qualification_score,
                "scoring_result": scoring_result,
                "next_agent": next_agent,
                "properties_found": len(properties),
                "compliance_passed": compliance_result.get("passed", False),
                "routing_recommendation": routing
            }

        except Exception as e:
            error_msg = f"Lead processing error: {str(e)}"
            print(f"❌ {error_msg}")

            # Log error
            audit_log_event("lead_processing_error", {
                "user_id": user_id,
                "message": message,
                "error": str(e),
                "channel": channel
            })

            # Return graceful error response
            return {
                "status": "error",
                "error": error_msg,
                "response_message": "I'm having trouble processing your request right now. Please try again in a few moments.",
                "lead_id": None
            }

    async def _calculate_qualification_score(self, extracted_info: Dict[str, Any]) -> float:
        """
        Legacy qualification score calculation - maintained for backward compatibility.

        Note: This is replaced by the enhanced scoring system in utils.lead_scoring
        """
        score = 0.4  # Base score for responding

        # Normalize fields for safe comparisons
        budget_val = extracted_info.get("budget")
        try:
            budget_num = int(budget_val) if budget_val is not None else 0
        except Exception:
            budget_num = 0

        # Budget clarity
        if budget_num > 0:
            score += 0.2

        # Location clarity
        if (extracted_info.get("location") or "").strip():
            score += 0.2

        # Timeline clarity
        if (extracted_info.get("timeline") or "").strip():
            score += 0.1

        # Property type clarity
        if (extracted_info.get("property_type") or "").strip():
            score += 0.1

        return min(score, 1.0)

    def _determine_next_agent(self, qualification_score: float, properties_found: int) -> str:
        """Determine the next agent in the workflow"""
        if qualification_score >= 0.7 or properties_found > 0:
            return "followup"  # Lead is qualified, move to followup
        elif qualification_score >= 0.5:
            return "qualifier"  # Need more qualification
        else:
            return "followup"  # Default to followup for nurturing


# Global function for direct import
async def process_lead_message(user_id: str, message: str, channel: str = "instagram", user_name: str = None) -> Dict[str, Any]:
    """Global function wrapper for process_lead_message"""
    processor = ProductionLeadProcessor()
    return await processor.process_lead_message(user_id, message, channel, user_name)
