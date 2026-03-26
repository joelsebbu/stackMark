# StackMark Ingestion Pipeline

## What is this?
A prototype ingestion pipeline for StackMark, a personal bookmark manager. It processes X/Twitter tweet URLs into search-optimized descriptions with vector embeddings for cosine similarity search.

## Tech stack
- Python 3.11+, managed with `uv`
- LLM: `google/gemini-2.5-flash-lite` via OpenRouter (OpenAI-compatible API)
- Embeddings: `qwen/qwen3-embedding-8b` via OpenRouter (1024 dimensions)
- Twitter API v2 for tweet data, media, and replies
- No database yet — output is printed JSON + embedding vector

## Required env vars (in `.env`)
- `OPENROUTER_API_KEY` — for LLM and embedding calls
- `X_API_BEARER_TOKEN` — for Twitter API v2

## How to run
```bash
cd stackmark-pipeline
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
```

## Project structure
```
stackmark-pipeline/
├── pyproject.toml          # Dependencies: python-dotenv, requests, openai
├── uv.lock
└── x_pipeline/             # Core pipeline package
    ├── pipeline.py         # Main orchestration + Twitter API calls
    ├── constants.py        # Model names, API endpoints, config values
    ├── prompts.py          # LLM prompts (enrichment + video triage)
    ├── utils.py            # Text processing helpers
    └── tweets.csv          # Sample tweet data
```

## Pipeline flow
1. Classify URL (only X/Twitter supported)
2. Fetch tweet via Twitter API v2 (text, media, author)
3. Enrich with Gemini:
   - **No video**: sends tweet text + images directly
   - **Video detected**: sends text + preview frame + fetched replies. Model decides if it has enough context. If not, returns `needs_video_review: true`
4. Detect quoted tweets via Twitter API v2 metadata (`referenced_tweets`)
5. If quote tweet found: fetch + enrich it too, then merge both records
6. Generate embedding vector via OpenRouter

## Key design decisions
- No video downloading — video tweets are triaged from text + preview + replies
- Single LLM model (`gemini-2.5-flash-lite`) for all enrichment — chosen for cost
- Anti-hallucination rules in prompts: model must only use info explicitly present in provided content
- All LLM calls go through OpenRouter's OpenAI-compatible API via a single shared client
