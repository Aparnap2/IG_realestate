"""
HubSpot CRM Integration for Real Estate Lead Management
"""
import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp

from config import get_settings

settings = get_settings()

class HubSpotClient:
    """HubSpot API client for lead and conversation sync"""
    
    def __init__(self):
        self.access_token = settings.HUBSPOT_ACCESS_TOKEN
        self.api_base = settings.HUBSPOT_API_BASE
        self.enabled = bool(self.access_token)
    
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
    """Convenience function to sync lead"""
    client = get_hubspot_client()
    return await client.sync_lead(lead_data)

async def sync_conversation_to_hubspot(contact_id: str, messages: List[Dict[str, Any]]) -> bool:
    """Convenience function to sync conversation"""
    client = get_hubspot_client()
    return await client.sync_conversation(contact_id, messages)
