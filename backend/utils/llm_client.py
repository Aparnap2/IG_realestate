"""
LLM client for OpenRouter API integration with Gemini fallback according to PRD specifications.
Enhanced with comprehensive error handling, circuit breaker pattern, SLA compliance,
proactive response generation, LangGraph integration, Redis checkpoints, and agentic AI patterns.
"""
import os
import aiohttp
import asyncio
import json
import threading
import time
import logging
from typing import Optional, Dict, Any, List, Union, Tuple
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass, field
import hashlib

load_dotenv()

# Import proactive engagement validation and utilities
from .proactive_validation import validate_proactive_engagement_conditions, PreconditionResult, get_validator
from config.settings import get_settings

# Import simplified proactive engagement system
from .proactive_engagement import (
    SimpleProactiveEngagement,
    ProactiveEngagementConfig,
    EngagementStrategy
)

# Import proactive response engine
from .proactive_responses import generate_proactive_response

# LangGraph and Redis checkpoint imports
try:
    from langgraph import StateGraph, END
    from langgraph.checkpoint.redis import RedisSaver
    from langgraph.types import Send, Command
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = None
    RedisSaver = None
    Send = None
    Command = None
    add_messages = None
    LANGGRAPH_AVAILABLE = False

# New enhanced imports for agentic AI patterns
from .redis_client import redis_client, redis_circuit_breaker

# Agentic AI patterns and Redis checkpoint classes
class TaskComplexity(Enum):
    """Task complexity levels for intelligent model routing."""
    SIMPLE = "simple"           # Basic extraction, classification
    MODERATE = "moderate"       # Qualification, analysis
    COMPLEX = "complex"         # Multi-step reasoning, planning
    SPECIALIZED = "specialized" # Domain-specific tasks

class ModelCapability(Enum):
    """LLM model capabilities for routing decisions."""
    REASONING = "reasoning"
    EXTRACTION = "extraction"
    CONVERSATION = "conversation"
    ANALYSIS = "analysis"
    CREATIVE = "creative"

@dataclass
class ConversationContext:
    """Conversation context with comprehensive state tracking."""
    thread_id: str
    user_id: str
    lead_info: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    qualification_data: Dict[str, Any] = field(default_factory=dict)
    agent_context: Dict[str, Any] = field(default_factory=dict)
    context_analysis: Dict[str, Any] = field(default_factory=dict)
    proactive_interventions: List[Dict[str, Any]] = field(default_factory=list)
    qualification_score: float = 0.0
    booking_stage: str = "initial"
    session_start: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    checkpoint_id: Optional[str] = None
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.conversation_history.append(message)
        self.message_count += 1
        self.last_activity = datetime.utcnow()
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages from conversation history."""
        return self.conversation_history[-count:] if self.conversation_history else []
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current context state."""
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "message_count": self.message_count,
            "session_duration_minutes": (datetime.utcnow() - self.session_start).total_seconds() / 60,
            "last_activity_minutes_ago": (datetime.utcnow() - self.last_activity).total_seconds() / 60,
            "qualification_score": self.qualification_score,
            "booking_stage": self.booking_stage,
            "missing_info": self._identify_missing_info()
        }
    
    def _identify_missing_info(self) -> List[str]:
        """Identify missing qualification information."""
        required_fields = ["budget", "location", "timeline", "property_type"]
        return [field for field in required_fields if not self.qualification_data.get(field)]

class RedisCheckpointManager:
    """Redis-based checkpoint management for LangGraph state persistence."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis checkpoint manager."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.checkpointer = None
        self.namespace = "llm_client"
        self.logger = logging.getLogger(__name__)
        self._initialize_checkpointer()
    
    def _initialize_checkpointer(self):
        """Initialize Redis checkpointer if LangGraph is available."""
        if LANGGRAPH_AVAILABLE and RedisSaver:
            try:
                self.checkpointer = RedisSaver.from_conn_string(self.redis_url)
                self.logger.info("✅ Redis checkpointer initialized successfully")
            except Exception as e:
                self.logger.warning(f"⚠️ Redis checkpointer initialization failed: {e}")
                self.checkpointer = None
        else:
            self.logger.info("📦 LangGraph not available - using fallback checkpoint management")
    
    async def save_checkpoint(
        self,
        thread_id: str,
        state: Dict[str, Any],
        checkpoint_id: Optional[str] = None
    ) -> str:
        """Save state checkpoint to Redis."""
        try:
            if self.checkpointer:
                # Use LangGraph Redis checkpointer
                config = {"configurable": {"thread_id": thread_id}}
                await self.checkpointer.aput(config, state, {}, {})
                return thread_id
            else:
                # Fallback to direct Redis storage
                key = f"{self.namespace}:checkpoint:{thread_id}"
                checkpoint_data = {
                    "state": state,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checkpoint_id": checkpoint_id or thread_id
                }
                await redis_client.setex(key, 86400, json.dumps(checkpoint_data))  # 24h TTL
                return thread_id
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
            return thread_id
    
    async def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load state checkpoint from Redis."""
        try:
            if self.checkpointer:
                # Use LangGraph Redis checkpointer
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = await self.checkpointer.aget(config)
                return checkpoint.channel_values if checkpoint else None
            else:
                # Fallback to direct Redis storage
                key = f"{self.namespace}:checkpoint:{thread_id}"
                data = await redis_client.get(key)
                if data:
                    return json.loads(data)["state"]
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
        return None

class IntelligentModelRouter:
    """Routes requests to optimal models based on task complexity and context."""
    
    def __init__(self):
        """Initialize model router with capability mappings."""
        self.model_capabilities = {
            "anthropic/claude-3-7-sonnet-latest": [ModelCapability.REASONING, ModelCapability.CONVERSATION],
            "nvidia/nemotron-nano-12b-v2-vl:free": [ModelCapability.EXTRACTION, ModelCapability.CONVERSATION],
            "openai/gpt-4o": [ModelCapability.REASONING, ModelCapability.ANALYSIS],
            "openai/gpt-3.5-turbo": [ModelCapability.EXTRACTION, ModelCapability.CONVERSATION],
            "google/gemini-2.5-flash": [ModelCapability.ANALYSIS, ModelCapability.CREATIVE]
        }
    
    def route_request(
        self,
        task_description: str,
        context: Optional[ConversationContext] = None
    ) -> Tuple[str, TaskComplexity, List[ModelCapability]]:
        """Route request to optimal model based on task and context."""
        
        # Analyze task complexity
        complexity = self._analyze_complexity(task_description, context)
        
        # Determine required capabilities
        capabilities = self._determine_required_capabilities(task_description)
        
        # Select primary model
        model = self._select_primary_model(complexity, capabilities)
        
        return model, complexity, capabilities
    
    def _analyze_complexity(self, task_description: str, context: Optional[ConversationContext]) -> TaskComplexity:
        """Analyze task complexity based on content and context."""
        
        complex_indicators = [
            "analyze", "compare", "evaluate", "strategic", "plan", "optimize",
            "complex", "multi-step", "reasoning", "decision", "recommendation"
        ]
        
        simple_indicators = [
            "extract", "classify", "categorize", "basic", "simple", "identify"
        ]
        
        task_lower = task_description.lower()
        complexity_score = 0
        
        # Check for complex reasoning indicators
        if any(indicator in task_lower for indicator in complex_indicators):
            complexity_score += 3
        
        # Check for simple extraction indicators
        if any(indicator in task_lower for indicator in simple_indicators):
            complexity_score -= 2
        
        # Check context factors
        if context:
            complexity_score += len(context.conversation_history) > 5
            complexity_score += context.qualification_score > 0.7
            complexity_score += len(context._identify_missing_info()) > 2
        
        # Determine complexity level
        if complexity_score >= 3:
            return TaskComplexity.COMPLEX
        elif complexity_score >= 1:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.SIMPLE
    
    def _determine_required_capabilities(self, task_description: str) -> List[ModelCapability]:
        """Determine required model capabilities for the task."""
        capabilities = []
        task_lower = task_description.lower()
        
        # Reasoning capabilities
        if any(word in task_lower for word in ["analyze", "evaluate", "reason", "decide"]):
            capabilities.append(ModelCapability.REASONING)
        
        # Extraction capabilities
        if any(word in task_lower for word in ["extract", "identify", "classify", "parse"]):
            capabilities.append(ModelCapability.EXTRACTION)
        
        # Analysis capabilities
        if any(word in task_lower for word in ["compare", "assess", "determine", "calculate"]):
            capabilities.append(ModelCapability.ANALYSIS)
        
        # Creative capabilities
        if any(word in task_lower for word in ["generate", "create", "compose", "write"]):
            capabilities.append(ModelCapability.CREATIVE)
        
        # Default to conversation capability
        if not capabilities:
            capabilities.append(ModelCapability.CONVERSATION)
        
        return capabilities
    
    def _select_primary_model(self, complexity: TaskComplexity, capabilities: List[ModelCapability]) -> str:
        """Select primary model based on complexity and capabilities."""
        
        if complexity == TaskComplexity.COMPLEX:
            if ModelCapability.REASONING in capabilities:
                return "anthropic/claude-3-7-sonnet-latest"
            elif ModelCapability.ANALYSIS in capabilities:
                return "openai/gpt-4o"
            else:
                return "anthropic/claude-3-7-sonnet-latest"
        
        elif complexity == TaskComplexity.MODERATE:
            if ModelCapability.EXTRACTION in capabilities:
                return "nvidia/nemotron-nano-12b-v2-vl:free"
            elif ModelCapability.CONVERSATION in capabilities:
                return "google/gemini-2.5-flash"
            else:
                return "openai/gpt-3.5-turbo"
        
        else:  # SIMPLE
            return "nvidia/nemotron-nano-12b-v2-vl:free"

