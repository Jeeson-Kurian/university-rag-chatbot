"""HTTP boundary for Course Compass. Run: uvicorn Code.main:app --host 127.0.0.1 --port 8000"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .course_core import DEPARTMENTS, get_assistant

Department = Literal["AIandCybersecurity", "Business", "English", "Informatics"]


class QueryRequest(BaseModel):
    question: str = Field(min_length=4, max_length=800)
    department: Department


class SourceReference(BaseModel):
    id: str
    document: str
    page: int | None
    department: str
    excerpt: str


class QueryResponse(BaseModel):
    question: str
    department: str
    retrieval_mode: str
    mode: str
    answer: str
    sources: list[SourceReference]
    warning: str | None = None
    grounding: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    model: str | None = None
    cached: bool = False


app = FastAPI(title="Course Compass — AI University Course Assistant", version="3.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "course-compass"}


@app.get("/departments")
def departments():
    return [{"id": k, "name": v} for k, v in DEPARTMENTS.items()]


@app.get("/stats")
def stats():
    """Process-local counters: model calls avoided, tokens spent, cache hits."""
    assistant = get_assistant()
    return {
        "chat_model": assistant.chat_model if assistant.client else None,
        "embedding_model": assistant.embedding_model if assistant.vector_enabled else None,
        "passages": len(assistant.passages),
        "counters": dict(assistant.stats),
    }


@app.post("/ask", response_model=QueryResponse)
def ask(request: QueryRequest):
    try:
        return get_assistant().ask(request.question, request.department)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Do not leak API keys, filesystem paths, or document contents to callers.
        raise HTTPException(status_code=503, detail="Course assistant unavailable") from exc
