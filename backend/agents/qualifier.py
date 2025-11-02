import sys
import os
import types
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.llm_client import get_llm_response_sync, generate_proactive_lead_response
from utils.supabase_client import query_properties_db, get_config, save_lead
from utils.redis_client import cache_query_result, get_cached_query_result
from tools.handoffs import handoff_to_scheduler, handoff_to_followup
from tools.qualifier_utils import generate_transparent_scoring_breakdown, prioritize_questions_llm, assess_qualification_readiness
from schemas.state import AgentState
from typing import Dict, Any, Optional, List
from utils.observability import track_performance
from utils.lead_scoring import calculate_lead_score, get_next_qualification_question, lead_scorer
from utils.audit import audit_log_event

# Provide legacy module path for tests and backward compatibility
if "agents" not in sys.modules:
    legacy_agents_module = types.ModuleType("agents")
    legacy_agents_module.__path__ = []  # type: ignore[attr-defined]
    sys.modules["agents"] = legacy_agents_module

sys.modules["agents.qualifier"] = sys.modules[__name__]

# Provide QualifierAgent for legacy imports via prd_compliant_workflow implementation
from .prd_compliant_workflow import QualifierAgent  # noqa: E402

@track_performance
def qualifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced qualifier agent with sophisticated scoring and progressive qualification.
    
    Implements PRD-compliant qualification flow:
    - Lead scoring with >=0.75 → scheduler, <0.75 → followup, <0.4 → offramp
    - Progressive question flow with intelligent field mapping
    - Compliance checks and state-specific requirements
    - Score delta calculation and storage
    - Qualification stage tracking
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with qualification score and routing decision
    """
    lead = state["lead"]
    
    # Add the incoming message to the lead's history
    lead.history.append({
        "message": lead.message,
        "timestamp": datetime.now().isoformat(),
        "agent": "user"
    })
    
    # Extract lead information for scoring
    lead_data = {
        'budget': lead.budget,
        'location': lead.location,
        'timeline': lead.timeline,
        'property_type': lead.property_type,
        'desired_bedrooms': lead.desired_bedrooms,
        'email': lead.email,
        'name': lead.name,
        'message': lead.message
    }
    
    # Calculate comprehensive lead score
    scoring_result = calculate_lead_score(
        lead_data,
        previous_score=lead.previous_score,
        conversation_history=lead.history
    )
    
    # Update lead with scoring information
    lead.qualified_score = scoring_result['final_score']
    lead.previous_score = lead.previous_score or scoring_result['final_score']
    lead.score_delta = scoring_result['score_delta']
    lead.qualification_stage = scoring_result['qualification_stage']
    
    # Log scoring event
    audit_log_event("lead_scored", {
        "lead_id": lead.user_id,
        "score": scoring_result['final_score'],
        "previous_score": lead.previous_score,
        "score_delta": scoring_result['score_delta'],
        "qualification_stage": scoring_result['qualification_stage'],
        "routing_recommendation": scoring_result['routing_recommendation']
    })
    
    # Check if qualification should continue
    if lead_scorer.should_continue_qualification(lead_data, scoring_result['final_score']):
        next_question = get_next_qualification_question(lead_data, lead.asked_questions)
        
        if next_question:
            # Store question to prevent repetition
            if next_question['field'] not in lead.asked_questions:
                lead.asked_questions.append(next_question['field'])
            lead.last_question_sent = next_question['field']
            
            # Build qualification question message
            question_message = build_qualification_question(lead, next_question)
            
            # Add to messages
            if "messages" not in state:
                state["messages"] = []
            
            state["messages"].append({
                "role": "assistant",
                "content": question_message
            })
            
            # Update lead history
            lead.history.append({
                "message": f"Asked qualification question: {next_question['field']}",
                "timestamp": datetime.now().isoformat(),
                "agent": "qualifier"
            })
            
            return {
                "lead": lead,
                "messages": state["messages"],
                "requires_more_info": True,
                "next_agent": "qualifier",
                "scoring_result": scoring_result
            }
    
    # Check for missing critical information (PRD Section 3.2)
    missing_info = check_missing_information(lead)
    if missing_info and scoring_result['final_score'] < 0.75:
        result = handle_missing_information(lead, missing_info, state)
        if result.get("requires_more_info"):
            return result
    
    # Build cache key for property search
    cache_key = (
        f"properties:{lead.budget or 'na'}:{lead.location or 'na'}:"
        f"{lead.property_type or 'na'}"
    )

    # Attempt to fetch cached query results first
    try:
        db_results = get_cached_query_result(cache_key, lead.user_id)
    except Exception as cache_error:
        print(f"Error retrieving cached query result: {cache_error}")
        db_results = None

    # Query properties from DB if not cached
    if not db_results:
        db_results = query_properties_db(
            lead.budget or 0,
            lead.location or "",
            lead.property_type or ""
        )

        # Cache the query results for future lookups (24h TTL handled in utility)
        try:
            cache_query_result(cache_key, lead.user_id, db_results)
        except Exception as cache_error:
            print(f"Error caching query result: {cache_error}")
    
    # Check if no properties match the criteria
    if not db_results:
        # Still score the lead even if no properties match
        # This allows low-scoring leads to go to followup
        no_props_result = handle_no_matching_properties(lead, state)
        
        # Get LLM score to determine routing
        score_response = get_llm_response_sync(f"""
        Score this lead (0-1) for real estate interest based on:
        Budget: {lead.budget}
        Location: {lead.location}
        Type: {lead.property_type}
        Timeline: {lead.timeline}

        Note: No properties currently match in database.

        Provide your response as a JSON object with the following structure:
        {{
            "score": 0.8,
            "reasoning": "Explanation of the score"
        }}
        """)
        
        # Parse the score from JSON response
        try:
            import json
            score_data = json.loads(score_response)
            score = float(score_data["score"])
            if score > 1.0:
                score = 1.0
            elif score < 0.0:
                score = 0.0
        except:
            # Fallback to simple parsing if JSON fails
            try:
                score = float(score_response.strip())
                if score > 1.0:
                    score = 1.0
                elif score < 0.0:
                    score = 0.0
            except:
                score = 0.5  # Default score if parsing fails
        
        # Update lead with score (already updated above)
        
        # Route based on scoring result
        routing = scoring_result['routing_recommendation']
        
        if routing['next_agent'] == 'scheduler':
            # High score but no properties - wait for response about waitlist
            return no_props_result
        elif routing['next_agent'] == 'offramp':
            # Low score and no properties - send to offramp
            lead.history.append({
                "message": f"Lead disqualified (score: {scoring_result['final_score']}), sending to offramp despite no matching properties",
                "timestamp": datetime.now().isoformat(),
                "agent": "qualifier"
            })
            return {"lead": lead, "next_agent": "offramp"}
        else:
            # Medium score and no properties - send to followup for nurturing
            lead.history.append({
                "message": f"Lead needs nurturing (score: {scoring_result['final_score']}), sending to followup despite no matching properties",
                "timestamp": datetime.now().isoformat(),
                "agent": "qualifier"
            })
            return {"lead": lead, "next_agent": "followup"}
    
    # Check for budget mismatches
    budget_analysis = detect_budget_mismatch(lead, db_results)
    if budget_analysis.get("detected"):
        # Build budget mismatch message
        recommendations = budget_analysis.get("recommendations", [])
        rec_text = "\n".join([f"• {rec}" for rec in recommendations])
        
        message = f"""Hi {lead.name or 'there'}! 💰 I found {len(db_results)} properties in {lead.location}, but there's a budget consideration:

