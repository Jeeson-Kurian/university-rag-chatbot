"""Course Compass engine: evidence-first curriculum answers, checked by a second reader.

Pipeline (every step scoped to one study programme):
  1. Page-aware ingestion of curated PDF/TXT files into bounded passages.
  2. Question understanding: in AI mode a language model turns a question in any language
     into English and German curriculum terms; offline, a curated EN<->DE glossary does a
     smaller version of the same job.
  3. BM25 keyword ranking over those terms, then an evidence-coverage gate that abstains
     *before* any answer is written when the best passage covers too little of the question.
  4. Optional semantic re-ranking (OpenAI embeddings + FAISS). Semantic similarity can only
     re-order keyword candidates, never introduce new evidence.
  5. Answer: a citation-constrained model answer (AI mode) or copied source sentences
     (free mode), followed by
  6. Checks: a lexical/numeric screen on every sentence, and in AI mode an independent
     second-reader model that judges each claim and whether the question was answered.
     If the second reader says the question was not answered, the engine looks once more
     with a wider search before giving up.
  7. Compare: the same question across all programmes, with a short contrast.

The repository's historical pickle/FAISS index is never deserialised.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from hashlib import sha256
from math import log
from pathlib import Path
import json
import os
import re
import threading
from typing import Any

from pypdf import PdfReader

from . import ai_steps
from .ai_steps import NO_EVIDENCE
from .grounding import CITATION_RE, verify
from .text_tools import clean_sentence, content_terms, expand, numbers, sentences, stem, tokens

ROOT = Path(__file__).resolve().parent.parent
DEPARTMENTS = {
    "AIandCybersecurity": "AI and Cybersecurity (Master)",
    "Informatics": "Informatics (Master)",
    "English": "Worlds of English (Master, German curriculum)",
    "Business": "International Business and Economics (Bachelor)",
}
SHORT_NAMES = {
    "AIandCybersecurity": "AI & Cybersecurity",
    "Informatics": "Informatics",
    "English": "Worlds of English",
    "Business": "Int. Business & Economics",
}
MAX_FILE_BYTES = 6 * 1024 * 1024
MAX_PDF_PAGES = 150
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
TOP_K = 4
WIDE_K = 8                  # second look after the second reader says "not answered"
EXPANSION_WEIGHT = 0.7
MIN_COVERAGE = 0.35         # idf-weighted share of question terms found in best passage
EXTRA_LINE_RATIO = 0.75     # extractive answer: extra lines must score >= 75% of the best
BM25_K1, BM25_B = 1.5, 0.75

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_REVIEW_MODEL = "gpt-4.1-mini"      # a different model family member checks the answer
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DAILY_BUDGET_USD = 2.0
# USD per 1M tokens (input, output), from the OpenAI pricing page, checked 2026-11-12.
PRICES = {
    "gpt-5-nano": (0.05, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


@dataclass(frozen=True)
class Passage:
    identifier: str
    department: str
    document: str
    page: int | None
    text: str


HYPHEN_BREAK_RE = re.compile(r"(?<=[a-zäöüß])-[ \t]*\n[ \t]*(?=[a-zäöüß])")


def normalise(text: str) -> str:
    """Re-join words hyphenated across PDF line breaks ("Wör-\\ntern" -> "Wörtern")."""
    return re.sub(r"[ \t]+", " ", HYPHEN_BREAK_RE.sub("", text)).strip()


def split_passages(text: str):
    """Yield bounded, overlapping pieces; offsets are only for chunk identity."""
    text = normalise(text)
    position = 0
    while position < len(text):
        end = min(position + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = text.rfind(" ", position + CHUNK_SIZE // 2, end)
            if boundary > position:
                end = boundary
        piece = text[position:end].strip()
        if piece:
            yield position, piece
        if end >= len(text):
            break
        position = max(position + 1, end - CHUNK_OVERLAP)


def load_passages(data_dir: Path) -> list[Passage]:
    """Only curated local .txt and .pdf files in the known programme directories."""
    passages = []
    root = data_dir.resolve()
    for department in DEPARTMENTS:
        folder = root / department
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".txt", ".pdf"} or not path.is_file():
                continue
            if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                if path.suffix.lower() == ".pdf":
                    reader = PdfReader(str(path), strict=False)
                    pages = [(i + 1, p.extract_text() or "") for i, p in
                             enumerate(reader.pages[:MAX_PDF_PAGES])]
                else:
                    pages = [(None, path.read_text(encoding="utf-8"))]
            except Exception as exc:
                # Filename and error class only: no raw document text in errors.
                raise ValueError(f"Could not parse {path.name}: {type(exc).__name__}") from exc
            for page, text in pages:
                for offset, piece in split_passages(text):
                    token = f"{department}:{path.name}:{page}:{offset}"
                    passages.append(Passage(
                        sha256(token.encode("utf-8")).hexdigest()[:16],
                        department, path.name, page, piece,
                    ))
    return passages


class _BM25:
    """Okapi BM25 over one programme's passages (term frequencies precomputed)."""

    def __init__(self, docs: list[Passage]):
        self.docs = docs
        self.tf = [Counter(tokens(p.text)) for p in docs]
        self.lengths = [sum(c.values()) for c in self.tf]
        self.avgdl = (sum(self.lengths) / len(docs)) if docs else 0.0
        self.df = Counter(t for c in self.tf for t in c)

    def idf(self, term: str) -> float:
        n, df = len(self.docs), self.df.get(term, 0)
        return log(1.0 + (n - df + 0.5) / (df + 0.5))

    def term_score(self, i: int, term: str) -> float:
        f = self.tf[i].get(term, 0)
        if not f:
            return 0.0
        norm = BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[i] / (self.avgdl or 1.0))
        return self.idf(term) * f * (BM25_K1 + 1) / (f + norm)


