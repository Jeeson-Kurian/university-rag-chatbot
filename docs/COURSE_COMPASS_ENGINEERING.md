# Course Compass — engineering notes

## Defects found in the pre-hackathon baseline and how they were fixed

| Baseline defect | Fix |
|---|---|
| Ingestion labelled the AI programme `ArtificialIntelligence and Cybersecurity`, but the API filtered on `AIandCybersecurity`, so filtering silently failed | One canonical department registry is used everywhere, and folders map 1:1 to departments |
| A FAISS index was loaded with `allow_dangerous_deserialization=True` (pickle) | No pickle anywhere. Embeddings are rebuilt from curated text and cached with `np.save(..., allow_pickle=False)` |
| No page numbers and no way to check an answer | Passages carry file and page. Answers must cite `[S#]` IDs that exist, or the system abstains |
| The model was called even for questions with no evidence | The evidence-coverage gate abstains before any provider call |
| Every query re-tokenised the whole corpus | Term statistics are computed once per department (BM25 index) |
| English questions could not match the German *Worlds of English* curriculum | EN↔DE curriculum glossary with weighted expansion (0.7) |
| PDF line-break hyphenation split words ("Wör-tern") | Joined at ingestion when both sides are lowercase letters |
| Plural/verb forms did not match ("requires" vs "required") | Light suffix folding, applied identically to documents and questions |

## Retrieval

- **BM25** (k1 = 1.5, b = 0.75), computed per department over 900-character passages with 120-character overlap. Passages never cross page boundaries.
- **Coverage gate:** `coverage = Σ idf(question terms present in passage, directly or via glossary) / Σ idf(all question terms)`. Terms missing from the department get the maximum IDF, so an unknown topic word pulls coverage down sharply. The threshold of 0.35 was picked from the sweep in `eval/RESULTS.md`. At that value, Hit@4 is unchanged from no gate, and all 8 unanswerable questions are rejected.
- **Hybrid re-rank** (only when a key is configured): the top 16 lexical candidates are fused by reciprocal rank (constant 60) with the semantic ranking. Semantic-only hits are ignored.

## Answering

- **Extractive (free):** the best-scoring sentence from up to three top passages. Extra lines must score at least 60% of the best line. Abbreviations ("max.", "para.") don't break sentences.
- **LLM:** at most four excerpts, each up to 850 characters, are labelled `[S1]`…`[S4]` and given to the model as untrusted data. The model must cite every factual sentence and copy numbers exactly. Answers with no citation or an unknown ID become an abstention. `gpt-5*` models are sent `reasoning_effort` and `max_completion_tokens` instead of `temperature`.
- **Grounding screen** (`Code/grounding.py`) runs on every sentence and checks three things: is there a citation, does every number appear in the cited excerpts, and do at least 50% of the informative terms (or their glossary translations) appear there. A failing sentence produces a visible warning in the UI.

## Cost controls

1. Abstention before any model call when evidence is missing.
2. Corpus embeddings are computed once and cached on disk, keyed by model and content hash. Query embeddings are cached in memory (LRU, 512 entries).
3. Answers are cached in memory (LRU, 256 entries) under a normalised question key.
4. The defaults are the cheapest suitable models. Token usage and estimated USD are returned for each answer. `/stats` aggregates the counters per process.

## Security model

Untrusted inputs are PDF text, questions and model output. Mitigations:

- fixed department folders, no symlinks, a 6 MiB file cap and a 150-page cap
- question length limits and control-character stripping
- no pickle
- sanitised HTTP errors
- citation validation
- secrets read only from the environment or Streamlit secrets

Not done: authentication, rate limiting, measured prompt-injection robustness, PII review.

## Testing

`Code/tests` run offline with a fake provider. They cover:

- department isolation
- deterministic extractive answers
- abstention without a model call
- input validation
- unique and bounded chunks
- de-hyphenation and glossary retrieval
- citation validation and detection of invented numbers
- answer caching and reasoning-model parameters
- fallback models
- the pickle-free embedding cache (needs `faiss`)
- the HTTP contract (needs `fastapi`)

`scripts/evaluate.py` validates its own labels, compares against the pre-v3 scorer and enforces regression floors in CI.

## Demo script (2 minutes)

| Time | What to show |
|---|---|
| 0:00–0:15 | The problem: long, partly German curricula |
| 0:15–0:45 | Informatics: "How many hours must the internship last?" → open the cited page 15 excerpt |
| 0:45–1:05 | English (German PDF): an English question answered from German evidence, with the grounding panel open |
| 1:05–1:25 | An out-of-scope question → abstains, and the counters show no model call was made |
| 1:25–1:50 | `eval/RESULTS.md`: baseline vs v3, plus the known failure |
| 1:50–2:00 | Free mode vs AI mode, cost per answer, and limitations |

Record real screen use only.
