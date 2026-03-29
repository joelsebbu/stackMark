# StackMark — Ingestion Pipeline & API

Personal bookmark manager that takes social media URLs → fetches content → analyzes with Gemini → generates search-optimized descriptions and embeddings → exposes via FastAPI.

Supported sources: **X/Twitter**, **Instagram** (posts, reels, carousels), **YouTube**, **Web** (any URL).

## Setup

```bash
# 1. Navigate to this folder
cd stackmark-BE

# 2. Set your API keys
cp .env.example .env
# Edit .env and add:
#   OPENROUTER_API_KEY  — from https://openrouter.ai/keys
#   X_API_BEARER_TOKEN  — from https://developer.x.com
#   DATABASE_URL or DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME — PostgreSQL

# 3. Ensure ffmpeg is installed (needed for Instagram video fallback)
sudo apt install ffmpeg

# 4. Install Playwright browser (needed for web pipeline JS fallback)
uv run playwright install chromium

# 5. Install dependencies
uv sync
```

## Running the API

```bash
# Start the FastAPI server
uv run uvicorn app:app --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health

# Ingest a URL (auto-detects source: x, instagram, youtube, or web)
curl -X POST http://localhost:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://x.com/someone/status/123456"}'

# Semantic search
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "funny programming meme", "top_k": 5}'
```

All responses follow a common structure:
```json
{
  "success": true,
  "error": null,
  "data": { ... }
}
```

## CLI usage (still works)

```bash
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
uv run -m web_pipeline "https://example.com/article"
uv run -m retrieval.search "your query" --top 5
```

`uv run` will create a `.venv`, install dependencies, and run the command.

## How it works

### Unified URL router
The `router.py` module auto-detects the URL source using regex patterns from each pipeline and dispatches to the correct `run_pipeline()`. The web pipeline is the fallback for any URL that doesn't match X, Instagram, or YouTube.

### API layer
`app.py` exposes two FastAPI endpoints (`POST /ingest`, `POST /search`) with:
- Common response structure (`success`, `error`, `data`)
- `PipelineError` exceptions instead of `sys.exit()` for safe concurrent request handling
- Per-request timeouts (5 min for ingestion, 30s for search) to prevent stuck threads

### X/Twitter pipeline
```
Tweet URL → Classify → Fetch (Twitter API v2) → Analyze (Gemini) → Detect quote tweet → Merge quoted content → Generate embedding → Store in DB
```

For video tweets, the pipeline triages with the tweet text + preview frame + top replies. If the model can produce a confident description from that context alone, it does. Otherwise, the tweet is flagged with `needs_video_review: true` for later processing.

### Instagram pipeline
```
Instagram URL → Extract shortcode → Fetch (instaloader) → Download media → Analyze (Gemini) → Generate embedding → Store in DB → Clean up downloaded media
```

For video reels, the pipeline sends the full video as base64 to Gemini. If that fails (size limits, API errors), it falls back to extracting frames with ffmpeg and sending them as multiple images. Downloaded media is automatically cleaned up after processing (success or failure).

### YouTube pipeline
```
YouTube URL → Extract video ID → Fetch metadata (yt-dlp) → Analyze (Gemini, direct URL) → Generate embedding → Store in DB
```

Passes the YouTube URL directly to Gemini for video analysis — no downloading needed. Falls back to metadata-only analysis if URL analysis fails.

### Web pipeline
```
Any URL → Fetch page (httpx → Playwright fallback) → Extract metadata + text (BeautifulSoup) → Analyze (Gemini) → Generate embedding → Store in DB
```

Tries a lightweight HTTP fetch up to 3 times. If all attempts return too little content (likely a JS-rendered SPA) or fail, falls back to Playwright headless Chromium to render the page with JavaScript.

### Output format

All pipelines produce the same JSON schema optimized for vector embedding search:

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
stackmark-BE/
├── app.py                   # FastAPI application (POST /ingest, POST /search)
├── router.py                # Unified URL router — auto-detects source, dispatches to pipeline
├── errors.py                # PipelineError exception
├── pyproject.toml
├── uv.lock
├── README.md
├── x_pipeline/              # X/Twitter ingestion
│   ├── pipeline.py          # Main orchestration
│   ├── constants.py         # Model names, API endpoints, config
│   ├── prompts.py           # LLM prompts (enrichment + video triage)
│   ├── utils.py             # Text processing helpers
│   └── tweets.csv           # Sample tweet data
├── instagram_pipeline/      # Instagram ingestion
│   ├── pipeline.py          # Main orchestration
│   ├── fetcher.py           # URL parsing, instaloader fetch + download
│   ├── media.py             # base64 encoding, file finding, ffmpeg frames
│   ├── messages.py          # LLM message building (photo/video/frames)
│   ├── llm.py               # OpenRouter client, LLM calls, embeddings
│   ├── constants.py         # Model names, URL pattern, frame settings
│   └── prompts.py           # Enrichment prompt for Instagram
├── youtube_pipeline/        # YouTube ingestion
│   ├── pipeline.py          # Main orchestration
│   ├── fetcher.py           # URL parsing, yt-dlp metadata fetch
│   ├── messages.py          # LLM message building
│   ├── llm.py               # OpenRouter client, LLM calls, embeddings
│   ├── constants.py         # Model names, URL patterns
│   └── prompts.py           # Enrichment prompt for YouTube
├── web_pipeline/            # Web page ingestion (any URL)
│   ├── pipeline.py          # Main orchestration
│   ├── fetcher.py           # httpx fetch + Playwright fallback, BeautifulSoup extraction
│   ├── messages.py          # LLM message building
│   ├── llm.py               # OpenRouter client, LLM calls, embeddings
│   ├── constants.py         # Model names, content length limits
│   └── prompts.py           # Enrichment prompt for web pages
├── db/                      # Database layer
│   ├── base.py              # SQLAlchemy DeclarativeBase
│   ├── session.py           # Engine + SessionLocal factory
│   ├── operations.py        # insert_embedding()
│   └── models/
│       └── embedding.py     # Embedding model (uuid, source, url, vector, created_at)
├── retrieval/               # Semantic search layer
│   ├── search.py            # generate_query_embedding() + search()
│   └── __main__.py          # CLI entry point
└── alembic/                 # Database migrations
    └── versions/
```

## Cost

Using `google/gemini-2.5-flash-lite` via OpenRouter — each bookmark costs well under $0.01.
