"""Capture actual Streamlit screenshots in free mode; no remote model calls."""
from pathlib import Path
import os
import subprocess
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission-media"
OUT.mkdir(exist_ok=True)
environment = dict(os.environ)
environment.pop("OPENAI_API_KEY", None)
environment.pop("UNIVERSITY_API_URL", None)
server = subprocess.Popen([
    "python", "-m", "streamlit", "run", "streamlit_app.py", "--server.headless=true",
    "--server.address=127.0.0.1", "--browser.gatherUsageStats=false",
], cwd=ROOT, env=environment)
try:
    for attempt in range(60):
        try:
            with urlopen("http://127.0.0.1:8501/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(1)
    else:
        raise RuntimeError("Streamlit did not become healthy")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        page.goto("http://127.0.0.1:8501", wait_until="networkidle")
        expect(page.get_by_text("Free mode: no API key configured, answers are extractive.", exact=True)).to_be_visible(timeout=60000)

        def ask(question, expected_text, filename):
            page.get_by_label("Your question", exact=True).fill(question)
            page.get_by_label("Your question", exact=True).press("Tab")
            page.get_by_role("button", name="Find the answer", exact=True).click()
            expect(page.get_by_text(expected_text, exact=False).first).to_be_visible(timeout=30000)
            # Wait until the server-side execution and Streamlit rerender have settled.
            page.wait_for_timeout(1200)
            page.screenshot(path=str(OUT / filename), full_page=True)

        question = "How many ECTS credits does the Master's thesis comprise?"
        ask(question, "The Master’s thesis comprises 23 ECTS credits.", "01_ai_thesis.png")

        def choose(area):
            page.get_by_role("combobox").click()
            page.get_by_role("option", name=area, exact=True).click()
            page.wait_for_timeout(500)

        choose("Informatics")
        ask(question, "The Master’s thesis comprises 25 ECTS credits.", "02_informatics_thesis.png")
        ask("What is the tuition fee for non-EU students?",
            "I cannot find this information in the selected university documents.", "03_refusal.png")
        choose("English")
        ask("What English level is required for applicants whose first language is not English?",
            "Niveau C1", "04_german_source.png")
        ask("How many words must the master's thesis have?",
            "Die Studierenden sind in der Lage", "05_known_failure.png")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=15)

print("Captured", len(list(OUT.glob('*.png'))), "actual free-mode application screenshots")