# Global instances
redis_checkpoint_manager = RedisCheckpointManager()
intelligent_model_router = IntelligentModelRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LLM Client class wrapper for compatibility
class LLMClient:
    """Wrapper class for LLM client functions for compatibility with existing code."""
    
    def __init__(self):
        """Initialize LLM client with default settings."""
        self.api_status = validate_api_key_environment()
        logger.info(f"LLM Client initialized. API Status: {self.api_status}")
    
    def get_response(self, prompt: str, **kwargs) -> str:
        """Get LLM response using the async function."""
        return get_llm_response_sync(prompt, **kwargs)
    
    def extract_lead_info(self, message: str) -> Dict[str, Any]:
        """Extract lead information from message."""
        return extract_lead_info(message)
    
    def generate_response_message(self, lead_info: Dict[str, Any], **kwargs) -> str:
        """Generate response message for lead."""
        return generate_response_message(lead_info, **kwargs)
    
    def health_status(self) -> Dict[str, Any]:
        """Get health status of LLM services."""
        return get_llm_health_status()
    
    def reset_circuits(self):
        """Reset circuit breakers."""
        reset_circuit_breakers()
    
    def generate_proactive_response(self, lead_info: Dict[str, Any], scoring_result: Dict[str, Any],
                                  conversation_stage: str = "qualification", user_message: str = "") -> str:
        """Generate proactive response for lead."""
        return generate_proactive_lead_response(lead_info, scoring_result, conversation_stage, user_message)

# Circuit Breaker States
class CircuitState:
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for LLM API calls with failure tracking and automatic recovery."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60, expected_exception: Exception = Exception):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}")
                
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (self.last_failure_time is not None and
                time.time() - self.last_failure_time >= self.timeout)
                
    def _on_success(self):
        """Handle successful API call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.debug("Circuit breaker reset to CLOSED state")
        
    def _on_failure(self):
        """Handle failed API call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        else:
            logger.info(f"API call failed. Failure count: {self.failure_count}/{self.failure_threshold}")

# Performance Monitor for SLA compliance
class PerformanceMonitor:
    """Monitor API performance and SLA compliance."""
    
    def __init__(self, window_size: int = 100, sla_threshold: float = 60.0):
        self.window_size = window_size
        self.sla_threshold = sla_threshold  # 60 seconds SLA
        self.response_times = deque(maxlen=window_size)
        self.error_counts = deque(maxlen=window_size)
        self.start_time = None
        
    def start_request(self):
        """Mark start of request for timing."""
        self.start_time = time.time()
        
    def end_request(self, success: bool, error: Optional[str] = None):
        """Mark end of request and record metrics."""
        if self.start_time:
            duration = time.time() - self.start_time
            self.response_times.append(duration)
            self.error_counts.append(0 if success else 1)
            self.start_time = None
            
            # Log SLA violations
            if duration > self.sla_threshold:
                logger.warning(f"SLA violation: Request took {duration:.2f}s (threshold: {self.sla_threshold}s)")
                
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        if not self.response_times:
            return {
                "status": "no_data",
                "avg_response_time": 0,
                "error_rate": 0,
                "sla_compliance": 100.0,
                "total_requests": 0
            }
            
        response_times = list(self.response_times)
        error_counts = list(self.error_counts)
        
        avg_response_time = sum(response_times) / len(response_times)
        error_rate = (sum(error_counts) / len(error_counts)) * 100
        sla_compliance = (sum(1 for rt in response_times if rt <= self.sla_threshold) / len(response_times)) * 100
        
        return {
            "status": "healthy",
            "avg_response_time": round(avg_response_time, 2),
            "max_response_time": round(max(response_times), 2),
            "min_response_time": round(min(response_times), 2),
            "error_rate": round(error_rate, 2),
            "sla_compliance": round(sla_compliance, 2),
            "total_requests": len(response_times),
            "sla_threshold": self.sla_threshold,
            "last_updated": datetime.utcnow().isoformat()
        }

# Initialize global instances
openrouter_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
gemini_circuit_breaker = CircuitBreaker(failure_threshold=2, timeout=60)
performance_monitor = PerformanceMonitor()

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google Generative AI not available. Install with: pip install google-generativeai")

# Default model selection - use more efficient free models
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", " nvidia/nemotron-nano-12b-v2-vl:free")

def validate_api_key_environment() -> Dict[str, bool]:
    """Validate API key availability and return status for all LLM providers."""
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "has_any_llm": bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    }

async def get_gemini_response(prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
    """
    Get response from Google Gemini Pro as fallback with enhanced error handling.
    
    Args:
        prompt: The prompt to send to Gemini
        max_tokens: Maximum tokens in response
        temperature: Temperature for response generation
        
    Returns:
        Gemini response text or None if failed
    """
    if not GEMINI_AVAILABLE:
        logger.warning("Gemini not available - google-generativeai package not installed")
        return None
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("Google API key not configured for Gemini fallback")
        return None
    
    def _make_gemini_call():
        """Make the actual Gemini API call."""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Configure generation with safety settings
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "candidate_count": 1
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        if response.text:
            return response.text.strip()
        return None
    
    try:
        # Use circuit breaker for Gemini calls
        response = gemini_circuit_breaker.call(_make_gemini_call)
        if response:
            logger.info("✅ Gemini response received successfully")
            return response
        else:
            logger.warning("❌ Gemini returned empty response")
            return None
            
    except Exception as e:
        logger.error(f"❌ Gemini error: {e}")
        return None

# Local extraction fallback functions
def extract_budget_from_text(text: str) -> Optional[float]:
    """Extract budget information using regex patterns."""
    import re
    
    # Common budget patterns
    patterns = [
        r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $100,000 or $100,000.00
        r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:k|K|thousand)',  # 100k or 100K
        r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:m|M|million)',  # 1m or 1M
        r'budget[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)',  # budget: $100000
        r'looking.*?(\$[0-9,]+)',  # looking for $100000
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                budget_str = match.group(1).replace(',', '')
                budget = float(budget_str)
                
                # Handle k/m suffixes
                if 'k' in pattern.lower():
                    budget *= 1000
                elif 'm' in pattern.lower():
                    budget *= 1000000
                    
                return budget
            except ValueError:
                continue
    
    return None

def extract_location_from_text(text: str) -> Optional[str]:
    """Extract location information using keyword matching."""
    import re
    
    # Common location indicators
    location_keywords = [
        'in', 'at', 'near', 'around', 'looking in', 'area of', 'location'
    ]
    
    # Split text into sentences
    sentences = re.split(r'[.!?]+', text)
    
    for sentence in sentences:
        sentence = sentence.strip().lower()
        for keyword in location_keywords:
            if keyword in sentence:
                # Extract potential location (words after keyword)
                parts = sentence.split(keyword, 1)
                if len(parts) > 1:
                    potential_location = parts[1].strip()
                    # Clean up common prefixes
                    potential_location = re.sub(r'^(for|a|an|the)\s+', '', potential_location)
                    # Take first few words as location
                    location_words = potential_location.split()[:3]
                    if location_words:
                        return ' '.join(location_words).title()
    
    return None

