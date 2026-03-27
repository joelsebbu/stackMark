"""OpenRouter client, LLM calls, and embedding generation."""

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .constants import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    IG_PIPELINE_MODEL,
    OPENROUTER_BASE_URL,
)

load_dotenv()

_openrouter_client: OpenAI | None = None
_openrouter_api_key = os.getenv("OPENROUTER_API_KEY")


def get_openrouter_client() -> OpenAI:
    """Get or initialize the OpenRouter client."""
    global _openrouter_client

    if _openrouter_client is None:
        if not _openrouter_api_key:
            print("Error: OPENROUTER_API_KEY not set in environment.")
            sys.exit(1)
        _openrouter_client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=_openrouter_api_key)

    return _openrouter_client


def _clean_response(text: str) -> str:
    """Remove markdown fences and JSON prefixes from LLM response."""
    cleaned = text.strip().strip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    return cleaned.strip()


def call_llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Send messages to Gemini via OpenRouter and parse the JSON response."""
    client = get_openrouter_client()
    response = client.chat.completions.create(
        model=IG_PIPELINE_MODEL, messages=messages
    )
    result_text = _clean_response(response.choices[0].message.content or "")

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "parse_error": True}


def generate_embedding(text: str) -> list[float]:
    """Generate vector embedding via OpenRouter."""
    client = get_openrouter_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding
