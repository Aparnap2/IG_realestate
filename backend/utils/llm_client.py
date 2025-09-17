from openai import OpenAI
import os

# Initialize OpenAI client for OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def get_llm_response(prompt: str, model: str = "anthropic/claude-3.5-sonnet") -> str:
    """
    Get a response from the LLM via OpenRouter.
    
    Args:
        prompt: The prompt to send to the LLM
        model: The model to use (default: claude-3.5-sonnet)
        
    Returns:
        Response from the LLM
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content