# youtube_pipeline — YouTube Ingestion Module

## Files
- `pipeline.py` — Main orchestration: `run_pipeline()` is the entry point, `enrich_video()` handles LLM analysis
- `fetcher.py` — URL parsing (`extract_video_id`), metadata fetch (`fetch_metadata`) via yt-dlp
- `messages.py` — `build_video_url_messages()`, `build_metadata_only_messages()`
- `llm.py` — OpenRouter client (`get_openrouter_client`), `call_llm()`, `generate_embedding()`
- `constants.py` — `YT_PIPELINE_MODEL`, embedding config, URL patterns
- `prompts.py` — `ENRICHMENT_PROMPT` adapted for YouTube videos
- `__main__.py` — CLI entry point: `uv run -m youtube_pipeline "https://youtube.com/..."`

## Architecture
All imports are relative (`from .constants import ...`). Package entry point: `youtube_pipeline.pipeline:main`.

Single OpenRouter client in `llm.py` shared for both LLM and embedding calls. Same lazy singleton pattern as instagram_pipeline and x_pipeline. Timeout set to 300s for video analysis.

Metadata fetching uses `yt-dlp` (no API key needed). No video downloading — YouTube URL is passed directly to Gemini for analysis.

## Enrichment flow in `enrich_video()`
```
fetch metadata via yt-dlp (title, description, channel, tags)
  ├─ Try: pass YouTube URL directly to Gemini for video analysis
  └─ Fallback: metadata-only analysis (title + description + channel + tags)
```

## Pipeline flow
1. Parse URL → extract video ID via regex (watch, youtu.be, shorts)
2. Fetch video metadata via yt-dlp (title, description, channel, duration, tags)
3. Enrich with Gemini (direct YouTube URL analysis, fallback to metadata-only)
4. Generate embedding via OpenRouter (same model + dimensions as other pipelines)
5. Store in PostgreSQL via `db.operations.insert_embedding(source="youtube", ...)`

## Database integration
Reuses `db.operations.insert_embedding()` with `source: "youtube"`. Same Embedding model, same 1024-dimension vectors. Retrieval layer works automatically.

## Key design decisions
- No video downloading — Gemini analyzes YouTube videos directly by URL
- yt-dlp used only for metadata fetching (no API key required)
- Metadata (title, description, channel, tags) sent alongside URL to give Gemini extra context
- Fallback to metadata-only analysis if Gemini URL analysis fails
- Entities capped at 5-15, deduplicated, central to video topic only
- 5-minute HTTP timeout on OpenRouter client for long video analysis
