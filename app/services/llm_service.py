import json
import httpx
from app.config import settings

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


async def call_llm(system_prompt: str, user_prompt: str) -> dict:
    url = _GEMINI_URL.format(model=settings.GEMINI_MODEL, key=settings.GEMINI_API_KEY)
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(2):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Gemini API error {e.response.status_code}: {e.response.text}") from e
            except (httpx.ReadError, httpx.TimeoutException) as e:
                if attempt == 1:
                    raise RuntimeError(f"Gemini request failed: {e}") from e
        else:
            raise RuntimeError("Gemini request failed")

    content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(content)
