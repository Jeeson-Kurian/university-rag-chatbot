"""Offline retrieval / abstention evaluation on the labelled curriculum question set.

No credentials or network. Measures the deterministic pipeline only (BM25,
glossary, coverage gate, extractive answer, grounding screen). It does NOT
measure LLM answer quality.

Usage:  python scripts/evaluate.py [--write]   (--write refreshes eval/RESULTS.md)
"""
from __future__ import annotations

from collections import Counter
from math import log
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from Code.course_core import CourseAssistant, normalise  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
K = 4
# Regression floors for CI (set just below the measured values recorded in eval/RESULTS.md).
FLOORS = {"hit_at_4": 0.85, "abstention_accuracy": 0.85, "false_abstention_rate_max": 0.10}

_LEGACY_TOKEN = re.compile(r"[a-z0-9]+")
_LEGACY_STOP = frozenset(
    "a an and are as at be can do does for from how i in into is it me my of on "
    "or our the their there these this to what when where which who why will with "
    "you your about find tell show please course programme program university".split())


def legacy_rank(assistant: CourseAssistant, question: str, department: str):
    """Re-implementation of the pre-v3 scorer (commit 56814ad) for a baseline."""
    terms = {t for t in _LEGACY_TOKEN.findall(question.lower())
             if t not in _LEGACY_STOP and len(t) > 1}
    docs = assistant.by_dept[department]
    df = Counter(t for p in docs for t in {t for t in _LEGACY_TOKEN.findall(p.text.lower())
                                          if t not in _LEGACY_STOP and len(t) > 1})
    scored = []
    for p in docs:
        counts = Counter(_LEGACY_TOKEN.findall(p.text.lower()))
        common = terms.intersection(counts)
        if not common:
            continue
        score = sum((1.0 + log(counts[t])) * log(1.0 + (len(docs) + 1) / (df[t] + 1))
                    for t in common) + len(common) / len(terms)
        scored.append((p, score))
    scored.sort(key=lambda item: (-item[1], item[0].identifier))
    return [p for p, _ in scored[:K]]


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def load_questions():
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line]


def validate_labels(assistant, questions):
    """Every answerable label's keyword must occur on one of its expected pages."""
    pages = {}
    for p in assistant.passages:
        pages.setdefault((p.document, p.page), []).append(p.text)
    problems = []
    for q in questions:
        if not q["answerable"]:
            continue
        found = any(flat(q["evidence_keyword"]) in flat(" ".join(pages.get((d, pg), [])))
                    for d, pg in q["expected"])
        if not found:
            problems.append(q["id"])
    return problems


def is_hit(passage, expected):
    return any(passage.document == d and passage.page == pg for d, pg in expected)


def score_system(name, questions, rank_fn):
    rows = []
    for q in questions:
        ranked = rank_fn(q)
        hit_rank = next((i for i, p in enumerate(ranked, 1) if is_hit(p, q["expected"])), None)
        keyword = (q["answerable"] and any(flat(q["evidence_keyword"]) in flat(p.text) for p in ranked))
        rows.append({"id": q["id"], "kind": q["kind"], "language": q["language"],
                     "answerable": q["answerable"], "abstained": not ranked,
                     "hit_rank": hit_rank, "keyword_in_top4": bool(keyword)})
    return name, rows


def summarise(rows):
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    n = len(ans) or 1
    return {
        "answerable": len(ans),
        "unanswerable": len(una),
        "hit_at_1": round(sum(r["hit_rank"] == 1 for r in ans) / n, 3),
        "hit_at_4": round(sum(r["hit_rank"] is not None for r in ans) / n, 3),
        "mrr_at_4": round(sum(1 / r["hit_rank"] for r in ans if r["hit_rank"]) / n, 3),
        "evidence_keyword_at_4": round(sum(r["keyword_in_top4"] for r in ans) / n, 3),
        "false_abstention_rate": round(sum(r["abstained"] for r in ans) / n, 3),
        "abstention_accuracy": round(sum(r["abstained"] for r in una) / (len(una) or 1), 3),
    }


def by_kind(rows):
    groups = {}
    for r in rows:
        key = "unanswerable" if not r["answerable"] else (
            "german_question" if r["language"] == "de" else r["kind"])
        groups.setdefault(key, []).append(r)
    return {k: summarise(v) for k, v in sorted(groups.items())}


