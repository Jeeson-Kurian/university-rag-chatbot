"""Evidence viewer: render the cited PDF page and highlight the sentence that supports the answer.

Students should not have to trust an excerpt; they can see the real page. Rendering uses
pypdfium2 (no network, no model). The highlight is found by searching the page text for the
supporting sentence, falling back to shorter fragments when PDF line breaks get in the way.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re

from .text_tools import content_terms, sentences, tokens

HIGHLIGHT = (255, 214, 10, 110)   # translucent yellow
OUTLINE = (214, 158, 0, 255)


def best_sentence(excerpt: str, claim: str) -> str:
    """The excerpt sentence that shares the most informative words and numbers with a claim."""
    claim_terms = set(content_terms(re.sub(r"\[S\d+\]", "", claim)))
    best, best_score = "", -1.0
    for sentence in sentences(excerpt) or [excerpt]:
        vocab = set(tokens(sentence))
        score = len(claim_terms & vocab) + 0.5 * len(set(re.findall(r"\d+", claim)) & set(re.findall(r"\d+", sentence)))
        if score > best_score:
            best, best_score = sentence, score
    return best


def _fragments(sentence: str) -> list[str]:
    """Search strings from longest to shortest; PDF text may break lines mid-sentence."""
    words = re.sub(r"\s+", " ", sentence).strip().split(" ")
    out = []
    for size in (12, 8, 5, 3):
        if len(words) >= size:
            for start in range(0, len(words) - size + 1, max(1, size // 2)):
                out.append(" ".join(words[start:start + size]))
    return out or [" ".join(words)]


@lru_cache(maxsize=64)
def _render(path: str, page_number: int, highlight: str, scale: float) -> bytes:
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[page_number - 1]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().convert("RGBA")
        boxes: list[tuple[float, float, float, float]] = []
        if highlight:
            textpage = page.get_textpage()

            def find(fragment):
                found_boxes = []
                searcher = textpage.search(fragment, match_case=False, match_whole_word=False)
                found = searcher.get_next()
                while found:
                    start, count = found
                    found_boxes += [textpage.get_rect(i)
                                    for i in range(textpage.count_rects(start, count))]
                    found = searcher.get_next()
                searcher.close()
                return found_boxes

            for fragment in _fragments(highlight):
                hits = find(fragment)
                if not hits:
                    continue
                if not boxes:
                    boxes = hits          # the longest fragment that matches anchors the mark
                    continue
                # Shorter fragments only extend the mark near the anchor (the same sentence,
                # continued over a PDF line break), never elsewhere on the page.
                top = max(b[3] for b in boxes) + 30
                bottom = min(b[1] for b in boxes) - 30
                boxes += [b for b in hits if bottom <= b[1] and b[3] <= top]
            textpage.close()
        if boxes:
            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            height = page.get_height()
            for left, bottom, right, top in boxes:
                draw.rectangle([left * scale - 2, (height - top) * scale - 2,
                                right * scale + 2, (height - bottom) * scale + 2],
                               fill=HIGHLIGHT, outline=OUTLINE)
            image = Image.alpha_composite(image, overlay)
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    finally:
        pdf.close()


def render_page(path: Path, page: int, highlight: str = "", scale: float = 1.6) -> bytes:
    """PNG bytes of one PDF page, with the highlight sentence marked when it can be found."""
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF sources have pages")
    return _render(str(path), int(page), highlight[:600], scale)
