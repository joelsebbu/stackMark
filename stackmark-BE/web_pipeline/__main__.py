"""CLI entry point for the web ingestion pipeline.

Usage:
    uv run -m web_pipeline "https://example.com/article"
"""

from .pipeline import main

main()
