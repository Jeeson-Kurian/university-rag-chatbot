# 🧭 Course Compass — an AI course assistant that shows its sources

Students lose time hunting through long, partly German curriculum PDFs for one number: how many ECTS the thesis is worth, which language level admission needs, how long an internship must last. Generic chatbots answer confidently and are sometimes wrong.

Course Compass answers questions about the University of Klagenfurt curricula in this repository. It **cites the file and page** for every answer, **refuses** when the documents don't cover a question, and **flags any sentence or number** in a generated answer that the cited text doesn't support.

> Status: hackathon project (AI OpenBuild 2026). Not an official university service and not production-validated. Curricula can change; check the official documents before making decisions.

## What it does

| Student action | What Course Compass does |
|---|---|
| Picks a study area and asks a question | Searches only that study area's documents |
| Asks in English about a German curriculum | Bridges the languages with a curated English↔German curriculum glossary |
| Asks something the documents don't cover | Abstains **before** any model call: no cost and no made-up answer |
| Gets an answer | Every sentence carries a `[S#]` citation that links to the file, page and excerpt |
| Reads a generated answer | A grounding check marks each sentence as supported, uncited, weakly matched, or containing a number missing from the source |

## Pipeline

```
curated PDFs/TXT ──► page-aware chunks (900 chars, PDF hyphenation repaired)
                         │
question ─► terms (+ EN↔DE glossary) ─► BM25 within one department
                         │
                 evidence-coverage gate ──(too little evidence)──► abstain, no model call
                         │
          optional semantic re-rank (embeddings + FAISS, cached as .npy)
          semantic hits may only re-order lexical candidates, never add new evidence
                         │
      ┌──────────────────┴──────────────────┐
  no API key: free extractive answer    API key: citation-constrained LLM answer
      └──────────────────┬──────────────────┘
          claim-level grounding check (citations, numbers, term support)
                         │
                FastAPI  /  Streamlit UI
```

Design choices:

- **Evidence-coverage gate.** The share of the question's informative terms (weighted by IDF) found in the best passage must reach 0.35. Otherwise the system abstains without calling a model. The threshold sweep in [`eval/RESULTS.md`](eval/RESULTS.md) shows the trade-off.
- **Conservative hybrid retrieval.** Embeddings can only re-rank passages the lexical search already found. This protects traceability, but it means a paraphrase with no shared words is missed.
- **Grounding screen, not proof.** The check is lexical and numeric. It catches invented numbers and uncited claims cheaply, but it can't prove that a sentence is entailed by its source.

## Models and cost

Each step uses the cheapest option that is good enough, and paid calls only happen once evidence exists.

| Step | Default | Why |
|---|---|---|
| Retrieval, gate, extractive answers, grounding | No model (BM25 + rules) | Free and deterministic; it can be tested offline in CI |
| Embeddings (optional) | `text-embedding-3-small` | OpenAI's cheapest embedding model ($0.02 per 1M tokens). Each department's corpus is embedded once and cached on disk as `.npy` |
| Answer generation (optional) | `gpt-4o-mini`, temperature 0 | Non-reasoning, deterministic and low-cost ($0.15 in / $0.60 out per 1M tokens) |
| Cheaper alternative | `UNIVERSITY_CHAT_MODEL=gpt-5-nano` | $0.05 in / $0.40 out per 1M. Sent with `reasoning_effort=minimal` and `max_completion_tokens`. Supported in code but **not yet verified live** |
| Safety net | `UNIVERSITY_FALLBACK_MODEL` (optional) | A second model is tried once if the first one errors |

Prices are from the OpenAI pricing page as checked on 2026-11-12, and they are used only for the per-answer cost estimate shown in the UI. With the default model, a typical answer uses about 1,000–1,500 input tokens, so it costs roughly $0.0002–$0.0003. A repeated question is answered from an in-memory cache. Any OpenAI-compatible server can be used by setting `OPENAI_BASE_URL`. **No paid service is required**: without a key, the app runs in free extractive mode.

## Measured results

From `python scripts/evaluate.py`: 53 labelled questions (45 answerable, 8 unanswerable), run offline with no model calls.

| System | Hit@4 | MRR@4 | Correct abstention | False abstention |
|---|---|---|---|---|
| Pre-hackathon scorer (baseline) | 91.1% | 0.756 | 37.5% | 2.2% |
| Course Compass v3 | **97.8%** | **0.850** | **100%** | **0.0%** |

