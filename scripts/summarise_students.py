"""Summarise the small student check (eval/student_results.csv -> eval/STUDENT_RESULTS.md)."""
from collections import Counter
from pathlib import Path
import csv
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "eval" / "student_results.csv"
TRUSTED = {"checked twice", "words and numbers match"}


def main() -> int:
    if not SOURCE.is_file():
        print(f"No {SOURCE.relative_to(ROOT)} yet (template: docs/student_testing/).")
        return 2
    rows = [r for r in csv.DictReader(SOURCE.open(encoding="utf-8")) if r.get("question")]
    n = len(rows) or 1
    outcome = Counter(r["answer_was"].strip() for r in rows)
    trusted = [r for r in rows if r["label_shown"].strip() in TRUSTED]
    trusted_right = sum(r["answer_was"].strip() == "correct" for r in trusted)
    seconds = [float(r["seconds_to_answer"]) for r in rows if r["seconds_to_answer"].strip()]
    reuse = [float(r["would_use_again"]) for r in rows if r["would_use_again"].strip()]
    lines = [
        "# Student check", "",
        f"{len({r['participant'] for r in rows})} students, {len(rows)} of their own questions. "
        "A very small sample: it shows how the prototype behaves for real questions, not a "
        "statistically reliable accuracy.", "",
        "| Outcome | Questions |", "|---|---|",
        *[f"| {k.replace('_', ' ')} | {v} ({v / n:.0%}) |" for k, v in outcome.most_common()],
        "",
        f"- Answers shown as checked: {len(trusted)}; judged correct by the student: "
        f"{trusted_right}/{len(trusted) or 0}.",
        f"- The highlighted page helped confirm the answer: "
        f"{sum(r['page_helped'].strip() == 'yes' for r in rows)}/{len(rows)}.",
    ]
    if seconds:
        lines.append(f"- Median time to a confident answer: {statistics.median(seconds):.0f} s.")
    if reuse:
        lines.append(f"- Would use again (1–5): median {statistics.median(reuse):.1f}.")
    lines += ["", "## Every question", "", "| Programme | Question | Outcome | Label | Comment |",
              "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['programme']} | {r['question']} | {r['answer_was']} | "
                     f"{r['label_shown']} | {r['comment']} |")
    (ROOT / "eval" / "STUDENT_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
