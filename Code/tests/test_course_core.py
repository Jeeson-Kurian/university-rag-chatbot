"""Offline tests for source traceability, isolation, model abstention and API."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from Code.course_core import CourseAssistant, DEPARTMENTS, NO_EVIDENCE, load_passages
from Code.main import app


@pytest.fixture
def corpus(tmp_path: Path):
    for name in DEPARTMENTS:
        (tmp_path / name).mkdir()
    (tmp_path / "AIandCybersecurity" / "curriculum.txt").write_text(
        "The Master in Artificial Intelligence and Cybersecurity requires 120 ECTS credits. "
        "The thesis carries 30 ECTS credits.", encoding="utf-8")
    (tmp_path / "Informatics" / "curriculum.txt").write_text(
        "The Informatics Master programme has a thesis carrying 30 ECTS credits.",
        encoding="utf-8")
    return tmp_path


@pytest.fixture
def assistant(corpus):
    return CourseAssistant(corpus, use_environment_key=False)


def test_department_metadata_and_isolation(assistant):
    assert assistant.by_dept["AIandCybersecurity"][0].department == "AIandCybersecurity"
    passages, mode, warning = assistant.retrieve("How many ECTS for the thesis?", "Informatics")
    assert passages and all(p.department == "Informatics" for p in passages)
    assert mode == "lexical" and warning is None


def test_repeatable_preview_and_real_citation(assistant):
    a = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    b = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert a == b
    assert a["mode"] == "preview"
    assert a["sources"][0]["id"] == "S1"
    assert a["sources"][0]["document"] == "curriculum.txt"


def test_unknown_question_abstains(assistant):
    result = assistant.ask("What is the spacecraft fueling timetable for Neptune?", "English")
    assert result["mode"] == "abstained"
    assert result["sources"] == []
    assert result["answer"] == NO_EVIDENCE


def test_rejects_invalid_inputs(assistant):
    with pytest.raises(ValueError):
        assistant.ask("hi", "Informatics")
    with pytest.raises(ValueError):
        assistant.ask("Find courses", "../../secrets")


def test_chunk_ids_unique(corpus):
    passages = load_passages(corpus)
    assert passages and len({p.identifier for p in passages}) == len(passages)
    assert all(len(p.text) <= 900 for p in passages)


class FakeClient:
    def __init__(self, message):
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=message))])))


def test_model_citations_are_validated(corpus):
    assistant = CourseAssistant(corpus, client=FakeClient("The degree requires 120 ECTS [S1]."),
                               use_environment_key=False, vector_enabled=False)
    result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert result["mode"] == "llm" and result["sources"][0]["id"] == "S1"
    for wrong in ("There are 120 ECTS.", "There are 120 ECTS [S99]."):
        assistant.client = FakeClient(wrong)
        result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
        assert result["mode"] == "abstained" and not result["sources"]


def test_http_api_contract(monkeypatch, assistant):
    from Code import main
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert len(client.get("/departments").json()) == 4
        response = client.post("/ask", json={
            "department": "AIandCybersecurity",
            "question": "How many ECTS credits are required?"})
        assert response.status_code == 200
        assert response.json()["sources"][0]["id"] == "S1"
        assert client.post("/ask", json={
            "department": "Unknown", "question": "How many credits?"}).status_code == 422
        assert client.post("/ask", json={
            "department": "Informatics", "question": "hi"}).status_code == 422
