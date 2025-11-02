"""
Enhanced Prompt Engineering Framework with Context Injection and Progressive Disclosure
Implements sophisticated prompt patterns for pure agentic AI systems

Features:
- Context-aware prompt generation
- Progressive disclosure strategies
- Agent-specific prompt templates
- Dynamic context injection
- Conversation state-based prompting
- Multi-turn conversation optimization
- Personality and tone adaptation
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from functools import lru_cache

from .langgraph_enhanced_agentic_system import (
    EnhancedAgentState,
    TaskRequest,
    AgentCapability,
    TaskComplexityLevel
)

logger = logging.getLogger(__name__)

class PromptStrategy(Enum):
    """Prompt engineering strategies."""
    CONTEXTUAL = "contextual"
    PROGRESSIVE_DISCLOSURE = "progressive_disclosure"
    ROLE_BASED = "role_based"
    CONVERSATION_FLOW = "conversation_flow"
    AGENT_SPECIALIZATION = "agent_specialization"
    ADAPTIVE = "adaptive"

class ConversationPhase(Enum):
    """Conversation phases for progressive disclosure."""
    INITIAL_CONTACT = "initial_contact"
    INFORMATION_GATHERING = "information_gathering"
    QUALIFICATION = "qualification"
    SCHEDULING = "scheduling"
    BOOKING = "booking"
    FOLLOWUP = "followup"
    CONVERSION = "conversion"

class PersonalityTrait(Enum):
    """Agent personality traits."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    ENTHUSIASTIC = "enthusiastic"
    EMPATHETIC = "empathetic"
    AUTHORITATIVE = "authoritative"
    CONSULTATIVE = "consultative"

@dataclass
class PromptContext:
    """Context for prompt generation."""
    agent_type: str
    conversation_phase: ConversationPhase
    personality: PersonalityTrait = PersonalityTrait.PROFESSIONAL
    context_data: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    lead_info: Dict[str, Any] = field(default_factory=dict)
    missing_info: List[str] = field(default_factory=list)
    strategy: PromptStrategy = PromptStrategy.CONTEXTUAL
    user_preferences: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PromptTemplate:
    """Prompt template with variables and conditions."""
    template_id: str
    agent_type: str
    strategy: PromptStrategy
    template: str
    variables: List[str]
    conditions: Dict[str, Any]
    context_requirements: List[str]
    progressive_levels: List[str] = field(default_factory=list)

class EnhancedPromptEngineeringFramework:
    """Enhanced prompt engineering framework with sophisticated patterns."""
    
    def __init__(self):
        self.templates = self._initialize_templates()
        self.context_patterns = self._initialize_context_patterns()
        self.progressive_strategies = self._initialize_progressive_strategies()
        self.personality_adapters = self._initialize_personality_adapters()
        
        # Performance tracking
        self.template_usage_stats = {}
        self.effectiveness_metrics = {}
    
    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize comprehensive prompt templates."""
        templates = {}
        
        # Qualifier Agent Templates
        templates["qualifier_initial_contact"] = PromptTemplate(
            template_id="qualifier_initial_contact",
            agent_type="qualifier",
            strategy=PromptStrategy.CONTEXTUAL,
            template="""
You are a professional real estate qualification agent with expertise in understanding client needs and preferences.

CONVERSATION CONTEXT:
{conversation_summary}

LEAD INFORMATION:
{lead_information}

CURRENT PHASE: {conversation_phase}
MISSING INFORMATION: {missing_info}

TASK: Generate a warm, professional response that:
1. Acknowledges their specific property interest mentioned in: "{user_message}"
2. Uses progressive disclosure to naturally gather missing information
3. Maintains conversation momentum and engagement
4. Demonstrates expertise without being pushy
5. Keeps response under 1000 characters for Instagram DMs

STRATEGY: {strategy_guidance}

{personality_adaptation}

RESPONSE GUIDANCE:
{focused_guidance}

Generate a response that feels natural, helpful, and professional while efficiently qualifying this lead.
            """,
            variables=[
                "conversation_summary", "lead_information", "conversation_phase",
                "missing_info", "user_message", "strategy_guidance",
                "personality_adaptation", "focused_guidance"
            ],
            conditions={
                "conversation_phase": ["initial_contact", "information_gathering"],
                "missing_info": ["budget", "location", "property_type"]
            },
            context_requirements=["user_message", "lead_info", "conversation_history"]
        )
        
        templates["qualifier_progressive"] = PromptTemplate(
            template_id="qualifier_progressive",
            agent_type="qualifier",
            strategy=PromptStrategy.PROGRESSIVE_DISCLOSURE,
            template="""
