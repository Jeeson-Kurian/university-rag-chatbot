# Course Compass — AI University Course Assistant

Status: hackathon development candidate. Not production-validated.

A student-facing, source-grounded curriculum assistant. Select a study department, ask a question, and inspect the original file, page (where available), and excerpt associated with each numbered citation.

## Architecture and evidence policy

Curated PDF and TXT documents -> per-page extraction -> bounded text chunks -> strict department filter -> lexical evidence ranking -> optional ephemeral FAISS semantic re-ranking -> optional citation-constrained LLM -> FastAPI -> Streamlit.

The system limits semantic search to candidates already supported by lexical overlap. This conservative gate prioritizes traceability over recall. When no credentials are configured, it returns an explicitly labelled extractive preview, not a generated AI answer. Generated answers without valid citation IDs abstain. A valid citation does not guarantee that the claim is semantically supported; inspect the underlying excerpt.

## Run locally

Python 3.12 recommended.

1. Install dependencies: python -m pip install -r requirements.txt
2. API terminal: uvicorn Code.main:app --host 127.0.0.1 --port 8000
3. UI terminal: streamlit run streamlit_app.py
4. Open the local Streamlit page and choose a department.

To enable generation and semantic search, set OPENAI_API_KEY in your terminal environment before starting FastAPI. Default models: gpt-4o-mini for generation and text-embedding-3-small for embeddings, configurable via UNIVERSITY_CHAT_MODEL and UNIVERSITY_EMBEDDING_MODEL. The provider can receive your student questions and document text; use only documents approved for this purpose. Provider charges apply.

Commands: python -m pytest Code/tests/test_course_core.py -q
Evaluation: python scripts/evaluate.py
Docker: docker build -t course-compass . && docker run --rm -p 127.0.0.1:8000:8000 course-compass

Docker starts the API only; run Streamlit separately.

## HTTP contract

GET /health is liveness, not provider readiness.
GET /departments lists canonical names.
POST /ask accepts a JSON object with question and department, e.g. {"question":"What does the curriculum say about the thesis?","department":"Informatics"}.

The response exposes answer, mode (preview, llm, abstained or model_error), retrieval_mode, optional warning, and source records with file name, department, page, reference ID, and excerpt.

## Baseline versus new competition work

Before this branch: LangChain + OpenAI QA, FastAPI, FAISS, ingestion scripts, PDF/TXT documents, Docker and CI were present. Changes in this branch: explicit source evidence model, canonical department filtering, safer in-memory vector rebuilding, constrained generation and abstention, input validation, Streamlit student UI, synthetic offline tests, five-case retrieval smoke evaluation, and CI with no secret requirement.

This is an existing-project enhancement. Clearly disclose all earlier development and the dates/team contributions in AI OpenBuild. Do not claim this system was built entirely from scratch during the competition.

## Remaining boundaries

The repository's old university_index contains pickle material and is deliberately not loaded. No OCR for scanned pages, web hosting, user authentication, rate limiting or independent verification of prompt-injection resilience is included. Original curricula can be out of date. The project is not endorsed by the university. See docs/COURSE_COMPASS_ENGINEERING.md for security, evaluation and demonstration guidance.
