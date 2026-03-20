# StackMark — Tags as a Complement to Vector Search

## The Idea

During the AI enrichment step of the ingestion pipeline, the LLM already generates a rich description of each bookmark. We can extend the prompt to also produce 5-10 short tags per bookmark — essentially free since the LLM call is already happening.

## Why Tags Don't Replace Vector Search

The embedding vector already captures the full semantic meaning of the AI description. If the description mentions "Ferrari," "F1," and "Leclerc," the vector already encodes that. Adding tags doesn't make vector search any better.

Tags serve a different purpose entirely.

## What Tags Are Good For

### 1. Exact Filtering (No Search Query Needed)
Browse all bookmarks with a specific tag without typing a search.
```sql
SELECT * FROM bookmarks WHERE 'F1' = ANY(tags);
```

### 2. Browsing & Discovery
Display a tag cloud or sidebar showing what's in the collection:
- "47 bookmarks tagged F1"
- "23 tagged memes"
- "12 tagged Python"

Useful for exploring when you don't know what to search for.

### 3. Combined with Vector Search (Filtered Semantic Search)
Search "funny behind the scenes" but only within F1 content:
```sql
SELECT url, ai_description, thumbnail,
       embedding <=> $query_embedding AS distance
FROM bookmarks
WHERE 'F1' = ANY(tags) AND status = 'ready'
ORDER BY distance ASC
LIMIT 10;
```

This narrows the vector search to a subset, giving tighter results.

## How Tags Get Generated

Part of the existing AI enrichment prompt during ingestion. Just extend the prompt to include:

```
Also produce 5-10 short, lowercase tags for this content.
Tags should cover: topic, people/entities, content type, mood, platform-specific context.
```

### Example

For a funny Ferrari pit crew video from X:

```json
{
  "tags": ["f1", "ferrari", "leclerc", "pit stop", "motorsport", "humor", "behind the scenes", "team culture"]
}
```

## Storage

Tags live as a Postgres array column on the same bookmarks table:

| Field           | Type              |
| --------------- | ----------------- |
| `tags`          | `TEXT[]`          |

Index with GIN for fast lookups:
```sql
CREATE INDEX idx_bookmarks_tags ON bookmarks USING GIN(tags);
```

## Summary

- **Vector search** handles fuzzy, natural language queries ("that funny F1 video")
- **Tags** handle exact filtering and browsing ("show me all F1 content")
- **Together** they cover both use cases
- **Cost:** Zero extra — generated in the same LLM call that produces the description