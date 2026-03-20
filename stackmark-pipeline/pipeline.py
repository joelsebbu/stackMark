"""
StackMark — Barebone Ingestion Pipeline Prototype

Takes a tweet URL → uses xAI Grok's x_search to fetch content →
generates a search-optimized description via Grok.
Uses cheap model first, escalates to expensive model if media is detected
and model reports low confidence. Use --rich flag to force expensive model.

Usage:
    uv run pipeline.py "https://x.com/someone/status/123456"
    uv run pipeline.py "https://x.com/someone/status/123456" --rich
"""

import sys
import os
import re
import json

from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user, system
from xai_sdk.tools import x_search

# Load .env file automatically
load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

MODEL_CHEAP = "grok-4-1-fast-non-reasoning"
MODEL_RICH = "grok-4.20-beta-latest-non-reasoning"


# ─── Step 1: Source Classification ────────────────────────────────────────────

def classify_url(url: str) -> dict:
    """Classify the URL and extract useful identifiers."""

    x_pattern = r"(?:x\.com|twitter\.com)/(\w+)/status/(\d+)"
    match = re.search(x_pattern, url)
    if match:
        return {
            "source": "x",
            "username": match.group(1),
            "tweet_id": match.group(2),
            "url": url,
        }

    return {"source": "unknown", "url": url}


# ─── Step 2+3: Fetch & Describe ──────────────────────────────────────────────

ENRICHMENT_PROMPT = """\
You are a bookmark indexer for a personal bookmark manager called StackMark.

Find the tweet at the URL below using x_search. Analyze ALL content including \
any images, videos, and text overlays in the media. Then produce a JSON \
description that will be converted into a vector embedding for semantic search.

Tweet URL: {url}

Return a JSON object with these fields:

{{
  "description": "A rich 2-3 sentence description of what this content \
actually shows/says. If it's a video, describe what happens in it. If there's \
text overlay or captions in images/video, include that. Be SPECIFIC about \
the actual visual content, not just metadata.",

  "topics": ["list", "of", "relevant", "searchable", "keywords"],

  "content_type": "one of: meme, tutorial, article, news, thread, tool, \
library, announcement, opinion, discussion, resource, showcase, other",

  "mood": "one of: funny, informative, inspiring, technical, emotional, \
controversial, casual, serious",

  "entities": ["specific names of people, characters, brands, tools, \
technologies mentioned or shown"],

  "has_media": true or false,

  "media_type": "none, image, video, or gif",

  "confidence": "high or low — say low if you cannot see/analyze media \
content (images, videos) that the tweet contains, or if your description \
is mostly based on metadata (handles, replies, engagement) rather than \
the actual content of the tweet"
}}

IMPORTANT RULES:
- ACTUALLY WATCH any video and LOOK AT any images. Describe what you see.
- If there's text overlay on a video/image, include it in the description.
- Be SPECIFIC — "Po from Kung Fu Panda shuffling scrolls" not "an animated character"
- Include the DOMAIN: humor, tech, sports, etc.
- has_media must be true if the tweet contains any image, video, or gif.
- Return ONLY valid JSON, no markdown fences, no extra text.
"""


def fetch_and_describe(client: Client, url_info: dict, use_rich_model: bool = False) -> dict:
    """Fetch tweet content AND generate description in one Grok call."""

    model = MODEL_RICH if use_rich_model else MODEL_CHEAP

    if use_rich_model:
        print(f"\n🔬 Re-analyzing with rich model (media detected)...")
    else:
        print(f"\n📡 Fetching tweet and generating description...")
    print(f"   Model: {model}")
    print(f"   User: @{url_info['username']}")
    print(f"   Tweet ID: {url_info['tweet_id']}")

    if use_rich_model:
        tools = [
            x_search(
                enable_image_understanding=True,
                enable_video_understanding=True,
            )
        ]
    else:
        tools = [x_search()]

    chat = client.chat.create(
        model=model,
        tools=tools,
    )

    chat.append(
        user(ENRICHMENT_PROMPT.format(url=url_info["url"]))
    )

    response = chat.sample()
    result_text = response.content.strip()

    # Clean up potential markdown fences
    result_text = result_text.strip("`")
    if result_text.startswith("json"):
        result_text = result_text[4:]
    result_text = result_text.strip()

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "parse_error": True}


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(url: str, force_rich: bool = False):
    """Run the full ingestion pipeline on a URL."""

    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("❌ Error: Set your XAI_API_KEY environment variable.")
        print("   Add your key to the .env file.")
        sys.exit(1)

    client = Client(api_key=api_key)

    # ── Step 1: Classify ──
    print("=" * 60)
    print("🔖 StackMark Ingestion Pipeline (Prototype)")
    print("=" * 60)

    url_info = classify_url(url)
    print(f"\n📋 Classification:")
    print(f"   Source: {url_info['source']}")
    print(f"   URL: {url_info['url']}")

    if url_info["source"] == "unknown":
        print("\n❌ Only X/Twitter URLs are supported in this prototype.")
        sys.exit(1)

    # ── Step 2+3: Fetch & Describe ──
    if force_rich:
        print(f"\n🔬 Forced rich model via --rich flag.")
        description = fetch_and_describe(client, url_info, use_rich_model=True)
    else:
        description = fetch_and_describe(client, url_info, use_rich_model=False)

        if not description.get("parse_error"):
            has_media = description.get("has_media", False)
            confidence = description.get("confidence", "high").lower()

            if confidence == "low" and has_media:
                print(f"\n⚠️  Model reported low confidence and tweet has media.")
                print(f"   Escalating to rich model for better analysis...")
                description = fetch_and_describe(client, url_info, use_rich_model=True)
            elif confidence == "low":
                print(f"\n📝 Low confidence but no media — keeping as-is.")
            else:
                print(f"\n✅ High confidence from cheap model.")

    # ── Output ──
    print(f"\n{'=' * 60}")
    print("✅ PIPELINE OUTPUT")
    print(f"{'=' * 60}")

    if description.get("parse_error"):
        print("\n⚠️  Couldn't parse as JSON. Raw response:")
        print(description.get("raw_response", "No response"))
    else:
        print(f"\n📝 Description:")
        print(f"   {description.get('description', 'N/A')}")

        print(f"\n🏷️  Topics:")
        topics = description.get("topics", [])
        print(f"   {', '.join(topics)}")

        print(f"\n📦 Content Type: {description.get('content_type', 'N/A')}")
        print(f"🎭 Mood: {description.get('mood', 'N/A')}")
        print(f"🖼️  Has Media: {description.get('has_media', 'N/A')} ({description.get('media_type', 'N/A')})")
        print(f"🎯 Confidence: {description.get('confidence', 'N/A')}")

        print(f"\n👤 Entities:")
        entities = description.get("entities", [])
        print(f"   {', '.join(entities) if entities else 'None'}")

    print(f"\n{'=' * 60}")
    print("💡 This description would be embedded and stored in the vector DB.")
    print("   A search for any of the topics above would surface this bookmark.")
    print(f"{'=' * 60}")

    return description


def main():
    args = sys.argv[1:]

    force_rich = "--rich" in args
    if force_rich:
        args.remove("--rich")

    if len(args) < 1:
        print("Usage: uv run pipeline.py <tweet-url> [--rich]")
        print('Example: uv run pipeline.py "https://x.com/elonmusk/status/123456"')
        print('         uv run pipeline.py "https://x.com/..." --rich')
        sys.exit(1)

    url = args[0]
    run_pipeline(url, force_rich=force_rich)


if __name__ == "__main__":
    main()