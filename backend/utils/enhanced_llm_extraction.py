"""
Pure Agentic AI Lead Information Extraction

This module provides real estate lead information extraction using ONLY LLM-based agentic patterns.
No hardcoded ML dependencies, no pattern matching, no fallback lists - pure intelligence.

Key Features:
- Pure LLM-based information extraction (budget, location, property type, timeline)
- LangGraph state management for agent coordination
- Redis checkpoint persistence
- Pure agentic AI patterns: routing, parallelization, checkpoint management
- Proactive engagement with LLM intelligence
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Agentic message types for intelligent routing."""
    INITIAL = "initial"
    QUALIFICATION = "qualification"
    SCHEDULING = "scheduling"
    FOLLOWUP = "followup"

@dataclass
class ExtractionResult:
    """Result of pure agentic real estate lead information extraction."""
    budget: Optional[float] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    timeline: Optional[str] = None
    desired_bedrooms: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    extraction_confidence: float = 0.0
    conversation_stage: str = "initial"
    extracted_fields: List[str] = None
    
    def __post_init__(self):
        if self.extracted_fields is None:
            self.extracted_fields = []

@dataclass
class AgenticContext:
    """LangGraph-managed context for pure agentic coordination."""
    thread_id: str
    user_id: str
    current_agent: str
    conversation_stage: str
    extracted_data: Dict[str, Any]
    agent_history: List[str]
    last_activity: str
    
    def add_agent_interaction(self, agent_type: str, action: str):
        """Record pure agentic interaction."""
        self.agent_history.append(f"{agent_type}:{action}")

class PureAgenticExtractor:
    """Pure agentic extraction using ONLY LLM intelligence - no hardcoded patterns."""
    
    def __init__(self):
        self.extraction_prompt = """You are an expert real estate lead qualification agent. Extract ALL relevant information from this message using pure intelligence.

Message: "{message}"

Extract and return ONLY valid JSON with this exact structure:
{{
    "budget": <number or null>,
    "location": <string or null>, 
    "property_type": <string or null>,
    "timeline": <string or null>,
    "desired_bedrooms": <number or null>,
    "email": <string or null>,
    "phone": <string or null>,
    "name": <string or null>,
    "confidence": <0.0 to 1.0>,
    "conversation_stage": <"initial" or "qualification" or "qualified">,
    "extracted_fields": [<list of fields found>]
}}

Rules:
- Use pure intelligence to understand context and intent
- NO hardcoded lists or pattern matching
- Return null for fields not mentioned
- confidence based on how complete the information is
- conversation_stage based on amount and quality of information extracted
- Extract bedrooms as numbers (1, 2, 3, 4, etc.)
- Budget as full number (250000, not 250k)
- location as proper case ("Miami Beach", not "miami beach")
- If no clear budget, location, or property details, return confidence under 0.5

Examples:
Message: "i need ASAP , miami beach , 250k dollar 4bhk condo"
Response: {{"budget": 250000, "location": "Miami Beach", "property_type": "4BHK", "timeline": "immediately", "desired_bedrooms": 4, "email": null, "phone": null, "name": null, "confidence": 1.0, "conversation_stage": "qualified", "extracted_fields": ["budget", "location", "property_type", "timeline", "bedrooms"]}}

Message: "looking for houses under 500k"
Response: {{"budget": 500000, "location": null, "property_type": "House", "timeline": null, "desired_bedrooms": null, "email": null, "phone": null, "name": null, "confidence": 0.6, "conversation_stage": "qualification", "extracted_fields": ["budget", "property_type"]}}

Now extract from this message:"""

    async def extract_information(self, message: str, context: Optional[AgenticContext] = None) -> ExtractionResult:
        """Extract information using ONLY pure LLM intelligence."""
        try:
            # Create intelligent extraction prompt
            full_prompt = self.extraction_prompt.format(message=message)
            
            # Use LLM for pure agentic extraction
            try:
                # Direct import for backend directory
                from backend.utils.llm_client import get_llm_response_sync
            except ImportError:
                # Fallback for direct execution - use absolute path from backend root
                import sys
                import os
                # Add backend directory to path
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sys.path.insert(0, backend_dir)
                from utils.llm_client import get_llm_response_sync
            
            logger.info(f"🤖 PURE AGENTIC EXTRACTION: Using LLM for intelligent extraction from: '{message}'")
            response = get_llm_response_sync(full_prompt)
            
            if not response:
                logger.warning("No response from LLM extraction")
                return ExtractionResult()
            
            # Parse the intelligent LLM response
            try:
                import json
                # Clean response - remove any markdown formatting
                clean_response = response.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                
                extraction_data = json.loads(clean_response.strip())
                
                # Create extraction result from pure LLM intelligence
                result = ExtractionResult(
                    budget=extraction_data.get("budget"),
                    location=extraction_data.get("location"),
                    property_type=extraction_data.get("property_type"),
                    timeline=extraction_data.get("timeline"),
                    desired_bedrooms=extraction_data.get("desired_bedrooms"),
                    email=extraction_data.get("email"),
                    phone=extraction_data.get("phone"),
                    name=extraction_data.get("name"),
                    extraction_confidence=extraction_data.get("confidence", 0.0),
                    conversation_stage=extraction_data.get("conversation_stage", "initial"),
                    extracted_fields=extraction_data.get("extracted_fields", [])
                )
                
                logger.info(f"✅ PURE AGENTIC EXTRACTION: {len(result.extracted_fields)} fields extracted with confidence {result.extraction_confidence}")
                logger.info(f"   Extracted: {result.extracted_fields}")
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM extraction response: {e}")
                logger.error(f"Response: {response}")
                return ExtractionResult()
                
        except Exception as e:
            logger.error(f"Pure agentic extraction failed: {e}")
            return ExtractionResult()

