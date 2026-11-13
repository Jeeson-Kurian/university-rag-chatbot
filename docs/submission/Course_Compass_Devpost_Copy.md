# Course Compass

**Tagline:** Ask your curriculum. Check the page. Know when the evidence runs out.

## Inspiration

A curriculum question can look simple: how many credits is the thesis worth? The answer depends on the programme. In the documents used here, the AI and Cybersecurity thesis is worth 23 ECTS, while the Informatics thesis is worth 25. A fluent answer from the wrong curriculum would be worse than an honest refusal.

Course Compass focuses on that problem: helping students find an answer they can check, even when their question is in English and the curriculum is in German.

## What it does

Students choose a study area, ask a question, and inspect an answer alongside its cited document, page and excerpt. The prototype covers four University of Klagenfurt curricula: AI and Cybersecurity, Informatics, Business, and English.

It has two modes. Free extractive mode copies relevant source sentences and requires no API key. Optional AI mode asks a language model to write a short answer using only the retrieved excerpts and attach source citations. A grounding screen flags uncited sentences, weak lexical matches, and numbers absent from the cited text. It is a warning mechanism, not a guarantee of correctness.

Before either answer path, an evidence-coverage gate checks whether the best passage covers enough of the question. When evidence is insufficient, the assistant refuses before making a model call. Asking about a tuition fee missing from the Informatics corpus produces: "I cannot find this information in the selected university documents."

## How we built it

The engine loads curated PDF and text files into overlapping, page-aware passages. BM25 searches within the selected study area; a small English-German glossary bridges curriculum terms. Optional OpenAI embeddings and FAISS re-rank lexical candidates without introducing unrelated semantic hits. The embedding cache uses NumPy files without pickle deserialisation.

FastAPI exposes the engine, and Streamlit supplies the student interface. The UI can run the engine directly or call a separate API. Optional answer generation defaults to `gpt-4o-mini`; optional embeddings use `text-embedding-3-small`. Answer caching and token-based cost estimates help make model use visible. No model was trained or fine-tuned for this project.

The repository includes offline tests, an evaluation script, a baseline comparison, Docker configuration, and GitHub Actions. A separate AI evaluation workflow runs only on manual dispatch or a push to its dedicated evaluation branch; it uses a repository secret and uploads results as an artifact.

## What we tested

The offline evaluation was reproduced on 13 November 2026 from main commit `19723f976b5196f4f07683c36ff8ac784dfb8552`:

| Measure | Baseline | Course Compass v3 |
|---|---:|---:|
| Expected page in top four, 45 answerable questions | 91.1% | 97.8% (44/45) |
| Mean reciprocal rank at four | 0.756 | 0.850 |
| Correct refusal, 8 unsupported questions | 37.5% | 100% (8/8) |

These are retrieval and refusal results, not LLM answer accuracy. In free mode, the expected keyword appeared in 82.2% of answers. The 53 questions were AI-assisted and used during development; the glossary and threshold were tuned on them. They are not a held-out student study.

The accompanying visual walkthrough shows actual free-mode engine outputs, including a failure. It is not a recording of the Streamlit interface or a live LLM demonstration. A live provider evaluation on 13 November returned AuthenticationError for all 45 answerable questions, with zero successful generated answers; the eight unsupported questions were refused. This run cannot establish AI answer quality. The failed-run report is included in the submission folder.

## Challenges and what we learned

The useful trade-off was between answering more questions and refusing unsupported ones. Raising the evidence threshold improves caution but can also withhold valid answers. Language bridging helped retrieval: four of five English questions over the German curriculum found the expected page in the top four, compared with none without the glossary.

The most instructive failure asks how many words the English master's thesis must contain. The correct page falls outside the top four, and the returned extractive answer does not give the requested count. Its grounding screen still passes because the returned words match a source. This demonstrates why source matching does not establish that an answer resolves the question.

## Accomplishments

The prototype makes study-area boundaries, page evidence, abstention and uncertainty visible. Its evaluation separates retrieval from answer quality and preserves the remaining failure rather than hiding it behind one accuracy score. Students can inspect useful evidence without requiring a paid model account.

## What's next

Repair provider authentication and evaluate live AI answers with the existing workflow, collect an untouched set of questions from students, improve the word-count failure, and test whether users can verify answers faster with the interface. Broader deployment would also require authentication, rate limits, document-version controls and independent prompt-injection testing.

## Credits and prior work

The pre-event repository contained a LangChain/OpenAI RetrievalQA prototype, curriculum files, a stored FAISS index, FastAPI, Docker, Kubernetes manifests and CI. The repository dates that prototype to May 2026. The event work, from 11 November 2026, replaces the retrieval/answering engine and adds the evidence gate, bilingual glossary, page citations, grounding screen, Streamlit interface, evaluation, caching and model controls. Legacy code remains separately identified.

Substantial implementation and question-drafting assistance came from Claude, as disclosed in the repository. ChatGPT/Codex helped verify the current repository, reproduce the offline evaluation, prepare this submission copy and create the visual walkthrough. The curriculum documents are credited to the University of Klagenfurt. This is an independent prototype, not an official university service. Source documents can become outdated; English translations may not be legally binding.

**Built with:** Python, FastAPI, Streamlit, BM25, pypdf, NumPy, FAISS, OpenAI API (optional), Docker, GitHub Actions.

**Repository:** https://github.com/Jeeson-Kurian/university-rag-chatbot

**Team field:** Confirm the actual entrant list and each person's role in Devpost. Do not infer other members from unrelated projects. The project owner is Jeeson Joseph Kurian.
