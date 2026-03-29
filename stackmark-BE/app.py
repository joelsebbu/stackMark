"""FastAPI application for StackMark."""

import concurrent.futures

from fastapi import FastAPI
from pydantic import BaseModel

from router import ingest
from retrieval.search import search
from errors import PipelineError

app = FastAPI(title="StackMark", version="0.1.0")

INGEST_TIMEOUT = 300  # 5 minutes
SEARCH_TIMEOUT = 30   # 30 seconds

_executor = concurrent.futures.ThreadPoolExecutor()


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


def _run_with_timeout(fn, timeout, *args):
    future = _executor.submit(fn, *args)
    return future.result(timeout=timeout)


@app.post("/ingest")
def ingest_url(req: IngestRequest):
    try:
        result = _run_with_timeout(ingest, INGEST_TIMEOUT, req.url)
        result.pop("embedding", None)
        return success(result)
    except concurrent.futures.TimeoutError:
        return error(f"Ingestion timed out after {INGEST_TIMEOUT}s.")
    except PipelineError as e:
        return error(str(e))
    except Exception as e:
        return error(str(e))


@app.post("/search")
def search_bookmarks(req: SearchRequest):
    try:
        results = _run_with_timeout(search, SEARCH_TIMEOUT, req.query, req.top_k)
        return success(results)
    except concurrent.futures.TimeoutError:
        return error(f"Search timed out after {SEARCH_TIMEOUT}s.")
    except Exception as e:
        return error(str(e))
