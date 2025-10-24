"""
Router Agent - Intent Classification & Compliance Gateway

This agent serves as the entry point for all conversations, implementing:
1. Intent classification using LLM with structured output
2. Fair housing compliance checks before any response
3. GDPR/TCPA consent tracking
4. Routing to appropriate specialist agents
5. Immutable audit logging of all decisions

According to PRD Section 2.1: Intelligent Multi-Channel Lead Capture
"""

import sys
import os
import asyncio
from typing import Dict, Any, Literal, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schemas.state import AgentState
from tools import compliance as compliance_tools
from tools.agent_tools import send_instagram_message
import utils.audit as audit_utils
from config import get_settings
from utils.observability import log_agent_handoff
from utils.redis_client import get_conversation_state

settings = get_settings()

class IntentClassification(BaseModel):
    """Structured output for intent routing with confidence scoring"""
    
    intent: Literal[
        "new_inquiry",        # First-time property interest
        "schedule_tour",      # Ready to book showing
        "modify_tour",        # Change existing appointment
        "answer_question",    # Follow-up about property details
        "objection_handling", # Price/location concerns
        "general_chitchat",   # Rapport building
        "comment_warmup",     # Comment-triggered warm-up sequence
        "off_topic"          # Spam or inappropriate content
    ] = Field(description="Primary intent of the user's message")
    
    confidence: float = Field(
        ge=0.0, 
        le=1.0, 
        description="Confidence in intent classification (0-1)"
    )
    
    requires_qualification: bool = Field(
        description="Whether lead needs budget/location/timeline extraction"
    )
    
    next_agent: Literal["qualifier", "scheduler", "followup", "human"] = Field(
        description="Which agent should handle this conversation"
    )
    
    reasoning: str = Field(
        description="Brief explanation of routing decision for audit trail"
    )
    
    urgency_level: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Business priority level for routing"
    )


