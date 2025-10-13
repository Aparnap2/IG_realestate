"""
LLM client for OpenRouter API integration according to PRD specifications.
"""
import os
import aiohttp
import asyncio
import json
import threading
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Default model selection
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

async def get_llm_response(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> str:
    """
    Get response from OpenRouter LLM using async HTTP client.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model to use (default: Claude 3.5 Sonnet)
        max_tokens: Maximum tokens in response
        temperature: Temperature for response generation
        
    Returns:
        LLM response text
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key not configured"
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aaa-real-estate.com",
                "X-Title": "AAA Real Estate Lead Capture System"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    error_text = await response.text()
                    print(f"OpenRouter API error: {response.status} - {error_text}")
                    return "I apologize, but I'm having trouble processing your request right now. Please try again later."
                    
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again later."


def _run_coro_sync(coro_fn, *args, **kwargs):
    """Run an async coroutine in a blocking context using a dedicated thread."""
    try:
        return asyncio.run(coro_fn(*args, **kwargs))
    except RuntimeError:
        # Likely inside an active event loop; execute in separate thread
        result_container: Dict[str, Any] = {}
        exception_container: Dict[str, BaseException] = {}

        def _runner():
            try:
                result_container["value"] = asyncio.run(coro_fn(*args, **kwargs))
            except BaseException as exc:  # noqa: BLE001 - propagate any exception
                exception_container["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in exception_container:
            raise exception_container["error"]

        return result_container.get("value")


def get_llm_response_sync(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> str:
    """Blocking wrapper around get_llm_response for sync contexts."""
    return _run_coro_sync(
        get_llm_response,
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature
    )

def get_structured_llm_response(
    prompt: str,
    response_format: Dict[str, Any],
    model: str = "anthropic/claude-3.5-sonnet"
) -> Dict[str, Any]:
    """
    Get structured response from LLM with specific format.
    
    Args:
        prompt: The prompt to send to the LLM
        response_format: Expected response format
        model: Model to use
        
    Returns:
        Structured response dictionary
    """
    try:
        # Add format instructions to prompt
        format_prompt = f"{prompt}\n\nPlease respond in the following JSON format:\n{response_format}"

        response = get_llm_response_sync(format_prompt, model=model)
        
        # Try to parse as JSON
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Return default structure if parsing fails
            return {"error": "Failed to parse structured response", "raw_response": response}
            
    except Exception as e:
        print(f"Error getting structured LLM response: {e}")
        return {"error": str(e)}

def extract_lead_info(message: str) -> Dict[str, Any]:
    """
    Extract lead information from a message using LLM.
    
    Args:
        message: The lead's message
        
    Returns:
        Dictionary with extracted information
    """
    prompt = f"""
    Extract real estate lead information from this message: "{message}"
    
    Look for:
    - Budget (in USD)
    - Location (city/area)
    - Property type (1BHK, 2BHK, 3BHK, Condo, etc.)
    - Timeline (when they want to buy/rent)
    - Any other relevant details
    
    Respond in JSON format:
    {{
        "budget": null or number,
        "location": null or string,
        "property_type": null or string,
        "timeline": null or string,
        "other_details": null or string
    }}
    """
    
    return get_structured_llm_response(prompt, {
        "budget": "number or null",
        "location": "string or null", 
        "property_type": "string or null",
        "timeline": "string or null",
        "other_details": "string or null"
    })

def generate_response_message(
    lead_info: Dict[str, Any],
    context: str = "",
    agent_type: str = "qualifier"
) -> str:
    """
    Generate a response message for a lead.
    
    Args:
        lead_info: Information about the lead
        context: Additional context
        agent_type: Type of agent generating response
        
    Returns:
        Generated response message
    """
    if agent_type == "qualifier":
        prompt = f"""
        You are a real estate qualification agent. A lead has contacted us with this information:
        {lead_info}
        
        Context: {context}
        
        Generate a friendly, professional response that:
        1. Acknowledges their interest
        2. Asks for any missing key information (budget, location, property type, timeline)
        3. Keeps the conversation moving forward
        4. Is concise and engaging
        
        Respond as if you're texting the lead directly.
        """
    elif agent_type == "scheduler":
        prompt = f"""
        You are a real estate scheduling agent. A qualified lead needs to schedule a property tour:
        {lead_info}
        
        Context: {context}
        
        Generate a response that:
        1. Congratulates them on being qualified
        2. Offers to schedule a property tour
        3. Asks for their preferred time/date
        4. Is professional and enthusiastic
        
        Respond as if you're texting the lead directly.
        """
    elif agent_type == "followup":
        prompt = f"""
        You are a real estate follow-up agent. This lead needs nurturing:
        {lead_info}
        
        Context: {context}
        
        Generate a response that:
        1. Stays helpful and engaged
        2. Offers relevant property suggestions
        3. Keeps the door open for future opportunities
        4. Is warm and professional
        
        Respond as if you're texting the lead directly.
        """
    else:
        prompt = f"Generate a professional real estate response for: {lead_info}"
    
    return get_llm_response_sync(prompt)
