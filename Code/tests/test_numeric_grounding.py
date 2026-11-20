"""Offline regressions for decimal corruption in the grounding screen."""
import unittest

from Code.grounding import verify
from Code.text_tools import numbers


class NumericGroundingTests(unittest.TestCase):
    def test_decimal_separators_preserve_value(self):
        self.assertEqual(numbers("1.5 and 1,5"), {"1.5"})
        self.assertNotEqual(numbers("1.5"), numbers("15"))
        self.assertNotEqual(numbers("0.25"), numbers("025"))
        self.assertNotEqual(numbers("12.75"), numbers("1275"))

    def test_regular_thousands_groups_remain_compatible(self):
        self.assertEqual(numbers("30.000 30,000 30000"), {"30000"})
        self.assertEqual(numbers("1.234.567 1,234,567 1234567"), {"1234567"})

    def test_malformed_groups_are_not_collapsed_into_an_integer(self):
        self.assertNotEqual(numbers("1.23.456"), numbers("123456"))
        self.assertNotEqual(numbers("1,234.567"), numbers("1234567"))

    def test_wrong_decimal_claim_is_flagged_in_both_directions(self):
        for claim, evidence in (("15", "1.5"), ("15", "1,5"),
                                ("1.5", "15"), ("1275", "12.75")):
            with self.subTest(claim=claim, evidence=evidence):
                report = verify(f"The module requires {claim} ECTS [S1].",
                                {1: f"The module requires {evidence} ECTS."})
                self.assertEqual(report["verdict"], "flagged")
                self.assertEqual(report["sentences"][0]["status"], "number_not_in_evidence")

    def test_matching_decimals_and_thousands_still_pass(self):
        for claim, evidence in (("1.5", "1.5"), ("1.5", "1,5"),
                                ("30000", "30.000"), ("30000", "30,000")):
            with self.subTest(claim=claim, evidence=evidence):
                report = verify(f"The thesis requires {claim} words [S1].",
                                {1: f"The thesis requires {evidence} words."})
                self.assertEqual(report["verdict"], "passed")
