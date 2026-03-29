# StackMark Backend

## What is this?
Backend for StackMark, a personal bookmark manager. A FastAPI server exposes two endpoints: one for ingesting URLs (auto-routed to the correct pipeline) and one for semantic search. Ingestion pipelines process social media URLs into search-optimized descriptions with vector embeddings.

## Tech stack
- Python 3.11+, managed with `uv`
- **FastAPI** + **uvicorn** for the HTTP API
- LLM: `google/gemini-2.5-flash-lite` via OpenRouter (OpenAI-compatible API)
- Embeddings: `qwen/qwen3-embedding-8b` via OpenRouter (1024 dimensions)
- Database: PostgreSQL with pgvector (HNSW index, cosine distance)
- ORM: SQLAlchemy 2.0 + Alembic migrations
- Twitter API v2 for tweet data, media, and replies
- instaloader for Instagram post/reel data (no API key needed)
- yt-dlp for YouTube video metadata (no API key needed)
- ffmpeg/ffprobe for video frame extraction (Instagram video fallback)
- Playwright (headless Chromium) for web page rendering (handles JS-heavy sites)
- beautifulsoup4 for HTML parsing and content extraction

## Required env vars (in `.env`)
- `OPENROUTER_API_KEY` — for LLM and embedding calls
- `X_API_BEARER_TOKEN` — for Twitter API v2
- `DATABASE_URL` or `DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME` — PostgreSQL connection

## How to run
```bash
cd stackmark-BE

# Start the FastAPI server
uv run uvicorn app:app --host 0.0.0.0 --port 8000

# API endpoints
# POST /ingest   — body: {"url": "..."}
# POST /search   — body: {"query": "...", "top_k": 3}
# GET  /health   — returns {"status": "ok"}

# CLI still works for individual pipelines
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
uv run -m web_pipeline "https://example.com/article"
uv run -m retrieval.search "your query" --top 5
```

## API response format
All endpoints return a common response structure:
```json
{"success": true, "error": null, "data": { ... }}
{"success": false, "error": "error message", "data": null}
```

## Project structure
```
stackmark-BE/
├── app.py                  # FastAPI application (POST /ingest, POST /search, GET /health)
├── router.py               # Unified URL router — detect_source() + ingest()
├── errors.py               # PipelineError exception (replaces sys.exit in pipelines)
├── pyproject.toml          # Dependencies and project metadata
├── uv.lock
├── alembic.ini             # Alembic config (points to alembic/)
├── alembic/                # Database migrations
│   └── versions/           # Migration scripts
├── db/                     # Database layer
│   ├── base.py             # SQLAlchemy DeclarativeBase
│   ├── session.py          # Engine + SessionLocal factory
│   ├── operations.py       # insert_embedding()
│   └── models/
│       └── embedding.py    # Embedding model (uuid, source, url, vector, created_at)
├── x_pipeline/             # X/Twitter ingestion pipeline
│   ├── pipeline.py         # Main orchestration + Twitter API calls
│   ├── constants.py        # Model names, API endpoints, config values
│   ├── prompts.py          # LLM prompts (enrichment + video triage)
│   ├── utils.py            # Text processing helpers
│   └── tweets.csv          # Sample tweet data
├── instagram_pipeline/     # Instagram ingestion pipeline
│   ├── pipeline.py         # Main orchestration (enrich_post, run_pipeline)
│   ├── fetcher.py          # URL parsing, instaloader fetch + download
│   ├── media.py            # base64 encoding, file finding, ffmpeg frames
│   ├── messages.py         # LLM message building (photo/video/frames)
│   ├── llm.py              # OpenRouter client, LLM calls, embeddings
│   ├── constants.py        # Model names, URL pattern, frame settings
│   ├── prompts.py          # ENRICHMENT_PROMPT for Instagram
│   └── __main__.py         # CLI entry point
├── youtube_pipeline/       # YouTube ingestion pipeline
│   ├── pipeline.py         # Main orchestration (enrich_video, run_pipeline)
│   ├── fetcher.py          # URL parsing, yt-dlp metadata fetch
│   ├── messages.py         # LLM message building (video URL / metadata-only)
│   ├── llm.py              # OpenRouter client, LLM calls, embeddings
│   ├── constants.py        # Model names, URL patterns
│   ├── prompts.py          # ENRICHMENT_PROMPT for YouTube
│   └── __main__.py         # CLI entry point
├── web_pipeline/           # Web page ingestion pipeline
│   ├── pipeline.py         # Main orchestration (enrich_page, run_pipeline)
│   ├── fetcher.py          # httpx fetch + Playwright fallback, BeautifulSoup extraction
│   ├── messages.py         # LLM message building (text-only)
│   ├── llm.py              # OpenRouter client, LLM calls, embeddings
│   ├── constants.py        # Model names, content length limits
│   ├── prompts.py          # ENRICHMENT_PROMPT for web pages
│   └── __main__.py         # CLI entry point
└── retrieval/              # Semantic search layer
    ├── search.py           # generate_query_embedding() + search()
    └── __main__.py         # CLI entry point
```