You are using progressive disclosure to naturally gather qualification information.

CONVERSATION FLOW:
{conversation_flow}

CURRENT FOCUS: {current_focus}
PROGRESSIVE LEVEL: {progressive_level}

LEAD PROGRESS:
{qualification_progress}

CURRENT TASK: {current_task}

{personality_guidance}

RESPONSE APPROACH:
{response_approach}

{context_injection}

Generate a response that advances the conversation naturally toward qualification goals.
            """,
            variables=[
                "conversation_flow", "current_focus", "progressive_level",
                "qualification_progress", "current_task", "personality_guidance",
                "response_approach", "context_injection"
            ],
            conditions={
                "conversation_phase": ["qualification", "information_gathering"]
            },
            context_requirements=["qualification_progress", "conversation_flow"],
            progressive_levels=[
                "basic_acknowledgment",
                "gentle_inquiry",
                "specific_questioning",
                "detailed_qualification"
            ]
        )
        
        # Scheduler Agent Templates
        templates["scheduler_booking_focused"] = PromptTemplate(
            template_id="scheduler_booking_focused",
            agent_type="scheduler",
            strategy=PromptStrategy.ROLE_BASED,
            template="""
You are a skilled real estate scheduling agent who transforms qualified leads into bookings.

QUALIFIED LEAD PROFILE:
{qualified_profile}

QUALIFICATION STATUS:
{qualification_status}

BOOKING READINESS: {booking_readiness}

PROPERTY MATCHES:
{property_matches}

SCHEDULING CONTEXT:
{scheduling_context}

TASK: Generate an enthusiastic, professional response that:
1. Congratulates them on being qualified
2. References their specific preferences from: {lead_preferences}
3. Offers to schedule a property tour
4. Mentions 1-2 relevant properties if available
5. Asks for their preferred viewing times
6. Creates urgency without pressure
7. Keeps response under 1000 characters

{personality_enhancement}

BOOKING PSYCHOLOGY:
{booking_psychology}

Generate a response that moves them toward scheduling a viewing.
            """,
            variables=[
                "qualified_profile", "qualification_status", "booking_readiness",
                "property_matches", "scheduling_context", "lead_preferences",
                "personality_enhancement", "booking_psychology"
            ],
            conditions={
                "conversation_phase": ["scheduling", "booking"],
                "qualification_score": 0.7
            },
            context_requirements=["qualification_score", "lead_preferences", "property_matches"]
        )
        
        # Follow-up Agent Templates
        templates["followup_engagement"] = PromptTemplate(
            template_id="followup_engagement",
            agent_type="followup",
            strategy=PromptStrategy.CONVERSATION_FLOW,
            template="""
You are a relationship-focused follow-up agent who maintains engagement and provides ongoing value.

CONVERSATION HISTORY:
{conversation_summary}

LAST INTERACTION:
{last_interaction}

ENGAGEMENT STATUS:
{engagement_status}

VALUE PROPOSITIONS:
{value_propositions}

MISSED OPPORTUNITIES:
{missed_opportunities}

TASK: Generate a thoughtful, value-driven response that:
1. References something specific from their last message: "{last_message}"
2. Provides immediate value or insights
3. Maintains the relationship without being repetitive
4. Offers relevant next steps or opportunities
5. Uses their name if available: {lead_name}
6. Keeps response under 1000 characters

ENGAGEMENT STRATEGY:
{engagement_strategy}

{relationship_building}

