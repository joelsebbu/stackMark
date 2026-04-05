"""Configuration constants for the retrieval pipeline."""

from x_pipeline.constants import OPENROUTER_BASE_URL  # noqa: F401

# LLM model for re-ranking search results
RERANK_MODEL = "google/gemini-2.5-flash-lite"

# Number of candidates to fetch from pgvector for re-ranking
RERANK_POOL = 10
