"""Offline tests: traceability, isolation, abstention, model gating, caching, costs."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from Code import ai_steps
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
    """Records calls and answers each model step (understand, answer, second reader,
    compare) with a fixed reply; deterministic embeddings."""

    def __init__(self, message="The degree requires 120 ECTS [S1].", fail=False,
                 review=None, understand=None, compare=None):
        self.calls = []
        self.embedding_calls = 0
        replies = {
            ai_steps.UNDERSTAND_SYSTEM: understand or '{"language": "en", "terms": []}',
            ai_steps.SECOND_READER_SYSTEM: review or (
                '{"answers_question": "yes", "reason": "ok", '
                '"sentences": [{"n": 1, "verdict": "supported", "reason": "stated"}]}'),
            ai_steps.COMPARE_SYSTEM: compare or '{"summary": "Both require 120 ECTS."}',
        }

        def create(**kwargs):
            self.calls.append(kwargs)
            if fail:
                raise RuntimeError("provider down")
            content = replies.get(kwargs["messages"][0]["content"], None)
            if callable(message) and content is None:
                content = message(kwargs)
            elif content is None:
                content = message
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=50))

        def embed(model, input):
            self.embedding_calls += 1
            data = [SimpleNamespace(index=i, embedding=[float(len(t) % 7) + 1.0, 1.0, float(i)])
                    for i, t in enumerate(input)]
            return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=10 * len(input)))

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        self.embeddings = SimpleNamespace(create=embed)

    def step_calls(self, system):
        return [c for c in self.calls if c["messages"][0]["content"] == system]

    @property
    def answer_calls(self):
        return self.step_calls(ai_steps.ANSWER_SYSTEM)


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
    assert client.answer_calls == []  # evidence gate: no answer written, no second read
    assert client.step_calls(ai_steps.SECOND_READER_SYSTEM) == []
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
    assert result["review"]["status"] == "done" and result["verdict"] == "verified"
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
    assert result["verdict"] == "check"  # the lexical screen overrules a lenient reader


def test_answer_cache_avoids_second_paid_call(corpus):
    client = FakeClient()
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    first = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    second = assistant.ask("  how many ECTS credits are REQUIRED? ", "AIandCybersecurity")
    assert len(client.answer_calls) == 1
    assert first["cached"] is False and second["cached"] is True
    assert second["answer"] == first["answer"]


def test_reasoning_models_get_compatible_parameters(corpus, monkeypatch):
    monkeypatch.setenv("UNIVERSITY_CHAT_MODEL", "gpt-5-nano")
    client = FakeClient()
    assistant = CourseAssistant(corpus, client=client, use_environment_key=False,
                                vector_enabled=False)
    assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    call = client.answer_calls[0]
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
    assert [c["model"] for c in client.answer_calls] == ["gpt-5-nano", "gpt-4o-mini"]
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


# ---------------------------------------------------------------- v4: AI steps

def ai(corpus, client, **kwargs):
    return CourseAssistant(corpus, client=client, use_environment_key=False,
                           vector_enabled=False, **kwargs)


ITALIAN_TERMS = ('{"language": "it", "terms": ['
                 '{"word": "tesi", "en": ["thesis"], "de": ["Masterarbeit"]}, '
                 '{"word": "parole", "en": ["words"], "de": ["Wörtern"]}]}')


def test_model_terms_let_an_italian_question_reach_german_evidence(corpus):
    question = "Quante parole deve avere la tesi?"
    offline = CourseAssistant(corpus, use_environment_key=False)
    assert offline.ask(question, "English")["mode"] == "abstained"
    client = FakeClient("Die Masterarbeit umfasst mindestens 30.000 Wörter [S1].",
                        understand=ITALIAN_TERMS)
    result = ai(corpus, client).ask(question, "English")
    assert result["mode"] == "llm" and result["question_language"] == "it"
    assert "masterarbeit" in result["searched_terms"]


def test_model_terms_must_belong_to_words_the_student_wrote(corpus):
    sneaky = ('{"terms": [{"word": "thesis", "en": ["thesis", "ECTS"], "de": []}, '
              '{"word": "credits", "en": ["ECTS"], "de": []}]}')
    client = FakeClient(understand=sneaky)
    result = ai(corpus, client).ask("Who won the football world cup?", "AIandCybersecurity")
    assert result["mode"] == "abstained" and client.answer_calls == []


def test_second_reader_contradiction_is_reported(corpus):
    review = ('{"answers_question": "yes", "sentences": '
              '[{"n": 1, "verdict": "contradicted", "reason": "page says 120"}]}')
    result = ai(corpus, FakeClient("The degree requires 120 ECTS [S1].", review=review)).ask(
        "How many ECTS credits are required?", "AIandCybersecurity")
    assert result["verdict"] == "contradicted"
    assert result["review"]["sentences"][0]["reason"] == "page says 120"


def test_not_answered_triggers_one_wider_second_look(corpus):
    review = '{"answers_question": "no", "reason": "no word count", "sentences": []}'
    client = FakeClient("Die Masterarbeit umfasst 30 ECTS-AP [S1].", review=review)
    result = ai(corpus, client).ask("How many words must the master's thesis have?", "English")
    assert len(client.answer_calls) == 2           # first try + one wider look, no loop
    assert result["second_look"] is True
    assert result["verdict"] == "not_answered"


def test_second_reader_failure_falls_back_to_lexical_screen(corpus):
    result = ai(corpus, FakeClient(review="not json")).ask(
        "How many ECTS credits are required?", "AIandCybersecurity")
    assert result["review"]["status"] == "unavailable"
    assert result["verdict"] == "screened"


def test_daily_budget_switches_to_free_mode(corpus):
    client = FakeClient()
    assistant = ai(corpus, client, daily_budget_usd=0.0)
    result = assistant.ask("How many ECTS credits are required?", "AIandCybersecurity")
    assert result["mode"] == "extractive" and client.calls == []
    assert "budget" in result["warning"]


def test_compare_runs_every_programme_and_checks_summary_numbers(corpus):
    client = FakeClient(lambda kw: "The thesis carries 30 ECTS credits [S1].",
                        compare='{"summary": "Both theses carry 30 ECTS."}')
    result = ai(corpus, client).compare("How many ECTS credits does the thesis carry?")
    assert [r["department"] for r in result["results"]] == list(DEPARTMENTS)
    assert set(result["answered"]) >= {"AIandCybersecurity", "Informatics"}
    assert result["summary"] == "Both theses carry 30 ECTS."
    invented = FakeClient(lambda kw: "The thesis carries 30 ECTS credits [S1].",
                          compare='{"summary": "Informatics needs 45 ECTS."}')
    assert ai(corpus, invented).compare("How many ECTS credits does the thesis carry?")["summary"] is None


def test_compare_offline_has_no_summary(corpus):
    result = CourseAssistant(corpus, use_environment_key=False).compare(
        "How many ECTS credits does the thesis carry?")
    assert result["summary"] is None and len(result["results"]) == len(DEPARTMENTS)


def test_parse_review_rejects_bad_output():
    assert ai_steps.parse_review(ai_steps.parse_json("nonsense"), 1) is None
    assert ai_steps.parse_review({"answers_question": "maybe"}, 1) is None
    parsed = ai_steps.parse_review(ai_steps.parse_json(
        '```json\n{"answers_question": "Yes", "sentences": [{"n": 7, "verdict": "supported"}]}\n```'), 1)
    assert parsed["answers_question"] == "yes"
    assert parsed["sentences"] == [{"verdict": "unchecked", "reason": ""}]


def test_document_path_blocks_traversal(corpus):
    from Code.course_core import document_path
    assert document_path("English", "curriculum.txt", corpus).name == "curriculum.txt"
    for bad in ("../Informatics/curriculum.txt", "/etc/passwd", "missing.pdf"):
        with pytest.raises(ValueError):
            document_path("English", bad, corpus)
