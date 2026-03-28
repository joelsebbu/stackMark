"""StackMark — YouTube Ingestion Pipeline

Orchestrates the full flow: URL parsing → fetch metadata via yt-dlp →
enrich with Gemini (direct YouTube URL analysis) → generate embedding →
store in PostgreSQL.

Usage:
    uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
    uv run -m youtube_pipeline "https://youtu.be/VIDEO_ID"
    uv run -m youtube_pipeline "https://youtube.com/shorts/VIDEO_ID"
"""

import os
import sys
from typing import Any

from .constants import YT_PIPELINE_MODEL
from .fetcher import extract_video_id, fetch_metadata
from .llm import call_llm, generate_embedding
from .messages import build_video_url_messages, build_metadata_only_messages
from .prompts import ENRICHMENT_PROMPT

from db.operations import insert_embedding
from errors import PipelineError


def _format_metadata(metadata: dict[str, Any]) -> str:
    """Format video metadata as text for the LLM."""
    parts = [
        f'Title: "{metadata["title"]}"',
        f'Channel: "{metadata["channel"]}"',
    ]
    if metadata.get("description"):
        desc = metadata["description"][:500]
        parts.append(f'Description: "{desc}"')
    if metadata.get("tags"):
        parts.append(f'Tags: {", ".join(metadata["tags"][:20])}')
    if metadata.get("categories"):
        parts.append(f'Categories: {", ".join(metadata["categories"])}')
    return "\n".join(parts)


def enrich_video(metadata: dict[str, Any], url: str) -> dict[str, Any]:
    """Analyze video content using Gemini via OpenRouter.

    Passes the YouTube URL directly to Gemini for video analysis.
    Falls back to metadata-only if URL analysis fails.
    """
    metadata_text = _format_metadata(metadata)
    print(f"\n   Analyzing video content...")
    print(f"   Model: {YT_PIPELINE_MODEL}")

    # Try direct YouTube URL analysis via Gemini
    try:
        print("   Sending YouTube URL to Gemini for direct analysis...")
        messages = build_video_url_messages(metadata_text, url, ENRICHMENT_PROMPT)
        return call_llm(messages)
    except Exception as e:
        print(f"   URL video analysis failed: {e}")
        print("   Falling back to metadata-only analysis...")

    # Fallback: metadata only
    messages = build_metadata_only_messages(metadata_text, ENRICHMENT_PROMPT)
    return call_llm(messages)


def run_pipeline(url: str) -> dict[str, Any]:
    """Run the full YouTube ingestion pipeline on a URL."""
    if not os.getenv("OPENROUTER_API_KEY"):
        raise PipelineError("OPENROUTER_API_KEY not set in .env")

    # ── Step 1: Parse URL ──
    print("=" * 60)
    print("StackMark YouTube Ingestion Pipeline")
    print("=" * 60)

    video_id = extract_video_id(url)
    print(f"\n   URL: {url}")
    print(f"   Video ID: {video_id}")

    # ── Step 2: Fetch video metadata ──
    print(f"\n   Fetching video metadata...")
    metadata = fetch_metadata(url)
    print(f"   Title:    {metadata['title']}")
    print(f"   Channel:  {metadata['channel']}")
    print(f"   Duration: {metadata['duration']}s")
    print(f"   Views:    {metadata['view_count']}")
    print(f"   Likes:    {metadata['like_count']}")
    if metadata["description"]:
        print(f"   Description: {metadata['description'][:120]}...")

    # ── Step 3: Enrich with Gemini (direct URL analysis) ──
    description = enrich_video(metadata, url)

    if description.get("parse_error"):
        print(f"\n{'=' * 60}")
        print("Could not parse LLM response as JSON. Raw response:")
        print(description.get("raw_response", "No response"))
        print(f"{'=' * 60}")
        return description

    # ── Step 4: Generate embedding ──
    print("\n   Generating embedding vector...")
    embedding_text = (
        f"{description.get('description', '')} "
        f"{' '.join(description.get('tags', []))} "
        f"{' '.join(description.get('entities', []))}"
    )
    try:
        embedding = generate_embedding(embedding_text)
        print(f"   Generated embedding: {len(embedding)} dimensions")
    except Exception as e:
        raise PipelineError(f"Error generating embedding: {e}") from e

    # ── Step 5: Store in database ──
    print("\n   Storing to database...")
    record = insert_embedding(
        source="youtube",
        url=url,
        embedding=embedding,
    )
    print(f"   Saved with UUID: {record.uuid}")

    # ── Output ──
    print(f"\n{'=' * 60}")
    print("PIPELINE OUTPUT")
    print(f"{'=' * 60}")

    print(f"\n   Description:")
    print(f"   {description.get('description', 'N/A')}")

    print(f"\n   Tags:")
    tags = description.get("tags", [])
    print(f"   {', '.join(tags)}")

    print(f"\n   Content Type: {description.get('content_type', 'N/A')}")
    mood = description.get("mood", [])
    print(f"   Mood: {', '.join(mood) if mood else 'N/A'}")
    print(f"   Has Media: {description.get('has_media', 'N/A')} ({description.get('media_type', 'N/A')})")
    print(f"   Media Confidence: {description.get('media_confidence', 'N/A')}")

    print(f"\n   Entities:")
    entities = description.get("entities", [])
    print(f"   {', '.join(entities) if entities else 'None'}")

    print(f"\n   Embedding: {len(embedding)} dimensions")

    print(f"\n{'=' * 60}")

    return {**description, "embedding": embedding}


def main() -> None:
    """CLI entry point for the pipeline."""
    if len(sys.argv) < 2:
        print("Usage: uv run -m youtube_pipeline <youtube-url>")
        print('Example: uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"')
        sys.exit(1)

    run_pipeline(sys.argv[1])


if __name__ == "__main__":
    main()
