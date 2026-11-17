"""The live evaluator must never turn a provider outage into a green job."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_llm.py"
spec = importlib.util.spec_from_file_location("evaluate_llm", SCRIPT)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def fake_assistant(provider_error):
    class FakeAssistant:
        chat_model, review_model, embedding_model = "chat", "reader", "emb"
        vector_enabled = False

        def __init__(self, *args, **kwargs):
            self.stats = {}

        def ask(self, question, department):
            error = provider_error and "free" not in str(self.__dict__.get("mode", ""))
            return {
                "mode": "model_error" if error else "llm", "verdict": "error" if error else "verified",
                "sources": [] if error else [{"id": "S1", "document": "d.pdf", "page": 3,
                                               "department": department, "excerpt": "23 ECTS"}],
                "answer": "Unavailable" if error else "The thesis has 23 ECTS [S1].",
                "grounding": None, "review": None, "usage": None,
                "warning": "Provider error: AuthenticationError" if error else None,
            }

        def second_read(self, question, answer, sources):
            return {"status": "done", "answers_question": "yes" if "23" in answer else "no",
                    "sentences": [{"verdict": "supported"}]}

        def verdict(self, grounding, review):
            return ("verified" if review["answers_question"] == "yes" else "not_answered", "")

        def compare(self, question):
            return {"results": [], "summary": None}

    return FakeAssistant


class EvaluationStatusTests(unittest.TestCase):
    def run_evaluation(self, provider_error):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "eval").mkdir()
            questions = root / "eval" / "q.jsonl"
            questions.write_text(json.dumps({
                "id": "one", "kind": "factoid", "language": "en", "answerable": True,
                "expected": [["d.pdf", 3]], "evidence_keyword": "23", "department": "Informatics",
                "question": "How many credits?"}) + "\n")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-placeholder"}), \
                 patch.object(evaluation, "ROOT", root), \
                 patch.object(evaluation, "SETS", {"held_out": questions}), \
                 patch.object(evaluation, "COMPARE_CASES", []), \
                 patch.object(evaluation, "CourseAssistant", fake_assistant(provider_error)), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = evaluation.main()
            result = json.loads((root / "eval" / "llm_results.json").read_text())
            report = (root / "eval" / "LLM_RESULTS.md").read_text()
            return status, result, report

    def test_provider_failure_is_nonzero_and_preserves_diagnostics(self):
        status, result, report = self.run_evaluation(True)
        self.assertEqual(status, 1)
        self.assertEqual(result["provider_errors"], 1)
        self.assertIn("does not establish live AI answer quality", report)

    def test_clean_run_reports_and_plants_errors(self):
        status, result, report = self.run_evaluation(False)
        self.assertEqual(status, 0)
        self.assertEqual(result["sets"]["held_out"]["ai"]["correct_with_right_page"], 1.0)
        planted = result["planted_errors"]["summary"]
        self.assertEqual(planted["changed_number"]["caught"], 1.0)
        self.assertIn("not a quality guarantee", report)

    def test_missing_key_stops_without_provider_calls(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(evaluation, "CourseAssistant") as assistant, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evaluation.main(), 2)
            assistant.assert_not_called()


if __name__ == "__main__":
    unittest.main()
