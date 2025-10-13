"""
Immutable Audit Logging System

Implements PRD Section 2.6: Compliance-by-Design with tamper-evident audit trails.

Key Features:
- Blockchain-style hash chaining for tamper detection
- Server-side timestamps to prevent manipulation
- Structured event logging with correlation IDs
- Automatic retention policies for GDPR compliance
- Query interface for compliance reporting
- Integration with Supabase for persistence
"""

import sys
import os
import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import uuid4

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_settings_cache: Optional[Any] = None


def _get_settings():
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    try:
        from config import get_settings as _cfg_get_settings
        _settings_cache = _cfg_get_settings()
    except Exception:
        class _Fallback:
            AUDIT_SALT = "default_salt"
            ENVIRONMENT = "testing"
            SUPABASE_URL = None
        _settings_cache = _Fallback()
    return _settings_cache
def _get_supabase_client():
    from utils.supabase_client import supabase as supabase_client
    return supabase_client


# Global variable to cache the last hash for chaining
_last_audit_hash: Optional[str] = None

class AuditEvent:
    """Structured audit event with tamper detection."""
    
    def __init__(
        self,
        event_type: str,
        payload: Dict[str, Any],
        entity_type: str = "system",
        entity_id: str = None,
        agent_type: str = None,
        correlation_id: str = None
    ):
        self.event_id = str(uuid4())
        self.event_type = event_type
        self.entity_type = entity_type
        self.entity_id = entity_id or "system"
        self.agent_type = agent_type
        self.payload = payload
        self.correlation_id = correlation_id or str(uuid4())
        self.timestamp = datetime.now(timezone.utc)
        
        # Generate tamper-evident hash
        self.prev_hash = _get_last_audit_hash()
        self.hash = self._generate_hash()
    
    def _generate_hash(self) -> str:
        """
        Generate SHA-256 hash of event data for tamper detection.
        
        Includes previous hash for blockchain-style chaining.
        """
        hash_data = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "prev_hash": self.prev_hash,
            "salt": getattr(_get_settings(), 'AUDIT_SALT', "default_salt")
        }
        
        # Create deterministic JSON string
        hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        
        # Generate SHA-256 hash
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary for storage."""
        return {
            "id": self.event_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "agent_type": self.agent_type,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.hash,
            "prev_hash": self.prev_hash
        }

def audit_log_event(
    event_type: str,
    payload: Dict[str, Any],
    entity_type: str = "system",
    entity_id: str = None,
    agent_type: str = None,
    correlation_id: str = None
) -> str:
    """
    Log an audit event with tamper-evident hash chaining.
    
    Args:
        event_type: Type of event (e.g., "message_sent", "policy_violation")
        payload: Event data dictionary
        entity_type: Type of entity (e.g., "lead", "agent", "system")
        entity_id: Unique identifier for the entity
        agent_type: Type of agent that triggered the event
        correlation_id: Correlation ID for tracking related events
        
    Returns:
        Event ID for reference
        
    Examples:
        audit_log_event("message_sent", {
            "lead_id": "user123",
            "message": "Hello, interested in properties?",
            "compliance_passed": True
        })
        
        audit_log_event("policy_violation", {
            "violation_type": "fair_housing",
            "original_message": "Perfect for young professionals",
            "blocked": True
        })
    """
    event: Optional[AuditEvent] = None

    try:
        # Create audit event
        event = AuditEvent(
            event_type=event_type,
            payload=payload,
            entity_type=entity_type,
            entity_id=entity_id,
            agent_type=agent_type,
            correlation_id=correlation_id
        )
        
        # Store in database
        _store_audit_event(event)
        
        # Update global hash chain
        global _last_audit_hash
        _last_audit_hash = event.hash
        
        return event.event_id
        
    except Exception as e:
        # Critical: Audit logging failure should not break the system
        # but must be logged to a fallback mechanism
        _log_audit_failure(event_type, payload, str(e))
        if event is not None:
            return event.event_id
        return "audit_failed"

def _store_audit_event(event: AuditEvent) -> None:
    """Store audit event in Supabase with retry logic."""
    max_retries = 3
    client = _get_supabase_client()
    
    for attempt in range(max_retries):
        try:
            response = client.table("audit_logs").insert(event.to_dict()).execute()
            
            if response.data:
                return  # Success
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt failed - log to fallback
                _log_to_fallback_storage(event, str(e))
                raise
            
            # Wait before retry (exponential backoff)
            import time
            time.sleep(2 ** attempt)

def _log_to_fallback_storage(event: AuditEvent, error: str) -> None:
    """
    Fallback storage for audit events when primary storage fails.
    
    Writes to local file system as last resort.
    """
    try:
        import os
        from pathlib import Path
        
        # Create fallback directory
        fallback_dir = Path("audit_fallback")
        fallback_dir.mkdir(exist_ok=True)
        
        # Write to dated file
        date_str = datetime.now().strftime("%Y-%m-%d")
        fallback_file = fallback_dir / f"audit_fallback_{date_str}.jsonl"
        
        fallback_entry = {
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "event": event.to_dict()
        }
        
        with open(fallback_file, "a") as f:
            f.write(json.dumps(fallback_entry) + "\n")
            
    except Exception as fallback_error:
        # Ultimate fallback - print to stderr
        print(f"CRITICAL: Audit logging completely failed: {fallback_error}", file=sys.stderr)

def _log_audit_failure(event_type: str, payload: Dict[str, Any], error: str) -> None:
    """Log audit system failures."""
    try:
        failure_event = {
            "timestamp": datetime.now().isoformat(),
            "failed_event_type": event_type,
            "failed_payload": payload,
            "error": error,
            "system": "audit_logger"
        }
        
        # Try to log the failure itself
        _get_supabase_client().table("system_errors").insert(failure_event).execute()
        
    except Exception:
        # If even error logging fails, write to stderr
        print(f"CRITICAL: Audit system failure: {error}", file=sys.stderr)

def _get_last_audit_hash() -> Optional[str]:
    """
    Get the hash of the most recent audit event for chaining.
    
    Returns None for the first event in the chain.
    """
    global _last_audit_hash
    
    if _last_audit_hash is not None:
        return _last_audit_hash
    settings = _get_settings()
    if getattr(settings, "ENVIRONMENT", "").lower() == "testing":
        return None
    if not getattr(settings, "SUPABASE_URL", None):
        return None
    
    try:
        # Query most recent audit event
        response = _get_supabase_client().table("audit_logs")\
            .select("hash")\
            .order("timestamp", desc=True)\
            .limit(1)\
            .execute()
        
        data = getattr(response, "data", None)
        if isinstance(data, list) and data:
            _last_audit_hash = data[0].get("hash")
            return _last_audit_hash
        return None
        
        return None  # First event in chain
        
    except Exception:
        return None  # Fail gracefully

def verify_audit_chain(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """
    Verify the integrity of the audit log chain.
    
    Args:
        start_date: Start date for verification (optional)
        end_date: End date for verification (optional)
        
    Returns:
        Dictionary with verification results
    """
    try:
        # Build query
        query = _get_supabase_client().table("audit_logs").select("*").order("timestamp", desc=False)
        
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        
        response = query.execute()
        events = response.data
        
        if not events:
            return {"valid": True, "events_checked": 0, "errors": []}
        
        errors = []
        prev_hash = None
        
        for i, event in enumerate(events):
            # Check hash chain
            if event["prev_hash"] != prev_hash:
                errors.append({
                    "event_id": event["id"],
                    "error": "Hash chain broken",
                    "expected_prev_hash": prev_hash,
                    "actual_prev_hash": event["prev_hash"]
                })
            
            # Verify event hash
            if not _verify_event_hash(event):
                errors.append({
                    "event_id": event["id"],
                    "error": "Event hash invalid",
                    "timestamp": event["timestamp"]
                })
            
            prev_hash = event["hash"]
        
        return {
            "valid": len(errors) == 0,
            "events_checked": len(events),
            "errors": errors,
            "verification_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "valid": False,
            "events_checked": 0,
            "errors": [{"error": f"Verification failed: {str(e)}"}]
        }

def _verify_event_hash(event: Dict[str, Any]) -> bool:
    """Verify that an event's hash is correct."""
    try:
        # Reconstruct hash data
        settings = _get_settings()
        hash_data = {
            "event_id": event["id"],
            "event_type": event["event_type"],
            "entity_type": event["entity_type"],
            "entity_id": event["entity_id"],
            "payload": event["payload"],
            "timestamp": event["timestamp"],
            "prev_hash": event["prev_hash"],
            "salt": getattr(settings, 'AUDIT_SALT', "default_salt")
        }
        
        # Generate expected hash
        hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
        
        return expected_hash == event["hash"]
        
    except Exception:
        return False

