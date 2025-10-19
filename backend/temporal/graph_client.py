"""
Temporal Knowledge Graph Client using Graphiti

Implements PRD Section 2.2 & 2.4: Temporal memory and context-aware nurturing.

Key Features:
- Real-time temporal fact storage and retrieval
- Lead engagement trajectory tracking
- Property interest evolution over time
- Context-aware query interface
- Integration with Supabase for fallback storage
"""

import sys
import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import get_settings
from utils.audit import audit_log_event

settings = get_settings()

class GraphitiClient:
    """
    Temporal knowledge graph client using Graphiti for AI agent memory.
    
    Provides temporal context for lead interactions, property interests,
    and engagement patterns over time.
    """
    
    def __init__(self):
        self.graphiti = None
        self.fallback_enabled = True
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Graphiti client with Neo4j backend."""
        try:
            if not settings.ENABLE_TEMPORAL_GRAPH:
                return
            
            from graphiti_core import Graphiti
            
            self.graphiti = Graphiti(
                uri=settings.NEO4J_URI,
                user=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD
            )
            
            # Build indices and constraints on first run
            # asyncio.run(self.graphiti.build_indices_and_constraints())
            
        except Exception as e:
            audit_log_event("graphiti_init_error", {"error": str(e)})
            self.graphiti = None
    
    async def record_lead_event(
        self,
        lead_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        timestamp: datetime = None
    ) -> bool:
        """
        Record a lead interaction event in the temporal graph.
        
        Args:
            lead_id: Unique lead identifier
            event_type: Type of event (message, qualification, tour, etc.)
            event_data: Event details and context
            timestamp: Event timestamp (defaults to now)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not timestamp:
                timestamp = datetime.now(timezone.utc)
            
            if self.graphiti:
                # Use Graphiti for temporal storage
                await self._store_in_graphiti(lead_id, event_type, event_data, timestamp)
            elif self.fallback_enabled:
                # Fallback to Supabase temporal tables
                await self._store_in_supabase_fallback(lead_id, event_type, event_data, timestamp)
            
            audit_log_event("temporal_event_recorded", {
                "lead_id": lead_id,
                "event_type": event_type,
                "timestamp": timestamp.isoformat(),
                "storage_method": "graphiti" if self.graphiti else "supabase_fallback"
            })
            
            return True
            
        except Exception as e:
            audit_log_event("temporal_event_error", {
                "error": str(e),
                "lead_id": lead_id,
                "event_type": event_type
            })
            return False
    
    async def get_lead_history(
        self,
        lead_id: str,
        days_back: int = 30,
        event_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get temporal history for a lead.
        
        Args:
            lead_id: Lead identifier
            days_back: Number of days to look back
            event_types: Filter by specific event types
            
        Returns:
            List of historical events
        """
        try:
            if self.graphiti:
                return await self._query_graphiti_history(lead_id, days_back, event_types)
            elif self.fallback_enabled:
                return await self._query_supabase_history(lead_id, days_back, event_types)
            
            return []
            
        except Exception as e:
            audit_log_event("temporal_history_error", {
                "error": str(e),
                "lead_id": lead_id
            })
            return []
    
    async def get_engagement_trajectory(self, lead_id: str) -> Dict[str, Any]:
        """
        Analyze lead's engagement trajectory over time.
        
        Returns:
            Dictionary with trajectory analysis
        """
        try:
            history = await self.get_lead_history(lead_id, days_back=90)
            
            if not history:
                return {
                    "trajectory": "stable",
                    "confidence": 0.5,
                    "trend": "no_data",
                    "recent_activity": 0
                }
            
            # Analyze engagement patterns
            recent_events = [e for e in history if self._is_recent_event(e, days=7)]
            older_events = [e for e in history if not self._is_recent_event(e, days=7)]
            
            recent_activity = len(recent_events)
            historical_activity = len(older_events) / max(1, (90 - 7) / 7)  # Weekly average
            
            # Calculate trajectory
            if recent_activity > historical_activity * 1.5:
                trajectory = "escalating"
                confidence = min(0.9, recent_activity / 10)
            elif recent_activity < historical_activity * 0.5:
                trajectory = "cooling"
                confidence = min(0.9, historical_activity / 10)
            else:
                trajectory = "stable"
                confidence = 0.7
            
            # Analyze trend
            if recent_activity >= 3:
                trend = "highly_engaged"
            elif recent_activity >= 1:
                trend = "moderately_engaged"
            else:
                trend = "low_engagement"
            
            return {
                "trajectory": trajectory,
                "confidence": confidence,
                "trend": trend,
                "recent_activity": recent_activity,
                "historical_average": historical_activity,
                "total_interactions": len(history)
            }
            
        except Exception as e:
            audit_log_event("engagement_trajectory_error", {
                "error": str(e),
                "lead_id": lead_id
            })
            return {
                "trajectory": "stable",
                "confidence": 0.5,
                "trend": "unknown",
                "recent_activity": 0
            }
    
    async def find_similar_leads(
        self,
        criteria: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find leads with similar patterns or characteristics.
        
        Args:
            criteria: Search criteria (budget, location, interests, etc.)
            limit: Maximum number of results
            
        Returns:
            List of similar leads with similarity scores
        """
        try:
            if self.graphiti:
                return await self._find_similar_in_graphiti(criteria, limit)
            elif self.fallback_enabled:
                return await self._find_similar_in_supabase(criteria, limit)
            
            return []
            
        except Exception as e:
            audit_log_event("similar_leads_error", {
                "error": str(e),
                "criteria": criteria
            })
            return []
    
    async def get_property_interest_evolution(
        self,
        lead_id: str
    ) -> Dict[str, Any]:
        """
        Track how a lead's property interests have evolved over time.
        
        Returns:
            Analysis of interest evolution
        """
        try:
            history = await self.get_lead_history(
                lead_id,
                days_back=180,
                event_types=["property_view", "qualification", "tour_request"]
            )
            
            if not history:
                return {"evolution": "no_data", "interests": []}
            
            # Group events by time periods
            periods = {
                "recent": [],      # Last 30 days
                "medium": [],      # 30-90 days ago
                "historical": []   # 90+ days ago
            }
            
            now = datetime.now(timezone.utc)
            for event in history:
                event_time = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
                days_ago = (now - event_time).days
                
                if days_ago <= 30:
                    periods["recent"].append(event)
                elif days_ago <= 90:
                    periods["medium"].append(event)
                else:
                    periods["historical"].append(event)
            
            # Analyze interest evolution
            evolution_analysis = {
                "budget_trend": self._analyze_budget_trend(periods),
                "location_preferences": self._analyze_location_evolution(periods),
                "property_type_evolution": self._analyze_property_type_evolution(periods),
                "engagement_intensity": {
                    "recent": len(periods["recent"]),
                    "medium": len(periods["medium"]),
                    "historical": len(periods["historical"])
                }
            }
            
            return evolution_analysis
            
        except Exception as e:
            audit_log_event("interest_evolution_error", {
                "error": str(e),
                "lead_id": lead_id
            })
            return {"evolution": "error", "interests": []}
    
    async def _store_in_graphiti(
        self,
        lead_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        timestamp: datetime
    ):
        """Store event in Graphiti temporal graph."""
        try:
            # Create episode for the event
            episode_data = {
                "uuid": f"{lead_id}_{event_type}_{int(timestamp.timestamp())}",
                "name": f"Lead {event_type}",
                "role": "Lead",
                "role_type": "user",
                "content": f"{event_type}: {event_data}",
                "timestamp": timestamp.isoformat(),
                "source_description": "Real Estate AI Agent"
            }
            
            # Add to processing queue
            await self.graphiti.add_messages(
                group_id=f"lead_{lead_id}",
                messages=[episode_data]
            )
            
        except Exception as e:
            raise Exception(f"Graphiti storage failed: {str(e)}")
    
    async def _store_in_supabase_fallback(
        self,
        lead_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        timestamp: datetime
    ):
        """Store event in Supabase as fallback."""
        try:
            from utils.supabase_client import supabase
            
            # Convert lead_id to UUID if needed by querying leads table
            # Try instagram_id first (primary identifier), then fallback to user_id
            lead_uuid_response = supabase.table("leads").select("id").eq("instagram_id", lead_id).execute()
            if not lead_uuid_response.data:
                # Fallback to user_id if instagram_id doesn't match
                lead_uuid_response = supabase.table("leads").select("id").eq("user_id", lead_id).execute()
            lead_uuid = None
            if lead_uuid_response.data:
                lead_uuid = lead_uuid_response.data[0]["id"]
            
            if not lead_uuid:
                # Skip if we can't find the lead UUID
                return
            
            event_record = {
                "lead_id": lead_uuid,  # Use UUID instead of user_id
                "event_type": event_type,
                "event_data": event_data,
                "created_at": timestamp.isoformat()  # Use timestamp as created_at
            }
            
            # Insert into lead_events table with proper schema
            supabase.table("lead_events").insert(event_record).execute()
            
        except Exception as e:
            # Silently fail if lead_events table doesn't exist or schema mismatch
            print(f"⚠️ Lead events fallback failed: {e}")
            pass
    
    async def _query_graphiti_history(
        self,
        lead_id: str,
        days_back: int,
        event_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Query history from Graphiti."""
        try:
            reference_time = datetime.now(timezone.utc)
            
            episodes = await self.graphiti.retrieve_episodes(
                reference_time=reference_time,
                last_n=100,  # Retrieve last 100 episodes
                group_ids=[f"lead_{lead_id}"]
            )
            
            # Filter by time range and event types
            filtered_events = []
            cutoff_time = reference_time - timedelta(days=days_back)
            
            for episode in episodes:
                episode_time = datetime.fromisoformat(episode.valid_at.replace('Z', '+00:00'))
                
                if episode_time >= cutoff_time:
                    event_data = {
                        "timestamp": episode.valid_at,
                        "event_type": episode.name.split()[-1].lower(),  # Extract event type
                        "content": episode.content,
                        "source": "graphiti"
                    }
                    
                    if not event_types or event_data["event_type"] in event_types:
                        filtered_events.append(event_data)
            
            return filtered_events
            
        except Exception as e:
            raise Exception(f"Graphiti history query failed: {str(e)}")
    
    async def _query_supabase_history(
        self,
        lead_id: str,
        days_back: int,
        event_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Query history from Supabase fallback."""
        try:
            from utils.supabase_client import supabase
            
            cutoff_time = datetime.now() - timedelta(days=days_back)
            
            # Convert lead_id to UUID if needed by querying leads table
            # Try instagram_id first (primary identifier), then fallback to user_id
            lead_uuid_response = supabase.table("leads").select("id").eq("instagram_id", lead_id).execute()
            if not lead_uuid_response.data:
                # Fallback to user_id if instagram_id doesn't match
                lead_uuid_response = supabase.table("leads").select("id").eq("user_id", lead_id).execute()
            
            if not lead_uuid_response.data:
                return []
            
            lead_uuid = lead_uuid_response.data[0]["id"]
            
            query = supabase.table("lead_events")\
                .select("*")\
                .eq("lead_id", lead_uuid)\
                .gte("created_at", cutoff_time.isoformat())\
                .order("created_at", desc=True)
            
            if event_types:
                query = query.in_("event_type", event_types)
            
            response = query.execute()
            
            return response.data or []
            
        except Exception as e:
            raise Exception(f"Supabase history query failed: {str(e)}")
    
    def _is_recent_event(self, event: Dict[str, Any], days: int = 7) -> bool:
        """Check if event is within the recent time window."""
        try:
            event_time = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            return event_time >= cutoff
        except Exception:
            return False
    
    def _analyze_budget_trend(self, periods: Dict[str, List]) -> Dict[str, Any]:
        """Analyze how budget preferences have changed over time."""
        try:
            budget_data = {}
            
            for period, events in periods.items():
                budgets = []
                for event in events:
                    if "budget" in str(event.get("event_data", {})):
                        # Extract budget from event data (simplified)
                        try:
                            budget = event["event_data"].get("budget")
                            if budget and isinstance(budget, (int, float)):
                                budgets.append(budget)
                        except Exception:
                            continue
                
                if budgets:
                    budget_data[period] = {
                        "average": sum(budgets) / len(budgets),
                        "max": max(budgets),
                        "min": min(budgets),
                        "count": len(budgets)
                    }
            
            # Determine trend
            if "recent" in budget_data and "historical" in budget_data:
                recent_avg = budget_data["recent"]["average"]
                historical_avg = budget_data["historical"]["average"]
                
                if recent_avg > historical_avg * 1.1:
                    trend = "increasing"
                elif recent_avg < historical_avg * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            return {
                "trend": trend,
                "periods": budget_data
            }
            
        except Exception:
            return {"trend": "error", "periods": {}}
    
    def _analyze_location_evolution(self, periods: Dict[str, List]) -> Dict[str, Any]:
        """Analyze location preference changes."""
        try:
            location_data = {}
            
            for period, events in periods.items():
                locations = []
                for event in events:
                    event_data = event.get("event_data", {})
                    if isinstance(event_data, dict) and "location" in event_data:
                        location = event_data["location"]
                        if location:
                            locations.append(location.lower())
                
                if locations:
                    # Count frequency
                    location_counts = {}
                    for loc in locations:
                        location_counts[loc] = location_counts.get(loc, 0) + 1
                    
                    location_data[period] = location_counts
            
            return location_data
            
        except Exception:
            return {}
    
    def _analyze_property_type_evolution(self, periods: Dict[str, List]) -> Dict[str, Any]:
        """Analyze property type preference changes."""
        try:
            type_data = {}
            
            for period, events in periods.items():
                property_types = []
                for event in events:
                    event_data = event.get("event_data", {})
                    if isinstance(event_data, dict) and "property_type" in event_data:
                        prop_type = event_data["property_type"]
                        if prop_type:
                            property_types.append(prop_type.lower())
                
                if property_types:
                    # Count frequency
                    type_counts = {}
                    for ptype in property_types:
                        type_counts[ptype] = type_counts.get(ptype, 0) + 1
                    
                    type_data[period] = type_counts
            
            return type_data
            
        except Exception:
            return {}

# Global client instance
_graphiti_client = None

def get_graphiti_client() -> GraphitiClient:
    """Get or create the global Graphiti client instance."""
    global _graphiti_client
    if _graphiti_client is None:
        _graphiti_client = GraphitiClient()
    return _graphiti_client