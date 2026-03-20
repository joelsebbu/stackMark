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
You are a bookmark indexer for StackMark, a personal bookmark manager.

Find the tweet at the URL below using x_search. Analyze ALL content — text, \
images, videos, text overlays, captions baked into media. Then return a JSON \
object whose description field will be converted into a vector embedding for \
cosine similarity search.

Tweet URL: {url}

Return ONLY a valid JSON object (no markdown fences, no extra text) with \
these fields:

{{
  "description": "A dense, keyword-rich block of text that captures \
everything someone might search to find this content later. Front-load \
named entities and concrete nouns. Include synonyms and related terms \
(e.g. 'Kung Fu Panda Po DreamWorks animated panda character'). Cover: \
what it shows, who/what is in it, what domain it belongs to, what the \
tone is, and what words a person would type to relocate this bookmark. \
No filler, no narrative prose, no editorial commentary. Just dense, \
searchable text.",

  "tags": ["5-10 short lowercase tags for exact-match filtering. \
Cover: primary topic, people/entities, content type (meme, tutorial, \
thread, etc.), mood (funny, technical, etc.), and domain (tech, sports, \
gaming, etc.). Prefer canonical short terms — 'f1' not \
'formula-one-racing', 'python' not 'python-programming-language'. \
Max 3 words per tag."],

  "content_type": "one of: meme, tutorial, article, news, thread, \
tool, library, announcement, opinion, discussion, resource, showcase, \
other",

  "mood": ["one or two from: funny, informative, inspiring, technical, \
emotional, controversial, casual, serious"],

  "entities": ["proper nouns only — people, characters, brands, tools, \
technologies, places mentioned or shown"],

  "has_media": true,

  "media_type": "none | image | video | gif",

  "media_confidence": "high or low (see rules below)"
}}

RULES:

1. MEDIA ANALYSIS: ACTUALLY WATCH any video and LOOK AT any images. \
If there's text overlay or captions baked into video frames or images, \
transcribe them into the description.

2. SPECIFICITY: Use exact names. "Po from Kung Fu Panda" not "animated \
character". "FastAPI" not "a web framework". "Charles Leclerc" not \
"an F1 driver".

3. DESCRIPTION DENSITY: Write for a search engine, not a person. Pack \
in every relevant term, synonym, and related concept. A good test: if \
someone searches any reasonable phrase to find this content, at least \
one phrase in the description should be a near-match.

4. MEDIA CONFIDENCE:
   - "high" = you viewed and can describe the actual visual content
   - "low" = the tweet has media you could not analyze, OR your \
description is mostly based on metadata (handle name, reply context, \
engagement) rather than actual content
   - Text-only tweets with no media = always "high"

5. UNAVAILABLE CONTENT: If the tweet is deleted, private, or \
inaccessible, return:
   {{"description": "", "tags": [], "content_type": "other", \
"mood": [], "entities": [], "has_media": false, "media_type": "none", \
"media_confidence": "low"}}

6. has_media must be true if the tweet contains ANY image, video, or gif.

7. tags: lowercase, 5-10 items, no duplicates, max 3 words each.

8. Return ONLY the JSON object.
"""


def fetch_and_describe(
    client: Client, url_info: dict, use_rich_model: bool = False
) -> dict:
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

    chat.append(user(ENRICHMENT_PROMPT.format(url=url_info["url"])))

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
            confidence = description.get("media_confidence", "high").lower()

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

        print(f"\n🏷️  Tags:")
        tags = description.get("tags", [])
        print(f"   {', '.join(tags)}")

        print(f"\n📦 Content Type: {description.get('content_type', 'N/A')}")
        mood = description.get("mood", [])
        print(f"🎭 Mood: {', '.join(mood) if mood else 'N/A'}")
        print(
            f"🖼️  Has Media: {description.get('has_media', 'N/A')} ({description.get('media_type', 'N/A')})"
        )
        print(f"🎯 Media Confidence: {description.get('media_confidence', 'N/A')}")

        print(f"\n👤 Entities:")
        entities = description.get("entities", [])
        print(f"   {', '.join(entities) if entities else 'None'}")

    print(f"\n{'=' * 60}")
    print("💡 This description would be embedded and stored in the vector DB.")
    print("   Tags would be stored for exact-match filtering.")
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
