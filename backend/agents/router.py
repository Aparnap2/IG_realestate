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
from typing import Dict, Any, Literal
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schemas.state import AgentState
from tools.compliance import fair_housing_evaluator, gdpr_tcpa_tracker
from tools.agent_tools import send_instagram_message
from utils.audit import audit_log_event
from config import get_settings

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
    Router Agent implementing PRD-compliant intent classification and compliance gates.
    
    Key Features:
    - Multi-intent detection with priority ordering
    - Fair housing compliance evaluation before any response
    - Temporal context awareness from lead history
    - Confidence-based human escalation
    - Immutable audit logging
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.1,  # Low temperature for consistent routing
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        ).with_structured_output(IntentClassification)
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """
        Process incoming message through intent classification and compliance gates.
        
        Flow:
        1. Extract latest user message and conversation context
        2. Build temporal context from lead history
        3. Classify intent using LLM with structured output
        4. Apply business rules for priority routing
        5. Run compliance evaluators before any response
        6. Route to appropriate agent or flag for human review
        7. Log all decisions to immutable audit trail
        
        Args:
            state: Current conversation state with lead and message history
            
        Returns:
            Updated state with routing decision and compliance checks
        """
        lead = state["lead"]
        messages = state.get("messages", [])
        
        # Log router invocation
        audit_log_event("router_invoked", {
            "lead_id": lead.user_id,
            "message_count": len(messages),
            "lead_status": getattr(lead, 'status', 'unknown')
        })
        
        try:
            # Edge case: No messages yet (defensive programming)
            if not messages:
                return self._handle_empty_conversation(state)
            
            # Get latest user message
            latest_message = messages[-1]
            if latest_message.get("role") != "user":
                return self._handle_non_user_message(state)
            
            # Build context-aware prompt with lead history
            classification = await self._classify_intent(latest_message, lead, messages)
            
            # Apply business rules and priority routing
            routing_decision = self._apply_routing_rules(classification, lead)
            
            # Run compliance evaluators BEFORE any response
            compliance_result = await self._evaluate_compliance(
                latest_message["content"], 
                lead, 
                routing_decision
            )
            
            # Handle compliance violations
            if compliance_result["blocked"]:
                return self._handle_compliance_violation(state, compliance_result)
            
            # Update state with routing decision
            state["current_agent"] = routing_decision["next_agent"]
            state["agent_decision"] = {
                "agent_type": "router",
                "reasoning": classification.reasoning,
                "action": f"route_to_{routing_decision['next_agent']}",
                "confidence": classification.confidence,
                "intent": classification.intent,
                "urgency": classification.urgency_level
            }
            
            # Log successful routing
            audit_log_event("routing_decision", {
                "lead_id": lead.user_id,
                "intent": classification.intent,
                "confidence": classification.confidence,
                "next_agent": routing_decision["next_agent"],
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
7. OFF_TOPIC: Spam, inappropriate, unrelated → Human review

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
        Apply business rules for routing decisions.
        
        Considers lead value, engagement history, and system load.
        """
        next_agent = classification.next_agent
        
        # Business rule: High-value leads get priority routing
        if hasattr(lead, 'budget') and lead.budget and lead.budget > 500000:
            if classification.intent in ["schedule_tour", "new_inquiry"]:
                next_agent = "scheduler"  # Fast-track high-value leads
        
        # Business rule: Low confidence → human review
        if classification.confidence < 0.6:
            next_agent = "human"
        
        # Business rule: Off-topic → always human review
        if classification.intent == "off_topic":
            next_agent = "human"
        
        return {
            "next_agent": next_agent,
            "original_agent": classification.next_agent,
            "business_rule_applied": next_agent != classification.next_agent
        }
    
    async def _evaluate_compliance(
        self, 
        message_content: str, 
        lead: Any, 
        routing_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run compliance evaluators before any agent response.
        
        Checks Fair Housing Act, GDPR, TCPA compliance.
        """
        try:
            # Fair Housing Act evaluation
            fair_housing_result = await fair_housing_evaluator(
                message_content, 
                context={
                    "lead_id": lead.user_id,
                    "budget": getattr(lead, 'budget', None),
                    "location": getattr(lead, 'location', None)
                }
            )
            
            # GDPR/TCPA consent tracking
            gdpr_tcpa_tracker(
                lead_id=lead.user_id,
                event="message_received",
                metadata={
                    "message_length": len(message_content),
                    "intent": routing_decision.get("intent", "unknown"),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "blocked": not fair_housing_result.get("passed", True),
                "violations": fair_housing_result.get("violations", []),
                "neutral_reply": fair_housing_result.get("suggested_replacement", ""),
                "evaluators_run": ["fair_housing", "gdpr_tcpa"]
            }
            
        except Exception as e:
            # Fail-safe: Block on compliance evaluation error
            return {
                "blocked": True,
                "violations": [f"Compliance evaluation error: {str(e)}"],
                "neutral_reply": "Thank you for your message. A team member will respond shortly.",
                "evaluators_run": ["error_fallback"]
            }
    
    def _handle_compliance_violation(
        self, 
        state: AgentState, 
        compliance_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle compliance violations with neutral response and human escalation."""
        lead = state["lead"]
        
        # Send neutral response
        neutral_message = compliance_result.get(
            "neutral_reply", 
            "Let's focus on finding properties that match your needs and preferences."
        )
        
        # Log compliance violation
        audit_log_event("compliance_violation", {
            "lead_id": lead.user_id,
            "violations": compliance_result["violations"],
            "neutral_reply_sent": neutral_message,
            "escalated_to_human": True
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
        
        # Route to human review
        state["current_agent"] = "human"
        state["requires_human_review"] = True
        state["compliance_flags"] = compliance_result["violations"]
        
        return state
    
    def _handle_empty_conversation(self, state: AgentState) -> Dict[str, Any]:
        """Handle edge case of empty conversation."""
        audit_log_event("router_empty_conversation", {
            "lead_id": state["lead"].user_id,
            "action": "default_to_qualifier"
        })
        
        state["current_agent"] = "qualifier"
        state["agent_decision"] = {
            "agent_type": "router",
            "reasoning": "Empty conversation, defaulting to qualification",
            "action": "route_to_qualifier",
            "confidence": 0.5
        }
        
        return state
    
    def _handle_non_user_message(self, state: AgentState) -> Dict[str, Any]:
        """Handle edge case of non-user message as latest."""
        audit_log_event("router_non_user_message", {
            "lead_id": state["lead"].user_id,
            "latest_message_role": state["messages"][-1].get("role", "unknown")
        })
        
        # Continue with current agent or default to followup
        state["current_agent"] = state.get("current_agent", "followup")
        
        return state
    
    def _handle_router_error(self, state: AgentState, error: Exception) -> Dict[str, Any]:
        """Handle router errors with graceful degradation."""
        audit_log_event("router_error", {
            "lead_id": state["lead"].user_id,
            "error": str(error),
            "fallback_action": "route_to_human"
        })
        
        # Fail-safe: Route to human on any router error
        state["current_agent"] = "human"
        state["requires_human_review"] = True
        state["error"] = str(error)
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        return state
    
    def _build_lead_context(self, lead: Any) -> str:
        """Build formatted lead context for LLM prompt."""
        return f"""
- Budget: {getattr(lead, 'budget', 'unknown')}
- Desired bedrooms: {getattr(lead, 'desired_bedrooms', 'unknown')}
- Location: {getattr(lead, 'location', 'unknown')}
- Timeline: {getattr(lead, 'timeline', 'unknown')}
- Status: {getattr(lead, 'status', 'new')}
- Engagement score: {getattr(lead, 'engagement_score', 0.0)}
- Last interaction: {getattr(lead, 'last_interaction_at', 'never')}
        """.strip()
    
    def _build_conversation_context(self, recent_messages: list) -> str:
        """Build formatted conversation context for LLM prompt."""
        if not recent_messages:
            return "No recent conversation history"
        
        context_lines = []
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]  # Truncate long messages
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)

# Conditional edge function for LangGraph routing
def route_to_agent(state: AgentState) -> str:
    """
    LangGraph conditional edge function for routing decisions.
    
    Handles edge cases:
    - Human review flag set → "human"
    - Error state → "error_handler" 
    - Unknown agent → "qualifier" (safe default)
    """
    if state.get("requires_human_review"):
        return "human"
    
    if state.get("error"):
        return "error_handler"
    
    agent = state.get("current_agent", "qualifier")
    
    # Validate agent exists (defensive programming)
    valid_agents = ["qualifier", "scheduler", "followup", "human"]
    if agent not in valid_agents:
        audit_log_event("invalid_agent_route", {
            "invalid_agent": agent,
            "fallback_to": "qualifier"
        })
        return "qualifier"
    
    return agent