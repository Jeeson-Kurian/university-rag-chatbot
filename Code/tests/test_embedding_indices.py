"""Offline embedding-response contract checks; no remote provider calls."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from Code.course_core import CourseAssistant


class EmbeddingIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def assistant(self, create):
        return CourseAssistant(
            data_dir=self.root / "data",
            cache_dir=self.root / "cache",
            client=SimpleNamespace(embeddings=SimpleNamespace(create=create)),
            use_environment_key=False,
        )

    @staticmethod
    def response(indices):
        return SimpleNamespace(
            object="list", model="offline-fixture",
            data=[SimpleNamespace(object="embedding", index=i, embedding=[1.0, 2.0])
                  for i in indices],
            usage=SimpleNamespace(prompt_tokens=2, total_tokens=2),
        )

    def test_response_fixture_matches_sdk_schema(self):
        try:
            from openai.types import CreateEmbeddingResponse
        except ImportError:
            self.skipTest("OpenAI SDK unavailable locally; installed by repository CI")
        response = self.response([1, 0])
        parsed = CreateEmbeddingResponse.model_validate({
            **vars(response),
            "data": [vars(item) for item in response.data],
            "usage": vars(response.usage),
        })
        self.assertEqual([item.index for item in parsed.data], [1, 0])
        self.assertEqual(parsed.data[0].embedding, [1.0, 2.0])

    def test_rejects_invalid_batch_indices(self):
        for indices in ([0, 0], [-1, 0], [0, 2], [1, 2], [0]):
            with self.subTest(indices=indices):
                assistant = self.assistant(lambda **kwargs: self.response(indices))
                with self.assertRaises(ValueError):
                    assistant._embed(["first passage", "second passage"])

    def test_reorders_valid_batches_using_batch_local_indices(self):
        calls = []

        def create(*, model, input):
            calls.append(len(input))
            return SimpleNamespace(
                data=[SimpleNamespace(index=i, embedding=[float(text), 1.0])
                      for i, text in reversed(list(enumerate(input)))],
                usage=SimpleNamespace(total_tokens=len(input)),
            )

        assistant = self.assistant(create)
        actual = assistant._embed([str(i) for i in range(1, 67)])
        expected = np.asarray([[i, 1.0] for i in range(1, 67)], dtype="float32")
        expected /= np.linalg.norm(expected, axis=1, keepdims=True)
        np.testing.assert_allclose(actual, expected)
        self.assertEqual(calls, [64, 2])
        self.assertEqual(assistant.stats["embedding_tokens"], 66)

    def test_invalid_indices_are_not_persisted_as_passage_embeddings(self):
        department = self.root / "data" / "Informatics"
        department.mkdir(parents=True)
        for name, credits in (("first", 30), ("second", 120)):
            (department / (name + ".txt")).write_text(
                f"The curriculum requires {credits} ECTS credits.", encoding="utf-8")
        assistant = self.assistant(lambda **kwargs: self.response([0, 0]))
        self.assertEqual(len(assistant.by_dept["Informatics"]), 2)
        with self.assertRaises(ValueError):
            assistant._passage_matrix("Informatics")
        self.assertEqual(list((self.root / "cache").rglob("*.npy")), [])


if __name__ == "__main__":
    unittest.main()