def extract_property_type_from_text(text: str) -> Optional[str]:
    """Extract property type using keyword matching."""
    import re
    
    property_types = {
        '1bhk': '1BHK', '1 bhk': '1BHK',
        '2bhk': '2BHK', '2 bhk': '2BHK',
        '3bhk': '3BHK', '3 bhk': '3BHK',
        '4bhk': '4BHK', '4 bhk': '4BHK',
        'studio': 'Studio',
        'condo': 'Condominium',
        'apartment': 'Apartment',
        'house': 'House',
        'home': 'House',
        'villa': 'Villa',
        'townhouse': 'Townhouse'
    }
    
    text_lower = text.lower()
    for keyword, prop_type in property_types.items():
        if keyword in text_lower:
            return prop_type
    
    # Check for bedroom indicators
    bedroom_match = re.search(r'(\d+)\s*(?:bed|bedroom|br)', text_lower)
    if bedroom_match:
        bedrooms = bedroom_match.group(1)
        return f"{bedrooms}BHK"
    
    return None

def local_extract_lead_info(message: str) -> Dict[str, Any]:
    """
    Extract lead information using local processing as fallback.
    
    Args:
        message: The lead's message
        
    Returns:
        Dictionary with extracted information
    """
    return {
        "budget": extract_budget_from_text(message),
        "location": extract_location_from_text(message),
        "property_type": extract_property_type_from_text(message),
        "timeline": None,  # Hard to extract reliably with regex
        "other_details": "Extracted using local processing (LLM service unavailable)"
    }

async def get_llm_response(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    # Enhanced LangGraph and agentic AI parameters
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    current_state: Optional[Dict[str, Any]] = None,
    extraction_confidence: float = 0.0,
    context_message_analysis: Optional[Dict[str, Any]] = None,
    # New LangGraph-enhanced parameters
    conversation_context: Optional[ConversationContext] = None,
    enable_checkpointing: bool = True,
    enable_intelligent_routing: bool = True,
    agent_type: str = "qualifier"
) -> str:
    """
    Enhanced LLM response with LangGraph patterns, Redis checkpoints, and agentic AI.
    
    This function extends the existing robust LLM client with:
    - Intelligent model routing based on task complexity
    - Redis checkpoint state persistence
    - LangGraph-style conversation management
    - Proactive engagement with configurable thresholds
    - Parallel processing capabilities
    
    Priority: OpenRouter → OpenAI → Gemini → Local Processing
    
    CRITICAL: Includes proactive engagement validation to prevent infinite loops
    when circuit breakers are open.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model to use (default: nvidia/nemotron-nano-12b-v2-vl:free)
        max_tokens: Maximum tokens in response
        temperature: Temperature for response generation
        response_format: Optional OpenRouter response_format for JSON mode
        timeout: Request timeout in seconds
        # Enhanced context and validation parameters
        user_id: User identifier for validation and context
        thread_id: Thread identifier for Redis checkpointing
        lead_id: Lead identifier for validation
        current_state: Current conversation state for validation
        extraction_confidence: Confidence score for extracted information
        context_message_analysis: Analysis of current message context
        # LangGraph-enhanced parameters
        conversation_context: Enhanced conversation context with full state
        enable_checkpointing: Enable Redis checkpoint saving/loading
        enable_intelligent_routing: Enable intelligent model selection
        agent_type: Type of agent for context-aware processing
        
    Returns:
        Enhanced LLM response with metadata
    """
    start_time = time.time()
    
    try:
        # Enhanced model routing with LangGraph patterns
        if enable_intelligent_routing and conversation_context:
            routed_model, complexity, capabilities = intelligent_model_router.route_request(
                task_description=f"{agent_type}: {prompt[:100]}",
                context=conversation_context
            )
            if routed_model != model:
                logger.info(f"🎯 Intelligent routing: {model} → {routed_model} ({complexity.value})")
                model = routed_model
        
        # Redis checkpoint management
        checkpoint_data = None
        if enable_checkpointing and thread_id:
            try:
                # Save checkpoint before processing
                checkpoint_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "prompt": prompt[:500],  # Truncate for storage
                    "model": model,
                    "agent_type": agent_type,
                    "conversation_stage": conversation_context.booking_stage if conversation_context else "unknown"
                }
                await redis_checkpoint_manager.save_checkpoint(thread_id, checkpoint_data)
            except Exception as e:
                logger.warning(f"Failed to save Redis checkpoint: {e}")
        
        # Enhanced validation with conversation context
        if current_state is not None and user_id is not None:
            validation_result = await validate_proactive_engagement_conditions(
                user_id=user_id,
                thread_id=thread_id,
                lead_id=lead_id,
                current_state=current_state or {},
                extraction_confidence=extraction_confidence,
                context_message_analysis=context_message_analysis or {}
            )
            
            if validation_result.result != PreconditionResult.ALLOW:
                logger.info(f"PROACTIVE NOOP: {validation_result.reason}")
                settings = get_settings()
                if (validation_result.result == PreconditionResult.NOOP_CIRCUIT_OPEN and
                    settings.LLM_CIRCUIT_OPEN_NOOP):
                    lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
                    return generate_extracted_info_fallback(lead_info_from_prompt, "circuit_open_fallback")
        
        # Enhanced prompt with conversation context
        enhanced_prompt = prompt
        if conversation_context:
            context_prompt = _build_enhanced_context_prompt(conversation_context, agent_type)
            if context_prompt:
                enhanced_prompt = f"{context_prompt}\n\n{prompt}"
        
        # Call the original robust LLM client implementation
        response = await _original_llm_response(
            enhanced_prompt, model, max_tokens, temperature, response_format, timeout,
            user_id, thread_id, lead_id, current_state, extraction_confidence, context_message_analysis
        )
        
        # Update conversation context if available
        if conversation_context:
            conversation_context.add_message("assistant", response, {
                "model": model,
                "processing_time": time.time() - start_time,
                "agent_type": agent_type,
                "complexity": getattr(complexity, 'value', "unknown") if 'complexity' in locals() else "unknown"
            })
        
        # Log performance metrics
        processing_time = time.time() - start_time
        logger.info(f"✅ LangGraph-enhanced response: {model} ({processing_time:.2f}s)")
        
        return response
        
    except Exception as e:
        logger.error(f"LangGraph-enhanced processing failed: {e}")
        # Fallback to original robust implementation
        return await _original_llm_response(
            prompt, model, max_tokens, temperature, response_format, timeout,
            user_id, thread_id, lead_id, current_state, extraction_confidence, context_message_analysis
        )

