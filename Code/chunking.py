from ingestion import all_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter


splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=[
        "\n\n",
        "\n",
        ". ",
        " ",
        ""
    ]
)

chunks = splitter.split_documents(all_documents)

print(f"Total original documents/pages loaded: {len(all_documents)}")
print(f"Total chunks created: {len(chunks)}")

if chunks:
    print("\nSample chunk metadata:")
    print(chunks[0].metadata)

    print("\nSample chunk text:")
    print(chunks[0].page_content[:500])