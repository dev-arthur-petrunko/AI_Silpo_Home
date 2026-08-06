"""Мінімальний клієнт для LLM через Groq (OpenAI-сумісний chat completions).

Використовується tone_profiler (аналіз тону групи) і reminders (генерація
нагадувань). Ніяких сторонніх залежностей — звичайний httpx.
"""
from __future__ import annotations

import json
import logging

import httpx

from core.config import Settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM call failed or returned unusable output."""


def _headers(settings: Settings) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.groq_api_key:
        headers["Authorization"] = f"Bearer {settings.groq_api_key}"
    return headers


async def llm_text(
    settings: Settings,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Викликає chat completions, повертає текст відповіді."""
    if not settings.groq_api_key:
        raise LLMError("GROQ_API_KEY не задано")
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=settings.groq_request_timeout_seconds) as client:
        resp = await client.post(settings.groq_base_url, json=payload, headers=_headers(settings))
    if resp.status_code >= 400:
        raise LLMError(f"Groq HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Groq malformed response: {data!r}") from exc


def extract_json(text: str) -> dict:
    """Дістає перший JSON-об'єкт з тексту (LLM часто додає ```json-обгортку)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError(f"No JSON object in LLM output: {text[:300]}")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {cleaned[start : end + 1][:300]}") from exc


async def llm_json(
    settings: Settings,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> dict:
    """Викликає LLM і повертає розпарсений JSON-об'єкт."""
    return extract_json(await llm_text(settings, system, user, temperature, max_tokens))
