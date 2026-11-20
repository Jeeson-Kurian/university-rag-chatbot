"""Citation excerpts must include the evidence actually used for an answer."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from Code.course_core import CHUNK_SIZE, CourseAssistant
from Code.main import QueryResponse


class ExcerptBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / "Informatics"
        folder.mkdir()
        self.fact = "The thesis carries 30 ECTS credits."
        self.text = ("General curriculum information. " * 27) + self.fact
        assert 850 < self.text.index(self.fact) < len(self.text) <= CHUNK_SIZE
        (folder / "synthetic.txt").write_text(self.text, encoding="utf-8")

    def test_extractive_tail_fact_is_visible_and_supported(self):
        assistant = CourseAssistant(self.root, use_environment_key=False)
        self.assertEqual(len(assistant.passages), 1)
        result = assistant.ask("How many ECTS credits for the thesis?", "Informatics")
        QueryResponse(**result)  # validate against the actual HTTP response schema
        self.assertEqual(result["mode"], "extractive")
        self.assertIn(self.fact, result["answer"])
        self.assertIn(self.fact, result["sources"][0]["excerpt"])
        self.assertEqual(result["sources"][0]["excerpt"], assistant.passages[0].text)
        self.assertLessEqual(len(result["sources"][0]["excerpt"]), CHUNK_SIZE)
        self.assertEqual(result["grounding"]["verdict"], "passed")

    def test_model_context_and_citation_share_the_complete_passage(self):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="The thesis carries 30 ECTS credits [S1]."))],
                usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0))

        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))
        assistant = CourseAssistant(self.root, client=client,
                                    use_environment_key=False, vector_enabled=False)
        result = assistant.ask("How many ECTS credits for the thesis?", "Informatics")
        QueryResponse(**result)
        self.assertEqual(len(calls), 1)
        self.assertIn(self.text, calls[0]["messages"][1]["content"])
        self.assertEqual(result["sources"][0]["excerpt"], self.text)
        self.assertEqual(result["grounding"]["verdict"], "passed")
