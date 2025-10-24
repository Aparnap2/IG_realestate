from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging
import os
import time
import threading
from contextlib import contextmanager

# Use runtime settings, avoid import-time hard failures
from config import get_settings

# Lazily initialized Supabase client; tests can patch this symbol directly
supabase: Optional[Client] = None

logger = logging.getLogger(__name__)

# Authentication context for current user
_current_user_context: Optional[Dict[str, Any]] = None

# Circuit breaker state
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception: Exception = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise self.expected_exception("Circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
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

# Global circuit breaker for Supabase operations
supabase_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0

@contextmanager
def supabase_timeout_context(timeout_seconds: int = 30):
    """Context manager for Supabase operations with timeout"""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Supabase operation timed out after {timeout_seconds} seconds")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def retry_with_backoff(func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Retry function with exponential backoff"""
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except (ConnectionError, TimeoutError, OSError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(f"Supabase operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Supabase operation failed after {max_retries + 1} attempts: {e}")
                raise last_exception
        except Exception as e:
            # Don't retry for non-transient errors
            logger.error(f"Non-retryable Supabase error: {e}")
            raise e


def _ensure_supabase() -> Client:
    """
    Lazily initialize the Supabase client using environment-backed Settings.
    - Uses .env as-is via get_settings()
    - Does not fail at import; raises only when first use without configuration
    - Honors test patches: if tests set utils.supabase_client.supabase = mock, returns that
    - Includes connection resilience and circuit breaker protection
    """
    global supabase
    if supabase is not None:
        return supabase

    try:
        settings = get_settings()
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_KEY

        if not url or not key:
            raise ValueError(f"Missing Supabase configuration: SUPABASE_URL={bool(url)}, SUPABASE_KEY={bool(key)}")

        # Test connection with timeout and retry
        def _create_client():
            client = create_client(url, key)
            # Test the connection - use a simple table that should exist
            with supabase_timeout_context(10):
                try:
                    # Try health check table first
                    client.table("_supabase_health_check").select("count").limit(1).execute()
                except Exception:
                    # Fallback to checking basic connectivity via leads table
                    client.table("leads").select("id").limit(1).execute()
            return client

        supabase = retry_with_backoff(_create_client)
        logger.info("Supabase client initialized successfully")
        return supabase

    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        # Reset circuit breaker on initialization failure
        supabase_circuit_breaker._on_failure()
        raise e


def query_properties_db(budget: int, location: str, property_type: str, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Smart property query with single database call using OR condition.
    
    Features:
    - Single optimized SQL query
    - Fuzzy location matching via OR conditions
    - Budget flexibility (up to 10% buffer)
    - Property type expansion via OR conditions
    """
    def _execute_query():
        with supabase_timeout_context(15):  # 15 second timeout for queries
            client = _ensure_supabase()

            # Smart location variations - limited to avoid huge queries
            location_variations = _get_location_variations(location)[:3]  # Max 3 locations
            max_budget = budget * 1.1
            property_variations = _get_property_type_variations(property_type)[:3]  # Max 3 types
            
            logger.info(f"🏠 Smart single-query search: location={location_variations}, budget≤${max_budget:,}, types={property_variations}")

            # Simple and efficient: Get ALL properties under budget, filter in memory
            response = (
                client.table("properties")
                .select("*")
                .lte("price", int(max_budget))
                .execute()
            )
            
            logger.info(f"📊 Single query completed: {len(response.data or [])} total results")
            
            # Filter in memory for location and type (much faster!)
            all_properties = response.data or []
            filtered_properties = []
            
            if all_properties and (location_variations or property_variations):
                logger.info(f"🔍 Filtering {len(all_properties)} properties for smart match...")
                
                # Debug: Show what exists
                logger.info(f"🏠 Available properties:")
                for prop in all_properties[:3]:  # Show first 3 for debugging
                    logger.info(f"   - {prop.get('address', 'N/A')} | {prop.get('location', 'N/A')} | {prop.get('property_type', 'N/A')} | ${prop.get('price', 'N/A')}")
                
                for prop in all_properties:
                    prop_location = prop.get('location', '').lower()
                    prop_type = prop.get('property_type', '').lower()
                    
                    # Check location match (very flexible)
                    location_match = False
                    if location_variations:
                        for loc in location_variations:
                            if loc.replace(' ', '') in prop_location.replace(' ', '') or prop_location.replace(' ', '') in loc.replace(' ', ''):
                                location_match = True
                                break
                    else:
                        location_match = True
                    
                    # Check property type match (very flexible)  
                    type_match = False
                    if property_variations:
                        for ptype in property_variations:
                            if ptype.replace(' ', '') in prop_type.replace(' ', '') or prop_type.replace(' ', '') in ptype.replace(' ', ''):
                                type_match = True
                                break
                    else:
                        type_match = True
                    
                    if location_match and type_match:
                        filtered_properties.append(prop)
                        logger.info(f"✅ Matched: {prop.get('address', 'N/A')} in {prop_location} (Type: {prop_type})")
                        if len(filtered_properties) >= 5:  # Early exit if we have good matches
                            break
            
            logger.info(f"🎯 Filtered to {len(filtered_properties)} relevant properties")
            return filtered_properties[:10]  # Limit to top 10

            # Remove duplicates by MLS ID and sort by relevance
            unique_properties = {}
            for prop in all_properties:
                mls_id = prop.get('mls_id')
                if mls_id and mls_id not in unique_properties:
                    # Calculate relevance score
                    prop['relevance_score'] = _calculate_relevance_score(prop, location, budget)
                    unique_properties[mls_id] = prop

            # Sort by relevance score (closest to budget + location match)
            sorted_properties = sorted(unique_properties.values(), key=lambda x: (
                x['relevance_score']['budget_score'],
                x['relevance_score']['location_score']
            ), reverse=True)

            # Limit to top 10 results
            return sorted_properties[:10]

    try:
        properties = supabase_circuit_breaker.call(_execute_query)
        logger.info(f"✅ Smart search completed: {len(properties)} results - SINGLE QUERY!")
        return properties

    except Exception as e:
        error_msg = f"Smart property query error: {str(e)}"
        logger.error(error_msg)
        return []

def _get_location_variations(location: str) -> List[str]:
    """Get smart location variations including nearby areas"""
    if not location:
        return []
    
    base_location = location.strip().lower()
    variations = [base_location]
    
    # Predefined location mappings for Florida (extend as needed)
    location_mappings = {
        'miami': ['miami beach', 'brickell', 'downtown miami', 'coconut grove', 'key biscayne'],
        'miami beach': ['miami', 'south beach', 'brickell', 'downtown miami'],
        'fort lauderdale': ['dania beach', 'hollywood', 'pompano beach', 'deerfield beach'],
        'boca raton': ['delray beach', 'boynton beach', 'palm beach'],
        'tampa': ['st. petersburg', 'clearwater', 'brandon', 'lutz'],
        'orlando': ['kissimmee', 'winter park', 'lake mary', 'altamonte springs'],
        'west palm beach': ['palm beach', 'lake worth', 'boynton beach', 'jupiter'],
        'jacksonville': ['neptune beach', 'atlantic beach', 'st. augustine'],
        'naples': ['marco island', 'bonita springs', 'estero'],
        'sarasota': ['bradenton', 'longboat key', 'venice']
    }
    
    # Add mapping variations
    for key, values in location_mappings.items():
        if key in base_location:
            variations.extend(values)
        elif base_location in [v.lower() for v in values]:
            variations.append(key)
            variations.extend(values)
    
    # Add plural/singular variations
    if base_location.endswith('s'):
        variations.append(base_location[:-1])  # Remove 's'
    else:
        variations.append(base_location + 's')  # Add 's'
    
    # Remove duplicates and preserve original variations first
    unique_variations = list(dict.fromkeys([base_location] + variations))
    return unique_variations[:8]  # Limit to avoid too many queries

def _get_property_type_variations(property_type: str) -> List[str]:
    """Get property type variations for better matching"""
    if not property_type:
        return ['']  # Search all types if not specified
    
    prop_type = property_type.strip().lower()
    variations = [prop_type]
    
    # Typo corrections and variations
    type_mappings = {
        'condo': ['condominium', 'apartment', 'apt', 'unit'],
        'house': ['home', 'single family', 'residence', 'detached'],
        'townhouse': ['town home', 'row house', 'linked'],
        'villa': ['luxury home', 'estate'],
        'apt': ['apartment', 'condo', 'unit'],
        'apartment': ['apt', 'condo', 'unit'],
        'studio': ['efficiency', 'bachelor'],
        'loft': ['open concept']
    }
    
    for key, values in type_mappings.items():
        if key in prop_type:
            variations.extend(values)
        elif prop_type in values:
            variations.append(key)
            variations.extend(values)
    
    return list(dict.fromkeys(variations))

def _calculate_relevance_score(property_data: Dict[str, Any], search_location: str, search_budget: int) -> Dict[str, float]:
    """Calculate relevance score for property sorting"""
    price = property_data.get('price', 0)
    location = property_data.get('location', '').lower()
    
    # Budget score: closer to budget = higher score
    if price <= search_budget:
        budget_ratio = price / search_budget
        budget_score = 1.0 - (budget_ratio * 0.5)  # Best score at lowest price
    else:
        # Over budget properties get lower scores
        over_ratio = (price - search_budget) / search_budget
        budget_score = max(0.2, 0.5 - over_ratio)
    
    # Location score: exact match gets highest score
    search_loc = search_location.lower()
    if search_loc in location and location.startswith(search_loc):
        location_score = 1.0
    elif search_loc in location:
        location_score = 0.8
    elif any(word in location for word in search_loc.split()):
        location_score = 0.6
    else:
        location_score = 0.3
    
    return {
        'budget_score': budget_score,
        'location_score': location_score,
        'total_score': (budget_score + location_score) / 2
    }


def get_lead_history(lead_id: str) -> List[Dict[str, Any]]:
    """
    Get conversation history for a lead from Supabase.
    Includes circuit breaker protection and timeout handling.

    Args:
        lead_id: ID of the lead

    Returns:
        List of conversation history entries, or empty list on failure
    """
    def _execute_query():
        with supabase_timeout_context(10):
            client = _ensure_supabase()
            response = client.table("leads").select("history").eq("id", lead_id).execute()
            if response.data and len(response.data) > 0:
                history = response.data[0].get("history") or []
                # Normalize timestamps to ISO strings if needed
                normalized = []
                for entry in history:
                    if isinstance(entry, dict):
                        ts = entry.get("timestamp")
                        if isinstance(ts, datetime):
                            entry["timestamp"] = ts.isoformat()
                        normalized.append(entry)
                    else:
                        normalized.append(entry)
                return normalized
            return []

    try:
        history = supabase_circuit_breaker.call(_execute_query)
        logger.debug(f"Retrieved lead history for {lead_id}: {len(history)} entries")
        return history
    except Exception as e:
        error_msg = f"Supabase get_lead_history error: {str(e)}"
        logger.error(error_msg, extra={'lead_id': lead_id})
        return []


def save_lead(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save or update lead information in Supabase for Instagram DM automation.
    Includes circuit breaker protection, timeout handling, and retry logic.

    Args:
        lead_data: Dictionary containing lead information

    Returns:
        Saved lead data, or empty dict on failure
    """
    def _execute_save():
        with supabase_timeout_context(20):  # Longer timeout for write operations
            client = _ensure_supabase()

            # Normalize datetime fields to ISO strings for storage
            def _normalize(v):
                if isinstance(v, datetime):
                    return v.isoformat()
                return v

            normalized_lead = json.loads(json.dumps(lead_data, default=_normalize))

            # Validate channel value before database operations
            if "channel" in normalized_lead:
                valid_channels = {'instagram', ' ', 'web', 'email', ' '}
                if normalized_lead["channel"] not in valid_channels:
                    logger.warning(f"Invalid channel value '{normalized_lead['channel']}' in save_lead. Defaulting to 'instagram'")
                    normalized_lead["channel"] = "instagram"
            else:
                # Ensure channel has a default value
                normalized_lead["channel"] = "instagram"

            # No company_id needed for Instagram DM automation
            # Use instagram_id as primary identifier

            # Check if lead exists by instagram_id first (primary deduplication field)
            instagram_id = normalized_lead.get("instagram_id") or normalized_lead.get("user_id")
            if instagram_id and "id" not in normalized_lead:
                # Try to find existing lead by instagram_id first
                query = client.table("leads").select("id, user_id, instagram_id, name")
                existing_instagram = query.eq("instagram_id", instagram_id).execute()
                
                if existing_instagram.data and len(existing_instagram.data) > 0:
                    # Found existing lead by instagram_id - use it for update
                    existing_lead = existing_instagram.data[0]
                    normalized_lead["id"] = existing_lead["id"]
                    # Ensure we maintain the instagram_id field
                    if "instagram_id" not in normalized_lead:
                        normalized_lead["instagram_id"] = instagram_id
                    # Ensure user_id is set properly
                    if "user_id" not in normalized_lead:
                        normalized_lead["user_id"] = existing_lead.get("user_id") or instagram_id
                    logger.debug(f"Updating existing lead by instagram_id {instagram_id}: {normalized_lead['id']}")
                else:
                    # Fallback to legacy user_id search
                    query = client.table("leads").select("id").eq("user_id", instagram_id)
                    existing_legacy = query.execute()
                    
                    if existing_legacy.data and len(existing_legacy.data) > 0:
                        # Found existing lead by user_id - migrate to instagram_id
                        existing_lead = existing_legacy.data[0]
                        normalized_lead["id"] = existing_lead["id"]
                        normalized_lead["instagram_id"] = instagram_id  # Add the instagram_id field
                        logger.debug(f"Updating existing legacy lead {existing_lead['id']} with instagram_id {instagram_id}")
                    else:
                        # New lead - ensure instagram_id is set
                        normalized_lead["instagram_id"] = instagram_id
                        logger.debug(f"Creating new lead with instagram_id: {instagram_id}")
                        
                        # Use extracted name if available, fallback to Instagram username
                        if not normalized_lead.get("name") and normalized_lead.get("instagram_username"):
                            normalized_lead["name"] = normalized_lead["instagram_username"]

            response = client.table("leads").upsert(normalized_lead).execute()
            return response.data[0] if response.data else {}

    try:
        result = supabase_circuit_breaker.call(_execute_save)
        logger.info(f"Lead saved successfully: {result.get('id', 'unknown')}")
        return result
    except Exception as e:
        error_msg = f"Supabase save_lead error: {str(e)}"
        logger.error(error_msg, extra={
            'lead_data_keys': list(lead_data.keys()) if lead_data else None,
            'user_id': lead_data.get('user_id') if lead_data else None,
            'instagram_id': lead_data.get('instagram_id') if lead_data else None
        })
        return {}


def save_or_update_lead(instagram_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert lead with proper deduplication by instagram_id for Instagram DM automation.
    This function prevents duplicate prospect creation by using instagram_id as the primary key.

    Args:
        instagram_id: Instagram user ID (Meta PSID) for deduplication
        lead_data: Dictionary containing lead information

    Returns:
        Saved lead data with is_new flag, or empty dict on failure
    """
    def _execute_upsert():
        with supabase_timeout_context(20):
            client = _ensure_supabase()

            # Normalize datetime fields to ISO strings for storage
            def _normalize(v):
                if isinstance(v, datetime):
                    return v.isoformat()
                return v

            normalized_lead = json.loads(json.dumps(lead_data, default=_normalize))

            # Validate channel value before database operations
            if "channel" in normalized_lead:
                valid_channels = {'instagram', ' ', 'web', 'email', ' '}
                if normalized_lead["channel"] not in valid_channels:
                    logger.warning(f"Invalid channel value '{normalized_lead['channel']}' for instagram_id {instagram_id}. Defaulting to 'instagram'")
                    normalized_lead["channel"] = "instagram"
            else:
                # Ensure channel has a default value
                normalized_lead["channel"] = "instagram"

            # No company_id needed for Instagram DM automation
            # Use name + instagram_id as primary identifiers

            # Always set the instagram_id for deduplication
            normalized_lead["instagram_id"] = instagram_id
            normalized_lead["user_id"] = instagram_id  # Maintain backward compatibility

            # Check if lead exists by instagram_id
            existing = client.table("leads")\
                .select("id, status, history, created_at")\
                .eq("instagram_id", instagram_id)\
                .execute()

            is_new_lead = False
            if existing.data and len(existing.data) > 0:
                # Update existing lead
                existing_lead = existing.data[0]
                lead_id = existing_lead["id"]
                
                # Preserve important fields that shouldn't be overwritten
                preserved_fields = {
                    "created_at": existing_lead.get("created_at"),
                }
                
                # Merge history if it exists
                existing_history = existing_lead.get("history", [])
                new_history = normalized_lead.get("history", [])
                
                if new_history and existing_history:
                    # Combine histories, avoiding duplicates
                    combined_history = existing_history.copy()
                    for new_entry in new_history:
                        # Simple duplicate check by timestamp and message
                        is_duplicate = False
                        for existing_entry in combined_history:
                            if (existing_entry.get("timestamp") == new_entry.get("timestamp") and
                                existing_entry.get("message") == new_entry.get("message")):
                                is_duplicate = True
                                break
                        if not is_duplicate:
                            combined_history.append(new_entry)
                    normalized_lead["history"] = combined_history
                elif new_history:
                    normalized_lead["history"] = new_history
                elif existing_history:
                    normalized_lead["history"] = existing_history

                # Update the lead
                normalized_lead["id"] = lead_id
                # Don't set updated_at - it's auto-managed by database trigger
                
                # Merge preserved fields
                for key, value in preserved_fields.items():
                    if key not in normalized_lead:
                        normalized_lead[key] = value

                logger.info(f"Updating existing lead {lead_id} for instagram_id {instagram_id}")
            else:
                # Create new lead
                is_new_lead = True
                normalized_lead["created_at"] = normalized_lead.get("created_at", datetime.now().isoformat())
                # Don't set updated_at - it's auto-managed by database trigger
                
                logger.info(f"Creating new lead for instagram_id {instagram_id}")

            # Perform the upsert
            response = client.table("leads").upsert(normalized_lead).execute()
            
            if response.data and len(response.data) > 0:
                result = response.data[0]
                result["is_new"] = is_new_lead  # Add flag to indicate if this was a new lead
                return result
            else:
                return {}

    try:
        result = supabase_circuit_breaker.call(_execute_upsert)
        if result:
            action = "created" if result.get("is_new", False) else "updated"
            logger.info(f"Lead {action} successfully: {result.get('id', 'unknown')} for instagram_id {instagram_id}")
        return result
    except Exception as e:
        error_msg = f"Supabase save_or_update_lead error: {str(e)}"
        logger.error(error_msg, extra={
            'instagram_id': instagram_id,
            'lead_data_keys': list(lead_data.keys()) if lead_data else None
        })
        return {}


def get_config(key: str, default_value: str = "") -> str:
    """
    Get a configuration value from the Supabase database.
    Includes circuit breaker protection and timeout handling.

    Args:
        key: Configuration key
        default_value: Default value if key is not found

    Returns:
        Configuration value or default value
    """
    def _execute_query():
        with supabase_timeout_context(10):
            client = _ensure_supabase()
            response = client.table("configs").select("value").eq("key", key).execute()
            if response.data:
                return response.data[0].get("value", default_value)
            else:
                return default_value

    try:
        result = supabase_circuit_breaker.call(_execute_query)
        logger.debug(f"Config retrieved for key '{key}': {len(result) if result != default_value else 'default'}")
        return result
    except Exception as e:
        error_msg = f"Supabase get_config error for key '{key}': {str(e)}"
        logger.error(error_msg, extra={'key': key})
        return default_value


def set_auth_context(user_context: Optional[Dict[str, Any]]) -> None:
    """
    Set the current authentication context for database operations.

    Args:
        user_context: User authentication context or None to clear
    """
    global _current_user_context
    _current_user_context = user_context


def get_auth_context() -> Optional[Dict[str, Any]]:
    """
    Get the current authentication context.

    Returns:
        Current user context or None if not authenticated
    """
    return _current_user_context


def get_instagram_user_mapping(instagram_user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get secure mapping from Instagram user ID to Supabase authenticated user.
    Includes circuit breaker protection and timeout handling.

    Args:
        instagram_user_id: Instagram user ID (PSID)

    Returns:
        User mapping data or None if not found
    """
    def _execute_query():
        with supabase_timeout_context(10):
            client = _ensure_supabase()
            response = client.table("instagram_user_mappings")\
                .select("user_id, company_id, created_at, is_active")\
                .eq("instagram_user_id", instagram_user_id)\
                .eq("is_active", True)\
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

    try:
        result = supabase_circuit_breaker.call(_execute_query)
        logger.debug(f"Instagram user mapping retrieved for {instagram_user_id}")
        return result
    except Exception as e:
        logger.error(f"Error getting Instagram user mapping for {instagram_user_id}: {str(e)}")
        return None


def create_instagram_user_mapping(instagram_user_id: str, user_id: str, company_id: Optional[str] = None) -> bool:
    """
    Create secure mapping from Instagram user to authenticated Supabase user.
    Includes circuit breaker protection and timeout handling.

    Args:
        instagram_user_id: Instagram user ID (PSID)
        user_id: Supabase authenticated user ID
        company_id: Optional company ID for multi-tenant context

    Returns:
        True if successful, False otherwise
    """
    def _execute_operation():
        with supabase_timeout_context(15):
            client = _ensure_supabase()

            # Check if mapping already exists
            existing = client.table("instagram_user_mappings")\
                .select("id")\
                .eq("instagram_user_id", instagram_user_id)\
                .eq("is_active", True)\
                .execute()

            if existing.data:
                # Update existing mapping
                result = client.table("instagram_user_mappings")\
                    .update({
                        "user_id": user_id,
                        "company_id": company_id,
                        "updated_at": "now()"
                    })\
                    .eq("instagram_user_id", instagram_user_id)\
                    .eq("is_active", True)\
                    .execute()
            else:
                # Create new mapping
                result = client.table("instagram_user_mappings")\
                    .insert({
                        "instagram_user_id": instagram_user_id,
                        "user_id": user_id,
                        "company_id": company_id,
                        "is_active": True,
                        "created_at": "now()"
                    })\
                    .execute()

            return bool(result.data)

    try:
        result = supabase_circuit_breaker.call(_execute_operation)
        logger.info(f"Instagram user mapping created/updated for {instagram_user_id}")
        return result
    except Exception as e:
        logger.error(f"Error creating Instagram user mapping for {instagram_user_id}: {str(e)}")
        return False


def validate_user_access(user_id: str, company_id: Optional[str] = None, resource: str = "leads") -> bool:
    """
    Validate user has access to perform operations on a resource.
    Includes circuit breaker protection and timeout handling.

    Args:
        user_id: Supabase user ID
        company_id: Optional company ID for multi-tenant validation
        resource: Resource being accessed

    Returns:
        True if access is granted, False otherwise
    """
    def _execute_validation():
        with supabase_timeout_context(10):
            if not user_id:
                return False

            client = _ensure_supabase()

            # For company-scoped resources, verify user belongs to company
            if company_id and resource in ["leads", "properties", "configs"]:
                user_company = client.table("company_users")\
                    .select("role, is_active")\
                    .eq("user_id", user_id)\
                    .eq("company_id", company_id)\
                    .eq("is_active", True)\
                    .execute()

                if not user_company.data:
                    logger.warning(f"User {user_id} attempted access to company {company_id} resource {resource} without membership")
                    return False

                # Check if user has appropriate role for the operation
                user_role = user_company.data[0]["role"]
                if resource == "leads" and user_role not in ["viewer", "member", "admin", "owner"]:
                    return False
                elif resource in ["properties", "configs"] and user_role not in ["member", "admin", "owner"]:
                    return False

            return True

    try:
        result = supabase_circuit_breaker.call(_execute_validation)
        logger.debug(f"User access validation for {user_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error validating user access for {user_id}: {str(e)}")
        return False

def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get the current status of the Supabase circuit breaker for monitoring.

    Returns:
        Dictionary with circuit breaker status information
    """
    return {
        "state": supabase_circuit_breaker.state,
        "failure_count": supabase_circuit_breaker.failure_count,
        "last_failure_time": supabase_circuit_breaker.last_failure_time,
        "recovery_timeout": supabase_circuit_breaker.recovery_timeout
    }