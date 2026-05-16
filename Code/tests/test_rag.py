from Code.retrieval import get_retriever
from Code.synthesis import get_qa_chain


def test_informatics_retrieval_returns_docs():
    retriever = get_retriever("Informatics")

    docs = retriever.invoke(
        "What are the main admission requiremnents from the curriculum for the Master's programme?"
    )

    assert len(docs) > 0


def test_department_filter_informatics():
    retriever = get_retriever("Informatics")

    docs = retriever.invoke(
        "What are the admission requirements?"
    )

    for doc in docs:
        assert doc.metadata.get("department") == "Informatics"


def test_answer_has_source_documents():
    chain = get_qa_chain("Informatics")

    response = chain.invoke({
        "query": "What are the admission requirements for the Informatics Master's programme?"
    })

    assert "result" in response
    assert "source_documents" in response
    assert len(response["source_documents"]) > 0


def test_hallucination_control():
    chain = get_qa_chain("Informatics")

    response = chain.invoke({
        "query": "What is the parking rule for flying cars in 2099?"
    })

    answer = response["result"].lower()

    assert (
        "cannot find" in answer
        or "not present" in answer
        or "not in the university documents" in answer
    )
