"""Configuration constants for the YouTube ingestion pipeline."""

# LLM model (via OpenRouter)
YT_PIPELINE_MODEL = "google/gemini-2.5-flash-lite"

# Embedding model configuration (via OpenRouter)
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024

# API endpoints
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# URL patterns for YouTube videos
YT_URL_PATTERNS = [
    r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
]
