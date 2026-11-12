"""Offline tests: traceability, isolation, abstention, model gating, caching, costs."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from Code.course_core import CourseAssistant, DEPARTMENTS, NO_EVIDENCE, load_passages, normalise


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
    (tmp_path / "English" / "curriculum.txt").write_text(
        "Die Masterarbeit umfasst 30 ECTS-AP und hat einen Umfang von mindestens "
        "30.000 Wör-\ntern im Haupttext.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def assistant(corpus):
    return CourseAssistant(corpus, use_environment_key=False)


class FakeClient:
    """Records calls; returns a fixed chat message and deterministic embeddings."""

    def __init__(self, message="The degree requires 120 ECTS [S1].", fail=False):
        self.calls = []
        self.embedding_calls = 0

        def create(**kwargs):
            self.calls.append(kwargs)
            if fail:
                raise RuntimeError("provider down")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=message))],
                usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=50))

        def embed(model, input):
            self.embedding_calls += 1
            data = [SimpleNamespace(index=i, embedding=[float(len(t) % 7) + 1.0, 1.0, float(i)])
                    for i, t in enumerate(input)]
            return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=10 * len(input)))

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        self.embeddings = SimpleNamespace(create=embed)


def test_department_metadata_and_isolation(assistant):
    assert assistant.by_dept["AIandCybersecurity"][0].department == "AIandCybersecurity"
    passages, mode, warning = assistant.retrieve("How many ECTS for the thesis?", "Informatics")
    assert passages and all(p.department == "Informatics" for p in passages)
    assert mode == "lexical" and warning is None


def test_repeatable_extractive_answer_with_real_citation(assistant):
    a = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    b = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert a == b
    assert a["mode"] == "extractive"
    assert "120 ECTS" in a["answer"] and "[S1]" in a["answer"]
    assert a["sources"][0]["id"] == "S1"
    assert a["sources"][0]["document"] == "curriculum.txt"
    assert a["grounding"]["verdict"] == "passed"


def test_unknown_question_abstains_without_model_call(corpus):
    client = FakeClient()
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    result = assistant.ask("What is the spacecraft fueling timetable for Neptune?", "English")
    assert result["mode"] == "abstained"
    assert result["sources"] == [] and result["answer"] == NO_EVIDENCE
    assert client.calls == []  # evidence gate prevented a paid call
    assert assistant.stats["abstained_before_model"] == 1


def test_rejects_invalid_inputs(assistant):
    with pytest.raises(ValueError):
        assistant.ask("hi", "Informatics")
    with pytest.raises(ValueError):
        assistant.ask("Find courses", "../../secrets")


def test_chunk_ids_unique_and_bounded(corpus):
    passages = load_passages(corpus)
    assert passages and len({p.identifier for p in passages}) == len(passages)
    assert all(len(p.text) <= 900 for p in passages)


def test_pdf_hyphenation_is_repaired():
    assert normalise("mindestens 30.000 Wör-\ntern") == "mindestens 30.000 Wörtern"
    assert normalise("post -\nsecondary") == "post -\nsecondary"  # spaced dash is not a split word


def test_cross_lingual_glossary_reaches_german_evidence(corpus):
    with_glossary = CourseAssistant(corpus, use_environment_key=False)
    without = CourseAssistant(corpus, use_environment_key=False, use_glossary=False)
    question = "How many words must the master's thesis have?"
    assert with_glossary.retrieve(question, "English")[0]
    assert without.retrieve(question, "English")[0] == []


def test_model_citations_are_validated(corpus):
    assistant = CourseAssistant(corpus, client=FakeClient(), use_environment_key=False,
                                vector_enabled=False)
    result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert result["mode"] == "llm" and result["sources"][0]["id"] == "S1"
    assert result["grounding"]["verdict"] == "passed"
    assert result["usage"]["estimated_cost_usd"] == pytest.approx((1000 * 0.15 + 50 * 0.60) / 1e6)
    for wrong in ("There are 120 ECTS.", "There are 120 ECTS [S99]."):
        assistant = CourseAssistant(corpus, client=FakeClient(wrong), use_environment_key=False,
                                    vector_enabled=False)
        result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
        assert result["mode"] == "abstained" and not result["sources"]


def test_hallucinated_number_is_flagged(corpus):
    assistant = CourseAssistant(corpus, client=FakeClient("The degree requires 180 ECTS [S1]."),
                                use_environment_key=False, vector_enabled=False)
    result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert result["mode"] == "llm"
    assert result["grounding"]["verdict"] == "flagged"
    assert result["grounding"]["sentences"][0]["missing_numbers"] == ["180"]
    assert result["warning"]


def test_answer_cache_avoids_second_paid_call(corpus):
    client = FakeClient()
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    first = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    second = assistant.ask("  how many ECTS credits are REQUIRED? ", "AIandCybersecurity")
    assert len(client.calls) == 1
    assert first["cached"] is False and second["cached"] is True
    assert second["answer"] == first["answer"]


def test_reasoning_models_get_compatible_parameters(corpus, monkeypatch):
    monkeypatch.setenv("UNIVERSITY_CHAT_MODEL", "gpt-5-nano")
    client = FakeClient()
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    call = client.calls[0]
    assert call["model"] == "gpt-5-nano"
    assert "temperature" not in call and call["reasoning_effort"] == "minimal"
    assert "max_completion_tokens" in call


def test_fallback_model_on_provider_error(corpus, monkeypatch):
    monkeypatch.setenv("UNIVERSITY_FALLBACK_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("UNIVERSITY_CHAT_MODEL", "gpt-5-nano")
    client = FakeClient(fail=True)
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert [c["model"] for c in client.calls] == ["gpt-5-nano", "gpt-4o-mini"]
    assert result["mode"] == "model_error" and result["warning"] == "Provider error: RuntimeError"


def test_embeddings_cached_on_disk_without_pickle(corpus, tmp_path):
    pytest.importorskip("faiss")
    cache = tmp_path / "cache"
    client = FakeClient()
    first = CourseAssistant(corpus, client=client, use_environment_key=False, cache_dir=cache)
    passages, mode, _ = first.retrieve("How many ECTS credits are required?", "AIandCybersecurity")
    assert mode == "hybrid" and passages
    calls_after_first = client.embedding_calls
    files = list((cache / "embeddings").glob("*.npy"))
    assert files
    second = CourseAssistant(corpus, client=client, use_environment_key=False, cache_dir=cache)
    second.retrieve("How many ECTS credits are required?", "AIandCybersecurity")
    assert client.embedding_calls == calls_after_first + 1  # only the query was embedded
    assert second.stats["embedding_cache_hits"] == 1
