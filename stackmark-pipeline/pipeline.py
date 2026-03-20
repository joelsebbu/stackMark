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
import requests

from dotenv import load_dotenv
from openai import OpenAI
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import x_search

# Load .env file automatically
load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

MODEL_CHEAP = "grok-4-1-fast-non-reasoning"
MODEL_RICH = "grok-4.20-beta-latest-non-reasoning"

# OpenRouter client for embeddings
_openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
_embedding_client = (
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_openrouter_api_key)
    if _openrouter_api_key
    else None
)


# ─── Step 1: Source Classification ────────────────────────────────────────────


def classify_url(url: str) -> dict:
    """Classify the URL and extract useful identifiers."""

    x_pattern = r"(?:x\.com|twitter\.com)/(?:([A-Za-z0-9_]+)/status|i/web/status)/(\d+)"
    match = re.search(x_pattern, url)
    if match:
        return {
            "source": "x",
            "username": match.group(1) or "",
            "tweet_id": match.group(2),
            "url": url,
        }

    return {"source": "unknown", "url": url}


# ─── Step 4: Generate Embedding ─────────────────────────────────────────────


def generate_embedding(text: str) -> list[float]:
    """Generate vector embedding via OpenRouter."""
    global _embedding_client

    if not _embedding_client:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("❌ Error: OPENROUTER_API_KEY not set in environment.")
            sys.exit(1)
        _embedding_client = OpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=api_key
        )

    response = _embedding_client.embeddings.create(
        model="qwen/qwen3-embedding-8b",
        input=text,
        dimensions=1024,
    )
    return response.data[0].embedding


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


QUOTE_DETECTION_PROMPT = """\
You are a tweet relationship analyzer.

Find the tweet at the URL below using x_search. Determine whether the tweet is a
quote tweet (a tweet that quotes another tweet).

Tweet URL: {url}

Return ONLY a valid JSON object with these fields:
{{
  "is_quote_tweet": true or false,
  "quoted_tweet_url": "full quoted tweet URL or empty string",
  "quoted_tweet_id": "numeric ID or empty string",
  "quoted_username": "username without @ or empty string"
}}

RULES:
1. If the tweet is not a quote tweet, return false and empty strings.
2. If it is a quote tweet, fill as many quoted fields as you can.
3. quoted_tweet_url should be canonical when possible: https://x.com/<username>/status/<id>
4. Return ONLY the JSON object.
"""


def _clean_response_json_text(result_text: str) -> str:
    """Remove markdown fences/prefixes before json.loads."""
    cleaned = result_text.strip().strip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    return cleaned.strip()


def _as_list(value) -> list:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _normalize_status_url(url: str) -> str:
    match = re.search(
        r"https?://(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)/status/(\d+)", url or ""
    )
    if not match:
        return ""
    return f"https://x.com/{match.group(1)}/status/{match.group(2)}"


def parse_quoted_tweet_from_x_api_payload(payload: dict) -> dict:
    """Parse X API v2 tweet payload and extract quoted tweet metadata."""
    data = payload.get("data", {}) or {}
    referenced = data.get("referenced_tweets", []) or []

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

    users_by_id = {
        str(user.get("id", "")).strip(): str(user.get("username", "")).strip()
        for user in included_users
        if user.get("id") and user.get("username")
    }

    quoted_tweet_obj = None
    for tweet in included_tweets:
        if str(tweet.get("id", "")).strip() == quoted_tweet_id:
            quoted_tweet_obj = tweet
            break

    quoted_username = ""
    if quoted_tweet_obj:
        author_id = str(quoted_tweet_obj.get("author_id", "")).strip()
        quoted_username = users_by_id.get(author_id, "")

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


def _pick_media_type(main_media_type: str, quoted_media_type: str) -> str:
    priority = ["video", "gif", "image", "none"]
    values = [
        (main_media_type or "none").lower(),
        (quoted_media_type or "none").lower(),
    ]
    for media_type in priority:
        if media_type in values:
            return media_type
    return "none"


