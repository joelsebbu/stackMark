"""Configuration constants for the web ingestion pipeline."""

# LLM model (via OpenRouter)
WEB_PIPELINE_MODEL = "google/gemini-2.5-flash-lite"

# Embedding model configuration (via OpenRouter)
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024

# API endpoints
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Page fetching
REQUEST_TIMEOUT = 30_000  # milliseconds for Playwright navigation
MAX_CONTENT_LENGTH = 100_000  # chars of extracted body text to send to LLM
