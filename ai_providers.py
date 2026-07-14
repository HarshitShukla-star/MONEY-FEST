import json
from typing import Any, Optional, Tuple

import httpx


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def _strip_json_wrappers(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1]
    return text


def parse_json_text(text: str) -> Any:
    return json.loads(_strip_json_wrappers(text))


def groq_chat_text(
    api_key: str,
    prompt: str,
    model: str = DEFAULT_GROQ_MODEL,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    if not api_key:
        raise ValueError("Missing GROQ_API_KEY")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def best_available_text_provider(
    prompt: str,
    gemini_key: Optional[str] = None,
    groq_key: Optional[str] = None,
    gemini_model: str = "gemini-flash-latest",
    groq_model: str = DEFAULT_GROQ_MODEL,
    system_prompt: Optional[str] = None,
    prefer_gemini: bool = True,
) -> Tuple[str, str]:
    last_error: Optional[Exception] = None
    providers = []
    if prefer_gemini:
        providers = ["gemini", "groq"]
    else:
        providers = ["groq", "gemini"]

    for provider in providers:
        try:
            if provider == "gemini" and gemini_key:
                from google import genai

                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=prompt,
                )
                return response.text or "", "gemini"

            if provider == "groq" and groq_key:
                return groq_chat_text(
                    api_key=groq_key,
                    prompt=prompt,
                    model=groq_model,
                    system_prompt=system_prompt,
                ), "groq"
        except Exception as e:
            last_error = e

    raise RuntimeError(f"No available provider succeeded: {last_error}")
