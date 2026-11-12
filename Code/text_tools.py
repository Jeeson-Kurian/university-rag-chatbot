"""Deterministic text utilities: tokenisation, light stemming, bilingual glossary.

Everything here is dependency-free so that retrieval, evaluation and the
grounding verifier behave identically with or without a paid model provider.
"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-z0-9äöüß]+")
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")
# Split after sentence punctuation that follows a letter/bracket (so "12. Januar" and
# "30.000" survive), or before numbered paragraphs such as "(3) ".
SENTENCE_SPLIT_RE = re.compile(r"(?<=[A-Za-zäöüß)\]][.!?;])\s+(?=[A-ZÄÖÜ0-9(„\"“])|\s+(?=\(\d+\)\s)")

ENGLISH_STOPWORDS = (
    "a an and are as at be been can could do does did for from has have how i if in into is "
    "it its me my of on or our over should the their them there these they this those to "
    "was were what when where which who whom why will with would you your about find tell "
    "show please course courses programme programs program university many much any each "
    "get got give given need needs must may also than then so such per other there's"
)
GERMAN_STOPWORDS = (
    "der die das den dem des ein eine einer eines einem einen und oder ist sind wird werden "
    "wurde für mit von vom im in zu zum zur auf als bei nach wie viele welche welcher welches "
    "gilt gelten was wer wo wann gibt es sich nicht auch nur so"
)
STOPWORDS = frozenset((ENGLISH_STOPWORDS + " " + GERMAN_STOPWORDS).split())

# Curated English -> German curriculum vocabulary (stemmed when the module loads).
# The repository's "English" department ships a German-language curriculum, so an
# English question would otherwise share almost no tokens with its evidence.
_RAW_GLOSSARY: dict[str, tuple[str, ...]] = {
    "thesis": ("masterarbeit", "bachelorarbeit"),
    "admission": ("zulassung", "zulassungsvoraussetzungen", "aufnahmeverfahren"),
    "requirement": ("voraussetzungen", "vorausgesetzt", "zulassungsvoraussetzungen"),
    "required": ("vorausgesetzt", "pflichtfach", "verpflichtend"),
    "english": ("englisch", "englischen", "englischer"),
    "language": ("sprache", "sprachen", "sprachniveau"),
    "level": ("niveau", "sprachniveau"),
    "proficiency": ("kenntnisse", "sprachniveau"),
    "degree": ("grad", "akademische"),
    "academic": ("akademische", "akademischer"),
    "title": ("grad",),
    "word": ("wörtern", "wörter"),
    "participant": ("teilnehmerinnen", "teilnehmern"),
    "maximum": ("maximale",),
    "limited": ("beschränkter",),
    "examination": ("prüfung", "prüfungen", "gesamtprüfung", "prüfungsordnung"),
    "exam": ("prüfung", "prüfungen", "gesamtprüfung"),
    "oral": ("mündliche",),
    "abroad": ("auslandsaufenthalt", "ausland"),
    "mobility": ("mobilität",),
    "elective": ("wahlfächer", "wahlfach"),
    "supervisor": ("betreuerin", "betreuer"),
    "duration": ("studiendauer",),
    "graduate": ("absolventinnen", "absolventen"),
    "registration": ("anmeldung", "anmeldungsvoraussetzungen"),
    "specialisation": ("spezialisierung",),
    "specialization": ("spezialisierung",),
    "deadline": ("frist", "anmeldefrist"),
    "application": ("bewerbung", "anmeldefrist"),
    "semester": ("semestern",),
    "written": ("abzufassen", "verfassen"),
    "approve": ("genehmigen",),
    "approved": ("genehmigen",),
    "submitted": ("einzureichen",),
    "submit": ("einzureichen",),
    "comprise": ("umfasst", "umfang"),
    "credit": ("anrechnungspunkte",),
    "native": ("erstsprache",),
    "first": ("erstsprache",),
}
def stem(token: str) -> str:
    """Light English suffix folding (plural, -ed, -ing, final -e) applied to both
    documents and questions. Tokens with German umlauts/ß and numbers are kept."""
    if len(token) <= 3 or token.isdigit() or any(ch in token for ch in "äöüß"):
        return token
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            token = token[: -len(suffix)]
            break
    else:
        if len(token) > 5 and token.endswith("es") and token[-3] in "sxzh":
            token = token[:-2]
        elif token.endswith("s") and not token.endswith(("ss", "us", "is", "ys")):
            token = token[:-1]
    if len(token) > 4 and token.endswith("e"):
        token = token[:-1]
    return token


def _build_glossaries():
    en_de: dict[str, tuple[str, ...]] = {}
    de_en: dict[str, tuple[str, ...]] = {}
    for english, german in _RAW_GLOSSARY.items():
        key = stem(english)
        values = tuple(stem(g) for g in german)
        en_de[key] = tuple(dict.fromkeys(en_de.get(key, ()) + values))
        for value in values:
            de_en[value] = tuple(dict.fromkeys(de_en.get(value, ()) + (key,)))
    return en_de, de_en


GLOSSARY_EN_DE, GLOSSARY_DE_EN = _build_glossaries()


def tokens(text: str) -> list[str]:
    """All stemmed tokens, stopwords included (used for document statistics)."""
    return [stem(t) for t in TOKEN_RE.findall(text.lower())]


def content_terms(text: str) -> list[str]:
    """Ordered, de-duplicated informative terms."""
    seen: dict[str, None] = {}
    for raw in TOKEN_RE.findall(text.lower()):
        if raw in STOPWORDS or len(raw) < 2:
            continue
        term = stem(raw)
        if term in STOPWORDS:
            continue
        seen.setdefault(term, None)
    return list(seen)


def expand(term: str) -> tuple[str, ...]:
    """Cross-lingual alternatives for one stemmed term (may be empty)."""
    return GLOSSARY_EN_DE.get(term, ()) + GLOSSARY_DE_EN.get(term, ())


def numbers(text: str) -> set[str]:
    """Numbers normalised so that 30.000, 30,000 and 30000 compare equal."""
    return {re.sub(r"[.,]", "", n) for n in NUMBER_RE.findall(text)}


ABBREVIATIONS = ("max.", "min.", "para.", "paras.", "no.", "nr.", "abs.", "vgl.", "lit.",
                 "e.g.", "i.e.", "etc.", "approx.", "z.b.", "bzw.", "inkl.", "incl.", "gem.")


def sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    merged: list[str] = []
    for part in (p.strip() for p in SENTENCE_SPLIT_RE.split(flat)):
        if merged and merged[-1].lower().endswith(ABBREVIATIONS):
            merged[-1] = f"{merged[-1]} {part}"
        elif part:
            merged.append(part)
    return [p for p in merged if len(p) >= 12]
