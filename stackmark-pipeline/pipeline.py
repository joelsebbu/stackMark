"""StackMark — Barebone Ingestion Pipeline Prototype

Takes a tweet URL → fetches content via Twitter API v2 →
sends text + media to Grok vision model for analysis →
generates a search-optimized description.
Uses cheap model first, escalates to expensive model if media is detected
and model reports low confidence. Use --rich flag to force expensive model.

Usage:
    uv run pipeline.py "https://x.com/someone/status/123456"
    uv run pipeline.py "https://x.com/someone/status/123456" --rich
"""

# Standard library imports
import json
import os
import re
import sys
from typing import Any

# Third-party imports
import requests
from dotenv import load_dotenv
from openai import OpenAI


# Local imports
from constants import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MODEL_CHEAP,
    MODEL_RICH,
    OPENROUTER_BASE_URL,
    REQUEST_TIMEOUT,
    X_API_BASE_URL,
    XAI_API_BASE_URL,
    X_URL_PATTERN,
)
from prompts import ENRICHMENT_PROMPT
from utils import (
    as_list,
    clean_response_json_text,
    dedupe,
    pick_media_type,
)

# Load environment variables from .env file
load_dotenv()

# ─── Global State ───────────────────────────────────────────────────────────

# Clients (initialized lazily)
_embedding_client: OpenAI | None = None
_xai_client: OpenAI | None = None

# API keys
x_api_key = os.getenv("XAI_API_KEY")
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
x_api_bearer_token = os.getenv("X_API_BEARER_TOKEN")

def _get_embedding_client() -> OpenAI:
    """Get or initialize the OpenRouter embedding client."""
    global _embedding_client

    if _embedding_client is None:
        if not openrouter_api_key:
            print("❌ Error: OPENROUTER_API_KEY not set in environment.")
            sys.exit(1)
        _embedding_client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=openrouter_api_key)

    return _embedding_client


def _get_xai_client() -> OpenAI:
    """Get or initialize the xAI client (OpenAI-compatible)."""
    global _xai_client

    if _xai_client is None:
        if not x_api_key:
            print("❌ Error: XAI_API_KEY not set in environment.")
            sys.exit(1)
        _xai_client = OpenAI(base_url=XAI_API_BASE_URL, api_key=x_api_key)

    return _xai_client


# ─── Twitter API ─────────────────────────────────────────────────────────────


