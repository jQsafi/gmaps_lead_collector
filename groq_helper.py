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

def suggest_search_queries_and_strategy(
    user_goal_or_product: str,
    location: str = "",
    api_key: Optional[str] = None
) -> Dict:
    """
    Analyzes what product/service the user wants to sell and their target location,
    identifies the exact prospective buyer business types, generates high-intent Google Maps
    search queries to find those leads, and provides B2B sales strategy & WhatsApp pitch.
    """
    import json
    client = get_groq_client(api_key)

    loc_text = f"Target Location: {location}" if location else "Target Location specified in query"
    user_prompt = f"""User request: {user_goal_or_product}
{loc_text}

You are an elite B2B sales consultant and Google Maps lead generation specialist.
The user wants to find commercial client businesses on Google Maps to sell their product/service to.

Please analyze:
1. Who are the commercial target businesses in that location who BUY or NEED this product/service?
2. Generate 6-10 specific, high-intent Google Maps search queries to find those PROSPECT businesses (e.g., if selling POS software in Dhanmondi, suggest 'restaurants in Dhanmondi', 'pharmacies in Dhanmondi', 'super shop in Dhanmondi', 'clothing boutique in Dhanmondi').
3. Actionable sales & outreach strategy on how to approach and close deals with these local businesses on WhatsApp.
4. A high-converting cold outreach WhatsApp pitch message.

Return a valid JSON object with the following exact keys:
- "target_buyers": A clear description of the buyer business types.
- "suggested_queries": A list of 6-10 exact Google Maps search query strings.
- "sales_strategy": Strategic actionable advice for selling to these businesses.
- "recommended_pitch": A short, persuasive cold WhatsApp message to send them.
"""

    try:
        resp = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": "You are an elite B2B growth strategist. Output valid JSON only."},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=1400
        )
        data = json.loads(resp.choices[0].message.content)
        return data
    except Exception as e:
        default_queries = [
            f"shops in {location}".strip(),
            f"restaurants in {location}".strip(),
            f"businesses in {location}".strip()
        ]
        return {
            "target_buyers": f"Businesses in {location} interested in {user_goal_or_product}",
            "suggested_queries": [q for q in default_queries if q],
            "sales_strategy": "Reach out directly via WhatsApp introducing your service and offering a quick free consultation.",
            "recommended_pitch": f"Hello {{Name}}, we noticed your business in {{Address}}. We help local companies with {user_goal_or_product}. Are you open to a brief chat?",
            "error": str(e)
        }


