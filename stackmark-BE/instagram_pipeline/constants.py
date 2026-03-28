"""Configuration constants for the Instagram ingestion pipeline."""

# LLM model (via OpenRouter)
IG_PIPELINE_MODEL = "google/gemini-2.5-flash-lite"

# Embedding model configuration (via OpenRouter)
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024

# API endpoints
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# URL pattern for Instagram posts and reels (handles optional username prefix)
IG_URL_PATTERN = r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:p|reel)/([A-Za-z0-9_-]+)"

# Frame extraction settings (ffmpeg fallback for video)
FRAME_INTERVAL_SECONDS = 2
