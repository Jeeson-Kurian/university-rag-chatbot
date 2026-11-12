from langchain_community.document_loaders import TextLoader, PyPDFLoader
from pathlib import Path


def load_department_docs(folder_path: str, department: str) -> list:
    """
    Loads all .txt and .pdf files from one department folder.
    Adds department metadata to every loaded document.
    """
    all_docs = []
    folder = Path(folder_path)

    for file_path in folder.iterdir():
        if file_path.suffix.lower() == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif file_path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(file_path))
        else:
            continue

        docs = loader.load()

        for doc in docs:
            doc.metadata["department"] = department
            doc.metadata["source_file"] = file_path.name

        all_docs.extend(docs)

    return all_docs


aiandcyber_docs = load_department_docs("data/AIandCybersecurity", "ArtificialIntelligence and Cybersecurity")
informatics_docs = load_department_docs("data/Informatics", "Informatics")
business_docs = load_department_docs("data/Business", "Business")
english_docs = load_department_docs("data/English", "English")

all_documents = aiandcyber_docs + informatics_docs + business_docs + english_docs

print(f"Total documents loaded: {len(all_documents)}")

if all_documents:
    print("Sample metadata:", all_documents[0].metadata)
    print("Sample text:", all_documents[0].page_content[:300])