def usage_cost(model: str | None, prompt_tokens: int, completion_tokens: int) -> float | None:
    price = PRICES.get(model or "")
    if price is None:
        return None
    return round((prompt_tokens * price[0] + completion_tokens * price[1]) / 1_000_000, 8)


class DailyBudget:
    """Process-wide spending cap for a public demo. Once the estimated spend for the day
    reaches the cap, the app answers in free mode instead of calling the provider."""

    def __init__(self, limit_usd: float | None):
        self.limit = limit_usd
        self.day = date.today()
        self.spent = 0.0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        if date.today() != self.day:
            self.day, self.spent = date.today(), 0.0

    def available(self) -> bool:
        with self._lock:
            self._roll()
            return self.limit is None or self.spent < self.limit

    def add(self, amount: float | None) -> None:
        with self._lock:
            self._roll()
            self.spent += amount or 0.0


def _env_float(name: str, default: float | None) -> float | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    if value.strip().lower() in {"none", "off", "unlimited"}:
        return None
    return float(value)


class CourseAssistant:
    """Retrieval is deterministic; every model call is optional, metered and checked."""

    def __init__(
        self,
        data_dir: Path | None = None,
        client: Any | None = None,
        use_environment_key: bool = True,
        vector_enabled: bool = True,
        cache_dir: Path | None = None,
        min_coverage: float | None = None,
        use_glossary: bool = True,
        ai_query: bool = True,
        second_reader: bool = True,
        daily_budget_usd: float | None | str = "env",
    ) -> None:
        self.data_dir = Path(data_dir or ROOT / "data")
        self.passages = load_passages(self.data_dir)
        self.by_dept = {
            name: [p for p in self.passages if p.department == name]
            for name in DEPARTMENTS
        }
        self._bm25 = {name: _BM25(docs) for name, docs in self.by_dept.items()}
        self.client = client
        if client is None and use_environment_key and os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI  # honours OPENAI_BASE_URL for compatible servers
            self.client = OpenAI(timeout=30.0, max_retries=1)
        self.vector_enabled = vector_enabled and self.client is not None
        self.ai_query = ai_query and self.client is not None
        self.second_reader = second_reader and self.client is not None
        self.chat_model = os.getenv("UNIVERSITY_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.review_model = os.getenv("UNIVERSITY_REVIEW_MODEL", DEFAULT_REVIEW_MODEL)
        self.fallback_model = os.getenv("UNIVERSITY_FALLBACK_MODEL") or None
        self.embedding_model = os.getenv("UNIVERSITY_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.cache_dir = Path(cache_dir or os.getenv("UNIVERSITY_CACHE_DIR", str(ROOT / ".cache")))
        self.min_coverage = MIN_COVERAGE if min_coverage is None else min_coverage
        self.use_glossary = use_glossary
        if daily_budget_usd == "env":
            daily_budget_usd = _env_float("DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD)
        self.budget = DailyBudget(daily_budget_usd)  # type: ignore[arg-type]
        self._vector_indexes: dict[str, Any] = {}
        self._query_vectors: OrderedDict[str, Any] = OrderedDict()
        self._understood: OrderedDict[str, dict] = OrderedDict()
        self._answers: OrderedDict[tuple, dict] = OrderedDict()
        self._lock = threading.Lock()
        self.stats: Counter = Counter()

    # ------------------------------------------------------------------ model plumbing
    @property
    def ai_available(self) -> bool:
        return self.client is not None and self.budget.available()

    def _chat(self, model: str, messages: list[dict], json_mode: bool = False,
              max_tokens: int = 450):
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if model.startswith("gpt-5"):
            # Reasoning-family models: no temperature; keep reasoning minimal for a lookup task.
            kwargs["reasoning_effort"] = os.getenv("UNIVERSITY_REASONING_EFFORT", "minimal")
            kwargs["max_completion_tokens"] = max_tokens + 800
        else:
            kwargs["temperature"] = 0
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        prompt_t = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_t = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = usage_cost(model, prompt_t, completion_t)
        self.budget.add(cost)
        with self._lock:
            self.stats["chat_calls"] += 1
            self.stats["chat_prompt_tokens"] += prompt_t
            self.stats["chat_completion_tokens"] += completion_t
        text = (response.choices[0].message.content or "").strip()
        return text, {"model": model, "prompt_tokens": prompt_t,
                      "completion_tokens": completion_t, "estimated_cost_usd": cost}

    # ------------------------------------------------------------------ understanding
    def understand(self, question: str) -> dict:
        """Model-generated search terms for a question (cached). Empty dict if unavailable."""
        if not (self.ai_query and self.ai_available):
            return {}
        key = " ".join(question.lower().split())
        with self._lock:
            if key in self._understood:
                return self._understood[key]
        try:
            text, usage = self._chat(self.chat_model, [
                {"role": "system", "content": ai_steps.UNDERSTAND_SYSTEM},
                {"role": "user", "content": question}], json_mode=True, max_tokens=300)
        except Exception as exc:  # retrieval still works with the offline glossary
            return {"error": type(exc).__name__}
        language, terms = ai_steps.parse_terms(ai_steps.parse_json(text))
        result = {"language": language, "terms": terms, "usage": usage}
        with self._lock:
            self._understood[key] = result
            while len(self._understood) > 512:
                self._understood.popitem(last=False)
        return result

    # ------------------------------------------------------------------ retrieval
    def _query_terms(self, question: str, understood: dict | None = None
                     ) -> list[tuple[str, float, str]]:
        """(term, weight, original_term) triples including glossary and model expansions."""
        triples: list[tuple[str, float, str]] = []
        originals = content_terms(question)
        for term in originals:
            triples.append((term, 1.0, term))
            if self.use_glossary:
                triples.extend((alt, EXPANSION_WEIGHT, term) for alt in expand(term))
        for word, alternatives in (understood or {}).get("terms", []):
            word_terms = content_terms(word)
            if not word_terms:
                continue
            original = word_terms[0]
            if original not in originals:
                continue  # a model term must stand for a word the student actually wrote
            for alternative in alternatives:
                for alt in content_terms(alternative):
                    if alt != original:
                        triples.append((alt, EXPANSION_WEIGHT, original))
        return list(dict.fromkeys(triples))

    @staticmethod
    def _key_words(question: str, understood: dict | None) -> set[str]:
        originals = set(content_terms(question))
        chosen = set()
        for word, _ in (understood or {}).get("terms", []):
            chosen.update(t for t in content_terms(word) if t in originals)
        return chosen

    def lexical_ranking(self, question: str, department: str, understood: dict | None = None
                        ) -> list[tuple[Passage, float, float]]:
        """Passages with (BM25 score, idf-weighted question coverage), best first."""
        bm25 = self._bm25[department]
        triples = self._query_terms(question, understood)
        originals = list(dict.fromkeys(orig for _, _, orig in triples))
        if not originals or not bm25.docs:
            return []
        weight_of = {o: bm25.idf(o) for o in originals}
        key_words = self._key_words(question, understood)
        if key_words:
            # Words the model did not mark as content (e.g. Italian "quante", "deve") still
            # count, but only a fifth, so a non-English question is not blocked by its
            # function words. The model can only choose among words the student wrote.
            weight_of = {o: w * (1.0 if o in key_words else 0.2) for o, w in weight_of.items()}
        total = sum(weight_of.values()) or 1.0
        results = []
        for i, passage in enumerate(bm25.docs):
            score, covered = 0.0, set()
            for term, weight, original in triples:
                s = bm25.term_score(i, term)
                if s:
                    score += weight * s
                    covered.add(original)
            if score > 0:
                coverage = sum(weight_of[o] for o in covered) / total
                results.append((passage, score, round(coverage, 4)))
        results.sort(key=lambda r: (-r[1], r[0].identifier))
        return results

    def _embed(self, texts: list[str]):
        import numpy as np

        vectors, tokens_used = [], 0
        for start in range(0, len(texts), 64):
            batch_in = texts[start:start + 64]
            response = self.client.embeddings.create(model=self.embedding_model, input=batch_in)
            batch = sorted(response.data, key=lambda item: item.index)
            if len(batch) != len(batch_in):
                raise ValueError("Embedding provider returned an incomplete batch")
            vectors.extend(item.embedding for item in batch)
            usage = getattr(response, "usage", None)
            tokens_used += int(getattr(usage, "total_tokens", 0) or 0)
        self.stats["embedding_tokens"] += tokens_used
        self.budget.add(usage_cost(self.embedding_model, tokens_used, 0))
        array = np.asarray(vectors, dtype="float32")
        if array.ndim != 2 or not np.isfinite(array).all():
            raise ValueError("Invalid embedding matrix")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        return array / np.where(norms == 0, 1.0, norms)

    def _passage_matrix(self, department: str):
        """Embeddings for a programme, cached on disk as .npy keyed by content hash."""
        import numpy as np

        docs = self.by_dept[department]
        digest = sha256((self.embedding_model + "\n" + "\n".join(
            p.identifier + sha256(p.text.encode()).hexdigest() for p in docs)).encode()).hexdigest()[:24]
        path = self.cache_dir / "embeddings" / f"{department}-{digest}.npy"
        if path.is_file():
            matrix = np.load(path, allow_pickle=False)
            if matrix.ndim == 2 and matrix.shape[0] == len(docs):
                self.stats["embedding_cache_hits"] += 1
                return matrix
        matrix = self._embed([p.text for p in docs])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, matrix, allow_pickle=False)
            (path.with_suffix(".json")).write_text(json.dumps({
                "model": self.embedding_model, "department": department,
                "passages": len(docs), "dim": int(matrix.shape[1])}), encoding="utf-8")
        except OSError:
            pass  # read-only deployments still work, just without persistence
        return matrix

    def _vector(self, question: str, department: str, limit: int) -> list[Passage]:
        import faiss

        with self._lock:
            if department not in self._vector_indexes:
                docs = self.by_dept[department]
                if not docs:
                    return []
                matrix = self._passage_matrix(department)
                index = faiss.IndexFlatIP(matrix.shape[1])
                index.add(matrix)
                self._vector_indexes[department] = (index, docs)
            index, docs = self._vector_indexes[department]
            query = self._query_vectors.get(question)
        if query is None:
            query = self._embed([question])
            with self._lock:
                self._query_vectors[question] = query
                while len(self._query_vectors) > 512:
                    self._query_vectors.popitem(last=False)
        if query.shape[1] != index.d:
            raise ValueError("Embedding dimensions changed")
        _, positions = index.search(query, min(limit, len(docs)))
        return [docs[int(i)] for i in positions[0] if int(i) >= 0]

    def retrieve(self, question: str, department: str, k: int = TOP_K,
                 understood: dict | None = None):
        """Return (passages, retrieval_mode, warning). Empty list means abstain."""
        if department not in DEPARTMENTS:
            raise ValueError("Unsupported department")
        lexical = self.lexical_ranking(question, department, understood)
        if not lexical or lexical[0][2] < self.min_coverage:
            return [], "lexical", None
        candidates = lexical[: max(12, k * 4)]
        ranks = {p.identifier: 1.0 / (60 + i) for i, (p, _, _) in enumerate(candidates)}
        passage_map = {p.identifier: p for p, _, _ in candidates}
        mode, warning = "lexical", None
        if self.vector_enabled and self.budget.available():
            try:
                semantic = self._vector(question, department, max(12, k * 4))
                for i, p in enumerate(semantic):
                    if p.identifier in ranks:  # semantic similarity alone is not evidence
                        ranks[p.identifier] += 1.0 / (60 + i)
                mode = "hybrid"
            except Exception as exc:
                warning = f"Vector lookup unavailable ({type(exc).__name__}); used keyword search."
        selected = sorted(ranks, key=lambda ident: (-ranks[ident], ident))[:k]
        return [passage_map[ident] for ident in selected], mode, warning

    # ------------------------------------------------------------------ answering
    def _extractive(self, question: str, department: str, selected: list[Passage],
                    understood: dict | None = None) -> str:
        """Best-matching sentence from up to three passages, each with its citation."""
        bm25 = self._bm25[department]
        triples = self._query_terms(question, understood)
        scored = []
        for idx, passage in enumerate(selected[:3], start=1):
            best, best_score, best_cover = None, 0.0, set()
            for sentence in sentences(passage.text):
                vocab = set(tokens(sentence))
                score = sum(w * bm25.idf(t) for t, w, _ in triples if t in vocab)
                if score > best_score and len(sentence) <= 400:
                    best, best_score = sentence, score
                    best_cover = {o for t, _, o in triples if t in vocab}
            if best:
                scored.append((best_score, idx, clean_sentence(best), best_cover))
        if not scored:
            return f"- {clean_sentence(selected[0].text[:320])} [S1]"
        top_score, _, _, top_cover = max(scored, key=lambda row: row[0])
        # An extra line must either cover the question words of the best line (all but the
        # least informative one) or add a question word the best line lacks; so a thesis
        # question does not also return the degree total, but "seminar" can complete a list.
        required = set(sorted(top_cover, key=bm25.idf)[1:])
        lines = [f"- {text} [S{idx}]" for score, idx, text, cover in scored
                 if text and score >= EXTRA_LINE_RATIO * top_score
                 and (required <= cover or cover - top_cover)]
        return "\n".join(lines) or f"- {clean_sentence(selected[0].text[:320])} [S1]"

    @staticmethod
    def _sources(selected: list[Passage]) -> list[dict]:
        return [{"id": f"S{i}", "document": p.document, "page": p.page,
                 "department": p.department, "excerpt": p.text[:850]}
                for i, p in enumerate(selected, start=1)]

    def _write(self, question: str, selected: list[Passage]) -> tuple[str | None, dict | None, Exception | None]:
        excerpts = "\n\n".join(
            f"[S{i}] Document: {p.document}; page: {p.page or 'text file'}\n{p.text[:850]}"
            for i, p in enumerate(selected, start=1))
        messages = [
            {"role": "system", "content": ai_steps.ANSWER_SYSTEM},
            {"role": "user", "content": f"SOURCE EXCERPTS:\n{excerpts}\n\nQUESTION:\n{question}"},
        ]
        last_error = None
        for model in [self.chat_model] + ([self.fallback_model] if self.fallback_model else []):
            try:
                text, usage = self._chat(model, messages)
                return text, usage, None
            except Exception as exc:
                last_error = exc
        return None, None, last_error

    def second_read(self, question: str, answer: str, sources: list[dict]) -> dict | None:
        """Independent model check of an answer against its cited excerpts."""
        if not (self.second_reader and self.ai_available):
            return None
        answer_sentences = [s for s in (sentences(answer) or [answer]) if s.strip()]
        excerpts = "\n\n".join(f"[{s['id']}] page {s['page'] or '-'}\n{s['excerpt']}" for s in sources)
        try:
            text, usage = self._chat(self.review_model, [
                {"role": "system", "content": ai_steps.SECOND_READER_SYSTEM},
                {"role": "user", "content": (
                    f"QUESTION:\n{question}\n\nSOURCE EXCERPTS:\n{excerpts}\n\n"
                    f"ANSWER SENTENCES:\n{ai_steps.numbered(answer_sentences)}")}],
                json_mode=True, max_tokens=500)
        except Exception as exc:
            return {"status": "unavailable", "error": type(exc).__name__}
        review = ai_steps.parse_review(ai_steps.parse_json(text), len(answer_sentences))
        if review is None:
            return {"status": "unavailable", "error": "unparseable", "usage": usage}
        for row, sentence in zip(review["sentences"], answer_sentences):
            row["sentence"] = sentence
        review.update({"status": "done", "model": self.review_model, "usage": usage})
        self.stats["second_reads"] += 1
        return review

    @staticmethod
    def verdict(grounding: dict | None, review: dict | None) -> tuple[str, str]:
        """Combine the lexical screen and the second reader into one student-facing label."""
        lexical_ok = bool(grounding) and grounding.get("verdict") == "passed"
        if review and review.get("status") == "done":
            rows = [r["verdict"] for r in review["sentences"]]
            if review["answers_question"] == "no":
                return "not_answered", "The second reader found that the cited pages do not answer this question."
            if "contradicted" in rows:
                return "contradicted", "The second reader found a statement that the cited page contradicts."
            if review["answers_question"] == "partly" or "not_in_source" in rows or not lexical_ok:
                return "check", "Partly confirmed: check the highlighted sentences against the pages."
            return "verified", "Both checks passed: every sentence matches its cited page."
        if lexical_ok:
            return "screened", "Words and numbers match the cited pages (no second reader in this mode)."
        return "check", "Some words or numbers could not be matched to the cited pages."

    def _model_answer(self, question: str, department: str, selected: list[Passage],
                      base: dict) -> dict:
        sources = self._sources(selected)
        excerpt_by_number = {i: s["excerpt"] for i, s in enumerate(sources, start=1)}
        answer, usage, error = self._write(question, selected)
        if error is not None:
            base.update({"mode": "model_error",
                         "answer": "Answer generation is temporarily unavailable; please retry.",
                         "warning": f"Provider error: {type(error).__name__}"})
            return base
        base["model"], base["usage"] = usage["model"], usage
        citations = {int(i) for i in CITATION_RE.findall(answer or "")}
        valid = bool(citations) and all(1 <= i <= len(sources) for i in citations)
        if not valid or NO_EVIDENCE in (answer or ""):
            return base  # abstained: no valid evidence trail
        cited_sources = [s for i, s in enumerate(sources, start=1) if i in citations]
        grounding = verify(answer, excerpt_by_number)
        review = self.second_read(question, answer, cited_sources)
        base.update({"answer": answer, "mode": "llm", "sources": cited_sources,
                     "grounding": grounding, "review": review})
        return base

    def ask(self, question: str, department: str, _wide: bool = False) -> dict[str, Any]:
        question = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", question).strip()
        if not 4 <= len(question) <= 800:
            raise ValueError("Question must be between 4 and 800 characters.")
        if department not in DEPARTMENTS:
            raise ValueError("Unsupported department")
        use_ai = self.ai_available
        cache_key = (department, " ".join(question.lower().split()),
                     self.chat_model if use_ai else "free")
        with self._lock:
            cached = self._answers.get(cache_key)
        if cached is not None:
            self.stats["answer_cache_hits"] += 1
            return {**cached, "cached": True}

        understood = self.understand(question) if use_ai else {}
        k = WIDE_K if _wide else TOP_K
        selected, retrieval_mode, warning = self.retrieve(question, department, k, understood)
        base: dict[str, Any] = {
            "question": question,
            "department": department,
            "retrieval_mode": retrieval_mode,
            "warning": warning,
            "sources": [],
            "mode": "abstained",
            "answer": NO_EVIDENCE,
            "grounding": None,
            "review": None,
            "verdict": "abstained",
            "verdict_text": "The documents do not cover this question, so nothing was generated.",
            "usage": None,
            "model": None,
            "cached": False,
            "searched_terms": sorted({t for t, w, _ in self._query_terms(question, understood)
                                      if w < 1.0})[:12],
            "question_language": understood.get("language"),
            "second_look": _wide,
        }
        if self.client is not None and not use_ai:
            base["warning"] = ("Today's AI budget for this public demo is used up, so this "
                               "answer was copied from the documents without a model.")
        if not selected:
            self.stats["abstained_before_model"] += 1
            return base

        if not use_ai:
            sources = self._sources(selected)
            answer = self._extractive(question, department, selected, understood)
            cited = {int(i) for i in CITATION_RE.findall(answer)}
            grounding = verify(answer, {i: s["excerpt"] for i, s in enumerate(sources, start=1)})
            base.update({"mode": "extractive", "answer": answer, "grounding": grounding,
                         "sources": [s for i, s in enumerate(sources, start=1) if i in cited]})
        else:
            base = self._model_answer(question, department, selected, base)
            review = base.get("review") or {}
            if (not _wide and base["mode"] == "llm" and review.get("status") == "done"
                    and review["answers_question"] == "no"):
                # Second look: search wider once before telling the student we failed.
                self.stats["second_looks"] += 1
                wider = self.ask(question, department, _wide=True)
                if wider["mode"] == "llm" and (wider.get("review") or {}).get("answers_question") != "no":
                    return wider
                base = wider if wider["mode"] in {"llm", "abstained"} else base

        if base["mode"] in {"llm", "extractive"}:
            base["verdict"], base["verdict_text"] = self.verdict(base["grounding"], base.get("review"))
        elif base["mode"] == "abstained":
            base["verdict"] = "abstained"
        else:
            base["verdict"], base["verdict_text"] = "error", base.get("warning") or "Provider error"
        if use_ai and base["mode"] in {"llm", "abstained"}:  # free mode is cheap: not cached
            with self._lock:
                self._answers[cache_key] = dict(base)
                while len(self._answers) > 256:
                    self._answers.popitem(last=False)
        return base

    # ------------------------------------------------------------------ compare
    def compare(self, question: str, departments: list[str] | None = None) -> dict[str, Any]:
        """Ask the same question in several programmes and contrast the checked answers."""
        departments = departments or list(DEPARTMENTS)
        for department in departments:
            if department not in DEPARTMENTS:
                raise ValueError("Unsupported department")
        if self.client is not None:  # one understanding call shared by all programmes
            self.understand(question)
        with ThreadPoolExecutor(max_workers=min(4, len(departments))) as pool:
            results = list(pool.map(lambda d: self.ask(question, d), departments))
        answered = [r for r in results if r["mode"] in {"llm", "extractive"}
                    and r["verdict"] not in {"not_answered", "contradicted"}]
        summary, usage = None, None
        if len(answered) >= 2 and self.ai_available:
            block = "\n\n".join(f"{SHORT_NAMES[r['department']]}:\n{CITATION_RE.sub('', r['answer'])}"
                                for r in answered)
            try:
                text, usage = self._chat(self.chat_model, [
                    {"role": "system", "content": ai_steps.COMPARE_SYSTEM},
                    {"role": "user", "content": f"QUESTION:\n{question}\n\nANSWERS:\n{block}"}],
                    json_mode=True, max_tokens=200)
                data = ai_steps.parse_json(text) or {}
                candidate = str(data.get("summary", "")).strip()
                # Every number in the contrast must appear in one of the checked answers.
                allowed = set().union(*(numbers(r["answer"]) for r in answered))
                if candidate and numbers(candidate) <= allowed:
                    summary = candidate[:600]
            except Exception:
                summary = None
        return {"question": question, "results": results, "summary": summary,
                "summary_usage": usage,
                "answered": [r["department"] for r in answered]}


@lru_cache(maxsize=1)
def get_assistant() -> CourseAssistant:
    """One local immutable corpus per server process; restart after changing data."""
    data_dir = Path(os.getenv("UNIVERSITY_DATA_DIR", str(ROOT / "data")))
    return CourseAssistant(data_dir=data_dir)


def document_path(department: str, document: str, data_dir: Path | None = None) -> Path:
    """Resolve a cited document inside its programme folder (no path traversal)."""
    if department not in DEPARTMENTS:
        raise ValueError("Unsupported department")
    folder = (Path(data_dir or os.getenv("UNIVERSITY_DATA_DIR", str(ROOT / "data"))) / department).resolve()
    path = (folder / document).resolve()
    if path.parent != folder or not path.is_file():
        raise ValueError("Unknown document")
    return path


__all__ = ["CourseAssistant", "DEPARTMENTS", "SHORT_NAMES", "NO_EVIDENCE", "Passage",
           "load_passages", "normalise", "get_assistant", "document_path", "usage_cost", "stem"]
