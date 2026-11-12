from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS


embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parent.parent / "university_index"
vectorstore = FAISS.load_local(
    INDEX_PATH,
    embeddings,
    allow_dangerous_deserialization=True
)


def get_retriever(department: str):
    """
    Creates a retriever filtered by department.
    """
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 4,
            "filter": {"department": department}
        }
    )
    return retriever


if __name__ == "__main__":
    retriever = get_retriever("Informatics")

    results = retriever.invoke(
        "What are the admission requirements?"
    )

    print(f"Total retrieved chunks: {len(results)}")

    for i, doc in enumerate(results, start=1):
        print(f"\n--- Result {i} ---")
        print("Department:", doc.metadata.get("department"))
        print("Source file:", doc.metadata.get("source_file"))
        print("Text:", doc.page_content[:500])