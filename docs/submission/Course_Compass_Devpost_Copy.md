# Course Compass: Devpost story (v4 draft)

> Fill every `⟦…⟧` from `eval/LLM_RESULTS.md` after the live run, and the demo link after
> deployment. Do not submit while any `⟦…⟧` remains.

**Tagline:** Ask your curriculum in any language. Get the answer, the page that proves it, and a second AI that checks it.

## Inspiration

How many credits is the master's thesis worth? At the University of Klagenfurt the answer is 23
ECTS in AI and Cybersecurity, 25 in Informatics and 30 in Worlds of English, whose curriculum
exists only in German. International students ask in English, Italian (the AI and
Cybersecurity double degree runs with Udine) or their own language. A fluent chatbot answer
from the wrong programme or the wrong page is worse than no answer, because students plan
their semesters on it.

## What it does

A student picks a programme and asks in any language. Course Compass:

1. **Understands the question with AI.** It maps the student's words to the terms the
   curriculum uses (*tesi* → *thesis* → *Masterarbeit*).
2. **Searches only that programme's documents** and refuses when the best page covers too
   little of the question. That prevents a made-up answer.
3. **Answers from the excerpts only**, with a citation on every sentence. The **real PDF page
   opens with the supporting sentence highlighted**.
4. **Has a second AI read it.** A different model checks each sentence against its page
   (supported / contradicted / not in the source) and whether the question was actually
   answered. If it wasn't, Course Compass **looks again with a wider search** before admitting
   failure. A deterministic check flags any number that isn't on the page.
5. **Compare mode** answers one question for every programme side by side, with a one-line
   contrast whose numbers must all appear in the checked answers.

The student sees one plain label: *checked twice*, *partly confirmed: check the page*, *not
answered by these pages*, *contradicted by the page*, or *not in the documents*.

## How we built it

Python, FastAPI and Streamlit. Retrieval is BM25 over page-aware passages, scoped to one
programme; optional `text-embedding-3-small` embeddings can re-order candidates but never add
evidence. The model steps are separated in `Code/ai_steps.py`:

| Step | Model | Role |
|---|---|---|
| Question understanding | gpt-4o-mini (JSON) | Key words and curriculum terms in English and German. It can only add terms for words the student wrote |
| Answer | gpt-4o-mini, temperature 0 | Short answer from the excerpts, citation on every sentence, exact numbers |
| Second reader | gpt-4.1-mini (JSON) | Sentence verdicts and "does this answer the question?" |
| Compare contrast | gpt-4o-mini (JSON) | One or two sentences; rejected if it contains a number not in the answers |

All model output is untrusted: JSON is parsed defensively, citations are validated, and
excerpts are passed as data, not instructions. The evidence viewer renders the PDF page with
pypdfium2 and highlights the sentence. A public demo needs guard rails, so there is a daily
spending cap (after which the app answers in free mode), a per-session limit and answer
caching. Without a key, the app runs in a free mode that copies source sentences and says
plainly that their meaning was not checked. No model was trained or fine-tuned.

## How we tested it

- **Two question sets.** 53 development questions (used while building) and a 26-question
  **held-out set frozen in a commit before any system ran on it**: paraphrases, questions in
  Italian, German, Spanish and French, and near-miss questions the documents don't answer.
  Both sets were drafted with an AI assistant from the curriculum pages; labels are checked
  automatically against the expected page.
- **The honest baseline.** Our earlier keyword-only system looked excellent on the development
  set (right page in the top 4 for 97.8%) and **found the right page for only 35% of the
  held-out questions, and 0 of 8 non-English ones.** It had been tuned to its own test.
- **AI mode, held-out set:** correct fact on the right page ⟦X%⟧ (free mode ⟦Y%⟧). False
  abstention ⟦…⟧, correct abstention ⟦…⟧. Of the answers labelled *checked twice*, ⟦…⟧ were
  right.
- **Planted errors.** We corrupted correct answers on purpose and checked them again: changed
  number caught ⟦…⟧, answer to a different question caught ⟦…⟧, invented extra rule caught
  ⟦…⟧. Untouched answers wrongly flagged: ⟦…⟧.
- **Compare mode:** ⟦…⟧ of programme answers correct on three questions whose answer differs
  by programme.
- **Students:** ⟦n⟧ students asked ⟦m⟧ of their own questions (`eval/STUDENT_RESULTS.md`).
- Offline tests in CI cover the engine, API, Streamlit UI and evaluator; CI builds both Docker
  images.

## Failure cases we kept

- *"How many words must the master's thesis have?"* (German curriculum). Keyword search ranks
  the right page 6th, and free mode copies a nearby sentence without the number. ⟦In AI mode:
  what the second reader and second look did⟧.
- In free mode, *"What is the tuition fee for non-EU students?"* (AI and Cybersecurity) copies
  an application-deadline sentence that mentions non-EU citizens. The label says the meaning
  was not checked, and ⟦AI mode result⟧.
- ⟦Worst held-out miss from LLM_RESULTS.md⟧.

## Challenges and what we learned

A test set you tune on lies to you: 97.8% became 35% on fresh questions. Citations are not
correctness either. An answer can quote a real page and still not answer the question, which
is why the second reader judges *the question* and not only the words. The hardest trade-off
is refusing versus answering. Every threshold that stops a made-up answer also withholds some
real ones, and we report both rates.

## What's next

More curricula and versions (with dates), OCR for scanned tables, a larger student-written
test set, and a study planner ("what do I still need?") built on the same evidence-first rules.

## Credits, prior work and AI assistance

Before the event (May 2026) the repository held a LangChain/OpenAI RetrievalQA prototype,
curriculum files, a pickled FAISS index, FastAPI, Docker, Kubernetes manifests and CI. That
code is kept in `legacy/` and `deploy/kubernetes/` and is not used. During the event (from 11
Nov 2026) the engine was rebuilt (v3) and then extended (v4) as described above and in the
commit history. Substantial implementation, test-question drafting and documentation help came
from Claude; ChatGPT/Codex helped verify the repository and an earlier submission draft.
Curriculum documents © University of Klagenfurt; English translations state they are not
legally binding. Independent prototype, not an official university service.

**Built with:** Python, OpenAI API (gpt-4o-mini, gpt-4.1-mini, text-embedding-3-small),
FastAPI, Streamlit, BM25, pypdf, pypdfium2, FAISS, NumPy, Docker, GitHub Actions, Hugging Face Spaces.

**Links:** demo ⟦Hugging Face Space⟧ · code https://github.com/Jeeson-Kurian/university-rag-chatbot

**Team:** Jeeson Joseph Kurian, solo ⟦confirm⟧.
