"""
Waitlist Manager for Self-Driving Booking Ops 2.0

Implements waitlist backfill system for no-show recovery with ranked candidates,
guardrails, and fairness rotation to maximize booking utilization.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.lead_scoring import LeadScoringSystem
from backend.utils.response_tracker import ResponseTimeTracker
from backend.communication.multi_channel_manager import MultiChannelManager
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

class WaitlistManager:
    """
    Waitlist backfill system for recovering no-show slots.
    
    Maintains ranked waitlist of qualified leads and attempts backfill
    with guardrails for fairness, frequency limits, and notice requirements.
    """

    def __init__(self):
        self.redis_client = redis_client
        self.scoring_system = LeadScoringSystem()
        self.response_tracker = ResponseTimeTracker()
        self.multi_channel = MultiChannelManager()

    def add_to_waitlist(
        self,
        lead_id: str,
        service: str,
        location: str,
        fit_score: float,
        responsiveness_score: float
    ) -> bool:
        """
        Add lead to waitlist for backfill opportunities.
        
        Args:
            lead_id: Lead identifier
            service: Service type (tour, consultation, etc.)
            location: Service location
            fit_score: Lead fit score from qualification
            responsiveness_score: Response time score
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            waitlist_entry = {
                'lead_id': lead_id,
                'service': service,
                'location': location,
                'fit_score': fit_score,
                'responsiveness_score': responsiveness_score,
                'composite_score': fit_score * responsiveness_score,
                'backfill_attempts': 0,
                'last_contacted_at': None,
                'created_at': datetime.now().isoformat()
            }

            # Store in database
            success = self._persist_waitlist_entry(waitlist_entry)

            if success:
                audit_log_event("waitlist_added", {
                    "lead_id": lead_id,
                    "service": service,
                    "location": location,
                    "composite_score": waitlist_entry['composite_score']
                })

            return success

        except Exception as e:
            logger.error(f"Error adding {lead_id} to waitlist: {e}")
            return False

    def trigger_backfill(self, slot_time: datetime, service: str, location: str) -> Dict[str, Any]:
        """
        Trigger waitlist backfill for a no-show slot.
        
        Args:
            slot_time: The slot time that became available
            service: Service type
            location: Service location
            
        Returns:
            Dict with backfill attempt results
        """
        try:
            # Query eligible candidates
            candidates = self._query_eligible_candidates(service, location, slot_time)

            if not candidates:
                return {
                    "status": "no_candidates",
                    "slot_time": slot_time.isoformat(),
                    "service": service,
                    "location": location
                }

            # Sort by composite score (descending)
            candidates.sort(key=lambda x: x['composite_score'], reverse=True)

            # Attempt backfill with top candidates
            backfill_results = []
            max_attempts = min(len(candidates), 5)  # Max 5 attempts

            for candidate in candidates[:max_attempts]:
                result = self.attempt_backfill_for_candidate(
                    candidate['lead_id'],
                    slot_time
                )
                backfill_results.append(result)

                if result.get('status') == 'accepted':
                    # Stop after first acceptance
                    break

            # Store backfill attempt results
            self._store_backfill_results(slot_time, backfill_results)

            audit_log_event("backfill_triggered", {
                "slot_time": slot_time.isoformat(),
                "service": service,
                "location": location,
                "candidates_found": len(candidates),
                "attempts_made": len(backfill_results),
                "successful_backfills": sum(1 for r in backfill_results if r.get('status') == 'accepted')
            })

            return {
                "status": "backfill_attempted",
                "slot_time": slot_time.isoformat(),
                "candidates_found": len(candidates),
                "attempts_made": len(backfill_results),
                "results": backfill_results
            }

        except Exception as e:
            logger.error(f"Error triggering backfill for {slot_time}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def attempt_backfill_for_candidate(self, lead_id: str, slot_time: datetime) -> Dict[str, Any]:
        """
        Attempt backfill offer for a specific candidate.
        
        Args:
            lead_id: Candidate lead ID
            slot_time: Available slot time
            
        Returns:
            Dict with attempt result
        """
        try:
            # Check guardrails
            if not self._check_backfill_guardrails(lead_id, slot_time):
                return {
                    "lead_id": lead_id,
                    "status": "guardrail_failed",
                    "slot_time": slot_time.isoformat()
                }

            # Get lead data for fit calculation
            lead_data = self._get_lead_data(lead_id)
            if not lead_data:
                return {
                    "lead_id": lead_id,
                    "status": "lead_not_found",
                    "slot_time": slot_time.isoformat()
                }

            # Calculate updated fit score
            slot_context = {
                'service': 'backfill_offer',
                'slot_time': slot_time,
                'urgency': 'immediate'
            }
            current_fit_score = self.calculate_fit_score(lead_data, slot_context)

            # Generate idempotency key for this backfill attempt
            from uuid import uuid4
            idempotency_key = str(uuid4())

            # Send backfill offer
            offer_result = self._send_backfill_offer(lead_id, slot_time, idempotency_key)

            # Record attempt
            self._record_backfill_attempt({
                'lead_id': lead_id,
                'slot_time': slot_time,
                'idempotency_key': idempotency_key,
                'fit_score': current_fit_score,
                'offer_sent': offer_result.get('success', False),
                'attempted_at': datetime.now()
            })

            return {
                "lead_id": lead_id,
                "status": "offered" if offer_result.get('success') else "send_failed",
                "slot_time": slot_time.isoformat(),
                "fit_score": current_fit_score,
                "idempotency_key": idempotency_key
            }

        except Exception as e:
            logger.error(f"Error attempting backfill for {lead_id}: {e}")
            return {
                "lead_id": lead_id,
                "status": "error",
                "error": str(e)
            }

    def calculate_fit_score(self, lead_data: Dict[str, Any], slot_context: Dict[str, Any]) -> float:
        """
        Calculate updated fit score for backfill opportunity.
        
        Args:
            lead_data: Lead qualification data
            slot_context: Slot and service context
            
        Returns:
            Fit score between 0.0 and 1.0
        """
        try:
            # Use existing scoring system with backfill context
            base_score = lead_data.get('qualification_score', 0.5)

            # Adjust for backfill urgency
            urgency_multiplier = 1.2 if slot_context.get('urgency') == 'immediate' else 1.0

            # Adjust for time sensitivity
            slot_time = slot_context.get('slot_time')
            if isinstance(slot_time, datetime):
                hours_until_slot = (slot_time - datetime.now()).total_seconds() / 3600
                if hours_until_slot < 24:
                    time_multiplier = 1.1  # Premium for same-day
                elif hours_until_slot < 48:
                    time_multiplier = 1.05  # Slight premium for next-day
                else:
                    time_multiplier = 1.0
            else:
                time_multiplier = 1.0

            fit_score = min(base_score * urgency_multiplier * time_multiplier, 1.0)

            return fit_score

        except Exception as e:
            logger.warning(f"Error calculating fit score: {e}")
            return 0.5

    def calculate_responsiveness_score(self, lead_id: str) -> float:
        """
        Calculate responsiveness score from response time history.
        
        Args:
            lead_id: Lead identifier
            
        Returns:
            Responsiveness score between 0.0 and 1.0
        """
        try:
            # Get response time score from tracker
            response_score = self.response_tracker.get_urgency_score(lead_id)
            return response_score if response_score is not None else 0.5

        except Exception as e:
            logger.warning(f"Error calculating responsiveness score for {lead_id}: {e}")
            return 0.5

    def _query_eligible_candidates(
        self,
        service: str,
        location: str,
        slot_time: datetime
    ) -> List[Dict[str, Any]]:
        """Query waitlist for eligible backfill candidates."""
        try:
            from utils.supabase_client import supabase

            # Calculate minimum notice time (24 hours default)
            min_notice_time = datetime.now() + timedelta(hours=24)

            # Query candidates with guardrail filters
            result = supabase.table("waitlist").select("*").eq("service", service).eq("location", location).execute()

            candidates = []
            for candidate in result.data or []:
                # Check notice time guardrail
                if slot_time < min_notice_time:
                    continue

                # Check contact frequency (max 2 per day)
                last_contacted = candidate.get('last_contacted_at')
                if last_contacted:
                    last_contact = datetime.fromisoformat(last_contacted)
                    if (datetime.now() - last_contact).days < 1:
                        contact_count = self._get_daily_contact_count(candidate['lead_id'])
                        if contact_count >= 2:
                            continue

                # Check max attempts (3 per candidate)
                if candidate.get('backfill_attempts', 0) >= 3:
                    continue

                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error querying waitlist candidates: {e}")
            return []

    def _check_backfill_guardrails(self, lead_id: str, slot_time: datetime) -> bool:
        """Check all guardrails for backfill attempt."""
        try:
            # Minimum notice time (24 hours)
            min_notice = datetime.now() + timedelta(hours=24)
            if slot_time < min_notice:
                return False

            # Maximum contacts per day (2)
            daily_contacts = self._get_daily_contact_count(lead_id)
            if daily_contacts >= 2:
                return False

            # Fairness rotation - check if recently contacted
            last_contact = self._get_last_contact_time(lead_id)
            if last_contact:
                hours_since_contact = (datetime.now() - last_contact).total_seconds() / 3600
                if hours_since_contact < 24:  # Minimum 24h between contacts
                    return False

            return True

        except Exception as e:
            logger.warning(f"Error checking guardrails for {lead_id}: {e}")
            return False

    def _send_backfill_offer(self, lead_id: str, slot_time: datetime, idempotency_key: str) -> Dict[str, Any]:
        """Send backfill offer message to candidate."""
        try:
            formatted_time = slot_time.strftime("%I:%M %p on %A, %B %d")

            message = f"""Great news! A slot just opened up for {formatted_time}.

Would you be available for a tour at this time instead? This opportunity won't last long!

Reply 'YES' to confirm or 'NO' if this doesn't work for you."""

            result = self.multi_channel.send_message(
                user_id=lead_id,
                message=message,
                channel='auto',  # Use optimal channel
                priority='urgent',
                message_type='backfill_offer'
            )

            return result

        except Exception as e:
            logger.error(f"Error sending backfill offer to {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    def _persist_waitlist_entry(self, entry: Dict[str, Any]) -> bool:
        """Persist waitlist entry to database."""
        try:
            from utils.supabase_client import supabase

            result = supabase.table("waitlist").upsert(
                entry,
                on_conflict="lead_id,service,location"
            ).execute()

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error persisting waitlist entry: {e}")
            return False

    def _record_backfill_attempt(self, attempt: Dict[str, Any]) -> bool:
        """Record backfill attempt in database."""
        try:
            from utils.supabase_client import supabase

            result = supabase.table("waitlist_attempts").insert(attempt).execute()

            # Update waitlist with attempt count and last contacted
            supabase.table("waitlist").update({
                'backfill_attempts': supabase.rpc('increment', {'table': 'waitlist', 'column': 'backfill_attempts', 'id': attempt['lead_id']}),
                'last_contacted_at': attempt['attempted_at'].isoformat()
            }).eq('lead_id', attempt['lead_id']).execute()

            return True

        except Exception as e:
            logger.error(f"Error recording backfill attempt: {e}")
            return False

    def _store_backfill_results(self, slot_time: datetime, results: List[Dict[str, Any]]) -> None:
        """Store backfill attempt results in Redis."""
        if self.redis_client is None:
            return

        def _store_operation():
            key = f"backfill_state:{slot_time.isoformat()}"
            state = {
                'slot_time': slot_time.isoformat(),
                'attempted_candidates': [r['lead_id'] for r in results],
                'successful_backfills': [r for r in results if r.get('status') == 'accepted'],
                'last_attempt': datetime.now().isoformat()
            }
            self.redis_client.setex(key, 86400, json.dumps(state, default=str))  # 24 hours

        try:
            redis_circuit_breaker.call(_store_operation)
        except Exception as e:
            logger.warning(f"Error storing backfill results: {e}")

    def _get_lead_data(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get lead qualification data."""
        try:
            from utils.supabase_client import supabase
            result = supabase.table("leads").select("*").eq("id", lead_id).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _get_daily_contact_count(self, lead_id: str) -> int:
        """Get number of contacts today for fairness rotation."""
        try:
            from utils.supabase_client import supabase
            today_start = datetime.now().replace(hour=0, minute=0, second=0)

            result = supabase.table("waitlist_attempts").select("id", count="exact").eq("lead_id", lead_id).gte("attempted_at", today_start.isoformat()).execute()

            return result.count or 0
        except Exception:
            return 0

    def _get_last_contact_time(self, lead_id: str) -> Optional[datetime]:
        """Get last contact time for this lead."""
        try:
            from utils.supabase_client import supabase
            result = supabase.table("waitlist").select("last_contacted_at").eq("lead_id", lead_id).execute()

            if result.data and result.data[0].get('last_contacted_at'):
                return datetime.fromisoformat(result.data[0]['last_contacted_at'])
            return None
        except Exception:
            return None
