"""HTTP boundary for Course Compass. Run: uvicorn Code.main:app --host 127.0.0.1 --port 8000"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .course_core import DEPARTMENTS, document_path, get_assistant

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
    review: dict[str, Any] | None = None
    verdict: str | None = None
    verdict_text: str | None = None
    searched_terms: list[str] = []
    question_language: str | None = None
    second_look: bool = False
    usage: dict[str, Any] | None = None
    model: str | None = None
    cached: bool = False


class CompareRequest(BaseModel):
    question: str = Field(min_length=4, max_length=800)
    departments: list[Department] | None = None


class CompareResponse(BaseModel):
    question: str
    results: list[QueryResponse]
    summary: str | None = None
    answered: list[str]


app = FastAPI(title="Course Compass — AI University Course Assistant", version="4.0.0")


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
        "review_model": assistant.review_model if assistant.second_reader else None,
        "ai_available": assistant.ai_available,
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


@app.post("/compare", response_model=CompareResponse)
def compare(request: CompareRequest):
    try:
        return get_assistant().compare(request.question, request.departments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Course assistant unavailable") from exc


@app.get("/page")
def page_image(department: Department, document: str = Query(max_length=200),
         page: int = Query(ge=1, le=150), highlight: str = Query("", max_length=600),
               crop: bool = False):
    """PNG of a cited PDF page with the supporting sentence highlighted."""
    from .page_view import render_page
    try:
        path = document_path(department, document)
        return Response(render_page(path, page, highlight, crop=crop), media_type="image/png")
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=404, detail="Page not available") from exc