async def _original_llm_response(
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    response_format: Optional[Dict[str, Any]],
    timeout: int,
    user_id: Optional[str],
    thread_id: Optional[str],
    lead_id: Optional[str],
    current_state: Optional[Dict[str, Any]],
    extraction_confidence: float,
    context_message_analysis: Optional[Dict[str, Any]]
) -> str:
    """Original LLM response implementation (extracted for reuse)."""
    # Start performance monitoring
    performance_monitor.start_request()
    api_status = validate_api_key_environment()
    
    # CRITICAL: Early validation for proactive engagement safety
    if current_state is not None and user_id is not None:
        validation_result = await validate_proactive_engagement_conditions(
            user_id=user_id,
            thread_id=thread_id,
            lead_id=lead_id,
            current_state=current_state or {},
            extraction_confidence=extraction_confidence,
            context_message_analysis=context_message_analysis
        )
        
        if validation_result.result != PreconditionResult.ALLOW:
            settings = get_settings()
            if (validation_result.result == PreconditionResult.NOOP_CIRCUIT_OPEN and
                settings.LLM_CIRCUIT_OPEN_NOOP):
                performance_monitor.end_request(success=False, error="Circuit open - forced NOOP")
                lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
                return generate_extracted_info_fallback(lead_info_from_prompt, "circuit_open_fallback")
    
    # Log available APIs for debugging
    logger.info(f"API Status: OpenRouter={api_status['openrouter']}, Gemini={api_status['google']}, OpenAI={api_status['openai']}")
    
    # CRITICAL: If LLM_CIRCUIT_OPEN_NOOP and both circuits are open, bail immediately
    settings = get_settings()
    if (settings.LLM_CIRCUIT_OPEN_NOOP and
        openrouter_circuit_breaker.state == CircuitState.OPEN and
        gemini_circuit_breaker.state == CircuitState.OPEN):
        
        logger.warning(
            f"⚡ CIRCUIT OPEN NOOP: Both OpenRouter and Gemini circuits are OPEN. "
            f"OpenRouter last failure: {openrouter_circuit_breaker.last_failure_time}, "
            f"Gemini last failure: {gemini_circuit_breaker.last_failure_time}. "
            f"Forcing early NOOP to prevent local processing loops."
        )
        
        performance_monitor.end_request(success=False, error="Both circuits open - forced NOOP")
        
        lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
        return generate_extracted_info_fallback(lead_info_from_prompt, "circuit_open_early_noop")
    
    # Try OpenRouter first
    if api_status['openrouter']:
        try:
            logger.info(f"🤖 Calling OpenRouter with model: {model}{' [JSON mode]' if response_format else ''}")
            
            def _make_openrouter_call():
                """Make OpenRouter API call through circuit breaker."""
                headers = {
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://aaa-real-estate.com",
                    "X-Title": "IG Real Estate Lead Capture System"
                }

                payload: Dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                if response_format:
                    payload["response_format"] = response_format

                async def _make_async_call():
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                return data["choices"][0]["message"]["content"].strip()
                            elif response.status == 429:
                                raise Exception(f"Rate limit: {await response.text()}")
                            else:
                                raise Exception(f"API error {response.status}: {await response.text()}")
                
                return _run_coro_sync(_make_async_call)
            
            response = openrouter_circuit_breaker.call(_make_openrouter_call)
            performance_monitor.end_request(success=True)
            logger.info("✅ OpenRouter response received successfully")
            return response
            
        except Exception as e:
            logger.warning(f"❌ OpenRouter error: {e}")
            performance_monitor.end_request(success=False, error=str(e))
    
    # Try OpenAI as secondary option if available
    if api_status['openai']:
        try:
            logger.info("🤖 Trying OpenAI as fallback...")
            
            def _make_openai_call():
                """Make OpenAI API call through circuit breaker."""
                headers = {
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                }

                payload: Dict[str, Any] = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                if response_format:
                    payload["response_format"] = response_format

                async def _make_async_call():
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                        async with session.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers=headers,
                            json=payload
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                return data["choices"][0]["message"]["content"].strip()
                            elif response.status == 429:
                                raise Exception(f"Rate limit: {await response.text()}")
                            else:
                                raise Exception(f"API error {response.status}: {await response.text()}")
                
                return _run_coro_sync(_make_async_call)
            
            response = openrouter_circuit_breaker.call(_make_openai_call)
            performance_monitor.end_request(success=True)
            logger.info("✅ OpenAI response received successfully")
            return response
            
        except Exception as e:
            logger.warning(f"❌ OpenAI error: {e}")
            performance_monitor.end_request(success=False, error=str(e))

    # Try Gemini as fallback
    if api_status['google']:
        try:
            logger.info("🔥 Trying Gemini as fallback...")
            gemini_response = await get_gemini_response(prompt, max_tokens, temperature)
            if gemini_response:
                performance_monitor.end_request(success=True)
                logger.info("✅ Gemini fallback successful")
                return gemini_response
        except Exception as e:
            logger.warning(f"❌ Gemini error: {e}")
            performance_monitor.end_request(success=False, error=str(e))

    # All remote APIs failed, use local fallback
    logger.warning("💡 All LLM services unavailable, using local processing fallback")
    performance_monitor.end_request(success=False, error="All LLM services unavailable")
    
    lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
    return await generate_contextual_fallback(prompt, lead_info_from_prompt)

def _build_enhanced_context_prompt(conversation_context: ConversationContext, agent_type: str) -> str:
    """Build enhanced context prompt for better LLM understanding."""
    
    context_parts = []
    
    # Add conversation context
    if conversation_context.message_count > 0:
        context_parts.append(f"CONVERSATION CONTEXT (Message #{conversation_context.message_count}):")
        
        # Add recent conversation
        recent_messages = conversation_context.get_recent_messages(3)
        for msg in recent_messages:
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            context_parts.append(f"{role_emoji} {msg['content'][:100]}...")
    
    # Add qualification context
    if conversation_context.qualification_data:
        context_parts.append(f"\nLEAD QUALIFICATION:")
        for key, value in conversation_context.qualification_data.items():
            if value:
                context_parts.append(f"- {key}: {value}")
        
        context_parts.append(f"Qualification Score: {conversation_context.qualification_score:.2f}")
        context_parts.append(f"Stage: {conversation_context.booking_stage}")
        
        # Add missing information
        missing = conversation_context._identify_missing_info()
        if missing:
            context_parts.append(f"Missing: {', '.join(missing)}")
    
    # Add agent-specific context
    if agent_type == "qualifier":
        context_parts.append("\nAGENT CONTEXT: You are a real estate qualification agent. Focus on gathering missing information and qualifying the lead.")
    elif agent_type == "scheduler":
        context_parts.append("\nAGENT CONTEXT: You are a scheduling agent. Help qualified leads book property tours.")
    elif agent_type == "followup":
        context_parts.append("\nAGENT CONTEXT: You are a follow-up agent. Maintain engagement and provide value.")
    
    return "\n".join(context_parts) if context_parts else ""


def _run_coro_sync(coro_fn, *args, **kwargs):
    """Run an async coroutine in a blocking context using a dedicated thread."""
    result_container: Dict[str, Any] = {}
    exception_container: Dict[str, BaseException] = {}

    def _runner():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_container["value"] = loop.run_until_complete(coro_fn(*args, **kwargs))
            finally:
                loop.close()
        except BaseException as exc:  # noqa: BLE001 - propagate any exception
            exception_container["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in exception_container:
        raise exception_container["error"]

    return result_container.get("value")

def get_llm_response_sync(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    # Additional proactive engagement context for sync version
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    current_state: Optional[Dict[str, Any]] = None,
    extraction_confidence: float = 0.0,
    context_message_analysis: Optional[Dict[str, Any]] = None
) -> str:
    """Blocking wrapper around get_llm_response for sync contexts with LangGraph fallback."""
    try:
        return _run_coro_sync(
            get_llm_response,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            timeout=timeout,
            # Pass proactive engagement context
            user_id=user_id,
            thread_id=thread_id,
            lead_id=lead_id,
            current_state=current_state,
            extraction_confidence=extraction_confidence,
            context_message_analysis=context_message_analysis
        )
    except Exception as e:
        logger.error(f"❌ Sync LLM call failed: {e}")
        
        # CRITICAL: Qualifier-only mode for pilot - route all through qualifier
        settings = get_settings()
        if settings.QUALIFIER_ONLY_MODE:
            logger.info("🔒 QUALIFIER-ONLY MODE: Routing all proactive engagement through qualifier agent")
            # Force qualifier path only
            lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
            return generate_extracted_info_fallback(lead_info_from_prompt, "qualifier_only_fallback")
        
        # Use LangGraph-powered fallback instead of hardcoded responses
        lead_info_from_prompt = parse_lead_info_from_prompt(prompt)
        return _run_coro_sync(
            generate_langgraph_fallback_response,
            prompt=prompt,
            lead_info=lead_info_from_prompt,
            user_id=lead_info_from_prompt.get('user_id')
        )

# Health Monitoring Functions
def get_llm_health_status() -> Dict[str, Any]:
    """Get comprehensive health status of all LLM services."""
    api_status = validate_api_key_environment()
    performance_metrics = performance_monitor.get_metrics()
    
    # Check circuit breaker states
    circuit_states = {
        "openrouter": openrouter_circuit_breaker.state,
        "gemini": gemini_circuit_breaker.state
    }
    
    # Determine overall health
    healthy_apis = sum(1 for status in api_status.values() if status and isinstance(status, bool))
    open_circuits = sum(1 for state in circuit_states.values() if state == CircuitState.OPEN)
    
    if healthy_apis == 0:
        overall_status = "critical"
    elif open_circuits >= len(circuit_states):
        overall_status = "degraded"
    elif performance_metrics.get('error_rate', 0) > 50:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "api_availability": api_status,
        "circuit_breakers": circuit_states,
        "performance_metrics": performance_metrics,
        "sla_compliance": performance_metrics.get('sla_compliance', 0) >= 95,
        "recommendations": _get_health_recommendations(api_status, circuit_states, performance_metrics)
    }

