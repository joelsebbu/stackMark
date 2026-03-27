"""CLI entry point for the Instagram ingestion pipeline.

Usage:
    uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
    uv run -m instagram_pipeline "https://www.instagram.com/user/reel/SHORTCODE/"
"""

from .pipeline import main

main()