Limits of these numbers: the questions were drafted with an AI assistant, not written by students. It is a development set, because the threshold and glossary were tuned on it. The unanswerable group has only 8 questions. LLM answer quality is **not** measured here. The full report, with the per-type breakdown, the threshold sweep and the remaining failure, is in [`eval/RESULTS.md`](eval/RESULTS.md).

The glossary is what makes the German curriculum usable: on the 5 English questions about it, Hit@4 goes from 0/5 without the glossary to 4/5 with it.

**Known failure:** for *"How many words must the master's thesis have?"* in the German *Worlds of English* curriculum, the right page (p. 10, "30.000 Wörtern") is ranked 6th, outside the top 4. Generic terms such as "master" outweigh the translated term.

## Submission materials and live evaluation status

The [submission folder](docs/submission/README.md) contains a visual walkthrough with actual free-mode outputs, the draft Devpost story, reproducibility records and limitations.

A live evaluation on 13 November 2026 returned `AuthenticationError` for all 45 answerable questions: **zero generated answers**. The eight unsupported questions were refused before model calls. The [original failed-run report](docs/submission/LLM_RESULTS_2026-11-13.md) is preserved. This does not establish live AI answer quality. The evaluator now returns a nonzero exit status on provider errors while retaining diagnostic artifacts. Repair the GitHub `OPENAI_API_KEY` secret and rerun before claiming live AI success.

## Run it

Python 3.12 is recommended.

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py          # one command; free extractive mode
```

AI mode: set `OPENAI_API_KEY` in your environment (or in `.streamlit/secrets.toml`, which git ignores) before starting the app.

As a separate API:

```bash
uvicorn Code.main:app --host 127.0.0.1 --port 8000
UNIVERSITY_API_URL=http://127.0.0.1:8000 streamlit run streamlit_app.py
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /departments` | List of study areas |
| `POST /ask` `{"question": "...", "department": "Informatics"}` | Returns `answer`, `mode` (`llm`, `extractive`, `abstained` or `model_error`), `sources[]`, `grounding`, `usage`, `model`, `cached` |
| `GET /stats` | Process counters: abstentions before any model call, tokens used, cache hits |

Tests and evaluation, both offline: `python -m pytest Code/tests -q` and `python scripts/evaluate.py`. CI runs both and builds the Docker image. The evaluation fails CI if Hit@4 drops below 85% or correct abstention below 85%.

## Repository map

| Path | Contents |
|---|---|
| `Code/course_core.py` | Ingestion, BM25, gate, hybrid re-rank, answering, caching and cost accounting |
| `Code/text_tools.py` | Tokeniser, light stemmer, EN↔DE glossary, sentence splitter |
| `Code/grounding.py` | Claim-level grounding screen |
| `Code/main.py` | FastAPI service |
| `streamlit_app.py` | Student UI (runs in-process or against the API) |
| `eval/` | Labelled questions, generated results |
| `legacy/` | The pre-hackathon LangChain pipeline, kept for disclosure and not used |

## Prior work and what was built during AI OpenBuild

**Before the event (May 14–17, 2026):** a LangChain + OpenAI RetrievalQA prototype with FastAPI, a stored FAISS index (loaded with pickle deserialisation), the curriculum files, Docker, Kubernetes manifests and a CI workflow.

**During the event (from Nov 11, 2026):** a new engine replacing LangChain, built with substantial help from an AI coding assistant (Claude):

- department-safe ingestion with page citations
- BM25 retrieval with stemming, PDF de-hyphenation and the EN↔DE glossary
- the evidence-coverage gate, plus the conservative hybrid re-rank with a pickle-free embedding cache
- free extractive answers, citation-validated LLM answers and the claim-level grounding check
- model tiering, cost reporting, answer caching and a fallback model
- the Streamlit UI and API v3
- a 53-question labelled evaluation with a baseline comparison, and offline tests in CI

The full history is in the git log.

## Limitations

- Four curricula from one university, without OCR. Scanned PDFs and tables extract imperfectly.
- The lexical design misses pure paraphrases. The glossary covers common curriculum terms only.
- The grounding screen is lexical, not semantic entailment.
- Prompt-injection resistance has not been independently tested. Excerpts are passed to the model as untrusted data.
- The model provider receives questions and excerpts. Use only documents you are allowed to share.
- No authentication or rate limiting. The API is meant for local or demo use.

Curriculum documents © University of Klagenfurt and included for demonstration. The English translations state that they are not legally binding.