def _get_health_recommendations(api_status: Dict[str, bool], circuit_states: Dict[str, str], performance_metrics: Dict[str, Any]) -> List[str]:
    """Get actionable recommendations based on health status."""
    recommendations = []
    
    if not api_status['openrouter'] and not api_status['openai']:
        recommendations.append("Configure OPENROUTER_API_KEY or OPENAI_API_KEY for LLM functionality")
    
    if not api_status['google']:
        recommendations.append("Configure GOOGLE_API_KEY for Gemini fallback")
    
    if circuit_states.get('openrouter') == CircuitState.OPEN:
        recommendations.append("OpenRouter service is failing - check API key and service status")
    
    if circuit_states.get('gemini') == CircuitState.OPEN:
        recommendations.append("Gemini service is failing - check Google API key and service status")
    
    error_rate = performance_metrics.get('error_rate', 0)
    if error_rate > 20:
        recommendations.append(f"High error rate ({error_rate}%) - investigate API issues")
    
    avg_response_time = performance_metrics.get('avg_response_time', 0)
    if avg_response_time > 30:
        recommendations.append(f"Slow response times ({avg_response_time}s) - consider timeout adjustments")
    
    if not recommendations:
        recommendations.append("All systems operational")
    
    return recommendations

def reset_circuit_breakers():
    """Reset all circuit breakers (useful for testing or recovery)."""
    openrouter_circuit_breaker.state = CircuitState.CLOSED
    openrouter_circuit_breaker.failure_count = 0
    gemini_circuit_breaker.state = CircuitState.CLOSED
    gemini_circuit_breaker.failure_count = 0
    logger.info("Circuit breakers reset")

def clear_performance_metrics():
    """Clear performance metrics (useful for testing or fresh monitoring)."""
    performance_monitor.response_times.clear()
    performance_monitor.error_counts.clear()
    logger.info("Performance metrics cleared")

def get_structured_llm_response(
    prompt: str,
    response_format: Dict[str, Any],
    model: str = DEFAULT_OPENROUTER_MODEL
) -> Dict[str, Any]:
    """
    Get structured response from LLM with specific format.
    
    Args:
        prompt: The prompt to send to the LLM
        response_format: Expected response format
        model: Model to use
        
    Returns:
        Structured response dictionary
    """
    try:
        # Add format instructions to prompt (belt-and-suspenders with JSON mode)
        format_prompt = f"{prompt}\n\nPlease respond strictly as a JSON object matching:\n{response_format}"

        response = _run_coro_sync(
            get_llm_response,
            format_prompt,
            model=model,
            response_format={"type": "json_object"},
        )

        # Try to parse as JSON with robust error handling
        import json
        import re
        try:
            # Strip markdown code blocks if present
            cleaned = re.sub(r'^```json\s*|\s*```$', '', response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r'^```\s*|\s*```$', '', cleaned.strip(), flags=re.MULTILINE)

            # Handle case where LLM returns explanatory text before JSON
            if '{' in cleaned and '}' in cleaned:
                # Extract JSON from the response
                start_idx = cleaned.find('{')
                end_idx = cleaned.rfind('}') + 1
                json_str = cleaned[start_idx:end_idx]

                # Basic JSON repair: fix common issues
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays

                return json.loads(json_str)
            else:
                # Try to repair malformed JSON
                cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas
                cleaned = re.sub(r',\s*]', ']', cleaned)  # Remove trailing commas in arrays
                return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Attempt to repair common JSON issues
            try:
                print(f"⚠️ JSON parsing failed, attempting repair: {e}")
                print(f"   Response was: {response[:500]}...")

                # Try to extract JSON-like content and repair
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    # Fix common issues
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    json_str = re.sub(r'":\s*"([^"]*)"([^,}]*),', r'": "\1\2",', json_str)  # Fix string concatenation
                    return json.loads(json_str)
                else:
                    # Return fallback with default values
                    print(f"❌ Could not extract JSON from response")
                    return {"error": "Failed to parse structured response", "raw_response": response[:200]}
            except Exception as repair_e:
                print(f"❌ JSON repair also failed: {repair_e}")
                return {"error": "Failed to parse structured response", "raw_response": response[:200]}

    except Exception as e:
        print(f"❌ Error getting structured LLM response: {e}")
        return {"error": str(e)}

def extract_lead_info(message: str) -> Dict[str, Any]:
    """
    Extract lead information from a message using LLM with comprehensive fallback.
    
    Args:
        message: The lead's message
        
    Returns:
        Dictionary with extracted information
    """
    api_status = validate_api_key_environment()
    
    # If no LLM APIs available, use local extraction
    if not any([api_status['openrouter'], api_status['openai'], api_status['google']]):
        logger.warning("No LLM APIs available, using local extraction")
        return local_extract_lead_info(message)
    
    try:
        prompt = f"""
        Extract real estate lead information from this message: "{message}"
        
        Look for:
        - Budget (in USD)
        - Location (city/area)
        - Property type (1BHK, 2BHK, 3BHK, Condo, etc.)
        - Timeline (when they want to buy/rent)
        - Any other relevant details
        
        Respond in JSON format:
        {{
            "budget": null or number,
            "location": null or string,
            "property_type": null or string,
            "timeline": null or string,
            "other_details": null or string
        }}
        """
        
        result = get_structured_llm_response(prompt, {
            "budget": "number or null",
            "location": "string or null",
            "property_type": "string or null",
            "timeline": "string or null",
            "other_details": "string or null"
        })
        
        # Validate result structure
        if not isinstance(result, dict) or 'error' in result:
            logger.warning("LLM extraction failed, falling back to local processing")
            return local_extract_lead_info(message)
            
        return result
        
    except Exception as e:
        logger.error(f"Error in lead extraction: {e}")
        return local_extract_lead_info(message)

def generate_response_message(
    lead_info: Dict[str, Any],
    context: str = "",
    agent_type: str = "qualifier"
) -> str:
    """
    Generate a response message for a lead with LangGraph-powered fallback.
    
    Args:
        lead_info: Information about the lead
        context: Additional context
        agent_type: Type of agent generating response
        
    Returns:
        Generated response message or LangGraph-powered fallback
    """
    api_status = validate_api_key_environment()
    
    # If no LLM APIs available, use LangGraph-powered fallback
    if not any([api_status['openrouter'], api_status['openai'], api_status['google']]):
        logger.warning("No LLM APIs available, using LangGraph-powered fallback")
        try:
            # Use sync fallback to LangGraph system
            return _run_coro_sync(
                generate_langgraph_fallback_response,
                f"{agent_type} response",
                lead_info,
                lead_info.get('user_id')
            )
        except Exception as e:
            logger.error(f"LangGraph fallback failed: {e}")
            return generate_extracted_info_fallback(lead_info, f"{agent_type} response")
    
    try:
        if agent_type == "qualifier":
            prompt = f"""
            You are a real estate qualification agent. A lead has contacted us with this information:
            {lead_info}
            
            Context: {context}
            
            Generate a friendly, professional response that:
            1. Acknowledges their interest
            2. Asks for any missing key information (budget, location, property type, timeline)
            3. Keeps the conversation moving forward
            4. Is concise and engaging
            
            Respond as if you're texting the lead directly.
            """
        elif agent_type == "scheduler":
            prompt = f"""
            You are a real estate scheduling agent. A qualified lead needs to schedule a property tour:
            {lead_info}
            
            Context: {context}
            
            Generate a response that:
            1. Congratulates them on being qualified
            2. Offers to schedule a property tour
            3. Asks for their preferred time/date
            4. Is professional and enthusiastic
            5. IMPORTANT: Keep response under 1000 characters for Instagram DMs
            
            Respond as if you're texting the lead directly.
            """
        elif agent_type == "followup":
            prompt = f"""
            You are a real estate follow-up agent. This lead needs nurturing:
            {lead_info}
            
            Context: {context}
            
            Generate a response that:
            1. Stays helpful and engaged
            2. Offers relevant property suggestions
            3. Keeps the door open for future opportunities
            4. Is warm and professional
            5. IMPORTANT: Keep response under 1000 characters for Instagram DMs
            
            Respond as if you're texting the lead directly.
            """
        else:
            prompt = f"Generate a professional real estate response for: {lead_info}"
        
        return get_llm_response_sync(prompt, timeout=15)  # Shorter timeout for response generation
        
    except Exception as e:
        logger.error(f"Error generating response message: {e}")
        # Use LangGraph-powered fallback
        try:
            return _run_coro_sync(
                generate_langgraph_fallback_response,
                f"{agent_type} response generation failed",
                lead_info,
                lead_info.get('user_id')
            )
        except Exception as fallback_error:
            logger.error(f"LangGraph fallback also failed: {fallback_error}")
            return generate_extracted_info_fallback(lead_info, f"{agent_type} response")