def main(write: bool = False) -> int:
    questions = load_questions()
    full = CourseAssistant(ROOT / "data", use_environment_key=False)
    no_gloss = CourseAssistant(ROOT / "data", use_environment_key=False, use_glossary=False)
    bad_labels = validate_labels(full, questions)

    systems = [
        score_system("legacy_baseline", questions,
                     lambda q: legacy_rank(full, q["question"], q["department"])),
        score_system("bm25_no_glossary", questions,
                     lambda q: no_gloss.retrieve(q["question"], q["department"])[0]),
        score_system("course_compass_v3", questions,
                     lambda q: full.retrieve(q["question"], q["department"])[0]),
    ]
    summary = {name: summarise(rows) for name, rows in systems}
    breakdown = by_kind(systems[-1][1])

    sweep = []
    for threshold in (0.0, 0.2, 0.35, 0.5, 0.6, 0.7):
        tuned = CourseAssistant(ROOT / "data", use_environment_key=False, min_coverage=threshold)
        s = summarise(score_system("t", questions,
                                   lambda q: tuned.retrieve(q["question"], q["department"])[0])[1])
        sweep.append({"min_coverage": threshold, "hit_at_4": s["hit_at_4"],
                      "false_abstention_rate": s["false_abstention_rate"],
                      "abstention_accuracy": s["abstention_accuracy"]})

    answer_rows = []
    for q in questions:
        if not q["answerable"]:
            continue
        result = full.ask(q["question"], q["department"])
        answer_rows.append({
            "id": q["id"],
            "mode": result["mode"],
            "keyword_in_answer": flat(q["evidence_keyword"]) in flat(result["answer"]),
            "grounding": (result["grounding"] or {}).get("verdict"),
        })
    n = len(answer_rows) or 1
    extractive = {
        "answers": len(answer_rows),
        "keyword_in_extractive_answer": round(sum(r["keyword_in_answer"] for r in answer_rows) / n, 3),
        "grounding_passed": round(sum(r["grounding"] == "passed" for r in answer_rows) / n, 3),
    }
    v3_rows = systems[-1][1]
    failures = [r for r in v3_rows
                if (r["answerable"] and r["hit_rank"] is None) or (not r["answerable"] and not r["abstained"])]

    report = {
        "scope": "offline deterministic retrieval + extractive answers; not LLM accuracy",
        "questions": len(questions),
        "label_validation_failures": bad_labels,
        "systems": summary,
        "v3_by_question_type": breakdown,
        "coverage_threshold_sweep": sweep,
        "extractive_answers": extractive,
        "v3_failures": failures,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if write:
        (ROOT / "eval" / "results.json").write_text(
            json.dumps({**report, "per_question": v3_rows, "answers": answer_rows},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        (ROOT / "eval" / "RESULTS.md").write_text(render_markdown(report), encoding="utf-8")

    v3 = summary["course_compass_v3"]
    ok = (not bad_labels
          and v3["hit_at_4"] >= FLOORS["hit_at_4"]
          and v3["abstention_accuracy"] >= FLOORS["abstention_accuracy"]
          and v3["false_abstention_rate"] <= FLOORS["false_abstention_rate_max"])
    return 0 if ok else 1


def render_markdown(r) -> str:
    def pct(x):
        return f"{x * 100:.1f}%"
    lines = [
        "# Evaluation results (generated by `python scripts/evaluate.py --write`)",
        "",
        f"Scope: {r['scope']}. {r['questions']} questions "
        f"({r['systems']['course_compass_v3']['answerable']} answerable, "
        f"{r['systems']['course_compass_v3']['unanswerable']} unanswerable). "
        f"Label validation failures: {len(r['label_validation_failures'])}.",
        "",
        "Questions were drafted with an AI assistant (Claude) from the four curriculum files, "
        "not written by students. Labels are checked automatically: each label's evidence "
        "keyword must occur on its expected page. This is a development set: the coverage "
        "threshold and glossary were chosen while looking at it, so the numbers are optimistic, "
        "not held-out. The unanswerable group is small (8 questions).",
        "",
        "## Retrieval and abstention",
        "",
        "| System | Hit@1 | Hit@4 | MRR@4 | Evidence keyword@4 | False abstention | Correct abstention |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, s in r["systems"].items():
        lines.append(f"| {name} | {pct(s['hit_at_1'])} | {pct(s['hit_at_4'])} | {s['mrr_at_4']:.3f} | "
                     f"{pct(s['evidence_keyword_at_4'])} | {pct(s['false_abstention_rate'])} | "
                     f"{pct(s['abstention_accuracy'])} |")
    lines += ["", "## Course Compass v3 by question type", "",
              "| Type | n | Hit@4 | False abstention | Correct abstention |", "|---|---|---|---|---|"]
    for kind, s in r["v3_by_question_type"].items():
        n = s["unanswerable"] if kind == "unanswerable" else s["answerable"]
        lines.append(f"| {kind} | {n} | {pct(s['hit_at_4']) if s['answerable'] else '-'} | "
                     f"{pct(s['false_abstention_rate']) if s['answerable'] else '-'} | "
                     f"{pct(s['abstention_accuracy']) if s['unanswerable'] else '-'} |")
    lines += ["", "## Evidence-coverage gate sweep", "",
              "| min_coverage | Hit@4 | False abstention | Correct abstention |", "|---|---|---|---|"]
    for row in r["coverage_threshold_sweep"]:
        lines.append(f"| {row['min_coverage']} | {pct(row['hit_at_4'])} | "
                     f"{pct(row['false_abstention_rate'])} | {pct(row['abstention_accuracy'])} |")
    e = r["extractive_answers"]
    lines += ["", "## Free extractive answers (no model provider)", "",
              f"- Answerable questions answered: {e['answers']}",
              f"- Evidence keyword appears in the extractive answer: {pct(e['keyword_in_extractive_answer'])}",
              f"- Grounding screen passed: {pct(e['grounding_passed'])}",
              "", "## Remaining failures (v3)", ""]
    if r["v3_failures"]:
        for f in r["v3_failures"]:
            what = "retrieved evidence for an unanswerable question" if not f["answerable"] else (
                "abstained on an answerable question" if f["abstained"] else "expected page not in top 4")
            lines.append(f"- `{f['id']}` ({f['kind']}): {what}")
    else:
        lines.append("- None on this set.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main(write="--write" in sys.argv))
