"""Unified URL router for StackMark ingestion pipelines.

Detects the source from a URL and dispatches to the correct pipeline.
"""

import re
from typing import Any

from x_pipeline.constants import X_URL_PATTERN
from instagram_pipeline.constants import IG_URL_PATTERN
from youtube_pipeline.constants import YT_URL_PATTERNS


SOURCE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("x", re.compile(X_URL_PATTERN)),
    ("instagram", re.compile(IG_URL_PATTERN)),
]
for yt_pattern in YT_URL_PATTERNS:
    SOURCE_PATTERNS.append(("youtube", re.compile(yt_pattern)))


def detect_source(url: str) -> str:
    """Classify a URL into one of: x, instagram, youtube, web."""
    for source, pattern in SOURCE_PATTERNS:
        if pattern.search(url):
            return source
    return "web"


def ingest(url: str) -> dict[str, Any]:
    """Route a URL to the appropriate pipeline and run it."""
    source = detect_source(url)

    if source == "x":
        from x_pipeline.pipeline import run_pipeline
    elif source == "instagram":
        from instagram_pipeline.pipeline import run_pipeline
    elif source == "youtube":
        from youtube_pipeline.pipeline import run_pipeline
    else:
        from web_pipeline.pipeline import run_pipeline

    return run_pipeline(url)
