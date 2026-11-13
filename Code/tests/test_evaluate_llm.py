"""Provider failures must not produce a green live-evaluation job."""
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


class EvaluationStatusTests(unittest.TestCase):
    def run_evaluation(self, provider_error):
        class FakeAssistant:
            chat_model = "test-model"
            embedding_model = "test-embeddings"
            vector_enabled = False
            stats = {}

            def __init__(self, *args):
                pass

            def ask(self, question, department):
                return {
                    "mode": "model_error" if provider_error else "llm",
                    "retrieval_mode": "lexical", "sources": [],
                    "answer": "Unavailable" if provider_error else "23 ECTS [S1]",
                    "grounding": None, "warning": "Provider error: AuthenticationError" if provider_error else None,
                }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "eval").mkdir()
            questions = root / "eval" / "questions.jsonl"
            questions.write_text(json.dumps({
                "id": "one", "kind": "factoid", "language": "en", "answerable": True,
                "expected": [], "evidence_keyword": "23", "department": "Informatics",
                "question": "How many credits?",
            }) + "\n")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-placeholder"}), \
                 patch.object(evaluation, "ROOT", root), \
                 patch.object(evaluation, "QUESTIONS", questions), \
                 patch.object(evaluation, "CourseAssistant", FakeAssistant), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = evaluation.main()
            result = json.loads((root / "eval" / "llm_results.json").read_text())
            report = (root / "eval" / "LLM_RESULTS.md").read_text()
            return status, result, report

    def test_provider_failure_is_nonzero_and_preserves_diagnostics(self):
        status, result, report = self.run_evaluation(True)
        self.assertEqual(status, 1)
        self.assertEqual(result["summary"]["model_errors"], 1)
        self.assertEqual(result["rows"][0]["warning"], "Provider error: AuthenticationError")
        self.assertIn("does not establish live AI answer quality", report)

    def test_quality_misses_without_provider_errors_still_generate_report(self):
        status, result, report = self.run_evaluation(False)
        self.assertEqual(status, 0)
        self.assertEqual(result["summary"]["cites_expected_page"], 0)
        self.assertIn("not a quality guarantee", report)

    def test_missing_key_stops_without_provider_calls(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(evaluation, "CourseAssistant") as assistant, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evaluation.main(), 2)
            assistant.assert_not_called()


if __name__ == "__main__":
    unittest.main()