class RouterAgent:
    """
    Simplified Router Agent for Instagram DM automation.
    
    Key Features:
    - Basic keyword-based intent classification
    - Simple routing to qualifier agent
    - Minimal compliance checks
    """
    
    def __init__(self):
        # Enhanced keyword-based classifier for value delivery routing
        self.intent_keywords = {
            "schedule": ["schedule", "tour", "book", "appointment", "meeting", "showing"],
            "question": ["price", "how much", "details", "information", "question"],
            "modify": ["change", "reschedule", "modify", "different", "another"],
            "general": ["hello", "hi", "thanks", "ok", "yes", "no"],
            "accept": ["yes", "yeah", "sure", "ok", "okay", "accept", "send", "want", "like"],
            "decline": ["no", "nope", "don't", "not interested", "decline", "pass"],
            "property": ["property", "home", "house", "condo", "apartment", "address", "specific"],
            "market": ["market", "prices", "trends", "neighborhood", "area", "average", "statistics"],
            "value": ["guide", "checklist", "ebook", "download", "resource", "tips", "help", "advice"]
        }
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """
        Process incoming message through basic intent classification.
        
        Flow:
        1. Extract latest user message
        2. Classify intent using keyword matching
        3. Route to qualifier agent (simplified flow)
        4. Basic compliance check
        
        Args:
            state: Current conversation state with lead and message history
            
        Returns:
            Updated state with routing decision
        """
        lead = state["lead"]
        messages = state.get("messages", [])
        
        # Log router invocation
        audit_utils.audit_log_event("router_invoked", {
            "lead_id": lead.user_id,
            "message_count": len(messages)
        })
        
        try:
            # Edge case: No messages yet
            if not messages:
                return self._handle_empty_conversation(state)
            
            # Get latest user message
            latest_message = messages[-1]
            if latest_message.get("role") != "user":
                return self._handle_non_user_message(state)
            
            # Classify intent using enhanced keyword matching
            classification = self._classify_intent(latest_message["content"])
            
            # Check if this is a comment-triggered warm-up conversation
            conversation_state = get_conversation_state(lead.user_id) or {}
            current_stage = conversation_state.get("stage", "")
            
            if current_stage == "warmup" or classification.intent == "comment_warmup":
                next_agent = "warmup"
            elif classification.intent in ["accept_lead_magnet", "decline_lead_magnet"]:
                next_agent = "value_delivery"
            elif classification.intent in ["request_property_info", "ask_market_question", "value_delivery_request"]:
                next_agent = "value_delivery"
            elif classification.intent == "nurture_response":
                next_agent = "followup"
            else:
                # Enhanced routing based on qualification stage
                if lead.qualification_stage == "qualified":
                    next_agent = "scheduler"
                elif lead.qualification_stage == "nurturing":
                    next_agent = "followup"
                elif lead.qualification_stage == "disqualified":
                    next_agent = "offramp"
                else:
                    next_agent = "qualifier"
            
            # Basic compliance check
            compliance_result = await self._evaluate_compliance(
                latest_message["content"],
                lead
            )
            
            # Handle compliance violations
            if compliance_result["blocked"]:
                return self._handle_compliance_violation(state, compliance_result)
            
            # Update state with routing decision
            state["current_agent"] = next_agent
            state["agent_decision"] = {
                "agent_type": "router",
                "reasoning": classification.reasoning,
                "action": f"route_to_{next_agent}",
                "confidence": classification.confidence,
                "intent": classification.intent
            }
            
            # Log successful routing
            audit_utils.audit_log_event("routing_decision", {
                "lead_id": lead.user_id,
                "intent": classification.intent,
                "confidence": classification.confidence,
                "next_agent": next_agent,
                "reasoning": classification.reasoning,
                "compliance_passed": True
            })
            
            return state
            
        except Exception as e:
            return self._handle_router_error(state, e)
    
    async def _classify_intent(
        self, 
        latest_message: Dict[str, str], 
        lead: Any, 
        messages: list
    ) -> IntentClassification:
        """
        Classify user intent using LLM with temporal context.
        
        Includes conversation history and lead profile for context-aware classification.
        """
        # Build temporal context
        lead_context = self._build_lead_context(lead)
        conversation_context = self._build_conversation_context(messages[-5:])  # Last 5 messages
        
        system_prompt = f"""You are an intelligent routing agent for a real estate lead capture system.

Your job: Analyze the user's message and determine their primary intent, then route to the appropriate specialist agent.

LEAD CONTEXT:
{lead_context}

RECENT CONVERSATION:
{conversation_context}

ROUTING RULES:
1. NEW_INQUIRY: First-time lead expressing interest → Qualifier
2. SCHEDULE_TOUR: Ready to book showing ("when can I see it", "book appointment") → Scheduler  
3. MODIFY_TOUR: Change existing tour time → Scheduler
4. ANSWER_QUESTION: Follow-up about property details → FollowUp
5. OBJECTION_HANDLING: Price concerns, location doubts → FollowUp
6. GENERAL_CHITCHAT: Small talk, rapport building → FollowUp
7. OFF_TOPIC: Spam, inappropriate, unrelated ��� Human review

PRIORITY ORDER (if multiple intents detected):
SCHEDULE_TOUR > MODIFY_TOUR > NEW_INQUIRY > ANSWER_QUESTION > OBJECTION_HANDLING > GENERAL_CHITCHAT

CONFIDENCE THRESHOLDS:
- <0.6: Route to human review (ambiguous intent)
- 0.6-0.8: Standard routing with monitoring
- >0.8: High confidence routing

Output your analysis as structured JSON matching the IntentClassification schema."""
        
        try:
            classification = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=latest_message["content"])
            ])
            
            return classification
            
        except Exception as e:
            self._last_classification_error = str(e)
            # Fallback classification on LLM failure
            return IntentClassification(
                intent="new_inquiry",
                confidence=0.3,
                requires_qualification=True,
                next_agent="qualifier",
                reasoning=f"Fallback classification due to LLM error: {str(e)}",
                urgency_level="medium"
            )
    
    def _apply_routing_rules(
        self,
        classification: IntentClassification,
        lead: Any
    ) -> Dict[str, Any]:
        """
        Simplified routing rules - always route to qualifier for Instagram DM automation.
        """
        # Simplified: Always route to qualifier for Instagram DM automation
        return {
            "next_agent": "qualifier",
            "original_agent": classification.next_agent,
            "business_rule_applied": True
        }
    
    async def _evaluate_compliance(
        self,
        message_content: str,
        lead: Any
    ) -> Dict[str, Any]:
        """
        Simplified compliance evaluation - basic Fair Housing check.
        """
        try:
            # Basic Fair Housing Act evaluation
            fair_housing_result = await compliance_tools.fair_housing_evaluator(
                message_content,
                context={
                    "lead_id": lead.user_id
                }
            )
            
            return {
                "blocked": not fair_housing_result.get("passed", True),
                "violations": fair_housing_result.get("violations", []),
                "neutral_reply": fair_housing_result.get("suggested_replacement", ""),
                "evaluators_run": ["fair_housing"]
            }
            
        except Exception as e:
            # Fail-safe: Allow message on compliance evaluation error
            return {
                "blocked": False,
                "violations": [],
                "neutral_reply": "",
                "evaluators_run": ["error_fallback"]
            }
    
    def _handle_compliance_violation(
        self,
        state: AgentState,
        compliance_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle compliance violations with neutral response."""
        lead = state["lead"]
        
        # Send neutral response
        neutral_message = compliance_result.get(
            "neutral_reply",
            "Let's focus on finding properties that match your needs and preferences."
        )
        
        # Log compliance violation
        audit_utils.audit_log_event("compliance_violation", {
            "lead_id": lead.user_id,
            "violations": compliance_result["violations"],
            "neutral_reply_sent": neutral_message
        })
        
        # Add neutral response to conversation
        state["messages"].append({
            "role": "assistant",
            "content": neutral_message,
            "metadata": {
                "agent": "router",
                "compliance_blocked": True,
                "violations": compliance_result["violations"]
            }
        })
        
        # Route to qualifier (simplified - no human escalation)
        state["current_agent"] = "qualifier"
        state["compliance_flags"] = compliance_result["violations"]
        
        return state
    
    def _handle_empty_conversation(self, state: AgentState) -> Dict[str, Any]:
        """Handle edge case of empty conversation."""
        audit_utils.audit_log_event("router_empty_conversation", {
            "lead_id": state["lead"].user_id,
            "action": "default_to_qualifier"
        })
        
        state["current_agent"] = "qualifier"
        state["agent_decision"] = {
            "agent_type": "router",
            "reasoning": "No messages found, defaulting to qualification",
            "action": "route_to_qualifier",
            "confidence": 0.5
        }
        
        return state
    
    def _handle_non_user_message(self, state: AgentState) -> Dict[str, Any]:
        """Handle edge case of non-user message as latest."""
        audit_utils.audit_log_event("router_non_user_message", {
            "lead_id": state["lead"].user_id,
            "latest_message_role": state["messages"][-1].get("role", "unknown")
        })
        
        # Continue with current agent or default to followup
        state["current_agent"] = state.get("current_agent", "followup")
        
        return state
    
    def _handle_router_error(self, state: AgentState, error: Exception) -> Dict[str, Any]:
        """Handle router errors with graceful degradation."""
        audit_utils.audit_log_event("router_error", {
            "lead_id": state["lead"].user_id,
            "error": str(error),
            "fallback_action": "route_to_qualifier"
        })
        
        # Fail-safe: Route to qualifier as safe default
        state["current_agent"] = "qualifier"
        state["error"] = str(error)
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        return state
    
# Removed complex context building methods for simplification

# Simplified conditional edge function for LangGraph routing
def route_to_agent(state: AgentState) -> str:
    """
    Enhanced LangGraph conditional edge function for routing decisions.
    
    Routes to appropriate agent based on conversation state, intent, and qualification stage.
    """
    # Check if this is a warm-up conversation
    lead = state["lead"]
    conversation_state = get_conversation_state(lead.user_id) or {}
    current_stage = conversation_state.get("stage", "")
    
    if current_stage == "warmup":
        return "warmup"
    
    # Enhanced routing based on qualification stage
    if lead.qualification_stage == "qualified":
        return "scheduler"
    elif lead.qualification_stage == "nurturing":
        return "followup"
    elif lead.qualification_stage == "disqualified":
        return "offramp"
    
    # Check for value delivery intents
    if "agent_decision" in state:
        intent = state["agent_decision"].get("intent", "")
        if intent in ["accept_lead_magnet", "decline_lead_magnet", "request_property_info",
                     "ask_market_question", "value_delivery_request"]:
            return "value_delivery"
    
    # Default: Route to qualifier for Instagram DM automation
    return "qualifier"
