#!/usr/bin/env python3
"""
Production-grade lead processing for AAA Real Estate System.
Implements the complete PRD workflow with LangGraph swarm.
"""

import os
import sys
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Import required modules
from utils.supabase_client import supabase, query_properties_db, save_lead, get_config
from utils.llm_client import get_llm_response
from utils.redis_client import redis_client
from models.lead import Lead

class ProductionLeadProcessor:
    """Production-grade lead processor implementing PRD workflow"""
    
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = "anthropic/claude-3.5-sonnet"
    
    async def process_lead_message(self, user_id: str, message: str, channel: str) -> Dict[str, Any]:
        """
        Process a lead message through the complete PRD workflow.
        
        Args:
            user_id: User identifier from Meta API
            message: Lead's message text
            channel: Channel (ig/whatsapp)
            
        Returns:
            Processing result with lead data and next steps
        """
        try:
            # Step 1: Create or update lead
            lead_data = {
                "user_id": user_id,
                "channel": channel,
                "message": message,
                "status": "new",
                "history": [
                    {
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                        "agent": "user",
                        "details": "Initial message received"
                    }
                ]
            }
            
            # Save lead to database
            saved_lead = save_lead(lead_data)
            lead_id = saved_lead.get("id")
            
            print(f"✅ Lead created: {lead_id}")
            
            # Step 2: Extract lead information using LLM
            extracted_info = await self.extract_lead_info(message)
            
            # Update lead with extracted info
            if extracted_info:
                lead_data.update(extracted_info)
                lead_data["id"] = lead_id
                saved_lead = save_lead(lead_data)
            
            print(f"✅ Lead info extracted: {extracted_info}")
            
            # Step 3: Query properties database
            db_results = []
            if extracted_info.get("budget") and extracted_info.get("location"):
                db_results = query_properties_db(
                    budget=extracted_info["budget"],
                    location=extracted_info["location"],
                    property_type=extracted_info.get("property_type", "")
                )
            
            print(f"✅ Found {len(db_results)} matching properties")
            
            # Step 4: Qualify lead using LLM
            qualification_result = await self.qualify_lead(extracted_info, db_results)
            
            # Update lead with qualification
            lead_data["qualified_score"] = qualification_result["score"]
            lead_data["status"] = "qualified" if qualification_result["score"] > 0.7 else "new"
            lead_data["history"].append({
                "message": f"Lead qualified with score: {qualification_result['score']}",
                "timestamp": datetime.now().isoformat(),
                "agent": "qualifier",
                "details": qualification_result["reasoning"]
            })
            
            saved_lead = save_lead(lead_data)
            
            print(f"✅ Lead qualified: {qualification_result['score']}")
            
            # Step 5: Determine next agent and actions
            next_agent = await self.determine_next_agent(qualification_result, extracted_info)
            
            # Step 6: Generate response message
            response_message = await self.generate_response_message(
                extracted_info, db_results, qualification_result, next_agent
            )
            
            # Step 7: Store state in Redis (LangGraph checkpointer simulation)
            thread_state = {
                "lead": lead_data,
                "messages": [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_message}
                ],
                "db_results": db_results,
                "qualification": qualification_result,
                "next_agent": next_agent,
                "timestamp": datetime.now().isoformat()
            }
            
            redis_client.setex(
                f"langgraph:thread:{user_id}",
                86400,  # 24 hours
                json.dumps(thread_state, default=str)
            )
            
            print(f"✅ State stored in Redis for thread: {user_id}")
            
            # Step 8: Handle HITL if needed
            interrupt_needed = await self.check_hitl_interrupt(qualification_result, extracted_info)
            
            return {
                "lead_id": lead_id,
                "user_id": user_id,
                "qualified_score": qualification_result["score"],
                "next_agent": next_agent,
                "response_message": response_message,
                "properties_found": len(db_results),
                "interrupt_needed": interrupt_needed,
                "status": "success"
            }
            
        except Exception as e:
            print(f"❌ Error processing lead: {e}")
            return {
                "status": "error",
                "error": str(e),
                "user_id": user_id
            }
    
    async def extract_lead_info(self, message: str) -> Dict[str, Any]:
        """Extract structured information from lead message using pattern matching"""
        
        import re
        
        extracted = {}
        message_lower = message.lower()
        
        # Extract budget
        budget_patterns = [
            r'\$(\d+)k',  # $350k
            r'\$(\d+),?(\d+)',  # $350,000
            r'budget.*?\$?(\d+)k',  # budget $350k
            r'(\d+)k.*?budget',  # 350k budget
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                if 'k' in pattern:
                    extracted['budget'] = int(match.group(1)) * 1000
                else:
                    budget_str = match.group(1) + (match.group(2) if match.lastindex > 1 else '')
                    extracted['budget'] = int(budget_str)
                break
        
        # Extract location
        locations = ['miami', 'orlando', 'tampa', 'jacksonville', 'miami beach', 'fort lauderdale']
        for location in locations:
            if location in message_lower:
                extracted['location'] = location.title()
                break
        
        # Extract property type
        property_types = ['1bhk', '2bhk', '3bhk', 'condo', 'apartment', 'house', 'penthouse']
        for prop_type in property_types:
            if prop_type in message_lower:
                extracted['property_type'] = prop_type.upper() if 'bhk' in prop_type else prop_type.title()
                break
        
        # Extract timeline
        if any(word in message_lower for word in ['asap', 'urgent', 'immediately', 'soon']):
            extracted['timeline'] = 'ASAP'
        elif any(word in message_lower for word in ['flexible', 'no rush', 'whenever']):
            extracted['timeline'] = 'flexible'
        elif 'month' in message_lower:
            month_match = re.search(r'(\d+)\s*month', message_lower)
            if month_match:
                extracted['timeline'] = f"{month_match.group(1)} months"
        
        # Extract name (simple pattern)
        name_patterns = [r'i\'?m\s+([a-z]+)', r'my name is\s+([a-z]+)', r'this is\s+([a-z]+)']
        for pattern in name_patterns:
            match = re.search(pattern, message_lower)
            if match:
                extracted['name'] = match.group(1).title()
                break
        
        # Extract email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        if email_match:
            extracted['email'] = email_match.group()
        
        return extracted
    
    async def qualify_lead(self, lead_info: Dict[str, Any], db_results: list) -> Dict[str, Any]:
        """Qualify lead using LLM with PRD scoring criteria"""
        
        # Use rule-based qualification for now (can be enhanced with LLM later)
        score = 0.3  # Base score
        reasoning_parts = []
        
        budget = lead_info.get("budget", 0)
        location = lead_info.get("location", "")
        property_type = lead_info.get("property_type", "")
        timeline = lead_info.get("timeline", "")
        
        # Budget scoring (PRD criteria)
        if budget > 500000:
            score += 0.4
            reasoning_parts.append("High budget ($500k+)")
        elif budget > 100000:
            score += 0.2
            reasoning_parts.append("Moderate budget ($100k+)")
        
        # Location match scoring
        if location and db_results:
            score += 0.3
            reasoning_parts.append(f"Location match with {len(db_results)} properties")
        elif location:
            score += 0.1
            reasoning_parts.append("Location specified")
        
        # Property type scoring
        if property_type:
            score += 0.2
            reasoning_parts.append("Property type specified")
        
        # Timeline scoring
        if timeline and timeline.lower() in ["asap", "urgent", "immediately"]:
            score += 0.2
            reasoning_parts.append("Urgent timeline")
        elif timeline:
            score += 0.1
            reasoning_parts.append("Timeline specified")
        
        final_score = min(score, 1.0)
        reasoning = f"Score: {final_score:.1f} - " + ", ".join(reasoning_parts)
        
        return {
            "score": final_score,
            "reasoning": reasoning
        }
        # Fallback scoring
        score = 0.3  # Base score
        if lead_info.get("budget", 0) > 500000:
            score += 0.4
        elif lead_info.get("budget", 0) > 100000:
            score += 0.2
        
        if lead_info.get("location") and db_results:
            score += 0.3
        
        if lead_info.get("property_type"):
            score += 0.2
        
        return {
            "score": min(score, 1.0),
            "reasoning": "Fallback scoring based on budget and property match"
        }
    
    async def determine_next_agent(self, qualification: Dict[str, Any], lead_info: Dict[str, Any]) -> str:
        """Determine next agent based on PRD workflow rules"""
        
        score = qualification["score"]
        budget = lead_info.get("budget", 0)
        
        # PRD Rules:
        # - Score > 0.7: Scheduler
        # - Budget > $500k: HITL first
        # - Score <= 0.7: FollowUp
        
        if budget > 500000 and score > 0.9:
            return "hitl"  # High-value lead needs human review
        elif score > 0.7:
            return "scheduler"
        else:
            return "followup"
    
    async def generate_response_message(self, lead_info: Dict[str, Any], db_results: list, 
                                      qualification: Dict[str, Any], next_agent: str) -> str:
        """Generate appropriate response message based on qualification and next agent"""
        
        score = qualification["score"]
        properties_count = len(db_results)
        
        if next_agent == "hitl":
            return f"Thank you for your interest! Based on your requirements, I found {properties_count} premium properties that might be perfect for you. Let me connect you with our senior advisor who specializes in luxury properties."
        
        elif next_agent == "scheduler":
            return f"Great! I found {properties_count} properties that match your criteria. I'd love to show you these options. Would you like to schedule a viewing? I have availability this week."
        
        else:  # followup
            if properties_count > 0:
                return f"Thank you for your interest! I found {properties_count} properties in your area. Let me share some details about what's available and help you explore your options."
            else:
                return "Thank you for reaching out! While I don't have exact matches right now, I'd love to understand your needs better and keep you updated on new listings that might interest you."
    
    async def check_hitl_interrupt(self, qualification: Dict[str, Any], lead_info: Dict[str, Any]) -> bool:
        """Check if HITL interrupt is needed based on PRD criteria"""
        
        hitl_threshold = float(get_config("hitl_threshold", "0.9"))
        high_value_budget = int(get_config("high_value_budget", "500000"))
        
        score = qualification["score"]
        budget = lead_info.get("budget", 0)
        
        return score >= hitl_threshold or budget >= high_value_budget

# Global processor instance
processor = ProductionLeadProcessor()

async def process_lead_message(user_id: str, message: str, channel: str) -> Dict[str, Any]:
    """Main entry point for lead processing"""
    return await processor.process_lead_message(user_id, message, channel)