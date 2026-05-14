from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
from synthesis import get_qa_chain
app = FastAPI(
    title="University RAG Chatbot",
    version="1.0")
DepartmentType = Literal[
    "AIandCybersecurity",
    "Business",
    "English",
    "Informatics"
]
class QueryRequest(BaseModel):
    question: str
    department: DepartmentType
class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    department: str
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "University RAG Chatbot"}
@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    try:
        chain = get_qa_chain(request.department)

        response = chain.invoke({
            "query": request.question
        })

        sources = list({
            doc.metadata.get("source_file", "unknown")
            for doc in response["source_documents"]
        })

        return QueryResponse(
            answer=response["result"],
            sources=sources,
            department=request.department
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))