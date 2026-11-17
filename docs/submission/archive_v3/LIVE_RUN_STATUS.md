# Live provider evaluation: blocked by authentication

Run: https://github.com/Jeeson-Kurian/university-rag-chatbot/actions/runs/43443789004

- 45 answerable questions: all returned `Provider error: AuthenticationError`.
- Successful generated answers: 0.
- Eight unsupported questions: all refused before a provider call.
- The workflow received a masked `OPENAI_API_KEY` repository secret; its value was not read or exposed.
- The provider rejected authentication. The stored credential must be repaired or replaced before retesting. No model-quality conclusion can be drawn from this failed connection.
- Reported zero token cost means no successful usage records were returned; it is not an account-billing check.
- The original evaluator returned success despite provider errors. The submitted fix returns status 1 while preserving the diagnostic files. A zero exit status without provider errors still does not guarantee high answer quality.

The untouched original report and JSON are included alongside this note. The offline, no-key walkthrough remains separately labelled.
