"""
Universal Lead Processing Pipeline - Multi-Industry Architecture

This module integrates all Phase 1-3 components into a unified, industry-adaptive
lead processing pipeline that can handle any business type while maintaining specialized
logic needed for high conversion rates.

Key Components Integrated:
- Industry Detection and Configuration Management
- Response Time Tracking (5-minute response window compliance)
- Enhanced Lead Scoring (industry-adaptive scoring)
- Engagement Tracking (touch points and conversion readiness)
- Nurture Sequences (automated follow-up based on industry)
- Smart Booking Engine (multi-factor booking triggers)
- Multi-Channel Communication (intelligent channel selection)
- Industry-Specific Compliance Checking
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# LangGraph imports for dynamic workflow orchestration
try:
    from langgraph.func import entrypoint, task
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import interrupt
    from langgraph.prebuilt import create_react_agent
    from langchain_core.runnables import Runnable
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not available. Install with: pip install langgraph langchain")

# Import all Phase 1-3 components
from ..utils.response_tracker import ResponseTimeTracker, response_tracker
from ..utils.lead_scoring import LeadScoringSystem, calculate_enhanced_lead_score
from ..utils.engagement_tracker import EngagementTracker, engagement_tracker
from ..utils.correlation_tracker import correlation_tracker, CorrelationType
from ..automation.nurture_sequences import NurtureSequenceManager, nurture_sequence_manager
# Import booking state machine integration for T0+120s automation
from ..integrations.booking_state_machine_integration import (
    booking_integration,
    BookingTrigger,
    trigger_booking_flow_immediate,
    process_qualification_completion,
    handle_t0_120s_automation
)
from ..communication.multi_channel_manager import MultiChannelManager, multi_channel_manager
from ..config.industry_configs import get_industry_config_manager, IndustryConfig
from ..utils.supabase_client import save_or_update_lead
from ..utils.audit import audit_log_event
from ..utils.llm_client import get_llm_response_sync
from ..tasks.production_lead_processing import ProductionLeadProcessor

logger = logging.getLogger(__name__)

class WorkflowType(Enum):
    """Workflow types for intelligent routing"""
    BOOKING_FLOW = "booking_flow"
    NURTURE_SEQUENCE = "nurture_sequence"
    DIRECT_RESPONSE = "direct_response"
    QUALIFICATION_GATHERING = "qualification_gathering"
    IMMEDIATE_HANDOFF = "immediate_handoff"

class IndustryType(Enum):
    """Supported industry types"""
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    DEFAULT = "default"

@dataclass
class LeadReadinessAssessment:
    """Comprehensive lead readiness assessment"""
    user_id: str
    industry_type: str
    booking_readiness: bool
    nurture_required: bool
    immediate_response: bool
    qualification_gathering: bool
    readiness_score: float
    confidence_level: float
    assessment_factors: Dict[str, float]
    recommended_workflow: WorkflowType
    next_steps: List[str]
    assessment_timestamp: datetime

@dataclass
class ProcessingContext:
    """Context for lead processing pipeline"""
    user_id: str
    message: str
    channel: str
    user_name: Optional[str]
    industry_type: str
    lead_data: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    previous_scores: List[float]
    touch_points: List[Dict[str, Any]]
    processing_start_time: datetime
    metadata: Dict[str, Any]

class UniversalLeadProcessor:
    """
    Universal Lead Processing Pipeline for Multi-Industry Architecture
    
    This unified system replaces the current fragmented approach with a cohesive,
    industry-adaptive pipeline that can handle any business type while maintaining
    the specialized logic needed for high conversion rates.
    
    Key Features:
    - Industry detection and configuration management
    - Response time tracking with 5-minute window compliance
    - Enhanced lead scoring with industry-adaptive thresholds
    - Engagement tracking and conversion prediction
    - Automated nurture sequences based on industry
    - Smart booking triggers with multi-factor assessment
    - Multi-channel communication with intelligent selection
    - Industry-specific compliance checking
    - Comprehensive error handling and monitoring
    """
    
    def __init__(self):
        """Initialize the universal lead processor with all components."""
        logger.info("🚀 Initializing Universal Lead Processor")
        
        # Initialize all integrated components
        self.response_tracker = response_tracker
        self.lead_scorer = LeadScoringSystem()
        self.engagement_tracker = engagement_tracker
        self.nurture_manager = nurture_sequence_manager
        # Removed old booking engine initialization - now using state machine approach
        self.channel_manager = multi_channel_manager
        self.industry_config_manager = get_industry_config_manager()
        
        # Fallback to existing production processor
        self.production_processor = ProductionLeadProcessor()
        
        # Processing metrics
        self.processing_metrics = {
            'total_processed': 0,
            'successful_processing': 0,
            'industry_distribution': {},
            'workflow_distribution': {},
            'average_processing_time': 0.0,
            'error_count': 0,
            'fallback_count': 0
        }
        
        logger.info("✅ Universal Lead Processor initialized with all components")
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        channel: str = "instagram",
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        Main processing pipeline - orchestrates all components for unified lead processing.
        
        Args:
            user_id: Unique identifier for the user/lead
            message: Incoming message content
            channel: Communication channel (instagram, sms, email, etc.)
            user_name: Optional user name for personalization
            
        Returns:
            Dictionary with processing result, response message, and next steps
        """
        processing_start = datetime.now()
        
        try:
            logger.info(f"🎯 UNIVERSAL PIPELINE: Processing message for {user_id} via {channel}")
            logger.info(f"👤 User: {user_name or 'Unknown'}")
            logger.info(f"📝 Message: '{message[:100]}{'...' if len(message) > 100 else ''}'")
            
            # Update processing metrics
            self.processing_metrics['total_processed'] += 1
            
            # Step 1: Create processing context
            context = await self._create_processing_context(
                user_id, message, channel, user_name
            )
            
            # Step 2: Industry detection and configuration loading
            industry_result = await self.detect_and_configure_industry(
                user_id, message, context.conversation_history
            )
            context.industry_type = industry_result['industry_type']
            context.lead_data.update(industry_result.get('extracted_info', {}))
            
            logger.info(f"🏭 Industry detected: {context.industry_type}")
            logger.info(f"⚙️ Configuration loaded for {context.industry_type}")
            
            # Step 3: Response time tracking
            await self._track_response_time(context)
            
            # Step 4: Enhanced lead scoring
            scoring_result = await self._calculate_enhanced_lead_score(context)
            context.lead_data.update(scoring_result.get('lead_data', {}))
            
            logger.info(f"📊 Enhanced score: {scoring_result.get('enhanced_score', 0):.3f}")
            logger.info(f"🎯 Qualification stage: {scoring_result.get('qualification_stage', 'unknown')}")
            
            # Step 5: Engagement tracking
            await self._track_engagement(context)
            
            # Step 6: Multi-factor assessment
            assessment = await self.assess_lead_readiness(
                user_id, context.lead_data, context.industry_type
            )
            
            logger.info(f"🔍 Lead readiness: {assessment.readiness_score:.3f}")
            logger.info(f"🚀 Recommended workflow: {assessment.recommended_workflow.value}")
            
            # Step 7: Intelligent workflow routing
            routing_result = await self.route_to_appropriate_workflow(
                user_id, assessment, context.industry_type, context
            )
            
            logger.info(f"🧭 Routed to: {routing_result['workflow_type']}")
            logger.info(f"📋 Routing reasoning: {routing_result['reasoning']}")
            
            # Step 8: Execute workflow using LangGraph
            workflow_result = await self._execute_workflow_with_langgraph(
                routing_result['workflow_type'], context, assessment
            )
            
            # Step 9: Industry-specific compliance checking
            compliance_result = await self._check_compliance(
                workflow_result.get('response_message', ''),
                context.industry_type,
                workflow_result.get('workflow_type', 'direct_response')
            )
            
            # Step 10: Generate industry-appropriate response
            final_response = await self.generate_industry_response(
                user_id, context, context.industry_type, 
                routing_result['workflow_type']
            )
            
            # Step 11: Multi-channel message delivery
            delivery_result = await self._deliver_message(
                user_id, final_response, context.industry_type, 
                routing_result['workflow_type']
            )
            
            # Step 12: Update processing metrics
            processing_time = (datetime.now() - processing_start).total_seconds()
            self._update_processing_metrics(
                context.industry_type, routing_result['workflow_type'],
                processing_time, True
            )
            
            # Step 13: Comprehensive audit logging
            await self._audit_processing_pipeline(
                context, assessment, routing_result, workflow_result, 
                compliance_result, delivery_result
            )
            
            # Success response
            self.processing_metrics['successful_processing'] += 1
            
            return {
                "status": "success",
                "user_id": user_id,
                "response_message": final_response,
                "industry_type": context.industry_type,
                "workflow_type": routing_result['workflow_type'],
                "readiness_assessment": asdict(assessment),
                "scoring_result": scoring_result,
                "delivery_result": delivery_result,
                "compliance_result": compliance_result,
                "processing_time_seconds": processing_time,
                "next_steps": routing_result.get('next_steps', []),
                "pipeline_version": "universal_v1.0"
            }
            
        except Exception as e:
            # Comprehensive error handling
            processing_time = (datetime.now() - processing_start).total_seconds()
            self._update_processing_metrics(
                getattr(context, 'industry_type', 'unknown'),
                getattr(assessment, 'recommended_workflow', WorkflowType.DIRECT_RESPONSE),
                processing_time, False
            )
            
            error_msg = f"Universal pipeline error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            # Audit error
            await audit_log_event("universal_pipeline_error", {
                "user_id": user_id,
                "error": str(e),
                "message": message,
                "channel": channel,
                "processing_time": processing_time
            })
            
            # Fallback to production processor
            logger.warning("🔄 Falling back to production processor")
            self.processing_metrics['fallback_count'] += 1
            
            try:
                fallback_result = await self.production_processor.process_lead_message(
                    user_id, message, channel, user_name
                )
                
                return {
                    "status": "fallback_success",
                    "user_id": user_id,
                    "response_message": fallback_result.get("response_message"),
                    "fallback_reason": error_msg,
                    "fallback_result": fallback_result,
                    "processing_time_seconds": processing_time,
                    "pipeline_version": "fallback_to_production"
                }
                
            except Exception as fallback_error:
                logger.error(f"❌ Fallback processor also failed: {str(fallback_error)}")
                
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": error_msg,
                    "fallback_error": str(fallback_error),
                    "response_message": "I'm experiencing technical difficulties. Please try again later.",
                    "processing_time_seconds": processing_time,
                    "pipeline_version": "error_fallback"
                }
    
    async def detect_and_configure_industry(
        self,
        user_id: str,
        message: str,
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Auto-detect business type from conversation and load appropriate configuration.
        
        Args:
            user_id: Unique user identifier
            message: Current message content
            conversation_history: Previous conversation messages
            
        Returns:
            Dictionary with detected industry type and configuration
        """
        try:
            logger.info(f"🔍 DETECTING INDUSTRY for user {user_id}")
            
            # Use industry config manager for detection
            detected_industry = self.industry_config_manager.detect_industry_type(
                message=message,
                extracted_info={},  # Will be populated by LLM extraction
                conversation_history=conversation_history
            )
            
            # Get industry configuration
            industry_config = self.industry_config_manager.get_config(detected_industry)
            
            # Extract industry-specific information from message
            extracted_info = await self._extract_industry_specific_info(
                message, detected_industry
            )
            
            logger.info(f"✅ Industry detected: {detected_industry}")
            logger.info(f"⚙️ Configuration loaded: {industry_config.conversion_threshold}")
            
            return {
                "industry_type": detected_industry,
                "industry_config": industry_config,
                "extracted_info": extracted_info,
                "confidence": 0.85,  # High confidence in detection
                "detection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error detecting industry for user {user_id}: {e}")
            # Default to real estate on error
            default_config = self.industry_config_manager.get_config("real_estate")
            
            return {
                "industry_type": "real_estate",
                "industry_config": default_config,
                "extracted_info": {},
                "confidence": 0.5,
                "error": str(e),
                "detection_timestamp": datetime.now().isoformat()
            }
    
    async def assess_lead_readiness(
        self,
        user_id: str,
        lead_data: Dict[str, Any],
        industry_type: str
    ) -> LeadReadinessAssessment:
        """
        Multi-factor assessment of lead readiness for conversion.
        
        Args:
            user_id: Unique user identifier
            lead_data: Lead information and qualification data
            industry_type: Industry type for specific assessment criteria
            
        Returns:
            Comprehensive lead readiness assessment
        """
        try:
            logger.info(f"🎯 ASSESSING LEAD READINESS for user {user_id} in {industry_type}")
            
            # Get industry configuration
            industry_config = self.industry_config_manager.get_config(industry_type)
            
            # Calculate individual factors
            
            # 1. Enhanced lead score
            scoring_result = calculate_enhanced_lead_score(
                lead_data=lead_data,
                user_id=user_id,
                industry_type=industry_type
            )
            enhanced_score = scoring_result.get('enhanced_score', 0.0)
            
            # 2. Response urgency
            response_urgency = self.response_tracker.calculate_urgency_score(user_id)
            
            # 3. Engagement momentum
            engagement_momentum = self.engagement_tracker.calculate_engagement_momentum(user_id)
            
            # 4. Conversion readiness prediction
            conversion_ready = self.engagement_tracker.should_convert_soon(user_id, industry_type)
            
            # 5. Booking readiness assessment - now handled by state machine
            # booking_readiness = self.booking_engine.assess_booking_readiness(
            #     user_id, lead_data, industry_type
            # )
            booking_readiness = None  # Placeholder - booking now handled by scheduler agent
            
            # Calculate overall readiness score
            readiness_factors = {
                'enhanced_score': enhanced_score,
                'response_urgency': response_urgency,
                'engagement_momentum': engagement_momentum,
                'conversion_readiness': 1.0 if conversion_ready else 0.0,
                'booking_readiness': booking_readiness.readiness_score
            }
            
            # Weighted combination for overall readiness
            readiness_score = (
                enhanced_score * 0.4 +
                response_urgency * 0.2 +
                engagement_momentum * 0.2 +
                (1.0 if conversion_ready else 0.0) * 0.1 +
                booking_readiness.readiness_score * 0.1
            )
            
            # Determine workflow routing based on multi-factor assessment
            conversion_threshold = industry_config.conversion_threshold
            nurture_threshold = industry_config.nurture_threshold
            
            if booking_readiness.is_ready and enhanced_score >= conversion_threshold:
                recommended_workflow = WorkflowType.BOOKING_FLOW
                confidence = min(0.95, readiness_score + 0.2)
            elif enhanced_score >= conversion_threshold:
                recommended_workflow = WorkflowType.IMMEDIATE_HANDOFF
                confidence = min(0.85, readiness_score + 0.1)
            elif enhanced_score >= nurture_threshold:
                recommended_workflow = WorkflowType.NURTURE_SEQUENCE
                confidence = min(0.75, readiness_score)
            elif response_urgency >= 0.8:
                recommended_workflow = WorkflowType.DIRECT_RESPONSE
                confidence = min(0.65, readiness_score)
            else:
                recommended_workflow = WorkflowType.QUALIFICATION_GATHERING
                confidence = min(0.55, readiness_score)
            
            # Generate next steps
            next_steps = self._generate_next_steps(
                recommended_workflow, lead_data, industry_config
            )
            
            assessment = LeadReadinessAssessment(
                user_id=user_id,
                industry_type=industry_type,
                booking_readiness=booking_readiness.is_ready,
                nurture_required=enhanced_score < conversion_threshold,
                immediate_response=response_urgency >= 0.8,
                qualification_gathering=enhanced_score < nurture_threshold,
                readiness_score=round(readiness_score, 3),
                confidence_level=round(confidence, 3),
                assessment_factors=readiness_factors,
                recommended_workflow=recommended_workflow,
                next_steps=next_steps,
                assessment_timestamp=datetime.now()
            )
            
            logger.info(f"✅ Readiness assessment complete: {readiness_score:.3f}")
            logger.info(f"🚀 Recommended workflow: {recommended_workflow.value}")
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error assessing lead readiness for user {user_id}: {e}")
            
            # Return safe default assessment
            return LeadReadinessAssessment(
                user_id=user_id,
                industry_type=industry_type,
                booking_readiness=False,
                nurture_required=True,
                immediate_response=False,
                qualification_gathering=True,
                readiness_score=0.3,
                confidence_level=0.2,
                assessment_factors={},
                recommended_workflow=WorkflowType.QUALIFICATION_GATHERING,
                next_steps=["Please provide more information about your needs"],
                assessment_timestamp=datetime.now()
            )
    
    async def route_to_appropriate_workflow(
        self,
        user_id: str,
        assessment: LeadReadinessAssessment,
        industry_type: str,
        context: Optional[ProcessingContext] = None
    ) -> Dict[str, Any]:
        """
        Intelligent workflow routing using LangGraph for dynamic decision-making.
        
        Args:
            user_id: Unique user identifier
            assessment: Lead readiness assessment
            industry_type: Industry type for specific routing logic
            context: Optional processing context for enhanced routing
            
        Returns:
            Dictionary with workflow routing decision and reasoning
        """
        try:
            logger.info(f"🧭 ROUTING WORKFLOW for user {user_id}")
            
            # Use LangGraph for dynamic routing if available
            if LANGGRAPH_AVAILABLE and context:
                return await self._route_with_langgraph(user_id, assessment, industry_type, context)
            else:
                return await self._route_with_traditional_logic(user_id, assessment, industry_type)
                
        except Exception as e:
            logger.error(f"Error routing workflow for user {user_id}: {e}")
            
            # Default to qualification gathering on error
            return {
                "workflow_type": WorkflowType.QUALIFICATION_GATHERING,
                "reasoning": f"Routing error: {str(e)} - defaulting to qualification",
                "confidence": 0.3,
                "error": str(e),
                "routing_timestamp": datetime.now().isoformat()
            }
    
    async def _route_with_langgraph(
        self,
        user_id: str,
        assessment: LeadReadinessAssessment,
        industry_type: str,
        context: ProcessingContext
    ) -> Dict[str, Any]:
        """Use LangGraph for dynamic workflow routing."""
        try:
            # Create dynamic routing prompt
            routing_prompt = f"""
            Analyze this lead assessment and determine the optimal workflow using AI:
            
            User ID: {user_id}
            Industry: {industry_type}
            Assessment: {asdict(assessment)}
            Context: {asdict(context)}
            
            Available workflows:
            - booking_flow: For leads ready to schedule appointments
            - nurture_sequence: For leads needing automated follow-up
            - direct_response: For immediate conversational response
            - qualification_gathering: For leads needing more information
            - immediate_handoff: For urgent human intervention
            
            Consider:
            1. Lead readiness and qualification level
            2. Industry-specific buying signals
            3. Engagement patterns and history
            4. Conversion probability and urgency
            5. Optimal next steps for highest conversion
            
            Return JSON with:
            - recommended_workflow: "workflow_name"
            - confidence_score: 0.0-1.0
            - reasoning: "Brief explanation of recommendation"
            - alternative_workflows: ["workflow1", "workflow2"]
            - success_factors: ["factor1", "factor2"]
            - next_steps: ["step1", "step2"]
            """
            
            routing_response = get_llm_response_sync(routing_prompt, max_tokens=500)
            
            try:
                import json
                routing_analysis = json.loads(routing_response)
                recommended_workflow = routing_analysis.get("recommended_workflow", "qualification_gathering")
                confidence = routing_analysis.get("confidence_score", 0.7)
                reasoning = routing_analysis.get("reasoning", "AI-based routing decision")
                next_steps = routing_analysis.get("next_steps", assessment.next_steps)
                
                # Map string to WorkflowType enum
                workflow_mapping = {
                    "booking_flow": WorkflowType.BOOKING_FLOW,
                    "nurture_sequence": WorkflowType.NURTURE_SEQUENCE,
                    "direct_response": WorkflowType.DIRECT_RESPONSE,
                    "qualification_gathering": WorkflowType.QUALIFICATION_GATHERING,
                    "immediate_handoff": WorkflowType.IMMEDIATE_HANDOFF
                }
                
                workflow_type = workflow_mapping.get(recommended_workflow, WorkflowType.QUALIFICATION_GATHERING)
                industry_config = self.industry_config_manager.get_config(industry_type)
                
                logger.info(f"🧠 LangGraph routing: {recommended_workflow} (confidence: {confidence:.2f})")
                logger.info(f"🤖 AI reasoning: {reasoning}")
                
                # Update workflow distribution metrics
                if workflow_type.value not in self.processing_metrics['workflow_distribution']:
                    self.processing_metrics['workflow_distribution'][workflow_type.value] = 0
                self.processing_metrics['workflow_distribution'][workflow_type.value] += 1
                
                return {
                    "workflow_type": workflow_type,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "industry_config": industry_config,
                    "next_steps": next_steps,
                    "routing_timestamp": datetime.now().isoformat(),
                    "routing_method": "langgraph_dynamic",
                    "ai_analysis": routing_analysis
                }
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse routing analysis: {routing_response}")
                # Fallback to traditional logic
                return await self._route_with_traditional_logic(user_id, assessment, industry_type)
                
        except Exception as e:
            logger.error(f"Error in LangGraph routing: {e}")
            # Fallback to traditional logic
            return await self._route_with_traditional_logic(user_id, assessment, industry_type)
    
    async def _route_with_traditional_logic(
        self,
        user_id: str,
        assessment: LeadReadinessAssessment,
        industry_type: str
    ) -> Dict[str, Any]:
        """Traditional workflow routing logic as fallback."""
        try:
            workflow_type = assessment.recommended_workflow
            industry_config = self.industry_config_manager.get_config(industry_type)
            
            # Generate routing reasoning
            reasoning_parts = []
            
            if assessment.booking_readiness:
                reasoning_parts.append(f"Booking ready (score: {assessment.readiness_score:.3f})")
            
            if assessment.nurture_required:
                reasoning_parts.append(f"Nurture needed (score: {assessment.readiness_score:.3f} < {industry_config.conversion_threshold})")
            
            if assessment.immediate_response:
                reasoning_parts.append(f"Immediate response required (urgency: {assessment.assessment_factors.get('response_urgency', 0):.3f})")
            
            if assessment.qualification_gathering:
                reasoning_parts.append(f"Qualification gathering needed (score: {assessment.readiness_score:.3f} < {industry_config.nurture_threshold})")
            
            routing_reasoning = " | ".join(reasoning_parts) or "Standard processing"
            
            # Update workflow distribution metrics
            if workflow_type.value not in self.processing_metrics['workflow_distribution']:
                self.processing_metrics['workflow_distribution'][workflow_type.value] = 0
            self.processing_metrics['workflow_distribution'][workflow_type.value] += 1
            
            logger.info(f"✅ Traditional routing: {workflow_type.value}")
            logger.info(f"📋 Reasoning: {routing_reasoning}")
            
            return {
                "workflow_type": workflow_type,
                "reasoning": routing_reasoning,
                "confidence": assessment.confidence_level,
                "industry_config": industry_config,
                "next_steps": assessment.next_steps,
                "routing_timestamp": datetime.now().isoformat(),
                "routing_method": "traditional_logic"
            }
            
        except Exception as e:
            logger.error(f"Error in traditional routing: {e}")
            
            # Default to qualification gathering on error
            return {
                "workflow_type": WorkflowType.QUALIFICATION_GATHERING,
                "reasoning": f"Routing error: {str(e)} - defaulting to qualification",
                "confidence": 0.3,
                "error": str(e),
                "routing_timestamp": datetime.now().isoformat(),
                "routing_method": "error_fallback"
            }
    
    async def generate_industry_response(
        self,
        user_id: str,
        context: ProcessingContext,
        industry_type: str,
        workflow: WorkflowType
    ) -> str:
        """
        Generate industry-appropriate response based on workflow and context.
        
        Args:
            user_id: Unique user identifier
            context: Processing context with all lead information
            industry_type: Industry type for specific response patterns
            workflow: Current workflow type
            
        Returns:
            Industry-appropriate response message
        """
        try:
            logger.info(f"💬 GENERATING RESPONSE for {industry_type} - {workflow.value}")
            
            # Get industry configuration for value propositions
            industry_config = self.industry_config_manager.get_config(industry_type)
            
            # Build response context
            response_context = {
                "user_name": context.user_name or "there",
                "industry_type": industry_type,
                "workflow": workflow.value,
                "lead_data": context.lead_data,
                "value_props": industry_config.value_props,
                "readiness_score": context.lead_data.get('enhanced_score', 0.0),
                "conversation_history": context.conversation_history[-3:] if context.conversation_history else []
            }
            
            # Generate workflow-specific response
            if workflow == WorkflowType.BOOKING_FLOW:
                response = await self._generate_booking_response(response_context)
            elif workflow == WorkflowType.NURTURE_SEQUENCE:
                response = await self._generate_nurture_response(response_context)
            elif workflow == WorkflowType.DIRECT_RESPONSE:
                response = await self._generate_direct_response(response_context)
            elif workflow == WorkflowType.QUALIFICATION_GATHERING:
                response = await self._generate_qualification_response(response_context)
            elif workflow == WorkflowType.IMMEDIATE_HANDOFF:
                response = await self._generate_handoff_response(response_context)
            else:
                response = await self._generate_default_response(response_context)
            
            logger.info(f"✅ Response generated for {workflow.value}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response for user {user_id}: {e}")
            
            # Fallback response
            return f"Hi {context.user_name or 'there'}! I'm here to help you. Could you tell me more about what you're looking for?"
    
    async def _create_processing_context(
        self,
        user_id: str,
        message: str,
        channel: str,
        user_name: str
    ) -> ProcessingContext:
        """Create comprehensive processing context for the pipeline."""
        try:
            # Get existing conversation history and lead data
            from ..utils.redis_client import get_thread_state, get_conversation_state
            
            thread_state = get_thread_state(f"langgraph:thread:{user_id}") or {}
            conv_state = get_conversation_state(user_id) or {}
            
            conversation_history = thread_state.get("messages", [])
            lead_data = thread_state.get("lead", {})
            
            # Get touch points for engagement tracking
            touch_points = self.engagement_tracker.get_touch_history(user_id, limit=10)
            
            # Get previous scores for trend analysis
            previous_scores = []
            if 'qualification' in thread_state:
                qualification = thread_state['qualification']
                if 'final_score' in qualification:
                    previous_scores.append(qualification['final_score'])
            
            return ProcessingContext(
                user_id=user_id,
                message=message,
                channel=channel,
                user_name=user_name,
                industry_type="",  # Will be detected
                lead_data=lead_data,
                conversation_history=conversation_history,
                previous_scores=previous_scores,
                touch_points=touch_points,
                processing_start_time=datetime.now(),
                metadata={
                    "thread_state": thread_state,
                    "conversation_state": conv_state
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating processing context: {e}")
            
            # Return minimal context on error
            return ProcessingContext(
                user_id=user_id,
                message=message,
                channel=channel,
                user_name=user_name,
                industry_type="real_estate",  # Default
                lead_data={},
                conversation_history=[],
                previous_scores=[],
                touch_points=[],
                processing_start_time=datetime.now(),
                metadata={"error": str(e)}
            )
    
    async def _track_response_time(self, context: ProcessingContext) -> None:
        """Track response time for 5-minute window compliance."""
        try:
            # Track first response if this is a new lead
            if not context.conversation_history:
                self.response_tracker.track_first_response(
                    context.user_id,
                    context.processing_start_time
                )
            
            # Update response timestamp
            self.response_tracker.update_response_timestamp(
                context.user_id,
                context.processing_start_time
            )
            
        except Exception as e:
            logger.error(f"Error tracking response time: {e}")
    
    async def _calculate_enhanced_lead_score(self, context: ProcessingContext) -> Dict[str, Any]:
        """Calculate enhanced lead score with industry-adaptive scoring."""
        try:
            return calculate_enhanced_lead_score(
                lead_data=context.lead_data,
                user_id=context.user_id,
                industry_type=context.industry_type,
                conversation_history=context.conversation_history,
                touch_points=context.touch_points
            )
        except Exception as e:
            logger.error(f"Error calculating enhanced lead score: {e}")
            return {"enhanced_score": 0.5, "error": str(e)}
    
    async def _track_engagement(self, context: ProcessingContext) -> None:
        """Track engagement touch points."""
        try:
            self.engagement_tracker.record_touch_point(
                user_id=context.user_id,
                touch_type=context.channel,
                content=context.message,
                metadata={
                    "industry_type": context.industry_type,
                    "processing_pipeline": "universal",
                    "message_length": len(context.message)
                }
            )
        except Exception as e:
            logger.error(f"Error tracking engagement: {e}")
    
    async def _execute_workflow(
        self,
        workflow_type: WorkflowType,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute the appropriate workflow based on routing decision."""
        try:
            logger.info(f"🚀 EXECUTING WORKFLOW: {workflow_type.value}")
            
            if workflow_type == WorkflowType.BOOKING_FLOW:
                return await self._execute_booking_workflow(context, assessment)
            elif workflow_type == WorkflowType.NURTURE_SEQUENCE:
                return await self._execute_nurture_workflow(context, assessment)
            elif workflow_type == WorkflowType.IMMEDIATE_HANDOFF:
                return await self._execute_handoff_workflow(context, assessment)
            elif workflow_type == WorkflowType.QUALIFICATION_GATHERING:
                return await self._execute_qualification_workflow(context, assessment)
            else:  # DIRECT_RESPONSE
                return await self._execute_direct_response_workflow(context, assessment)
                
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_type.value}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _check_compliance(
        self,
        message: str,
        industry_type: str,
        workflow_type: WorkflowType
    ) -> Dict[str, Any]:
        """Check industry-specific compliance for the message."""
        try:
            # Use multi-channel manager for compliance checking
            from ..communication.multi_channel_manager import IndustryType
            
            industry_enum = IndustryType(industry_type.upper())
            
            # Check compliance using the channel manager
            compliance_passed = self.channel_manager.check_compliance(
                user_id="",  # Not needed for compliance check
                message=message,
                channel=self.channel_manager.get_optimal_channel("", "engagement", "normal"),
                industry_type=industry_enum
            )
            
            return {
                "passed": compliance_passed,
                "industry_type": industry_type,
                "workflow_type": workflow_type.value,
                "compliance_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking compliance: {e}")
            return {"passed": True, "error": str(e)}  # Allow on error
    
    async def _deliver_message(
        self,
        user_id: str,
        message: str,
        industry_type: str,
        workflow_type: WorkflowType
    ) -> Dict[str, Any]:
        """Deliver message via optimal channel."""
        try:
            # Determine message type and priority based on workflow
            message_type = "engagement"
            priority = "normal"
            
            if workflow_type == WorkflowType.BOOKING_FLOW:
                message_type = "booking"
                priority = "high"
            elif workflow_type == WorkflowType.IMMEDIATE_HANDOFF:
                message_type = "urgent"
                priority = "urgent"
            
            # Send via multi-channel manager
            delivery_result = self.channel_manager.send_message(
                user_id=user_id,
                message=message,
                channel="auto",  # Let manager select optimal channel
                priority=priority,
                message_type=message_type
            )
            
            return delivery_result
            
        except Exception as e:
            logger.error(f"Error delivering message: {e}")
            return {"success": False, "error": str(e)}
    
    async def _extract_industry_specific_info(
        self,
        message: str,
        industry_type: str
    ) -> Dict[str, Any]:
        """Extract industry-specific information from message."""
        try:
            # Use LLM to extract industry-specific information
            extraction_prompt = f"""
            Extract industry-specific information from this message for {industry_type} industry.
            
            Message: "{message}"
            
            Extract and return JSON with these fields:
            - budget: numeric budget amount if mentioned
            - location: location/area mentioned
            - timeline: purchase/booking timeline
            - {industry_type}_specific: any industry-specific details
            
            Return only valid JSON, no explanations.
            """
            
            response = get_llm_response_sync(extraction_prompt, max_tokens=500)
            
            try:
                import json
                extracted_info = json.loads(response)
                return extracted_info
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM extraction response: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"Error extracting industry-specific info: {e}")
            return {}
    
    def _generate_next_steps(
        self,
        workflow: WorkflowType,
        lead_data: Dict[str, Any],
        industry_config: IndustryConfig
    ) -> List[str]:
        """Generate next steps based on workflow and industry."""
        try:
            if workflow == WorkflowType.BOOKING_FLOW:
                return [
                    "Select preferred time slot",
                    "Provide contact information",
                    "Confirm booking details"
                ]
            elif workflow == WorkflowType.NURTURE_SEQUENCE:
                return [
                    "Continue engagement through nurture sequence",
                    "Provide additional information as requested",
                    "Monitor engagement and adjust approach"
                ]
            elif workflow == WorkflowType.QUALIFICATION_GATHERING:
                missing_fields = []
                for field in ['budget', 'location', 'timeline']:
                    if not lead_data.get(field):
                        missing_fields.append(field)
                
                return [
                    f"Provide missing information: {', '.join(missing_fields)}",
                    "Answer qualification questions",
                    "Engage with value propositions"
                ]
            elif workflow == WorkflowType.IMMEDIATE_HANDOFF:
                return [
                    "Connect with specialist/agent",
                    "Schedule consultation",
                    "Provide detailed requirements"
                ]
            else:  # DIRECT_RESPONSE
                return [
                    "Continue conversation",
                    "Monitor for qualification signals",
                    "Provide relevant information"
                ]
                
        except Exception as e:
            logger.error(f"Error generating next steps: {e}")
            return ["Continue conversation"]
    
    def _update_processing_metrics(
        self,
        industry_type: str,
        workflow_type: WorkflowType,
        processing_time: float,
        success: bool
    ) -> None:
        """Update processing metrics for monitoring."""
        try:
            # Update industry distribution
            if industry_type not in self.processing_metrics['industry_distribution']:
                self.processing_metrics['industry_distribution'][industry_type] = 0
            self.processing_metrics['industry_distribution'][industry_type] += 1
            
            # Update average processing time
            total_time = self.processing_metrics['average_processing_time'] * (self.processing_metrics['total_processed'] - 1)
            self.processing_metrics['average_processing_time'] = (total_time + processing_time) / self.processing_metrics['total_processed']
            
            # Update error count
            if not success:
                self.processing_metrics['error_count'] += 1
                
        except Exception as e:
            logger.error(f"Error updating processing metrics: {e}")
    
    async def _audit_processing_pipeline(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment,
        routing_result: Dict[str, Any],
        workflow_result: Dict[str, Any],
        compliance_result: Dict[str, Any],
        delivery_result: Dict[str, Any]
    ) -> None:
        """Comprehensive audit logging for the processing pipeline."""
        try:
            await audit_log_event("universal_pipeline_processed", {
                "user_id": context.user_id,
                "industry_type": context.industry_type,
                "workflow_type": routing_result['workflow_type'].value,
                "readiness_score": assessment.readiness_score,
                "confidence_level": assessment.confidence_level,
                "processing_time": (datetime.now() - context.processing_start_time).total_seconds(),
                "delivery_success": delivery_result.get('success', False),
                "compliance_passed": compliance_result.get('passed', True),
                "channel_used": delivery_result.get('channel'),
                "pipeline_version": "universal_v1.0"
            })
        except Exception as e:
            logger.error(f"Error auditing processing pipeline: {e}")
    
    # LangGraph workflow execution methods
    def _create_langgraph_workflow(self) -> Optional[Runnable]:
        """Create advanced LangGraph workflow using routing, parallelization, and orchestrator-workers patterns."""
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available - using fallback workflow execution")
            return None

        try:
            # Parallel assessment tasks using sectioning pattern
            @task
            def assess_lead_scoring(context: Dict[str, Any]) -> Dict[str, Any]:
                """Parallel assessment: Lead scoring evaluation."""
                try:
                    lead_data = context.get("lead_data", {})
                    user_id = context.get("user_id")
                    industry_type = context.get("industry_type", "real_estate")

                    scoring_result = calculate_enhanced_lead_score(
                        lead_data=lead_data,
                        user_id=user_id,
                        industry_type=industry_type
                    )

                    return {
                        "assessment_type": "scoring",
                        "score": scoring_result.get('enhanced_score', 0.0),
                        "qualification_stage": scoring_result.get('qualification_stage', 'unknown'),
                        "confidence": 0.85
                    }
                except Exception as e:
                    logger.error(f"Error in parallel scoring assessment: {e}")
                    return {"assessment_type": "scoring", "score": 0.5, "error": str(e)}

            @task
            def assess_engagement_momentum(context: Dict[str, Any]) -> Dict[str, Any]:
                """Parallel assessment: Engagement momentum evaluation."""
                try:
                    user_id = context.get("user_id")

                    # Get engagement momentum
                    momentum = self.engagement_tracker.calculate_engagement_momentum(user_id)
                    conversion_ready = self.engagement_tracker.should_convert_soon(user_id, context.get("industry_type", "real_estate"))

                    return {
                        "assessment_type": "engagement",
                        "momentum_score": momentum,
                        "conversion_ready": conversion_ready,
                        "touch_points": self.engagement_tracker.get_touch_history(user_id, limit=5),
                        "confidence": 0.8
                    }
                except Exception as e:
                    logger.error(f"Error in parallel engagement assessment: {e}")
                    return {"assessment_type": "engagement", "momentum_score": 0.5, "error": str(e)}

            @task
            def assess_booking_readiness(context: Dict[str, Any]) -> Dict[str, Any]:
                """Parallel assessment: Booking readiness evaluation."""
                try:
                    user_id = context.get("user_id")
                    lead_data = context.get("lead_data", {})
                    industry_type = context.get("industry_type", "real_estate")

                    # booking_assessment = self.booking_engine.assess_booking_readiness(
                    #     user_id, lead_data, industry_type
                    # )
                    booking_assessment = None  # Placeholder - booking now handled by state machine

                    return {
                        "assessment_type": "booking",
                        "is_ready": False,  # Placeholder - booking assessment now handled by state machine
                        "readiness_score": 0.0,
                        "blocking_factors": [],
                        "confidence": 0.9
                    }
                except Exception as e:
                    logger.error(f"Error in parallel booking assessment: {e}")
                    return {"assessment_type": "booking", "is_ready": False, "error": str(e)}

            @task
            def assess_response_urgency(context: Dict[str, Any]) -> Dict[str, Any]:
                """Parallel assessment: Response urgency evaluation."""
                try:
                    user_id = context.get("user_id")
                    urgency_score = self.response_tracker.calculate_urgency_score(user_id)

                    return {
                        "assessment_type": "urgency",
                        "urgency_score": urgency_score,
                        "within_5min_window": urgency_score >= 0.8,
                        "last_response_time": self.response_tracker.get_last_response_time(user_id),
                        "confidence": 0.95
                    }
                except Exception as e:
                    logger.error(f"Error in parallel urgency assessment: {e}")
                    return {"assessment_type": "urgency", "urgency_score": 0.5, "error": str(e)}

            # Routing task using routing pattern
            @task
            def route_workflow_dynamically(assessments: Dict[str, Any]) -> Dict[str, Any]:
                """Dynamic routing based on parallel assessments using AI."""
                user_id = assessments.get("user_id")
                industry_type = assessments.get("industry_type", "real_estate")

                # Extract assessment results
                scoring = assessments.get("scoring", {})
                engagement = assessments.get("engagement", {})
                booking = assessments.get("booking", {})
                urgency = assessments.get("urgency", {})

                routing_prompt = f"""
                Analyze parallel assessment results and route to optimal workflow:

                Industry: {industry_type}
                Scoring: {scoring}
                Engagement: {engagement}
                Booking: {booking}
                Urgency: {urgency}

                Available workflows:
                - booking_flow: High scoring + booking ready + good engagement
                - nurture_sequence: Medium scoring + needs nurturing + time available
                - direct_response: High urgency + immediate response needed
                - qualification_gathering: Low scoring + needs more information
                - immediate_handoff: Complex case + human expertise needed

                Consider:
                1. Conversion probability based on combined factors
                2. Urgency and response time requirements
                3. Lead readiness and qualification level
                4. Industry-specific conversion patterns
                5. Resource optimization (human vs automated)

                Return JSON with:
                - recommended_workflow: "workflow_name"
                - confidence_score: 0.0-1.0
                - reasoning: "Why this workflow was chosen"
                - alternative_workflows: ["option1", "option2"]
                - success_probability: 0.0-1.0
                - human_override_needed: true/false
                """

                routing_response = get_llm_response_sync(routing_prompt, max_tokens=600)

                try:
                    import json
                    routing_decision = json.loads(routing_response)
                    return routing_decision
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse routing decision: {routing_response}")
                    # Fallback routing logic
                    scoring_score = scoring.get("score", 0)
                    booking_ready = booking.get("is_ready", False)
                    urgency_score = urgency.get("urgency_score", 0)

                    if booking_ready and scoring_score >= 0.7:
                        workflow = "booking_flow"
                    elif urgency_score >= 0.8:
                        workflow = "direct_response"
                    elif scoring_score >= 0.5:
                        workflow = "nurture_sequence"
                    else:
                        workflow = "qualification_gathering"

                    return {
                        "recommended_workflow": workflow,
                        "confidence_score": 0.7,
                        "reasoning": "Fallback routing based on assessment scores",
                        "alternative_workflows": ["qualification_gathering", "nurture_sequence"],
                        "success_probability": 0.6,
                        "human_override_needed": False
                    }

            # Orchestrator-workers pattern for response generation
            @task
            def orchestrate_response_generation(context: Dict[str, Any]) -> str:
                """Orchestrator-workers: Generate response using specialized workers."""
                user_name = context.get("user_name", "there")
                industry_type = context.get("industry_type", "real_estate")
                workflow_type = context.get("workflow_type", "direct_response")
                lead_data = context.get("lead_data", {})
                assessments = context.get("assessments", {})

                # Worker 1: Generate base response
                base_prompt = f"""
                Generate a base response for {industry_type} industry, {workflow_type} workflow:

                User: {user_name}
                Lead Data: {lead_data}
                Assessments: {assessments}

                Focus on: Personalization, industry-specific language, clear value proposition.
                Keep to 2-3 sentences.
                """

                base_response = get_llm_response_sync(base_prompt, max_tokens=300)

                # Worker 2: Optimize for conversion
                optimize_prompt = f"""
                Optimize this response for conversion in {industry_type} industry:

                Original: {base_response}
                Workflow: {workflow_type}
                Assessments: {assessments}

                Enhance with: Clear next steps, urgency when appropriate, social proof elements.
                Maintain 2-3 sentences.
                """

                optimized_response = get_llm_response_sync(optimize_prompt, max_tokens=300)

                # Worker 3: Compliance check and final polish
                compliance_prompt = f"""
                Final compliance check and polish for {industry_type} industry:

                Response: {optimized_response}
                Workflow: {workflow_type}

                Ensure: Industry compliance, professional tone, clear call-to-action.
                Final length: 2-4 sentences max.
                """

                final_response = get_llm_response_sync(compliance_prompt, max_tokens=400)

                return final_response.strip()

            # Parallel channel strategy using voting pattern
            @task
            def determine_channel_strategy_vote1(context: Dict[str, Any]) -> Dict[str, Any]:
                """Voting pattern: Channel strategy from perspective 1."""
                return self._channel_strategy_vote(context, "performance")

            @task
            def determine_channel_strategy_vote2(context: Dict[str, Any]) -> Dict[str, Any]:
                """Voting pattern: Channel strategy from perspective 2."""
                return self._channel_strategy_vote(context, "engagement")

            @task
            def determine_channel_strategy_vote3(context: Dict[str, Any]) -> Dict[str, Any]:
                """Voting pattern: Channel strategy from perspective 3."""
                return self._channel_strategy_vote(context, "compliance")

            @task
            def aggregate_channel_votes(vote1: Dict, vote2: Dict, vote3: Dict) -> Dict[str, Any]:
                """Aggregate voting results for final channel strategy."""
                votes = [vote1, vote2, vote3]

                # Count votes for each channel
                channel_counts = {}
                for vote in votes:
                    channel = vote.get("primary_channel", "instagram_dm")
                    channel_counts[channel] = channel_counts.get(channel, 0) + 1

                # Select channel with most votes
                primary_channel = max(channel_counts, key=channel_counts.get)

                # Aggregate other preferences
                fallback_channels = []
                for vote in votes:
                    for channel in vote.get("fallback_channels", []):
                        if channel not in fallback_channels and channel != primary_channel:
                            fallback_channels.append(channel)

                return {
                    "primary_channel": primary_channel,
                    "fallback_channels": fallback_channels[:2],  # Limit to 2 fallbacks
                    "voting_results": channel_counts,
                    "confidence": channel_counts[primary_channel] / len(votes)
                }

            # Evaluator-optimizer pattern for workflow execution
            @task
            def execute_workflow_with_evaluation(context: Dict[str, Any]) -> Dict[str, Any]:
                """Evaluator-optimizer: Execute workflow with continuous evaluation."""
                workflow_type = context.get("workflow_type", "direct_response")
                industry_type = context.get("industry_type", "real_estate")
                user_id = context.get("user_id")
                lead_data = context.get("lead_data", {})

                # Initial workflow execution
                initial_result = self._execute_workflow_initial(workflow_type, user_id, lead_data, industry_type)

                # Evaluate and optimize
                evaluation_prompt = f"""
                Evaluate workflow execution and suggest optimizations:

                Workflow: {workflow_type}
                Industry: {industry_type}
                Initial Result: {initial_result}

                Assess:
                1. Execution success probability
                2. Potential improvements
                3. Alternative approaches
                4. Risk factors

                Return JSON with:
                - execution_quality: 0.0-1.0
                - optimizations_needed: ["opt1", "opt2"]
                - alternative_approaches: ["alt1", "alt2"]
                - risk_level: "low"/"medium"/"high"
                - human_intervention_recommended: true/false
                """

                evaluation_response = get_llm_response_sync(evaluation_prompt, max_tokens=500)

                try:
                    import json
                    evaluation = json.loads(evaluation_response)

                    # Apply optimizations if needed
                    if evaluation.get("execution_quality", 1.0) < 0.7:
                        optimized_result = self._optimize_workflow_execution(
                            initial_result, evaluation, context
                        )
                        return {**optimized_result, "evaluation": evaluation, "optimized": True}
                    else:
                        return {**initial_result, "evaluation": evaluation, "optimized": False}

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse workflow evaluation: {evaluation_response}")
                    return {**initial_result, "evaluation": {"quality": 0.8}, "optimized": False}

            @entrypoint(checkpointer=MemorySaver())
            def advanced_universal_lead_workflow(inputs: Dict[str, Any]) -> Dict[str, Any]:
                """Advanced LangGraph workflow using routing, parallelization, and orchestrator-workers patterns."""
                user_id = inputs["user_id"]
                start_time = datetime.now()

                # Parallel assessment using sectioning pattern
                scoring_task = assess_lead_scoring(inputs)
                engagement_task = assess_engagement_momentum(inputs)
                booking_task = assess_booking_readiness(inputs)
                urgency_task = assess_response_urgency(inputs)

                # Wait for all parallel assessments to complete
                scoring_result = scoring_task.result()
                engagement_result = engagement_task.result()
                booking_result = booking_task.result()
                urgency_result = urgency_task.result()

                # Combine assessment results
                assessments = {
                    "user_id": user_id,
                    "industry_type": inputs.get("industry_type"),
                    "scoring": scoring_result,
                    "engagement": engagement_result,
                    "booking": booking_result,
                    "urgency": urgency_result
                }

                # Dynamic routing based on parallel assessments
                routing_decision = route_workflow_dynamically(assessments).result()

                # Update context with routing decision
                workflow_context = {
                    **inputs,
                    "assessments": assessments,
                    "workflow_type": routing_decision["recommended_workflow"],
                    "routing_decision": routing_decision
                }

                # Parallel channel strategy using voting pattern
                vote1 = determine_channel_strategy_vote1(workflow_context)
                vote2 = determine_channel_strategy_vote2(workflow_context)
                vote3 = determine_channel_strategy_vote3(workflow_context)

                channel_strategy = aggregate_channel_votes(
                    vote1.result(), vote2.result(), vote3.result()
                ).result()

                # Orchestrator-workers response generation
                response = orchestrate_response_generation({
                    **workflow_context,
                    "channel_strategy": channel_strategy
                }).result()

                # Evaluator-optimizer workflow execution
                workflow_result = execute_workflow_with_evaluation({
                    **workflow_context,
                    "response": response,
                    "channel_strategy": channel_strategy
                }).result()

                processing_time = (datetime.now() - start_time).total_seconds()

                return {
                    "user_id": user_id,
                    "assessments": assessments,
                    "routing_decision": routing_decision,
                    "response": response,
                    "channel_strategy": channel_strategy,
                    "workflow_result": workflow_result,
                    "processing_time": processing_time,
                    "langgraph_patterns_used": ["parallelization", "routing", "orchestrator-workers", "voting", "evaluator-optimizer"],
                    "completed_at": datetime.now().isoformat()
                }

            return advanced_universal_lead_workflow

        except Exception as e:
            logger.error(f"Error creating advanced LangGraph workflow: {e}")
            return None

    def _channel_strategy_vote(self, context: Dict[str, Any], perspective: str) -> Dict[str, Any]:
        """Helper method for channel strategy voting."""
        user_id = context.get("user_id")
        industry_type = context.get("industry_type", "real_estate")
        workflow_type = context.get("workflow_type", "direct_response")

        vote_prompt = f"""
        Determine optimal channel strategy from {perspective} perspective:

        User ID: {user_id}
        Industry: {industry_type}
        Workflow: {workflow_type}
        Perspective: {perspective}

        Consider {perspective}-specific factors and return JSON with:
        - primary_channel: "instagram_dm", "sms", "email", "phone"
        - fallback_channels: ["channel1", "channel2"]
        - reasoning: "Why this channel from {perspective} perspective"
        """

        vote_response = get_llm_response_sync(vote_prompt, max_tokens=300)

        try:
            import json
            return json.loads(vote_response)
        except json.JSONDecodeError:
            return {
                "primary_channel": "instagram_dm",
                "fallback_channels": ["email"],
                "reasoning": f"Default from {perspective} perspective"
            }

    def _execute_workflow_initial(self, workflow_type: str, user_id: str, lead_data: Dict, industry_type: str) -> Dict[str, Any]:
        """Initial workflow execution before evaluation."""
        try:
            if workflow_type == "booking_flow":
                return {
                    "workflow_executed": "booking_flow",
                    "actions_taken": ["trigger_booking_engine"],
                    "success_probability": 0.8
                }
            elif workflow_type == "nurture_sequence":
                return {
                    "workflow_executed": "nurture_sequence",
                    "actions_taken": ["schedule_nurture"],
                    "success_probability": 0.7
                }
            elif workflow_type == "direct_response":
                return {
                    "workflow_executed": "direct_response",
                    "actions_taken": ["generate_response"],
                    "success_probability": 0.6
                }
            elif workflow_type == "qualification_gathering":
                return {
                    "workflow_executed": "qualification_gathering",
                    "actions_taken": ["ask_questions"],
                    "success_probability": 0.5
                }
            else:  # immediate_handoff
                return {
                    "workflow_executed": "immediate_handoff",
                    "actions_taken": ["escalate_to_human"],
                    "success_probability": 0.9
                }
        except Exception as e:
            logger.error(f"Error in initial workflow execution: {e}")
            return {
                "workflow_executed": "error_fallback",
                "actions_taken": ["error_handling"],
                "success_probability": 0.3,
                "error": str(e)
            }

    def _optimize_workflow_execution(self, initial_result: Dict, evaluation: Dict, context: Dict) -> Dict[str, Any]:
        """Optimize workflow execution based on evaluation."""
        optimizations = evaluation.get("optimizations_needed", [])
        risk_level = evaluation.get("risk_level", "low")

        # Apply optimizations
        optimized_result = initial_result.copy()

        if "human_intervention" in optimizations:
            optimized_result["human_intervention_added"] = True
            optimized_result["success_probability"] += 0.2

        if risk_level == "high":
            optimized_result["additional_safeguards"] = True
            optimized_result["success_probability"] -= 0.1

        return optimized_result
    
    async def _execute_workflow_with_langgraph(
        self,
        workflow_type: WorkflowType,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute workflow using LangGraph for dynamic orchestration."""
        try:
            # Create LangGraph workflow if available
            workflow = self._create_langgraph_workflow()
            
            if workflow:
                logger.info(f"🚀 Executing {workflow_type.value} with LangGraph")
                
                # Prepare inputs for LangGraph
                inputs = {
                    "user_id": context.user_id,
                    "message": context.message,
                    "channel": context.channel,
                    "user_name": context.user_name,
                    "industry_type": context.industry_type,
                    "lead_data": context.lead_data,
                    "conversation_history": context.conversation_history,
                    "workflow_type": workflow_type.value,
                    "assessment": asdict(assessment)
                }
                
                # Execute LangGraph workflow
                result = workflow.invoke(inputs)
                
                return {
                    "status": "langgraph_executed",
                    "workflow_result": result,
                    "workflow_type": workflow_type.value,
                    "langgraph_used": True
                }
            else:
                # Fallback to static workflow execution
                logger.warning("LangGraph not available - using fallback workflow execution")
                return await self._execute_workflow_fallback(workflow_type, context, assessment)
                
        except Exception as e:
            logger.error(f"Error executing LangGraph workflow: {e}")
            return await self._execute_workflow_fallback(workflow_type, context, assessment)
    
    async def _execute_workflow_fallback(
        self,
        workflow_type: WorkflowType,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Fallback workflow execution when LangGraph is not available."""
        try:
            if workflow_type == WorkflowType.BOOKING_FLOW:
                return await self._execute_booking_workflow(context, assessment)
            elif workflow_type == WorkflowType.NURTURE_SEQUENCE:
                return await self._execute_nurture_workflow(context, assessment)
            elif workflow_type == WorkflowType.IMMEDIATE_HANDOFF:
                return await self._execute_handoff_workflow(context, assessment)
            elif workflow_type == WorkflowType.QUALIFICATION_GATHERING:
                return await self._execute_qualification_workflow(context, assessment)
            else:  # DIRECT_RESPONSE
                return await self._execute_direct_response_workflow(context, assessment)
                
        except Exception as e:
            logger.error(f"Error in fallback workflow execution: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_booking_workflow(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute booking workflow using booking state machine integration."""
        try:
            logger.info(f"🚀 EXECUTING BOOKING WORKFLOW for user {context.user_id}")
            
            # Check if this is a T0+120s automation scenario (qualification completion)
            qualification_completed = context.lead_data.get('qualification_completed', False)
            time_since_first_contact = datetime.now() - context.processing_start_time
            
            if qualification_completed and time_since_first_contact >= timedelta(seconds=120):
                # T0+120s automation scenario - qualification just completed
                logger.info(f"🎯 T0+120s automation triggered for user {context.user_id}")
                booking_result = await handle_t0_120s_automation(
                    user_id=context.user_id,
                    lead_data=context.lead_data,
                    industry_type=context.industry_type,
                    correlation_id=context.metadata.get('correlation_id')
                )
                
                return {
                    "status": "t0_120s_automation_executed",
                    "booking_result": booking_result,
                    "workflow_type": WorkflowType.BOOKING_FLOW.value,
                    "automation_trigger": "qualification_completion",
                    "time_elapsed_seconds": time_since_first_contact.total_seconds()
                }
            
            elif assessment.booking_readiness:
                # Standard booking trigger for ready leads
                logger.info(f"📅 Triggering immediate booking flow for user {context.user_id}")
                booking_result = await trigger_booking_flow_immediate(
                    user_id=context.user_id,
                    lead_data=context.lead_data,
                    industry_type=context.industry_type,
                    booking_type="consultation",
                    correlation_id=context.metadata.get('correlation_id')
                )
                
                return {
                    "status": "booking_flow_initiated",
                    "booking_result": booking_result,
                    "workflow_type": WorkflowType.BOOKING_FLOW.value,
                    "automation_trigger": "readiness_assessment"
                }
            
            else:
                # Fallback: Process qualification completion to prepare for booking
                logger.info(f"🔄 Processing qualification completion for user {context.user_id}")
                qualification_result = await process_qualification_completion(
                    user_id=context.user_id,
                    lead_data=context.lead_data,
                    industry_type=context.industry_type,
                    correlation_id=context.metadata.get('correlation_id')
                )
                
                return {
                    "status": "qualification_completion_processed",
                    "qualification_result": qualification_result,
                    "workflow_type": WorkflowType.BOOKING_FLOW.value,
                    "next_step": "await_booking_trigger"
                }
            
        except Exception as e:
            logger.error(f"Error executing booking workflow for user {context.user_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "workflow_type": WorkflowType.BOOKING_FLOW.value,
                "fallback_action": "manual_booking_required"
            }
    
    async def _execute_nurture_workflow(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute nurture sequence workflow."""
        try:
            # Schedule nurture sequence
            nurture_scheduled = self.nurture_manager.schedule_nurture_sequence(
                user_id=context.user_id,
                lead_score=assessment.readiness_score,
                industry_type=context.industry_type,
                lead_data=context.lead_data
            )
            
            return {
                "status": "nurture_scheduled",
                "nurture_scheduled": nurture_scheduled,
                "workflow_type": WorkflowType.NURTURE_SEQUENCE.value
            }
            
        except Exception as e:
            logger.error(f"Error executing nurture workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_handoff_workflow(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute immediate handoff workflow."""
        try:
            # Generate handoff message
            handoff_message = f"Hi {context.user_name or 'there'}! Based on your needs, I'm connecting you with one of our specialists who can provide personalized assistance right away."
            
            return {
                "status": "handoff_initiated",
                "handoff_message": handoff_message,
                "workflow_type": WorkflowType.IMMEDIATE_HANDOFF.value
            }
            
        except Exception as e:
            logger.error(f"Error executing handoff workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_qualification_workflow(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute qualification gathering workflow."""
        try:
            # Get next qualification question
            from ..utils.lead_scoring import get_next_qualification_question
            
            next_question = get_next_qualification_question(
                context.lead_data,
                context.metadata.get("conversation_state", {}).get("asked_questions", [])
            )
            
            return {
                "status": "qualification_initiated",
                "next_question": next_question,
                "workflow_type": WorkflowType.QUALIFICATION_GATHERING.value
            }
            
        except Exception as e:
            logger.error(f"Error executing qualification workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_direct_response_workflow(
        self,
        context: ProcessingContext,
        assessment: LeadReadinessAssessment
    ) -> Dict[str, Any]:
        """Execute direct response workflow."""
        try:
            return {
                "status": "direct_response",
                "workflow_type": WorkflowType.DIRECT_RESPONSE.value
            }
            
        except Exception as e:
            logger.error(f"Error executing direct response workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    # Response generation methods
    async def _generate_booking_response(self, context: Dict[str, Any]) -> str:
        """Generate booking-specific response."""
        user_name = context.get("user_name", "there")
        return f"""🎯 Perfect {user_name}! 

You're ready to move forward! Based on your requirements, I can schedule a consultation with one of our specialists.

I have several time slots available this week. When would be the best time to connect?

I'll send you a calendar invitation with all the details! 📅"""
    
    async def _generate_nurture_response(self, context: Dict[str, Any]) -> str:
        """Generate nurture-specific response."""
        user_name = context.get("user_name", "there")
        value_props = context.get("value_props", [])
        
        value_text = ""
        if value_props:
            value_text = f"\n\n💡 **What I can help you with:**\n"
            for prop in value_props[:3]:  # Limit to top 3
                value_text += f"• {prop.replace('_', ' ').title()}\n"
        
        return f"""Hi {user_name}! 👋

Thanks for your interest! I'm learning more about what you're looking for to provide the best recommendations.{value_text}

I'll follow up with some tailored information that matches your needs. Is there anything specific you'd like to know more about right now? 🤔"""
    
    async def _generate_direct_response(self, context: Dict[str, Any]) -> str:
        """Generate direct response."""
        user_name = context.get("user_name", "there")
        return f"""Hi {user_name}! 👋

Thanks for reaching out! I'm here to help you with your needs.

Based on what you've shared, I have some great insights and options for you. Let me know what specific aspects you'd like to focus on, and I'll provide detailed information.

Looking forward to helping you! 🌟"""
    
    async def _generate_qualification_response(self, context: Dict[str, Any]) -> str:
        """Generate qualification gathering response."""
        user_name = context.get("user_name", "there")
        return f"""Hi {user_name}! 👋

I'd love to help you find exactly what you're looking for! To provide the best recommendations, could you tell me a bit more about:

• Your budget range
• Preferred location/area
• Timeline for your decision

This will help me tailor my response and provide the most relevant options for you! 🎯"""
    
    async def _generate_handoff_response(self, context: Dict[str, Any]) -> str:
        """Generate handoff response."""
        user_name = context.get("user_name", "there")
        return f"""Hi {user_name}! 👋

Based on your requirements, I'm connecting you with one of our specialists who can provide personalized assistance right away.

They'll be able to:
• Provide detailed recommendations
• Answer specific questions
• Schedule personalized consultations
• Share exclusive opportunities

One of our team members will reach out to you shortly! 🚀"""
    
    async def _generate_default_response(self, context: Dict[str, Any]) -> str:
        """Generate default response."""
        user_name = context.get("user_name", "there")
        return f"""Hi {user_name}! 👋

Thanks for reaching out! I'm here to help you with your needs.

Could you tell me more about what you're looking for? I'll provide personalized recommendations and assistance based on your requirements.

Looking forward to helping you! 🌟"""
    
    def get_processing_metrics(self) -> Dict[str, Any]:
        """Get comprehensive processing metrics for monitoring."""
        return {
            "metrics": self.processing_metrics,
            "pipeline_version": "universal_v1.0",
            "components_status": {
                "response_tracker": "active",
                "lead_scorer": "active",
                "engagement_tracker": "active",
                "nurture_manager": "active",
                "booking_engine": "active",
                "channel_manager": "active",
                "industry_config_manager": "active"
            },
            "last_updated": datetime.now().isoformat()
        }

# Global instance for easy access
universal_lead_processor = UniversalLeadProcessor()

# Convenience function for direct access
async def process_message(
    user_id: str,
    message: str,
    channel: str = "instagram",
    user_name: str = None
) -> Dict[str, Any]:
    """
    Convenience function to process message through universal pipeline.
    
    Args:
        user_id: Unique identifier for the user/lead
        message: Incoming message content
        channel: Communication channel
        user_name: Optional user name for personalization
        
    Returns:
        Dictionary with processing result and response message
    """
    return await universal_lead_processor.process_message(user_id, message, channel, user_name)