"""FastAPI application for StackMark."""

import concurrent.futures
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from auth.dependencies import get_current_user
from auth.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from db.models.refresh_token import RefreshToken
from db.models.user import User
from db.session import SessionLocal
from errors import PipelineError
from retrieval.search import search
from router import ingest

app = FastAPI(title="StackMark", version="0.1.0")

_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:4321").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    top_k: int = 5


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def success(data):
    return {"success": True, "error": None, "data": data}


def error(message: str):
    return {"success": False, "error": message, "data": None}


def _run_with_timeout(fn, timeout, *args):
    future = _executor.submit(fn, *args)
    return future.result(timeout=timeout)


@app.post("/login")
def login(req: LoginRequest):
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.username == req.username)
        ).scalar_one_or_none()

    if user is None or not verify_password(req.password, user.password):
        return error("Invalid username or password.")

    user_id = str(user.uuid)
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    with SessionLocal() as session:
        session.query(RefreshToken).filter(
            RefreshToken.user_id == user.uuid
        ).delete()
        session.add(RefreshToken(user_id=user.uuid, token=refresh_token))
        session.commit()

    return success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    })


@app.post("/refresh")
def refresh(req: RefreshRequest):
    payload = verify_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return error("Invalid refresh token.")

    with SessionLocal() as session:
        stored = session.execute(
            select(RefreshToken).where(RefreshToken.token == req.refresh_token)
        ).scalar_one_or_none()

    if stored is None:
        return error("Refresh token has been revoked.")

    access_token = create_access_token(payload["sub"])
    return success({
        "access_token": access_token,
        "token_type": "bearer",
    })


@app.post("/ingest")
def ingest_url(req: IngestRequest, _user: User = Depends(get_current_user)):
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
def search_bookmarks(req: SearchRequest, _user: User = Depends(get_current_user)):
    try:
        results = _run_with_timeout(search, SEARCH_TIMEOUT, req.query, req.top_k)
        return success(results)
    except concurrent.futures.TimeoutError:
        return error(f"Search timed out after {SEARCH_TIMEOUT}s.")
    except Exception as e:
        return error(str(e))
