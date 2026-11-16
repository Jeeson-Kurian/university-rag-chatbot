# Course Compass: submission materials (v4)

These files prepare the AI OpenBuild entry. They are not proof that the Devpost entry was
submitted.

- [Devpost story (v4 draft)](Course_Compass_Devpost_Copy.md): every `⟦…⟧` must be filled from
  measured results before submitting
- [Submission checklist](Course_Compass_Submission_Checklist.md)
- Screenshots: produced by the *Capture app screenshots* workflow and published on the
  `results/screenshots` branch (`ai/` = AI mode, `free/` = no key)
- Live evaluation: produced by the *Live AI-mode evaluation* workflow and published on the
  `results/llm-eval` branch, then copied to `eval/LLM_RESULTS.md`
- [Student check kit](../student_testing/README.md)
- [`archive_v3/`](archive_v3/): the earlier v3 materials, including the 13 Nov live run that failed
  with `AuthenticationError` (zero generated answers), kept for the record

Status on 16 Nov 2026: the v4 code and offline evaluation are done. The live AI run is blocked
until the `OPENAI_API_KEY` repository secret is replaced, and the public demo needs
`HF_TOKEN` and `HF_SPACE`.
