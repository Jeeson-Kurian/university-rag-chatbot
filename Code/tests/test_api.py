"""HTTP contract tests (skipped when FastAPI is not installed; CI installs it)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from Code import main  # noqa: E402
from Code.course_core import CourseAssistant  # noqa: E402


@pytest.fixture
def client(monkeypatch, tmp_path):
    (tmp_path / "AIandCybersecurity").mkdir()
    (tmp_path / "AIandCybersecurity" / "c.txt").write_text(
        "The Master in Artificial Intelligence and Cybersecurity requires 120 ECTS credits.",
        encoding="utf-8")
    assistant = CourseAssistant(tmp_path, use_environment_key=False)
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    with TestClient(main.app) as c:
        yield c


def test_http_api_contract(client):
    assert client.get("/health").status_code == 200
    assert len(client.get("/departments").json()) == 4
    response = client.post("/ask", json={
        "department": "AIandCybersecurity", "question": "How many ECTS credits are required?"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "extractive" and body["sources"][0]["id"] == "S1"
    assert body["grounding"]["verdict"] == "passed" and body["cached"] is False
    assert client.post("/ask", json={"department": "Unknown", "question": "How many credits?"}).status_code == 422
    assert client.post("/ask", json={"department": "Informatics", "question": "hi"}).status_code == 422


def test_stats_endpoint(client):
    client.post("/ask", json={"department": "AIandCybersecurity",
                              "question": "What is the Neptune launch timetable?"})
    stats = client.get("/stats").json()
    assert stats["chat_model"] is None and stats["passages"] == 1
    assert stats["counters"]["abstained_before_model"] == 1


def test_compare_endpoint(client):
    body = client.post("/compare", json={"question": "How many ECTS credits are required?"}).json()
    assert body["answered"] == ["AIandCybersecurity"]
    assert len(body["results"]) == 4 and body["summary"] is None


def test_page_endpoint_renders_real_pdf_and_rejects_traversal(monkeypatch):
    from fastapi.testclient import TestClient
    pytest.importorskip("pypdfium2")
    with TestClient(main.app) as c:
        ok = c.get("/page", params={
            "department": "AIandCybersecurity", "page": 10,
            "document": "curriculum-master-artificial-intelligence-and-cybersecurity-english.pdf",
            "highlight": "The Master's thesis comprises 23 ECTS credits."})
        assert ok.status_code == 200 and ok.content[:4] == b"\x89PNG"
        bad = c.get("/page", params={"department": "AIandCybersecurity", "page": 1,
                                      "document": "../Informatics/EN_MA_Informatics.pdf"})
        assert bad.status_code == 404