{budget_analysis.get("suggest_message", "")}

Here are your options:
{rec_text}

Would you like to:
1. See the {budget_analysis.get("affordable_options", 0)} properties slightly closer to your budget?
2. Adjust your search criteria?
3. Get notified when new properties in your range become available?"""

        # Add to messages
        if "messages" not in state:
            state["messages"] = []
        
        state["messages"].append({
            "role": "assistant",
            "content": message
        })
        
        # Update lead history
        lead.history.append({
            "message": f"Budget mismatch detected: {budget_analysis}",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        
        return {
            "lead": lead,
            "messages": state["messages"],
            "budget_mismatch": budget_analysis,
            "requires_more_info": True,
            "next_agent": "qualifier"
        }
    
    # Get thresholds from configuration (with sensible defaults)
    hitl_threshold = float(get_config("hitl_threshold", "0.9"))
    scheduler_threshold = float(get_config("scheduler_threshold", "0.7"))
    
    # Create prompt for LLM to score the lead with explicit scoring rubric
    prompt = f"""
    Score this lead (0-1) for real estate interest based on:
    Budget: {lead.budget}
    Location: {lead.location}
    Type: {lead.property_type}
    Timeline: {lead.timeline}
    
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
    }}
    """
    
    # Get LLM response
    score_response = get_llm_response_sync(prompt)
    
    # Parse the score from JSON response
    try:
        import json
        score_data = json.loads(score_response)
        score = float(score_data["score"])
        if score > 1.0:
            score = 1.0
        elif score < 0.0:
            score = 0.0
    except:
        # Fallback to simple parsing if JSON fails
        try:
            score = float(score_response.strip())
            if score > 1.0:
                score = 1.0
            elif score < 0.0:
                score = 0.0
        except:
            score = 0.5  # Default score if parsing fails
    
    # Add qualification message to the lead's history
    lead.history.append({
        "message": f"Lead qualification complete with score: {scoring_result['final_score']}, routing to {scoring_result['routing_recommendation']['next_agent']}",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    # Determine next agent based on scoring result
    routing = scoring_result['routing_recommendation']
    
    # Save lead with updated information
    try:
        save_lead(lead.model_dump())
    except Exception as save_error:
        print(f"Error saving lead during routing: {save_error}")
    
    # Route based on enhanced scoring thresholds
    if routing['next_agent'] == 'scheduler':
        lead.history.append({
            "message": f"Highly qualified lead (score: {scoring_result['final_score']} >= 0.4), sending to scheduler",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "scheduler"}
    elif routing['next_agent'] == 'offramp':
        lead.history.append({
            "message": f"Lead disqualified (score: {scoring_result['final_score']} < 0.4), sending to offramp",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "offramp"}
    else:  # followup
        lead.history.append({
            "message": f"Lead needs nurturing (score: {scoring_result['final_score']} between 0.4-1.0), sending to followup",
            "timestamp": datetime.now().isoformat(),
            "agent": "qualifier"
        })
        return {"lead": lead, "next_agent": "followup"}

def check_missing_information(lead: Any) -> Dict[str, bool]:
    """
    Check for missing critical information needed for qualification.
    
    Returns a dict of missing fields and their status.
    """
    missing = {}
    
    # Check budget - critical for property search
    if not lead.budget or lead.budget <= 0:
        missing["budget"] = True
    
    # Check location - essential for property search
    if not lead.location or lead.location.strip() == "":
        missing["location"] = True
    
    # Check property preferences (bedrooms or property type)
    bedrooms_missing = not lead.desired_bedrooms or lead.desired_bedrooms <= 0
    property_type_missing = not lead.property_type or lead.property_type.strip() == ""
    
    if bedrooms_missing and property_type_missing:
        missing["property_preferences"] = True
    
    return missing

def handle_missing_information(lead: Any, missing_info: Dict[str, bool], state: AgentState) -> Dict[str, Any]:
    """
    Handle missing information by asking clarification questions.
    
    Returns a state dict that includes clarification questions.
    """
    questions = []
    
    if missing_info.get("budget"):
        questions.append("What's your approximate budget for this purchase?")
    
    if missing_info.get("location"):
        if questions:  # If we already have budget context
            questions.append("What specific area or neighborhood are you interested in?")
        else:
            questions.append("What area or neighborhood are you looking for properties in?")
    
    if missing_info.get("property_preferences"):
        if questions:  # Context already established
            questions.append("What type of property are you looking for (apartment, house, condo)?")
            questions.append("How many bedrooms do you need?")
        else:
            questions.append("What kind of property are you looking for and how many bedrooms?")
    
    # Build clarification message
    if len(questions) == 1:
        message = f"Hi {lead.name or 'there'}! 👋 To help you find the perfect property, could you let me know {questions[0].lower()}"
    else:
        question_list = " ".join([q.rstrip("?") + "," for q in questions[:-1]]) + f" and {questions[-1].rstrip('.?')}?"
        message = f"Hi {lead.name or 'there'}! 👋 To better assist you, could you let me know {question_list.lower()} This will help me find the best options for you."
    
    # Add the clarification to messages
    if "messages" not in state:
        state["messages"] = []
    
    state["messages"].append({
        "role": "assistant", 
        "content": message
    })
    
    # Update lead history
    lead.history.append({
        "message": f"Requests clarification for: {', '.join(missing_info.keys())}",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    return {
        "lead": lead,
        "messages": state["messages"],
        "requires_more_info": True,
        "missing_info": missing_info,
        "next_agent": "qualifier"  # Stay in qualifier until we have complete info
    }

def detect_budget_mismatch(lead: Any, properties: list) -> Dict[str, Any]:
    """
    Detect and handle budget mismatches with available properties.
    
    Returns analysis of budget compatibility and suggestions.
    """
    if not properties:
        return {"mismatch": False, "message": "No properties found"}
    
    # Calculate property price range
    prices = [prop.get("price", 0) for prop in properties if prop.get("price")]
    if not prices:
        return {"mismatch": False, "message": "Property prices not available"}
    
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    # Check if lead's budget is too low for available options
    if lead.budget and lead.budget < min_price:
        shortfall_pct = ((min_price - lead.budget) / lead.budget) * 100
        suggestion = f"Properties in your criteria range from ${min_price:,.0f} to ${max_price:,.0f}, which is about {shortfall_pct:.0f}% higher than your budget."
        
        # Find properties closer to budget
        affordable_options = [prop for prop in properties if prop.get("price", 0) <= lead.budget * 1.1]  # Within 10%
        
        return {
            "mismatch": True,
            "detected": True,
            "budget": lead.budget,
            "price_range": {"min": min_price, "max": max_price, "avg": avg_price},
            "shortfall_pct": shortfall_pct,
            "suggest_message": suggestion,
            "affordable_options": len(affordable_options),
            "recommendations": _generate_budget_mismatch_recommendations(lead, properties)
        }
    
    return {
        "mismatch": False,
        "detected": False,
        "price_range": {"min": min_price, "max": max_price, "avg": avg_price}
    }

def _generate_budget_mismatch_recommendations(lead: Any, properties: list) -> list:
    """Generate recommendations for budget mismatch scenarios."""
    recommendations = []
    
    if not lead.budget:
        return recommendations
    
    # Find smaller properties within budget
    smaller_properties = []
    for prop in properties:
        if prop.get("price", 0) <= lead.budget:
            bedrooms = prop.get("bedrooms", 0)
            if bedrooms and bedrooms > 0:  # Valid bedroom count
                smaller_properties.append(prop)
    
    if smaller_properties:
        min_bedrooms = min(prop.get("bedrooms", 0) for prop in smaller_properties)
        recommendations.append(f"Consider {min_bedrooms}-bedroom options within your budget")
    
    # Consider higher budget
    min_price = min(prop.get("price", 0) for prop in properties)
    if min_price > lead.budget:
        needed_budget = min_price * 0.8  # Suggest 80% of min price as target
        recommendations.append(f"Properties in your area start around ${min_price:,.0f}. Consider a budget of ${needed_budget:,.0f}+")
    
    # Suggest waitlist
    recommendations.append("Join our waitlist for new properties matching your criteria")
    
    return recommendations[:3]  # Top 3 recommendations

def handle_no_matching_properties(lead: Any, state: AgentState) -> Dict[str, Any]:
    """
    Handle scenario where no properties match the lead's criteria.
    
    Waitlist/Alert handling per PRD Section 3.2.
    """
    message = f"""Hi {lead.name or 'there'}! 👋 

