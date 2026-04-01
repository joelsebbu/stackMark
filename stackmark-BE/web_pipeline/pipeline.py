"""StackMark — Web Ingestion Pipeline

Orchestrates the full flow: fetch page via headless browser →
extract metadata + text → enrich with Gemini → generate embedding →
store in PostgreSQL.

Usage:
    uv run -m web_pipeline "https://example.com/article"
"""

import os
import sys
from typing import Any

from .constants import WEB_PIPELINE_MODEL
from .fetcher import fetch_page, extract_metadata
from .llm import call_llm, generate_embedding
from .messages import build_web_page_messages
from .prompts import ENRICHMENT_PROMPT

from db.operations import insert_embedding
from errors import PipelineError


def _format_metadata(metadata: dict[str, Any]) -> str:
    """Format extracted page metadata as text for the LLM."""
    parts = []

    if metadata.get("title"):
        parts.append(f'Title: "{metadata["title"]}"')
    if metadata.get("og_site_name"):
        parts.append(f'Site: "{metadata["og_site_name"]}"')
    if metadata.get("meta_description"):
        parts.append(f'Meta Description: "{metadata["meta_description"]}"')
    if metadata.get("og_description") and metadata["og_description"] != metadata.get("meta_description"):
        parts.append(f'OG Description: "{metadata["og_description"]}"')
    if metadata.get("og_type"):
        parts.append(f'OG Type: {metadata["og_type"]}')
    if metadata.get("og_image"):
        parts.append(f'OG Image: {metadata["og_image"]}')

    if metadata.get("main_text"):
        parts.append(f'\n--- Page Content ---\n{metadata["main_text"]}')

    return "\n".join(parts)


def enrich_page(metadata: dict[str, Any]) -> dict[str, Any]:
    """Analyze web page content using Gemini via OpenRouter."""
    metadata_text = _format_metadata(metadata)
    print(f"\n   Analyzing page content...")
    print(f"   Model: {WEB_PIPELINE_MODEL}")

    messages = build_web_page_messages(metadata_text, ENRICHMENT_PROMPT)
    return call_llm(messages)


def run_pipeline(url: str) -> dict[str, Any]:
    """Run the full web ingestion pipeline on a URL."""
    if not os.getenv("OPENROUTER_API_KEY"):
        raise PipelineError("OPENROUTER_API_KEY not set in .env")

    # ── Step 1: Fetch page ──
    print("=" * 60)
    print("StackMark Web Ingestion Pipeline")
    print("=" * 60)

    print(f"\n   URL: {url}")
    print(f"   Fetching page...")
    html = fetch_page(url)
    print(f"   Fetched {len(html)} chars of HTML")

    # ── Step 2: Extract metadata ──
    print(f"\n   Extracting metadata and content...")
    metadata = extract_metadata(html)
    print(f"   Title:    {metadata['title'] or '(none)'}")
    print(f"   Site:     {metadata['og_site_name'] or '(none)'}")
    print(f"   Content:  {len(metadata['main_text'])} chars of text")

    # ── Step 3: Enrich with Gemini ──
    description = enrich_page(metadata)

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
        source="web",
        url=url,
        embedding=embedding,
        heading=description.get("heading"),
        brief=description.get("brief"),
    )
    print(f"   Saved with UUID: {record.uuid}")

    # ── Output ──
    print(f"\n{'=' * 60}")
    print("PIPELINE OUTPUT")
    print(f"{'=' * 60}")

    print(f"\n   Description:")
    print(f"   {description.get('description', 'N/A')}")

    print(f"\n   Heading:")
    print(f"   {description.get('heading', 'N/A')}")

    print(f"\n   Brief:")
    print(f"   {description.get('brief', 'N/A')}")

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
        print("Usage: uv run -m web_pipeline <url>")
        print('Example: uv run -m web_pipeline "https://example.com/article"')
        sys.exit(1)

    run_pipeline(sys.argv[1])


if __name__ == "__main__":
    main()
