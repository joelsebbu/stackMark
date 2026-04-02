"""Semantic search over stored embeddings.

Usage:
    uv run -m retrieval.search "vulnerability hacking"
    uv run -m retrieval.search "funny meme about programming" --top 5
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from db.session import SessionLocal
from db.models.embedding import Embedding
from x_pipeline.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, OPENROUTER_BASE_URL

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def generate_query_embedding(query: str) -> list[float]:
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


def search(query: str, top_k: int = 3) -> list[dict]:
    query_vector = generate_query_embedding(query)

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
            .limit(top_k)
            .all()
        )

    return [
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