def fetch_tweet(tweet_id: str) -> dict[str, Any]:
    """Fetch tweet data from Twitter API v2 including media and author info.

    Args:
        tweet_id: The numeric tweet ID.

    Returns:
        Raw JSON response from the Twitter API v2.

    Raises:
        requests.HTTPError: If the API call fails.
    """
    endpoint = f"{X_API_BASE_URL}/tweets/{tweet_id}"
    params = {
        "expansions": "attachments.media_keys,author_id",
        "media.fields": "type,url,preview_image_url,width,height,duration_ms,variants,alt_text",
        "tweet.fields": "text,created_at,attachments,author_id",
        "user.fields": "name,username",
    }
    headers = {"Authorization": f"Bearer {x_api_bearer_token}"}
    resp = requests.get(endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _best_video_url(variants: list[dict]) -> str | None:
    """Pick the highest-bitrate MP4 variant."""
    mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
    if mp4s:
        return max(mp4s, key=lambda v: v.get("bitrate", 0))["url"]
    return variants[0]["url"] if variants else None


def extract_media(tweet_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract media items from tweet API response.

    Each media item has:
      type        - "photo" | "video" | "animated_gif"
      url         - image URL (preview frame for video/gif)
      video_url   - direct MP4 URL if available
      is_preview  - True when url is a preview frame
    """
    media_items = []

    for media in tweet_data.get("includes", {}).get("media", []):
        mtype = media["type"]
        if mtype == "photo":
            media_items.append({
                "type": "photo",
                "url": media["url"],
                "video_url": None,
                "is_preview": False,
            })
        elif mtype == "animated_gif":
            media_items.append({
                "type": "animated_gif",
                "url": media.get("url") or media.get("preview_image_url"),
                "video_url": _best_video_url(media.get("variants", [])),
                "is_preview": not media.get("url"),
            })
        elif mtype == "video":
            media_items.append({
                "type": "video",
                "url": media.get("preview_image_url"),
                "video_url": _best_video_url(media.get("variants", [])),
                "is_preview": True,
            })

    return media_items


def build_vision_messages(
    tweet_text: str, media_items: list[dict], prompt: str
) -> list[dict[str, Any]]:
    """Build multimodal messages with images for vision model.

    Constructs an OpenAI-compatible message list with image_url content
    blocks so the model can actually see the media.
    """
    content: list[dict[str, Any]] = []

    for item in media_items:
        if not item.get("url"):
            continue
        label = item["type"].upper()
        if item["is_preview"]:
            label += " (preview frame — original is a video/GIF)"
        content.append({"type": "text", "text": f"[{label}]"})
        content.append({"type": "image_url", "image_url": {"url": item["url"]}})

    content.append({"type": "text", "text": f'Tweet text: "{tweet_text}"\n\n{prompt}'})
    return [{"role": "user", "content": content}]


# ─── Source Classification ────────────────────────────────────────────────────


def classify_url(url: str) -> dict[str, Any]:
    """Classify the URL and extract useful identifiers.

    Currently supports X/Twitter URLs. Extracts username and tweet ID
    from status URLs for further processing.

    Args:
        url: The URL to classify.

    Returns:
        Dictionary with keys:
        - source: 'x' or 'unknown'
        - username: Extracted username (if X status URL)
        - tweet_id: Extracted tweet ID (if X status URL)
        - url: Original URL
    """
    match = re.search(X_URL_PATTERN, url)
    if match:
        return {
            "source": "x",
            "username": match.group(1) or "",
            "tweet_id": match.group(2),
            "url": url,
        }

    return {"source": "unknown", "url": url}


# ─── Embedding Generation ─────────────────────────────────────────────────────


def generate_embedding(text: str) -> list[float]:
    """Generate vector embedding via OpenRouter.

    Uses Qwen embedding model to create a 1024-dimensional vector
    suitable for cosine similarity search.

    Args:
        text: The text to embed (typically description + tags + entities).

    Returns:
        List of float values representing the embedding vector.
    """
    client = _get_embedding_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


# ─── Quote Tweet Detection ────────────────────────────────────────────────────


def parse_quoted_tweet_from_x_api_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse X API v2 tweet payload and extract quoted tweet metadata.

    Analyzes the 'referenced_tweets' field to identify quote tweet
    relationships, then extracts the quoted tweet's URL and author
    information from the 'includes' section.

    Args:
        payload: Raw JSON response from X API v2 tweets endpoint.

    Returns:
        Dictionary with keys:
        - is_quote_tweet: Boolean indicating if this is a quote tweet
        - quoted_tweet_url: Full URL to quoted tweet (if available)
        - quoted_tweet_id: Numeric ID of quoted tweet
        - quoted_username: Username of quoted tweet author (if available)
        - detection_source: Always 'x_api' for this function
    """
    data = payload.get("data", {}) or {}
    referenced = data.get("referenced_tweets", []) or []

    # Find the quoted tweet reference
    quoted_ref = None
    for ref in referenced:
        if ref.get("type") == "quoted" and ref.get("id"):
            quoted_ref = ref
            break

    if not quoted_ref:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "detection_source": "x_api",
        }

    quoted_tweet_id = str(quoted_ref.get("id", "")).strip()
    includes = payload.get("includes", {}) or {}
    included_tweets = includes.get("tweets", []) or []
    included_users = includes.get("users", []) or []

    # Build user lookup by ID
    users_by_id = {
        str(user.get("id", "")).strip(): str(user.get("username", "")).strip()
        for user in included_users
        if user.get("id") and user.get("username")
    }

    # Find the quoted tweet in includes to get author_id
    quoted_tweet_obj = None
    for tweet in included_tweets:
        if str(tweet.get("id", "")).strip() == quoted_tweet_id:
            quoted_tweet_obj = tweet
            break

    # Extract username from author_id
    quoted_username = ""
    if quoted_tweet_obj:
        author_id = str(quoted_tweet_obj.get("author_id", "")).strip()
        quoted_username = users_by_id.get(author_id, "")

    # Build canonical URL
    if quoted_username:
        quoted_tweet_url = f"https://x.com/{quoted_username}/status/{quoted_tweet_id}"
    else:
        quoted_tweet_url = f"https://x.com/i/web/status/{quoted_tweet_id}"

    return {
        "is_quote_tweet": True,
        "quoted_tweet_url": quoted_tweet_url,
        "quoted_tweet_id": quoted_tweet_id,
        "quoted_username": quoted_username,
        "detection_source": "x_api",
    }

def detect_quoted_tweet_with_x_api(url_info: dict[str, Any]) -> dict[str, Any]:
    """Primary quote detection using deterministic X API v2 metadata.

    Calls the X API v2 to get tweet metadata including referenced_tweets.
    This is the preferred method as it's deterministic and doesn't rely on LLM.

    Args:
        url_info: URL classification dict with 'tweet_id' key.

    Returns:
        Dictionary with quote tweet metadata, or error information if the
        API call fails or X_API_BEARER_TOKEN is not configured.
    """
    if not x_api_bearer_token:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "detection_source": "x_api",
            "unavailable": True,
            "error": "X_API_BEARER_TOKEN not configured",
        }

    tweet_id = url_info.get("tweet_id", "")
    endpoint = f"{X_API_BASE_URL}/tweets/{tweet_id}"
    params = {
        "tweet.fields": "referenced_tweets,author_id",
        "expansions": "referenced_tweets.id,referenced_tweets.id.author_id",
        "user.fields": "username",
    }
    headers = {"Authorization": f"Bearer {x_api_bearer_token}"}

    try:
        response = requests.get(
            endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as exc:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "detection_source": "x_api",
            "error": f"X API request failed: {exc}",
        }

    if response.status_code != 200:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "detection_source": "x_api",
            "error": f"X API returned HTTP {response.status_code}",
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "detection_source": "x_api",
            "error": "X API returned non-JSON response",
        }

    return parse_quoted_tweet_from_x_api_payload(payload)


