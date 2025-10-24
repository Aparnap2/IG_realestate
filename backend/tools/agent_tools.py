"""
Comprehensive tools for LangGraph agents according to PRD specifications.

These tools handle database queries, API integrations, caching, and handoffs
between agents in the swarm architecture.

Enhanced with comprehensive error handling, circuit breaker patterns,
timeout handling, and graceful degradation according to DDG MCP best practices.
"""
import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import hashlib
import logging
import time
import threading
from langchain_core.tools import tool
from pydantic import BaseModel, ValidationError, Field

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.supabase_client import (
    query_properties_db,
    save_lead,
    get_config,
    get_auth_context,
    validate_user_access,
    supabase_circuit_breaker
)
from utils.redis_client import cache_query_result, get_cached_query_result, redis_health_check, redis_circuit_breaker
from utils.llm_client import get_llm_response_sync
from utils.observability import log_hubspot_operation, log_supabase_query
from utils.rate_limiter import check_rate_limit, record_request, RateLimitExceeded, RateLimitError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Circuit breaker for external API calls
class ExternalAPICircuitBreaker:
    def __init__(self, service_name: str, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception(f"{self.service_name} circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = 'CLOSED'

    def _on_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'

# Global circuit breakers for external services
instagram_circuit_breaker = ExternalAPICircuitBreaker("Instagram API", failure_threshold=5, recovery_timeout=120)
calendar_circuit_breaker = ExternalAPICircuitBreaker("Google Calendar API", failure_threshold=3, recovery_timeout=60)
hubspot_circuit_breaker = ExternalAPICircuitBreaker("HubSpot API", failure_threshold=3, recovery_timeout=60)

# Timeout configurations
API_TIMEOUTS = {
    "instagram": 10,
    "calendar": 15,
    "hubspot": 15,
    "llm": 30
}

# Pydantic validation models for tool inputs
class QueryPropertiesInput(BaseModel):
    budget: int = Field(..., gt=0, description="Maximum budget for properties")
    location: str = Field(..., min_length=1, description="Desired location")
    property_type: str = Field(..., min_length=1, description="Type of property")

class SaveLeadInput(BaseModel):
    lead_data: Dict[str, Any] = Field(..., description="Lead information to save")

class GetConfigInput(BaseModel):
    key: str = Field(..., min_length=1, description="Configuration key")
    default_value: str = Field("", description="Default value if key is not found")

class QualifyLeadInput(BaseModel):
    budget: Optional[int] = Field(None, gt=0, description="Lead's budget")
    location: Optional[str] = Field(None, min_length=1, description="Lead's desired location")
    property_type: Optional[str] = Field(None, min_length=1, description="Lead's desired property type")
    timeline: Optional[str] = Field(None, min_length=1, description="Lead's timeline")
    db_results: List[Dict[str, Any]] = Field(..., description="Available properties from database")

class SendInstagramMessageInput(BaseModel):
    user_id: str = Field(..., min_length=1, description="Instagram user ID (PSID)")
    message: str = Field(..., min_length=1, description="Message to send")

class GetCalendarSlotsInput(BaseModel):
    days_ahead: int = Field(7, ge=1, le=365, description="Number of days to look ahead")
    time_of_day: str = Field("any", description="Preferred time (morning, afternoon, evening, any)")

class BookCalendarEventInput(BaseModel):
    start_time: datetime = Field(..., description="Event start time")
    duration_minutes: int = Field(..., gt=0, le=480, description="Event duration in minutes")
    attendee_email: str = Field(..., description="Attendee's email")
    summary: str = Field(..., min_length=1, description="Event summary")
    description: str = Field("", description="Event description")
    property_addresses: Optional[List[str]] = Field(None, description="List of property addresses for tour")

class CreateHubSpotContactInput(BaseModel):
    email: str = Field(..., description="Contact's email")
    first_name: str = Field("", description="Contact's first name")
    phone: str = Field("", description="Contact's phone number")
    lifecycle_stage: str = Field("lead", description="HubSpot lifecycle stage")

class CreateHubSpotDealInput(BaseModel):
    contact_id: str = Field(..., min_length=1, description="Associated contact ID")
    deal_name: str = Field(..., min_length=1, description="Deal name")
    amount: int = Field(..., ge=0, description="Deal amount")
    deal_stage: str = Field("appointmentscheduled", description="HubSpot deal stage")

# Database and Caching Tools
@tool
def query_properties_tool(budget: int, location: str, property_type: str) -> List[Dict[str, Any]]:
    """
    Query properties from the database based on lead criteria.
    Includes comprehensive error handling and graceful degradation.

    Args:
        budget: Maximum budget for properties
        location: Desired location
        property_type: Type of property

    Returns:
        List of matching properties, or empty list on failure
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for property queries")
            raise HTTPException(status_code=401, detail="Authentication required for property queries")

        user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(user_id, company_id, "properties")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {user_id} to properties in company {company_id}")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for property queries")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("query_properties_tool")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for query_properties_tool, reset at {reset_time}")
                raise RateLimitExceeded("query_properties_tool", 100, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")
            # Continue with request despite rate limiting failure

        # Validate inputs
        try:
            validated_input = QueryPropertiesInput(budget=budget, location=location, property_type=property_type)
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            return []

        # Check cache with circuit breaker protection
        query_key = f"properties_{budget}_{location}_{property_type}_{company_id or 'global'}"
        cached_result = None
        try:
            cached_result = redis_circuit_breaker.call(
                lambda: get_cached_query_result(query_key, user_id)
            )
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e} - proceeding with database query")

        if cached_result:
            record_request("query_properties_tool")
            logger.debug(f"Cache hit for query_properties_tool: {len(cached_result)} results")
            return cached_result

        # Query database with circuit breaker protection
        try:
            results = supabase_circuit_breaker.call(
                lambda: query_properties_db(budget, location, property_type, company_id)
            )
            log_supabase_query("properties", "select", len(results) > 0, record_count=len(results))
            logger.info(f"Database query successful: {len(results)} properties found")
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return []

        # Cache results with circuit breaker protection
        try:
            redis_circuit_breaker.call(
                lambda: cache_query_result(query_key, user_id, results, ttl=86400)
            )
        except Exception as e:
            logger.debug(f"Cache storage failed: {e} - continuing without caching")

        record_request("query_properties_tool")
        return results

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for query_properties_tool")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in query_properties_tool: {e}", exc_info=True)
        return []

@tool
def save_lead_tool(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save lead information to the database.
    Includes comprehensive error handling and circuit breaker protection.

    Args:
        lead_data: Lead information to save

    Returns:
        Saved lead data, or empty dict on failure
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for saving leads")
            raise HTTPException(status_code=401, detail="Authentication required for saving leads")

        user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(user_id, company_id, "leads")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {user_id} to save leads in company {company_id}")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for saving leads")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("save_lead_tool")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for save_lead_tool, reset at {reset_time}")
                raise RateLimitExceeded("save_lead_tool", 50, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        try:
            validated_input = SaveLeadInput(lead_data=lead_data)
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            return {}

        # Ensure lead data includes user and company context
        lead_data_with_context = {
            **validated_input.lead_data,
            "user_id": user_id,
            "company_id": company_id
        }

        # Save lead with circuit breaker protection
        try:
            result = supabase_circuit_breaker.call(lambda: save_lead(lead_data_with_context))
            log_supabase_query("leads", "upsert", bool(result), record_count=1 if result else 0)
            logger.info(f"Lead saved successfully: {result.get('id', 'unknown')}")
            record_request("save_lead_tool")
            return result
        except Exception as e:
            logger.error(f"Database save failed: {e}")
            log_supabase_query("leads", "upsert", False, error=str(e))
            return {}

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for save_lead_tool")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in save_lead_tool: {e}", exc_info=True)
        return {}

@tool
def get_config_tool(key: str, default_value: str = "") -> str:
    """
    Get configuration value from the database.

    Args:
        key: Configuration key
        default_value: Default value if key is not found

    Returns:
        Configuration value or default value
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            raise HTTPException(status_code=401, detail="Authentication required for configuration access")

        user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access
        if not validate_user_access(user_id, company_id, "configs"):
            raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for configuration access")

        # Check rate limit
        allowed, headers = check_rate_limit("get_config_tool")
        if not allowed:
            raise RateLimitExceeded("get_config_tool", 200, int(headers["X-RateLimit-Reset"]))

        # Validate inputs
        validated_input = GetConfigInput(key=key, default_value=default_value)
        result = get_config(validated_input.key, validated_input.default_value)
        record_request("get_config_tool")
        return result
    except HTTPException:
        raise
    except RateLimitExceeded:
        print(f"Rate limit exceeded for get_config_tool")
        return default_value
    except Exception as e:
        print(f"Error getting config: {e}")
        return default_value

# LLM Tools
@tool
def qualify_lead_with_llm(
    budget: Optional[int],
    location: Optional[str],
    property_type: Optional[str],
    timeline: Optional[str],
    db_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use LLM to qualify a lead based on criteria and available properties.

    Args:
        budget: Lead's budget
        location: Lead's desired location
        property_type: Lead's desired property type
        timeline: Lead's timeline
        db_results: Available properties from database

    Returns:
        Dictionary with score and reasoning
    """
    try:
        # Check rate limit
        allowed, headers = check_rate_limit("qualify_lead_with_llm")
        if not allowed:
            raise RateLimitExceeded("qualify_lead_with_llm", 30, int(headers["X-RateLimit-Reset"]))

        # Validate inputs
        validated_input = QualifyLeadInput(
            budget=budget,
            location=location,
            property_type=property_type,
            timeline=timeline,
            db_results=db_results
        )
        # Get qualification prompt from config
        prompt_template = get_config_tool.invoke({
            "key": "qualifier_prompt",
            "default_value": """Score this lead (0-1) for real estate interest based on:
Budget: {budget}
Location: {location}
Type: {property_type}
Timeline: {timeline}

DB properties: {db_results}

Scoring Rubric:
- Budget > $500k: +0.3
- Budget > $300k: +0.2
- Budget > $100k: +0.1
- Location and property type match DB: +0.3
- Timeline < 6 months: +0.1

Provide your response as a JSON object with the following structure:
{{
    "score": 0.8,
    "reasoning": "Explanation of the score"
}}"""
        })

        # Format the prompt
        prompt = prompt_template.format(
            budget=validated_input.budget or "Not specified",
            location=validated_input.location or "Not specified",
            property_type=validated_input.property_type or "Not specified",
            timeline=validated_input.timeline or "Not specified",
            db_results=json.dumps(validated_input.db_results[:3])  # Limit to first 3 properties
        )

        # Get LLM response enforcing JSON mode to prevent malformed outputs
        response = get_llm_response_sync(prompt, response_format={"type": "json_object"})

        # Parse response robustly (strip fences, extract JSON segment if mixed content)
        try:
            cleaned = response.strip()
            # Remove markdown code fences if present
            cleaned = cleaned.replace("```json", "").replace("```", "")
            # Extract JSON object from mixed text
            if "{" in cleaned and "}" in cleaned:
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}") + 1
                cleaned = cleaned[start_idx:end_idx]
            result = json.loads(cleaned)
            score = float(result.get("score", 0.5))
            reasoning = result.get("reasoning", "Default reasoning")

            # Normalize score
            score = max(0.0, min(1.0, score))

            record_request("qualify_lead_with_llm")
            return {
                "score": score,
                "reasoning": reasoning
            }
        except json.JSONDecodeError:
            # Fallback parsing: tolerate plain numeric score
            try:
                score = float(response.strip())
                score = max(0.0, min(1.0, score))
                record_request("qualify_lead_with_llm")
                return {
                    "score": score,
                    "reasoning": "Fallback parsing used"
                }
            except Exception:
                record_request("qualify_lead_with_llm")
                return {
                    "score": 0.5,
                    "reasoning": "Default score due to parsing error"
                }

    except RateLimitExceeded:
        print(f"Rate limit exceeded for qualify_lead_with_llm")
        return {
            "score": 0.5,
            "reasoning": "Rate limit exceeded"
        }
    except Exception as e:
        print(f"Error qualifying lead with LLM: {e}")
        return {
            "score": 0.5,
            "reasoning": f"Error occurred: {str(e)}"
        }

# Instagram Graph API Integration
@tool
def send_instagram_message(user_id: str, message: str) -> bool:
    """
    Send a message via Instagram Graph API.
    Includes circuit breaker protection, timeout handling, and graceful degradation.

    Args:
        user_id: Instagram user ID (PSID)
        message: Message to send

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for Instagram messaging")
            raise HTTPException(status_code=401, detail="Authentication required for Instagram messaging")

        authenticated_user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(authenticated_user_id, company_id, "leads")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {authenticated_user_id} to Instagram messaging")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for Instagram messaging")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # No user mapping needed for simple Instagram DM automation
        # Direct access allowed for Instagram users
        
        logger.debug(f"Instagram user {user_id} access granted")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("send_instagram_message")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for send_instagram_message, reset at {reset_time}")
                raise RateLimitExceeded("send_instagram_message", 20, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        try:
            validated_input = SendInstagramMessageInput(user_id=user_id, message=message)
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            return False

        from config import get_settings
        settings = get_settings()

        if not settings.ENABLE_REAL_INSTAGRAM_API:
            # Mock implementation for development
            logger.info(f"[MOCK] Sending Instagram message to {validated_input.user_id}: {validated_input.message[:50]}...")
            record_request("send_instagram_message")
            return True

        # Send message with circuit breaker protection
        def _send_message():
            import requests

            url = "https://graph.facebook.com/v21.0/me/messages"
            payload = {
                "recipient": {"id": validated_input.user_id},
                "message": {"text": validated_input.message}
            }
            headers = {
                "Authorization": f"Bearer {settings.INSTAGRAM_PAGE_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers, timeout=API_TIMEOUTS["instagram"])

            if response.status_code == 200:
                # Log successful send
                from utils.audit import audit_log_event
                audit_log_event("instagram_message_sent", {
                    "user_id": validated_input.user_id,
                    "authenticated_user_id": authenticated_user_id,
                    "company_id": company_id,
                    "message_length": len(validated_input.message),
                    "response_id": response.json().get("message_id")
                })
                return True
            else:
                # Log failure
                from utils.audit import audit_log_event
                audit_log_event("instagram_message_failed", {
                    "user_id": validated_input.user_id,
                    "authenticated_user_id": authenticated_user_id,
                    "company_id": company_id,
                    "status_code": response.status_code,
                    "error": response.text
                })
                return False

        try:
            result = instagram_circuit_breaker.call(_send_message)
            record_request("send_instagram_message")
            return result
        except Exception as e:
            logger.error(f"Instagram API call failed: {e}")
            from utils.audit import audit_log_event
            audit_log_event("instagram_message_error", {
                "user_id": user_id,
                "error": str(e)
            })
            return False

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for send_instagram_message")
        from utils.audit import audit_log_event
        audit_log_event("instagram_message_rate_limited", {
            "user_id": user_id,
            "message_length": len(message)
        })
        return False
    except Exception as e:
        logger.error(f"Unexpected error in send_instagram_message: {e}", exc_info=True)
        return False



# Google Calendar Tools (Real Implementation)
@tool
def get_available_calendar_slots(days_ahead: int = 7, time_of_day: str = "any") -> List[datetime]:
    """
    Get available calendar slots from Google Calendar.
    Includes circuit breaker protection and timeout handling.

    Args:
        days_ahead: Number of days to look ahead
        time_of_day: Preferred time ("morning", "afternoon", "evening", "any")

    Returns:
        List of available datetime slots, or empty list on failure
    """
    try:
        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("get_available_calendar_slots")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for get_available_calendar_slots, reset at {reset_time}")
                raise RateLimitExceeded("get_available_calendar_slots", 50, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        try:
            validated_input = GetCalendarSlotsInput(days_ahead=days_ahead, time_of_day=time_of_day)
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            return []

        # Get calendar slots with circuit breaker protection
        def _get_slots():
            from tools.calendar_integration import get_available_calendar_slots as get_slots
            return get_slots(days_ahead=validated_input.days_ahead, time_of_day=validated_input.time_of_day)

        try:
            result = calendar_circuit_breaker.call(_get_slots)
            record_request("get_available_calendar_slots")
            logger.info(f"Retrieved {len(result)} calendar slots")
            return result
        except Exception as e:
            logger.error(f"Calendar API call failed: {e}")
            from utils.audit import audit_log_event
            audit_log_event("calendar_slots_error", {"error": str(e)})
            return []

    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for get_available_calendar_slots")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_available_calendar_slots: {e}", exc_info=True)
        return []

@tool
def book_calendar_event(
    start_time: datetime,
    duration_minutes: int,
    attendee_email: str,
    summary: str,
    description: str = "",
    property_addresses: List[str] = None
) -> Dict[str, Any]:
    """
    Book a calendar event via Google Calendar API with Google Meet link.

    Args:
        start_time: Event start time
        duration_minutes: Event duration in minutes
        attendee_email: Attendee's email
        summary: Event summary
        description: Event description
        property_addresses: List of property addresses for tour

    Returns:
        Dictionary with event details or error
    """
    try:
        # Check rate limit
        allowed, headers = check_rate_limit("book_calendar_event")
        if not allowed:
            raise RateLimitExceeded("book_calendar_event", 10, int(headers["X-RateLimit-Reset"]))

        # Validate inputs
        validated_input = BookCalendarEventInput(
            start_time=start_time,
            duration_minutes=duration_minutes,
            attendee_email=attendee_email,
            summary=summary,
            description=description,
            property_addresses=property_addresses
        )
        from tools.calendar_integration import create_tour_event
        result = create_tour_event(
            start_time=validated_input.start_time,
            duration_minutes=validated_input.duration_minutes,
            attendee_email=validated_input.attendee_email,
            summary=validated_input.summary,
            description=validated_input.description,
            property_addresses=validated_input.property_addresses or []
        )
        record_request("book_calendar_event")
        return result
    except RateLimitExceeded:
        print(f"Rate limit exceeded for book_calendar_event")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        print(f"Error booking calendar event: {e}")
        from utils.audit import audit_log_event
        audit_log_event("calendar_booking_error", {
            "error": str(e),
            "start_time": validated_input.start_time.isoformat(),
            "attendee_email": validated_input.attendee_email
        })
        return {"error": str(e)}

# HubSpot Tools (Gated implementation)
@tool
def create_hubspot_contact(
    email: str,
    first_name: str = "",
    phone: str = "",
    lifecycle_stage: str = "lead"
) -> Dict[str, Any]:
    """
    Create a contact in HubSpot.
    Includes circuit breaker protection, timeout handling, and graceful degradation.

    Args:
        email: Contact's email
        first_name: Contact's first name
        phone: Contact's phone number
        lifecycle_stage: HubSpot lifecycle stage

    Returns:
        Dictionary with contact details or error
    """
    try:
        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("create_hubspot_contact")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for create_hubspot_contact, reset at {reset_time}")
                raise RateLimitExceeded("create_hubspot_contact", 20, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        try:
            validated_input = CreateHubSpotContactInput(
                email=email,
                first_name=first_name,
                phone=phone,
                lifecycle_stage=lifecycle_stage
            )
        except ValidationError as e:
            logger.error(f"Input validation error: {e}")
            return {"error": "Invalid input parameters"}

        from config import get_settings
        settings = get_settings()

        # Gate HubSpot integration on access token availability
        access_token = getattr(settings, 'HUBSPOT_ACCESS_TOKEN', None)
        if not access_token:
            logger.info("HubSpot access token not configured - using mock implementation")
            # Mock implementation for development
            contact_id = f"mock_contact_{hashlib.md5(validated_input.email.encode()).hexdigest()[:8]}"
            logger.info(f"[MOCK] Creating HubSpot contact: {validated_input.email}")
            record_request("create_hubspot_contact")

            return {
                "contact_id": contact_id,
                "email": validated_input.email,
                "first_name": validated_input.first_name,
                "phone": validated_input.phone,
                "lifecycle_stage": validated_input.lifecycle_stage,
                "status": "mock_created"
            }

        # Real HubSpot API implementation with circuit breaker protection
        def _create_contact():
            import requests

            # Create contact via HubSpot API
            url = "https://api.hubapi.com/contacts/v1/contact"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Prepare contact properties
            properties = []
            if validated_input.email:
                properties.append({"property": "email", "value": validated_input.email})
            if validated_input.first_name:
                properties.append({"property": "firstname", "value": validated_input.first_name})
            if validated_input.phone:
                properties.append({"property": "phone", "value": validated_input.phone})
            if validated_input.lifecycle_stage:
                properties.append({"property": "lifecyclestage", "value": validated_input.lifecycle_stage})

            payload = {"properties": properties}

            response = requests.post(url, json=payload, headers=headers, timeout=API_TIMEOUTS["hubspot"])

            if response.status_code == 200:
                contact_data = response.json()
                contact_id = str(contact_data.get("vid", ""))
                logger.info(f"Created HubSpot contact: {validated_input.email} (ID: {contact_id})")

                # Log successful creation
                from utils.audit import audit_log_event
                audit_log_event("hubspot_contact_created", {
                    "contact_id": contact_id,
                    "email": validated_input.email,
                    "status": "success"
                })

                # Structured observability logging
                log_hubspot_operation("contact_created", True, contact_id=contact_id)
                record_request("create_hubspot_contact")

                return {
                    "contact_id": contact_id,
                    "email": validated_input.email,
                    "first_name": validated_input.first_name,
                    "phone": validated_input.phone,
                    "lifecycle_stage": validated_input.lifecycle_stage,
                    "status": "created"
                }
            else:
                error_msg = f"HubSpot API error: {response.status_code} - {response.text}"
                logger.error(f"Failed to create HubSpot contact: {error_msg}")

                from utils.audit import audit_log_event
                audit_log_event("hubspot_contact_failed", {
                    "email": validated_input.email,
                    "status_code": response.status_code,
                    "error": error_msg
                })

                # Structured observability logging
                log_hubspot_operation("contact_creation_failed", False, error=error_msg)

                return {"error": error_msg}

        try:
            result = hubspot_circuit_breaker.call(_create_contact)
            return result
        except Exception as e:
            logger.error(f"HubSpot API call failed: {e}")
            from utils.audit import audit_log_event
            audit_log_event("hubspot_contact_error", {
                "email": validated_input.email,
                "error": str(e)
            })
            return {"error": str(e)}

    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for create_hubspot_contact")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        logger.error(f"Unexpected error in create_hubspot_contact: {e}", exc_info=True)
        return {"error": str(e)}

@tool
def create_hubspot_deal(
    contact_id: str,
    deal_name: str,
    amount: int,
    deal_stage: str = "appointmentscheduled"
) -> Dict[str, Any]:
    """
    Create a deal in HubSpot.

    Args:
        contact_id: Associated contact ID
        deal_name: Deal name
        amount: Deal amount
        deal_stage: HubSpot deal stage

    Returns:
        Dictionary with deal details or error
    """
    try:
        # Check rate limit
        allowed, headers = check_rate_limit("create_hubspot_deal")
        if not allowed:
            raise RateLimitExceeded("create_hubspot_deal", 10, int(headers["X-RateLimit-Reset"]))

        # Validate inputs
        validated_input = CreateHubSpotDealInput(
            contact_id=contact_id,
            deal_name=deal_name,
            amount=amount,
            deal_stage=deal_stage
        )
        from config import get_settings
        settings = get_settings()

        # Gate HubSpot integration on access token availability
        access_token = getattr(settings, 'HUBSPOT_ACCESS_TOKEN', None)
        if not access_token:
            print("ℹ️ HubSpot access token not configured - using mock implementation")
            # Mock implementation for development
            deal_id = f"mock_deal_{hashlib.md5(f'{validated_input.contact_id}_{validated_input.deal_name}'.encode()).hexdigest()[:8]}"
            print(f"[MOCK] Creating HubSpot deal: {validated_input.deal_name} for ${validated_input.amount}")
            record_request("create_hubspot_deal")

            return {
                "deal_id": deal_id,
                "contact_id": validated_input.contact_id,
                "deal_name": validated_input.deal_name,
                "amount": validated_input.amount,
                "deal_stage": validated_input.deal_stage,
                "status": "mock_created"
            }

        # Real HubSpot API implementation
        import requests

        # Create deal via HubSpot API
        url = "https://api.hubapi.com/deals/v1/deal"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Prepare deal properties
        properties = [
            {"name": "dealname", "value": validated_input.deal_name},
            {"name": "amount", "value": str(validated_input.amount)},
            {"name": "dealstage", "value": validated_input.deal_stage}
        ]

        # Associate with contact if it's a real HubSpot contact ID (not mock)
        associations = {}
        if not validated_input.contact_id.startswith("mock_contact_"):
            associations = {
                "associatedVids": [int(validated_input.contact_id)]
            }

        payload = {
            "properties": properties,
            "associations": associations
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            deal_data = response.json()
            deal_id = str(deal_data.get("dealId", ""))
            print(f"✅ Created HubSpot deal: {validated_input.deal_name} (ID: {deal_id})")

            # Log successful creation
            from utils.audit import audit_log_event
            audit_log_event("hubspot_deal_created", {
                "deal_id": deal_id,
                "contact_id": validated_input.contact_id,
                "deal_name": validated_input.deal_name,
                "amount": validated_input.amount,
                "status": "success"
            })

            # Structured observability logging
            log_hubspot_operation("deal_created", True, contact_id=validated_input.contact_id, deal_id=deal_id)
            record_request("create_hubspot_deal")

            return {
                "deal_id": deal_id,
                "contact_id": validated_input.contact_id,
                "deal_name": validated_input.deal_name,
                "amount": validated_input.amount,
                "deal_stage": validated_input.deal_stage,
                "status": "created"
            }
        else:
            error_msg = f"HubSpot API error: {response.status_code} - {response.text}"
            print(f"❌ Failed to create HubSpot deal: {error_msg}")

            from utils.audit import audit_log_event
            audit_log_event("hubspot_deal_failed", {
                "contact_id": validated_input.contact_id,
                "deal_name": validated_input.deal_name,
                "status_code": response.status_code,
                "error": error_msg
            })

            # Structured observability logging
            log_hubspot_operation("deal_creation_failed", False, contact_id=validated_input.contact_id, error=error_msg)

            return {"error": error_msg}

    except RateLimitExceeded:
        print(f"Rate limit exceeded for create_hubspot_deal")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        print(f"Error creating HubSpot deal: {e}")
        from utils.audit import audit_log_event
        audit_log_event("hubspot_deal_error", {
            "contact_id": validated_input.contact_id,
            "deal_name": validated_input.deal_name,
            "error": str(e)
        })
        return {"error": str(e)}

# Handoff Tools
@tool
def handoff_to_scheduler() -> str:
    """
    Handoff to scheduler agent.
    
    Returns:
        Next agent name
    """
    return "scheduler"

@tool
def handoff_to_followup() -> str:
    """
    Handoff to followup agent.
    
    Returns:
        Next agent name
    """
    return "followup"

@tool
def handoff_to_end() -> str:
    """
    End the workflow.
    
    Returns:
        End signal
    """
    return "END"

# Circuit breaker status monitoring
def get_external_api_status() -> Dict[str, Any]:
    """
    Get the current status of all external API circuit breakers for monitoring.

    Returns:
        Dictionary with circuit breaker statuses
    """
    return {
        "instagram_api": {
            "state": instagram_circuit_breaker.state,
            "failure_count": instagram_circuit_breaker.failure_count,
            "last_failure_time": instagram_circuit_breaker.last_failure_time
        },
        "calendar_api": {
            "state": calendar_circuit_breaker.state,
            "failure_count": calendar_circuit_breaker.failure_count,
            "last_failure_time": calendar_circuit_breaker.last_failure_time
        },
        "hubspot_api": {
            "state": hubspot_circuit_breaker.state,
            "failure_count": hubspot_circuit_breaker.failure_count,
            "last_failure_time": hubspot_circuit_breaker.last_failure_time
        }
    }

# Lead Magnet Tools
@tool
def fetch_lead_magnet(magnet_type: str) -> Dict[str, Any]:
    """
    Fetch lead magnet from Supabase Storage.
    
    Args:
        magnet_type: Type of lead magnet (e.g., "first_time_buyer_guide")
        
    Returns:
        Dictionary with lead magnet data or empty dict on failure
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for lead magnet access")
            raise HTTPException(status_code=401, detail="Authentication required for lead magnet access")

        user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(user_id, company_id, "lead_magnets")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {user_id} to lead magnets")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for lead magnet access")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("fetch_lead_magnet")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for fetch_lead_magnet, reset at {reset_time}")
                raise RateLimitExceeded("fetch_lead_magnet", 50, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        if not magnet_type or not isinstance(magnet_type, str):
            logger.error(f"Invalid magnet_type: {magnet_type}")
            return {}

        # Fetch lead magnet from Supabase Storage
        def _fetch_magnet():
            from utils.supabase_client import supabase
            
            # Get lead magnet metadata from database
            magnet_response = supabase.table("lead_magnets").select("*").eq("type", magnet_type).eq("active", True).execute()
            
            if not magnet_response.data or len(magnet_response.data) == 0:
                logger.warning(f"No active lead magnet found for type: {magnet_type}")
                return {}
            
            magnet_data = magnet_response.data[0]
            
            # For now, return mock data since we don't have actual Supabase Storage integration
            # In production, this would fetch the actual file from Supabase Storage
            return {
                "id": magnet_data.get("id"),
                "type": magnet_data.get("type"),
                "title": magnet_data.get("title"),
                "description": magnet_data.get("description"),
                "delivery_text": magnet_data.get("delivery_text"),
                "file_url": magnet_data.get("file_url"),
                "thumbnail_url": magnet_data.get("thumbnail_url"),
                "active": magnet_data.get("active")
            }

        try:
            result = supabase_circuit_breaker.call(_fetch_magnet)
            record_request("fetch_lead_magnet")
            logger.info(f"Retrieved lead magnet: {magnet_type}")
            return result
        except Exception as e:
            logger.error(f"Failed to fetch lead magnet: {e}")
            return {}

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for fetch_lead_magnet")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in fetch_lead_magnet: {e}", exc_info=True)
        return {}

# Enhanced Value Delivery Tools
@tool
def deliver_property_info(property_id: str, user_id: str) -> Dict[str, Any]:
    """
    Deliver detailed property information to lead.
    
    Args:
        property_id: ID of property to deliver
        user_id: Lead's user ID for personalization
        
    Returns:
        Dictionary with property information or error
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for property info delivery")
            raise HTTPException(status_code=401, detail="Authentication required for property info delivery")

        authenticated_user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(authenticated_user_id, company_id, "properties")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {authenticated_user_id} to property info delivery")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for property info delivery")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("deliver_property_info")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for deliver_property_info, reset at {reset_time}")
                raise RateLimitExceeded("deliver_property_info", 50, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        if not property_id or not isinstance(property_id, str):
            logger.error(f"Invalid property_id: {property_id}")
            return {"error": "Invalid property ID"}
        
        if not user_id or not isinstance(user_id, str):
            logger.error(f"Invalid user_id: {user_id}")
            return {"error": "Invalid user ID"}

        # Query property details
        def _get_property_details():
            from utils.supabase_client import supabase
            
            # Get property with full details
            property_response = supabase.table("properties").select("*").eq("id", property_id).execute()
            
            if not property_response.data or len(property_response.data) == 0:
                return {"error": f"Property {property_id} not found"}
            
            property_data = property_response.data[0]
            
            # Get additional property details (images, features, etc.)
            images_response = supabase.table("property_images").select("*").eq("property_id", property_id).execute()
            features_response = supabase.table("property_features").select("*").eq("property_id", property_id).execute()
            
            # Enhance property data
            property_data["images"] = images_response.data or []
            property_data["features"] = features_response.data or []
            
            return property_data

        try:
            property_data = supabase_circuit_breaker.call(_get_property_details)
            record_request("deliver_property_info")
            logger.info(f"Property info delivered: {property_id}")
            return {
                "property_id": property_id,
                "property_data": property_data,
                "delivery_timestamp": datetime.now().isoformat(),
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to deliver property info: {e}")
            return {"error": str(e)}

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for deliver_property_info")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        logger.error(f"Unexpected error in deliver_property_info: {e}", exc_info=True)
        return {"error": str(e)}

@tool
def send_market_insights(location: str, insight_type: str = "general", user_id: str = None) -> Dict[str, Any]:
    """
    Send market insights and neighborhood data to lead.
    
    Args:
        location: Location for market insights
        insight_type: Type of insights (prices, trends, neighborhood, general)
        user_id: Lead's user ID for personalization
        
    Returns:
        Dictionary with market insights or error
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for market insights")
            raise HTTPException(status_code=401, detail="Authentication required for market insights")

        authenticated_user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(authenticated_user_id, company_id, "market_data")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {authenticated_user_id} to market insights")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for market insights")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("send_market_insights")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for send_market_insights, reset at {reset_time}")
                raise RateLimitExceeded("send_market_insights", 30, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        if not location or not isinstance(location, str):
            logger.error(f"Invalid location: {location}")
            return {"error": "Invalid location"}
        
        valid_insight_types = ["prices", "trends", "neighborhood", "general"]
        if insight_type not in valid_insight_types:
            logger.error(f"Invalid insight_type: {insight_type}")
            return {"error": f"Invalid insight type. Must be one of: {valid_insight_types}"}

        # Generate market insights using LLM
        def _generate_insights():
            from utils.llm_client import get_llm_response_sync
            
            insights_prompt = f"""
            Generate comprehensive real estate market insights for {location}.
            
            Focus on: {insight_type}
            
            Provide:
            1. Current market trends and conditions
            2. Average price ranges for different property types
            3. Neighborhood highlights and amenities
            4. Investment potential and appreciation
            5. Market predictions for next 6-12 months
            6. Buying tips specific to this area
            
            Format as structured JSON with these sections:
            {{
                "market_trends": "...",
                "price_ranges": {{"low": "...", "average": "...", "high": "..."}},
                "neighborhood_highlights": ["...", "..."],
                "investment_potential": "...",
                "predictions": "...",
                "buying_tips": ["...", "..."]
            }}
            """
            
            insights_response = get_llm_response_sync(insights_prompt)
            
            # Parse JSON response
            try:
                import json
                cleaned = insights_response.strip()
                # Remove markdown code fences if present
                cleaned = cleaned.replace("```json", "").replace("```", "")
                # Extract JSON object from mixed text
                if "{" in cleaned and "}" in cleaned:
                    start_idx = cleaned.find("{")
                    end_idx = cleaned.rfind("}") + 1
                    cleaned = cleaned[start_idx:end_idx]
                insights_data = json.loads(cleaned)
                return insights_data
            except json.JSONDecodeError:
                # Fallback to structured text
                return {
                    "market_trends": insights_response,
                    "price_ranges": {"low": "N/A", "average": "N/A", "high": "N/A"},
                    "neighborhood_highlights": ["Market data available"],
                    "investment_potential": "Contact agent for details",
                    "predictions": "Market conditions changing",
                    "buying_tips": ["Research thoroughly", "Get pre-approved"]
                }

        try:
            insights_data = supabase_circuit_breaker.call(_generate_insights)
            record_request("send_market_insights")
            logger.info(f"Market insights sent for: {location}")
            return {
                "location": location,
                "insight_type": insight_type,
                "insights_data": insights_data,
                "delivery_timestamp": datetime.now().isoformat(),
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to generate market insights: {e}")
            return {"error": str(e)}

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for send_market_insights")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        logger.error(f"Unexpected error in send_market_insights: {e}", exc_info=True)
        return {"error": str(e)}

@tool
def create_nurture_sequence(
    lead_score: float,
    lead_stage: str,
    user_id: str,
    custom_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create personalized nurture sequence for lead.
    
    Args:
        lead_score: Current qualification score
        lead_stage: Current qualification stage
        user_id: Lead's user ID
        custom_content: Custom content for nurture sequence
        
    Returns:
        Dictionary with nurture sequence or error
    """
    try:
        # Check authentication context
        auth_context = get_auth_context()
        if not auth_context:
            logger.error("Authentication required for nurture sequence")
            raise HTTPException(status_code=401, detail="Authentication required for nurture sequence")

        authenticated_user_id = auth_context.get("id")
        company_id = auth_context.get("company_id")

        # Validate user access with circuit breaker protection
        try:
            access_granted = supabase_circuit_breaker.call(
                lambda: validate_user_access(authenticated_user_id, company_id, "nurture_campaigns")
            )
            if not access_granted:
                logger.warning(f"Access denied for user {authenticated_user_id} to nurture campaigns")
                raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions for nurture campaigns")
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            raise HTTPException(status_code=403, detail="Access validation failed")

        # Check rate limit with error handling
        try:
            allowed, headers = check_rate_limit("create_nurture_sequence")
            if not allowed:
                reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 60))
                logger.warning(f"Rate limit exceeded for create_nurture_sequence, reset at {reset_time}")
                raise RateLimitExceeded("create_nurture_sequence", 20, reset_time)
        except RateLimitError as e:
            logger.warning(f"Rate limiting error: {e} - allowing request")

        # Validate inputs
        if not isinstance(lead_score, (int, float)) or not (0 <= lead_score <= 1):
            logger.error(f"Invalid lead_score: {lead_score}")
            return {"error": "Invalid lead score. Must be between 0 and 1"}
        
        valid_stages = ["nurturing", "qualified", "disqualified"]
        if lead_stage not in valid_stages:
            logger.error(f"Invalid lead_stage: {lead_stage}")
            return {"error": f"Invalid lead stage. Must be one of: {valid_stages}"}

        # Generate nurture sequence based on lead profile
        def _generate_sequence():
            from utils.llm_client import get_llm_response_sync
            
            # Determine nurture strategy based on score and stage
            if lead_stage == "nurturing":
                if lead_score >= 0.6:
                    strategy = "high_potential_nurture"
                    timeline = "2_weeks"
                else:
                    strategy = "standard_nurture"
                    timeline = "4_weeks"
            elif lead_stage == "qualified":
                strategy = "value_add_nurture"
                timeline = "1_week"
            else:  # disqualified
                strategy = "re_engagement_nurture"
                timeline = "8_weeks"
            
            sequence_prompt = f"""
            Create a personalized nurture sequence for a real estate lead.
            
            Lead Profile:
            - Score: {lead_score} (0-1 scale)
            - Stage: {lead_stage}
            - Strategy: {strategy}
            - Timeline: {timeline}
            
            {f'Custom Content: {custom_content}' if custom_content else ''}
            
            Create a sequence of 3-5 messages with:
            1. Personalized greeting and value proposition
            2. Educational content relevant to their stage
            3. Property recommendations or market insights
            4. Call-to-action appropriate for their qualification level
            5. Follow-up timing and next steps
            
            For each message, include:
            - Timing (e.g., "Day 1", "Day 3", "Day 7")
            - Subject/Topic
            - Message content
            - Purpose (education, engagement, conversion)
            - Send timing (immediate, 1_day, 3_days, etc.)
            
            Format as JSON array of messages.
            """
            
            sequence_response = get_llm_response_sync(sequence_prompt)
            
            # Parse JSON response
            try:
                import json
                cleaned = sequence_response.strip()
                # Remove markdown code fences if present
                cleaned = cleaned.replace("```json", "").replace("```", "")
                # Extract JSON array from mixed text
                if "[" in cleaned and "]" in cleaned:
                    start_idx = cleaned.find("[")
                    end_idx = cleaned.rfind("]") + 1
                    cleaned = cleaned[start_idx:end_idx]
                sequence_data = json.loads(cleaned)
                return sequence_data
            except json.JSONDecodeError:
                # Fallback to basic sequence
                return [
                    {
                        "timing": "Day 1",
                        "subject": "Helpful Real Estate Tips",
                        "content": "Here are some valuable insights for your property search...",
                        "purpose": "education",
                        "send_timing": "immediate"
                    },
                    {
                        "timing": "Day 3",
                        "subject": "Market Update",
                        "content": "I wanted to share some latest market trends...",
                        "purpose": "engagement",
                        "send_timing": "2_days"
                    }
                ]

        try:
            sequence_data = supabase_circuit_breaker.call(_generate_sequence)
            record_request("create_nurture_sequence")
            logger.info(f"Nurture sequence created for user {user_id}: {strategy}")
            return {
                "user_id": user_id,
                "lead_score": lead_score,
                "lead_stage": lead_stage,
                "strategy": strategy,
                "timeline": timeline,
                "sequence": sequence_data,
                "creation_timestamp": datetime.now().isoformat(),
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to create nurture sequence: {e}")
            return {"error": str(e)}

    except HTTPException:
        raise
    except RateLimitExceeded:
        logger.warning("Rate limit exceeded for create_nurture_sequence")
        return {"error": "Rate limit exceeded"}
    except Exception as e:
        logger.error(f"Unexpected error in create_nurture_sequence: {e}", exc_info=True)
        return {"error": str(e)}

# All available tools for agents
ALL_TOOLS = [
    query_properties_tool,
    save_lead_tool,
    get_config_tool,
    qualify_lead_with_llm,
    send_instagram_message,
    get_available_calendar_slots,
    book_calendar_event,
    create_hubspot_contact,
    create_hubspot_deal,
    fetch_lead_magnet,
    deliver_property_info,
    send_market_insights,
    create_nurture_sequence,
    handoff_to_scheduler,
    handoff_to_followup,
    handoff_to_end
]