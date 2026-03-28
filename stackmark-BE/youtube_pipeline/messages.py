"""LLM message building — constructs multimodal payloads for OpenRouter."""

from typing import Any


def build_video_url_messages(
    metadata_text: str, youtube_url: str, prompt: str
) -> list[dict[str, Any]]:
    """Build multimodal messages with a YouTube URL for Gemini to analyze directly."""
    content = [
        {"type": "text", "text": "[VIDEO]"},
        {
            "type": "video_url",
            "video_url": {"url": youtube_url},
        },
        {
            "type": "text",
            "text": f"{metadata_text}\n\n{prompt}",
        },
    ]
    return [{"role": "user", "content": content}]


def build_metadata_only_messages(
    metadata_text: str, prompt: str
) -> list[dict[str, Any]]:
    """Build text-only messages as fallback when video URL analysis fails."""
    content = [
        {
            "type": "text",
            "text": f"{metadata_text}\n\n{prompt}",
        },
    ]
    return [{"role": "user", "content": content}]
