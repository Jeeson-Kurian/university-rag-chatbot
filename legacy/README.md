# Pre-hackathon pipeline (kept for disclosure)

These modules are the original LangChain-based RAG pipeline that existed before
AI OpenBuild (Nov 5 – Dec 10, 2026). They are **not imported** by Course
Compass and are not installed by `requirements.txt` (they need `langchain_*`
packages). They are kept, unmodified apart from the move, so reviewers can see
what predates the event. The old `university_index/` pickle/FAISS index was
removed from the tree because loading it required
`allow_dangerous_deserialization=True`; it remains in git history.
