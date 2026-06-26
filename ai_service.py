"""OpenAI helpers for MAXEK ERP AI features."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class OpenAIConfigurationError(Exception):
    """Raised when OPENAI_API_KEY is missing or invalid."""


def get_openai_client() -> OpenAI:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise OpenAIConfigurationError(
            "OPENAI_API_KEY is not configured. Set it in the server environment."
        )
    return OpenAI(api_key=api_key)


def chat_completion(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> str:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model or OPENAI_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = response.choices[0].message.content if response.choices else ""
    return (choice or "").strip()


def chat_completion_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    text = chat_completion(
        system + "\nRespond with valid JSON only, no markdown fences.",
        user,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("AI returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("AI JSON response must be an object.")
    return parsed
