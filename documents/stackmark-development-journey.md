# StackMark — Ingestion Pipeline Development Journey

**Prototype Phase — March 2026**

---

## 1. Project Overview

StackMark is a single-user personal bookmark manager designed to be a universal inbox for content saved from X (Twitter), Instagram, YouTube, and websites. The core differentiator is semantic search — instead of relying on tags or folders, users type natural language queries like "cat memes" or "that Python web framework" and the system surfaces relevant bookmarks regardless of their source.

The ingestion pipeline is the heart of the system. It takes any saved URL, extracts its content, generates an AI-powered description optimized for vector embeddings, and stores it for later retrieval via cosine similarity search.

---

## 2. Tech Stack Decisions

Every technology choice was made deliberately, balancing simplicity, cost, and capability for a personal-scale application.

| Decision | Reasoning |
|----------|-----------|
| **Python (FastAPI)** for backend | Primary language expertise, FastAPI is lightweight and async-friendly |
| **React** for frontend | Primary frontend framework experience |
| **PostgreSQL + pgvector** for storage | Single database handles both relational data and vector search |
| **xAI Grok API** for AI | Had $5 preloaded credits, native X/Twitter integration via x_search |
| **xai-sdk** (not OpenAI SDK) | xAI has its own native SDK — using the proper SDK instead of the OpenAI-compatible wrapper |
| **uv** for project management | Fast, handles venv + deps in one tool, no manual pip install or activation |
| **python-dotenv** for env vars | Auto-loads `.env` file so no need to `export` keys in the terminal |

---

## 3. Pipeline Design — The Original Plan

The pipeline doc defined a 6-step flow:

```
URL in → Classify → Scrape → AI Describe → Embed → Store
```

For the prototype, we scoped it down to just the core loop with console output — no database, no embeddings, no web server. The goal was to see the AI description quality before building anything else.

---

## 4. Development Iterations

### Iteration 1: Two-Step Pipeline (Cheap Model)

**Approach:** Separate the tweet fetching and description generation into two distinct Grok calls.

- Step 1: Use `x_search` to fetch raw tweet content
- Step 2: Send that text to a second Grok call with an enrichment prompt to produce a structured JSON description

**Model:** `grok-4-1-fast-non-reasoning`

**Result:** Worked for text-only tweets. But for media-heavy tweets (videos, image memes), the description was generic and missed the actual content entirely. The model would hallucinate context from the account handle name (e.g., inferring "2049-era memes" from `@shitpost_2049`).

**Problem identified:** The two-step approach loses visual context. Even with `enable_image_understanding` and `enable_video_understanding` enabled, the first call analyzes the media but only passes back text to the second call. By the time we ask for the description, the video/image context is gone.

---

### Iteration 2: Single Combined Call

**Approach:** Collapse fetch + describe into one Grok call. Send the tweet URL and the enrichment prompt together, so Grok sees the media and writes the description in a single pass.

**Model:** `grok-4.20-beta-latest-non-reasoning` (with `enable_image_understanding=True` and `enable_video_understanding=True`)

**Result:** Significantly better. For a video meme tweet, the model actually watched the video and described two people in a casual setting with exaggerated reactions. It correctly identified it as humor/banter content.

**Remaining gap:** The specific joke (Po from Kung Fu Panda shuffling scrolls, caption about "confusing the nurse with asian babies") was still missed. The model described the *surface* of the video but not the embedded caption/meme content. Text overlays baked into video frames are still unreliable for automated analysis.

**Key learning:** For meme/shitpost content where the joke lives inside the media (text overlays, visual references), automated description will likely need a manual note field as a fallback.

---

### Iteration 3: Smart Model Routing

**Problem:** The rich model (`grok-4.20-beta-latest-non-reasoning`) with media analysis is expensive. Using it for every bookmark — including simple text tweets — wastes money.

**Approach:** Always start with the cheap model. If the description is thin and the tweet has media, escalate to the expensive model.

**How we detect "thin":** Instead of brittle heuristic word-matching, we added a `confidence` field to the JSON output. The model self-reports `"high"` or `"low"` based on whether it could actually analyze the content vs. just describing metadata. The routing logic:

```
if confidence == "low" AND has_media == true → re-run with rich model
if confidence == "low" AND has_media == false → keep as-is (text is just thin)
if confidence == "high" → keep (cheap model was sufficient)
```

**CLI flag:** Added `--rich` flag to force the expensive model when the user knows the content needs it.

```bash
# Auto mode
uv run pipeline.py "https://x.com/someone/status/123"

# Force rich model
uv run pipeline.py "https://x.com/someone/status/123" --rich
```

---

## 5. Prompt Engineering

The enrichment prompt went through several iterations:

### V1 — Generic bookmark description
Asked for "a detailed description of what this content is about" plus topics, content type, mood, and entities. Produced fluffy, editorial descriptions with filler like "perfect for saving" and "lightens up feeds in tech circles."

### V2 — Search-optimized with specificity rules
Added explicit rules: "Be SPECIFIC — say 'a Python library for building REST APIs called FastAPI' not 'a programming library'." Also added domain identification and "why someone saved this." Better, but still missed media content.

### V3 — Media-aware with confidence
Added instructions to "ACTUALLY WATCH any video and LOOK AT any images." Added `has_media`, `media_type`, and `confidence` fields. Told the model to say `"low"` confidence if it's mostly describing metadata rather than actual content. This is the current version.

---

## 6. Key Architectural Decisions

### Single call vs. two calls for media tweets
**Decision:** Single combined call.
**Why:** Grok's x_search with video/image understanding runs server-side. The visual analysis only exists during that call — it can't be passed to a subsequent call as text without losing information.

### Confidence-based escalation vs. heuristic
**Decision:** Model self-reported confidence.
**Why:** A heuristic (checking for filler words, description length, topic count) is brittle — a long description can still say nothing useful. The model knows when it's guessing, so asking it to self-assess is more reliable.

### Cheap-first routing vs. always-rich
**Decision:** Cheap first, escalate if needed.
**Why:** Most bookmarks are text tweets, articles, and links where the cheap model is sufficient. The rich model with media analysis is reserved for the ~20-30% of content that actually has meaningful visual content the cheap model can't see.

---

## 7. Current Limitations

| Limitation | Impact | Possible Fix |
|-----------|--------|-------------|
| Video text overlays not reliably OCR'd | Memes with baked-in captions get described at surface level only | Optional manual note field at save time |
| Only X/Twitter supported | Instagram, YouTube, websites not yet implemented | Source-specific adapters in the pipeline doc |
| No embeddings or storage | Descriptions print to console only | Next phase: sentence-transformers or xAI embeddings + pgvector |
| No search | Can't query saved bookmarks yet | Next phase: embedding similarity search |
| Confidence self-report may be inconsistent | Model might say "high" when it shouldn't | Could add a secondary check or human review flag |

---

## 8. Cost Profile

| Component | Model | Cost per bookmark |
|-----------|-------|-------------------|
| Text-only tweets | `grok-4-1-fast-non-reasoning` | ~$0.001 |
| Media tweets (auto-escalated) | `grok-4.20-beta-latest-non-reasoning` + x_search + media | ~$0.01 |
| x_search tool call | Per invocation | $0.005 |

At 5-10 bookmarks/day with ~70% text-only, estimated monthly cost: **~$1-2**.

---

## 9. What's Next

The prototype proved the core concept works: take a URL, generate a rich AI description, and produce structured output ready for embedding. Next steps:

1. **Embedding generation** — convert descriptions to vectors (sentence-transformers locally or xAI embedding API)
2. **PostgreSQL + pgvector storage** — persist bookmarks with their embeddings
3. **Semantic search** — query interface that embeds the search query and finds nearest neighbors
4. **FastAPI backend** — wrap the pipeline in an API with endpoints for saving and searching
5. **Additional sources** — YouTube (transcript extraction), Instagram (scraping), generic websites (trafilatura)
6. **Optional manual notes** — fallback field for when automated description misses the point
7. **React frontend** — simple UI for pasting URLs and searching bookmarks
