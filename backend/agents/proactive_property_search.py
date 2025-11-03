"""
Proactive Property Search Agent - Pure Agentic AI Implementation

This agent searches for properties proactively to demonstrate value and create
compelling property recommendations that guide the conversation forward.

Key Features:
- Pure LLM-based property search decisions (no hardcoded rules)
- Autonomous routing to appropriate agents based on property availability
- Sales-oriented messaging using property results
- Smart property ranking and recommendations
"""

import asyncio
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, Command
from langgraph.prebuilt import ToolNode
import json
import logging

# Supabase client for property queries
from backend.utils.supabase_client import query_properties_db

logger = logging.getLogger(__name__)

class ProactivePropertySearchState:
    """State for proactive property search agent"""
    def __init__(self, message: str, lead_data: Dict[str, Any], prior_context: Dict[str, Any] = None):
        self.message = message
        self.lead_data = lead_data or {}
        self.prior_context = prior_context or {}
        self.properties_found = []
        self.search_attempted = False
        self.property_recommendations = []
        self.sales_intelligence = {}

class ProactivePropertySearchAgent:
    """
    Pure Agentic Property Search Agent
    Uses only LLM intelligence for autonomous property search and sales decisions
    """
    
    def __init__(self):
        self.property_search_prompt = self._build_property_search_prompt()
        self.sales_routing_prompt = self._build_sales_routing_prompt()
    
    def _build_property_search_prompt(self) -> str:
        """Build LLM prompt for autonomous property search decisions"""
        return """
        You are a sophisticated real estate property search AI. Your task is to decide WHEN and HOW to search for properties based on lead information.

        DECISION FRAMEWORK:
        1. Property Search Trigger Conditions (use LLM intelligence, NOT hardcoded rules):
        - Budget provided ($50k-$10M range is viable)
        - ANY location mentioned (even partial)
        - ANY property type mentioned
        - Timeline indicates urgency or serious intent
        - Combination of partial criteria

        2. Search Strategy (be intelligent, not mechanical):
        - If budget missing: Search for properties matching other criteria
        - If location missing: Search broadly in mentioned areas
        - If property type missing: Search multiple property types
        - Prioritize searches that will yield 2+ relevant results

        3. Example Decision Logic (LLM-based):
        - "I need a house" → Search houses in available locations
        - "$250k budget" → Search properties under $275k (10% buffer)
        - "Miami Beach area" → Search Miami Beach and surrounding areas
        - "ASAP timeline" → Prioritize active listings

        RESPONSE FORMAT:
        Return JSON with:
        {
            "should_search": true/false,
            "search_criteria": {
                "budget_min": number or null,
                "budget_max": number or null,
                "locations": [list of locations to search],
                "property_types": [list of property types],
                "search_strategy": "broad/specific/targeted"
            },
            "reasoning": "Why you decided to search or not",
            "expected_results": "How many properties you expect to find",
            "confidence": 0.0-1.0
        }
        """

    def _build_sales_routing_prompt(self) -> str:
        """Build LLM prompt for sales-oriented agent routing based on properties"""
        return """
        You are a sales-oriented routing AI that uses property search results to make intelligent agent routing decisions.

        CONTEXT: A lead has provided some information, and we have found properties that match their criteria.

        ROUTING INTELLIGENCE:
        1. If 3+ excellent matches found → Route to "value_delivery" (showcase properties)
        2. If 1-2 partial matches found → Route to "qualifier" (gather more info for better matches)
        3. If no matches found → Route to "offramp" or "qualifier" based on budget viability
        4. If high-end budget ($1M+) → Route to "value_delivery" (luxury market)

        SALES TACTICS:
        - Use property results to create urgency ("Only 2 similar properties available")
        - Use market insights ("Properties in your area are moving fast")
        - Guide toward scheduling ("Would you like to see any of these today?")

        RESPONSE FORMAT:
        {
            "recommended_agent": "qualifier/value_delivery/scheduler/followup/offramp",
            "routing_reasoning": "Why this agent routing decision",
            "property_insight": "Key insight from property search",
            "sales_angle": "How to present the properties to move the sale forward",
            "next_steps": ["Specific actions to take"],
            "urgency_level": "high/medium/low",
            "confidence": 0.0-1.0
        }
        """

    async def search_properties_autonomously(self, state: ProactivePropertySearchState) -> ProactivePropertySearchState:
        """
        Pure LLM-based property search decision making
        """
        try:
            # Get LLM decision on whether to search for properties
            from backend.utils.llm_client import call_llm
            
            search_context = {
                "lead_data": state.lead_data,
                "message": state.message,
                "prior_properties": state.prior_context.get("properties", [])
            }
            
            search_decision = await call_llm(
                prompt=self.property_search_prompt + f"\n\nLEAD CONTEXT: {json.dumps(search_context, indent=2)}",
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse LLM decision
            try:
                decision = json.loads(search_decision)
            except:
                # Fallback if JSON parsing fails
                decision = {
                    "should_search": state.lead_data.get("budget") and state.lead_data.get("location"),
                    "search_criteria": {
                        "budget_max": state.lead_data.get("budget", 0) * 1.1 if state.lead_data.get("budget") else None,
                        "locations": [state.lead_data.get("location", "")] if state.lead_data.get("location") else [],
                        "property_types": [state.lead_data.get("property_type", "")] if state.lead_data.get("property_type") else [],
                        "search_strategy": "targeted"
                    },
                    "reasoning": "Fallback decision based on available criteria",
                    "confidence": 0.7
                }
            
            # Execute property search if LLM decided to search
            if decision.get("should_search", False):
                criteria = decision.get("search_criteria", {})
                budget_max = criteria.get("budget_max") or state.lead_data.get("budget", 0)
                locations = criteria.get("locations", [state.lead_data.get("location", "")]) or [state.lead_data.get("location", "")]
                property_types = criteria.get("property_types", [state.lead_data.get("property_type", "")]) or [state.lead_data.get("property_type", "")]
                
                # Search for properties (use first location and property type for now)
                search_location = locations[0] if locations else state.lead_data.get("location", "")
                search_type = property_types[0] if property_types else state.lead_data.get("property_type", "")
                
                if search_location and budget_max > 0:
                    logger.info(f"🔍 PROACTIVE SEARCH: Budget ${budget_max:,}, Location: {search_location}, Type: {search_type}")
                    
                    state.properties_found = query_properties_db(
                        budget=int(budget_max),
                        location=search_location,
                        property_type=search_type
                    )
                    
                    state.search_attempted = True
                    logger.info(f"✅ Found {len(state.properties_found)} properties proactively")
                    
                    # Store search decision
                    state.sales_intelligence["search_decision"] = decision
                    state.sales_intelligence["properties_found"] = len(state.properties_found)
                    state.sales_intelligence["search_location"] = search_location
                    state.sales_intelligence["search_budget"] = budget_max
            
            return state
            
        except Exception as e:
            logger.error(f"Proactive property search error: {e}")
            return state

    async def generate_property_recommendations(self, state: ProactivePropertySearchState) -> ProactivePropertySearchState:
        """
        Generate sales-oriented property recommendations using LLM
        """
        if not state.properties_found:
            return state
        
        try:
            from backend.utils.llm_client import call_llm
            
            properties_context = {
                "properties": state.properties_found[:5],  # Top 5 properties
                "lead_data": state.lead_data,
                "message": state.message
            }
            
            recommendation_prompt = f"""
            You are a real estate sales expert. Create compelling property recommendations for a lead.

            PROPERTIES FOUND: {json.dumps(properties_context, indent=2)}

            CREATE 2-3 PROPERTY RECOMMENDATIONS:
            1. Pick the most relevant properties from the list
            2. Create sales-oriented descriptions
            3. Include compelling reasons to act
            4. Suggest next steps (viewing, more info, etc.)

            RESPONSE FORMAT:
            {{
                "recommendations": [
                    {{
                        "property_summary": "Brief compelling description",
                        "key_features": ["feature1", "feature2", "feature3"],
                        "sales_angle": "Why this property is perfect for them",
                        "urgency_factor": "Reason to act now",
                        "next_step": "Suggested action"
                    }}
                ],
                "market_insight": "Key market insight to create urgency",
                "overall_strategy": "How to present these properties to move the sale forward"
            }}
            """
            
            recommendations = await call_llm(
                prompt=recommendation_prompt,
                max_tokens=800,
                temperature=0.4
            )
            
            try:
                state.property_recommendations = json.loads(recommendations)
            except:
                # Fallback recommendations
                state.property_recommendations = {
                    "recommendations": [{
                        "property_summary": f"Found {len(state.properties_found)} matching properties",
                        "key_features": ["Good location", "Within budget", "Ready to view"],
                        "sales_angle": "These properties match your criteria perfectly",
                        "urgency_factor": "Properties in this area move quickly",
                        "next_step": "Would you like to schedule a viewing?"
                    }],
                    "market_insight": "Properties in your area are selling quickly",
                    "overall_strategy": "Use property matches to demonstrate value and create urgency"
                }
            
            return state
            
        except Exception as e:
            logger.error(f"Property recommendation error: {e}")
            return state

    async def get_sales_routing_decision(self, state: ProactivePropertySearchState) -> Dict[str, Any]:
        """
        Get LLM-based routing decision using property search results
        """
        try:
            from backend.utils.llm_client import call_llm
            
            routing_context = {
                "properties_found": len(state.properties_found),
                "property_recommendations": state.property_recommendations,
                "lead_data": state.lead_data,
                "search_intelligence": state.sales_intelligence
            }
            
            routing_decision = await call_llm(
                prompt=self.sales_routing_prompt + f"\n\nROUTING CONTEXT: {json.dumps(routing_context, indent=2)}",
                max_tokens=600,
                temperature=0.3
            )
            
            try:
                routing = json.loads(routing_decision)
            except:
                # Fallback routing logic
                property_count = len(state.properties_found)
                if property_count >= 3:
                    routing = {
                        "recommended_agent": "value_delivery",
                        "routing_reasoning": "Multiple properties found - showcase value",
                        "property_insight": f"Found {property_count} excellent matches",
                        "sales_angle": "Use property matches to demonstrate immediate value",
                        "next_steps": ["Showcase top properties", "Schedule viewing"],
                        "urgency_level": "high",
                        "confidence": 0.8
                    }
                elif property_count >= 1:
                    routing = {
                        "recommended_agent": "qualifier",
                        "routing_reasoning": "Some properties found - need more details for better matches",
                        "property_insight": f"Found {property_count} partial matches",
                        "sales_angle": "Use initial matches to gather more requirements",
                        "next_steps": ["Show initial matches", "Gather more criteria"],
                        "urgency_level": "medium",
                        "confidence": 0.7
                    }
                else:
                    routing = {
                        "recommended_agent": "qualifier",
                        "routing_reasoning": "No properties found - need different approach",
                        "property_insight": "Need to adjust search criteria",
                        "sales_angle": "Gather more specific requirements for better matches",
                        "next_steps": ["Gather requirements", "Adjust search"],
                        "urgency_level": "low",
                        "confidence": 0.6
                    }
            
            return routing
            
        except Exception as e:
            logger.error(f"Sales routing decision error: {e}")
            return {
                "recommended_agent": "qualifier",
                "routing_reasoning": "Error in routing decision",
                "property_insight": "Unable to process property search results",
                "sales_angle": "Continue with qualification process",
                "next_steps": ["Gather requirements"],
                "urgency_level": "medium",
                "confidence": 0.5
            }

    async def run_proactive_search(self, message: str, lead_data: Dict[str, Any], prior_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main function to run proactive property search
        """
        try:
            state = ProactivePropertySearchState(message, lead_data, prior_context)
            
            # Step 1: Decide whether to search for properties
            state = await self.search_properties_autonomously(state)
            
            # Step 2: Generate property recommendations if properties found
            if state.properties_found:
                state = await self.generate_property_recommendations(state)
            
            # Step 3: Get sales routing decision
            routing_decision = await self.get_sales_routing_decision(state)
            
            return {
                "status": "success",
                "properties_found": len(state.properties_found),
                "properties": state.properties_found,
                "recommendations": state.property_recommendations,
                "routing_decision": routing_decision,
                "search_attempted": state.search_attempted,
                "sales_intelligence": state.sales_intelligence
            }
            
        except Exception as e:
            logger.error(f"Proactive property search failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "properties_found": 0,
                "properties": [],
                "routing_decision": {
                    "recommended_agent": "qualifier",
                    "routing_reasoning": "Property search failed",
                    "confidence": 0.3
                }
            }

# Global instance
proactive_property_search = ProactivePropertySearchAgent()

# Convenience function
async def run_proactive_property_search(message: str, lead_data: Dict[str, Any], prior_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Global function to run proactive property search"""
    return await proactive_property_search.run_proactive_search(message, lead_data, prior_context)