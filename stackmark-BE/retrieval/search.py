"""Semantic search over stored embeddings.

Usage:
    uv run -m retrieval.search "vulnerability hacking"
    uv run -m retrieval.search "funny meme about programming" --top 5
"""

import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from db.session import SessionLocal
from db.models.embedding import Embedding
from retrieval.constants import OPENROUTER_BASE_URL, RERANK_MODEL, RERANK_POOL
from x_pipeline.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

_openrouter_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
    return _openrouter_client


def generate_query_embedding(query: str) -> list[float]:
    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Use an LLM to re-rank search candidates by relevance to the query."""
    if not candidates:
        return candidates

    numbered = "\n".join(
        f"{i}. [similarity: {c['similarity']}] heading: {c['heading'] or '(none)'} | brief: {c['brief'] or '(none)'}"
        for i, c in enumerate(candidates)
    )

    prompt = (
        "You are a search result re-ranker. Given a user query and a numbered list of "
        "search candidates (each with a vector similarity score, heading, and brief), "
        "re-order them by relevance to the query.\n\n"
        "Rules:\n"
        "- Consider BOTH semantic relevance to the query AND the vector similarity score.\n"
        "- Respect high similarity scores — don't completely discard them. But if you're "
        "confident a lower-similarity result is clearly more relevant to the query, you "
        "may rank it higher.\n"
        f"- Return a JSON array of the top {top_k} candidate indices (0-based) in order "
        "from most relevant to least relevant.\n"
        "- Return ONLY the JSON array, no other text.\n\n"
        f"Query: \"{query}\"\n\n"
        f"Candidates:\n{numbered}"
    )

    original_order = [c['heading'] or c['url'] for c in candidates]
    print(f"[rerank] query: \"{query}\"")
    print(f"[rerank] {len(candidates)} candidates in, returning top {top_k}")
    print(f"[rerank] vector order: {original_order}")

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content or ""
        cleaned = raw.strip().strip("`").lstrip("json").strip()
        ranked_indices = json.loads(cleaned)
        print(f"[rerank] LLM returned indices: {ranked_indices}")

        if not isinstance(ranked_indices, list):
            print("[rerank] LLM response was not a list, falling back to vector order")
            return candidates[:top_k]

        reranked = []
        seen = set()
        for idx in ranked_indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                reranked.append(candidates[idx])
                seen.add(idx)
            if len(reranked) >= top_k:
                break

        # Fill remaining slots if LLM returned fewer than top_k valid indices
        if len(reranked) < top_k:
            for c in candidates:
                if c not in reranked:
                    reranked.append(c)
                if len(reranked) >= top_k:
                    break

        reranked_order = [c['heading'] or c['url'] for c in reranked]
        print(f"[rerank] final order: {reranked_order}")
        return reranked
    except Exception as e:
        print(f"[rerank] FAILED ({e}), falling back to vector order")
        return candidates[:top_k]


def search(query: str, top_k: int = 5) -> list[dict]:
    query_vector = generate_query_embedding(query)
    fetch_count = max(top_k, RERANK_POOL)

    with SessionLocal() as session:
        results = (
            session.query(
                Embedding.uuid,
                Embedding.source,
                Embedding.url,
                Embedding.heading,
                Embedding.brief,
                Embedding.created_at,
                Embedding.embedding.cosine_distance(query_vector).label("distance"),
            )
            .filter(Embedding.embedding.isnot(None))
            .order_by("distance")
            .limit(fetch_count)
            .all()
        )

    candidates = [
        {
            "uuid": str(r.uuid),
            "source": r.source,
            "url": r.url,
            "heading": r.heading,
            "brief": r.brief,
            "created_at": r.created_at.isoformat(),
            "similarity": round(1 - r.distance, 4),
        }
        for r in results
    ]

    return rerank(query, candidates, top_k)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run -m retrieval.search \"your query\" [--top N]")
        sys.exit(1)

    top_k = 3
    args = sys.argv[1:]

    if "--top" in args:
        idx = args.index("--top")
        top_k = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    query = " ".join(args)
    print(f"Searching for: \"{query}\" (top {top_k})\n")

    results = search(query, top_k)

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['similarity']}] {r['url']}")
        print(f"   source: {r['source']} | created: {r['created_at']}")
        print()


if __name__ == "__main__":
    main()
