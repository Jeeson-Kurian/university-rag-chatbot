from retrieval import get_retriever
from langchain_openai import ChatOpenAI
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

PROMPT_TEMPLATE = """
You are a helpful university academic assistant.

Answer the student's question using ONLY the context below.
If the answer is not present in the context, say:
"I cannot find this information in the university documents."

Do not guess.
Do not use general knowledge.

Context:
{context}

Student Question:
{question}

Answer:
"""

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=PROMPT_TEMPLATE
)


def get_qa_chain(department: str):
    retriever = get_retriever(department)

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

    return chain


if __name__ == "__main__":
    chain = get_qa_chain("Informatics")

    response = chain.invoke({
        "query": "Tell me about curriculum for the Informatics Master's programme?"
    })

    print("\nAnswer:")
    print(response["result"])

    print("\nSources:")
    for doc in response["source_documents"]:
        print("-", doc.metadata.get("source_file"))