I don't currently have properties matching your exact criteria. Here are your options:

🔔 **Get Notified**: Join our waitlist and I'll alert you when new properties matching your needs become available.

🎯 **Broaden Search**: Would you be open to:
   • Expanding your budget range
   • Considering nearby neighborhoods  
   • Looking at properties with slightly different features

📱 **Personal Consultation**: I can schedule a free consultation to discuss alternatives.

Would you like me to add you to our waitlist for: {lead.budget or 'flexible budget'}, {lead.location or 'your preferred area'}, {lead.desired_bedrooms or 'your preferred bedrooms'} bedrooms?"""

    # Add to messages
    if "messages" not in state:
        state["messages"] = []
    
    state["messages"].append({
        "role": "assistant",
        "content": message
    })
    
    # Update lead history
    lead.history.append({
        "message": f"No matching properties found - offered waitlist and alternatives",
        "timestamp": datetime.now().isoformat(),
        "agent": "qualifier"
    })
    
    return {
        "lead": lead,
        "messages": state["messages"],
        "no_properties_found": True,
        "requires_more_info": True,  # Need response about waitlist
        "next_agent": "qualifier"
    }

def build_qualification_question(lead: Any, question_data: Dict[str, Any]) -> str:
    """
    Build personalized qualification question based on lead context.
    
    Args:
        lead: Lead object
        question_data: Question information from scoring system
        
    Returns:
        Personalized question message
    """
    field = question_data['field']
    question = question_data['question']
    
    # Personalize based on lead name
    name = lead.name or 'there'
    
    # Add context based on what we already know
    context_parts = []
    
    if lead.budget and field != 'budget':
        context_parts.append(f"budget of ${lead.budget:,}")
    
    if lead.location and field != 'location':
        context_parts.append(f"area in {lead.location}")
    
    if lead.timeline and field != 'timeline':
        context_parts.append(f"timeline of {lead.timeline}")
    
    # Build contextual question
    if context_parts:
        context_str = ", ".join(context_parts)
        return f"Hi {name}! 👋 Thanks for sharing your {context_str}. To help you find the perfect property, {question.lower()}"
    else:
        return f"Hi {name}! 👋 {question}"

def check_compliance_requirements(lead: Any, location: Optional[str] = None) -> Dict[str, Any]:
    """
    Check state-specific compliance requirements for real estate.
    
    Args:
        lead: Lead object
        location: Specific location if different from lead.location
        
    Returns:
        Compliance check results
    """
    compliance_issues = []
    
    # Check for TCPA consent if phone number is present
    if hasattr(lead, 'phone') and lead.phone:
        if not lead.tcpa_opt_in:
            compliance_issues.append("TCPA consent required for SMS communication")
    
    # Check for fair housing compliance
    message = lead.message.lower() if lead.message else ""
    protected_classes = ["race", "color", "religion", "sex", "national origin", "familial status", "disability"]
    
    for protected_class in protected_classes:
        if protected_class in message:
            compliance_issues.append(f"Potential fair housing violation: {protected_class}")
    
    # State-specific requirements (simplified)
    if location:
        location_lower = location.lower()
        if "california" in location_lower:
            compliance_issues.append("California: Ensure compliance with CA Fair Housing and BRELA")
        elif "new york" in location_lower:
            compliance_issues.append("New York: Ensure compliance with NY Human Rights Law")
    
    return {
        "compliant": len(compliance_issues) == 0,
        "issues": compliance_issues,

# Phase 2: Rules-First Qualification Engine
def qualifier_node_phase2(state: AgentState) -> Dict[str, Any]:
    """
    Phase 2: Rules-First Qualification Engine with transparent scoring.
    
    Implements the refined qualification requirements:
    - 3-5 targeted questions mapped to real estate offer
    - Transparent scoring rules with clear breakdown
    - Qualification state machine with structured progression
    - Question priority and logic flow using LLM
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with qualification score and routing decision
    """
    lead = state["lead"]
    
    # Add the incoming message to the lead's history
    lead.history.append({
        "message": lead.message,
        "timestamp": datetime.now().isoformat(),
        "agent": "user"
    })
    
    # Prepare lead data for Phase 2 transparent scoring
    lead_data = {
        'user_id': lead.user_id,
        'budget': lead.budget,
        'location': lead.location,
        'timeline': lead.timeline,
        'property_type': lead.property_type,
        'desired_bedrooms': lead.desired_bedrooms,
        'email': lead.email,
        'name': lead.name,
        'message': lead.message,
        'role': getattr(lead, 'role', None),
        'use_case': getattr(lead, 'use_case', None)
    }
    
    try:
        # Generate transparent scoring breakdown
        scoring_result = generate_transparent_scoring_breakdown(lead_data, "real_estate")
        
        if scoring_result["success"]:
            phase2_scoring = scoring_result["scoring_result"]
            qualification_score = phase2_scoring.get("total_score", 0.5)
            qualification_state = phase2_scoring.get("qualification_state", "initial_contact")
            
            # Update lead with Phase 2 scoring information
            lead.qualified_score = qualification_score
            lead.qualification_stage = qualification_state
            lead.scoring_breakdown = phase2_scoring.get("scoring_breakdown", {})
            lead.budget_band_analysis = phase2_scoring.get("budget_band_analysis", {})
            lead.role_analysis = phase2_scoring.get("role_analysis", {})
            
            # Log Phase 2 scoring event
            audit_log_event("phase2_lead_scored", {
                "lead_id": lead.user_id,
                "score": qualification_score,
                "qualification_state": qualification_state,
                "budget_band": phase2_scoring.get("budget_band_analysis", {}).get("detected_band"),
                "role": phase2_scoring.get("role_analysis", {}).get("identified_role"),
                "phase_2_features": True
            })
            
            # Check if qualification should continue using Phase 2 gates
            readiness_assessment = assess_qualification_readiness(
                lead_data, qualification_score, getattr(lead, 'asked_questions', [])
            )
            
            # Continue qualification if not ready for scheduler
            if not readiness_assessment.get("ready_for_scheduler", False):
                # Use LLM to prioritize next questions
                question_priorities = prioritize_questions_llm(
                    lead_data, 
                    getattr(lead, 'asked_questions', []),
                    qualification_state
                )
                
                if question_priorities and question_priorities.get("prioritized_questions"):
                    next_question_data = question_priorities["prioritized_questions"][0]
                    
                    # Store question to prevent repetition
                    question_category = next_question_data["category"]
                    if question_category not in getattr(lead, 'asked_questions', []):
                        if not hasattr(lead, 'asked_questions'):
                            lead.asked_questions = []
                        lead.asked_questions.append(question_category)
                    
                    lead.last_question_sent = question_category
                    
                    # Build qualification question message with transparency
                    question_message = build_transparent_qualification_question(
                        lead, next_question_data, phase2_scoring
                    )
                    
                    # Add to messages
                    if "messages" not in state:
                        state["messages"] = []
                    
                    state["messages"].append({
                        "role": "assistant",
                        "content": question_message
                    })
                    
                    # Update lead history
                    lead.history.append({
                        "message": f"Asked Phase 2 qualification question: {question_category}",
                        "timestamp": datetime.now().isoformat(),
                        "agent": "qualifier"
                    })
                    
                    return {
                        "lead": lead,
                        "messages": state["messages"],
                        "requires_more_info": True,
                        "next_agent": "qualifier",
                        "phase_2_qualification": True,
                        "transparency_enabled": True,
                        "scoring_breakdown": phase2_scoring.get("scoring_breakdown", {}),
                        "readiness_assessment": readiness_assessment
                    }
            
            # Ready for scheduler handoff
            if readiness_assessment.get("ready_for_scheduler", False):
                lead.history.append({
                    "message": f"Lead qualified for scheduler (score: {qualification_score:.3f}) with Phase 2 transparent scoring",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "qualifier"
                })
                return {"lead": lead, "next_agent": "scheduler", "phase_2_qualified": True}
            else:
                # Not ready, send to followup for nurturing
                lead.history.append({
                    "message": f"Lead needs nurturing (score: {qualification_score:.3f}) - Phase 2 assessment",
                    "timestamp": datetime.now().isoformat(),
                    "agent": "qualifier"
                })
                return {"lead": lead, "next_agent": "followup", "phase_2_nurturing": True}
                
        else:
            # Fallback to original scoring if Phase 2 fails
            logger.warning(f"Phase 2 scoring failed: {scoring_result.get('error')}, falling back to Phase 1")
            return qualifier_node(state)
            
    except Exception as e:
        logger.error(f"Phase 2 qualification error: {e}")
        # Fallback to original qualifier
        return qualifier_node(state)

def build_transparent_qualification_question(
    lead: Any, 
    question_data: Dict[str, Any], 
    scoring_data: Dict[str, Any]
) -> str:
    """
    Build transparent qualification question with scoring context.
    
    Args:
        lead: Lead object
        question_data: Question information from LLM prioritization
        scoring_data: Current scoring breakdown
        
    Returns:
        Transparent question message with context
    """
    name = lead.name or 'there'
    category = question_data['category']
    question = question_data['question']
    reasoning = question_data.get('reasoning', '')
    expected_impact = question_data.get('expected_impact', 0)
    
    # Build transparent context
    context_parts = []
    
    # Add scoring context
    if scoring_data:
        budget_score = scoring_data.get('scoring_breakdown', {}).get('budget_score', 0)
        role_score = scoring_data.get('scoring_breakdown', {}).get('role_clarity_score', 0)
        
        if budget_score < 0.6:
            context_parts.append(f"Your budget alignment score is {budget_score:.1f}")
        if role_score < 0.6:
            context_parts.append(f"Role clarity needs improvement (current: {role_score:.1f})")
    
    # Build the question message
    if context_parts:
        context_str = ". ".join(context_parts)
        message = f"""Hi {name}! 👋 Thanks for the information.
        