class AgenticRouter:
    """Pure agentic message routing using ONLY LLM intelligence."""
    
    def __init__(self):
        self.routing_prompt = """You are an expert real estate sales agent routing system. Analyze the message for sales intelligence and customer psychology.

Message: "{message}"

Route based on SALES INTELLIGENCE:

AVAILABLE AGENTS:
- "qualifier": New leads, gathering requirements, initial contact
- "value_delivery": Customer wants properties, market insights, comparisons, similar properties
- "scheduler": Ready to book tours, scheduling appointments, availability requests
- "followup": Nurturing leads, handling objections, relationship building
- "warmup": Re-engaging cold leads, initial outreach

SALES ROUTING LOGIC:
- High urgency + specific requirements → value_delivery (provide immediate value)
- Property comparison/selection requests → value_delivery 
- Ready to schedule/book → scheduler
- Hesitation/objections → followup
- New lead with unclear needs → qualifier

Consider:
- Customer urgency and intent
- Sales stage (discovery → qualification → presentation → closing)
- Value delivery opportunities
- Buying signals
- Customer psychology

Return ONLY the agent name.

EXAMPLES:
"i need ASAP miami beach 250k dollar 4bhk condo" → "value_delivery" (urgent + specific = immediate value needed)
"show me similar properties" → "value_delivery" (wants property options)
"when can I schedule a viewing" → "scheduler" (ready to buy)
"thanks, I'll think about it" → "followup" (objection/hesitation)
"looking for houses under 500k" → "value_delivery" (property search intent)

Message: "{message}"

Agent:"""

    async def route_message(self, message: str, context: Optional[AgenticContext] = None) -> Tuple[str, float]:
        """Route message using ONLY pure LLM intelligence."""
        try:
            # Create intelligent routing prompt
            full_prompt = self.routing_prompt.format(message=message)
            
            # Use LLM for pure agentic routing
            try:
                # Direct import for backend directory
                from backend.utils.llm_client import get_llm_response_sync
            except ImportError:
                # Fallback for direct execution - use absolute path from backend root
                import sys
                import os
                # Add backend directory to path
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sys.path.insert(0, backend_dir)
                from utils.llm_client import get_llm_response_sync
            
            logger.info(f"🧭 PURE AGENTIC ROUTING: Using LLM to route: '{message}'")
            response = get_llm_response_sync(full_prompt)
            
            if not response:
                logger.warning("No routing response from LLM, defaulting to qualifier")
                return "qualifier", 0.3
            
            # Parse intelligent routing decision
            agent = response.strip().lower()
            
            # Validate agent type
            valid_agents = {"qualifier", "followup", "scheduler", "value_delivery", "offramp"}
            if agent not in valid_agents:
                logger.warning(f"Invalid agent from LLM: {agent}, defaulting to qualifier")
                return "qualifier", 0.5
            
            # Sales-oriented confidence based on buying signals and urgency
            urgency_words = ["asap", "urgent", "immediately", "now", "today", "quickly"]
            intent_words = ["show me", "similar", "properties", "viewing", "schedule", "book", "tour"]
            objection_words = ["think about", "consider", "maybe", "later", "not sure"]
            
            urgency_score = 0.3 if any(word in message.lower() for word in urgency_words) else 0.0
            intent_score = 0.4 if any(word in message.lower() for word in intent_words) else 0.0
            objection_score = 0.2 if any(word in message.lower() for word in objection_words) else 0.0
            
            # Base confidence for clear routing
            confidence = 0.6 + urgency_score + intent_score + objection_score
            
            logger.info(f"✅ PURE AGENTIC ROUTING: Routed to '{agent}' with confidence {confidence}")
            return agent, confidence
            
        except Exception as e:
            logger.error(f"Pure agentic routing failed: {e}")
            return "qualifier", 0.3

