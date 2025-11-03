"""
HubSpot CRM Integration for Real Estate Lead Management
"""
import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp

import logging

from config import get_settings
from backend.utils.audit import audit_log_event

settings = get_settings()
logger = logging.getLogger(__name__)
from config import get_settings

settings = get_settings()

class HubSpotClient:
    """Enhanced HubSpot API client with Phase 1 AI intent integration"""
    
    def __init__(self):
        self.access_token = settings.HUBSPOT_ACCESS_TOKEN
        self.api_base = settings.HUBSPOT_API_BASE
        self.enabled = bool(self.access_token)
    
    async def create_or_update_contact_with_intent(self, lead_data: Dict[str, Any], intent_analysis: Dict[str, Any]) -> Optional[str]:
        """
        Enhanced contact creation with Phase 1 AI intent analysis integration.
        
        Args:
            lead_data: Lead information dictionary
            intent_analysis: AI intent analysis results from LangGraph
            
        Returns:
            Contact ID if successful, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                # Extract intent signals for CRM enrichment
                intent_category = intent_analysis.get('intent_category', 'unknown')
                intent_score = intent_analysis.get('intent_score', 0.0)
                confidence = intent_analysis.get('confidence', 0.0)
                budget_mentioned = intent_analysis.get('budget_mentioned', False)
                timeline_urgent = intent_analysis.get('timeline_urgent', False)
                booking_signals = intent_analysis.get('booking_signals', False)
                high_intent_indicators = intent_analysis.get('high_intent_indicators', [])
                
                # Phase 1: Enhanced contact properties with intent data
                properties = {
                    # Basic contact info
                    "email": lead_data.get("email", f"{lead_data['user_id']}@instagram.com"),
                    "firstname": lead_data.get("name", "").split()[0] if lead_data.get("name") else "Instagram",
                    "lastname": lead_data.get("name", "").split()[-1] if lead_data.get("name") and len(lead_data.get("name", "").split()) > 1 else "User",
                    "phone": lead_data.get("phone", ""),
                    
                    # Real estate specific fields
                    "budget": lead_data.get("budget", 0),
                    "location": lead_data.get("location", ""),
                    "property_type": lead_data.get("property_type", ""),
                    "lead_source": lead_data.get("channel", "instagram"),
                    "instagram_id": lead_data.get("instagram_id") or lead_data.get("user_id"),
                    
                    # Phase 1: AI Intent Analysis Fields
                    "ai_intent_category": intent_category,
                    "ai_intent_score": round(intent_score, 3),
                    "ai_confidence": round(confidence, 3),
                    "budget_mentioned": "true" if budget_mentioned else "false",
                    "timeline_urgent": "true" if timeline_urgent else "false",
                    "booking_signals": "true" if booking_signals else "false",
                    "high_intent_indicators": ", ".join(high_intent_indicators),
                    
                    # Lead scoring and status
                    "lead_status": lead_data.get("status", "new"),
                    "qualified_score": lead_data.get("qualified_score", 0.0),
                    "intent_processed": "true",
                    "phase_1_enabled": "true",
                    
                    # Lead priority based on intent
                    "lead_priority": self._calculate_lead_priority(intent_category, intent_score, booking_signals),
                    
                    # Lifecycle stage based on intent
                    "lifecyclestage": self._determine_lifecycle_stage(intent_category, intent_score)
                }
                
                # Create or update contact
                url = f"{self.api_base}/crm/v3/objects/contacts"
                payload = {"properties": properties}
                
                logger.info(f"Creating HubSpot contact with AI intent data: {intent_category} "
                          f"(score: {intent_score:.3f}, confidence: {confidence:.3f})")
                
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in [200, 201]:
                        result = await resp.json()
                        contact_id = result.get("id")
                        
                        # Log successful creation with intent details
                        logger.info(f"HubSpot contact created: {contact_id} "
                                  f"with intent category: {intent_category}")
                        
                        return contact_id
                        
                    elif resp.status == 409:  # Contact exists
                        # Search and update existing contact
                        search_url = f"{self.api_base}/crm/v3/objects/contacts/search"
                        search_payload = {
                            "filterGroups": [{
                                "filters": [{
                                    "propertyName": "instagram_id",
                                    "operator": "EQ",
                                    "value": properties["instagram_id"]
                                }]
                            }]
                        }
                        
                        async with session.post(search_url, headers=headers, json=search_payload) as search_resp:
                            if search_resp.status == 200:
                                search_result = await search_resp.json()
                                if search_result.get("results"):
                                    contact_id = search_result["results"][0]["id"]
                                    
                                    # Update contact with intent data
                                    update_url = f"{self.api_base}/crm/v3/objects/contacts/{contact_id}"
                                    async with session.patch(update_url, headers=headers, json=payload) as update_resp:
                                        if update_resp.status == 200:
                                            logger.info(f"HubSpot contact updated: {contact_id} "
                                                      f"with new intent analysis: {intent_category}")
                                            return contact_id
                                            
                    logger.warning(f"Failed to create/update HubSpot contact: HTTP {resp.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error in enhanced HubSpot contact creation: {e}")
            return None
    
    def _calculate_lead_priority(self, intent_category: str, intent_score: float, booking_signals: bool) -> str:
        """Calculate lead priority based on AI intent analysis."""
        if booking_signals or (intent_category == 'booking_intent' and intent_score > 0.8):
            return "high"
        elif intent_category in ['budget_inquiry', 'timeline_urgent'] and intent_score > 0.7:
            return "high"
        elif intent_category in ['property_specific', 'information_request'] and intent_score > 0.6:
            return "medium"
        else:
            return "low"
    
    def _determine_lifecycle_stage(self, intent_category: str, intent_score: float) -> str:
        """Determine lifecycle stage based on intent analysis."""
        if intent_score > 0.8:
            return "salesqualifiedlead"  # High intent leads
        elif intent_score > 0.6:
            return "marketingqualifiedlead"  # Medium intent leads
        elif intent_score > 0.4:
            return "lead"  # Low-medium intent leads
        else:
            return "subscriber"  # Very low intent
    
    async def sync_lead(self, lead_data: Dict[str, Any]) -> Optional[str]:
        """Sync lead to HubSpot, return contact ID"""
        if not self.enabled:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                # Prepare contact properties
                properties = {
                    "email": lead_data.get("email", f"{lead_data['user_id']}@instagram.com"),
                    "firstname": lead_data.get("name", "").split()[0] if lead_data.get("name") else "Instagram",
                    "lastname": lead_data.get("name", "").split()[-1] if lead_data.get("name") and len(lead_data.get("name", "").split()) > 1 else "User",
                    "phone": lead_data.get("phone", ""),
                    "budget": lead_data.get("budget", 0),
                    "location": lead_data.get("location", ""),
                    "property_type": lead_data.get("property_type", ""),
                    "lead_source": lead_data.get("channel", "instagram"),
                    "lead_status": lead_data.get("status", "new"),
                    "instagram_id": lead_data.get("instagram_id") or lead_data.get("user_id"),
                }
                
                # Create or update contact
                url = f"{self.api_base}/crm/v3/objects/contacts"
                payload = {"properties": properties}
                
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in [200, 201]:
                        result = await resp.json()
                        return result.get("id")
                    elif resp.status == 409:  # Contact exists
                        # Search and update
                        search_url = f"{self.api_base}/crm/v3/objects/contacts/search"
                        search_payload = {
                            "filterGroups": [{
                                "filters": [{
                                    "propertyName": "instagram_id",
                                    "operator": "EQ",
                                    "value": properties["instagram_id"]
                                }]
                            }]
                        }
                        async with session.post(search_url, headers=headers, json=search_payload) as search_resp:
                            if search_resp.status == 200:
                                search_result = await search_resp.json()
                                if search_result.get("results"):
                                    contact_id = search_result["results"][0]["id"]
                                    # Update contact
                                    update_url = f"{self.api_base}/crm/v3/objects/contacts/{contact_id}"
                                    async with session.patch(update_url, headers=headers, json=payload) as update_resp:
                                        return contact_id if update_resp.status == 200 else None
                    return None
        except Exception as e:
            print(f"⚠️ HubSpot sync failed: {e}")
            return None
    
    async def sync_conversation(self, contact_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Sync conversation history as notes"""
        if not self.enabled or not contact_id:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                # Create note with conversation
                note_body = "Instagram Conversation:\n\n"
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    note_body += f"{role.upper()}: {content}\n\n"
                
                url = f"{self.api_base}/crm/v3/objects/notes"
                payload = {
                    "properties": {
                        "hs_note_body": note_body,
                        "hs_timestamp": datetime.now().isoformat()
                    },
                    "associations": [{
                        "to": {"id": contact_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
                    }]
                }
                
                async with session.post(url, headers=headers, json=payload) as resp:
                    return resp.status in [200, 201]
        except Exception as e:
            print(f"⚠️ HubSpot conversation sync failed: {e}")
            return False

# Global client
_hubspot_client = None

def get_hubspot_client() -> HubSpotClient:
    """Get or create HubSpot client"""
    global _hubspot_client
    if _hubspot_client is None:
        _hubspot_client = HubSpotClient()
    return _hubspot_client

async def sync_lead_to_hubspot(lead_data: Dict[str, Any]) -> Optional[str]:
    """Legacy convenience function to sync lead (backward compatibility)"""
    client = get_hubspot_client()
    return await client.sync_lead(lead_data)

async def sync_lead_with_intent_to_hubspot(lead_data: Dict[str, Any], intent_analysis: Dict[str, Any]) -> Optional[str]:
    """
    Phase 1: Enhanced lead sync with AI intent analysis.
    
    Args:
        lead_data: Lead information dictionary
        intent_analysis: AI intent analysis results
        
    Returns:
        Contact ID if successful, None otherwise
    """
    client = get_hubspot_client()
    return await client.create_or_update_contact_with_intent(lead_data, intent_analysis)

async def sync_conversation_to_hubspot(contact_id: str, messages: List[Dict[str, Any]]) -> bool:
    """Convenience function to sync conversation"""
    client = get_hubspot_client()
    return await client.sync_conversation(contact_id, messages)

# Phase 1: Auto-contact creation for high-intent leads
async def auto_create_high_intent_contact(lead_data: Dict[str, Any], intent_analysis: Dict[str, Any]) -> Optional[str]:
    """
    Automatically create HubSpot contact for high-intent leads only.
    
    This function implements Phase 1's high-intent filtering by only
    creating CRM contacts for leads that meet the intent threshold.
    
    Args:
        lead_data: Lead information dictionary
        intent_analysis: AI intent analysis results
        
    Returns:
        Contact ID if high-intent threshold met, None otherwise
    """
    intent_score = intent_analysis.get('intent_score', 0.0)
    intent_category = intent_analysis.get('intent_category', 'unknown')
    confidence = intent_analysis.get('confidence', 0.0)
    booking_signals = intent_analysis.get('booking_signals', False)
    
    # Phase 1: High-intent threshold logic
    high_intent_threshold = 0.75
    min_confidence_threshold = 0.6
    
    # Check if lead meets high-intent criteria
    is_high_intent = (
        intent_score >= high_intent_threshold and
        confidence >= min_confidence_threshold
    )
    
    # Special case: Booking signals are always high-intent regardless of score
    if booking_signals:
        is_high_intent = True
        logger.info(f"Booking signals detected - auto-creating contact for lead: {lead_data.get('user_id')}")
    
    if is_high_intent:
        logger.info(f"High-intent lead detected (score: {intent_score:.3f}, category: {intent_category}) - "
                   f"creating HubSpot contact automatically")
        return await sync_lead_with_intent_to_hubspot(lead_data, intent_analysis)
    else:
        logger.debug(f"Lead intent score {intent_score:.3f} below threshold {high_intent_threshold} - "
                    f"skipping auto-contact creation")
        return None

    async def create_booking_opportunity_with_context(
            self,
            contact_id: str,
            booking_context: Dict[str, Any],
            lead_data: Dict[str, Any],
            qualification_context: Dict[str, Any] = None,
            intent_analysis: Dict[str, Any] = None
        ) -> Optional[str]:
            """
            Phase 3: Create HubSpot opportunity on booking confirmation with full context.
            
            Args:
                contact_id: HubSpot contact ID
                booking_context: Booking details including time slot, location, service
                lead_data: Complete lead information
                qualification_context: Phase 2 qualification details and scoring
                intent_analysis: Phase 1 intent analysis results
                
            Returns:
                Opportunity ID if successful, None otherwise
            """
            if not self.enabled:
                return None
            
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    }
                    
                    # Prepare opportunity properties with complete context
                    opportunity_properties = {
                        # Basic opportunity details
                        "dealname": f"Property Tour - {lead_data.get('name', 'Unknown')} - {booking_context.get('slot_time', 'TBD')}",
                        "dealstage": "qualifiedtobuy",  # New opportunity from booking
                        "pipeline": "default",  # Default sales pipeline
                        "amount": lead_data.get("budget", 0),
                        "closedate": booking_context.get("slot_time", datetime.now().isoformat()),
                        
                        # Phase 1 Intent Analysis Context
                        "intent_category": intent_analysis.get('intent_category', 'unknown') if intent_analysis else 'unknown',
                        "intent_score": round(intent_analysis.get('intent_score', 0), 3) if intent_analysis else 0,
                        "confidence_level": round(intent_analysis.get('confidence', 0), 3) if intent_analysis else 0,
                        "booking_signals": "true" if (intent_analysis and intent_analysis.get('booking_signals')) else "false",
                        "budget_mentioned": "true" if (intent_analysis and intent_analysis.get('budget_mentioned')) else "false",
                        "timeline_urgent": "true" if (intent_analysis and intent_analysis.get('timeline_urgent')) else "false",
                        
                        # Phase 2 Qualification Context
                        "qualification_score": round(qualification_context.get('qualification_score', 0), 3) if qualification_context else 0,
                        "qualification_stage": qualification_context.get('qualification_stage', 'unknown') if qualification_context else 'unknown',
                        "budget_band": qualification_context.get('budget_band', 'unknown') if qualification_context else 'unknown',
                        "role_analysis": qualification_context.get('role_analysis', 'unknown') if qualification_context else 'unknown',
                        "readiness_assessment": qualification_context.get('readiness_assessment', 'unknown') if qualification_context else 'unknown',
                        
                        # Lead Journey Context
                        "lead_source": lead_data.get("channel", "instagram"),
                        "instagram_id": lead_data.get("instagram_id") or lead_data.get("user_id"),
                        "lead_location": lead_data.get("location", ""),
                        "property_type_interest": lead_data.get("property_type", ""),
                        "budget_range": f"{lead_data.get('budget', 0):,.0f}",
                        
                        # Booking Context
                        "scheduled_service": booking_context.get("service_type", "property_tour"),
                        "scheduled_location": booking_context.get("location", ""),
                        "scheduled_slot": booking_context.get("slot_time", ""),
                        "booking_priority": booking_context.get("priority_level", "standard"),
                        "meeting_duration_minutes": booking_context.get("duration_minutes", 60),
                        
                        # Lead Timeline & History
                        "qualification_questions_asked": len(qualification_context.get('asked_questions', [])) if qualification_context else 0,
                        "engagement_quality_score": lead_data.get("engagement_score", 0),
                        "lead_urgency_level": booking_context.get("urgency_level", "standard"),
                        
                        # Source Attribution for ROI tracking
                        "campaign_attribution": lead_data.get("campaign", "direct"),
                        "referrer_url": lead_data.get("referrer", ""),
                        "entry_point": lead_data.get("entry_point", "instagram"),
                        "session_start_time": lead_data.get("session_start", datetime.now().isoformat()),
                        
                        # Lead Lifecycle
                        "lead_priority": self._calculate_lead_priority(
                            intent_analysis.get('intent_category', 'unknown') if intent_analysis else 'unknown',
                            intent_analysis.get('intent_score', 0) if intent_analysis else 0,
                            intent_analysis.get('booking_signals', False) if intent_analysis else False
                        ),
                        "lifecyclestage": self._determine_lifecycle_stage(
                            intent_analysis.get('intent_category', 'unknown') if intent_analysis else 'unknown',
                            intent_analysis.get('intent_score', 0) if intent_analysis else 0
                        ),
                        
                        # Meta tracking
                        "phase_3_enhanced": "true",
                        "booking_confirmed": "true",
                        "context_preserved": "true"
                    }
                    
                    # Create opportunity
                    url = f"{self.api_base}/crm/v3/objects/deals"
                    payload = {"properties": opportunity_properties}
                    
                    logger.info(f"📅 Creating Phase 3 booking opportunity for contact {contact_id}")
                    
                    async with session.post(url, headers=headers, json=payload) as resp:
                        if resp.status in [200, 201]:
                            result = await resp.json()
                            opportunity_id = result.get("id")
                            
                            # Associate opportunity with contact
                            await self._associate_opportunity_with_contact(session, headers, opportunity_id, contact_id)
                            
                            # Create detailed meeting note with complete context
                            await self._create_meeting_context_note(session, headers, opportunity_id, lead_data, booking_context, qualification_context, intent_analysis)
                            
                            audit_log_event("booking_opportunity_created", {
                                "contact_id": contact_id,
                                "opportunity_id": opportunity_id,
                                "lead_id": lead_data.get("user_id"),
                                "intent_category": intent_analysis.get('intent_category') if intent_analysis else None,
                                "qualification_score": qualification_context.get('qualification_score') if qualification_context else None,
                                "scheduled_slot": booking_context.get("slot_time"),
                                "booking_priority": booking_context.get("priority_level")
                            })
                            
                            logger.info(f"✅ Phase 3 booking opportunity created: {opportunity_id}")
                            return opportunity_id
                            
                        else:
                            logger.warning(f"Failed to create HubSpot opportunity: HTTP {resp.status}")
                            return None
                            
            except Exception as e:
                logger.error(f"❌ Error creating Phase 3 booking opportunity: {str(e)}")
                audit_log_event("booking_opportunity_creation_error", {
                    "contact_id": contact_id,
                    "error": str(e),
                    "lead_id": lead_data.get("user_id")
                })
                return None
    
    async def _associate_opportunity_with_contact(
            self,
            session: aiohttp.ClientSession,
            headers: Dict[str, str],
            opportunity_id: str,
            contact_id: str
        ) -> bool:
            """Associate created opportunity with contact"""
            try:
                # Associate opportunity with contact
                association_url = f"{self.api_base}/crm/v3/objects/deals/{opportunity_id}/associations/contacts/{contact_id}"
                association_payload = {
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 3  # Deal-to-contact association
                }
                
                async with session.put(association_url, headers=headers, json=association_payload) as resp:
                    success = resp.status in [200, 204]
                    if success:
                        logger.debug(f"✅ Associated opportunity {opportunity_id} with contact {contact_id}")
                    else:
                        logger.warning(f"⚠️ Failed to associate opportunity with contact: HTTP {resp.status}")
                    return success
                    
            except Exception as e:
                logger.warning(f"⚠️ Error associating opportunity with contact: {str(e)}")
                return False
    
    async def _create_meeting_context_note(
            self,
            session: aiohttp.ClientSession,
            headers: Dict[str, str],
            opportunity_id: str,
            lead_data: Dict[str, Any],
            booking_context: Dict[str, Any],
            qualification_context: Dict[str, Any] = None,
            intent_analysis: Dict[str, Any] = None
        ) -> bool:
            """Create detailed meeting context note in HubSpot"""
            try:
                # Build comprehensive meeting context note
                note_content = self._build_meeting_context_note(lead_data, booking_context, qualification_context, intent_analysis)
                
                # Create note
                note_url = f"{self.api_base}/crm/v3/objects/notes"
                note_payload = {
                    "properties": {
                        "hs_note_body": note_content,
                        "hs_timestamp": datetime.now().isoformat()
                    },
                    "associations": [{
                        "to": {"id": opportunity_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]  # Note-to-deal association
                    }]
                }
                
                async with session.post(note_url, headers=headers, json=note_payload) as resp:
                    success = resp.status in [200, 201]
                    if success:
                        logger.debug("✅ Meeting context note created in HubSpot")
                    else:
                        logger.warning(f"⚠️ Failed to create meeting context note: HTTP {resp.status}")
                    return success
                    
            except Exception as e:
                logger.warning(f"⚠️ Error creating meeting context note: {str(e)}")
                return False
    
    def _build_meeting_context_note(
            self,
            lead_data: Dict[str, Any],
            booking_context: Dict[str, Any],
            qualification_context: Dict[str, Any] = None,
            intent_analysis: Dict[str, Any] = None
        ) -> str:
            """Build comprehensive meeting context note content"""
            try:
                note_lines = []
                note_lines.append("🤖 PHASE 3: ENHANCED BOOKING & CRM INTEGRATION CONTEXT")
                note_lines.append("=" * 60)
                note_lines.append("")
                
                # Lead Information
                note_lines.append("📋 LEAD INFORMATION:")
                note_lines.append(f"  Name: {lead_data.get('name', 'Unknown')}")
                note_lines.append(f"  Instagram ID: {lead_data.get('instagram_id') or lead_data.get('user_id')}")
                note_lines.append(f"  Location: {lead_data.get('location', 'Not specified')}")
                note_lines.append(f"  Budget: ${lead_data.get('budget', 0):,.0f}")
                note_lines.append(f"  Property Type: {lead_data.get('property_type', 'Not specified')}")
                note_lines.append(f"  Source Channel: {lead_data.get('channel', 'instagram')}")
                note_lines.append("")
                
                # Phase 1 Intent Analysis
                if intent_analysis:
                    note_lines.append("🎯 PHASE 1: AI INTENT ANALYSIS:")
                    note_lines.append(f"  Intent Category: {intent_analysis.get('intent_category', 'unknown')}")
                    note_lines.append(f"  Intent Score: {intent_analysis.get('intent_score', 0):.3f}")
                    note_lines.append(f"  Confidence Level: {intent_analysis.get('confidence', 0):.3f}")
                    note_lines.append(f"  Budget Mentioned: {'Yes' if intent_analysis.get('budget_mentioned') else 'No'}")
                    note_lines.append(f"  Timeline Urgent: {'Yes' if intent_analysis.get('timeline_urgent') else 'No'}")
                    note_lines.append(f"  Booking Signals: {'Yes' if intent_analysis.get('booking_signals') else 'No'}")
                    if intent_analysis.get('high_intent_indicators'):
                        note_lines.append(f"  High Intent Indicators: {', '.join(intent_analysis.get('high_intent_indicators', []))}")
                    note_lines.append("")
                
                # Phase 2 Qualification
                if qualification_context:
                    note_lines.append("📊 PHASE 2: TRANSPARENT QUALIFICATION:")
                    note_lines.append(f"  Qualification Score: {qualification_context.get('qualification_score', 0):.3f}")
                    note_lines.append(f"  Qualification Stage: {qualification_context.get('qualification_stage', 'unknown')}")
                    note_lines.append(f"  Budget Band: {qualification_context.get('budget_band', 'unknown')}")
                    note_lines.append(f"  Role Analysis: {qualification_context.get('role_analysis', 'unknown')}")
                    note_lines.append(f"  Questions Asked: {len(qualification_context.get('asked_questions', []))}")
                    note_lines.append(f"  Readiness Assessment: {qualification_context.get('readiness_assessment', 'unknown')}")
                    note_lines.append("")
                
                # Booking Details
                note_lines.append("📅 BOOKING CONFIRMATION:")
                note_lines.append(f"  Service Type: {booking_context.get('service_type', 'property_tour')}")
                note_lines.append(f"  Location: {booking_context.get('location', 'TBD')}")
                note_lines.append(f"  Scheduled Time: {booking_context.get('slot_time', 'TBD')}")
                note_lines.append(f"  Duration: {booking_context.get('duration_minutes', 60)} minutes")
                note_lines.append(f"  Priority Level: {booking_context.get('priority_level', 'standard')}")
                note_lines.append(f"  Urgency Level: {booking_context.get('urgency_level', 'standard')}")
                note_lines.append("")
                
                # Lead Journey Timeline
                note_lines.append("🛤️ LEAD JOURNEY SUMMARY:")
                note_lines.append(f"  Initial Contact: {lead_data.get('session_start', 'Unknown')}")
                note_lines.append(f"  Intent Processing: Complete")
                note_lines.append(f"  Qualification: Complete")
                note_lines.append(f"  Booking Confirmation: {datetime.now().isoformat()}")
                note_lines.append(f"  Total Processing Time: Calculated from session start")
                note_lines.append("")
                
                # Attribution Tracking
                note_lines.append("📈 SOURCE ATTRIBUTION:")
                note_lines.append(f"  Campaign: {lead_data.get('campaign', 'direct')}")
                note_lines.append(f"  Referrer: {lead_data.get('referrer', 'direct')}")
                note_lines.append(f"  Entry Point: {lead_data.get('entry_point', 'instagram')}")
                note_lines.append(f"  ROI Tracking: Enabled")
                note_lines.append("")
                
                # Sales Team Context
                note_lines.append("👥 SALES TEAM CONTEXT:")
                note_lines.append("  • High-intent lead with complete journey context")
                note_lines.append("  • Qualified through transparent Phase 2 process")
                note_lines.append("  • Booking confirmed via Phase 3 dynamic slot offering")
                note_lines.append("  • Full context preserved for optimal sales conversion")
                note_lines.append("  • Ready for immediate follow-up and conversion")
                note_lines.append("")
                
                # Next Steps
                note_lines.append("🎯 RECOMMENDED NEXT STEPS:")
                note_lines.append("  1. Review complete lead context above")
                note_lines.append("  2. Prepare for meeting with full background")
                note_lines.append("  3. Leverage qualification insights for conversation")
                note_lines.append("  4. Follow up within 24 hours of scheduled meeting")
                note_lines.append("  5. Track conversion for ROI optimization")
                
                return "\n".join(note_lines)
                
            except Exception as e:
                logger.warning(f"Error building meeting context note: {str(e)}")
                return f"Meeting context note generation failed: {str(e)}"

# Legacy convenience function for backward compatibility
async def create_opportunity_on_booking(
    contact_id: str,
    booking_details: Dict[str, Any],
    lead_data: Dict[str, Any],
    qualification_context: Dict[str, Any] = None,
    intent_analysis: Dict[str, Any] = None
) -> Optional[str]:
    """Create opportunity on booking with complete Phase 3 context"""
    client = get_hubspot_client()
    return await client.create_booking_opportunity_with_context(
        contact_id, booking_details, lead_data, qualification_context, intent_analysis
    )