def merge_bookmark_records(main: dict, quoted: dict) -> dict:
    """Merge main tweet enrichment and quoted tweet enrichment into one record."""
    main_description = (main.get("description") or "").strip()
    quoted_description = (quoted.get("description") or "").strip()

    if main_description and quoted_description:
        merged_description = (
            f"{main_description} quoted tweet context {quoted_description}"
        )
    else:
        merged_description = main_description or quoted_description

    main_tags = [tag.lower() for tag in _as_list(main.get("tags"))]
    quoted_tags = [tag.lower() for tag in _as_list(quoted.get("tags"))]
    merged_tags = _dedupe(main_tags + quoted_tags)[:10]

    main_mood = _as_list(main.get("mood"))
    quoted_mood = _as_list(quoted.get("mood"))
    merged_mood = _dedupe(main_mood + quoted_mood)[:2]

    main_entities = _as_list(main.get("entities"))
    quoted_entities = _as_list(quoted.get("entities"))
    merged_entities = _dedupe(main_entities + quoted_entities)

    main_content_type = (main.get("content_type") or "other").lower()
    quoted_content_type = (quoted.get("content_type") or "other").lower()
    merged_content_type = (
        main_content_type if main_content_type != "other" else quoted_content_type
    )

    has_media = bool(main.get("has_media", False) or quoted.get("has_media", False))
    media_type = _pick_media_type(
        main.get("media_type", "none"), quoted.get("media_type", "none")
    )

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
    client: Client, url_info: dict, use_rich_model: bool = False
) -> dict:
    """Fetch tweet content AND generate description in one Grok call."""

    model = MODEL_RICH if use_rich_model else MODEL_CHEAP

    if use_rich_model:
        print(f"\n🔬 Re-analyzing with rich model (media detected)...")
    else:
        print(f"\n📡 Fetching tweet and generating description...")
    print(f"   Model: {model}")
    username = url_info.get("username", "")
    if username:
        print(f"   User: @{username}")
    else:
        print("   User: (unknown)")
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
    result_text = _clean_response_json_text(response.content)

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "parse_error": True}


def detect_quoted_tweet_with_llm(client: Client, url_info: dict) -> dict:
    """Fallback quote detection using Grok + x_search."""
    chat = client.chat.create(
        model=MODEL_CHEAP,
        tools=[x_search()],
    )
    chat.append(user(QUOTE_DETECTION_PROMPT.format(url=url_info["url"])))

    response = chat.sample()
    result_text = _clean_response_json_text(response.content)

    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        return {
            "is_quote_tweet": False,
            "quoted_tweet_url": "",
            "quoted_tweet_id": "",
            "quoted_username": "",
            "parse_error": True,
        }

    quoted_url = _normalize_status_url(str(result.get("quoted_tweet_url", "")))
    quoted_id = str(result.get("quoted_tweet_id", "") or "").strip()
    quoted_username = str(result.get("quoted_username", "") or "").strip().lstrip("@")

    if not quoted_url and quoted_id and quoted_username:
        quoted_url = f"https://x.com/{quoted_username}/status/{quoted_id}"

    return {
        "is_quote_tweet": bool(result.get("is_quote_tweet", False)),
        "quoted_tweet_url": quoted_url,
        "quoted_tweet_id": quoted_id,
        "quoted_username": quoted_username,
        "detection_source": "x_search_llm",
    }


def detect_quoted_tweet_with_x_api(url_info: dict) -> dict:
    """Primary quote detection using deterministic X API v2 metadata."""
    bearer_token = os.getenv("X_API_BEARER_TOKEN")
    if not bearer_token:
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
    endpoint = f"https://api.x.com/2/tweets/{tweet_id}"
    params = {
        "tweet.fields": "referenced_tweets,author_id",
        "expansions": "referenced_tweets.id,referenced_tweets.id.author_id",
        "user.fields": "username",
    }
    headers = {"Authorization": f"Bearer {bearer_token}"}

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
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


def detect_quoted_tweet(client: Client, url_info: dict) -> dict:
    """Detect quoted tweet, preferring deterministic X API and falling back to LLM."""
    print("\n🔎 Detecting whether this tweet quotes another tweet...")

    api_result = detect_quoted_tweet_with_x_api(url_info)
    if not api_result.get("error"):
        print("   Detection source: X API v2")
        return api_result

    print(f"   X API detection unavailable: {api_result.get('error')}")
    print("   Falling back to x_search-based detection...")
    return detect_quoted_tweet_with_llm(client, url_info)


def enrich_tweet_with_escalation(
    client: Client, url_info: dict, force_rich: bool = False
) -> dict:
    """Fetch and enrich a tweet with cheap->rich escalation when needed."""
    if force_rich:
        print("\n🔬 Forced rich model via --rich flag.")
        return fetch_and_describe(client, url_info, use_rich_model=True)

    description = fetch_and_describe(client, url_info, use_rich_model=False)

    if not description.get("parse_error"):
        has_media = description.get("has_media", False)
        confidence = str(description.get("media_confidence", "high")).lower()

        if confidence == "low" and has_media:
            print("\n⚠️  Model reported low confidence and tweet has media.")
            print("   Escalating to rich model for better analysis...")
            description = fetch_and_describe(client, url_info, use_rich_model=True)
        elif confidence == "low":
            print("\n📝 Low confidence but no media — keeping as-is.")
        else:
            print("\n✅ High confidence from cheap model.")

    return description


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

    # ── Step 2+3: Fetch & Describe main tweet ──
    description = enrich_tweet_with_escalation(client, url_info, force_rich=force_rich)

    # ── Step 4: Detect and merge quoted tweet ──
    quote_result = detect_quoted_tweet(client, url_info)
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
            quoted_description = enrich_tweet_with_escalation(
                client,
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

    # ── Step 5: Generate Embedding ───────────────────────────────────────────
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