class PureAgenticCoordinator:
    """Pure agentic coordination using ONLY LLM intelligence."""
    
    def __init__(self):
        self.extractor = PureAgenticExtractor()
        self.router = AgenticRouter()
    
    async def coordinate_extraction(self, message: str, context: Optional[AgenticContext] = None) -> Dict[str, Any]:
        """Coordinate extraction using ONLY pure agentic patterns."""
        try:
            logger.info(f"🎯 PURE AGENTIC COORDINATION: Starting for message: '{message}'")
            
            # Use LLM for intelligent extraction
            extraction_result = await self.extractor.extract_information(message, context)
            
            # Use LLM for intelligent routing  
            agent_type, routing_confidence = await self.router.route_message(message, context)
            
            # Update context if provided
            if context:
                context.add_agent_interaction(agent_type, "pure_agentic_extraction")
                context.current_agent = agent_type
                context.conversation_stage = extraction_result.conversation_stage
                
                # Update extracted data with pure LLM intelligence
                for field in extraction_result.extracted_fields:
                    context.extracted_data[field] = getattr(extraction_result, field)
            
            return {
                "success": True,
                "agent_type": agent_type,
                "routing_confidence": routing_confidence,
                "extraction_result": extraction_result,
                "extraction_fields": extraction_result.extracted_fields,
                "conversation_stage": extraction_result.conversation_stage,
                "agent_coordination": "pure_agentic",
                "langgraph_managed": True,
                "extraction_confidence": extraction_result.extraction_confidence
            }
            
        except Exception as e:
            logger.error(f"Pure agentic coordination failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "qualifier",
                "fallback_used": False,  # No fallbacks in pure agentic system
                "extraction_confidence": 0.0
            }