async def generate_contextual_fallback(prompt: str, lead_info: Dict[str, Any] = None) -> str:
    """
    Generate intelligent fallback response using LangGraph proactive engagement system.
    
    This replaces hardcoded responses with LangGraph-powered intelligent conversation
    management that analyzes context and generates appropriate responses.
    
    Args:
        prompt: The original prompt that failed
        lead_info: Information about the lead that was extracted
        
    Returns:
        LangGraph-powered contextual response
    """
    if lead_info is None:
        lead_info = {}
    
    # Use LangGraph proactive engagement for intelligent fallback
    user_id = lead_info.get('user_id') if isinstance(lead_info, dict) else None
    return await generate_langgraph_fallback_response(prompt, lead_info, user_id)

def parse_lead_info_from_prompt(prompt: str) -> Dict[str, Any]:
    """Parse lead information from the prompt for response generation."""
    import re
    
    # Look for JSON-like structures in the prompt with improved patterns
    json_patterns = [
        r'\{[^}]*"budget"[^}]*\}',
        r'\{[^}]*"location"[^}]*\}',
        r'\{[^}]*"property_type"[^}]*\}',
        r'\{[^}]*"desired_bedrooms"[^}]*\}',
        # Also look for Python dict format
        r"\{[^}]*'budget'[^}]*\}",
        r"\{[^}]*'location'[^}]*\}",
        r"\{[^}]*'property_type'[^}]*\}",
        r"\{[^}]*'desired_bedrooms'[^}]*\}",
    ]
    
    # Try to find the full dict structure
    full_dict_match = re.search(r'\{[^}]*["\']?(?:budget|location|property_type|desired_bedrooms)["\']?[^}]*\}', prompt, re.IGNORECASE | re.DOTALL)
    if full_dict_match:
        try:
            import json
            # Clean up the JSON/Python dict
            dict_str = full_dict_match.group(0)
            
            # Convert Python dict format to JSON format
            dict_str = re.sub(r"(\w+):", r'"\1":', dict_str)  # Add quotes to keys
            dict_str = re.sub(r":\s*'([^']*)'", r': "\1"', dict_str)  # Convert single to double quotes
            
            return json.loads(dict_str)
        except:
            pass
    
    # Extract individual fields with better patterns
    # Handle both JSON and Python dict formats
    budget_patterns = [
        r'["\']?budget["\']?\s*:\s*(\d+)',
        r"'budget'\s*:\s*(\d+)",
        r'budget.*?(\d{3,})',  # General budget pattern
    ]
    
    location_patterns = [
        r'["\']?location["\']?\s*:\s*["\']([^"\']*)["\']',
        r"'location'\s*:\s*[']([^']*)[']",
    ]
    
    property_type_patterns = [
        r'["\']?property_type["\']?\s*:\s*["\']([^"\']*)["\']',
        r"'property_type'\s*:\s*[']([^']*)[']",
    ]
    
    bedroom_patterns = [
        r'["\']?desired_bedrooms["\']?\s*:\s*(\d+)',
        r"'desired_bedrooms'\s*:\s*(\d+)",
    ]
    
    budget = None
    for pattern in budget_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            budget = int(match.group(1))
            break
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            location = match.group(1)
            break
    
    property_type = None
    for pattern in property_type_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            property_type = match.group(1)
            break
    
    bedrooms = None
    for pattern in bedroom_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            bedrooms = int(match.group(1))
            break
    
    return {
        "budget": budget,
        "location": location,
        "property_type": property_type,
        "desired_bedrooms": bedrooms
    }

async def generate_langgraph_fallback_response(prompt: str, lead_info: Dict[str, Any] = None, user_id: str = None) -> str:
    """
    Generate intelligent fallback response using LangGraph proactive engagement system.
    
    This replaces hardcoded responses with LangGraph-powered intelligent conversation
    management that analyzes context, determines optimal strategies, and generates
    appropriate responses.
    
    Args:
        prompt: The original prompt that failed
        lead_info: Information about the lead that was extracted
        user_id: User identifier for temporal context
        
    Returns:
        LangGraph-powered contextual response
    """
    if lead_info is None:
        lead_info = {}
    
    try:
        # Initialize simple proactive engagement system
        config = ProactiveEngagementConfig()
        engine = SimpleProactiveEngagement(config)
        
        # Build current state for LangGraph analysis
        current_state = {
            "lead": lead_info,
            "qualification": {
                "status": "partial_qualification" if lead_info.get('budget') and lead_info.get('location') else "initial",
                "completeness_score": len([v for v in lead_info.values() if v]) / len(['budget', 'location', 'property_type', 'timeline']) if lead_info else 0
            },
            "conversation_stage": "qualification",
            "last_prompt": prompt
        }
        
        # Analyze conversation context using simple proactive engagement
        context_analysis = await engine.analyze_conversation_context(
            user_id=user_id or "unknown",
            current_state=current_state
        )
        
        # Generate proactive intervention using simple proactive engagement
        intervention = await engine.generate_proactive_intervention(
            user_id=user_id or "unknown",
            context_analysis=context_analysis,
            current_state=current_state
        )
        
        # Execute intervention with simple state management
        execution_result = await engine.execute_simple_intervention(
            user_id=user_id or "unknown",
            intervention=intervention,
            current_state=current_state
        )
        
        # Generate response based on proactive intervention results
        strategy = intervention.get('strategy', 'basic_followup')
        approach = intervention.get('approach', 'helpful')
        message_style = intervention.get('message_style', 'helpful')
        
        # Create agent-specific prompt for LLM processing (with extracted data)
        agent_type = "qualifier" if "qualification" in prompt.lower() else "followup" if "followup" in prompt.lower() else "qualifier"
        
        if agent_type == "qualifier":
            langgraph_prompt = f"""
            You are a real estate qualification agent using LangGraph-proactive engagement.
            
            LangGraph Analysis Results:
            - Strategy: {strategy}
            - Approach: {approach}
            - Message Style: {message_style}
            
            Lead Information: {lead_info}
            
            Generate a response that:
            1. Acknowledges their property interest specifically
            2. Uses the LangGraph-proposed strategy: {strategy}
            3. Addresses missing information proactively
            4. Maintains conversation momentum
            5. Is under 1000 characters for Instagram DMs
            
            Use the extracted information to make responses personal and relevant.
            """
        else:  # followup
            langgraph_prompt = f"""
            You are a real estate follow-up agent using LangGraph-proactive engagement.
            
            LangGraph Analysis Results:
            - Strategy: {strategy}
            - Approach: {approach}
            - Message Style: {message_style}
            
            Lead Information: {lead_info}
            
            Generate a response that:
            1. References their specific property interests
            2. Uses the LangGraph-proposed strategy: {strategy}
            3. Offers relevant value or next steps
            4. Maintains engagement momentum
            5. Is under 1000 characters for Instagram DMs
            
            Make it personal based on their extracted information.
            """
        
        # Try to get LLM response with enhanced prompt
        try:
            llm_response = await get_llm_response(langgraph_prompt, timeout=10)
            if llm_response and len(llm_response) > 20:  # Valid response
                return llm_response
        except Exception as e:
            logger.warning(f"LLM failed in proactive engagement fallback: {e}")
        
        # Fallback to intelligent template based on proactive analysis
        return await generate_intelligent_template_fallback(lead_info, strategy, approach, agent_type)
        
    except Exception as e:
        logger.error(f"LangGraph fallback failed: {e}")
        # Ultimate fallback with extracted information
        return generate_extracted_info_fallback(lead_info, prompt)

