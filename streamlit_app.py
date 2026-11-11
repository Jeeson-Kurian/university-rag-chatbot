"""Small student interface. API and UI run separately to keep components testable."""
import os
import requests
import streamlit as st

API_URL = os.getenv("UNIVERSITY_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEPARTMENTS = {
    "AIandCybersecurity": "AI and Cybersecurity",
    "Business": "Business",
    "English": "English",
    "Informatics": "Informatics",
}

st.set_page_config(page_title="Course Compass", page_icon="📚", layout="centered")
st.title("Course Compass")
st.caption("Evidence-grounded university curriculum assistant · verify important decisions against original documents")
department = st.selectbox(
    "Study area", list(DEPARTMENTS),
    format_func=lambda key: DEPARTMENTS[key],
)
question = st.text_area(
    "Ask about your course",
    placeholder="What are the admission requirements in the curriculum?",
    max_chars=800,
    height=110,
)
if st.button("Find an answer", type="primary", disabled=not question.strip()):
    if len(question.strip()) < 4:
        st.warning("Please enter a more specific question.")
    else:
        try:
            response = requests.post(
                f"{API_URL}/ask",
                json={"department": department, "question": question.strip()},
                timeout=45,
            )
            response.raise_for_status()
            result = response.json()
            st.subheader("Answer")
            st.write(result["answer"])
            st.caption(f"Answer mode: {result['mode']} · Retrieval: {result['retrieval_mode']}")
            if result.get("warning"):
                st.info(result["warning"])
            if result.get("sources"):
                st.subheader("Source evidence")
                for source in result["sources"]:
                    page = f", page {source['page']}" if source.get("page") else ""
                    with st.expander(f"[{source['id']}] {source['document']}{page}"):
                        st.write(source["excerpt"])
            else:
                st.warning("No validated supporting citations. Do not rely on this answer.")
        except requests.RequestException:
            st.error("The assistant API is unavailable. Start the FastAPI server and retry.")

st.divider()
st.caption(
    "This is an academic information tool, not an official university service. "
    "Uploaded curriculum texts can be outdated; check official documents before decisions. "
    "A preview response is not LLM-generated."
)
