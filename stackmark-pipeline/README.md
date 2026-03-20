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

The output is a JSON description optimized for vector embedding search:

```json
{
  "description": "A tweet announcing FastAPI 1.0, a Python web framework...",
  "topics": ["fastapi", "python", "web framework", "api", "open source"],
  "content_type": "announcement",
  "mood": "informative",
  "entities": ["FastAPI", "Sebastián Ramírez", "Python"]
}
```

## Cost

Using `grok-4-1-fast-non-reasoning` — each bookmark costs well under $0.01.
