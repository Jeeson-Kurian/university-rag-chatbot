"""Claim-level verification of generated answers against their cited evidence.

This is a cheap, deterministic *screen*, not proof of entailment. For every
answer sentence it checks that (1) at least one citation is present, (2) every
number in the sentence occurs in a cited excerpt, and (3) enough of the
sentence's informative terms (or their glossary translations) occur in the
cited excerpts. Sentences failing any check are flagged for the student.
"""
from __future__ import annotations

import re

from .text_tools import content_terms, expand, numbers, sentences, tokens

CITATION_RE = re.compile(r"\[S(\d+)\]")
MIN_TERM_SUPPORT = 0.5


def verify(answer: str, excerpts: dict[int, str]) -> dict:
    vocab = {i: set(tokens(text)) for i, text in excerpts.items()}
    nums = {i: numbers(text) for i, text in excerpts.items()}
    report = []
    for sentence in sentences(answer) or [answer]:
        cited = sorted({int(i) for i in CITATION_RE.findall(sentence)} & set(excerpts))
        body = CITATION_RE.sub("", sentence)
        terms = [t for t in content_terms(body) if not t.isdigit()]
        sentence_numbers = numbers(body)
        if not terms and not sentence_numbers:
            continue  # connective text such as "In summary:" carries no claim
        evidence_vocab = set().union(*(vocab[i] for i in cited)) if cited else set()
        evidence_nums = set().union(*(nums[i] for i in cited)) if cited else set()
        supported = [t for t in terms
                     if t in evidence_vocab or any(x in evidence_vocab for x in expand(t))]
        support = round(len(supported) / len(terms), 3) if terms else 1.0
        missing_numbers = sorted(sentence_numbers - evidence_nums)
        status = "supported"
        if not cited:
            status = "uncited"
        elif missing_numbers:
            status = "number_not_in_evidence"
        elif support < MIN_TERM_SUPPORT:
            status = "weak_support"
        report.append({
            "sentence": sentence,
            "citations": [f"S{i}" for i in cited],
            "term_support": support,
            "missing_numbers": missing_numbers,
            "status": status,
        })
    checked = len(report)
    passed = sum(1 for row in report if row["status"] == "supported")
    return {
        "method": "lexical-and-numeric screen (not entailment)",
        "sentences_checked": checked,
        "sentences_supported": passed,
        "score": round(passed / checked, 3) if checked else 0.0,
        "verdict": "passed" if checked and passed == checked else "flagged",
        "sentences": report,
    }