def detect_quoted_tweet(url_info: dict[str, Any]) -> dict[str, Any]:
    """Detect quoted tweet using X API v2 metadata.

    Args:
        url_info: URL classification dict.

    Returns:
        Dictionary with quote tweet metadata.
    """
    print("\n🔎 Detecting whether this tweet quotes another tweet...")

    api_result = detect_quoted_tweet_with_x_api(url_info)
    if api_result.get("error"):
        print(f"   X API detection error: {api_result.get('error')}")
    else:
        print("   Detection source: X API v2")
    return api_result


# ─── Content Enrichment ───────────────────────────────────────────────────────


def merge_bookmark_records(
    main: dict[str, Any], quoted: dict[str, Any]
) -> dict[str, Any]:
    """Merge main tweet enrichment and quoted tweet enrichment into one record.

    Combines descriptions, tags, entities, and metadata from both tweets,
    with the main tweet taking precedence for content_type. Media detection
    is unified (if either has media, result has media).

    Args:
        main: Enrichment dict from the main tweet.
        quoted: Enrichment dict from the quoted tweet.

    Returns:
        Merged enrichment dict suitable for final bookmark storage.
    """
    # Merge descriptions
    main_description = (main.get("description") or "").strip()
    quoted_description = (quoted.get("description") or "").strip()

    if main_description and quoted_description:
        merged_description = (
            f"{main_description} quoted tweet context {quoted_description}"
        )
    else:
        merged_description = main_description or quoted_description

    # Merge tags (dedupe and limit to 10)
    main_tags = [tag.lower() for tag in as_list(main.get("tags"))]
    quoted_tags = [tag.lower() for tag in as_list(quoted.get("tags"))]
    merged_tags = dedupe(main_tags + quoted_tags)[:10]

    # Merge mood (dedupe and limit to 2)
    main_mood = as_list(main.get("mood"))
    quoted_mood = as_list(quoted.get("mood"))
    merged_mood = dedupe(main_mood + quoted_mood)[:2]

    # Merge entities (dedupe, no limit)
    main_entities = as_list(main.get("entities"))
    quoted_entities = as_list(quoted.get("entities"))
    merged_entities = dedupe(main_entities + quoted_entities)

    # Content type: main takes precedence, fall back to quoted
    main_content_type = (main.get("content_type") or "other").lower()
    quoted_content_type = (quoted.get("content_type") or "other").lower()
    merged_content_type = (
        main_content_type if main_content_type != "other" else quoted_content_type
    )

    # Media: unified across both tweets
    has_media = bool(main.get("has_media", False) or quoted.get("has_media", False))
    media_type = pick_media_type(
        main.get("media_type", "none"), quoted.get("media_type", "none")
    )

    # Confidence: if either is low, result is low
    main_conf = str(main.get("media_confidence", "high")).lower()
    quoted_conf = str(quoted.get("media_confidence", "high")).lower()
    media_confidence = "low" if "low" in [main_conf, quoted_conf] else "high"

    return {
        "description": merged_description,
        "tags": merged_tags,
        "content_type": merged_content_type,
        "mood": merged_mood,
        "entities": merged_entities,
        "has_media": has_media,
        "media_type": media_type,
        "media_confidence": media_confidence,
    }


