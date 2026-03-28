# web_pipeline — Web Page Ingestion Module

## Files
- `pipeline.py` — Main orchestration: `run_pipeline()` is the entry point, `enrich_page()` handles LLM analysis
- `fetcher.py` — Page fetch (`fetch_page`) via httpx with Playwright fallback, metadata extraction (`extract_metadata`) via BeautifulSoup
- `messages.py` — `build_web_page_messages()` for text-only LLM payloads
- `llm.py` — OpenRouter client (`get_openrouter_client`), `call_llm()`, `generate_embedding()`
- `constants.py` — `WEB_PIPELINE_MODEL`, embedding config, content length limits
- `prompts.py` — `ENRICHMENT_PROMPT` adapted for web pages
- `__main__.py` — CLI entry point: `uv run -m web_pipeline "https://example.com"`

## Architecture
All imports are relative (`from .constants import ...`). Package entry point: `web_pipeline.pipeline:main`.

Single OpenRouter client in `llm.py` shared for both LLM and embedding calls. Same lazy singleton pattern as other pipelines. Timeout set to 60s.

Page fetching uses Playwright (headless Chromium) to render JS-heavy pages. BeautifulSoup extracts metadata and main text content.

## Enrichment flow in `enrich_page()`
```
fetch page via httpx (fast, lightweight)
  ├─ If enough content (≥200 chars): use HTTP response
  └─ Fallback: re-fetch via Playwright headless Chromium (JS rendering)
→ extract metadata (title, OG tags, meta description) + main text via BeautifulSoup
→ send text-only payload to Gemini for enrichment
```

## Pipeline flow
1. Fetch page via httpx (Playwright fallback for JS-heavy sites)
2. Extract metadata + main text content via BeautifulSoup
3. Enrich with Gemini (text-only — no images sent)
4. Generate embedding via OpenRouter (same model + dimensions as other pipelines)
5. Store in PostgreSQL via `db.operations.insert_embedding(source="web", ...)`

## Key design decisions
- httpx first (fast, Lambda-friendly), Playwright fallback only when body is too short (<200 chars)
- Text-only enrichment — og:image URL included as metadata text, not sent as image
- 100k char content cap — safety net for extremely large pages, Gemini has 1M token context
- Strips nav/footer/header/aside/script/style elements before text extraction
- Prefers `<main>` or `<article>` elements over full `<body>` for cleaner content
