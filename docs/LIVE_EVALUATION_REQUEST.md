# Live evaluation request

Requested on 2026-11-13 for the Course Compass AI OpenBuild submission.

This branch push invokes the existing `.github/workflows/llm-eval.yml` workflow, which uses only the `OPENAI_API_KEY` repository secret. It runs the existing 53-question development set once. No credentials are added to repository files.

Inspect the Actions run and its `llm-eval-results` artifact before claiming any live model performance. A missing secret or provider error is a blocked evaluation, not a successful AI demonstration.