Generate a response that strengthens the relationship and creates future opportunities.
            """,
            variables=[
                "conversation_summary", "last_interaction", "engagement_status",
                "value_propositions", "missed_opportunities", "last_message",
                "lead_name", "engagement_strategy", "relationship_building"
            ],
            conditions={
                "conversation_phase": ["followup", "conversion"]
            },
            context_requirements=["conversation_history", "engagement_level", "value_propositions"]
        )
        
        return templates
    
    def _initialize_context_patterns(self) -> Dict[str, Any]:
        """Initialize context injection patterns."""
        return {
            "conversation_summary": self._generate_conversation_summary,
            "lead_information": self._format_lead_information,
            "qualification_progress": self._analyze_qualification_progress,
            "missing_info": self._identify_missing_information,
            "progressive_level": self._determine_progressive_level,
            "value_propositions": self._generate_value_propositions,
            "engagement_status": self._assess_engagement_status,
            "booking_psychology": self._apply_booking_psychology
        }
    
    def _initialize_progressive_strategies(self) -> Dict[str, Any]:
        """Initialize progressive disclosure strategies."""
        return {
            "gentle_approach": {
                "style": "soft_inquiry",
                "questions": [
                    "I'd love to help you find the perfect property. What's most important to you in your search?",
                    "To suggest the best options, could you share what you're looking for?",
                    "Every great property search starts with understanding your needs. What matters most to you?"
                ],
                "tone": "warm_and_consultative"
            },
            "direct_approach": {
                "style": "specific_questioning",
                "questions": [
                    "What's your budget range for this property search?",
                    "Which area or neighborhood are you most interested in?",
                    "What type of property are you looking for - condo, house, or something else?"
                ],
                "tone": "professional_and_efficient"
            },
            "consultative_approach": {
                "style": "advisory_guidance",
                "questions": [
                    "Based on what you've shared, I think we should focus on [specific area]. What's your take?",
                    "Most buyers in your situation find [property type] works well. Any thoughts?",
                    "From a market perspective, I'd recommend looking at [price range]. Does that align with your thinking?"
                ],
                "tone": "expert_and_consultative"
            }
        }
    
    def _initialize_personality_adapters(self) -> Dict[str, Any]:
        """Initialize personality trait adapters."""
        return {
            PersonalityTrait.PROFESSIONAL: {
                "tone": "professional and businesslike",
                "language": "formal and precise",
                "approach": "focused and efficient",
                "key_phrases": ["I understand", "Based on your requirements", "I recommend"]
            },
            PersonalityTrait.FRIENDLY: {
                "tone": "warm and approachable",
                "language": "conversational and friendly",
                "approach": "supportive and encouraging",
                "key_phrases": ["I'd love to help", "That sounds great", "Let's find you"]
            },
            PersonalityTrait.ENTHUSIASTIC: {
                "tone": "excited and energetic",
                "language": "dynamic and passionate",
                "approach": "motivational and inspiring",
                "key_phrases": ["This is exciting", "I can't wait to help", "Let's make this happen"]
            },
            PersonalityTrait.EMPATHETIC: {
                "tone": "understanding and caring",
                "language": "supportive and validating",
                "approach": "patient and considerate",
                "key_phrases": ["I understand that", "That must be challenging", "Let's work together"]
            },
            PersonalityTrait.AUTHORITATIVE: {
                "tone": "confident and knowledgeable",
                "language": "clear and definitive",
                "approach": "expert guidance",
                "key_phrases": ["Based on my experience", "The best approach is", "I recommend"]
            },
            PersonalityTrait.CONSULTATIVE: {
                "tone": "advisory and collaborative",
                "language": "consultative and partnership-focused",
                "approach": "guided decision-making",
                "key_phrases": ["Let's consider", "In my experience", "What are your thoughts on"]
            }
        }
    
    async def generate_enhanced_prompt(
        self,
        prompt_context: PromptContext,
        user_message: str = "",
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate enhanced prompt with context injection and progressive disclosure."""
        
        try:
            # Select optimal template
            template = self._select_optimal_template(prompt_context)
            
            if not template:
                logger.warning("No suitable template found for context")
                return self._generate_fallback_prompt(prompt_context, user_message)
            
            # Generate context components
            context_components = await self._generate_context_components(
                prompt_context, additional_context
            )
            
            # Apply progressive disclosure if applicable
            if template.strategy == PromptStrategy.PROGRESSIVE_DISCLOSURE:
                context_components = await self._apply_progressive_disclosure(
                    context_components, prompt_context
                )
            
            # Apply personality adaptation
            context_components["personality_adaptation"] = await self._apply_personality_adaptation(
                prompt_context.personality, context_components
            )
            
            # Inject strategy-specific guidance
            context_components["strategy_guidance"] = await self._generate_strategy_guidance(
                template.strategy, prompt_context
            )
            
            # Format the final prompt
            formatted_prompt = self._format_prompt(template, context_components, user_message)
            
            # Track template usage
            self._track_template_usage(template.template_id)
            
            logger.info(f"🎯 Generated enhanced prompt using template: {template.template_id}")
            
            return formatted_prompt
            
        except Exception as e:
            logger.error(f"Enhanced prompt generation failed: {e}")
            return self._generate_fallback_prompt(prompt_context, user_message)
    
    def _select_optimal_template(self, context: PromptContext) -> Optional[PromptTemplate]:
        """Select the most appropriate template for the context."""
        
        # Get templates for the agent type
        agent_templates = {
            template_id: template for template_id, template in self.templates.items()
            if template.agent_type == context.agent_type
        }
        
        if not agent_templates:
            return None
        
        # Score templates based on conditions and context
        template_scores = {}
        
        for template_id, template in agent_templates.items():
            score = 0
            
            # Check strategy match
            if template.strategy == context.strategy:
                score += 10
            
            # Check conditions
            for condition_key, condition_value in template.conditions.items():
                context_value = context.context_data.get(condition_key)
                if context_value in condition_value:
                    score += 5
            
            # Check context requirements
            missing_requirements = set(template.context_requirements) - set(context.context_data.keys())
            if not missing_requirements:
                score += 3
            
            template_scores[template_id] = score
        
        # Return highest scoring template
        if template_scores:
            best_template_id = max(template_scores, key=template_scores.get)
            return self.templates[best_template_id]
        
        return None
    
    async def _generate_context_components(
        self,
        context: PromptContext,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Generate context components for prompt injection."""
        
        components = {}
        
        # Generate each context component
        for component_name, generator_func in self.context_patterns.items():
            try:
                if generator_func:
                    if hasattr(generator_func, '__call__'):
                        component_value = await generator_func(context, additional_context)
                    else:
                        component_value = generator_func(context, additional_context)
                    components[component_name] = component_value
                else:
                    components[component_name] = ""
            except Exception as e:
                logger.warning(f"Context component {component_name} generation failed: {e}")
                components[component_name] = ""
        
        return components
    
    async def _apply_progressive_disclosure(
        self,
        components: Dict[str, str],
        context: PromptContext
    ) -> Dict[str, str]:
        """Apply progressive disclosure strategy."""
        
        # Determine progressive level based on conversation state
        progressive_level = self._determine_progressive_level_internally(context)
        
        # Apply progressive strategy
        if progressive_level in self.progressive_strategies:
            strategy = self.progressive_strategies[progressive_level]
            
            # Update components with progressive guidance
            components["response_approach"] = f"Use {strategy['style']} approach"
            components["personality_guidance"] = f"Maintain {strategy['tone']} tone"
            
            # Add strategic questions if missing info
            if context.missing_info:
                questions = strategy["questions"][:len(context.missing_info)]
                components["strategic_questions"] = "Consider asking: " + ", ".join(questions)
        
        return components
    
    async def _apply_personality_adaptation(
        self,
        personality: PersonalityTrait,
        components: Dict[str, str]
    ) -> str:
        """Apply personality trait adaptation to the prompt."""
        
        if personality not in self.personality_adapters:
            return ""
        
        adapter = self.personality_adapters[personality]
        
        adaptation = f"""
PERSONALITY ADAPTATION:
- Tone: {adapter['tone']}
- Language style: {adapter['language']}
- Approach: {adapter['approach']}
- Key phrases to use: {', '.join(adapter['key_phrases'])}
- Avoid: overly casual language, excessive enthusiasm (unless trait), technical jargon
"""
        
        return adaptation
    
    async def _generate_strategy_guidance(
        self,
        strategy: PromptStrategy,
        context: PromptContext
    ) -> str:
        """Generate strategy-specific guidance."""
        
        guidance_map = {
            PromptStrategy.CONTEXTUAL: "Use all available context to make responses highly relevant and personalized.",
            PromptStrategy.PROGRESSIVE_DISCLOSURE: "Gradually reveal information and ask questions in a natural, conversational flow.",
            PromptStrategy.ROLE_BASED: "Stay in character as the specialized agent and use domain expertise.",
            PromptStrategy.CONVERSATION_FLOW: "Maintain smooth conversation flow and build on previous interactions.",
            PromptStrategy.AGENT_SPECIALIZATION: "Leverage your specific agent capabilities and coordinate with other agents.",
            PromptStrategy.ADAPTIVE: "Flexibly adapt your approach based on real-time feedback and conversation state."
        }
        
        return guidance_map.get(strategy, "Use a balanced, professional approach.")
    
    def _format_prompt(
        self,
        template: PromptTemplate,
        context_components: Dict[str, str],
        user_message: str
    ) -> str:
        """Format the final prompt with all components."""
        
        # Add user message to context if provided
        if user_message:
            context_components["user_message"] = user_message
        
        # Format the template with all variables
        try:
            formatted_prompt = template.template
            
            # Replace variables
            for var in template.variables:
                value = context_components.get(var, f"[{var.upper()}_PLACEHOLDER]")
                formatted_prompt = formatted_prompt.replace(f"{{{var}}}", str(value))
            
            return formatted_prompt
            
        except Exception as e:
            logger.error(f"Prompt formatting failed: {e}")
            return template.template  # Return unformatted template as fallback
    
    # Context generation helper methods
    def _generate_conversation_summary(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate conversation summary."""
        if not context.conversation_history:
            return "This is the start of a new conversation."
        
        summary_parts = []
        user_messages = [msg for msg in context.conversation_history if msg.get("role") == "user"]
        
        if len(user_messages) == 1:
            summary_parts.append("Initial contact made")
        elif len(user_messages) <= 3:
            summary_parts.append("Early stage conversation")
        else:
            summary_parts.append(f"Ongoing conversation with {len(user_messages)} user messages")
        
        # Add recent activity
        recent_messages = context.conversation_history[-2:]
        for msg in recent_messages:
            if msg.get("role") == "user":
                summary_parts.append(f"Recent: {msg['content'][:100]}...")
        
        return " | ".join(summary_parts)
    
    def _format_lead_information(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Format lead information for prompt."""
        if not context.lead_info:
            return "No lead information available yet."
        
        info_parts = []
        for key, value in context.lead_info.items():
            if value:
                info_parts.append(f"- {key}: {value}")
        
        return "\n".join(info_parts) if info_parts else "Basic information gathering in progress."
    
    def _analyze_qualification_progress(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Analyze qualification progress."""
        required_fields = ["budget", "location", "property_type"]
        provided_fields = [field for field in required_fields if context.lead_info.get(field)]
        progress = len(provided_fields) / len(required_fields)
        
        if progress >= 0.8:
            return "Near completion - 80%+ of information gathered"
        elif progress >= 0.5:
            return "Halfway through qualification process"
        elif progress >= 0.2:
            return "Early stage qualification"
        else:
            return "Starting qualification process"
    
    def _identify_missing_information(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Identify missing information."""
        required_fields = ["budget", "location", "property_type", "timeline"]
        missing = [field for field in required_fields if not context.lead_info.get(field)]
        
        if not missing:
            return "All key information gathered"
        
        return ", ".join(missing)
    
    def _determine_progressive_level_internally(self, context: PromptContext) -> str:
        """Determine progressive disclosure level."""
        conversation_length = len(context.conversation_history)
        
        if conversation_length == 0:
            return "gentle_approach"
        elif conversation_length <= 2:
            return "gentle_approach"
        elif conversation_length <= 5:
            return "direct_approach"
        else:
            return "consultative_approach"
    
    def _generate_value_propositions(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate value propositions based on context."""
        propositions = [
            "Expert market knowledge and insights",
            "Access to exclusive property listings",
            "Personalized property matching",
            "Negotiation expertise and market timing",
            "End-to-end transaction support"
        ]
        
        # Personalize based on lead info
        if context.lead_info.get("budget"):
            propositions.insert(0, f"Properties within your ${context.lead_info['budget']:,} budget")
        
        if context.lead_info.get("location"):
            propositions.insert(0, f"Properties in {context.lead_info['location']}")
        
        return " | ".join(propositions[:3])  # Top 3 propositions
    
    def _assess_engagement_status(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Assess engagement status."""
        recent_messages = context.conversation_history[-3:] if context.conversation_history else []
        user_recent = [msg for msg in recent_messages if msg.get("role") == "user"]
        
        if len(user_recent) >= 2:
            return "High engagement - actively participating"
        elif len(user_recent) == 1:
            return "Moderate engagement - responding to prompts"
        else:
            return "Low engagement - may need re-engagement"
    
    def _apply_booking_psychology(self, context: PromptContext, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Apply booking psychology principles."""
        return """
BOOKING PSYCHOLOGY:
- Create urgency without pressure
- Reference specific benefits they'll gain
- Use social proof (other satisfied clients)
- Make the next step feel natural and easy
- Address potential objections preemptively
"""
    
    def _generate_fallback_prompt(self, context: PromptContext, user_message: str) -> str:
        """Generate fallback prompt when template selection fails."""
        return f"""
You are a professional real estate agent helping a potential client.

CONTEXT:
- Agent type: {context.agent_type}
- Conversation phase: {context.conversation_phase.value}
- User message: {user_message}

TASK: Provide a helpful, professional response that moves the conversation forward.

Focus on understanding their needs and providing value. Keep the response concise and engaging.
"""
    
    def _track_template_usage(self, template_id: str):
        """Track template usage for optimization."""
        if template_id not in self.template_usage_stats:
            self.template_usage_stats[template_id] = 0
        self.template_usage_stats[template_id] += 1
    
    def get_template_effectiveness(self, template_id: str) -> Dict[str, Any]:
        """Get effectiveness metrics for a template."""
        return self.effectiveness_metrics.get(template_id, {
            "usage_count": self.template_usage_stats.get(template_id, 0),
            "average_rating": 0.0,
            "success_rate": 0.0
        })

# Specialized prompt generators
class QualifierPromptGenerator:
    """Specialized prompt generator for qualifier agent."""
    
    @staticmethod
    async def generate_qualification_prompt(
        conversation_history: List[Dict[str, Any]],
        lead_info: Dict[str, Any],
        missing_info: List[str],
        personality: PersonalityTrait = PersonalityTrait.PROFESSIONAL
    ) -> str:
        """Generate qualification-focused prompt."""
        
        context = PromptContext(
            agent_type="qualifier",
            conversation_phase=ConversationPhase.QUALIFICATION,
            personality=personality,
            conversation_history=conversation_history,
            lead_info=lead_info,
            missing_info=missing_info,
            strategy=PromptStrategy.PROGRESSIVE_DISCLOSURE
        )
        
        framework = EnhancedPromptEngineeringFramework()
        return await framework.generate_enhanced_prompt(context)

class SchedulerPromptGenerator:
    """Specialized prompt generator for scheduler agent."""
    
    @staticmethod
    async def generate_scheduling_prompt(
        qualification_score: float,
        lead_info: Dict[str, Any],
        property_matches: List[Dict[str, Any]] = None,
        personality: PersonalityTrait = PersonalityTrait.ENTHUSIASTIC
    ) -> str:
        """Generate scheduling-focused prompt."""
        
        context = PromptContext(
            agent_type="scheduler",
            conversation_phase=ConversationPhase.SCHEDULING,
            personality=personality,
            lead_info=lead_info,
            context_data={
                "qualification_score": qualification_score,
                "property_matches": property_matches or []
            },
            strategy=PromptStrategy.ROLE_BASED
        )
        
        framework = EnhancedPromptEngineeringFramework()
        return await framework.generate_enhanced_prompt(context)

class FollowupPromptGenerator:
    """Specialized prompt generator for follow-up agent."""
    
    @staticmethod
    async def generate_followup_prompt(
        conversation_history: List[Dict[str, Any]],
        last_interaction: Dict[str, Any],
        engagement_level: str,
        value_propositions: List[str],
        personality: PersonalityTrait = PersonalityTrait.FRIENDLY
    ) -> str:
        """Generate follow-up focused prompt."""
        
        context = PromptContext(
            agent_type="followup",
            conversation_phase=ConversationPhase.FOLLOWUP,
            personality=personality,
            conversation_history=conversation_history,
            context_data={
                "last_interaction": last_interaction,
                "engagement_level": engagement_level,
                "value_propositions": value_propositions
            },
            strategy=PromptStrategy.CONVERSATION_FLOW
        )
        
        framework = EnhancedPromptEngineeringFramework()
        return await framework.generate_enhanced_prompt(context)

# Export key components
__all__ = [
    "EnhancedPromptEngineeringFramework",
    "PromptContext",
    "PromptTemplate",
    "PromptStrategy",
    "ConversationPhase",
    "PersonalityTrait",
    "QualifierPromptGenerator",
    "SchedulerPromptGenerator",
    "FollowupPromptGenerator"
]

def create_prompt_framework() -> EnhancedPromptEngineeringFramework:
    """Create and return enhanced prompt engineering framework."""
    return EnhancedPromptEngineeringFramework()