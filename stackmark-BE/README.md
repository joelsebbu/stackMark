# StackMark — Ingestion Pipeline Prototype

Barebone prototype of the StackMark ingestion pipeline.
Takes social media URLs → fetches content → analyzes with Gemini → generates search-optimized descriptions and embeddings.

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

# 5. Run it (uv handles venv + deps automatically)
uv run -m x_pipeline.pipeline "https://x.com/someone/status/123456"
uv run -m instagram_pipeline "https://www.instagram.com/p/SHORTCODE/"
uv run -m instagram_pipeline "https://www.instagram.com/user/reel/SHORTCODE/"
uv run -m youtube_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
uv run -m web_pipeline "https://example.com/article"

# 6. Semantic search over stored bookmarks
uv run -m retrieval.search "your query" --top 5
```

That's it. `uv run` will:
- Create a `.venv` virtual environment
- Install dependencies (openai, requests, instaloader, yt-dlp, beautifulsoup4, playwright, python-dotenv)
- Run the pipeline

## What it does

### X/Twitter pipeline
```
Tweet URL → Classify → Fetch (Twitter API v2) → Analyze (Gemini) → Detect quote tweet → Merge quoted content → Generate embedding → Store in DB
```

For video tweets, the pipeline triages with the tweet text + preview frame + top replies. If the model can produce a confident description from that context alone, it does. Otherwise, the tweet is flagged with `needs_video_review: true` for later processing.

### Instagram pipeline
```
Instagram URL → Extract shortcode → Fetch (instaloader) → Download media → Analyze (Gemini) → Generate embedding → Store in DB
```

For video reels, the pipeline sends the full video as base64 to Gemini. If that fails (size limits, API errors), it falls back to extracting frames with ffmpeg and sending them as multiple images.

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
│   ├── prompts.py           # Enrichment prompt for Instagram
│   └── downloads/           # Downloaded media
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
