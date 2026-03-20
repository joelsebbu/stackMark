# StackMark — Ingestion Pipeline

## Overview

When a user saves a link to StackMark (via paste or mobile share sheet), the ingestion pipeline processes it into a searchable bookmark. The goal: turn any URL into a rich, AI-described entry that can be found later through natural language search.

## Pipeline Flow

```
URL in → Classify → Scrape → AI Describe → Embed → Store
```

---

## Step 1: Receive & Queue

The URL is saved immediately to the database with status `processing`. The user sees the bookmark right away with a loading indicator. The pipeline runs asynchronously in the background.

## Step 2: Source Classification

Simple URL pattern matching to determine the content source:

| Pattern                        | Source    |
| ------------------------------ | --------- |
| `x.com/*/status/*`            | X/Twitter |
| `youtube.com/watch*`          | YouTube   |
| `instagram.com/p/*`           | Instagram |
| `instagram.com/reel/*`        | Instagram |
| Everything else                | Website   |

This determines which scraping strategy to use in the next step.

## Step 3: Content Extraction

Each source has its own extraction strategy to pull raw content (text, images, metadata).

### X / Twitter
- **Method:** X API v2 or fallback scraper
- **Extracts:** Tweet text, media URLs (images/video thumbnails), author handle, timestamp
- **Notes:** If tweet contains images, those URLs are passed to the AI step for vision analysis

### YouTube
- **Method:** YouTube Data API + `youtube-transcript-api`
- **Extracts:** Title, description, thumbnail URL, channel name, transcript (if available)
- **Notes:** Transcript is the most valuable piece — makes the full video content searchable

### Instagram
- **Method:** Scraping service or headless browser (no reliable public API)
- **Extracts:** Caption text, image/video thumbnail, author handle
- **Notes:** Hardest source to extract from. Fallback: store URL + any metadata the user provides manually

### Generic Website
- **Method:** `trafilatura` or `BeautifulSoup` for content extraction
- **Extracts:** Page title, meta description, main body text, Open Graph image
- **Notes:** `trafilatura` handles article extraction well — strips nav, ads, footers automatically

## Step 4: AI Enrichment

All extracted content is sent to an LLM to produce a rich, human-readable description.

**For text-only content** → standard LLM call (e.g., GPT-4o-mini, Claude Haiku)

**For content with images** → vision model call with the image(s) attached

### Prompt Strategy

```
You are processing a saved bookmark. Given the following content
from a {source_type}, produce:

1. A detailed description of what this content is about
2. Key topics and themes
3. Content type (meme, tutorial, article, news, thread, etc.)
4. Mood/tone (funny, informative, emotional, etc.)
5. Notable entities mentioned (people, brands, places, etc.)

Raw content:
{scraped_content}
```

### Example Output

> **Description:** A humorous meme showing a cat dramatically falling off
> a kitchen table while the owner watches in shock. The caption reads
> something relatable about Monday mornings.
>
> **Topics:** cat, meme, pets, humor, relatable, monday
>
> **Content type:** meme
>
> **Mood:** funny, lighthearted
>
> **Entities:** none

## Step 5: Embedding Generation

The AI-generated description from Step 4 is converted into a vector embedding.

**Model options:**
- `text-embedding-3-small` (OpenAI) — cheap, good quality, hosted
- `all-MiniLM-L6-v2` (sentence-transformers) — free, runs locally, slightly lower quality

The resulting vector (e.g., 384 or 1536 dimensions depending on model) is a numerical representation of the content's "meaning." This is what makes semantic search possible.

## Step 6: Store

The bookmark record is updated with all processed data:

| Field           | Description                              |
| --------------- | ---------------------------------------- |
| `url`           | Original URL                             |
| `source`        | x / youtube / instagram / website        |
| `raw_content`   | Scraped text, image URLs                 |
| `ai_description`| LLM-generated rich description           |
| `embedding`     | Vector from Step 5                       |
| `thumbnail`     | Preview image URL (if available)         |
| `status`        | `ready`                                  |
| `created_at`    | Timestamp                                |

Status flips from `processing` → `ready`. The bookmark is now fully searchable.

---

## Search (Query Time)

When the user searches "cat memes":

1. The query string is passed through the same embedding model (Step 5)
2. The resulting vector is compared against all stored bookmark vectors
3. The vector DB returns the top-N closest matches (cosine similarity)
4. Results are ranked and displayed with thumbnails and descriptions

---

## Cost Estimate (5–10 bookmarks/day)

| Component             | Cost per bookmark | Daily (10/day) | Monthly |
| --------------------- | ----------------- | -------------- | ------- |
| LLM enrichment        | ~$0.002           | ~$0.02         | ~$0.60  |
| Vision model (images) | ~$0.005           | ~$0.05         | ~$1.50  |
| Embedding generation  | ~$0.0001          | ~$0.001        | ~$0.03  |
| **Total**             |                   |                | **~$2** |

---

## Tech Stack (Recommended)

- **Backend:** Python (FastAPI)
- **Database:** PostgreSQL + pgvector extension
- **Scraping:** trafilatura, youtube-transcript-api, source-specific adapters
- **AI:** OpenAI API (or Anthropic) for enrichment + embeddings
- **Queue:** Simple background task runner (Celery, or even just asyncio for this scale)
