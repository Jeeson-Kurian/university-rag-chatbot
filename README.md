# 🧭 Course Compass

**Ask your curriculum in any language. Get the answer, the page that proves it, and a second AI that checks it.**

AI OpenBuild 2026 · University of Klagenfurt curricula · student prototype, not an official university service

> **Live demo:** _Hugging Face Space link added after deployment_ · **Evaluation:** [`eval/`](eval/) · **Limits:** [below](#limitations)

---

## The problem

A curriculum question looks simple: *how many credits is the thesis worth?* The right answer depends
on the programme (23 ECTS in AI and Cybersecurity, 25 in Informatics, 30 in Worlds of English).
Some curricula exist only in German, and many international students ask in English or their own
language. A fluent chatbot answer from the wrong page is worse than no answer, because students
act on it.

## What Course Compass does

| You do | Course Compass does |
|---|---|
| Ask in English, German, Italian, Spanish… | **AI question understanding** turns your words into the terms the curriculum uses (*tesi* → *thesis* → *Masterarbeit*) |
| Pick your programme | Searches **only that programme's documents**, so another programme's rule can't leak in |
| Get an answer | Every sentence cites a page. **The real PDF page opens with the supporting sentence highlighted** |
| Trust it? | A **second AI reader** (a different model) checks every sentence against its page and whether your question was actually answered. A deterministic check flags any number not on the page |
| The first answer missed | It **looks again, wider**, before telling you it failed |
| Ask something the documents don't cover | It **says so** and writes nothing |
| Not sure which programme matters | **Compare mode** answers the same question for every programme side by side |

## How it works

```
question (any language)
   │
   ├─► [AI] understand: key words + curriculum terms in English and German
   │
   ▼
BM25 keyword search inside ONE programme  (+ optional embedding re-rank, never new evidence)
   │
   ├─► evidence gate: best page covers too little of the question → "not in the documents"
   │
   ▼
[AI] answer from the excerpts only, a citation on every sentence
   │
   ├─► [AI] second reader (another model): each sentence supported / contradicted / not in source;
   │        does the answer address the question?  ── "no" → one wider second look
   ├─► word & number check (deterministic): every number must be on the cited page
   │
   ▼
label for the student + highlighted PDF page        (Compare: the same, for each programme)
```

| Step | Model | Why this choice |
|---|---|---|
| Question understanding | `gpt-4o-mini`, JSON output | Cheap, multilingual; can only add terms for words the student wrote |
| Answer | `gpt-4o-mini`, temperature 0 | Short, citation-constrained answers; ~$0.0003 each |
| Second reader | `gpt-4.1-mini` | A *different* model checks the first one; ~$0.001 per check |
| Embeddings (optional re-rank) | `text-embedding-3-small` | Cached on disk as `.npy`, no pickle |
| Free mode (no key) | none | Copies the best source sentences; labelled "meaning not checked" |

Public-demo safety: a daily spending cap (`DAILY_BUDGET_USD`, default $2) after which the app
falls back to free mode, a per-session question limit, answer caching, and excerpts passed to
the model as untrusted data.

## Results

All numbers come from scripts in this repository; every run is reproducible.

**Two question sets.** The *development set* (53 questions) was used while building, so its
numbers are optimistic. The *held-out set* (26 questions: paraphrases, questions in Italian,
German, Spanish and French, near-miss unanswerable questions) was **frozen in a commit before any
system ran on it**; its questions and labels were never changed (but fixes were made after seeing its misses, see below). Both were drafted with an AI assistant from the
curriculum pages; labels are machine-checked against the expected page.

**Free mode, offline** (`python scripts/evaluate.py`):

| Set | Expected page in top 4 | False abstention | Correct abstention |
|---|---|---|---|
| Development (45 + 8) | 97.8% | 0.0% | 100% |
| Held-out (20 + 6) | **35.0%** | **65.0%** | 83.3% |

The gap is the honest headline: keyword search plus a hand-written glossary was tuned to the
development questions and fails on fresh wording and on every non-English question (0 of 8). This is the problem the
AI steps are built to solve.

**AI mode, live** (`python scripts/evaluate_llm.py`, run 5 on 16 Nov 2026, 0 provider errors,
≈ $0.09 for everything below; full report: [`eval/LLM_RESULTS.md`](eval/LLM_RESULTS.md)):

| Held-out set (20 answerable + 6 not) | Free mode | **AI mode** |
|---|---|---|
| Correct fact on the right page, strict keyword | 10% | **50%** |
| … in any language (model-graded, translations count) | 10% | **80%** |
| Answerable questions wrongly refused | 65% | **10%** |
| Unanswerable questions correctly refused | 83% | **100%** |
| Answers labelled *checked twice* that were right (graded) | – | **12 of 13** |

On the development set AI mode gets 93% right on the right page (free 78%), refuses all 8
unanswerable questions, and 42 of its 43 *checked twice* answers are right.

**Planted errors.** 52 correct AI answers were corrupted on purpose and re-checked:

| Corruption | Caught |
|---|---|
| A number changed (e.g. 23 → 28 ECTS) | 29 / 29 |
| The answer to a different question | 46 / 47 |
| An invented extra rule | 52 / 52 |
| *Untouched* correct answers wrongly flagged | 0 / 52 (98% shown as checked twice) |

Honest note: the deterministic word & number check alone already catches most of these
planted errors (94–100%). The second reader's distinct value is judging *meaning across
languages* and *whether the question was answered*, which word overlap cannot do.

**Compare mode:** 9 of 9 programme answers correct on three questions whose answer differs by
programme (thesis credits, English level, open electives).

**The road there is kept** in [`eval/live_runs/`](eval/live_runs/): five runs on 16 Nov. Run 1
(first contact with the held-out set) scored 40% strict; the fixes after it (answer language,
German word forms, gate, no arithmetic) were made **after seeing held-out misses**, so the
held-out numbers above are no longer fully blind. The student check is the next independent test.

**Remaining failures (shown, not hidden):**
- *Flattened tables.* PDF tables become one line of numbers. Twice the model read a
  semester-plan or subtotal row as the answer (Informatics: thesis "30" instead of 25, required
  subjects "22" instead of 34) and both checks passed, because the number really is on that page.
- *Two German-curriculum questions are still refused* ("how long is the programme planned to
  take", "how much time should the thesis topic allow"): their wording never reaches
  *Studiendauer* or *sechs Monaten*.
- A French question about the bachelor's total credits got a sub-total (122 for required
  subjects); it is labelled *check the page*, not checked.
- **The former known failure is fixed in AI mode:** *"How many words must the master's thesis
  have?"* on the German curriculum is now answered "at least 30,000 words", checked twice, with
  the sentence highlighted on page 10. In free mode it still fails.

## Run it

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py                 # free mode, no key needed
OPENAI_API_KEY=sk-... streamlit run streamlit_app.py   # AI mode
```

API: `uvicorn Code.main:app` → `POST /ask`, `POST /compare`, `GET /page` (PNG with highlight),
`GET /stats`, `GET /health`.

Tests and evaluation: `python -m pytest Code/tests -q` (offline, includes Streamlit UI tests)
and `python scripts/evaluate.py`. CI runs both and builds both Docker images.

**Deploy the public demo** (Hugging Face Space, free): add the GitHub secret `HF_TOKEN` (write
token) and the variable `HF_SPACE` (`name/course-compass`), then run the *Deploy public demo to
Hugging Face* workflow. It copies `OPENAI_API_KEY` into the Space as a secret.

## Limitations

- **Four curricula, one university, ~60 pages.** No OCR; tables extract imperfectly.
  Curricula change; the English versions say they are not legally binding.
- **The second reader is a model too** and can be wrong; it missed both flattened-table errors.
  The planted-error test measures catch and false-alarm rates on this data; it is not proof.
- **Tables** are read as flattened text, the main remaining source of wrong "checked" answers.
- **Question sets are AI-drafted**, not written by students. A small student check
  ([`docs/student_testing/`](docs/student_testing/)) is the next step; its results will be
  reported as they are.
- Keyword search is the gate: a question that shares no words (and no translated terms) with
  the right page is refused rather than guessed.
- Questions and excerpts go to OpenAI. No authentication on the API; the public demo relies on
  spending caps. Prompt-injection resistance has not been independently tested.

## Prior work and what was built during AI OpenBuild (5 Nov – 10 Dec 2026)

**Before the event (May 2026):** a LangChain + OpenAI RetrievalQA prototype with FastAPI, a
pickled FAISS index, the curriculum files, Docker, Kubernetes manifests (now in
`deploy/kubernetes/`) and CI. Kept in `legacy/` for disclosure, not used.

**During the event (from 11 Nov 2026)**, built with substantial help from AI coding assistants
(Claude; ChatGPT/Codex for verification), as disclosed in the commit history:
v3 (11–13 Nov) replaced LangChain with the page-cited BM25 engine, evidence gate, glossary,
lexical grounding check, Streamlit UI and the 53-question evaluation; v4 (from 16 Nov) added
AI question understanding, the second reader with a wider second look, compare mode, the
highlighted-page evidence viewer, the redesigned UI, budget controls, the frozen held-out set,
the planted-error evaluation, and the Hugging Face deployment.

## Repository map

| Path | Contents |
|---|---|
| `Code/course_core.py` | Engine: ingestion, search, gate, answers, second look, compare, budget |
| `Code/ai_steps.py` | The model prompts and defensive parsing of their JSON output |
| `Code/grounding.py` | Deterministic word & number check |
| `Code/page_view.py` | Renders a cited PDF page with the evidence highlighted |
| `Code/main.py` | FastAPI service |
| `streamlit_app.py` | Student UI: Ask · Compare · How it works |
| `eval/` | Development and held-out sets, results, student check |
| `scripts/` | Offline and live evaluation, screenshot capture, student summary |
| `deploy/` | Hugging Face Space, legacy Kubernetes |

Curriculum documents © University of Klagenfurt, included for demonstration.
