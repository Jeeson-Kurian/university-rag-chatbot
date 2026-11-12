from cleaning import cleaned_chunks
from chunking import chunks
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document



embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

cleaned_docs = []

for chunk, cleaned_text in zip(chunks, cleaned_chunks):
    cleaned_docs.append(
        Document(
            page_content=cleaned_text,
            metadata=chunk.metadata
        )
    )

print(f"Cleaned documents prepared: {len(cleaned_docs)}")
print("Building FAISS vector index...")

vectorstore = FAISS.from_documents(
    cleaned_docs,
    embedding=embeddings
)

vectorstore.save_local("university_index")

print("FAISS index saved to ./university_index")

test_results = vectorstore.similarity_search(
    "What subjects are in Semester 3?",
    k=3
)

print("\nTest search results:")
for doc in test_results:
    print("Department:", doc.metadata.get("department"))
    print("Source:", doc.metadata.get("source_file"))
    print("Text:", doc.page_content[:200])
    print("-" * 50)