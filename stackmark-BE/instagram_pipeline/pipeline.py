"""StackMark — Instagram Ingestion Pipeline

Orchestrates the full flow: URL parsing → fetch via instaloader →
enrich with Gemini → generate embedding → store in PostgreSQL.

Usage:
    uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
    uv run -m instagram_pipeline "https://www.instagram.com/user/reel/SHORTCODE/"
"""

import os
import sys
import tempfile
from typing import Any

import instaloader

from .constants import IG_PIPELINE_MODEL
from .fetcher import extract_shortcode, fetch_post, download_media
from .llm import call_llm, generate_embedding
from .media import find_files, extract_frames
from .messages import build_photo_messages, build_video_messages, build_frames_messages
from .prompts import ENRICHMENT_PROMPT

from db.operations import insert_embedding
from errors import PipelineError


def enrich_post(post: instaloader.Post, download_dir: str) -> dict[str, Any]:
    """Analyze post content using Gemini via OpenRouter.

    For photos/carousels: base64-encodes images and sends them.
    For videos: tries base64 video first, falls back to ffmpeg frame extraction.
    """
    caption = post.caption or ""
    print(f"\n   Analyzing post content...")
    print(f"   Model: {IG_PIPELINE_MODEL}")
    print(f"   Owner: @{post.owner_username}")
    print(f"   Type:  {post.typename}")

    images = find_files(download_dir, (".jpg", ".jpeg", ".png", ".webp"))
    videos = find_files(download_dir, (".mp4",))

    if post.is_video and videos:
        video_path = videos[0]
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"   Video: {size_mb:.1f} MB")

        # Try base64 video first
        try:
            print("   Sending full video as base64...")
            messages = build_video_messages(caption, video_path, ENRICHMENT_PROMPT)
            return call_llm(messages)
        except Exception as e:
            print(f"   Base64 video failed: {e}")
            print("   Falling back to frame extraction...")

        # Fallback: extract frames with ffmpeg
        frames_dir = tempfile.mkdtemp(prefix="ig_frames_")
        frames = extract_frames(video_path, frames_dir)
        if not frames:
            print("   No frames extracted — sending caption only.")
            messages = build_photo_messages(caption, [], ENRICHMENT_PROMPT)
            return call_llm(messages)

        messages = build_frames_messages(caption, frames, ENRICHMENT_PROMPT)
        return call_llm(messages)

    # Photo or carousel — send all images
    if images:
        print(f"   Images: {len(images)}")

    messages = build_photo_messages(caption, images, ENRICHMENT_PROMPT)
    return call_llm(messages)


def run_pipeline(url: str) -> dict[str, Any]:
    """Run the full Instagram ingestion pipeline on a URL."""
    if not os.getenv("OPENROUTER_API_KEY"):
        raise PipelineError("OPENROUTER_API_KEY not set in .env")

    # ── Step 1: Parse URL ──
    print("=" * 60)
    print("StackMark Instagram Ingestion Pipeline")
    print("=" * 60)

    shortcode = extract_shortcode(url)
    print(f"\n   URL: {url}")
    print(f"   Shortcode: {shortcode}")

    # ── Step 2: Fetch post metadata ──
    print(f"\n   Fetching post metadata...")
    post = fetch_post(shortcode)
    print(f"   Owner:    @{post.owner_username}")
    print(f"   Type:     {post.typename}")
    print(f"   Likes:    {post.likes}")
    print(f"   Comments: {post.comments}")
    print(f"   Is video: {post.is_video}")
    if post.caption:
        print(f"   Caption:  {post.caption[:120]}...")

    # ── Step 3: Download media ──
    print(f"\n   Downloading media...")
    download_dir = download_media(post, shortcode)
    print(f"   Downloaded to: {download_dir}")

    # ── Step 4: Enrich with Gemini ──
    description = enrich_post(post, download_dir)

    if description.get("parse_error"):
        print(f"\n{'=' * 60}")
        print("Could not parse LLM response as JSON. Raw response:")
        print(description.get("raw_response", "No response"))
        print(f"{'=' * 60}")
        return description

    # ── Step 5: Generate embedding ──
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

    # ── Step 6: Store in database ──
    print("\n   Storing to database...")
    record = insert_embedding(
        source="instagram",
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
        print("Usage: uv run -m instagram_pipeline <instagram-url>")
        print('Example: uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"')
        sys.exit(1)

    run_pipeline(sys.argv[1])


if __name__ == "__main__":
    main()
