"""Measure the offline /ask endpoint on the local rehearsal container."""
import json
import math
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def read_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def measure(base, payload):
    start = time.perf_counter()
    try:
        reply = read_json(base + "/ask", payload)
        mode = reply["mode"]
        if mode not in {"extractive", "abstained"}:
            raise ValueError("unexpected response mode: " + str(mode))
        outcome = mode
    except HTTPError as error:
        outcome = f"error:HTTP{error.code}"
    except (OSError, ValueError, KeyError) as error:
        outcome = f"error:{type(error).__name__}"
    return (time.perf_counter() - start) * 1000, outcome


def main():
    port, workers = map(int, sys.argv[1:])
    base = f"http://127.0.0.1:{port}"
    info = read_json(base + "/stats")  # Load corpus outside the measurement window.
    if info["chat_model"] is not None:
        raise RuntimeError("Expected provider-free mode")
    corpus = Path(__file__).resolve().parents[1] / "eval" / "questions.jsonl"
    records = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    cases = [{k: row[k] for k in ("department", "question")} for row in records]
    if not cases:
        raise ValueError("Empty benchmark workload")
    failures = 0
    for phase in ("first pass", "repeat pass"):
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda case: measure(base, case), cases))
        elapsed = time.perf_counter() - start
        times = sorted(ms for ms, _ in results)
        outcomes = Counter(outcome for _, outcome in results)
        errors = sum(n for outcome, n in outcomes.items() if outcome.startswith("error:"))
        failures += errors
        print(json.dumps({
            "phase": phase, "concurrency": workers, "requests": len(times),
            "outcomes": outcomes, "error_rate": errors / len(times),
            "p95_ms": round(times[math.ceil(.95 * len(times)) - 1], 2),
            "requests_per_second": round(len(times) / elapsed, 2),
            "model_api_cost_usd": 0,
        }), flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
