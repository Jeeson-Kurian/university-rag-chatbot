"""Grounding must not silently discard short factual sentences."""
import unittest
from Code.grounding import verify
from Code.text_tools import sentences


class ShortClaimTests(unittest.TestCase):
    def test_short_uncited_claim_is_checked_in_mixed_answer(self):
        for answer in ("30 ECTS [S1]. 180 ECTS.", "180 ECTS. 30 ECTS [S1]."):
            with self.subTest(answer=answer):
                report = verify(answer, {1: "The thesis carries 30 ECTS."})
                self.assertEqual(report["sentences_checked"], 2)
                self.assertEqual(report["verdict"], "flagged")
                self.assertIn("uncited", [r["status"] for r in report["sentences"]])

    def test_short_cited_wrong_number_is_checked(self):
        report = verify("The thesis carries 30 ECTS [S1]. 99 [S1].",
                        {1: "The thesis carries 30 ECTS."})
        self.assertEqual(report["sentences_checked"], 2)
        self.assertEqual(report["sentences"][1]["status"], "number_not_in_evidence")
        self.assertEqual(report["sentences"][1]["missing_numbers"], ["99"])
        self.assertEqual(report["verdict"], "flagged")

    def test_short_supported_number_still_passes(self):
        report = verify("The thesis carries 30 ECTS [S1]. 30 [S1].",
                        {1: "The thesis carries 30 ECTS."})
        self.assertEqual(report["sentences_checked"], 2)
        self.assertEqual(report["verdict"], "passed")

    def test_empty_answer_is_not_passed(self):
        self.assertEqual(verify("", {1: "30 ECTS"})["verdict"], "flagged")

    def test_extractive_sentence_filter_keeps_existing_default(self):
        self.assertEqual(sentences("30 ECTS."), [])
