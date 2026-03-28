"""LLM message building — constructs text payloads for OpenRouter."""

from typing import Any


def build_web_page_messages(
    metadata_text: str, prompt: str
) -> list[dict[str, Any]]:
    """Build text-only messages with extracted web page content."""
    content = [
        {
            "type": "text",
            "text": f"{metadata_text}\n\n{prompt}",
        },
    ]
    return [{"role": "user", "content": content}]
