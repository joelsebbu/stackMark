"""YouTube data fetching — URL parsing and metadata retrieval."""

import re
import sys
from typing import Any

import yt_dlp

from .constants import YT_URL_PATTERNS


def extract_video_id(url: str) -> str:
    """Extract video ID from a YouTube URL."""
    for pattern in YT_URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    print(f"Could not extract video ID from: {url}")
    sys.exit(1)


def fetch_metadata(url: str) -> dict[str, Any]:
    """Fetch video metadata without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "channel": info.get("channel", "") or info.get("uploader", ""),
        "channel_id": info.get("channel_id", ""),
        "duration": info.get("duration", 0),
        "view_count": info.get("view_count", 0),
        "like_count": info.get("like_count", 0),
        "comment_count": info.get("comment_count", 0),
        "upload_date": info.get("upload_date", ""),
        "tags": info.get("tags", []),
        "categories": info.get("categories", []),
        "thumbnail": info.get("thumbnail", ""),
    }
