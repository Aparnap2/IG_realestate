"""
Progressive Nurture System - Automated Follow-up Sequences using LangGraph

Implements industry-specific automated follow-up sequences with dynamic scheduling,
multi-channel communication, template-based messaging, and LangGraph orchestration.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

# LangGraph imports for workflow orchestration
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

# Local imports
from utils.redis_client import redis_client, redis_circuit_breaker
from utils.engagement_tracker import engagement_tracker
from utils.llm_client import get_llm_response_sync, get_structured_llm_response
from utils.audit import audit_log_event
from .nurture_config import nurture_config_loader, SequenceConfig, TemplateConfig, TouchPointConfig

logger = logging.getLogger(__name__)

class ChannelType(Enum):
    """Communication channels for nurture sequences"""
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"
    CALL = "call"

class IndustryType(Enum):
    """Supported industry types for nurture sequences"""
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    DEFAULT = "default"

@dataclass
class TouchPoint:
    """Represents a single touch point in nurture sequence"""
    day: int
    channel: ChannelType
    template_key: str
    content: Optional[str] = None
    personalization_data: Optional[Dict[str, Any]] = None
    compliance_checked: bool = False

@dataclass
class NurtureSequence:
    """Industry-specific nurture sequence configuration"""
    industry_type: IndustryType
    intent_threshold: float
    touch_points: List[TouchPoint]
    total_duration_days: int
    ab_test_enabled: bool = False

class NurtureSequenceManager:
    """
    Progressive Nurture System using LangGraph for automated follow-up sequences.
    
    Features:
    - Industry-specific sequences with different cadences
    - Automated scheduling based on qualification score
    - Multi-channel communication (SMS, email, in-app)
    - Template-based messaging with personalization
    - Integration with engagement tracker for triggering
    - LangGraph orchestration for dynamic workflows
    """
    
    def __init__(self):
        self.redis_client = redis_client
        self.circuit_breaker = redis_circuit_breaker
        self.checkpointer = MemorySaver() if LANGGRAPH_AVAILABLE else None
        
        # Redis key patterns
        self.SEQUENCE_KEY = "nurture:sequence:{user_id}"
        self.SCHEDULE_KEY = "nurture:schedule:{user_id}"
        self.PROGRESS_KEY = "nurture:progress:{user_id}"
        self.TEMPLATES_KEY = "nurture:templates:{industry}"
        
        # TTL settings (in seconds)
        self.SEQUENCE_TTL = 7776000  # 90 days
        self.SCHEDULE_TTL = 7776000  # 90 days
        self.PROGRESS_TTL = 7776000  # 90 days
        
        # Load dynamic configurations
        self._load_dynamic_configurations()
    
    def _load_dynamic_configurations(self):
        """Load sequences and templates from dynamic configuration"""
        # Load from configuration loader
        self.sequences = {}
        self.templates = {}
        
        # Convert config objects to internal data structures
        for industry_key, industry_data in nurture_config_loader.sequences.items():
            try:
                industry_enum = IndustryType(industry_key)
                self.sequences[industry_enum] = {}
            except ValueError:
                # Skip invalid industry types
                logger.warning(f"Skipping invalid industry type: {industry_key}")
                continue
                
            for intent_key, sequence_config in industry_data.items():
                # Convert TouchPointConfig to TouchPoint
                touch_points = [
                    TouchPoint(
                        day=tp.day,
                        channel=ChannelType(tp.channel),
                        template_key=tp.template_key,
                        content=tp.content,
                        personalization_data=tp.personalization_data,
                        compliance_checked=tp.compliance_checked
                    )
                    for tp in sequence_config.touch_points
                ]
                
                # Create NurtureSequence
                self.sequences[IndustryType(industry_key)][intent_key] = NurtureSequence(
                    industry_type=IndustryType(industry_key),
                    intent_threshold=sequence_config.intent_threshold,
                    touch_points=touch_points,
                    total_duration_days=sequence_config.total_duration_days,
                    ab_test_enabled=sequence_config.ab_test_enabled
                )
        
        # Convert template configs to internal format
        for industry_key, industry_data in nurture_config_loader.templates.items():
            try:
                industry_enum = IndustryType(industry_key)
                self.templates[industry_enum] = {}
            except ValueError:
                # Skip invalid industry types
                logger.warning(f"Skipping invalid industry type for templates: {industry_key}")
                continue
                
            for template_key, template_config in industry_data.items():
                self.templates[IndustryType(industry_key)][template_key] = {
                    "template": template_config.template,
                    "personalization_fields": template_config.personalization_fields,
                    "compliance_required": template_config.compliance_required,
                    "channel_specific": template_config.channel_specific,
                    "a_b_test_variants": template_config.a_b_test_variants
                }
        
        logger.info(f"Loaded dynamic configurations for {len(self.sequences)} industries")
    
    def schedule_nurture_sequence(self, user_id: str, lead_score: float, 
                                industry_type: str, lead_data: Dict[str, Any]) -> bool:
        """
        Schedule automated nurture sequence using LangGraph workflow.
        
        Args:
            user_id: Unique user identifier
            lead_score: Qualification score (0-1)
            industry_type: Industry type for sequence selection
            lead_data: Lead information for personalization
            
        Returns:
            True if successfully scheduled, False otherwise
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available - using fallback scheduling")
            return self._fallback_schedule_sequence(user_id, lead_score, industry_type, lead_data)
        
        try:
            # Determine industry type and intent level
            industry_enum = IndustryType(industry_type.lower())
            intent_level = "high_intent" if lead_score >= self._get_intent_threshold(industry_enum) else "low_intent"
            
            # Get appropriate sequence
            if industry_enum not in self.sequences or intent_level not in self.sequences[industry_enum]:
                logger.error(f"No sequence found for industry {industry_type} with intent level {intent_level}")
                return False
            
            sequence = self.sequences[industry_enum][intent_level]
            
            # Create LangGraph workflow for this sequence
            workflow = self._create_sequence_workflow(sequence, lead_data)
            
            # Store sequence in Redis
            sequence_data = {
                "user_id": user_id,
                "industry_type": industry_type,
                "lead_score": lead_score,
                "intent_level": intent_level,
                "sequence": asdict(sequence),
                "lead_data": lead_data,
                "scheduled_at": datetime.utcnow().isoformat(),
                "status": "active",
                "current_touch": 0,
                "completed_touches": []
            }
            
            def _store_sequence():
                sequence_key = self.SEQUENCE_KEY.format(user_id=user_id)
                self.redis_client.setex(sequence_key, self.SEQUENCE_TTL, json.dumps(sequence_data, default=str))
                
                # Store initial schedule
                schedule_key = self.SCHEDULE_KEY.format(user_id=user_id)
                schedule_data = self._generate_initial_schedule(sequence, lead_data)
                self.redis_client.setex(schedule_key, self.SCHEDULE_TTL, json.dumps(schedule_data, default=str))
                
                logger.info(f"Scheduled {intent_level} nurture sequence for user {user_id} in {industry_type}")
                return True
            
            try:
                return self.circuit_breaker.call(_store_sequence)
            except Exception as e:
                logger.error(f"Failed to schedule nurture sequence for user {user_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error scheduling nurture sequence for user {user_id}: {e}")
            return False
    
    def _create_sequence_workflow(self, sequence: NurtureSequence, lead_data: Dict[str, Any]) -> Optional[Runnable]:
        """
        Create LangGraph workflow for nurture sequence execution.
        
        Args:
            sequence: Nurture sequence configuration
            lead_data: Lead information for personalization
            
        Returns:
            LangGraph workflow or None if LangGraph unavailable
        """
        if not LANGGRAPH_AVAILABLE:
            return None
        
        try:
            @task
            def generate_personalized_content(touch_point: TouchPoint, context: Dict[str, Any]) -> str:
                """Generate personalized content for touch point"""
                template = self.templates[sequence.industry_type][touch_point.template_key]
                personalization = {k: lead_data.get(k, f"{{{k}}}") for k in template["personalization_fields"]}
                
                # Use LLM for dynamic content generation
                prompt = f"""
                Generate personalized {touch_point.channel.value} content for {sequence.industry_type.value} nurture sequence.
                
                Template: {template['template']}
                Personalization data: {personalization}
                
                Requirements:
                - Make it sound natural and personalized
                - Include relevant details from personalization data
                - Keep it concise and engaging
                - Follow compliance guidelines
                - Channel: {touch_point.channel.value}
                
                Return only the message content, no explanations.
                """
                
                content = get_llm_response_sync(prompt, max_tokens=500)
                
                # Record touch point with engagement tracker
                engagement_tracker.record_touch_point(
                    user_id=context["user_id"],
                    touch_type=touch_point.channel.value,
                    content=content,
                    metadata={
                        "sequence_id": context.get("sequence_id"),
                        "touch_day": touch_point.day,
                        "template_key": touch_point.template_key,
                        "industry_type": sequence.industry_type.value,
                        "personalization_used": personalization
                    }
                )
                
                return content
            
            @task
            def schedule_next_touch(touch_point: TouchPoint, context: Dict[str, Any]) -> Dict[str, Any]:
                """Schedule next touch point in sequence"""
                scheduled_date = datetime.utcnow() + timedelta(days=touch_point.day)
                
                return {
                    "action": "schedule_touch",
                    "touch_point": asdict(touch_point),
                    "scheduled_for": scheduled_date.isoformat(),
                    "content": generate_personalized_content(touch_point, context).result()
                }
            
            @task
            def wait_for_response(touch_point: TouchPoint, context: Dict[str, Any]) -> Dict[str, Any]:
                """Wait for user response before proceeding"""
                # Check if user has responded to previous touch
                user_id = context["user_id"]
                has_responded = engagement_tracker.get_touch_count(user_id, days=touch_point.day) > 0
                
                if has_responded:
                    return {
                        "action": "response_received",
                        "touch_point": asdict(touch_point),
                        "proceed_to_next": True
                    }
                else:
                    # Interrupt for human-in-the-loop if needed
                    if touch_point.channel == ChannelType.CALL:
                        return interrupt({
                            "action": "schedule_call",
                            "touch_point": asdict(touch_point),
                            "user_id": user_id,
                            "instructions": f"Call user for {touch_point.template_key}"
                        })
                    else:
                        return {
                            "action": "wait_for_response",
                            "touch_point": asdict(touch_point),
                            "wait_days": 2  # Wait 2 more days
                        }
            
            @entrypoint(checkpointer=self.checkpointer)
            def nurture_workflow(inputs: Dict[str, Any]) -> Dict[str, Any]:
                """Main nurture sequence workflow"""
                user_id = inputs["user_id"]
                sequence_id = inputs["sequence_id"]
                
                context = {
                    "user_id": user_id,
                    "sequence_id": sequence_id,
                    "lead_data": inputs["lead_data"],
                    "current_touch": 0
                }
                
                results = []
                
                for touch_point in sequence.touch_points:
                    context["current_touch"] += 1
                    
                    # Schedule the touch
                    schedule_result = schedule_next_touch(touch_point, context).result()
                    results.append(schedule_result)
                    
                    # Wait for response if needed
                    wait_result = wait_for_response(touch_point, context).result()
                    results.append(wait_result)
                    
                    # Update progress
                    self._update_sequence_progress(user_id, touch_point.day, wait_result)
                    
                    # Check if we should continue
                    if not wait_result.get("proceed_to_next", True):
                        break
                
                return {
                    "sequence_id": sequence_id,
                    "user_id": user_id,
                    "results": results,
                    "completed_at": datetime.utcnow().isoformat()
                }
            
            return nurture_workflow
            
        except Exception as e:
            logger.error(f"Error creating LangGraph workflow: {e}")
            return None
    
    def get_next_touch_point(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get next scheduled touch point for a user.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Next touch point data or None if no scheduled touches
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot get next touch point")
            return None
        
        def _get_next_touch():
            schedule_key = self.SCHEDULE_KEY.format(user_id=user_id)
            schedule_data = self.redis_client.get(schedule_key)
            
            if not schedule_data:
                return None
            
            schedule = json.loads(schedule_data)
            upcoming_touches = [
                touch for touch in schedule.get("upcoming_touches", [])
                if datetime.fromisoformat(touch["scheduled_for"]) <= datetime.utcnow()
            ]
            
            if not upcoming_touches:
                return None
            
            # Return the next touch point
            next_touch = upcoming_touches[0]
            next_touch["retrieved_at"] = datetime.utcnow().isoformat()
            
            return next_touch
        
        try:
            return self.circuit_breaker.call(_get_next_touch)
        except Exception as e:
            logger.error(f"Failed to get next touch point for user {user_id}: {e}")
            return None
    
    def cancel_nurture_sequence(self, user_id: str) -> bool:
        """
        Cancel active nurture sequence for a user.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            True if successfully cancelled, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot cancel nurture sequence")
            return False
        
        def _cancel_sequence():
            # Mark sequence as cancelled
            sequence_key = self.SEQUENCE_KEY.format(user_id=user_id)
            sequence_data = self.redis_client.get(sequence_key)
            
            if sequence_data:
                sequence = json.loads(sequence_data)
                sequence["status"] = "cancelled"
                sequence["cancelled_at"] = datetime.utcnow().isoformat()
                self.redis_client.setex(sequence_key, self.SEQUENCE_TTL, json.dumps(sequence, default=str))
            
            # Clear schedule
            schedule_key = self.SCHEDULE_KEY.format(user_id=user_id)
            self.redis_client.delete(schedule_key)
            
            logger.info(f"Cancelled nurture sequence for user {user_id}")
            return True
        
        try:
            return self.circuit_breaker.call(_cancel_sequence)
        except Exception as e:
            logger.error(f"Failed to cancel nurture sequence for user {user_id}: {e}")
            return False
    
    def update_sequence_progress(self, user_id: str, touch_completed: bool) -> bool:
        """
        Update sequence progress after touch point completion.
        
        Args:
            user_id: Unique user identifier
            touch_completed: Whether the touch was completed successfully
            
        Returns:
            True if successfully updated, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot update sequence progress")
            return False
        
        def _update_progress():
            progress_key = self.PROGRESS_KEY.format(user_id=user_id)
            progress_data = self.redis_client.get(progress_key)
            
            if progress_data:
                progress = json.loads(progress_data)
            else:
                progress = {
                    "user_id": user_id,
                    "completed_touches": [],
                    "last_updated": datetime.utcnow().isoformat()
                }
            
            if touch_completed:
                progress["completed_touches"].append(datetime.utcnow().isoformat())
            
            progress["last_updated"] = datetime.utcnow().isoformat()
            self.redis_client.setex(progress_key, self.PROGRESS_TTL, json.dumps(progress, default=str))
            
            logger.info(f"Updated sequence progress for user {user_id}: {touch_completed}")
            return True
        
        try:
            return self.circuit_breaker.call(_update_progress)
        except Exception as e:
            logger.error(f"Failed to update sequence progress for user {user_id}: {e}")
            return False
    
    def _get_intent_threshold(self, industry_type: IndustryType) -> float:
        """Get intent threshold for industry type"""
        if industry_type in self.sequences:
            # Use high_intent threshold as default
            high_intent_sequence = self.sequences[industry_type].get("high_intent")
            if high_intent_sequence:
                return high_intent_sequence.intent_threshold
        
        # Default thresholds
        return {
            IndustryType.REAL_ESTATE: 0.6,
            IndustryType.FITNESS: 0.5,
            IndustryType.RESTAURANT: 0.55,
            IndustryType.HOTEL: 0.7
        }.get(industry_type, 0.5)
    
    def _generate_initial_schedule(self, sequence: NurtureSequence, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate initial schedule for sequence"""
        upcoming_touches = []
        
        for touch_point in sequence.touch_points:
            scheduled_date = datetime.utcnow() + timedelta(days=touch_point.day)
            
            upcoming_touches.append({
                "day": touch_point.day,
                "channel": touch_point.channel.value,
                "template_key": touch_point.template_key,
                "scheduled_for": scheduled_date.isoformat(),
                "status": "scheduled",
                "content": None  # Will be generated at execution time
            })
        
        return {
            "sequence_id": f"{sequence.industry_type.value}_{datetime.utcnow().timestamp()}",
            "upcoming_touches": upcoming_touches,
            "total_touches": len(sequence.touch_points),
            "created_at": datetime.utcnow().isoformat()
        }
    
    def _update_sequence_progress(self, user_id: str, touch_day: int, result: Dict[str, Any]) -> bool:
        """Internal method to update sequence progress"""
        if self.redis_client is None:
            return False
        
        def _update():
            schedule_key = self.SCHEDULE_KEY.format(user_id=user_id)
            schedule_data = self.redis_client.get(schedule_key)
            
            if schedule_data:
                schedule = json.loads(schedule_data)
                
                # Update touch status
                for touch in schedule.get("upcoming_touches", []):
                    if touch["day"] == touch_day:
                        touch["status"] = "completed"
                        touch["completed_at"] = datetime.utcnow().isoformat()
                        touch["result"] = result
                        break
                
                self.redis_client.setex(schedule_key, self.SCHEDULE_TTL, json.dumps(schedule, default=str))
            
            return True
        
        try:
            return self.circuit_breaker.call(_update)
        except Exception as e:
            logger.error(f"Failed to update sequence progress: {e}")
            return False
    
    def _fallback_schedule_sequence(self, user_id: str, lead_score: float, 
                               industry_type: str, lead_data: Dict[str, Any]) -> bool:
        """Fallback scheduling method when LangGraph is unavailable"""
        try:
            # Simple Redis-based scheduling
            industry_enum = IndustryType(industry_type.lower())
            intent_level = "high_intent" if lead_score >= self._get_intent_threshold(industry_enum) else "low_intent"
            
            if industry_enum not in self.sequences or intent_level not in self.sequences[industry_enum]:
                return False
            
            sequence = self.sequences[industry_enum][intent_level]
            
            # Store basic sequence info
            sequence_data = {
                "user_id": user_id,
                "industry_type": industry_type,
                "lead_score": lead_score,
                "intent_level": intent_level,
                "sequence": asdict(sequence),
                "lead_data": lead_data,
                "scheduled_at": datetime.utcnow().isoformat(),
                "status": "active_fallback",
                "current_touch": 0,
                "completed_touches": []
            }
            
            def _store_fallback():
                sequence_key = self.SEQUENCE_KEY.format(user_id=user_id)
                self.redis_client.setex(sequence_key, self.SEQUENCE_TTL, json.dumps(sequence_data, default=str))
                
                # Generate simple schedule
                schedule_data = self._generate_initial_schedule(sequence, lead_data)
                schedule_key = self.SCHEDULE_KEY.format(user_id=user_id)
                self.redis_client.setex(schedule_key, self.SCHEDULE_TTL, json.dumps(schedule_data, default=str))
                
                logger.info(f"Scheduled fallback nurture sequence for user {user_id}")
                return True
            
            return self.circuit_breaker.call(_store_fallback)
            
        except Exception as e:
            logger.error(f"Error in fallback scheduling for user {user_id}: {e}")
            return False
    
    def update_sequence_config(self, industry: str, intent: str, sequence_config: SequenceConfig):
        """
        Update sequence configuration dynamically.
        
        Args:
            industry: Industry type
            intent: Intent level (high_intent/low_intent)
            sequence_config: New sequence configuration
        """
        try:
            industry_enum = IndustryType(industry.lower())
            
            # Convert to internal format
            touch_points = [
                TouchPoint(
                    day=tp.day,
                    channel=ChannelType(tp.channel),
                    template_key=tp.template_key,
                    content=tp.content,
                    personalization_data=tp.personalization_data,
                    compliance_checked=tp.compliance_checked
                )
                for tp in sequence_config.touch_points
            ]
            
            # Update internal sequences
            if industry_enum not in self.sequences:
                self.sequences[industry_enum] = {}
            
            self.sequences[industry_enum][intent] = NurtureSequence(
                industry_type=industry_enum,
                intent_threshold=sequence_config.intent_threshold,
                touch_points=touch_points,
                total_duration_days=sequence_config.total_duration_days,
                ab_test_enabled=sequence_config.ab_test_enabled
            )
            
            # Update configuration loader
            nurture_config_loader.update_sequence(industry, intent, sequence_config)
            
            logger.info(f"Updated sequence configuration for {industry} {intent}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update sequence configuration: {e}")
            return False
    
    def update_template_config(self, industry: str, template_key: str, template_config: TemplateConfig):
        """
        Update template configuration dynamically.
        
        Args:
            industry: Industry type
            template_key: Template identifier
            template_config: New template configuration
        """
        try:
            industry_enum = IndustryType(industry.lower())
            
            # Update internal templates
            if industry_enum not in self.templates:
                self.templates[industry_enum] = {}
            
            self.templates[industry_enum][template_key] = {
                "template": template_config.template,
                "personalization_fields": template_config.personalization_fields,
                "compliance_required": template_config.compliance_required,
                "channel_specific": template_config.channel_specific,
                "a_b_test_variants": template_config.a_b_test_variants
            }
            
            # Update configuration loader
            nurture_config_loader.update_template(industry, template_key, template_config)
            
            logger.info(f"Updated template configuration for {industry} {template_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update template configuration: {e}")
            return False
    
    def reload_configurations(self):
        """Reload all configurations from sources"""
        try:
            nurture_config_loader.load_configurations()
            self._load_dynamic_configurations()
            logger.info("Successfully reloaded nurture configurations")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configurations: {e}")
            return False
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current configurations"""
        summary = {
            "industries": list(self.sequences.keys()),
            "total_sequences": sum(len(industry_data) for industry_data in self.sequences.values()),
            "total_templates": sum(len(industry_data) for industry_data in self.templates.values()),
            "langgraph_available": LANGGRAPH_AVAILABLE,
            "config_source": "dynamic" if nurture_config_loader.config_path else "default"
        }
        
        # Add industry-specific details
        industry_details = {}
        for industry, industry_data in self.sequences.items():
            industry_details[industry.value] = {
                "intent_levels": list(industry_data.keys()),
                "templates": list(self.templates.get(industry, {}).keys()),
                "total_touch_points": sum(len(seq.touch_points) for seq in industry_data.values())
            }
        
        summary["industry_details"] = industry_details
        return summary

# Global instance
nurture_sequence_manager = NurtureSequenceManager()

# Convenience functions for backward compatibility
def schedule_nurture_sequence(user_id: str, lead_score: float, industry_type: str, lead_data: Dict[str, Any]) -> bool:
    """Schedule nurture sequence for a user"""
    return nurture_sequence_manager.schedule_nurture_sequence(user_id, lead_score, industry_type, lead_data)

def get_next_touch_point(user_id: str) -> Optional[Dict[str, Any]]:
    """Get next touch point for a user"""
    return nurture_sequence_manager.get_next_touch_point(user_id)

def cancel_nurture_sequence(user_id: str) -> bool:
    """Cancel nurture sequence for a user"""
    return nurture_sequence_manager.cancel_nurture_sequence(user_id)

def update_sequence_progress(user_id: str, touch_completed: bool) -> bool:
    """Update sequence progress for a user"""
    return nurture_sequence_manager.update_sequence_progress(user_id, touch_completed)