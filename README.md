# University RAG Chatbot

A Retrieval-Augmented Generation chatbot for university curriculum documents.

## Features
- PDF/TXT document ingestion
- Department-based metadata filtering
- Chunking and PII cleaning
- OpenAI embeddings with FAISS vector search
- GPT-based answer synthesis
- FastAPI backend
- Docker-ready structure

## Departments
- AIandCybersecurity
- Business
- English
- Informatics

## Run locally
pip install -r requirements.txt

Set OpenAI API key:
$env:OPENAI_API_KEY="your_key_here"

Run API:
cd Code
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
