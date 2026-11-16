# Live run history (16 Nov 2026)

Every live AI run is kept, including the ones that exposed bugs. The held-out set was frozen
before run 1; the fixes after runs 1 and 2 were made **after seeing held-out misses**, so the
held-out numbers of runs 2 and 3 are no longer fully blind. Run 1 is the first-contact result.

| Run | Source commit | What changed before it | Held-out, AI, correct on right page (strict / any language) |
|---|---|---|---|
| 1 | 3b64904 | first run with a working key | 40% / not measured |
| 2 | cfe3377 | answer language made explicit; German inflections for model terms; graded column | 50% / 80% |
| 3 | see `../LLM_RESULTS.md` | AI-mode gate considers the top four passages; function words damped | see `../LLM_RESULTS.md` |

Earlier, on 13 Nov, the v3 live run failed with `AuthenticationError` for every question
(`docs/submission/archive_v3/`); on 16 Nov the first v4 attempt failed with `expired_secret_key`.
