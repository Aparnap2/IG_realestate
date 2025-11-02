"""
LangGraph-Based Lead Information Extraction

This module provides real estate lead information extraction using pure agentic AI patterns
with LangGraph state management and Redis checkpointing. No hardcoded ML dependencies.

Key Features:
- Rule-based information extraction (budget, location, property type, timeline)
- LangGraph state management for agent coordination
- Redis checkpoint persistence
- Agentic AI patterns: routing, parallelization, checkpoint management
- Proactive engagement with rule-based patterns
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Simple message types for agent routing."""
    INITIAL = "initial"
    QUALIFICATION = "qualification"
    SCHEDULING = "scheduling"
    FOLLOWUP = "followup"

@dataclass
class ExtractionResult:
    """Result of real estate lead information extraction."""
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
    """LangGraph-managed context for agent coordination."""
    thread_id: str
    user_id: str
    current_agent: str
    conversation_stage: str
    extracted_data: Dict[str, Any]
    agent_history: List[str]
    last_activity: str
    
    def add_agent_interaction(self, agent_type: str, action: str):
        """Record agent interaction in LangGraph-managed history."""
        self.agent_history.append(f"{agent_type}:{action}")

class LangGraphMessageRouter:
    """Pure LangGraph-based message routing without ML classification."""
    
    def __init__(self):
        self.routing_rules = {
            "booking": ["book", "schedule", "tour", "viewing", "appointment"],
            "budget": ["budget", "$", "price", "cost", "afford", "payment"],
            "urgent": ["asap", "urgent", "immediately", "today", "emergency"],
            "info": ["info", "details", "more", "tell me", "show"],
            "qualification": ["looking", "need", "want", "search", "find"]
        }
    
    def route_message(self, message: str, context: Optional[AgenticContext] = None) -> Tuple[str, float]:
        """Route message to appropriate agent using simple rule-based patterns."""
        message_lower = message.lower()
        
        # Check routing patterns
        for agent_type, keywords in self.routing_rules.items():
            match_score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    match_score += 1
            
            if match_score > 0:
                confidence = min(match_score / len(keywords), 1.0)
                return agent_type, confidence
        
        # Default fallback
        return "qualifier", 0.3

