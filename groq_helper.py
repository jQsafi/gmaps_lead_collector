import os
from typing import Tuple, Dict, Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DEFAULT_MODEL = "openai/gpt-oss-120b"
FAST_MODEL = "openai/gpt-oss-20b"

def get_groq_api_key(api_key: Optional[str] = None) -> str:
    """Retrieve Groq API key from argument or environment variable."""
    if api_key and api_key.strip():
        return api_key.strip()
    return os.environ.get("GROQ_API_KEY", "").strip()

def get_groq_client(api_key: Optional[str] = None) -> Groq:
    """Initialize Groq client with API key."""
    key = get_groq_api_key(api_key)
    if not key:
        raise ValueError("Groq API Key is not set. Please provide it or set GROQ_API_KEY in .env.")
    return Groq(api_key=key)

def test_groq_connection(api_key: Optional[str] = None) -> Tuple[bool, str]:
    """Test Groq API connectivity and authentication."""
    try:
        client = get_groq_client(api_key)
        resp = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[{"role": "user", "content": "Respond with 'OK' only."}],
            max_tokens=10
        )
        return True, "Groq API connected successfully!"
    except Exception as e:
        return False, f"Groq API connection error: {str(e)}"

def generate_outreach_template(
    goal: str, 
    niche: str = "", 
    tone: str = "Friendly & Professional",
    api_key: Optional[str] = None
) -> str:
    """
    Uses Groq LLM to generate an optimized WhatsApp outreach template with variables.
    """
    client = get_groq_client(api_key)
    prompt = f"""You are an elite B2B sales copywriter crafting cold outreach messages for WhatsApp.
Write a concise, high-converting WhatsApp message template for reaching out to business owners.

Goal of outreach: {goal}
Target niche / business type: {niche or 'General local business'}
Tone: {tone}

Important formatting rules:
- Must be concise (under 50 words) suitable for WhatsApp reading.
- Must feel authentic and human, not generic spam.
- Include placeholders where appropriate: {{Name}} (business name), {{Category}} (business type), {{Address}} (business location), and/or {{Website}}.
- End with a low-friction question or call to action.
- Output ONLY the template text. Do not include markdown quotes, explanations, or introductory text.
"""
    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional B2B outreach copywriter. Return only the message template."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception as e:
        return f"Error generating template: {str(e)}"

def generate_personalized_message(
    lead: Dict,
    offering: str,
    tone: str = "Friendly & Professional",
    api_key: Optional[str] = None
) -> str:
    """
    Generates a bespoke personalized WhatsApp message specifically for one business.
    """
    client = get_groq_client(api_key)
    biz_name = lead.get("Name", "Business Owner")
    category = lead.get("Category", "Business")
    address = lead.get("Address", "")
    rating = lead.get("Rating", "")
    website = lead.get("Website", "")

    prompt = f"""Write a 1-to-1 personalized WhatsApp message to this business:
- Business Name: {biz_name}
- Category: {category}
- Location/Address: {address}
- Rating: {rating} stars
- Website: {website or 'No website listed'}

Our service/offer: {offering}
Tone: {tone}

Rules:
- Under 50 words.
- Specifically reference their business name ({biz_name}) and category.
- If they don't have a website and the offer involves web design/tech, mention that politely.
- Low-friction question at the end.
- Output ONLY the message.
"""
    try:
        resp = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert sales representative writing direct WhatsApp messages. Output only the final message."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception as e:
        return f"Hello {biz_name}, I noticed your {category} in {address}. Are you accepting new clients?"