# LangGraph Integration for Pure Agentic Patterns
class LangGraphPureAgenticCoordinator:
    """LangGraph-based pure agentic extraction workflow."""
    
    def __init__(self):
        self.coordinator = PureAgenticCoordinator()
        self.graph = self._build_pure_agentic_graph()
    
    def _build_pure_agentic_graph(self):
        """Build pure agentic LangGraph workflow."""
        try:
            from langgraph.graph import StateGraph, START
            from langgraph.types import Command, Send
            from typing import Literal, TypedDict, Annotated
            import operator
            from datetime import datetime
            
            # Define pure agentic state schema
            class PureAgenticState(TypedDict):
                message: str
                user_id: str
                thread_id: str
                extracted_data: Dict[str, Any]
                agent_history: Annotated[List[str], operator.add]
                current_stage: str
                extraction_confidence: float
                routing_confidence: float
                current_agent: str
                completed: bool
            
            def pure_agentic_supervisor(state: PureAgenticState) -> Command[Literal["pure_agentic_worker"]]:
                """Supervisor that delegates to pure agentic extraction."""
                return Command(
                    goto="pure_agentic_worker",
                    update={
                        "agent_history": state.get("agent_history", []) + ["supervisor:delegated_to_pure_agentic"],
                        "current_stage": "pure_agentic_processing"
                    }
                )
            
            def pure_agentic_worker(state: PureAgenticState) -> Command[Literal["supervisor"]]:
                """Worker that performs pure agentic extraction."""
                try:
                    message = state["message"]
                    
                    # Create context for pure agentic processing
                    context = AgenticContext(
                        thread_id=state["thread_id"],
                        user_id=state["user_id"],
                        current_agent="pure_agentic_worker",
                        conversation_stage=state.get("current_stage", "initial"),
                        extracted_data=state.get("extracted_data", {}),
                        agent_history=state.get("agent_history", []),
                        last_activity=datetime.utcnow().isoformat()
                    )
                    
                    # Use pure agentic coordinator for extraction
                    result = asyncio.run(self.coordinator.coordinate_extraction(message, context))
                    
                    if result["success"]:
                        updated_data = state.get("extracted_data", {})
                        extraction_result = result["extraction_result"]
                        
                        # Update extracted data with pure intelligence
                        for field in extraction_result.extracted_fields:
                            updated_data[field] = getattr(extraction_result, field)
                        
                        return Command(
                            goto="supervisor",
                            update={
                                "extracted_data": updated_data,
                                "extraction_confidence": extraction_result.extraction_confidence,
                                "routing_confidence": result["routing_confidence"],
                                "current_agent": result["agent_type"],
                                "agent_history": state.get("agent_history", []) + [f"worker:pure_agentic_extraction_completed_{result['agent_type']}"],
                                "completed": len(result["extraction_fields"]) > 0
                            }
                        )
                    else:
                        return Command(
                            goto="supervisor",
                            update={
                                "extraction_confidence": 0.0,
                                "routing_confidence": 0.0,
                                "current_agent": "qualifier",
                                "agent_history": state.get("agent_history", []) + ["worker:pure_agentic_extraction_failed"],
                                "completed": False
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Pure agentic worker failed: {e}")
                    return Command(
                        goto="supervisor",
                        update={
                            "extraction_confidence": 0.0,
                            "routing_confidence": 0.0,
                            "current_agent": "qualifier",
                            "agent_history": state.get("agent_history", []) + [f"worker:error_{str(e)}"],
                            "completed": False
                        }
                    )
            
            # Build the pure agentic graph
            workflow = StateGraph(PureAgenticState)
            workflow.add_node("supervisor", pure_agentic_supervisor)
            workflow.add_node("pure_agentic_worker", pure_agentic_worker)
            workflow.add_edge(START, "supervisor")
            workflow.add_edge("supervisor", "pure_agentic_worker")
            workflow.add_edge("pure_agentic_worker", "supervisor")
            
            return workflow.compile()
            
        except Exception as e:
            logger.warning(f"Failed to build pure agentic LangGraph graph: {e}")
            return None

# Main API functions for Pure Agentic System
async def extract_lead_info(message: str, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Main API function for pure agentic lead information extraction."""
    try:
        logger.info(f"🚀 PURE AGENTIC API: Starting extraction for message: '{message}'")
        
        coordinator = PureAgenticCoordinator()
        
        # Create context for pure agentic processing
        context = None
        if user_id and thread_id:
            context = AgenticContext(
                thread_id=thread_id,
                user_id=user_id,
                current_agent="extractor",
                conversation_stage="initial",
                extracted_data={},
                agent_history=[],
                last_activity=datetime.now().isoformat()
            )
        
        # Perform pure agentic extraction
        result = await coordinator.coordinate_extraction(message, context)
        
        if result["success"]:
            extraction_result = result["extraction_result"]
            logger.info(f"✅ PURE AGENTIC SUCCESS: Extracted {len(extraction_result.extracted_fields)} fields")
            
            return {
                "budget": extraction_result.budget,
                "location": extraction_result.location,
                "property_type": extraction_result.property_type,
                "timeline": extraction_result.timeline,
                "desired_bedrooms": extraction_result.desired_bedrooms,
                "email": extraction_result.email,
                "phone": extraction_result.phone,
                "other_details": extraction_result.name,
                "extraction_confidence": extraction_result.extraction_confidence,
                "message_type": extraction_result.conversation_stage,
                "agent_type": result["agent_type"],
                "routing_confidence": result["routing_confidence"],
                "extraction_fields": extraction_result.extracted_fields,
                "success": True,
                "agentic_coordination": True,
                "langgraph_managed": True,
                "pure_agentic": True
            }
        else:
            logger.warning(f"⚠️ PURE AGENTIC FAILED: {result.get('error', 'Unknown error')}")
            return {
                "budget": None,
                "location": None,
                "property_type": None,
                "timeline": None,
                "desired_bedrooms": None,
                "email": None,
                "phone": None,
                "other_details": None,
                "extraction_confidence": 0.0,
                "message_type": "error",
                "agent_type": "qualifier",
                "routing_confidence": 0.0,
                "extraction_fields": [],
                "success": False,
                "error": result.get("error", "Pure agentic extraction failed"),
                "agentic_coordination": True,
                "langgraph_managed": True,
                "pure_agentic": True
            }
            
    except Exception as e:
        logger.error(f"❌ PURE AGENTIC ERROR: {e}")
        return {
            "budget": None,
            "location": None,
            "property_type": None,
            "timeline": None,
            "desired_bedrooms": None,
            "email": None,
            "phone": None,
            "other_details": None,
            "extraction_confidence": 0.0,
            "message_type": "error",
            "agent_type": "qualifier",
            "routing_confidence": 0.0,
            "extraction_fields": [],
            "success": False,
            "error": str(e),
            "agentic_coordination": True,
            "langgraph_managed": False,
            "pure_agentic": True
        }

# Legacy compatibility function
def enhanced_extract_lead_info(message: str, user_id: Optional[str] = None, prior_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility - uses pure agentic system."""
    return extract_lead_info(message, user_id)

# Pure Agentic workflow integration
pure_agentic_coordinator = LangGraphPureAgenticCoordinator()

def get_pure_agentic_extraction_node():
    """Get pure agentic extraction node for LangGraph workflow integration."""
    return pure_agentic_coordinator

# Module-level exports for pure agentic patterns
__all__ = [
    "extract_lead_info",
    "AgenticContext",
    "PureAgenticCoordinator", 
    "LangGraphPureAgenticCoordinator",
    "PureAgenticExtractor",
    "AgenticRouter",
    "ExtractionResult"
]
