"""Five deterministic retrieval smoke cases; no credentials or provider calls."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Code.course_core import CourseAssistant

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("AIandCybersecurity", "What does artificial intelligence and cybersecurity curriculum cover?", "curriculum"),
    ("Informatics", "What topics are in the Informatics curriculum?", "EN_MA_Informatics"),
    ("Business", "What courses are in the Business curriculum?", "Curriculum-BA"),
    ("English", "What does the English curriculum describe?", "Mitteilungsblatt"),
    ("English", "What is the Neptune spacecraft launch timetable?", None),
]


def main():
    assistant = CourseAssistant(ROOT / "data", use_environment_key=False)
    outcomes = []
    for department, question, expected in CASES:
        result = assistant.ask(question, department)
        files = [src["document"] for src in result["sources"]]
        passed = (any(expected.lower() in file.lower() for file in files)
                  if expected else result["mode"] == "abstained")
        outcomes.append({
            "department": department, "question": question, "expected_document": expected,
            "retrieved": files, "mode": result["mode"], "pass": passed})
    report = {
        "scope": "offline smoke test, not LLM accuracy or citation entailment",
        "cases": len(outcomes), "passed": sum(row["pass"] for row in outcomes),
        "results": outcomes}
    print(json.dumps(report, indent=2))
    return 0 if all(row["pass"] for row in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
