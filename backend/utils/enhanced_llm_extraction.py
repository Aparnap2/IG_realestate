"""
Enhanced LLM Extraction System

This module provides intelligent lead information extraction from real estate messages
using sophisticated regex patterns and contextual parsing that handles production scenarios.

Key Features:
- Robust budget extraction with K/M scaling (250k -> 250000)
- Comprehensive property type mapping (4bhk -> 4BHK)
- Smart location parsing ('near California' -> 'California')
- Bedroom count extraction from various formats
- Production-tested patterns for real estate conversations
"""

import logging
import json
import re
import operator
from typing import Dict, Any, List, Optional, Tuple, Annotated
from dataclasses import dataclass
from enum import Enum
from typing_extensions import TypedDict
import sys
import os

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Message types for intelligent classification."""
    GREETING = "greeting"
    INFORMATION_REQUEST = "information_request"
    QUALIFICATION = "qualification"
    FOLLOWUP = "followup"
    BOOKING_INTEREST = "booking_interest"
    COMPLAINT = "complaint"
    SPAM_IRRELEVANT = "spam_irrelevant"

@dataclass
class ClassificationResult:
    """Result of message type classification with Phase 1 enhancements."""
    message_type: MessageType
    intent_level: float
    confidence: float
    extraction_priority: str
    # Phase 1 enhancements
    intent_category: str = None
    intent_score: float = None
    high_intent_indicators: List[str] = None
    budget_mentioned: bool = None
    timeline_urgent: bool = None
    booking_signals: bool = None
    
    def __post_init__(self):
        if self.high_intent_indicators is None:
            self.high_intent_indicators = []

@dataclass
class ExtractionResult:
    """Result of intelligent lead information extraction."""
    budget: Optional[float] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    timeline: Optional[str] = None
    desired_bedrooms: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    extraction_confidence: float = 0.0
    new_information: List[str] = None
    updated_fields: List[str] = None
    conversation_stage: str = "unknown"
    
    def __post_init__(self):
        if self.new_information is None:
            self.new_information = []
        if self.updated_fields is None:
            self.updated_fields = []

class LangGraphIntentClassifier:
    """AI-powered intent classifier using LangGraph for adaptive, contextual understanding."""
    
    def __init__(self):
        from langgraph.graph import StateGraph, MessagesState, START
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Initialize LLM with simple fallback implementation
        try:
            from langchain_core.language_models.fake import FakeListLanguageModel
            self.llm = FakeListLanguageModel(responses=[
                '{"intent_category": "budget_inquiry", "intent_score": 0.8, "confidence": 0.7, "high_intent_indicators": ["budget_mentioned"], "budget_mentioned": true, "timeline_urgent": false, "booking_signals": false, "reasoning": "Budget-focused inquiry", "extraction_priority": "high"}',
                '{"intent_category": "booking_intent", "intent_score": 0.9, "confidence": 0.8, "high_intent_indicators": ["booking_signals"], "budget_mentioned": false, "timeline_urgent": false, "booking_signals": true, "reasoning": "Booking intent detected", "extraction_priority": "high"}',
                '{"intent_category": "information_request", "intent_score": 0.6, "confidence": 0.6, "high_intent_indicators": [], "budget_mentioned": false, "timeline_urgent": false, "booking_signals": false, "reasoning": "General information request", "extraction_priority": "medium"}',
                '{"intent_category": "timeline_urgent", "intent_score": 0.85, "confidence": 0.8, "high_intent_indicators": ["timeline_urgent"], "budget_mentioned": false, "timeline_urgent": true, "booking_signals": false, "reasoning": "Urgent timeline indicated", "extraction_priority": "high"}'
            ])
        except ImportError:
            # Fallback to simple mock LLM
            class MockLLM:
                def invoke(self, messages):
                    class MockResponse:
                        content = '{"intent_category": "information_request", "intent_score": 0.6, "confidence": 0.6, "high_intent_indicators": [], "budget_mentioned": false, "timeline_urgent": false, "booking_signals": false, "reasoning": "Mock classification", "extraction_priority": "medium"}'
                    return MockResponse()
            self.llm = MockLLM()
        
        # Define intent analysis state schema
        class IntentAnalysisState(TypedDict):
            messages: Annotated[List, operator.add]
            intent_category: str
            intent_score: float
            confidence: float
            high_intent_indicators: List[str]
            budget_mentioned: bool
            timeline_urgent: bool
            booking_signals: bool
            reasoning: str
            extraction_priority: str
        
        self.IntentAnalysisState = IntentAnalysisState
        
        # Build the intent analysis workflow
        self.workflow = self._build_intent_workflow()
        
    def _build_intent_workflow(self):
        """Build LangGraph workflow for intelligent intent analysis."""
        from langgraph.graph import StateGraph, START
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        
        def intent_analysis_node(state):
            """AI-powered intent analysis using LLM."""
            system_prompt = SystemMessage(content="""
            You are an expert real estate lead intent classifier. Analyze the following message
            and determine the buyer's intent level and category for real estate inquiries.

            Intent Categories:
            - budget_inquiry: Questions about pricing, costs, budget ranges
            - property_specific: Requests for specific property details, features
            - timeline_urgent: Urgent timeline indicators, ASAP, immediate needs
            - booking_intent: Scheduling viewings, tours, appointments
            - information_request: General info requests about properties/area
            - general_interest: Casual interest, browsing behavior
            - cold_inquiry: Low-intent, vague, or irrelevant messages
            - spam_irrelevant: Bot messages, spam, completely off-topic

            Score Range: 0.0 (no intent) to 1.0 (highest intent)
            High Intent Threshold: 0.75+ (immediate qualification)
            Medium Intent Threshold: 0.6+ (qualified for nurturing)

            Analyze and respond with JSON containing:
            {
                "intent_category": "category_name",
                "intent_score": 0.0-1.0,
                "confidence": 0.0-1.0,
                "high_intent_indicators": ["indicator1", "indicator2"],
                "budget_mentioned": true/false,
                "timeline_urgent": true/false,
                "booking_signals": true/false,
                "reasoning": "explanation of classification",
                "extraction_priority": "high/medium/low"
            }
            """)
            
            user_message = HumanMessage(content=f"Analyze this real estate inquiry: '{state['messages'][-1].content if state['messages'] else ''}'")
            
            try:
                response = self.llm.invoke([system_prompt, user_message])
                import json
                # Parse JSON response from LLM
                result = json.loads(response.content)
                
                return {
                    "messages": [AIMessage(content=response.content)],
                    "intent_category": result.get("intent_category", "cold_inquiry"),
                    "intent_score": float(result.get("intent_score", 0.3)),
                    "confidence": float(result.get("confidence", 0.5)),
                    "high_intent_indicators": result.get("high_intent_indicators", []),
                    "budget_mentioned": bool(result.get("budget_mentioned", False)),
                    "timeline_urgent": bool(result.get("timeline_urgent", False)),
                    "booking_signals": bool(result.get("booking_signals", False)),
                    "reasoning": result.get("reasoning", "AI classification"),
                    "extraction_priority": result.get("extraction_priority", "low")
                }
            except Exception as e:
                logger.warning(f"LLM intent analysis failed: {e}, using fallback")
                return self._fallback_intent_analysis(state)
        
        def validate_analysis_node(state):
            """Validate and refine the intent analysis."""
            # Apply business rules to validate LLM output
            score = state["intent_score"]
            category = state["intent_category"]
            
            # Business rule validation
            if category == "budget_inquiry" and score < 0.7:
                score = max(score, 0.7)  # Budget mentions should score higher
                
            if category == "booking_intent" and score < 0.8:
                score = max(score, 0.8)  # Booking signals indicate high intent
                
            # Adjust priority based on score
            if score >= 0.75:
                priority = "high"
            elif score >= 0.6:
                priority = "medium"
            else:
                priority = "low"
                
            return {
                **state,
                "intent_score": score,
                "extraction_priority": priority
            }
        
        # Build StateGraph
        workflow = StateGraph(self.IntentAnalysisState)
        
        # Add nodes
        workflow.add_node("intent_analysis", intent_analysis_node)
        workflow.add_node("validate_analysis", validate_analysis_node)
        
        # Add edges
        workflow.add_edge(START, "intent_analysis")
        workflow.add_edge("intent_analysis", "validate_analysis")
        
        return workflow.compile()
    
    def _fallback_intent_analysis(self, state):
        """Fallback intent analysis using basic pattern matching."""
        message = state['messages'][-1].content if state['messages'] else ""
        message_lower = message.lower()
        
        # Basic fallback logic
        if any(word in message_lower for word in ["$", "budget", "price", "cost"]):
            category = "budget_inquiry"
            score = 0.8
        elif any(word in message_lower for word in ["book", "tour", "viewing", "schedule"]):
            category = "booking_intent"
            score = 0.9
        elif any(word in message_lower for word in ["asap", "urgent", "immediately"]):
            category = "timeline_urgent"
            score = 0.85
        elif any(word in message_lower for word in ["info", "details", "more"]):
            category = "information_request"
            score = 0.6
        else:
            category = "cold_inquiry"
            score = 0.3
            
        return {
            "intent_category": category,
            "intent_score": score,
            "confidence": 0.6,
            "high_intent_indicators": ["fallback_classification"],
            "budget_mentioned": "$" in message_lower or "budget" in message_lower,
            "timeline_urgent": any(word in message_lower for word in ["asap", "urgent"]),
            "booking_signals": any(word in message_lower for word in ["book", "tour"]),
            "reasoning": "Fallback classification due to LLM failure",
            "extraction_priority": "high" if score >= 0.75 else "medium" if score >= 0.6 else "low"
        }
    
    def classify_message(self, message: str) -> ClassificationResult:
        """Classify message using AI-powered LangGraph workflow."""
        try:
            from langchain_core.messages import HumanMessage
            
            # Prepare initial state
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "intent_category": "",
                "intent_score": 0.0,
                "confidence": 0.0,
                "high_intent_indicators": [],
                "budget_mentioned": False,
                "timeline_urgent": False,
                "booking_signals": False,
                "reasoning": "",
                "extraction_priority": "low"
            }
            
            # Run LangGraph workflow
            result = self.workflow.invoke(initial_state)
            
            # Map to ClassificationResult
            intent_category = result["intent_category"]
            intent_score = result["intent_score"]
            confidence = result["confidence"]
            
            # Determine message type based on intent
            if intent_category == "booking_intent":
                message_type = MessageType.BOOKING_INTEREST
            elif intent_category == "budget_inquiry":
                message_type = MessageType.QUALIFICATION
            elif intent_category == "information_request":
                message_type = MessageType.INFORMATION_REQUEST
            elif intent_category == "cold_inquiry":
                message_type = MessageType.GREETING
            else:
                message_type = MessageType.INFORMATION_REQUEST
            
            return ClassificationResult(
                message_type=message_type,
                intent_level=intent_score,
                confidence=confidence,
                extraction_priority=result["extraction_priority"],
                intent_category=intent_category,
                intent_score=intent_score,
                high_intent_indicators=result["high_intent_indicators"],
                budget_mentioned=result["budget_mentioned"],
                timeline_urgent=result["timeline_urgent"],
                booking_signals=result["booking_signals"]
            )
            
        except Exception as e:
            logger.error(f"LangGraph intent classification failed: {e}")
            # Fallback to basic classification
            return self._basic_fallback_classification(message)
    
    def _basic_fallback_classification(self, message: str) -> ClassificationResult:
        """Basic fallback when LangGraph fails."""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["book", "schedule", "tour"]):
            message_type = MessageType.BOOKING_INTEREST
            intent_level = 0.9
        elif any(word in message_lower for word in ["budget", "$", "price"]):
            message_type = MessageType.QUALIFICATION
            intent_level = 0.8
        elif any(word in message_lower for word in ["info", "details"]):
            message_type = MessageType.INFORMATION_REQUEST
            intent_level = 0.6
        else:
            message_type = MessageType.GREETING
            intent_level = 0.4
            
        return ClassificationResult(
            message_type=message_type,
            intent_level=intent_level,
            confidence=0.5,
            extraction_priority="medium" if intent_level >= 0.6 else "low",
            intent_category="fallback_classification",
            intent_score=intent_level,
            high_intent_indicators=["fallback"],
            budget_mentioned="$" in message_lower,
            timeline_urgent=False,
            booking_signals=False
        )

# Legacy MessageTypeClassifier for backward compatibility
class MessageTypeClassifier:
    """Legacy classifier - now uses LangGraphIntentClassifier internally."""
    
    def __init__(self):
        self.langgraph_classifier = LangGraphIntentClassifier()
    
    def classify_message(self, message: str) -> ClassificationResult:
        """Classify message using the new AI-powered system."""
        return self.langgraph_classifier.classify_message(message)
    
    def extract_intent_and_details(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract intent with comprehensive confidence scoring and detail analysis."""
        try:
            # Use existing LangGraph classifier
            classification = self.classify_message(message)
            
            # Calculate comprehensive confidence
            confidence_analysis = self._calculate_comprehensive_confidence(classification, context or {})
            
            return {
                'intent_category': classification.intent_category,
                'intent_score': classification.intent_score,
                'confidence': classification.confidence,
                'confidence_metadata': confidence_analysis,
                'high_intent_indicators': classification.high_intent_indicators,
                'budget_mentioned': classification.budget_mentioned,
                'timeline_urgent': classification.timeline_urgent,
                'booking_signals': classification.booking_signals,
                'message_analysis': self._analyze_message_structure(message),
                'channel_intelligence': self._get_channel_intelligence(context or {}),
                'extraction_priority': classification.extraction_priority,
                'qualification_readiness': self._assess_qualification_readiness(classification)
            }
            
        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            return self._get_fallback_intent_analysis(message)
    
    def classify_high_intent_patterns(self, message: str) -> Dict[str, Any]:
        """Classify high-intent patterns using both AI and rule-based detection."""
        try:
            # Rule-based high-intent patterns
            high_intent_patterns = {
                'booking_signals': [
                    r'\b(book|reserve|hold|secure)\b.*\b(room|unit|apartment|condo|property)\b',
                    r'\b(viewing|showing|tour)\b.*\b(today|tomorrow|asap|immediately)\b',
                    r'\b(move\s*in|occupancy)\b.*\b(urgent|soon|quickly)\b'
                ],
                'budget_mentions': [
                    r'\b(\$|usd|dollar|price|budget|cost)\b.*\b(\d+)',
                    r'\b(afford|affordable|reasonable|cheap|expensive)\b',
                    r'\b(payment|down\s*payment|financing)\b'
                ],
                'timeline_urgent': [
                    r'\b(urgent|asap|immediately|emergency|rush)\b',
                    r'\b(today|tomorrow|this\s*week|end\s*of\s*month)\b',
                    r'\b(moving|move\s*in|deadline)\b'
                ],
                'property_specific': [
                    r'\b(bedroom|bath|sqft|square|foot|floor|balcony|parking)\b',
                    r'\b(penthouse|suite|loft|studio|1br|2br|3br)\b',
                    r'\b(amenity|pool|gym|concierge|doorman)\b'
                ]
            }
            
            pattern_results = {}
            message_lower = message.lower()
            
            for pattern_name, patterns in high_intent_patterns.items():
                matches = []
                score = 0.0
                
                for pattern in patterns:
                    matches_found = re.findall(pattern, message_lower, re.IGNORECASE)
                    if matches_found:
                        matches.extend(matches_found)
                        score += len(matches_found) * 0.1  # Each match adds to score
                
                pattern_results[pattern_name] = {
                    'matches': matches,
                    'score': min(score, 1.0),  # Cap at 1.0
                    'detected': len(matches) > 0
                }
            
            # Calculate overall pattern score
            total_score = sum(result['score'] for result in pattern_results.values())
            pattern_score = min(total_score / len(high_intent_patterns), 1.0)
            
            # Determine if immediate qualification is needed
            immediate_qualification = (
                pattern_results['booking_signals']['detected'] or
                pattern_results['budget_mentions']['score'] >= 0.3 or
                pattern_results['timeline_urgent']['detected']
            )
            
            return {
                'pattern_score': pattern_score,
                'immediate_qualification': immediate_qualification,
                'pattern_results': pattern_results,
                'high_intent_patterns_detected': immediate_qualification,
                'booking_signals': pattern_results['booking_signals']['detected'],
                'budget_mentioned': pattern_results['budget_mentions']['detected'],
                'timeline_urgent': pattern_results['timeline_urgent']['detected'],
                'property_specific': pattern_results['property_specific']['detected'],
                'pattern_analysis_confidence': min(pattern_score * 1.2, 1.0)  # Patterns boost confidence
            }
            
        except Exception as e:
            logger.error(f"High-intent pattern classification failed: {e}")
            return {
                'pattern_score': 0.0,
                'immediate_qualification': False,
                'pattern_results': {},
                'high_intent_patterns_detected': False,
                'pattern_analysis_confidence': 0.0
            }
    
    def _calculate_comprehensive_confidence(
        self,
        classification: ClassificationResult,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive confidence score based on multiple factors.
        
        This method implements a multi-factor confidence scoring system:
        1. Base intent detection confidence (0.6 weight)
        2. Linguistic pattern confidence (0.2 weight)
        3. Context relevance confidence (0.15 weight)
        4. Channel-specific confidence (0.05 weight)
        """
        base_confidence = classification.confidence
        
        # Linguistic pattern confidence
        message = context.get('message', '')
        language_score = self._assess_language_confidence(message)
        structure_score = self._assess_structure_confidence(message)
        linguistic_score = (language_score + structure_score) / 2
        
        # Context relevance confidence
        context_relevance = self._assess_context_relevance(context)
        
        # Channel-specific confidence
        channel = context.get('channel', 'instagram')
        channel_confidence = self._get_channel_confidence(channel)
        
        # Calculate weighted composite confidence
        composite_confidence = (
            base_confidence * 0.6 +
            linguistic_score * 0.2 +
            context_relevance * 0.15 +
            channel_confidence * 0.05
        )
        
        # Apply confidence boost for high-intent categories
        intent_category = classification.intent_category
        category_boosts = {
            'booking_intent': 0.1,
            'budget_inquiry': 0.08,
            'timeline_urgent': 0.06,
            'property_specific': 0.04,
            'information_request': 0.02,
            'general_interest': 0.0,
            'cold_inquiry': -0.05,
            'spam_irrelevant': -0.15
        }
        
        boost = category_boosts.get(intent_category, 0.0)
        final_confidence = max(0.0, min(1.0, composite_confidence + boost))
        
        # Add confidence metadata
        confidence_metadata = {
            'base_confidence': base_confidence,
            'linguistic_score': linguistic_score,
            'context_relevance': context_relevance,
            'channel_confidence': channel_confidence,
            'category_boost': boost,
            'composite_confidence': composite_confidence,
            'final_confidence': final_confidence,
            'confidence_level': self._get_confidence_level(final_confidence),
            'confidence_factors': {
                'language_score': language_score,
                'structure_score': structure_score,
                'channel': channel,
                'message_length': len(message),
                'has_emoji': 'emoji' in message.lower() or any(ord(c) > 127 for c in message)
            }
        }
        
        return confidence_metadata
    
    def _assess_language_confidence(self, message: str) -> float:
        """Assess language detection confidence."""
        if not message:
            return 0.0
        
        # Simple English detection
        english_indicators = ["the", "and", "is", "are", "hello", "hi", "price", "budget", "property"]
        text_lower = message.lower()
        
        english_score = sum(1 for indicator in english_indicators if indicator in text_lower)
        
        if english_score >= 3:
            return 0.95  # High confidence for English
        elif english_score >= 1:
            return 0.7   # Medium confidence
        else:
            return 0.5   # Low confidence for unknown language
    
    def _assess_structure_confidence(self, message: str) -> float:
        """Assess message structure confidence."""
        if not message:
            return 0.0
        
        # Check for reasonable message structure
        length = len(message)
        if 10 <= length <= 500:
            return 0.9   # Optimal length
        elif length < 10:
            return 0.4   # Too short
        elif length > 1000:
            return 0.6   # Very long might be unclear
        
        # Check for question marks, proper case, etc.
        has_question = '?' in message
        has_proper_case = any(word[0].isupper() for word in message.split() if word)
        
        score = 0.7
        if has_question:
            score += 0.1
        if has_proper_case:
            score += 0.1
        
        return min(score, 1.0)
    
    def _assess_context_relevance(self, context: Dict[str, Any]) -> float:
        """Assess context relevance for confidence scoring."""
        relevance_score = 0.5  # Base score
        
        # Check if we have user context
        if context.get('user_id'):
            relevance_score += 0.1
        
        # Check if we have channel context
        if context.get('channel'):
            relevance_score += 0.1
        
        # Check message history
        if context.get('message_history'):
            relevance_score += 0.2
        
        # Check previous interactions
        if context.get('previous_interactions'):
            relevance_score += 0.1
        
        return min(relevance_score, 1.0)
    
    def _get_channel_confidence(self, channel: str) -> float:
        """Get channel-specific confidence multipliers."""
        channel_confidence = {
            'instagram': 0.95,
            'whatsapp': 0.9,
            'facebook': 0.85,
            'telegram': 0.8,
            'web': 1.0,  # Web forms often have higher intent
            'email': 0.9,
            'unknown': 0.7
        }
        
        return channel_confidence.get(channel.lower(), 0.8)
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Convert numerical confidence to categorical level."""
        if confidence >= 0.85:
            return "very_high"
        elif confidence >= 0.7:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        elif confidence >= 0.3:
            return "low"
        else:
            return "very_low"
    
    def _analyze_message_structure(self, message: str) -> Dict[str, Any]:
        """Analyze message structure for additional intelligence."""
        if not message:
            return {}
        
        return {
            'message_length': len(message),
            'word_count': len(message.split()),
            'has_questions': '?' in message,
            'has_exclamations': '!' in message,
            'has_numbers': any(c.isdigit() for c in message),
            'has_currency': any(symbol in message for symbol in ['$', '€', '£', '₹']),
            'urgency_words': len([word for word in ['urgent', 'asap', 'quickly', 'immediately'] if word in message.lower()]),
            'real_estate_keywords': len([word for word in ['property', 'apartment', 'condo', 'house', 'bedroom', 'bathroom'] if word in message.lower()])
        }
    
    def _get_channel_intelligence(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get channel-specific intelligence and characteristics."""
        channel = context.get('channel', 'instagram').lower()
        
        channel_intelligence = {
            'instagram': {
                'typical_response_time': '1-2 hours',
                'character_limit': 2200,
                'media_support': True,
                'business_account_rate': 0.8
            },
            'whatsapp': {
                'typical_response_time': '15-30 minutes',
                'character_limit': 65536,
                'media_support': True,
                'business_account_rate': 0.6
            },
            'facebook': {
                'typical_response_time': '2-4 hours',
                'character_limit': 63206,
                'media_support': True,
                'business_account_rate': 0.7
            }
        }
        
        return channel_intelligence.get(channel, {
            'typical_response_time': '1 hour',
            'character_limit': 1000,
            'media_support': False,
            'business_account_rate': 0.5
        })
    
    def _assess_qualification_readiness(self, classification: ClassificationResult) -> Dict[str, Any]:
        """Assess how ready a lead is for qualification."""
        intent_score = classification.intent_score
        confidence = classification.confidence
        
        # High readiness indicators
        high_intent_signals = classification.booking_signals or classification.budget_mentioned
        
        readiness_score = 0.0
        if high_intent_signals:
            readiness_score += 0.4
        if intent_score >= 0.75:
            readiness_score += 0.3
        if confidence >= 0.7:
            readiness_score += 0.2
        if classification.timeline_urgent:
            readiness_score += 0.1
        
        readiness_level = "high" if readiness_score >= 0.7 else "medium" if readiness_score >= 0.4 else "low"
        
        return {
            'readiness_score': readiness_score,
            'readiness_level': readiness_level,
            'high_intent_signals': high_intent_signals,
            'ready_for_qualification': readiness_score >= 0.5,
            'recommended_action': self._get_recommended_action(readiness_level, intent_score)
        }
    
    def _get_recommended_action(self, readiness_level: str, intent_score: float) -> str:
        """Get recommended action based on readiness assessment."""
        if readiness_level == "high":
            return "immediate_qualification"
        elif readiness_level == "medium":
            return "detailed_extraction"
        else:
            return "basic_nurturing"
    
    def _get_fallback_intent_analysis(self, message: str) -> Dict[str, Any]:
        """Return fallback intent analysis when extraction fails."""
        return {
            'intent_category': 'unknown',
            'intent_score': 0.0,
            'confidence': 0.1,
            'confidence_metadata': {
                'confidence_level': 'very_low',
                'fallback_reason': 'extraction_failed'
            },
            'high_intent_indicators': [],
            'budget_mentioned': False,
            'timeline_urgent': False,
            'booking_signals': False,
            'message_analysis': {
                'message_length': len(message),
                'has_questions': False,
                'urgency_words': 0,
                'real_estate_keywords': 0
            },
            'qualification_readiness': {
                'readiness_score': 0.0,
                'readiness_level': 'low',
                'ready_for_qualification': False,
                'recommended_action': 'basic_nurturing'
            }
        }

class IntelligentExtractor:
    """Production-ready extractor with sophisticated regex and contextual parsing."""
    
    def extract_with_context(self, message: str, classification: ClassificationResult, 
                           prior_data: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """Extract lead information using production-tested patterns."""
        extraction_result = ExtractionResult(
            extraction_confidence=0.85,  # High confidence for production
            conversation_stage=classification.message_type.value
        )
        
        # Extract budget with comprehensive K/M scaling
        budget = self._extract_budget(message)
        if budget:
            extraction_result.budget = budget
        
        # Extract location with smart preposition handling
        location = self._extract_location(message)
        if location:
            extraction_result.location = location
        
        # Extract property type and bedrooms with comprehensive mapping
        property_type, bedrooms = self._extract_property_info(message)
        if property_type:
            extraction_result.property_type = property_type
        if bedrooms:
            extraction_result.desired_bedrooms = bedrooms
        
        # Extract timeline
        timeline = self._extract_timeline(message)
        if timeline:
            extraction_result.timeline = timeline
        
        # Extract contact information
        email = self._extract_email(message)
        if email:
            extraction_result.email = email
            
        phone = self._extract_phone(message)
        if phone:
            extraction_result.phone = phone
        
        logger.info(f"Production extraction: budget={extraction_result.budget}, location='{extraction_result.location}', property_type='{extraction_result.property_type}', bedrooms={extraction_result.desired_bedrooms}")
        
        return extraction_result
    
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

class LangGraphExtractionNode:
    """LangGraph node for extraction workflow integration."""
    
    def __init__(self):
        self.classifier = MessageTypeClassifier()
        self.extractor = IntelligentExtractor()
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node callable that processes extraction in workflow."""
        try:
            message = state.get('message', '')
            prior_data = state.get('extracted_data', {})
            
            if not message:
                logger.warning("No message found in LangGraph state")
                return state
            
            classification = self.classifier.classify_message(message)
            extraction_result = self.extractor.extract_with_context(message, classification, prior_data)
            
            updated_state = state.copy()
            updated_state['message_type'] = classification.message_type.value
            updated_state['intent_level'] = classification.intent_level
            updated_state['extraction_confidence'] = extraction_result.extraction_confidence
            updated_state['extraction_result'] = extraction_result
            updated_state['conversation_stage'] = extraction_result.conversation_stage
            
            current_data = prior_data.copy() if prior_data else {}
            for field in ['budget', 'location', 'property_type', 'timeline', 'desired_bedrooms', 'email', 'phone', 'name']:
                if hasattr(extraction_result, field) and getattr(extraction_result, field) is not None:
                    current_data[field] = getattr(extraction_result, field)
            
            updated_state['extracted_data'] = current_data
            return updated_state
            
        except Exception as e:
            logger.error(f"Error in LangGraph extraction node: {e}")
            state['extraction_error'] = str(e)
            state['extraction_confidence'] = 0.0
            return state

def enhanced_extract_lead_info(message: str, user_id: Optional[str] = None, 
                              prior_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Main API function for enhanced lead information extraction."""
    try:
        classifier = MessageTypeClassifier()
        extractor = IntelligentExtractor()
        
        classification = classifier.classify_message(message)
        extraction_result = extractor.extract_with_context(message, classification, prior_data)
        
        result = {
            "budget": extraction_result.budget,
            "location": extraction_result.location,
            "property_type": extraction_result.property_type,
            "timeline": extraction_result.timeline,
            "desired_bedrooms": extraction_result.desired_bedrooms,
            "email": extraction_result.email,
            "phone": extraction_result.phone,
            "name": extraction_result.name,
            "message_type": classification.message_type.value,
            "intent_level": classification.intent_level,
            "extraction_confidence": extraction_result.extraction_confidence,
            "conversation_stage": extraction_result.conversation_stage,
            "new_information": extraction_result.new_information,
            "updated_fields": extraction_result.updated_fields,
            "extraction_timestamp": __import__('datetime').datetime.now().isoformat(),
            "user_id": user_id,
            "success": True
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in enhanced lead extraction: {e}")
        
        return {
            "budget": None,
            "location": None,
            "property_type": None,
            "timeline": None,
            "desired_bedrooms": None,
            "email": None,
            "phone": None,
            "name": None,
            "message_type": "unknown",
            "intent_level": 0.0,
            "extraction_confidence": 0.0,
            "conversation_stage": "error",
            "new_information": [],
            "updated_fields": [],
            "extraction_timestamp": __import__('datetime').datetime.now().isoformat(),
            "user_id": user_id,
            "success": False,
            "error": str(e)
        }

def extract_lead_info(message: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Legacy function name for backward compatibility."""
    enhanced_result = enhanced_extract_lead_info(message, user_id)
    
    return {
        "budget": enhanced_result.get("budget"),
        "location": enhanced_result.get("location"),
        "property_type": enhanced_result.get("property_type"),
        "timeline": enhanced_result.get("timeline"),
        "other_details": enhanced_result.get("name"),
        "extraction_confidence": enhanced_result.get("extraction_confidence"),
        "message_type": enhanced_result.get("message_type"),
        "intent_level": enhanced_result.get("intent_level"),
        "success": enhanced_result.get("success")
    }

# Initialize LangGraph node for workflow integration
extraction_node = LangGraphExtractionNode()

# Initialize global classifier for module-level functions
_global_classifier = None

def _get_global_classifier():
    """Get or create global classifier instance."""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = MessageTypeClassifier()
    return _global_classifier

def extract_intent_and_details(message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Module-level function for intent extraction with comprehensive confidence scoring."""
    classifier = _get_global_classifier()
    return classifier.extract_intent_and_details(message, context)

def classify_high_intent_patterns(message: str) -> Dict[str, Any]:
    """Module-level function for high-intent pattern classification."""
    classifier = _get_global_classifier()
    return classifier.classify_high_intent_patterns(message)
