# StackMark — Ingestion Pipeline Prototype

Barebone prototype of the StackMark ingestion pipeline.  
Takes a tweet URL → fetches content via Grok's x_search → generates a search-optimized description.

## Setup

```bash
# 1. Clone / navigate to this folder
cd stackmark-pipeline

# 2. Set your xAI API key
cp .env.example .env
# Edit .env and add your key from https://console.x.ai/team/default/api-keys

# 3. Run it (uv handles venv + deps automatically)
uv run pipeline.py "https://x.com/someone/status/123456"
```

That's it. `uv run` will:
- Create a `.venv` virtual environment
- Install `xai-sdk` and all its dependencies
- Run the pipeline

## What it does

```
Tweet URL → Classify → Fetch (x_search) → AI Enrich (Grok) → Print Description
```

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

## Cost

Using `grok-4-1-fast-non-reasoning` — each bookmark costs well under $0.01.
