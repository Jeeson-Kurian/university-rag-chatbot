# Course Compass: Engineering and submission handoff

## Design goals and verified baseline defects

- Canonical department metadata: baseline ingestion labelled the AI programme "ArtificialIntelligence and Cybersecurity" while the FastAPI filter expected "AIandCybersecurity".
- Safe index lifecycle: baseline used allow_dangerous_deserialization=True on local FAISS data. The new core builds its own ephemeral index from curated text; it never opens the historical pickle index.
- Evidence lineage: source IDs are stable hashes of department, file, page and chunk offset. Responses include local filename and best-effort PDF page number.
- Offline reproducibility: no model credentials, external network or real student records needed for synthetic API/retrieval tests.
- Failure transparency: extraction-only preview, model-generated response, abstention and provider-error modes are distinct.

## Architecture

Data trust: only fixed folders AIandCybersecurity, Business, English and Informatics under the curated repository data root are enumerated. Only PDF/TXT inputs are read; files over 6 MiB are skipped, and PDF extraction is capped at 150 pages. PDF content is untrusted.

Retrieval: lexical candidate matching and weighted term overlap always operate within the selected department. Optional OpenAI embeddings re-rank only these lexical candidates with a reciprocal-rank-fusion-like score. This is deliberately a conservative variant of hybrid retrieval: semantic-only hits cannot enter the answer. This may reduce recall for paraphrases.

Generation: the optional Chat Completions step receives only four selected excerpts and a prompt describing provenance requirements. It is instructed to cite [S1] through [S4] and abstain when evidence is insufficient. Software checks that cited identifiers are present in the supplied evidence bundle. Citation syntax validation is **not** entailment verification.

Serving: FastAPI validates input lengths and department enumeration. Streamlit provides user-facing display of citation snippets. The service is intended for loopback demonstration, not an exposed public endpoint.

## Security threat model

Attack surfaces: malicious PDF text, PDF parser errors, crafted student question, unsafe third-party embeddings, provider outages, sensitive curriculum files and untrusted model output.

Implemented mitigations: bounded question size, curated directories, rejected symlinks and oversized files, short excerpt budget, no pickle deserialization, citation-ID checks, no provider secrets sent to UI, sanitized HTTP errors, no network requirements for test fixtures.

Known limitations: prompt-injection resistance has not been independently measured; evidence passages may contain misleading instructions, and syntactically valid citations can still accompany unsupported conclusions. No public authentication, rate limiting, PII auditing or EU data-protection certification. No guarantee that historical curriculum PDFs are currently authoritative. No scanned-PDF OCR. No claim of production security.

## Quality assurance and reproducibility

Run locally:

    python -m pip install -r requirements.txt
    python -m pytest Code/tests/test_course_core.py -q
    python -m compileall -q Code streamlit_app.py
    python scripts/evaluate.py
    docker build -t course-compass:test .

Synthetic unit/API checks cover department isolation, deterministic IDs, offline answers, abstention, invalid inputs, fake-model citation checks and HTTP response validation.

The evaluation harness has five document-smoke cases: AI/Cybersecurity, Informatics, Business, English and an unrelated spacecraft question. It does not establish retrieval precision, factuality, model quality, user satisfaction or robustness to adversarial prompts. Record pass counts only after executing the suite on the actual commit.

For a stronger final evaluation, ask five students to write at least 30 realistic curriculum questions; label relevant source passages; measure retrieval hit@4, coverage, citation support and abstention accuracy; retain a failure-case table. Do not invent scores.

## Two-minute demonstration plan

0–15s: introduce the actual student problem.

15–45s: select AI/Cybersecurity, ask a question, expand and inspect the evidence source.

45–70s: select Informatics and demonstrate departmental isolation.

70–95s: ask an out-of-domain question and show abstention.

95–120s: show architecture, honest baseline disclosure and operational limitations.

Record actual screen use; label preview mode as extractive and model mode as generated. No fake or simulated screen captures.

## AI OpenBuild disclosure checklist

The old repository already included curriculum PDFs, FAISS, LLM access, a FastAPI service, Docker, and a CI workflow. This branch is an extension, not a greenfield project. Disclose which files/features predate the entry and which commit/dates were added later.

Devpost: project description, problem/target users, actual AI functionality, tools/model/provider, source code or demo access, video or screenshot walkthrough, evaluation plus at least one failure case, prior-work disclosure, acknowledgements and five-person team responsibilities where applicable.

Suggested roles for five participants: backend/retrieval, UI/accessibility, evaluation/test data, documentation/demo, deployment/quality verification. Names and contributions should be recorded truthfully rather than invented.

## Reused engineering ideas, not copied code

ClaimGuard: separate untrusted evidence/HTTP boundary.
TokenServe: explicit error modes, testable interfaces and conservative performance claims.
This project implements these ideas independently; no code copied from other repositories.
