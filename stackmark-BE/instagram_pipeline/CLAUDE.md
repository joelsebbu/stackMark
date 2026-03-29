# instagram_pipeline — Instagram Ingestion Module

## Files
- `pipeline.py` — Main orchestration: `run_pipeline()` is the entry point, `enrich_post()` handles branching logic
- `fetcher.py` — URL parsing (`extract_shortcode`), instaloader fetch (`fetch_post`), media download (`download_media`)
- `media.py` — `encode_file_base64()`, `find_files()`, `extract_frames()` (ffmpeg), `get_video_duration()` (ffprobe)
- `messages.py` — `build_photo_messages()`, `build_video_messages()`, `build_frames_messages()`
- `llm.py` — OpenRouter client (`get_openrouter_client`), `call_llm()`, `generate_embedding()`
- `constants.py` — `IG_PIPELINE_MODEL`, embedding config, URL pattern, frame extraction settings
- `prompts.py` — `ENRICHMENT_PROMPT` adapted for Instagram posts/reels
- `__main__.py` — CLI entry point: `uv run -m instagram_pipeline "https://instagram.com/..."`

## Trial scripts (standalone experimentation)
- `trial.py` — Fetch post metadata + download media via instaloader
- `video_trial.py` — Send full base64 video to Gemini
- `video_frames_trial.py` — Extract frames with ffmpeg, send as multiple images

## Architecture
All imports are relative (`from .constants import ...`). Package entry point: `instagram_pipeline.pipeline:main`.

Single OpenRouter client in `llm.py` shared for both LLM and embedding calls. Same lazy singleton pattern as x_pipeline.

Data fetching uses `instaloader` (no API key needed for public posts). Media is downloaded to a temporary directory and base64-encoded before sending to the LLM.

## Error handling
Pipeline errors raise `PipelineError` (from `errors.py`) instead of calling `sys.exit(1)`. This makes the pipeline safe for concurrent use via the FastAPI server. `sys.exit(1)` is only used in the CLI `main()` entry point.

## Media cleanup
Downloaded media is wrapped in a `try/finally` block — `shutil.rmtree()` always runs after processing, whether the pipeline succeeds, fails, or times out. This prevents disk space buildup from accumulated media files.

## Enrichment branching in `enrich_post()`
```
fetch post via instaloader → download to temp dir
  ├─ Photo / Carousel (no video)?
  │    ├─ base64-encode each image
  │    └─ send as multiple image_url blocks + caption → ENRICHMENT_PROMPT
  └─ Video (Reel / video post)?
       ├─ Try: base64-encode full video, send as video_url
       └─ Fallback: extract frames via ffmpeg, send as multiple image_url blocks
```

## Pipeline flow
1. Parse URL → extract shortcode via regex
2. Fetch post metadata via instaloader (caption, owner, hashtags, media URLs)
3. Download media to temporary directory
4. Enrich with Gemini (branching by post type)
5. Generate embedding via OpenRouter (same model + dimensions as x_pipeline)
6. Store in PostgreSQL via `db.operations.insert_embedding(source="instagram", ...)`
7. Clean up downloaded media (always runs via `try/finally`)

## Database integration
Reuses `db.operations.insert_embedding()` with `source: "instagram"`. Same Embedding model, same 1024-dimension vectors. Retrieval layer works automatically.

## Key design decisions
- instaloader for data fetching — no API key required for public posts
- Video sent as base64 to Gemini (works for typical reel sizes ~5-15 MB)
- FFmpeg frame extraction as fallback if base64 video fails (API error, size limits)
- Carousel posts send all images in a single LLM call as multiple image_url blocks
- No quote tweet equivalent — Instagram doesn't have that concept
- Downloaded media is automatically cleaned up after processing (success or failure)
- Trial scripts kept as standalone for experimentation
