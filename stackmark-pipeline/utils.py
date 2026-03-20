"""Utility functions for the StackMark ingestion pipeline.

This module contains helper functions for text processing, data normalization,
and media type handling.
"""

import re
from typing import Any

from constants import MEDIA_TYPE_PRIORITY, X_STATUS_URL_NORMALIZE_PATTERN


def clean_response_json_text(result_text: str) -> str:
    """Remove markdown fences and JSON prefixes from LLM response text.

    LLM responses often include markdown code fences (```json) or other
    formatting that needs to be stripped before parsing as JSON.

    Args:
        result_text: Raw text response from LLM.

    Returns:
        Cleaned text suitable for json.loads().
    """
    cleaned = result_text.strip().strip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    return cleaned.strip()


def as_list(value: Any) -> list[str]:
    """Normalize a value to a list of non-empty strings.

    Handles various input types:
    - Lists: converts each item to string and filters empties
    - Strings: returns single-item list if non-empty
    - Other types: returns empty list

    Args:
        value: Value to normalize (list, string, or other).

    Returns:
        List of non-empty strings.
    """
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def dedupe(items: list[str]) -> list[str]:
    """Remove duplicate items while preserving order.

    Uses case-sensitive comparison. First occurrence is kept.

    Args:
        items: List of strings that may contain duplicates.

    Returns:
        List with duplicates removed, order preserved.
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_status_url(url: str) -> str:
    """Normalize X/Twitter status URL to canonical form.

    Extracts username and tweet ID from various X/Twitter URL formats
    and returns a canonical https://x.com/<username>/status/<id> URL.

    Args:
        url: Raw URL string (may be from various sources, possibly None).

    Returns:
        Canonical X status URL, or empty string if not parseable.
    """
    match = re.search(X_STATUS_URL_NORMALIZE_PATTERN, url or "")
    if not match:
        return ""
    return f"https://x.com/{match.group(1)}/status/{match.group(2)}"


def pick_media_type(main_media_type: str, quoted_media_type: str) -> str:
    """Determine dominant media type between main and quoted tweet.

    Prioritizes media types by richness: video > gif > image > none.
    This ensures the most content-rich media type is used for display
    and further processing decisions.

    Args:
        main_media_type: Media type from main tweet (video, gif, image, none).
        quoted_media_type: Media type from quoted tweet (video, gif, image, none).

    Returns:
        Dominant media type based on priority order.
    """
    values = [
        (main_media_type or "none").lower(),
        (quoted_media_type or "none").lower(),
    ]
    for media_type in MEDIA_TYPE_PRIORITY:
        if media_type in values:
            return media_type
    return "none"
