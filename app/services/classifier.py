import json
from app.services.llm_service import call_llm

VALID_CATEGORIES = {
    "ecommerce", "finance", "education", "healthcare", "government",
    "social_media", "travel", "entertainment", "saas", "news_media",
    "insurance", "other",
}

_SYSTEM_PROMPT = """You are a website classification expert.
Classify the website strictly based on the crawled evidence provided.
Do NOT classify based on the domain name or URL alone.

Respond with a JSON object in this exact format:
{
    "category": "<category>",
    "confidence": <float 0.0 to 1.0>,
    "reason": "<one sentence citing specific evidence from the crawled data>"
}

Valid categories: ecommerce, finance, education, healthcare, government, social_media, travel, entertainment, saas, news_media, insurance, other"""


def _extract_evidence(crawler_data: dict) -> dict:
    return {
        "url": crawler_data.get("url", ""),
        "title": crawler_data.get("title", ""),
        "description": crawler_data.get("description", ""),
        "page_titles": crawler_data.get("page_titles", []),
        "page_text": str(crawler_data.get("page_text", crawler_data.get("page_content", "")))[:3000],
        "forms": crawler_data.get("forms", []),
        "products_services": crawler_data.get("products_services", []),
        "personal_data_collected": crawler_data.get("personal_data_collected", []),
        "cookies": crawler_data.get("cookies", []),
        "consent_mechanisms": crawler_data.get("consent_mechanisms", []),
        "privacy_policy": crawler_data.get("privacy_policy", crawler_data.get("privacy_policy_text", "")),
    }


async def classify_website(crawler_data: dict) -> dict:
    evidence = _extract_evidence(crawler_data)
    user_prompt = f"Crawled website evidence:\n{json.dumps(evidence, indent=2)}"

    result = await call_llm(_SYSTEM_PROMPT, user_prompt)

    category = result.get("category", "other")
    if category not in VALID_CATEGORIES:
        category = "other"

    return {
        "category": category,
        "confidence": float(result.get("confidence", 0.0)),
        "reason": result.get("reason", ""),
    }
