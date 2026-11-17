"""Capture real screenshots of the running Streamlit app (AI mode when a key is set).

Every step is independent: a failing step leaves ERR_<name>.png/.txt for debugging and the
run continues. The Streamlit server log is saved as server.log.

Usage:  python scripts/capture_submission_media.py [--free]
"""
from pathlib import Path
import os
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FREE = "--free" in sys.argv
OUT = ROOT / "submission-media" / ("free" if FREE else "ai")
OUT.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ)
environment.pop("UNIVERSITY_API_URL", None)
if FREE:
    environment.pop("OPENAI_API_KEY", None)
log = open(OUT / "server.log", "w")
server = subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--server.headless=true",
    "--server.address=127.0.0.1", "--browser.gatherUsageStats=false",
], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
failures = []
try:
    for _ in range(90):
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
        page = browser.new_page(viewport={"width": 1280, "height": 2300}, device_scale_factor=1)
        page.goto("http://127.0.0.1:8501", wait_until="networkidle")
        expect(page.get_by_text("Course Compass").first).to_be_visible(timeout=90000)
        page.wait_for_timeout(1500)

        def step(name, action):
            try:
                action()
                page.wait_for_timeout(1500)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                print("captured", name, flush=True)
            except Exception as exc:  # keep going; leave evidence for debugging
                failures.append(name)
                print("FAILED", name, type(exc).__name__, str(exc)[:300], flush=True)
                page.screenshot(path=str(OUT / f"ERR_{name}.png"), full_page=True)
                (OUT / f"ERR_{name}.txt").write_text(
                    f"{type(exc).__name__}: {exc}\n\n" + page.inner_text("body"), encoding="utf-8")

        def tab(name):
            page.get_by_role("tab", name=name).click()
            page.wait_for_timeout(600)

        def choose(label):
            page.get_by_role("combobox").first.click()
            page.get_by_role("option", name=label).click()
            page.wait_for_timeout(800)

        def ask(question, expand_checks=False):
            box = page.get_by_label("Your question", exact=True)
            box.fill(question)
            box.press("Tab")
            page.get_by_role("button", name="Find the answer", exact=True).click()
            page.wait_for_timeout(800)
            expect(page.locator(".cc-pill").first).to_be_visible(timeout=120000)
            page.wait_for_timeout(2500)  # page image renders after the answer
            if expand_checks:
                page.get_by_text("How this answer was checked").first.click()
                page.wait_for_timeout(800)

        thesis = "How many ECTS credits does the Master's thesis comprise?"
        step("01_ask_answer_with_page", lambda: ask(thesis))
        step("02_how_it_was_checked", lambda: ask(thesis, expand_checks=True))
        step("03_italian_question", lambda: ask(
            "Quanti crediti devo ottenere all'Università di Udine per il doppio titolo?"))
        step("04_refusal", lambda: ask("How much does student housing in Klagenfurt cost?"))

        def word_count():
            choose("Worlds of English (Master, German curriculum)")
            ask("How many words must the master's thesis have?", expand_checks=True)
        step("05_german_curriculum_word_count", word_count)

        def compare():
            tab("Compare programmes")
            page.get_by_label("Question for every programme").fill(
                "How many ECTS credits does the thesis comprise?")
            page.get_by_label("Question for every programme").press("Tab")
            page.get_by_role("button", name="Compare", exact=True).click()
            page.wait_for_timeout(1000)
            expect(page.locator(".cc-pill").nth(3)).to_be_visible(timeout=180000)
            page.wait_for_timeout(2000)
        step("06_compare_programmes", compare)

        def about():
            tab("How it works · limits")
        step("07_how_it_works", about)
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=15)
    log.close()

print("Captured", len(list(OUT.glob("0*.png"))), "screenshots; failed:", failures or "none")
sys.exit(1 if failures else 0)
