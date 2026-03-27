# instagram_pipeline — Instagram Ingestion Module

## Files
- `pipeline.py` — Main orchestration: `run_pipeline()` is the entry point, `enrich_post()` handles branching logic
- `constants.py` — `IG_PIPELINE_MODEL`, embedding config, URL pattern, frame extraction settings
- `prompts.py` — `ENRICHMENT_PROMPT` adapted for Instagram posts/reels
- `__main__.py` — CLI entry point: `uv run -m instagram_pipeline "https://instagram.com/..."`
- `trial.py` — Standalone script for fetching post metadata + downloading media
- `video_trial.py` — Standalone trial for base64 video → Gemini
- `video_frames_trial.py` — Standalone trial for ffmpeg frame extraction → Gemini

## Architecture
All imports are relative (`from .constants import ...`). Package entry point: `instagram_pipeline.pipeline:main`.

Single OpenRouter client (`_get_openrouter_client()`) shared for both LLM and embedding calls. Same pattern as x_pipeline.

Data fetching uses `instaloader` (no API key needed for public posts). Media is downloaded to a temp directory and base64-encoded before sending to the LLM.

## Enrichment branching in `enrich_post()`
```
fetch post via instaloader
  ├─ Photo / Carousel (no video)?
  │    ├─ download image(s)
  │    ├─ base64-encode each image
  │    └─ send as multiple image_url blocks + caption → ENRICHMENT_PROMPT
  └─ Video (Reel / video post)?
       ├─ Try: download video, base64-encode, send as video_url
       └─ Fallback: extract frames via ffmpeg, send as multiple image_url blocks
```

## Pipeline flow
1. Parse URL → extract shortcode via regex
2. Fetch post metadata via instaloader (caption, owner, hashtags, media URLs)
3. Download media to temp directory
4. Enrich with Gemini (branching by post type)
5. Generate embedding via OpenRouter (same model + dimensions as x_pipeline)
6. Store in PostgreSQL via `db.operations.insert_embedding(source="instagram", ...)`

## Database integration
Reuses `db.operations.insert_embedding()` with `source: "instagram"`. Same Embedding model, same 1024-dimension vectors. Retrieval layer works automatically.

## Key design decisions
- instaloader for data fetching — no API key required for public posts
- Video sent as base64 to Gemini (works for typical reel sizes ~5-15 MB)
- FFmpeg frame extraction as fallback if base64 video fails (API error, size limits)
- Carousel posts send all images in a single LLM call as multiple image_url blocks
- No quote tweet equivalent — Instagram doesn't have that concept
- Trial scripts kept as standalone for experimentation
