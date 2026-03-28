# StackMark Backend

## What is this?
Backend for StackMark, a personal bookmark manager. Ingestion pipelines process social media URLs into search-optimized descriptions with vector embeddings. A retrieval layer provides semantic search over stored bookmarks.

## Tech stack
- Python 3.11+, managed with `uv`
- LLM: `google/gemini-2.5-flash-lite` via OpenRouter (OpenAI-compatible API)
- Embeddings: `qwen/qwen3-embedding-8b` via OpenRouter (1024 dimensions)
- Database: PostgreSQL with pgvector (HNSW index, cosine distance)
- ORM: SQLAlchemy 2.0 + Alembic migrations
- Twitter API v2 for tweet data, media, and replies
- instaloader for Instagram post/reel data (no API key needed)
- ffmpeg/ffprobe for video frame extraction (Instagram video fallback)

## Required env vars (in `.env`)
- `OPENROUTER_API_KEY` — for LLM and embedding calls
- `X_API_BEARER_TOKEN` — for Twitter API v2
- `DATABASE_URL` or `DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME` — PostgreSQL connection

## How to run
```bash
cd stackmark-BE

# Ingest a tweet
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"

# Ingest an Instagram post or reel
uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
uv run -m instagram_pipeline "https://www.instagram.com/user/reel/SHORTCODE/"

# Semantic search
uv run -m retrieval.search "your query" --top 5
```

## Project structure
```
stackmark-BE/
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
│   ├── __main__.py         # CLI entry point
│   └── downloads/          # Downloaded media (gitignored)
└── retrieval/              # Semantic search layer
    ├── search.py           # generate_query_embedding() + search()
    └── __main__.py         # CLI entry point
```

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
3. Download media to `instagram_pipeline/downloads/`
4. Enrich with Gemini:
   - **Photo/Carousel**: base64-encode images, send as multiple `image_url` blocks + caption
   - **Video/Reel**: try base64 full video → fallback to ffmpeg frame extraction
5. Generate embedding vector via OpenRouter
6. Store in PostgreSQL via `db.operations.insert_embedding(source="instagram", ...)`

## Key design decisions
- No video downloading for x_pipeline — video tweets are triaged from text + preview + replies
- Instagram pipeline downloads media and base64-encodes it for direct LLM analysis
- FFmpeg frame extraction as fallback when base64 video fails (size limits, API errors)
- Single LLM model (`gemini-2.5-flash-lite`) for all enrichment — chosen for cost
- Anti-hallucination rules in prompts: model must only use info explicitly present in provided content
- All LLM calls go through OpenRouter's OpenAI-compatible API via a single shared client
- Same embedding model + dimensions used for both ingestion and retrieval to ensure consistency
