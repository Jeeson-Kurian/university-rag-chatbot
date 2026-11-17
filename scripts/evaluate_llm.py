"""Live evaluation of AI mode (needs OPENAI_API_KEY; the full run costs well under $1).

Three parts:
  A. Answers on both question sets: the 53-question development set (used while building)
     and the 26-question held-out set (frozen before any system ran on it). Free mode and
     AI mode are scored on the same questions, so the gain from the model steps is visible.
  B. Planted errors: correct AI answers are corrupted on purpose (a changed number, an
     answer to a different question, an invented extra rule) and the checks must catch them.
     The untouched answers measure false alarms.
  C. Compare mode: questions whose correct answer differs by programme.

Writes eval/LLM_RESULTS.md and eval/llm_results.json. Exit status 1 on provider errors.

Usage:  OPENAI_API_KEY=... python scripts/evaluate_llm.py [--quick]
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from Code.course_core import CourseAssistant, usage_cost  # noqa: E402
from Code.grounding import verify  # noqa: E402

SETS = {"development": ROOT / "eval" / "questions.jsonl",
        "held_out": ROOT / "eval" / "heldout_questions.jsonl"}
CATCHING = {"contradicted", "not_answered", "check"}
COMPARE_CASES = [
    {"question": "How many ECTS credits does the Master's thesis comprise?",
     "expect": {"AIandCybersecurity": "23", "Informatics": "25", "English": "30"}},
    {"question": "What English level is required for admission?",
     "expect": {"AIandCybersecurity": "B2", "English": "C1", "Business": "B2"}},
    {"question": "How many ECTS credits must be completed in open electives?",
     "expect": {"AIandCybersecurity": "6", "Informatics": "6", "Business": "10"}},
]


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def fact_in_answer(keyword: str, answer: str) -> bool:
    """Keyword match tolerant of number formatting and German/English unit spelling."""
    a, k = flat(answer), flat(keyword)
    if k in a:
        return True
    nums = re.findall(r"\d+(?:[.,]\d+)*", k)
    if nums:  # numeric facts: every number must appear (30.000 == 30,000 == 30000)
        norm = lambda s: re.sub(r"[.,]", "", s)  # noqa: E731
        answer_nums = {norm(n) for n in re.findall(r"\d+(?:[.,]\d+)*", a)}
        return all(norm(n) in answer_nums for n in nums)
    return False


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def total_cost(result: dict) -> float:
    cost = 0.0
    for usage in (result.get("usage"), (result.get("review") or {}).get("usage")):
        cost += (usage or {}).get("estimated_cost_usd") or 0.0
    return cost


GRADER_SYSTEM = (
    "You grade a curriculum assistant. Given a question, the expected fact (in English or "
    "German) and the assistant's answer (in any language), decide whether the answer states "
    "the expected fact correctly. Translations and paraphrases count; a different number or "
    "a missing fact does not. Reply with JSON only: {\"correct\": true|false}")


def graded(assistant: CourseAssistant, question: str, expected: str, answer: str) -> bool:
    """Language-independent check by a model that sees the expected fact (reported separately)."""
    try:
        text, _ = assistant._chat(assistant.review_model, [
            {"role": "system", "content": GRADER_SYSTEM},
            {"role": "user", "content": f"QUESTION: {question}\nEXPECTED FACT: {expected}\n"
                                        f"ANSWER: {answer}"}], json_mode=True, max_tokens=20)
        return bool((json.loads(text) or {}).get("correct"))
    except Exception:
        return False


def run_set(assistant: CourseAssistant, questions: list[dict], label: str) -> list[dict]:
    rows = []
    for q in questions:
        r = assistant.ask(q["question"], q["department"])
        cited = any([s["document"], s["page"]] in q["expected"] for s in r["sources"])
        review = r.get("review") or {}
        rows.append({
            "id": q["id"], "kind": q["kind"], "language": q["language"],
            "answerable": q["answerable"], "mode": r["mode"], "verdict": r.get("verdict"),
            "fact_in_answer": bool(q["answerable"] and fact_in_answer(q["evidence_keyword"], r["answer"])),
            "fact_graded": None,
            "cited_expected_page": bool(q["answerable"] and cited),
            "grounding": (r.get("grounding") or {}).get("verdict"),
            "reader_answers_question": review.get("answers_question"),
            "second_look": r.get("second_look", False),
            "searched_terms": r.get("searched_terms", []),
            "cost_usd": total_cost(r),
            "question": q["question"], "answer": r["answer"],
            "sources": [[s["document"], s["page"]] for s in r["sources"]],
            "warning": r.get("warning"),
        })
        row = rows[-1]
        row["fact_graded"] = row["fact_in_answer"]
        if q["answerable"] and not row["fact_in_answer"] and r["mode"] in {"llm", "extractive"} \
                and getattr(assistant, "client", None) is not None and hasattr(assistant, "_chat"):
            row["fact_graded"] = graded(assistant, q["question"], q["evidence_keyword"], r["answer"])
        print(f"[{label}] {q['id']}: {row['mode']}/{row['verdict']} fact={row['fact_in_answer']} "
              f"cite={row['cited_expected_page']}", flush=True)
    return rows


def summarise(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    n, m = len(ans) or 1, len(una) or 1
    correct = [r for r in ans if r["fact_in_answer"] and r["cited_expected_page"]]
    trusted = [r for r in ans if r["verdict"] in {"verified", "screened"}]
    return {
        "answerable": len(ans), "unanswerable": len(una),
        "correct_with_right_page": round(len(correct) / n, 3),
        "correct_any_language": round(sum(bool(r.get("fact_graded")) and r["cited_expected_page"]
                                          for r in ans) / n, 3),
        "fact_in_answer": round(sum(r["fact_in_answer"] for r in ans) / n, 3),
        "cites_expected_page": round(sum(r["cited_expected_page"] for r in ans) / n, 3),
        "false_abstention": round(sum(r["mode"] == "abstained" for r in ans) / n, 3),
        "correct_abstention": round(sum(r["mode"] == "abstained" for r in una) / m, 3),
        # Of the answers shown as checked, how many were actually right?
        "precision_of_checked_answers": round(
            sum(r["fact_in_answer"] for r in trusted) / (len(trusted) or 1), 3),
        "checked_answers": len(trusted),
        "second_looks": sum(r["second_look"] for r in rows),
        "model_errors": sum(r["mode"] == "model_error" for r in rows),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 5),
    }


def by_kind(rows: list[dict]) -> dict:
    out = {}
    for kind in sorted({r["kind"] for r in rows}):
        out[kind] = summarise([r for r in rows if r["kind"] == kind])
    return out


# ------------------------------------------------------------------ planted errors
def corruptions(answer: str, keyword: str, other_answer: str | None) -> list[tuple[str, str]]:
    out = []
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", keyword) or re.findall(r"\b\d+\b", answer)
    for n in numbers[:1]:
        if n in answer:
            value = float(n.replace(",", "."))
            changed = str(int(value + max(2, value // 4)))  # e.g. 23 -> 28, 120 -> 150
            out.append(("changed_number", answer.replace(n, changed, 1)))
    if other_answer:
        out.append(("answer_to_other_question", other_answer))
    out.append(("invented_rule", answer.rstrip() +
                " Students can also complete this requirement entirely online without approval. [S1]"))
    return out


def planted_errors(assistant: CourseAssistant, questions: dict, rows: list[dict],
                   results: dict) -> dict:
    correct = [r for r in rows if r["answerable"] and r["mode"] == "llm"
               and r["fact_in_answer"] and r["cited_expected_page"]]
    by_dept = {}
    for r in correct:
        by_dept.setdefault(questions[r["id"]]["department"], []).append(r)
    cases = []
    for r in correct:
        q = questions[r["id"]]
        result = results[r["id"]]
        excerpts = {int(s["id"][1:]): s["excerpt"] for s in result["sources"]}
        # The other answer must cite the same source numbers to stay citation-valid.
        siblings = [x for x in by_dept[q["department"]] if x["id"] != r["id"]]
        other = None
        for sibling in siblings:
            cand = results[sibling["id"]]["answer"]
            if all(int(i) in excerpts for i in re.findall(r"\[S(\d+)\]", cand)):
                other = cand
                break
        variants = [("original", r["answer"])] + corruptions(r["answer"], q["evidence_keyword"], other)
        for kind, text in variants:
            review = assistant.second_read(q["question"], text, result["sources"])
            grounding = verify(text, excerpts)
            verdict, _ = assistant.verdict(grounding, review)
            cases.append({"id": r["id"], "kind": kind, "verdict": verdict,
                          "reader": (review or {}).get("answers_question"),
                          "reader_rows": [s["verdict"] for s in (review or {}).get("sentences", [])],
                          "lexical": grounding["verdict"],
                          "reader_cost_usd": ((review or {}).get("usage") or {}).get("estimated_cost_usd") or 0.0})
            print(f"[planted] {r['id']} {kind}: {verdict}", flush=True)
    summary = {}
    for kind in sorted({c["kind"] for c in cases}):
        group = [c for c in cases if c["kind"] == kind]
        if kind == "original":
            summary[kind] = {"n": len(group),
                             "false_alarm": round(sum(c["verdict"] in {"contradicted", "not_answered"}
                                                      for c in group) / len(group), 3),
                             "shown_as_checked": round(sum(c["verdict"] == "verified"
                                                           for c in group) / len(group), 3)}
        else:
            summary[kind] = {"n": len(group),
                             "caught": round(sum(c["verdict"] in CATCHING for c in group) / len(group), 3),
                             "caught_by_lexical_check_alone": round(
                                 sum(c["lexical"] != "passed" for c in group) / len(group), 3)}
    return {"summary": summary, "cases": cases,
            "cost_usd": round(sum(c["reader_cost_usd"] for c in cases), 5)}


def run_compare(assistant: CourseAssistant) -> list[dict]:
    rows = []
    for case in COMPARE_CASES:
        result = assistant.compare(case["question"])
        got = {r["department"]: r for r in result["results"]}
        checks = {d: fact_in_answer(v, got[d]["answer"]) and got[d]["mode"] in {"llm", "extractive"}
                  for d, v in case["expect"].items()}
        rows.append({"question": case["question"], "per_programme_correct": checks,
                     "summary": result["summary"],
                     "answers": {d: r["answer"] for d, r in got.items()}})
        print(f"[compare] {case['question']}: {checks}", flush=True)
    return rows


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set; nothing to evaluate.")
        return 2
    quick = "--quick" in sys.argv
    ai = CourseAssistant(ROOT / "data", daily_budget_usd=None)
    free = CourseAssistant(ROOT / "data", use_environment_key=False)
    report = {"run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
              "chat_model": ai.chat_model, "review_model": ai.review_model,
              "embedding_model": ai.embedding_model if ai.vector_enabled else None,
              "sets": {}}
    all_rows = {}
    for name, path in SETS.items():
        questions = load(path)
        if quick:
            questions = questions[::4]
        ai_rows = run_set(ai, questions, f"{name}/ai")
        free_rows = run_set(free, questions, f"{name}/free")
        report["sets"][name] = {"ai": summarise(ai_rows), "free": summarise(free_rows),
                                "ai_by_kind": by_kind(ai_rows), "free_by_kind": by_kind(free_rows),
                                "rows": ai_rows}
        all_rows[name] = (questions, ai_rows)

    # Planted errors on correct AI answers from both sets (answers are cached, so the
    # results with their sources are re-read without new answer calls).
    questions_by_id, rows, results = {}, [], {}
    for name, (questions, ai_rows) in all_rows.items():
        for q in questions:
            questions_by_id[q["id"]] = q
        for row in ai_rows:
            if row["mode"] == "llm":
                results[row["id"]] = ai.ask(row["question"], questions_by_id[row["id"]]["department"])
        rows += ai_rows
    report["planted_errors"] = planted_errors(ai, questions_by_id, rows, results)
    report["compare"] = run_compare(ai)
    stats = dict(ai.stats)
    report["counters"] = stats
    report["embedding_cost_usd"] = round(usage_cost(ai.embedding_model, stats.get("embedding_tokens", 0), 0) or 0.0, 5)
    errors = sum(s["ai"]["model_errors"] for s in report["sets"].values())
    report["provider_errors"] = errors

    (ROOT / "eval" / "llm_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "eval" / "LLM_RESULTS.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "sets"} | {
        "sets": {k: {"ai": v["ai"], "free": v["free"]} for k, v in report["sets"].items()}},
        indent=2, ensure_ascii=False)[:6000])
    return 1 if errors else 0


def render(r: dict) -> str:
    pct = lambda x: f"{x * 100:.0f}%"  # noqa: E731
    lines = [
        "# Live AI-mode evaluation (generated by `scripts/evaluate_llm.py`)", "",
        f"Run {r['run_at_utc']} UTC. Answers by `{r['chat_model']}`, second reader "
        f"`{r['review_model']}`, embeddings `{r['embedding_model']}`. One run; model output "
        "can vary between runs. Free mode is the same engine without any model call.", "",
        ("**Provider failure: this run does not establish live AI answer quality.**"
         if r["provider_errors"] else
         "No provider errors. A clean run is still not a quality guarantee; read the misses below."),
        "",
        "## A. Answers: free mode vs AI mode", "",
        "| Set | Mode | Correct on the right page (strict keyword) | … any language (graded) | "
        "False abstention | Correct abstention | Right when shown as checked | Cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, s in r["sets"].items():
        for mode in ("free", "ai"):
            m = s[mode]
            lines.append(
                f"| {name.replace('_', '-')} ({m['answerable']}+{m['unanswerable']}) | {mode} | "
                f"{pct(m['correct_with_right_page'])} | {pct(m.get('correct_any_language', 0))} | "
                f"{pct(m['false_abstention'])} | "
                f"{pct(m['correct_abstention'])} | {pct(m['precision_of_checked_answers'])} "
                f"(n={m['checked_answers']}) | ${m['cost_usd']:.4f} |")
    lines += ["", "The development set was used while building; the held-out set was frozen "
              "before any system ran on it (commit history). Both were drafted with an AI "
              "assistant from the curriculum pages, not by students. \"Correct\" is an "
              "automatic keyword/number check plus the expected page among the citations, so a "
              "correct paraphrase can count as a miss. The *any language* column additionally "
              f"asks `{r['review_model']}`, shown the expected fact, whether a non-matching answer "
              "states it (translations count); it is a model judgement, reported separately.", "",
              "### Held-out, AI mode, by question type", "",
              "| Type | n | Correct on right page | False abstention | Correct abstention |",
              "|---|---|---|---|---|"]
    for kind, m in r["sets"].get("held_out", {}).get("ai_by_kind", {}).items():
        free_m = r["sets"]["held_out"]["free_by_kind"][kind]
        lines.append(f"| {kind} | {m['answerable'] + m['unanswerable']} | "
                     f"{pct(m['correct_with_right_page'])} (free {pct(free_m['correct_with_right_page'])}) | "
                     f"{pct(m['false_abstention'])} | {pct(m['correct_abstention'])} |")
    p = r["planted_errors"]["summary"]
    lines += ["", "## B. Planted errors: does the checking catch wrong answers?", "",
              "Correct AI answers were corrupted on purpose and re-checked. \"Caught\" means the "
              "student sees *contradicted*, *not answered* or *check the page* instead of a "
              "checked answer.", "",
              "| Corruption | n | Caught (second reader + word/number check) | Caught by word/number check alone |",
              "|---|---|---|---|"]
    for kind, m in p.items():
        if kind != "original":
            lines.append(f"| {kind.replace('_', ' ')} | {m['n']} | {pct(m['caught'])} | "
                         f"{pct(m['caught_by_lexical_check_alone'])} |")
    if "original" in p:
        lines += ["", f"Untouched correct answers (n={p['original']['n']}): "
                  f"{pct(p['original']['shown_as_checked'])} shown as checked twice, "
                  f"{pct(p['original']['false_alarm'])} wrongly marked contradicted or not answered."]
    lines += ["", "## C. Compare mode", ""]
    for c in r["compare"]:
        marks = ", ".join(f"{d} {'✓' if ok else '✗'}" for d, ok in c["per_programme_correct"].items())
        lines.append(f"- *{c['question']}* — {marks}" +
                     (f"<br>Summary: {c['summary']}" if c["summary"] else ""))
    total = sum(s["ai"]["cost_usd"] for s in r["sets"].values()) + r["planted_errors"]["cost_usd"]
    lines += ["", f"Provider errors: {r['provider_errors']}. Estimated model cost of this run: "
              f"${total + r['embedding_cost_usd']:.3f} (token-based estimate, not an invoice).", "",
              "## AI-mode answers that missed (held-out set)", ""]
    misses = [x for x in r["sets"].get("held_out", {}).get("rows", [])
              if (x["answerable"] and not (x["fact_in_answer"] and x["cited_expected_page"]))
              or (not x["answerable"] and x["mode"] != "abstained")]
    for x in misses:
        lines.append(f"- `{x['id']}` {x['question']} → {x['mode']}/{x['verdict']}"
                     f"{' (graded correct)' if x.get('fact_graded') else ''}: "
                     f"{x['answer'].replace(chr(10), ' ')[:240]}")
    if not misses:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