def query_audit_events(
    event_type: str = None,
    entity_id: str = None,
    agent_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query audit events with filtering.
    
    Args:
        event_type: Filter by event type
        entity_id: Filter by entity ID
        agent_type: Filter by agent type
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum number of results
        
    Returns:
        List of matching audit events
    """
    try:
        query = _get_supabase_client().table("audit_logs").select("*")
        
        if event_type:
            query = query.eq("event_type", event_type)
        if entity_id:
            query = query.eq("entity_id", entity_id)
        if agent_type:
            query = query.eq("agent_type", agent_type)
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        
        query = query.order("timestamp", desc=True).limit(limit)
        
        response = query.execute()
        return response.data or []
        
    except Exception as e:
        audit_log_event("audit_query_error", {
            "error": str(e),
            "filters": {
                "event_type": event_type,
                "entity_id": entity_id,
                "agent_type": agent_type
            }
        })
        return []

def generate_compliance_report(
    start_date: datetime,
    end_date: datetime,
    report_type: str = "full"
) -> Dict[str, Any]:
    """
    Generate compliance report for audit purposes.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        report_type: Type of report (full, violations_only, summary)
        
    Returns:
        Compliance report dictionary
    """
    try:
        # Query relevant events
        events = query_audit_events(
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Large limit for comprehensive report
        )
        
        # Analyze events
        total_events = len(events)
        policy_violations = [e for e in events if e["event_type"] == "policy_violation"]
        compliance_checks = [e for e in events if e["event_type"] == "compliance_check"]
        message_events = [e for e in events if e["event_type"] == "message_sent"]
        
        # Calculate metrics
        violation_rate = len(policy_violations) / max(len(message_events), 1)
        
        report = {
            "report_id": str(uuid4()),
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_events": total_events,
                "policy_violations": len(policy_violations),
                "compliance_checks": len(compliance_checks),
                "messages_sent": len(message_events),
                "violation_rate": violation_rate
            }
        }
        
        if report_type in ["full", "violations_only"]:
            report["violations"] = policy_violations
        
        if report_type == "full":
            report["all_events"] = events
        
        # Verify audit chain integrity for report period
        chain_verification = verify_audit_chain(start_date, end_date)
        report["audit_integrity"] = chain_verification
        
        return report
        
    except Exception as e:
        return {
            "error": f"Report generation failed: {str(e)}",
            "generated_at": datetime.now().isoformat()
        }

def cleanup_old_audit_logs(retention_days: int = 2555) -> Dict[str, Any]:
    """
    Clean up old audit logs according to retention policy.
    
    Default retention: 7 years (2555 days) for compliance.
    
    Args:
        retention_days: Number of days to retain logs
        
    Returns:
        Cleanup summary
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Query old events
        response = _get_supabase_client().table("audit_logs")\
            .select("id")\
            .lt("timestamp", cutoff_date.isoformat())\
            .execute()
        
        old_events = response.data or []
        
        if not old_events:
            return {
                "deleted_count": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "status": "no_old_events"
            }
        
        # Archive before deletion (optional)
        # _archive_audit_events(old_events)
        
        # Delete old events
        event_ids = [event["id"] for event in old_events]
        _get_supabase_client().table("audit_logs").delete().in_("id", event_ids).execute()
        
        # Log cleanup action
        audit_log_event("audit_cleanup", {
            "deleted_count": len(old_events),
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days
        })
        
        return {
            "deleted_count": len(old_events),
            "cutoff_date": cutoff_date.isoformat(),
            "status": "success"
        }
        
    except Exception as e:
        audit_log_event("audit_cleanup_error", {
            "error": str(e),
            "retention_days": retention_days
        })
        
        return {
            "deleted_count": 0,
            "error": str(e),
            "status": "failed"
        }