def fetch_and_describe(
    tweet_data: dict[str, Any],
    url_info: dict[str, Any],
    use_rich_model: bool = False,
) -> dict[str, Any]:
    """Analyze tweet content using Grok vision model.

    Sends tweet text and media (as image URLs) directly to Grok so the model
    can actually see images/video frames rather than relying on x_search summaries.

    Args:
        tweet_data: Raw Twitter API v2 response for the tweet.
        url_info: URL classification dict with 'url' key.
        use_rich_model: If True, use expensive model for better analysis.

    Returns:
        Dictionary with enrichment fields, or {'parse_error': True, 'raw_response': ...}
        if the LLM response couldn't be parsed as JSON.
    """
    model = MODEL_RICH if use_rich_model else MODEL_CHEAP

    if use_rich_model:
        print(f"\n🔬 Re-analyzing with rich model (media detected)...")
    else:
        print(f"\n📡 Analyzing tweet content...")
    print(f"   Model: {model}")
    username = url_info.get("username", "")
    if username:
        print(f"   User: @{username}")
    print(f"   Tweet ID: {url_info['tweet_id']}")

    tweet_text = tweet_data.get("data", {}).get("text", "")
    media_items = extract_media(tweet_data)

    if media_items:
        for item in media_items:
            tag = " [preview frame]" if item["is_preview"] else ""
            print(f"   Media: {item['type']}{tag}")

    messages = build_vision_messages(tweet_text, media_items, ENRICHMENT_PROMPT)

    client = _get_xai_client()
    response = client.chat.completions.create(model=model, messages=messages)  # type: ignore[arg-type]
    result_text = clean_response_json_text(response.choices[0].message.content or "")

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "parse_error": True}


def enrich_tweet_with_escalation(
    tweet_data: dict[str, Any],
    url_info: dict[str, Any],
    force_rich: bool = False,
) -> dict[str, Any]:
    """Enrich a tweet with cheap->rich model escalation when needed.

    Auto-escalates to rich model for video tweets (since we can only send
    a preview frame, the rich model does better with limited visual info).
    For images, the cheap model seeing the actual image is sufficient.

    Args:
        tweet_data: Raw Twitter API v2 response for the tweet.
        url_info: URL classification dict.
        force_rich: If True, skip cheap model and use rich model directly.

    Returns:
        Enrichment dictionary from either cheap or rich model analysis.
    """
    if force_rich:
        print("\n🔬 Forced rich model via --rich flag.")
        return fetch_and_describe(tweet_data, url_info, use_rich_model=True)

    # Auto-escalate for videos — we only have a preview frame, so the
    # rich model's stronger reasoning helps fill in the gaps.
    media_items = extract_media(tweet_data)
    has_video = any(m["type"] in ("video", "animated_gif") for m in media_items)

    if has_video:
        print("\n🔬 Video detected — using rich model (preview frame only).")
        return fetch_and_describe(tweet_data, url_info, use_rich_model=True)

    return fetch_and_describe(tweet_data, url_info, use_rich_model=False)


# ─── Main Pipeline ────────────────────────────────────────────────────────────


