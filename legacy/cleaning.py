from chunking import chunks
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import re


analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def clean_text(text: str) -> str:
    """
    Removes common document noise.
    """
    text = re.sub(r"Page \d+ of \d+", "", text)
    text = re.sub(r"[-_]{4,}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrub_pii(text: str) -> str:
    """
    Detects and anonymizes personal information.
    """
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=[
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "LOCATION",
            "CREDIT_CARD",
            "US_SSN",
        ],
    )

    if not results:
        return text

    cleaned_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results
    )

    return cleaned_result.text


def process_chunk(text: str) -> str:
    """
    Full cleaning pipeline for one chunk.
    """
    text = clean_text(text)
    text = scrub_pii(text)
    return text


cleaned_chunks = [process_chunk(chunk.page_content) for chunk in chunks]

print(f"Original chunks: {len(chunks)}")
print(f"Cleaned chunks: {len(cleaned_chunks)}")

if cleaned_chunks:
    print("\nSample cleaned chunk:")
    print(cleaned_chunks[0][:500])