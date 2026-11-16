"""Streamlit UI smoke tests in free mode (skipped when Streamlit is not installed)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

THESIS = "How many ECTS credits does the Master's thesis comprise?"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UNIVERSITY_API_URL", raising=False)
    at = AppTest.from_file("streamlit_app.py", default_timeout=60)
    at.run()
    assert not at.exception
    return at


def click(at, label):
    [button for button in at.button if button.label == label][0].click().run()
    assert not at.exception


def markdown_text(at):
    return "\n".join(m.value for m in at.markdown)


def test_ask_shows_answer_verdict_and_evidence(app):
    app.text_area(key="question").input(THESIS).run()
    click(app, "Find the answer")
    text = markdown_text(app)
    assert "23 ECTS" in text and "cc-pill" in text and "Evidence" in text


def test_refusal_is_explicit(app):
    app.text_area(key="question").input("What is the tuition fee for non-EU students?").run()
    click(app, "Find the answer")
    assert "I cannot find this information" in markdown_text(app)


def test_compare_shows_each_programme(app):
    app.text_input(key="cmp_question").input(THESIS).run()
    click(app, "Compare")
    text = markdown_text(app)
    assert "23 ECTS" in text and "25 ECTS" in text
