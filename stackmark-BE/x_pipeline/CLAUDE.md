# x_pipeline — X/Twitter Ingestion Module

## Files
- `pipeline.py` — Main orchestration: `run_pipeline()` is the entry point, `enrich_tweet()` handles the branching logic
- `constants.py` — `X_PIPELINE_MODEL`, embedding config, API URLs, URL patterns, content type/mood options
- `prompts.py` — Two prompts: `ENRICHMENT_PROMPT` (text/images) and `VIDEO_TRIAGE_PROMPT` (video tweets)
- `utils.py` — `clean_response_json_text()`, `as_list()`, `dedupe()`, `pick_media_type()`
- `tweets.csv` — Sample tweet data for testing

## Architecture
All imports are relative (`from .constants import ...`). Package entry point: `x_pipeline.pipeline:main`.

Single OpenRouter client (`_get_openrouter_client()`) shared for both LLM and embedding calls.

## Enrichment branching in `enrich_tweet()`
```
extract_media(tweet_data)
  ├─ has video/gif? → VIDEO TRIAGE PATH
  │    ├─ fetch_replies() for context
  │    ├─ send text + preview frame + replies to Gemini with VIDEO_TRIAGE_PROMPT
  │    ├─ model confident? → return enrichment JSON
  │    └─ model not confident? → return {needs_video_review: true}
  └─ no video? → STANDARD PATH
       └─ send text + images to Gemini with ENRICHMENT_PROMPT → return enrichment JSON
```

## Twitter API functions
- `fetch_tweet(tweet_id)` — GET `/tweets/{id}` with media expansions
- `fetch_replies(tweet_id)` — GET `/tweets/search/recent` with `conversation_id:{id} is:reply`
- `extract_media(tweet_data)` — Parses `includes.media` into typed items (photo/video/animated_gif)
- `detect_quoted_tweet_with_x_api()` — Checks `referenced_tweets` for `type: "quoted"`

## Database integration
`run_pipeline()` calls `db.operations.insert_embedding()` at the end to store source, URL, and embedding vector in PostgreSQL. The embedding is also used by `retrieval/` for semantic search.

## Prompt rules
Both prompts have anti-hallucination rules: model must ONLY use information explicitly present in the provided content. No facts, prices, or details from training data.

## Output schema
```json
{
  "description": "dense keyword-rich text for vector search",
  "tags": ["5-10 lowercase tags"],
  "content_type": "meme|tutorial|article|...",
  "mood": ["funny", "technical"],
  "entities": ["proper nouns"],
  "has_media": true,
  "media_type": "none|image|video|gif",
  "media_confidence": "high|low"
}
```