def run_pipeline(url: str, force_rich: bool = False) -> dict[str, Any]:
    """Run the full ingestion pipeline on a URL.

    Orchestrates the complete flow: classification, content fetching,
    enrichment (with model escalation), quote detection and merging,
    and finally embedding generation.

    Args:
        url: The tweet URL to process.
        force_rich: If True, skip cheap model and use rich model directly.

    Returns:
        Dictionary containing all enrichment data and the embedding vector.

    Raises:
        SystemExit: If XAI_API_KEY is not configured or source is unsupported.
    """
    
    missing = [k for k, v in {
        "XAI_API_KEY": x_api_key,
        "X_API_BEARER_TOKEN": x_api_bearer_token,
    }.items() if not v]
    if missing:
        print(f"❌ Error: Missing env vars: {', '.join(missing)}")
        print("   Add your keys to the .env file.")
        sys.exit(1)

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

    # ── Step 2: Fetch tweet data from Twitter API ──
    print(f"\n📡 Fetching tweet {url_info['tweet_id']} from Twitter API...")
    try:
        tweet_data = fetch_tweet(url_info["tweet_id"])
    except requests.HTTPError as exc:
        print(f"\n❌ Failed to fetch tweet: {exc}")
        sys.exit(1)

    author = tweet_data.get("includes", {}).get("users", [{}])[0]
    print(f"   Author: @{author.get('username', 'unknown')} ({author.get('name', '')})")
    print(f"   Text: {tweet_data.get('data', {}).get('text', '')[:120]}...")

    # ── Step 3: Analyze with vision model ──
    description = enrich_tweet_with_escalation(tweet_data, url_info, force_rich=force_rich)

    # ── Step 4: Detect and merge quoted tweet ──
    quote_result = detect_quoted_tweet(url_info)
    quote_url = quote_result.get("quoted_tweet_url", "")
    quote_id = quote_result.get("quoted_tweet_id", "")
    if not quote_url and quote_id:
        quote_url = f"https://x.com/i/web/status/{quote_id}"
    is_quote = bool(
        quote_result.get("is_quote_tweet", False) and (quote_url or quote_id)
    )

    if is_quote and not description.get("parse_error"):
        print(f"\n🔁 Quote tweet detected: {quote_url}")
        quoted_url_info = classify_url(quote_url)

        if quoted_url_info.get("source") == "x":
            try:
                quoted_tweet_data = fetch_tweet(quoted_url_info["tweet_id"])
            except requests.HTTPError as exc:
                print(f"\n⚠️  Could not fetch quoted tweet: {exc}")
                quoted_tweet_data = None

            if quoted_tweet_data is None:
                quoted_description = {"parse_error": True}
            else:
                quoted_description = enrich_tweet_with_escalation(
                    quoted_tweet_data,
                    quoted_url_info,
                    force_rich=force_rich,
                )
            if quoted_description.get("parse_error"):
                print(
                    "\n⚠️  Could not parse quoted tweet enrichment JSON. Keeping main tweet result."
                )
            else:
                description = merge_bookmark_records(description, quoted_description)
                print("\n✅ Merged quoted tweet content into this bookmark record.")
        else:
            print("\n⚠️  Quoted tweet URL was not parseable as an X status URL.")
    elif quote_result.get("parse_error"):
        print(
            "\n⚠️  Could not parse quote-detection JSON. Continuing with main tweet only."
        )
    else:
        print("\nℹ️  No quoted tweet detected.")

    # ── Step 5: Generate Embedding ──
    embedding = None
    if not description.get("parse_error"):
        print("\n🔢 Generating embedding vector...")
        embedding_text = f"{description.get('description', '')} {' '.join(description.get('tags', []))} {' '.join(description.get('entities', []))}"
        try:
            embedding = generate_embedding(embedding_text)
            print(f"   ✅ Generated embedding: {len(embedding)} dimensions")
        except Exception as e:
            print(f"\n❌ Error generating embedding: {e}")
            sys.exit(1)

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

        if embedding:
            print(f"\n🔢 Embedding: {len(embedding)} dimensions (vector generated)")

    print(f"\n{'=' * 60}")
    print("💡 Embedding generated and ready for vector DB storage.")
    print("   Tags stored for exact-match filtering.")
    print(f"{'=' * 60}")

    return {**description, "embedding": embedding}


def main() -> None:
    """CLI entry point for the pipeline.

    Parses command line arguments and runs the pipeline.
    Supports --rich flag to force expensive model usage.
    """
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