class RuleBasedExtractor:
    """Simple rule-based extraction without ML patterns."""
    
    def extract_information(self, message: str, context: Optional[AgenticContext] = None) -> ExtractionResult:
        """Extract lead information using regex patterns and simple rules."""
        result = ExtractionResult()
        
        # Extract budget
        budget = self._extract_budget(message)
        if budget:
            result.budget = budget
            result.extracted_fields.append("budget")
        
        # Extract location
        location = self._extract_location(message)
        if location:
            result.location = location
            result.extracted_fields.append("location")
        
        # Extract property type and bedrooms
        property_type, bedrooms = self._extract_property_info(message)
        if property_type:
            result.property_type = property_type
            result.extracted_fields.append("property_type")
        if bedrooms:
            result.desired_bedrooms = bedrooms
            result.extracted_fields.append("bedrooms")
        
        # Extract timeline
        timeline = self._extract_timeline(message)
        if timeline:
            result.timeline = timeline
            result.extracted_fields.append("timeline")
        
        # Extract contact info
        email = self._extract_email(message)
        if email:
            result.email = email
            result.extracted_fields.append("email")
            
        phone = self._extract_phone(message)
        if phone:
            result.phone = phone
            result.extracted_fields.append("phone")
        
        # Set confidence based on extracted fields
        result.extraction_confidence = min(len(result.extracted_fields) * 0.25, 1.0)
        
        # Determine conversation stage
        result.conversation_stage = self._determine_conversation_stage(result)
        
        logger.info(f"Rule-based extraction: {len(result.extracted_fields)} fields extracted")
        return result

    def _extract_budget(self, message: str) -> Optional[float]:
        """Extract budget using simple regex patterns."""
        message_lower = message.lower()
        
        budget_patterns = [
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:k|K|thousand)', 1000),
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:m|M|million)', 1000000),
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)', 1),
            (r'budget[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*)', 1),
        ]
        
        for pattern, multiplier in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    number_str = match.group(1).replace(',', '').replace('$', '').strip()
                    if number_str.isdigit():
                        budget = int(number_str) * multiplier
                        if 10000 <= budget <= 100000000:  # Reasonable range
                            return budget
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_location(self, message: str) -> Optional[str]:
        """Extract location using pattern matching."""
        message_lower = message.lower()
        
        location_patterns = [
            r'(?:near|in|around|at)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'located\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'([a-zA-Z\s]{3,25})\s+(?:area|region|city|state)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip().title()
                if (len(location) >= 3 and
                    location.lower() not in ['the', 'house', 'budget', 'property'] and
                    not re.match(r'^\d+$', location)):
                    return location
        return None
    
    def _extract_property_info(self, message: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract property type and bedrooms."""
        message_lower = message.lower()
        
        bedroom_patterns = [
            r'(\d+)\s*(?:bhk|bed|beds|bedroom|bedrooms)',
            r'(\d+)\s*(?:bed|bhk|br)\s*(?:apartment|condo|house)',
        ]
        
        bedrooms = None
        property_type = None
        
        for pattern in bedroom_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    bedrooms = int(match.group(1))
                    if 1 <= bedrooms <= 10:
                        property_type = f"{bedrooms}BHK"
                        break
                except ValueError:
                    continue
        
        if not property_type:
            property_patterns = [
                (r'(?:condo|condominium)', 'Condominium'),
                (r'(?:house|home)', 'House'),
                (r'(?:apartment|apt|flat)', 'Apartment'),
                (r'(?:studio)', 'Studio'),
            ]
            
            for pattern, prop_type in property_patterns:
                if re.search(pattern, message_lower):
                    property_type = prop_type
                    break
        
        return property_type, bedrooms
    
    def _extract_timeline(self, message: str) -> Optional[str]:
        """Extract purchase timeline."""
        message_lower = message.lower()
        
        timeline_patterns = [
            (r'(?:asap|immediately|right now|urgent)', 'immediately'),
            (r'(?:this month|next month|within\s+\d+\s*months?)', '1-3 months'),
            (r'(?:this year|by\s+end\s+of\s+year)', '6-12 months'),
            (r'(?:flexible|no rush|whenever)', 'flexible'),
        ]
        
        for pattern, timeline in timeline_patterns:
            if re.search(pattern, message_lower):
                return timeline
        return None
    
    def _extract_email(self, message: str) -> Optional[str]:
        """Extract email address."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        return email_match.group(1) if email_match else None
    
    def _extract_phone(self, message: str) -> Optional[str]:
        """Extract phone number."""
        phone_patterns = [
            r'(\d{3}[-.]?\d{3}[-.]?\d{4})',
            r'(\(\d{3}\)\s*\d{3}[-.]?\d{4})',
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, message)
            if phone_match:
                return phone_match.group(1)
        return None
    
    def _determine_conversation_stage(self, result: ExtractionResult) -> str:
        """Determine conversation stage based on extracted information."""
        extracted_count = len(result.extracted_fields)
        
        if extracted_count >= 3:
            return "qualified"
        elif extracted_count >= 1:
            return "qualification"
        else:
            return "initial"

class AgenticExtractionCoordinator:
    """LangGraph-based agent coordination for extraction workflows."""
    
    def __init__(self):
        self.router = LangGraphMessageRouter()
        self.extractor = RuleBasedExtractor()
        self.agent_mapping = {
            "booking": "scheduler",
            "budget": "qualifier",
            "urgent": "qualifier",
            "info": "qualifier",
            "qualification": "qualifier",
            "default": "qualifier"
        }
    
    async def coordinate_extraction(self, message: str, context: Optional[AgenticContext] = None) -> Dict[str, Any]:
        """Coordinate extraction using LangGraph agentic patterns."""
        try:
            # Route message to appropriate agent
            agent_type, confidence = self.router.route_message(message, context)
            mapped_agent = self.agent_mapping.get(agent_type, "qualifier")
            
            # Extract information using rule-based patterns
            extraction_result = self.extractor.extract_information(message, context)
            
            # Update context if provided
            if context:
                context.add_agent_interaction(mapped_agent, "extraction")
                context.current_agent = mapped_agent
                context.conversation_stage = extraction_result.conversation_stage
                
                # Update extracted data
                for field in extraction_result.extracted_fields:
                    context.extracted_data[field] = getattr(extraction_result, field)
            
            return {
                "success": True,
                "agent_type": mapped_agent,
                "routing_confidence": confidence,
                "extraction_result": extraction_result,
                "extraction_fields": extraction_result.extracted_fields,
                "conversation_stage": extraction_result.conversation_stage,
                "agent_coordination": "langgraph_managed"
            }
            
        except Exception as e:
            logger.error(f"Agentic extraction coordination failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "qualifier",
                "fallback_used": True
            }
    
    def _extract_budget(self, message: str) -> Optional[float]:
        """Extract budget with comprehensive K/M handling."""
        message_lower = message.lower()
        
        # Comprehensive budget patterns for production scenarios
        budget_patterns = [
            # Patterns with K/M scaling
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:k|K|thousand)\s*(?:dollars?|usd)?', 1000),
            (r'(\d{1,3}(?:,\d{3})*)\s*(?:k|K|thousand)\s*(?:dollars?|usd)?', 1000),
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:m|M|million)\s*(?:dollars?|usd)?', 1000000),
            (r'(\d{1,3}(?:,\d{3})*)\s*(?:m|M|million)\s*(?:dollars?|usd)?', 1000000),
            
            # Exact dollar amounts
            (r'\$?\s*(\d{1,3}(?:,\d{3})*)\s*(?:dollars?|usd)', 1),
            (r'budget[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*)', 1),
            (r'looking.*?(\$[0-9,]+)', 1),
            
            # Context-aware amounts (budget mentioned in sentence)
            (r'budget.*?(\d{1,3}(?:,\d{3})*)', 1),
            (r'(\d{1,3}(?:,\d{3})*)\s*dollars?', 1),
            
            # Standalone numbers that could be budgets (when other context suggests it)
            (r'\b(\d{2,3}(?:,\d{3})*)\b(?=.*\s*(?:budget|dollars?|price|cost|money|usd|\$))', 1),
        ]
        
        for pattern, multiplier in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    # Extract and clean the number
                    number_str = match.group(1).replace(',', '').replace('$', '').strip()
                    if number_str.isdigit():
                        budget = int(number_str) * multiplier
                        # Validate reasonable budget range
                        if 10000 <= budget <= 100000000:  # $10k to $100M range
                            logger.info(f"Budget extracted: {budget} from pattern '{pattern}'")
                            return budget
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_location(self, message: str) -> Optional[str]:
        """Extract location with smart preposition handling."""
        message_lower = message.lower()
        
        # Common US states and major cities for real estate
        known_locations = [
            'california', 'florida', 'texas', 'new york', 'illinois', 'pennsylvania',
            'ohio', 'georgia', 'north carolina', 'michigan', 'new jersey', 'virginia',
            'washington', 'arizona', 'massachusetts', 'tennessee', 'indiana', 'maryland',
            'missouri', 'wisconsin', 'colorado', 'minnesota', 'south carolina', 'alabama',
            'louisiana', 'kentucky', 'oregon', 'oklahoma', 'connecticut', 'utah',
            'miami', 'orlando', 'tampa', 'jacksonville', 'los angeles', 'san francisco',
            'san diego', 'sacramento', 'oakland', 'fresno', 'bakersfield', 'riverside',
            'new york city', 'manhattan', 'brooklyn', 'queens', 'bronx', 'staten island',
            'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio', 'san diego',
            'dallas', 'san jose', 'austin', 'jacksonville', 'fort worth', 'columbus'
        ]
        
        # Check for direct location mentions first
        for location in known_locations:
            if location in message_lower:
                return location.title()
        
        # Patterns with prepositions
        location_patterns = [
            r'(?:near|in|around|at|to)\s+([a-zA-Z\s]+?)(?:\s+(?:california|florida|texas|new\s+york|miami|orlando|tampa|london|canada|australia))?(?:\s|$|,)',
            r'(?:located|live|living)\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'([a-zA-Z\s]{3,25})\s+(?:area|region|county|city|state)',
            r'(?:looking|searching)\s+(?:in|near|around)\s+([a-zA-Z\s]+?)(?:\s|$|,)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip().title()
                # Filter out common non-location words
                location = re.sub(r'^(?:the|a|an|any|house|budget|property|option|about|for)\s+', '', location)
                location = location.strip()
                
                # Validate location
                if (len(location) >= 3 and 
                    location.lower() not in ['the', 'house', 'budget', 'property', 'option', 'area', 'region', 'location'] and
                    not re.match(r'^\d+$', location)):
                    logger.info(f"Location extracted: '{location}' from pattern")
                    return location
        
        return None
    
    def _extract_property_info(self, message: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract property type and bedrooms with comprehensive mapping."""
        message_lower = message.lower()
        
        # Bedroom patterns first (more specific)
        bedroom_patterns = [
            r'(\d+)\s*(?:bhk|bed|beds|bedroom|bedrooms)',
            r'(\d+)\s*(?:bed|bhk|br)\s*(?:apartment|condo|house|home)',
            r'(?:need|looking for|want)\s+(\d+)\s*(?:bed|beds|bedroom|bedrooms)',
        ]
        
        bedrooms = None
        property_type = None
        
        for pattern in bedroom_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    bedrooms = int(match.group(1))
                    if 1 <= bedrooms <= 10:  # Reasonable bedroom range
                        property_type = f"{bedrooms}BHK"
                        logger.info(f"Bedrooms extracted: {bedrooms}, Property type: {property_type}")
                        break
                except ValueError:
                    continue
        
        # Property type patterns if bedrooms not found
        if not property_type:
            property_patterns = [
                # Condo patterns
                (r'(?:condo|condominium)', 'Condominium'),
                # House patterns
                (r'(?:house|home|single family|residence)', 'House'),
                # Apartment patterns
                (r'(?:apartment|apt|flat)', 'Apartment'),
                # Townhouse patterns
                (r'(?:townhouse|town home|row house)', 'Townhouse'),
                # Villa patterns
                (r'(?:villa|luxury home|luxury)', 'Villa'),
                # Studio patterns
                (r'(?:studio|efficiency|loft)', 'Studio'),
                # Duplex patterns
                (r'(?:duplex|two family|multi family)', 'Duplex'),
            ]
            
            for pattern, prop_type in property_patterns:
                if re.search(pattern, message_lower):
                    property_type = prop_type
                    logger.info(f"Property type extracted: {property_type}")
                    break
        
        return property_type, bedrooms
    
    def _extract_timeline(self, message: str) -> Optional[str]:
        """Extract purchase timeline."""
        message_lower = message.lower()
        
        timeline_patterns = [
            (r'(?:asap|immediately|right now|urgent)', 'immediately'),
            (r'(?:this month|next month|within\s+\d+\s*months?)', '1-3 months'),
            (r'(?:within\s+\d+\s*months?)', '1-6 months'),
            (r'(?:this year|by\s+end\s+of\s+year)', '6-12 months'),
            (r'(?:next year|within\s+\d+\s*years?)', '1-2 years'),
            (r'(?:flexible|no rush|whenever)', 'flexible'),
        ]
        
        for pattern, timeline in timeline_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"Timeline extracted: {timeline}")
                return timeline
        
        return None
    
    def _extract_email(self, message: str) -> Optional[str]:
        """Extract email address."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            return email_match.group(1)
        return None
    
    def _extract_phone(self, message: str) -> Optional[str]:
        """Extract phone number."""
        phone_patterns = [
            r'(\d{3}[-.]?\d{3}[-.]?\d{4})',
            r'(\(\d{3}\)\s*\d{3}[-.]?\d{4})',
            r'(\+\d{1,3}[-.]?\d{10,})',
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, message)
            if phone_match:
                return phone_match.group(1)
        return None

class LangGraphExtractionCoordinator:
    """LangGraph-based extraction workflow with proper agentic patterns."""
    
    def __init__(self):
        self.coordinator = AgenticExtractionCoordinator()
        self.graph = self._build_extraction_graph()
    
    def _build_extraction_graph(self):
        """Build LangGraph extraction workflow using proper patterns."""
        try:
            from langgraph.graph import StateGraph, START
            from langgraph.types import Command, Send
            from typing import Literal, TypedDict, Annotated
            import operator
            from datetime import datetime
            
            # Define extraction state schema
            class ExtractionState(TypedDict):
                message: str
                user_id: str
                thread_id: str
                extracted_data: Dict[str, Any]
                agent_history: Annotated[List[str], operator.add]
                current_stage: str
                extraction_confidence: float
                completed: bool
            
            def extraction_supervisor(state: ExtractionState) -> Command[Literal["extraction_worker", "end"]]:
                """Supervisor that determines extraction workflow."""
                message = state["message"]
                current_stage = state.get("current_stage", "initial")
                
                # Simple rule-based routing without ML
                if any(word in message.lower() for word in ["book", "schedule", "tour"]):
                    return Command(
                        goto="extraction_worker",
                        update={
                            "current_stage": "scheduling",
                            "agent_history": state.get("agent_history", []) + ["supervisor:routed_to_scheduling"]
                        }
                    )
                elif any(word in message.lower() for word in ["budget", "$", "price", "cost"]):
                    return Command(
                        goto="extraction_worker",
                        update={
                            "current_stage": "qualification",
                            "agent_history": state.get("agent_history", []) + ["supervisor:routed_to_qualification"]
                        }
                    )
                else:
                    return Command(
                        goto="extraction_worker",
                        update={
                            "current_stage": "initial",
                            "agent_history": state.get("agent_history", []) + ["supervisor:routed_to_initial"]
                        }
                    )
            
            def extraction_worker(state: ExtractionState) -> Command[Literal["supervisor"]]:
                """Worker that performs rule-based extraction."""
                try:
                    message = state["message"]
                    context = AgenticContext(
                        thread_id=state["thread_id"],
                        user_id=state["user_id"],
                        current_agent="extraction_worker",
                        conversation_stage=state.get("current_stage", "initial"),
                        extracted_data=state.get("extracted_data", {}),
                        agent_history=state.get("agent_history", []),
                        last_activity=datetime.utcnow().isoformat()
                    )
                    
                    # Use agentic coordinator for extraction
                    result = asyncio.run(self.coordinator.coordinate_extraction(message, context))
                    
                    if result["success"]:
                        updated_data = state.get("extracted_data", {})
                        for field in result["extraction_fields"]:
                            if hasattr(result["extraction_result"], field):
                                updated_data[field] = getattr(result["extraction_result"], field)
                        
                        return Command(
                            goto="supervisor",
                            update={
                                "extracted_data": updated_data,
                                "extraction_confidence": result["extraction_result"].extraction_confidence,
                                "agent_history": state.get("agent_history", []) + [f"worker:extraction_completed_{result['agent_type']}"],
                                "completed": len(result["extraction_fields"]) > 0
                            }
                        )
                    else:
                        return Command(
                            goto="supervisor",
                            update={
                                "extraction_confidence": 0.0,
                                "agent_history": state.get("agent_history", []) + ["worker:extraction_failed"],
                                "completed": False
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Extraction worker failed: {e}")
                    return Command(
                        goto="supervisor",
                        update={
                            "extraction_confidence": 0.0,
                            "agent_history": state.get("agent_history", []) + [f"worker:error_{str(e)}"],
                            "completed": False
                        }
                    )
            
            # Build the graph
            workflow = StateGraph(ExtractionState)
            workflow.add_node("supervisor", extraction_supervisor)
            workflow.add_node("extraction_worker", extraction_worker)
            workflow.add_edge(START, "supervisor")
            
            return workflow.compile()
            
        except Exception as e:
            logger.warning(f"Failed to build LangGraph extraction graph: {e}")
            return None

# Main API functions
def extract_lead_info(message: str, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Main API function for pure agentic lead information extraction."""
    try:
        coordinator = AgenticExtractionCoordinator()
        
        # Create context for extraction
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
        
        # Perform extraction using agentic patterns
        result = asyncio.run(coordinator.coordinate_extraction(message, context))
        
        if result["success"]:
            extraction_result = result["extraction_result"]
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
                "langgraph_managed": True
            }
        else:
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
                "error": result.get("error", "Unknown extraction error"),
                "agentic_coordination": True,
                "langgraph_managed": True
            }
            
    except Exception as e:
        logger.error(f"Error in agentic lead extraction: {e}")
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
            "langgraph_managed": False
        }

# Legacy compatibility function
def enhanced_extract_lead_info(message: str, user_id: Optional[str] = None, prior_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    return extract_lead_info(message, user_id)

# LangGraph workflow integration
extraction_coordinator = LangGraphExtractionCoordinator()

def get_langgraph_extraction_node():
    """Get LangGraph extraction node for workflow integration."""
    return extraction_coordinator

# Module-level exports for agentic patterns
__all__ = [
    "extract_lead_info",
    "AgenticContext",
    "AgenticExtractionCoordinator",
    "LangGraphExtractionCoordinator",
    "LangGraphMessageRouter",
    "RuleBasedExtractor",
    "ExtractionResult"
]
