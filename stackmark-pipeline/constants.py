"""Configuration constants for the StackMark ingestion pipeline.

This module contains all hardcoded configuration values including:
- Model names and API endpoints
- Embedding dimensions and timeouts
- URL patterns for source classification
"""

# Model configurations for xAI Grok
MODEL_CHEAP = (
    "grok-4-1-fast-non-reasoning"  # Fast, cost-effective model for initial analysis
)
MODEL_RICH = "grok-4.20-beta-latest-non-reasoning"  # High-quality model for complex media analysis

# Embedding model configuration (via OpenRouter)
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024

# API endpoints
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
X_API_BASE_URL = "https://api.x.com/2"

# Request timeouts (seconds)
REQUEST_TIMEOUT = 15

# URL patterns for source classification
X_URL_PATTERN = r"(?:x\.com|twitter\.com)/(?:([A-Za-z0-9_]+)/status|i/web/status)/(\d+)"
X_STATUS_URL_NORMALIZE_PATTERN = (
    r"https?://(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)/status/(\d+)"
)

# Media type priority (for determining dominant media type)
MEDIA_TYPE_PRIORITY = ["video", "gif", "image", "none"]

# Content type options for enrichment
CONTENT_TYPES = [
    "meme",
    "tutorial",
    "article",
    "news",
    "thread",
    "tool",
    "library",
    "announcement",
    "opinion",
    "discussion",
    "resource",
    "showcase",
    "other",
]

# Mood options for enrichment
MOOD_OPTIONS = [
    "funny",
    "informative",
    "inspiring",
    "technical",
    "emotional",
    "controversial",
    "casual",
    "serious",
]