## API layer (app.py + router.py)
- `router.py` — `detect_source(url)` matches URL against X, Instagram, YouTube patterns (from each pipeline's constants); falls back to `"web"`. `ingest(url)` dispatches to the correct `run_pipeline()`.
- `app.py` — FastAPI app with `POST /ingest`, `POST /search`, `GET /health`. Uses `concurrent.futures` for per-request timeouts (5 min ingestion, 30s search). Catches `PipelineError` for clean error responses.

## Error handling
- `errors.py` defines `PipelineError`, used across all pipelines instead of `sys.exit(1)`
- Pipeline failures raise `PipelineError` with descriptive messages
- `app.py` catches these and returns `{"success": false, "error": "...", "data": null}`
- `sys.exit(1)` is only used in CLI `main()` entry points (not reachable via API)

## Pipeline flow (x_pipeline)
1. Classify URL (only X/Twitter supported)
2. Fetch tweet via Twitter API v2 (text, media, author)
3. Enrich with Gemini:
   - **No video**: sends tweet text + images directly
   - **Video detected**: sends text + preview frame + fetched replies. Model decides if it has enough context. If not, returns `needs_video_review: true`
4. Detect quoted tweets via Twitter API v2 metadata (`referenced_tweets`)
5. If quote tweet found: fetch + enrich it too, then merge both records
6. Generate embedding vector via OpenRouter
7. Store embedding + metadata in PostgreSQL via `db.operations.insert_embedding()`

## Retrieval flow
1. Embed the query string using the same model/dimensions as ingestion
2. Cosine similarity search via pgvector HNSW index
3. Return top-k results with similarity scores

## Pipeline flow (instagram_pipeline)
1. Parse URL → extract shortcode via regex
2. Fetch post metadata via instaloader (caption, owner, hashtags, media URLs)
3. Download media to a temporary directory
4. Enrich with Gemini:
   - **Photo/Carousel**: base64-encode images, send as multiple `image_url` blocks + caption
   - **Video/Reel**: try base64 full video → fallback to ffmpeg frame extraction
5. Generate embedding vector via OpenRouter
6. Store in PostgreSQL via `db.operations.insert_embedding(source="instagram", ...)`
7. Clean up downloaded media (always runs, even on error)

## Pipeline flow (youtube_pipeline)
1. Parse URL → extract video ID via regex (watch, youtu.be, shorts)
2. Fetch video metadata via yt-dlp (title, description, channel, duration, tags)
3. Enrich with Gemini:
   - Pass YouTube URL directly to Gemini for video analysis (no download needed)
   - Fallback to metadata-only analysis if URL analysis fails
4. Generate embedding vector via OpenRouter
5. Store in PostgreSQL via `db.operations.insert_embedding(source="youtube", ...)`

## Pipeline flow (web_pipeline)
1. Fetch page via httpx (fast, up to 3 retries); fallback to Playwright headless Chromium if all attempts return too little content (JS-rendered sites)
2. Extract metadata (title, meta description, OG tags) and main text content via BeautifulSoup
3. Enrich with Gemini (text-only — page content + metadata sent as text block)
4. Generate embedding vector via OpenRouter
5. Store in PostgreSQL via `db.operations.insert_embedding(source="web", ...)`

## Key design decisions
- FastAPI + uvicorn for the HTTP API; sync endpoints run in a threadpool for concurrency
- Unified URL router (`router.py`) auto-detects source and dispatches — single entry point for all pipelines
- `PipelineError` replaces `sys.exit(1)` to make pipelines safe for concurrent API requests
- Per-request timeouts prevent stuck threads from exhausting the threadpool
- No video downloading for x_pipeline — video tweets are triaged from text + preview + replies
- Instagram pipeline downloads media temporarily, cleans up via `try/finally` + `shutil.rmtree()`
- FFmpeg frame extraction as fallback when base64 video fails (size limits, API errors)
- Single LLM model (`gemini-2.5-flash-lite`) for all enrichment — chosen for cost
- Anti-hallucination rules in prompts: model must only use info explicitly present in provided content
- All LLM calls go through OpenRouter's OpenAI-compatible API via a single shared client
- YouTube pipeline passes URL directly to Gemini for video analysis — no download needed
- yt-dlp used only for metadata fetching (no API key required)
- Same embedding model + dimensions used for both ingestion and retrieval to ensure consistency
- Web pipeline uses httpx for fast fetching, Playwright as fallback for JS-rendered pages (React, SPAs)
- Web pipeline sends text-only to Gemini (no images) — og:image URL included as metadata
