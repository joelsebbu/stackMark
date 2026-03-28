"""FastAPI application for StackMark."""

from fastapi import FastAPI
from pydantic import BaseModel

from router import ingest
from retrieval.search import search
from errors import PipelineError

app = FastAPI(title="StackMark", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


class IngestRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


def success(data):
    return {"success": True, "error": None, "data": data}


def error(message: str):
    return {"success": False, "error": message, "data": None}


@app.post("/ingest")
def ingest_url(req: IngestRequest):
    try:
        result = ingest(req.url)
        result.pop("embedding", None)
        return success(result)
    except PipelineError as e:
        return error(str(e))
    except Exception as e:
        return error(str(e))


@app.post("/search")
def search_bookmarks(req: SearchRequest):
    try:
        results = search(req.query, req.top_k)
        return success(results)
    except Exception as e:
        return error(str(e))
