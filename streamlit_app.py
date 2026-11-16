"""Course Compass student interface.

Default: runs the engine in-process (one command; also what the Hugging Face Space runs).
Set UNIVERSITY_API_URL to call a separately running FastAPI service instead.
"""
from __future__ import annotations

import html
import os

import streamlit as st

from Code.course_core import DEPARTMENTS, SHORT_NAMES, CourseAssistant, document_path
from Code.page_view import best_sentence, render_page

API_URL = os.getenv("UNIVERSITY_API_URL", "").rstrip("/")
SESSION_AI_LIMIT = int(os.getenv("SESSION_AI_LIMIT", "25"))

ASK_EXAMPLES = {
    "AIandCybersecurity": [
        "How many ECTS credits does the Master's thesis comprise?",
        "Quanti crediti devo ottenere all'Università di Udine per il doppio titolo?",
        "What is the tuition fee for non-EU students?",
    ],
    "Informatics": [
        "How many hours must the internship last?",
        "Which specialisation subjects can I choose?",
        "Can I take the thesis defence online?",
    ],
    "English": [
        "How many words must the master's thesis have?",
        "Wie viele ECTS-AP umfasst die Masterarbeit?",
        "What English level do I need if English is not my first language?",
    ],
    "Business": [
        "How long should the internship last?",
        "How many ECTS credits are required in open electives?",
        "How much does a student parking permit cost?",
    ],
}
COMPARE_EXAMPLES = [
    "How many ECTS credits does the thesis comprise?",
    "How long must the internship last?",
    "What English level is required for admission?",
]
VERDICTS = {
    "verified": ("✓ Checked twice", "#0f7b4f", "#e3f5ec"),
    "screened": ("📄 Copied from the page, meaning not checked", "#1d5fa8", "#e6effa"),
    "check": ("⚠ Partly confirmed: check the page", "#9a5b00", "#fff3dc"),
    "not_answered": ("✗ Not answered by these pages", "#b42318", "#fde8e6"),
    "contradicted": ("✗ Contradicted by the page", "#b42318", "#fde8e6"),
    "abstained": ("○ Not in the documents", "#5b6270", "#eef0f3"),
    "error": ("! Model unavailable", "#b42318", "#fde8e6"),
}
READER_ICONS = {"supported": "✅", "contradicted": "❌", "not_in_source": "⚠️", "unchecked": "·"}
LEXICAL_TEXT = {
    "supported": "words and numbers found on the cited page",
    "uncited": "no citation",
    "number_not_in_evidence": "a number is not on the cited page",
    "weak_support": "few words match the cited page",
}

