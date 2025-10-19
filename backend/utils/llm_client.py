"""
LLM client for OpenRouter API integration with Gemini fallback according to PRD specifications.
"""
import os
import aiohttp
import asyncio
import json
import threading
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google Generative AI not available. Install with: pip install google-generativeai")

# Default model selection - use more efficient free models
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

async def get_gemini_response(prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
    """
    Get response from Google Gemini Pro as fallback.
    
    Args:
        prompt: The prompt to send to Gemini
        max_tokens: Maximum tokens in response
        temperature: Temperature for response generation
        
    Returns:
        Gemini response text
    """
    if not GEMINI_AVAILABLE:
        print("⚠️ Gemini not available, skipping fallback")
        return None
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️ Google API key not configured for Gemini fallback")
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        print(f"🔥 Calling Gemini Pro as fallback")
        
        response = model.generate_content(prompt)
        
        if response.text:
            print(f"✅ Gemini response received")
            return response.text.strip()
        else:
            print(f"❌ Gemini returned empty response")
            return None
            
    except Exception as e:
        print(f"❌ Error getting Gemini response: {e}")
        return None

async def get_llm_response(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> str:
    """
    Get response from OpenRouter LLM with Gemini fallback.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model to use (default: meta-llama/llama-3.2-3b-instruct:free)
        max_tokens: Maximum tokens in response
        temperature: Temperature for response generation
        
    Returns:
        LLM response text
    """
    # Try OpenRouter first
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        print(f"🤖 Calling OpenRouter with model: {model}")
        
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
                        print(f"✅ OpenRouter response received")
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        error_text = await response.text()
                        print(f"❌ OpenRouter API error: {response.status} - {error_text}")
                        if response.status == 429:
                            print(f"💡 Rate limit reached. Trying Gemini fallback...")
                        # Fall through to Gemini
                        
        except Exception as e:
            print(f"❌ Error getting OpenRouter response: {e}")
            print(f"💡 Trying Gemini fallback...")
    else:
        print("⚠️ OpenRouter API key not configured, trying Gemini...")
    
    # Try Gemini as fallback
    gemini_response = await get_gemini_response(prompt, max_tokens, temperature)
    if gemini_response:
        return gemini_response
    
    # If both fail, return fallback message
    return "I apologize, but I'm having trouble processing your request right now. Please try again later."


def _run_coro_sync(coro_fn, *args, **kwargs):
    """Run an async coroutine in a blocking context using a dedicated thread."""
    result_container: Dict[str, Any] = {}
    exception_container: Dict[str, BaseException] = {}

    def _runner():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_container["value"] = loop.run_until_complete(coro_fn(*args, **kwargs))
            finally:
                loop.close()
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
    model: str = DEFAULT_OPENROUTER_MODEL
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

        response = _run_coro_sync(get_llm_response, format_prompt, model=model)
        
        # Try to parse as JSON
        import json
        import re
        try:
            # Strip markdown code blocks if present
            cleaned = re.sub(r'^```json\s*|\s*```$', '', response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r'^```\s*|\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
            
            # Handle case where LLM returns explanatory text before JSON
            if '{' in cleaned and '}' in cleaned:
                # Extract JSON from the response
                start_idx = cleaned.find('{')
                end_idx = cleaned.rfind('}') + 1
                json_str = cleaned[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Return default structure if parsing fails
            print(f"⚠️ JSON parsing failed: {e}")
            print(f"   Response was: {response[:200]}...")
            return {"error": "Failed to parse structured response", "raw_response": response}
            
    except Exception as e:
        print(f"❌ Error getting structured LLM response: {e}")
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
    
    return _run_coro_sync(get_llm_response, prompt)
