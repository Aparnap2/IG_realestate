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

# Add parent directory to path
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
# Removed old booking_flow import - now using new Self-Driving Booking Ops 2.0
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
            try:
                extracted_info = extract_lead_info(message)
                if not extracted_info or "error" in extracted_info:
                    print(f"⚠️ LLM extraction failed, using fallback extraction")
                    extracted_info = fallback_extract_lead_info(message)
            except Exception as e:
                print(f"⚠️ LLM extraction error: {e}, using fallback extraction")
                extracted_info = fallback_extract_lead_info(message)

            # Use progressive Q&A: if a current_question exists, prefer mapping this answer
            cq = get_current_question(user_id)
            if cq:
                # Map answer into specific field deterministically
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

                update_conversation_state(user_id, conv_state)
                
                # For progressive Q&A responses, skip the rest of the main flow and return early
                return {
                    "status": "success",
                    "lead_id": None,  # Will be set on next message
                    "response_message": "Thanks for that information! Let me continue gathering details to help you better.",
                    "qualification_score": None,  # Will be calculated on next message
                    "next_agent": "qualifier",
                    "properties_found": 0,
                    "compliance_passed": True,
                    "progressive_qa": True
                }

            # Update message data with extracted info
            message_data.update(extracted_info)
            print(f"✅ Lead info extracted: {extracted_info}")

            # Step 3: Convert to lead format for database storage
            # Merge with previously known lead data to "remember" prior answers
            lead_data = {
                "instagram_id": user_id,
                "name": user_name or prior_lead.get("name"),
                "budget": self._safe_int_convert(extracted_info.get("budget", prior_lead.get("budget", 0))),
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

            # Step 5: Calculate qualification score and determine routing
            current_lead_data = {**prior_lead, **extracted_info}
            # Ensure budget is properly converted to int for scoring
            if "budget" in current_lead_data:
                current_lead_data["budget"] = self._safe_int_convert(current_lead_data["budget"])
            scoring_result = calculate_lead_score(
                current_lead_data,
                previous_score=prior_lead.get("qualified_score"),
                conversation_history=prior_state.get("messages", [])
            )
            
            qualification_score = scoring_result['final_score']
            print(f"✅ QUALIFIER: Enhanced scoring complete (score: {qualification_score})")
            print(f"   📊 Score breakdown: {scoring_result['score_breakdown']}")
            print(f"   🎯 Qualification stage: {scoring_result['qualification_stage']}")

            # Step 6: Booking flow now handled by Self-Driving Booking Ops 2.0 state machine
            # The new system uses scheduler agent with deterministic state transitions
            # Booking is now handled automatically by the LangGraph workflow when leads are qualified
            booking_response = None
            # Removed old booking flow logic - now using new state machine approach

            # Placeholder for booking response handling (now handled by workflow)
            if booking_response and booking_response.get("status") in ["email_capture_required", "slots_offered", "booking_confirmed"]:
                # Update lead data with booking information if provided
                if booking_response.get("status") == "booking_confirmed":
                    lead_updates = {
                        "meeting_slot": booking_response.get("meeting_time"),
                        "calendar_event_id": booking_response.get("event_id"),
                        "meeting_link": booking_response.get("meeting_link"),
                        "status": "scheduled"
                    }
                    save_or_update_lead(user_id, lead_updates)

                    # Record booking event in temporal graph
                    await self.graphiti_client.record_lead_event(
                        lead_id=user_id,
                        event_type="booking_confirmed",
                        event_data=booking_response,
                        timestamp=datetime.now()
                    )

                    # Sync booking to HubSpot as a deal
                    hubspot_contact_id = lead_data.get("hubspot_contact_id")
                    if hubspot_contact_id:
                        try:
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
                                save_or_update_lead(user_id, {"hubspot_deal_id": deal_id})
                            else:
                                print(f"⚠️ HubSpot deal creation failed: {deal_result.get('error')}")
                        except Exception as e:
                            print(f"⚠️ HubSpot deal sync failed: {e}")

                return {
                    "status": "success",
                    "lead_id": lead_id,
                    "response_message": booking_response["message"],
                    "qualification_score": qualification_score,
                    "next_agent": "scheduler",
                    "properties_found": 0,
                    "compliance_passed": True,
                    "booking_flow": True
                }

            # Step 7: Property search if criteria provided
            properties = []
            budget = self._safe_int_convert(lead_data.get("budget", 0))
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

            # Step 8: Route to next agent per enhanced workflow thresholds
            routing = scoring_result['routing_recommendation']
            next_agent = routing['next_agent']

            print(f"🧭 ROUTER: Enhanced routing based on qualification score")
            print(f"   📍 Next agent: {next_agent}")
            print(f"   💭 Routing reasoning: {routing['reasoning']}")

            # Step 9: Generate dynamic response
            print(f"💬 RESPONSE GEN: Creating dynamic AI response")
            # Build context with prior messages to improve continuity
            prior_messages = prior_state.get("messages", [])
            
            # Check for affirmative responses to progress conversation
            message_lower = message.lower().strip()
            is_affirmative = any(word in message_lower for word in ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'definitely', 'absolutely'])
            
            # Special handling for affirmative responses
            if is_affirmative and len(prior_messages) > 0:
                last_assistant_msg = prior_messages[-1].get("content", "") if prior_messages[-1].get("role") == "assistant" else ""
                
                # If last message was about neighborhoods/areas, move to next qualification step
                if any(word in last_assistant_msg.lower() for word in ['neighborhood', 'area', 'location']):
                    # Get next qualification question
                    next_q = get_next_qualification_question(current_lead_data, conv_state.get("asked_questions", []))
                    if next_q:
                        set_current_question(user_id, next_q['field'])
                        conv_state["current_question"] = next_q['field']
                        update_conversation_state(user_id, conv_state)
                        
                        response_message = f"Great! Since you're interested in those areas, let me gather a bit more information to help you better. {next_q['question']}"
                    else:
                        response_message = "Great! I have a good sense of what you're looking for. Based on your budget of $250k near New York, would you like me to send you some specific property listings, or would you prefer to schedule a call to discuss your options in more detail?"
                else:
                    # Default affirmative handling
                    response_message = "Excellent! I'm excited to help you find the perfect property. Let me know what specific aspects you'd like to focus on next, or if you have any questions about the areas I mentioned."
            else:
                # Standard response generation
                context = {
                    "user_name": user_name,
                    "extracted_info": extracted_info,
                    "properties": properties,
                    "qualification_score": qualification_score,
                    "prior_messages": prior_messages
                }

                try:
                    response_message = generate_response_message(
                        lead_info=extracted_info,
                        context=str(context),
                        agent_type=next_agent
                    )
                    if not response_message or "error" in response_message.lower():
                        print(f"⚠️ LLM response generation failed, using fallback")
                        response_message = generate_fallback_response(extracted_info, next_agent, user_name)
                except Exception as e:
                    print(f"⚠️ LLM response generation error: {e}, using fallback")
                    response_message = generate_fallback_response(extracted_info, next_agent, user_name)

            # Enhanced routing with value delivery integration (only for non-affirmative responses)
            if not is_affirmative or len(prior_messages) == 0:
                if next_agent == "scheduler":
                    showcase_lines = []
                    for p in (properties or [])[:3]:
                        try:
                            showcase_lines.append(f"• {p.get('property_type','Service')} in {p.get('location','your area')} at ${p.get('price',0):,}")
                        except Exception:
                            continue
                    prompt = " Ready to take the next step? I have availability this week for a 30-min consultation. Should I send you some time options?"
                    showcase_text = ("Based on what you shared, here are some examples that match your preferences:\n" + "\n".join(showcase_lines) + "\n\n" if showcase_lines else "")
                    response_message = showcase_text + response_message + prompt
                    store_temporary_data(confirm_key, {"awaiting_confirmation": True}, ttl=7200)
                elif next_agent == "followup":
                    # Add contextual value delivery options (less repetitive)
                    if qualification_score < 0.6:
                        value_options = "\n\n💡 **Next steps:**\n• I can share specific property listings in your budget\n• Send market insights for New York area\n• Schedule a call to discuss your preferences"
                    else:
                        value_options = "\n\n💡 **How I can help:**\n• Send you tailored property recommendations\n• Share market insights for your target areas\n• Schedule viewings for interested properties"
                    response_message = response_message + value_options
                elif next_agent == "offramp":
                    # Add gentle off-ramp messaging
                    offramp_note = "\n\nI understand now might not be the right time, but I'd love to keep you updated on market changes and new opportunities. Would that be helpful?"
                    response_message = response_message + offramp_note

            # Step 10: Enhanced Compliance checking with UX guards
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
            # Step 10.5: Instagram message length validation
            if channel == "instagram":
                final_response = self._validate_and_truncate_message(final_response)

            # Step 11: Record assistant response in temporal graph
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

            # Step 12: Sync conversation to HubSpot if contact exists
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

            # Step 13: UX Guards - Prevent infinite loops and ensure conversation quality
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

            # Step 14: Store conversation state in Redis/LangGraph
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

    def _safe_int_convert(self, value) -> int:
        """
        Safely convert a value to integer, handling string and None values.
        
        Args:
            value: Value to convert (could be string, int, None, etc.)
            
        Returns:
            Integer value, defaulting to 0 if conversion fails
        """
        if value is None:
            return 0
        
        try:
            if isinstance(value, str):
                # Remove common currency symbols and whitespace
                cleaned = value.replace('$', '').replace(',', '').strip()
                return int(cleaned) if cleaned else 0
            return int(value)
        except (ValueError, TypeError):
            return 0

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

    def _validate_and_truncate_message(self, message: str) -> str:
        """
        Validate and truncate message for Instagram DM character limit.
        
        Args:
            message: The message to validate
            
        Returns:
            Validated and potentially truncated message
        """
        if not message:
            return message
        
        # Instagram DM limit is 1000 characters
        INSTAGRAM_LIMIT = 1000
        
        if len(message) <= INSTAGRAM_LIMIT:
            return message
        
        # Truncate with smart breaking
        truncated = message[:INSTAGRAM_LIMIT-10] + "... [truncated]"
        print(f"⚠️ Instagram message truncated: {len(message)} -> {len(truncated)} chars")
        
        return truncated

    def _determine_next_agent(self, qualification_score: float, properties_found: int) -> str:
        """Determine the next agent in the workflow"""
        if qualification_score >= 0.7 or properties_found > 0:
            return "followup"  # Lead is qualified, move to followup
        elif qualification_score >= 0.5:
            return "qualifier"  # Need more qualification
        else:
            return "followup"  # Default to followup for nurturing

    def fallback_extract_lead_info(self, message: str) -> Dict[str, Any]:
        """
        Fallback lead information extraction using regex patterns when LLM fails.
        
        Args:
            message: The lead's message
            
        Returns:
            Dictionary with basic extracted information
        """
        import re
        
        extracted = {
            "budget": None,
            "location": None,
            "property_type": None,
            "timeline": None,
            "other_details": message
        }
        
        message_lower = message.lower()
        
        # Extract budget patterns
        budget_patterns = [
            r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|thousand|m|million|)',
            r'(\d+(?:,\d{3})*)\s*(?:dollars?|usd|)',
            r'budget.*?(\d+(?:,\d{3})*)',
            r'around.*?(\d+(?:,\d{3})*)',
            r'about.*?(\d+(?:,\d{3})*)'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                budget_str = match.group(1).replace(',', '')
                try:
                    budget = int(budget_str)
                    if 'k' in message_lower:
                        budget *= 1000
                    elif 'm' in message_lower:
                        budget *= 1000000
                    extracted["budget"] = budget
                    break
                except ValueError:
                    continue
        
        # Extract location patterns
        location_patterns = [
            r'in\s+([a-zA-Z\s]+?)(?:\s|$|,|\.|\!)',
            r'near\s+([a-zA-Z\s]+?)(?:\s|$|,|\.|\!)',
            r'around\s+([a-zA-Z\s]+?)(?:\s|$|,|\.|\!)',
            r'([a-zA-Z\s]+?)(?:\s+area|\s+city|\s+town)',
            r'(new york|nyc|los angeles|la|chicago|houston|phoenix|philadelphia|san antonio|san diego|dallas|san jose|austin|jacksonville|fort worth|columbus|charlotte|san francisco|indianapolis|seattle|denver|washington dc|boston|detroit|nashville|portland|oklahoma city|las vegas|milwaukee|albuquerque|tucson|fresno|sacramento|kansas city|mesa|atlanta|kansas city|omaha|miami|oakland|tulsa|wichita|new orleans|arlington|tampa|honolulu|anaheim|santa ana|riverside|corpus christi|lexington|pittsburgh|anchorage|stockton|cincinnati|st. paul|toledo|greensboro|newark|plano|lincoln|buffalo|jersey city|chula vista|orlando|norfolk|chandler|laredo|madison|durham|winston salem|lubbock|baton rouge|north las vegas|reno|glendale|garland|hialeah|raleigh|akron|irvine|chesapeake|gilbert|baton rouge)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip().title()
                if len(location) > 2:  # Filter out very short matches
                    extracted["location"] = location
                    break
        
        # Extract property type patterns
        property_patterns = [
            r'(\d+)\s*(?:bedroom|bed|br)',
            r'(house|condo|apartment|townhouse|villa|studio|loft|penthouse|duplex)',
            r'(1bhk|2bhk|3bhk|4bhk)',
            r'(single family|multi family|detached|attached)'
        ]
        
        for pattern in property_patterns:
            match = re.search(pattern, message_lower)
            if match:
                prop_type = match.group(1).strip()
                if prop_type.isdigit():
                    # Convert bedroom count to property type
                    bedrooms = int(prop_type)
                    if bedrooms == 1:
                        extracted["property_type"] = "1BHK"
                    elif bedrooms == 2:
                        extracted["property_type"] = "2BHK"
                    elif bedrooms == 3:
                        extracted["property_type"] = "3BHK"
                    else:
                        extracted["property_type"] = f"{bedrooms}BHK"
                else:
                    extracted["property_type"] = prop_type.title()
                break
        
        # Extract timeline patterns
        timeline_patterns = [
            r'(immediately|now|asap|right away|urgent)',
            r'(\d+)\s*(?:month|months?)',
            r'(next\s+week|this\s+week)',
            r'(soon|shortly|quickly)',
            r'(\d+)\s*(?:year|years?)'
        ]
        
        for pattern in timeline_patterns:
            match = re.search(pattern, message_lower)
            if match:
                timeline = match.group(1).strip()
                extracted["timeline"] = timeline.title()
                break
        
        return extracted

    def generate_fallback_response(self, extracted_info: Dict[str, Any], agent_type: str, user_name: str) -> str:
        """
        Generate fallback response when LLM fails.
        
        Args:
            extracted_info: Information about the lead
            agent_type: Type of agent generating response
            user_name: Lead's name
            
        Returns:
            Generated fallback response
        """
        name = user_name or "there"
        
        if agent_type == "qualifier":
            missing_info = []
            if not extracted_info.get("budget"):
                missing_info.append("budget range")
            if not extracted_info.get("location"):
                missing_info.append("preferred location")
            if not extracted_info.get("property_type"):
                missing_info.append("property type")
            
            if missing_info:
                return f"Hi {name}! I'm excited to help you find your perfect property. To get started, could you please share your {', '.join(missing_info)}? This will help me provide you with the best options."
            else:
                return f"Thank you for the information, {name}! I'm reviewing your requirements and will get back to you with some great property options shortly."
        
        elif agent_type == "scheduler":
            return f"Great news, {name}! You're qualified for our premium consultation service. I have availability this week for a 30-minute call to discuss your property needs. What day and time works best for you?"
        
        elif agent_type == "followup":
            budget = extracted_info.get("budget", "your budget")
            location = extracted_info.get("location", "your preferred area")
            return f"Thanks for your interest, {name}! Based on what you've shared about a budget of ${budget:,} in {location}, I have some excellent options for you. Would you like me to send specific property listings or schedule a call to discuss further?"
        
        elif agent_type == "offramp":
            return f"Thank you for reaching out, {name}! I understand you may be in the early stages of your property search. Feel free to come back anytime when you're ready to explore options. I'm here to help!"
        
        else:
            return f"Hi {name}! I'm here to help you find your perfect property. Please share your budget range and preferred location, and I'll provide you with the best available options."


# Global function for direct import
async def process_lead_message(user_id: str, message: str, channel: str = "instagram", user_name: str = None) -> Dict[str, Any]:
    """Global function wrapper for process_lead_message"""
    processor = ProductionLeadProcessor()
    return await processor.process_lead_message(user_id, message, channel, user_name)


# Global fallback functions for use outside the class
def fallback_extract_lead_info(message: str) -> Dict[str, Any]:
    """Global fallback function for lead extraction"""
    processor = ProductionLeadProcessor()
    return processor.fallback_extract_lead_info(message)


def generate_fallback_response(extracted_info: Dict[str, Any], agent_type: str, user_name: str) -> str:
    """Global fallback function for response generation"""
    processor = ProductionLeadProcessor()
    return processor.generate_fallback_response(extracted_info, agent_type, user_name)