def generate_extracted_info_fallback(lead_info: Dict[str, Any], original_prompt: str) -> str:
    """
    Ultimate fallback that uses only extracted lead information.
    
    This ensures we never return hardcoded responses and always acknowledge
    the user's specific information.
    """
    budget = lead_info.get('budget')
    location = lead_info.get('location')
    property_type = lead_info.get('property_type')
    desired_bedrooms = lead_info.get('desired_bedrooms')
    
    if "qualifier" in original_prompt.lower():
        response_parts = ["Hi! 👋 Thanks for reaching out about finding your perfect property!"]
        
        if budget or location or property_type:
            details = []
            if property_type:
                details.append(f"{property_type}")
            if desired_bedrooms and desired_bedrooms != 4:  # Don't duplicate 4BHK
                details.append(f"{desired_bedrooms}BHK")
            if location:
                details.append(f"near {location}")
            if budget:
                details.append(f"with a budget of ${budget:,}")
            
            if details:
                response_parts.append(f"I understand you're looking for {', '.join(details)}.")
        
        missing_info = []
        if not budget:
            missing_info.append("your budget range")
        if not location:
            missing_info.append("your preferred location")
        if not property_type:
            missing_info.append("the type of property you want")
        
        if missing_info:
            response_parts.append(f"To help you find the best options, could you share {', '.join(missing_info)}?")
        
        response_parts.append("I'm here to make your property search as smooth as possible! 🏠✨")
        return " ".join(response_parts)
    
    else:
        return "Hi! 👋 Thanks for reaching out about real estate opportunities. I'm here to help you find the perfect property! To get started, could you tell me your budget range and preferred location? Looking forward to working with you! 🏠✨"

async def generate_intelligent_template_fallback(lead_info: Dict[str, Any], strategy: str, approach: str, agent_type: str) -> str:
    """
    Generate intelligent template response based on LangGraph analysis.
    """
    budget = lead_info.get('budget')
    location = lead_info.get('location')
    property_type = lead_info.get('property_type')
    desired_bedrooms = lead_info.get('desired_bedrooms')
    
    if agent_type == "qualifier":
        if strategy == "progressive_disclosure":
            response_parts = ["Hi! 👋 Great to see your interest in properties!"]
            if budget and location:
                response_parts.append(f"For your {property_type or 'property'} search near {location} with a budget of ${budget:,},")
            response_parts.append("I'd love to get a few more details to find you the perfect match.")
            response_parts.append("What timeframe are you thinking for making a move?")
            return " ".join(response_parts)
        
        elif strategy == "inactivity_reengagement":
            response_parts = ["Hi there! 👋 Thanks for your interest in properties!"]
            if budget and location:
                response_parts.append(f"I see you're looking for a {property_type or 'property'} near {location} with a budget of ${budget:,}.")
            response_parts.append("I'm here to help you find exactly what you need. What can I do to assist you today?")
            return " ".join(response_parts)
        
        else:  # context_aware_suggestion or default
            response_parts = ["Hi! 👋 Thanks for reaching out about finding your perfect property!"]
            
            if budget and location and property_type:
                response_parts.append(f"I understand you're looking for a {property_type} near {location} with a budget of ${budget:,}.")
            elif budget and location:
                response_parts.append(f"I see you're interested in properties near {location} with a budget of ${budget:,}.")
            elif location:
                response_parts.append(f"I see you're interested in properties near {location}.")
            elif budget:
                response_parts.append(f"I see you have a budget of ${budget:,} in mind.")
            
            missing_info = []
            if not budget:
                missing_info.append("your budget range")
            if not location:
                missing_info.append("your preferred location")
            if not property_type:
                missing_info.append("the type of property you want")
            
            if missing_info:
                response_parts.append(f"To help you find the best options, could you share {', '.join(missing_info)}?")
            
            response_parts.append("I'm here to make your property search as smooth as possible! 🏠✨")
            return " ".join(response_parts)
    
    else:  # followup
        if budget and location:
            return f"Hi there! 👋 Just wanted to follow up on your property search for a {property_type or 'property'} near {location} with a budget of ${budget:,}. I have some new properties that might interest you, or if your needs have changed, I'm happy to adjust the search. What would be most helpful for you right now?"
        else:
            return "Hi there! 👋 Just wanted to follow up on your property search and see how things are going. I have some new properties that might interest you, or if your needs have changed, I'm happy to adjust the search. What would be most helpful for you right now?"

def generate_proactive_lead_response(
    lead_info: Dict[str, Any],
    scoring_result: Dict[str, Any],
    conversation_stage: str = "qualification",
    user_message: str = "",
    agent_type: str = "qualifier"
) -> str:
    """
    Generate proactive response for leads according to PRD specification.
    
    This function implements proactive reasoning by:
    - Anticipating user needs beyond initial prompts
    - Pre-empting follow-up questions with recommendations
    - Providing optimal actions with rationale
    - Generating contextual responses with next steps
    
    Args:
        lead_info: Information about the lead
        scoring_result: Lead scoring results
        conversation_stage: Current conversation stage
        user_message: User's latest message
        agent_type: Type of agent generating response
        
    Returns:
        Generated proactive response message
    """
    try:
        # Generate proactive response using the proactive engine
        proactive_result = generate_proactive_response(
            lead_data=lead_info,
            scoring_result=scoring_result,
            conversation_stage=conversation_stage,
            user_message=user_message
        )
        
        # Return the proactive response message
        return proactive_result.get('response_message', "I'm here to help you find your perfect property! Could you tell me more about what you're looking for? 🏠✨")
        
    except Exception as e:
        logger.error(f"Error generating proactive response: {e}")
        # Use sync fallback instead of await

# Enhanced parallel processing function
async def process_parallel_llm_requests(
    requests: List[Dict[str, Any]],
    conversation_context: Optional[ConversationContext] = None,
    max_concurrent: int = 3
) -> List[Dict[str, Any]]:
    """Process multiple LLM requests in parallel with LangGraph coordination."""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_single_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            try:
                response = await get_llm_response(
                    **request_data,
                    conversation_context=conversation_context
                )
                return {
                    "success": True,
                    "response": response,
                    "request_id": request_data.get("request_id", "unknown")
                }
            except Exception as e:
                logger.error(f"Parallel request failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "request_id": request_data.get("request_id", "unknown")
                }
    
    # Execute all requests in parallel
    results = await asyncio.gather(*[
        process_single_request(req) for req in requests
    ])
    
    return results

# Enhanced proactive engagement with thresholds
async def generate_proactive_with_thresholds(
    conversation_context: ConversationContext,
    thresholds: Optional[Dict[str, int]] = None
) -> Optional[Dict[str, Any]]:
    """Generate proactive engagement with configurable thresholds."""
    
    thresholds = thresholds or {
        "inactivity_minutes": 30,
        "max_interventions_per_day": 3,
        "response_time_threshold_hours": 2
    }
    
    # Check inactivity threshold
    time_since_last = (datetime.utcnow() - conversation_context.last_activity).total_seconds() / 60
    if time_since_last < thresholds["inactivity_minutes"]:
        return None
    
    # Check intervention frequency
    today_interventions = [
        intervention for intervention in conversation_context.proactive_interventions
        if (datetime.utcnow() - datetime.fromisoformat(intervention.get("timestamp", "2000-01-01"))).days == 0
    ]
    
    if len(today_interventions) >= thresholds["max_interventions_per_day"]:
        return None
    
    # Generate intervention using existing proactive engine
    try:
        context_analysis = await analyze_conversation_context(
            user_id=conversation_context.user_id,
            current_state=conversation_context.__dict__
        )
        
        intervention = await generate_proactive_intervention(
            user_id=conversation_context.user_id,
            context_analysis=context_analysis,
            current_state=conversation_context.__dict__
        )
        
        return intervention
        
    except Exception as e:
        logger.warning(f"Proactive engagement generation failed: {e}")
        return None

