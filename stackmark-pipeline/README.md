# StackMark — Ingestion Pipeline Prototype

Barebone prototype of the StackMark ingestion pipeline.
Takes a tweet URL → fetches content via Twitter API v2 → analyzes with Gemini → generates a search-optimized description and embedding.

## Setup

```bash
# 1. Clone / navigate to this folder
cd stackmark-pipeline

# 2. Set your API keys
cp .env.example .env
# Edit .env and add:
#   OPENROUTER_API_KEY  — from https://openrouter.ai/keys
#   X_API_BEARER_TOKEN  — from https://developer.x.com

# 3. Run it (uv handles venv + deps automatically)
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
```

That's it. `uv run` will:
- Create a `.venv` virtual environment
- Install dependencies (openai, requests, python-dotenv)
- Run the pipeline

## What it does

```
Tweet URL → Classify → Fetch (Twitter API v2) → Analyze (Gemini) → Detect quote tweet → Merge quoted content → Generate embedding → Output
```

For video tweets, the pipeline triages with the tweet text + preview frame + top replies. If the model can produce a confident description from that context alone, it does. Otherwise, the tweet is flagged with `needs_video_review: true` for later processing.

The output is a JSON payload optimized for vector embedding search:

```json
{
  "description": "fastapi python web framework api announcement open source ...",
  "tags": ["fastapi", "python", "announcement", "tech", "api"],
  "content_type": "announcement",
  "mood": ["informative", "technical"],
  "entities": ["FastAPI", "Sebastian Ramirez", "Python"],
  "has_media": false,
  "media_type": "none",
  "media_confidence": "high"
}
```

## Project structure

```
stackmark-pipeline/
├── pyproject.toml
├── uv.lock
├── README.md
└── x_pipeline/
    ├── __init__.py
    ├── pipeline.py      # Main pipeline orchestration
    ├── constants.py     # Model names, API endpoints, config
    ├── prompts.py       # LLM prompts (enrichment + video triage)
    ├── utils.py         # Text processing helpers
    └── tweets.csv       # Sample tweet data
```

## Cost

Using `google/gemini-2.5-flash-lite` via OpenRouter — each bookmark costs well under $0.01.
