"""HTTP boundary for University Course Assistant. Run: uvicorn Code.main:app."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

try:
    from .course_core import DEPARTMENTS, get_assistant
except ImportError:  # backward-compatible uvicorn main:app from /Code
    from course_core import DEPARTMENTS, get_assistant


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


app = FastAPI(title="AI University Course Assistant", version="2.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "university-course-assistant"}


@app.get("/departments")
def departments():
    return [{"id": k, "name": v} for k, v in DEPARTMENTS.items()]


@app.post("/ask", response_model=QueryResponse)
def ask(request: QueryRequest):
    try:
        return get_assistant().ask(request.question, request.department)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Do not leak API keys, filesystem paths, or document contents to callers.
        raise HTTPException(status_code=503, detail="Course assistant unavailable") from exc