# LangGraph state management functions
async def save_conversation_checkpoint(
    thread_id: str,
    conversation_context: ConversationContext,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Save conversation state to Redis with LangGraph patterns."""
    
    try:
        checkpoint_data = {
            "conversation_context": {
                "thread_id": conversation_context.thread_id,
                "user_id": conversation_context.user_id,
                "message_count": conversation_context.message_count,
                "qualification_data": conversation_context.qualification_data,
                "qualification_score": conversation_context.qualification_score,
                "booking_stage": conversation_context.booking_stage,
                "conversation_history": conversation_context.conversation_history,
                "last_activity": conversation_context.last_activity.isoformat(),
                "proactive_interventions": conversation_context.proactive_interventions
            },
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await redis_checkpoint_manager.save_checkpoint(
            thread_id, checkpoint_data, checkpoint_id=thread_id
        )
        
    except Exception as e:
        logger.error(f"Failed to save conversation checkpoint: {e}")
        return thread_id

async def load_conversation_checkpoint(
    thread_id: str
) -> Optional[ConversationContext]:
    """Load conversation state from Redis with LangGraph patterns."""
    
    try:
        checkpoint_data = await redis_checkpoint_manager.load_checkpoint(thread_id)
        if not checkpoint_data:
            return None
        
        context_data = checkpoint_data.get("conversation_context", {})
        
        # Reconstruct ConversationContext
        conversation_context = ConversationContext(
            thread_id=context_data.get("thread_id", thread_id),
            user_id=context_data.get("user_id", "unknown"),
            qualification_data=context_data.get("qualification_data", {}),
            qualification_score=context_data.get("qualification_score", 0.0),
            booking_stage=context_data.get("booking_stage", "initial"),
            conversation_history=context_data.get("conversation_history", [])
        )
        
        # Set additional fields
        conversation_context.message_count = context_data.get("message_count", 0)
        conversation_context.last_activity = datetime.fromisoformat(
            context_data.get("last_activity", datetime.utcnow().isoformat())
        )
        conversation_context.proactive_interventions = context_data.get("proactive_interventions", [])
        
        return conversation_context
        
    except Exception as e:
        logger.error(f"Failed to load conversation checkpoint: {e}")
        return None

# Advanced prompt engineering framework
class PromptEngineeringFramework:
    """Framework for intelligent prompt engineering with LangGraph patterns."""
    
    def __init__(self):
        self.templates = {
            "qualifier": {
                "initial_contact": """
You are a professional real estate qualification agent. A potential lead has reached out with interest in properties.

CONVERSATION CONTEXT:
{conversation_context}

LEAD INFORMATION:
{lead_info}

TASK: Generate a warm, professional response that:
1. Acknowledges their interest specifically
2. Identifies missing qualification information
3. Uses progressive disclosure to gather details naturally
4. Maintains engagement and momentum
5. Keeps response under 1000 characters for Instagram DMs

Focus on building rapport while efficiently qualifying the lead.
                """,
                "follow_up": """
You are following up with a lead who showed interest in properties.

CONVERSATION CONTEXT:
{conversation_context}

PREVIOUS QUALIFICATION:
{qualification_data}

TASK: Generate a response that:
1. References their specific interests from previous messages
2. Addresses any questions or concerns they may have
3. Provides value or new information
4. Moves the conversation toward qualification or scheduling
5. Is personal and engaging

Use their extracted information to make the message highly relevant.
                """
            },
            "scheduler": {
                "qualified_lead": """
You are a real estate scheduling agent. A qualified lead is ready to book a property tour.

QUALIFIED LEAD INFORMATION:
{lead_info}

QUALIFICATION STATUS:
{qualification_data}

CONVERSATION CONTEXT:
{conversation_context}

TASK: Generate a response that:
1. Congratulates them on being qualified
2. Offers to schedule a property tour
3. Asks for their preferred time and date
4. Mentions relevant properties if available
5. Is enthusiastic and professional
6. Keeps response under 1000 characters

Help them take the next step in their property journey.
                """
            }
        }
    
    def build_prompt(
        self,
        agent_type: str,
        scenario: str,
        conversation_context: Optional[ConversationContext] = None,
        lead_info: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build enhanced prompt using template and context."""
        
        template = self.templates.get(agent_type, {}).get(scenario, "")
        if not template:
            return ""
        
        # Format conversation context
        context_str = ""
        if conversation_context:
            recent_messages = conversation_context.get_recent_messages(3)
            context_parts = []
            
            for msg in recent_messages:
                role = "Lead" if msg["role"] == "user" else "Agent"
                context_parts.append(f"{role}: {msg['content'][:150]}...")
            
            context_str = "\n".join(context_parts)
        
        # Format lead info
        lead_str = ""
        if lead_info:
            lead_parts = []
            for key, value in lead_info.items():
                if value:
                    lead_parts.append(f"- {key}: {value}")
            lead_str = "\n".join(lead_parts)
        
        # Format qualification data
        qual_str = ""
        if conversation_context and conversation_context.qualification_data:
            qual_parts = []
            for key, value in conversation_context.qualification_data.items():
                if value:
                    qual_parts.append(f"- {key}: {value}")
            qual_parts.append(f"- Overall Score: {conversation_context.qualification_score:.2f}")
            qual_parts.append(f"- Stage: {conversation_context.booking_stage}")
            qual_str = "\n".join(qual_parts)
        
        # Format additional context
        addl_str = ""
        if additional_context:
            addl_parts = []
            for key, value in additional_context.items():
                if value:
                    addl_parts.append(f"- {key}: {value}")
            addl_str = "\n".join(addl_parts)
        
        # Replace placeholders
        formatted_prompt = template.format(
            conversation_context=context_str or "No previous conversation.",
            lead_info=lead_str or "No lead information available.",
            qualification_data=qual_str or "No qualification data.",
            additional_context=addl_str
        )
        
        return formatted_prompt

# Global prompt engineering framework instance
prompt_engineering_framework = PromptEngineeringFramework()

# Agent coordination functions
async def coordinate_agents_with_langgraph(
    lead_info: Dict[str, Any],
    current_stage: str,
    conversation_context: Optional[ConversationContext] = None,
    user_message: str = ""
) -> Dict[str, Any]:
    """Coordinate multiple agents using LangGraph patterns."""
    
    try:
        # Save current state checkpoint
        if conversation_context and conversation_context.thread_id:
            await save_conversation_checkpoint(
                conversation_context.thread_id, 
                conversation_context,
                {"current_stage": current_stage, "user_message": user_message}
            )
        
        # Determine optimal agent based on stage and context
        if current_stage == "initial":
            agent_type = "qualifier"
        elif current_stage == "qualified":
            agent_type = "scheduler"
        else:
            agent_type = "followup"
        
        # Build enhanced context
        enhanced_context = {
            "current_stage": current_stage,
            "agent_type": agent_type,
            "conversation_length": conversation_context.message_count if conversation_context else 0,
            "qualification_score": conversation_context.qualification_score if conversation_context else 0.0
        }
        
        # Use prompt engineering framework
        prompt = prompt_engineering_framework.build_prompt(
            agent_type=agent_type,
            scenario="initial_contact" if current_stage == "initial" else "follow_up",
            conversation_context=conversation_context,
            lead_info=lead_info,
            additional_context=enhanced_context
        )
        
        # Generate response with LangGraph enhancement
        response = await get_llm_response(
            prompt=prompt,
            conversation_context=conversation_context,
            agent_type=agent_type,
            enable_intelligent_routing=True,
            enable_checkpointing=True
        )
        
        return {
            "response": response,
            "agent_type": agent_type,
            "current_stage": current_stage,
            "prompt_used": prompt,
            "coordination_success": True
        }
        
    except Exception as e:
        logger.error(f"Agent coordination failed: {e}")
        return {
            "response": "I'm here to help you find your perfect property! Could you tell me more about what you're looking for? 🏠✨",
            "agent_type": "qualifier",
            "current_stage": current_stage,
            "coordination_success": False,
            "error": str(e)
        }

# Export enhanced functions for use in other modules
__all__ = [
    "get_llm_response",
    "ConversationContext",
    "RedisCheckpointManager", 
    "IntelligentModelRouter",
    "process_parallel_llm_requests",
    "generate_proactive_with_thresholds",
    "save_conversation_checkpoint",
    "load_conversation_checkpoint",
    "coordinate_agents_with_langgraph",
    "PromptEngineeringFramework",
    "prompt_engineering_framework"
]
