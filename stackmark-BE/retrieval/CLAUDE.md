# retrieval — Semantic Search + LLM Re-ranking Module

## Files
- `search.py` — Main search logic: `generate_query_embedding()`, `search()`, `rerank()`
- `constants.py` — `RERANK_MODEL`, `RERANK_POOL` config, re-exports `OPENROUTER_BASE_URL`
- `__main__.py` — CLI entry point: `uv run -m retrieval.search "your query" --top 5`

## Architecture
Uses a single lazy-initialized OpenRouter client (`_get_client()`) shared for both embedding and LLM re-ranking calls. Embedding config (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`) imported from `x_pipeline.constants`. Re-ranking config lives in `retrieval/constants.py`.

## Search flow
1. Embed the user's query using `qwen/qwen3-embedding-8b` (same model/dimensions as ingestion)
2. Cosine similarity search via pgvector HNSW index — fetches `max(top_k, RERANK_POOL)` candidates (at least 10)
3. LLM re-ranking via `rerank()`:
   - Sends the query + numbered candidate list (heading, brief, similarity score) to `gemini-2.5-flash-lite`
   - LLM returns a JSON array of candidate indices ordered by relevance
   - Results are reordered accordingly, trimmed to `top_k` (default 5)
4. Graceful fallback: if the LLM call fails (timeout, parse error, etc.), returns original vector-ordered results

## Re-ranking prompt design
- LLM receives both semantic context (heading + brief) and the vector similarity score for each candidate
- Instructed to honor high similarity scores but free to reorder when it's confident a lower-similarity result is clearly more relevant
- Returns only a JSON array of 0-based indices — minimal output for fast, cheap calls

## Key design decisions
- Over-fetch then trim: fetch 10 candidates from pgvector, re-rank, return top 5 — gives the LLM a wider pool to pick from
- Same model as ingestion pipelines (`gemini-2.5-flash-lite`) — cheap and fast
- Fallback-safe: search never fails due to re-ranking issues, silently degrades to vector order