📊 **Current Qualification Status:**
{context_str}

To help me provide better property matches, {question.lower()}

💡 **Why this helps:** {reasoning}
🎯 **Expected improvement:** +{expected_impact:.1f} to your qualification score"""
    else:
        message = f"Hi {name}! 👋 {question}"
    
    return message.strip()

# Enhanced qualification flow with conditional progression
def execute_conditional_qualification_flow(
    state: AgentState, 
    current_stage: str = "initial_contact"
) -> Dict[str, Any]:
    """
    Execute conditional qualification flow based on current stage and responses.
    
    Args:
        state: Current agent state
        current_stage: Current qualification stage
        
    Returns:
        Updated state with next actions
    """
    lead = state["lead"]
    
    try:
        # Get stage-specific configuration
        from tools.qualifier_utils import QUALIFICATION_STATES
        
        stage_config = QUALIFICATION_STATES.get(current_stage, {})
        threshold_score = stage_config.get("threshold_score", 0.2)
        questions_needed = stage_config.get("questions", 1)
        
        # Analyze current qualification score
        current_score = getattr(lead, 'qualified_score', 0.0)
        asked_questions = getattr(lead, 'asked_questions', [])
        
        # Determine if we should advance to next stage
        should_advance = (
            current_score >= threshold_score and 
            len(asked_questions) >= questions_needed
        )
        
        if should_advance:
            next_state = stage_config.get("next_state", current_stage)
            
            # Log stage advancement
            lead.history.append({
                "message": f"Advanced from {current_stage} to {next_state} (score: {current_score:.3f})",
                "timestamp": datetime.now().isoformat(),
                "agent": "qualifier"
            })
            
            return {
                "lead": lead,
                "next_stage": next_state,
                "stage_advanced": True,
                "current_score": current_score,
                "questions_asked": len(asked_questions)
            }
        else:
            # Continue current stage
            return {
                "lead": lead,
                "next_stage": current_stage,
                "stage_advanced": False,
                "current_score": current_score,
                "questions_needed": questions_needed - len(asked_questions)
            }
            
    except Exception as e:
        logger.error(f"Conditional qualification flow error: {e}")
        return {
            "lead": lead,
            "next_stage": current_stage,
            "stage_advanced": False,
            "error": str(e)
        }
        "warnings": [] if len(compliance_issues) == 0 else ["Review compliance requirements before proceeding"]
    }