"""Legacy test entry point: current deterministic course-assistant contract.

The former version invoked an external LLM and deserialized a stored FAISS
index. Those behaviors are intentionally excluded from offline CI.
See test_course_core.py for the full behavioral suite.
"""
from Code.course_core import DEPARTMENTS, CourseAssistant


def test_canonical_department_registry():
    assert set(DEPARTMENTS) == {
        "AIandCybersecurity", "Business", "English", "Informatics",
    }


def test_local_repository_documents_are_discoverable():
    assistant = CourseAssistant(use_environment_key=False)
    assert assistant.by_dept["AIandCybersecurity"]
    assert assistant.by_dept["Informatics"]


def test_unknown_department_is_rejected():
    assistant = CourseAssistant(use_environment_key=False)
    try:
        assistant.retrieve("What are the admission requirements?", "WrongDepartment")
    except ValueError:
        return
    assert False, "Unknown departments must be rejected"


def test_extractive_answer_stays_on_topic_and_drops_paragraph_markers():
    assistant = CourseAssistant(use_environment_key=False)
    answer = assistant.ask("How many ECTS credits does the Master's thesis comprise?",
                           "AIandCybersecurity")["answer"]
    assert "23 ECTS" in answer and "120" not in answer and "(3)" not in answer


def test_programme_answers_differ_in_compare_mode():
    result = CourseAssistant(use_environment_key=False).compare(
        "How many ECTS credits does the Master's thesis comprise?",
        ["AIandCybersecurity", "Informatics"])
    answers = {r["department"]: r["answer"] for r in result["results"]}
    assert "23 ECTS" in answers["AIandCybersecurity"] and "25 ECTS" in answers["Informatics"]
