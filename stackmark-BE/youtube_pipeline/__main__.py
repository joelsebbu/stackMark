"""CLI entry point for the YouTube ingestion pipeline.

Usage:
    uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
    uv run -m youtube_pipeline "https://youtu.be/VIDEO_ID"
"""

from .pipeline import main

main()