st.set_page_config(page_title="Course Compass · Klagenfurt curricula", page_icon="🧭",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 2.2rem;}
.cc-hero h1 {font-size: 2.3rem; margin-bottom: .1rem;}
.cc-hero p {color: #4a5160; font-size: 1.05rem; margin-top: 0;}
.cc-pill {display:inline-block; padding: .28rem .75rem; border-radius: 999px; font-weight: 600;
          font-size: .92rem; margin: .2rem 0 .6rem 0;}
.cc-mode {font-size: .85rem; color: #4a5160;}
.cc-terms code {font-size: .8rem;}
.cc-card-title {font-weight: 700; font-size: 1.02rem; margin-bottom: .15rem;}
.cc-summary {background:#f4f1ff; border-left: 4px solid #6b4fd8; padding:.8rem 1rem;
             border-radius: 6px; margin: .4rem 0 1rem 0;}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Reading the curriculum documents…")
def local_assistant() -> CourseAssistant:
    if not os.getenv("OPENAI_API_KEY"):
        try:  # Streamlit / Hugging Face secrets
            key = st.secrets.get("OPENAI_API_KEY")
            if key:
                os.environ["OPENAI_API_KEY"] = key
        except Exception:
            pass
    return CourseAssistant()


def ai_allowed() -> bool:
    return st.session_state.get("ai_questions", 0) < SESSION_AI_LIMIT


def ask(question: str, department: str) -> dict:
    if API_URL:
        import requests
        response = requests.post(f"{API_URL}/ask", json={"department": department,
                                                         "question": question}, timeout=60)
        response.raise_for_status()
        return response.json()
    return local_assistant().ask(question, department)


def compare(question: str, departments: list[str]) -> dict:
    if API_URL:
        import requests
        response = requests.post(f"{API_URL}/compare", json={
            "question": question, "departments": departments}, timeout=120)
        response.raise_for_status()
        return response.json()
    return local_assistant().compare(question, departments)


@st.cache_data(show_spinner=False, max_entries=64)
def page_png(department: str, document: str, page: int, highlight: str) -> bytes:
    if API_URL:
        import requests
        response = requests.get(f"{API_URL}/page", params={
            "department": department, "document": document, "page": page,
            "highlight": highlight}, timeout=60)
        response.raise_for_status()
        return response.content
    return render_page(document_path(department, document), page, highlight)


def pill(verdict: str, text: str | None = None) -> None:
    label, colour, background = VERDICTS.get(verdict, (verdict, "#333", "#eee"))
    tip = f' title="{html.escape(text)}"' if text else ""
    st.markdown(f'<span class="cc-pill" style="color:{colour};background:{background}"{tip}>'
                f"{label}</span>", unsafe_allow_html=True)


def claim_for_source(result: dict, source_id: str) -> str:
    for line in result["answer"].splitlines():
        if f"[{source_id}]" in line:
            return line
    return result["answer"]


def show_sources(result: dict, key: str, expanded_first: bool = True) -> None:
    for n, source in enumerate(result.get("sources") or []):
        page = source.get("page")
        title = f"[{source['id']}] {source['document']}" + (f" · page {page}" if page else "")
        with st.expander(title, expanded=expanded_first and n == 0 and bool(page)):
            highlight = best_sentence(source["excerpt"], claim_for_source(result, source["id"]))
            if page and source["document"].lower().endswith(".pdf"):
                try:
                    st.image(page_png(source["department"], source["document"], page, highlight),
                             caption="The highlighted sentence is the evidence for this answer.")
                except Exception:
                    st.caption("The page image is unavailable; the excerpt is shown instead.")
                    st.write(source["excerpt"])
            else:
                st.caption("Text source (no page image).")
                st.write(source["excerpt"])


def show_checks(result: dict) -> None:
    review = result.get("review") or {}
    grounding = result.get("grounding") or {}
    if review.get("status") == "done":
        st.markdown(f"**Second reader** ({review['model']}): does the answer address the "
                    f"question? **{review['answers_question']}**. {review.get('reason', '')}")
        for row in review["sentences"]:
            st.markdown(f"{READER_ICONS.get(row['verdict'], '·')} {row.get('sentence', '')}  \n"
                        f"<small>{html.escape(row['verdict'].replace('_', ' '))}: "
                        f"{html.escape(row.get('reason', ''))}</small>", unsafe_allow_html=True)
    elif review.get("status") == "unavailable":
        st.caption("The second reader was unavailable for this answer; only the word and number check ran.")
    if grounding.get("sentences"):
        st.markdown("**Word and number check** (deterministic, no model)")
        for row in grounding["sentences"]:
            st.caption(f"{LEXICAL_TEXT.get(row['status'], row['status'])} · "
                       f"{', '.join(row['citations']) or 'no citation'} · {row['sentence'][:160]}")


def show_meta(result: dict) -> None:
    parts = []
    if result.get("searched_terms"):
        parts.append("also searched for " + ", ".join(f"`{t}`" for t in result["searched_terms"][:8]))
    if result.get("second_look"):
        parts.append("looked twice (wider search after the first answer missed)")
    cost = 0.0
    for usage in [result.get("usage"), (result.get("review") or {}).get("usage")]:
        if usage and usage.get("estimated_cost_usd"):
            cost += usage["estimated_cost_usd"]
    if result.get("model"):
        parts.append(f"answer by {result['model']}" + (f" · ≈ ${cost:.4f}" if cost else ""))
    if result.get("cached"):
        parts.append("served from cache")
    if parts:
        st.markdown(f'<div class="cc-mode cc-terms">{" · ".join(parts)}</div>',
                    unsafe_allow_html=True)


def show_result(result: dict, key: str) -> None:
    pill(result.get("verdict", result["mode"]), result.get("verdict_text"))
    if result.get("verdict_text"):
        st.caption(result["verdict_text"])
    st.markdown(result["answer"])
    if result.get("warning"):
        st.warning(result["warning"])
    show_meta(result)
    if result["mode"] in {"llm", "extractive"}:
        with st.expander("How this answer was checked"):
            show_checks(result)
        st.markdown("##### Evidence")
        show_sources(result, key)


# ------------------------------------------------------------------ header
engine = None if API_URL else local_assistant()
st.markdown('<div class="cc-hero"><h1>🧭 Course Compass</h1>'
            "<p>Ask your curriculum in any language. Every answer shows the page it came "
            "from, a second AI model checks it, and the assistant says so when the documents "
            "don't cover your question.</p></div>", unsafe_allow_html=True)
if engine is not None:
    if engine.client is None:
        st.info("Free mode: no AI key is configured, so answers are sentences copied from the "
                "documents and nothing is generated.", icon="📄")
    elif not engine.ai_available:
        st.warning("Today's AI budget for this public demo is used up. Answers are copied "
                   "from the documents until tomorrow.", icon="⏸️")
    else:
        st.markdown(f'<div class="cc-mode">AI mode · answers by <b>{engine.chat_model}</b>, '
                    f"checked by <b>{engine.review_model}</b> · University of Klagenfurt "
                    "curricula · not an official university service</div>",
                    unsafe_allow_html=True)

ask_tab, compare_tab, about_tab = st.tabs(["Ask a question", "Compare programmes",
                                           "How it works · limits"])

# ------------------------------------------------------------------ ask
with ask_tab:
    department = st.selectbox("Your programme", list(DEPARTMENTS),
                              format_func=lambda k: DEPARTMENTS[k], key="dept")
    st.caption("Try:")
    for column, example in zip(st.columns(3), ASK_EXAMPLES[department]):
        if column.button(example, key=f"ex-{department}-{example}"):
            st.session_state["question"] = example
    question = st.text_area("Your question", key="question", max_chars=800, height=90,
                            placeholder="How many ECTS credits does the Master's thesis comprise?")
    if st.button("Find the answer", type="primary", disabled=len(question.strip()) < 4):
        if not ai_allowed() and engine is not None and engine.client is not None:
            st.info(f"You've asked {SESSION_AI_LIMIT} questions in this session, the limit for "
                    "the public demo. Please reload the page later.")
        else:
            try:
                with st.spinner("Searching the curriculum, writing and checking the answer…"):
                    st.session_state["last"] = ask(question.strip(), department)
                st.session_state["ai_questions"] = st.session_state.get("ai_questions", 0) + 1
            except Exception:
                st.error("The assistant is unavailable right now. Please retry.")
    last = st.session_state.get("last")
    if last and last["department"] == department:
        st.divider()
        show_result(last, "ask")

# ------------------------------------------------------------------ compare
with compare_tab:
    st.markdown("The right answer often depends on the programme. Ask once and see each "
                "programme's answer side by side, each with its own page.")
    for column, example in zip(st.columns(3), COMPARE_EXAMPLES):
        if column.button(example, key=f"cmp-{example}"):
            st.session_state["cmp_question"] = example
    cmp_question = st.text_input("Question for every programme", key="cmp_question",
                                 max_chars=800,
                                 placeholder="How many ECTS credits does the thesis comprise?")
    chosen = st.multiselect("Programmes", list(DEPARTMENTS), default=list(DEPARTMENTS),
                            format_func=lambda k: SHORT_NAMES[k])
    if st.button("Compare", type="primary", disabled=len(cmp_question.strip()) < 4 or not chosen):
        if not ai_allowed() and engine is not None and engine.client is not None:
            st.info("Session limit for the public demo reached. Please reload later.")
        else:
            try:
                with st.spinner("Asking each programme's curriculum…"):
                    st.session_state["cmp"] = compare(cmp_question.strip(), chosen)
                st.session_state["ai_questions"] = st.session_state.get("ai_questions", 0) + len(chosen)
            except Exception:
                st.error("The assistant is unavailable right now. Please retry.")
    cmp = st.session_state.get("cmp")
    if cmp:
        st.divider()
        if cmp.get("summary"):
            st.markdown(f'<div class="cc-summary"><b>In short:</b> {html.escape(cmp["summary"])}'
                        "<br><small>Written by the model from the checked answers below; every "
                        "number in it appears in one of them.</small></div>",
                        unsafe_allow_html=True)
        results = cmp["results"]
        for row_start in range(0, len(results), 2):
            columns = st.columns(2)
            for column, result in zip(columns, results[row_start:row_start + 2]):
                with column.container(border=True):
                    st.markdown(f'<div class="cc-card-title">{html.escape(DEPARTMENTS[result["department"]])}</div>',
                                unsafe_allow_html=True)
                    pill(result.get("verdict", result["mode"]), result.get("verdict_text"))
                    st.markdown(result["answer"])
                    if result["mode"] in {"llm", "extractive"}:
                        show_sources(result, f"cmp-{result['department']}", expanded_first=False)

# ------------------------------------------------------------------ about
with about_tab:
    st.markdown("""
**What happens when you ask**

1. **Understanding (AI).** A language model lists the key words of your question with the
   words a curriculum uses for them, in English and German. So *tesi*, *thesis* and
   *Masterarbeit* all reach the same page.
2. **Search.** A keyword search (BM25) looks only inside the selected programme's documents.
   Optional embeddings can re-order the results but never add new ones.
3. **Evidence gate.** If the best page covers too little of your question, Course Compass
   says it cannot find the answer, and no answer is written.
4. **Answer (AI).** A model writes a short answer using only the retrieved excerpts, with a
   citation on every sentence.
5. **Second reader (AI).** A different model checks each sentence against its cited page
   (supported, contradicted or not in the source) and whether the question was actually
   answered. If not, Course Compass searches once more, more widely, before giving up.
6. **Word and number check.** A deterministic check flags any number in the answer that
   does not appear on the cited page.

**Limits you should know**

- Four curricula from one university; they can change. The English versions say they are
  not legally binding. Check the official documents before decisions.
- The second reader is itself a model and can be wrong. The evaluation in the repository
  measures how often it catches planted errors.
- Questions and excerpts are sent to the model provider (OpenAI). Don't enter personal data.
- This is a student hackathon prototype (AI OpenBuild 2026), not an official university service.
""")
    if engine is not None and engine.stats:
        st.caption("This server since start: " + ", ".join(
            f"{k.replace('_', ' ')} = {v}" for k, v in sorted(engine.stats.items())))
