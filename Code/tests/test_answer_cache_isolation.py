"""A caller must not be able to modify cached evidence through a response."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from Code.course_core import CourseAssistant
from Code.main import QueryResponse


class AnswerCacheIsolationTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        folder = root / "Informatics"
        folder.mkdir()
        (folder / "synthetic.txt").write_text("The thesis carries 30 ECTS credits.",
                                              encoding="utf-8")
        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content="The thesis carries 30 ECTS credits [S1]."))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10))

        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))
        self.assistant = CourseAssistant(root, client=client,
                                         use_environment_key=False, vector_enabled=False)

    def ask(self):
        result = self.assistant.ask("How many ECTS credits for the thesis?", "Informatics")
        QueryResponse(**result)
        return result

    def corrupt(self, result):
        result["sources"][0]["excerpt"] = "Incorrect caller-edited evidence."
        result["grounding"]["sentences"][0]["status"] = "caller-edited"
        result["usage"]["prompt_tokens"] = 999

    def assert_unchanged(self, actual, expected):
        for field in ("sources", "grounding", "usage"):
            self.assertEqual(actual[field], expected[field], field)

    def test_initial_response_cannot_mutate_cache(self):
        first = self.ask()
        expected = deepcopy(first)
        self.corrupt(first)
        cached = self.ask()
        self.assertTrue(cached["cached"])
        self.assert_unchanged(cached, expected)
        self.assertEqual(len(self.calls), 1)

    def test_cached_response_cannot_mutate_cache_or_earlier_response(self):
        first = self.ask()
        expected = deepcopy(first)
        cached = self.ask()
        self.corrupt(cached)
        self.assert_unchanged(first, expected)
        self.assert_unchanged(self.ask(), expected)
        self.assertEqual(len(self.calls), 1)
