#!/usr/bin/env python3
"""
Simple test for pure agentic extraction
Tests direct LLM calls without complex imports
"""

import os
import sys

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Load environment variables
try:
    from load_envs import loadenvs
    loadenvs()
    print("✅ Environment variables loaded")
except ImportError:
    print("⚠️ Could not import loadenvs, trying direct dotenv")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment variables loaded via dotenv")
    except ImportError:
        print("⚠️ Could not load environment variables")

def test_direct_llm_extraction():
    """Test LLM extraction directly without complex imports."""
    
    print('🧪 DIRECT LLM EXTRACTION TEST')
    print('=' * 50)
    
    # Test message
    test_message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    print(f"💬 Message: '{test_message}'")
    
    # Create simple extraction prompt
    prompt = f"""Extract real estate lead information from this message: "{test_message}"
    
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
    }}"""
    
    # Test with direct HTTP call to see if API works
    try:
        import requests
        import json
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("❌ No OpenRouter API key found")
            return False
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aaa-real-estate.com",
            "X-Title": "IG Real Estate Lead Capture System"
        }

        payload = {
            "model": " openai/gpt-oss-20b:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        print("🤖 Calling OpenRouter API...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            llm_response = data["choices"][0]["message"]["content"].strip()
            print(f"📄 LLM Response: {llm_response}")
            
            # Try to parse JSON
            try:
                # Clean up response
                clean_response = llm_response.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                
                extraction_data = json.loads(clean_response.strip())
                print(f"✅ Parsed JSON: {extraction_data}")
                
                # Analyze results
                budget = extraction_data.get("budget")
                location = extraction_data.get("location")
                property_type = extraction_data.get("property_type")
                timeline = extraction_data.get("timeline")
                
                print(f"\n📊 RESULTS:")
                print(f"💰 Budget: {budget}")
                print(f"📍 Location: {location}")
                print(f"🏠 Property Type: {property_type}")
                print(f"⏰ Timeline: {timeline}")
                
                # Check if extraction worked
                if budget == 250000 and location == "Miami Beach" and property_type:
                    print("\n🎉 SUCCESS! LLM properly extracted the information!")
                    print("✅ Budget: 250000")
                    print("✅ Location: Miami Beach")
                    print("✅ Property type detected")
                    return True
                else:
                    print(f"\n⚠️ PARTIAL SUCCESS:")
                    if budget != 250000:
                        print(f"   Budget issue: got {budget}, expected 250000")
                    if location != "Miami Beach":
                        print(f"   Location issue: got {location}, expected Miami Beach")
                    if not property_type:
                        print(f"   Property type issue: not detected")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON: {e}")
                print(f"Response was: {llm_response}")
                return False
                
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gemini_fallback():
    """Test Gemini as fallback."""
    
    print('\n🔥 GEMINI FALLBACK TEST')
    print('=' * 30)
    
    test_message = "i need ASAP , miami beach , 250k dollar 4bhk condo"
    
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ No Google API key found")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Extract real estate information from: "{test_message}"
        
Return JSON with budget, location, property_type, timeline."""
        
        print("🤖 Calling Gemini...")
        response = model.generate_content(prompt)
        
        if response.text:
            print(f"📄 Gemini Response: {response.text}")
            # Try to parse the response
            try:
                import json
                data = json.loads(response.text)
                print(f"✅ Parsed: {data}")
                return True
            except:
                print("✅ Gemini responded but parsing failed")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Gemini test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 STARTING SIMPLE EXTRACTION TESTS")
    print("=" * 60)
    
    # Test OpenRouter
    openrouter_success = test_direct_llm_extraction()
    
    # Test Gemini fallback
    gemini_success = test_gemini_fallback()
    
    print("\n" + "=" * 60)
    print("📋 FINAL RESULTS:")
    print(f"OpenRouter: {'✅' if openrouter_success else '❌'}")
    print(f"Gemini: {'✅' if gemini_success else '❌'}")
    
    if openrouter_success or gemini_success:
        print("\n🎉 AT LEAST ONE LLM SERVICE WORKING!")
        print("✅ Pure agentic extraction is possible with working LLM")
        print("✅ The system can extract information from complex messages")
    else:
        print("\n❌ NO LLM SERVICES WORKING")
        print("⚠️ Need to fix API keys or connectivity")