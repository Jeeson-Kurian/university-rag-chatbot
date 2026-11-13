# Course Compass - final submission checklist

Prepared: 13 November 2026. This package is not a Devpost submission confirmation.

## Ready to use

- `Course_Compass_Devpost_Copy.md`: structured submission text, stack and honest disclosures.
- `Course_Compass_Visual_Walkthrough.pdf`: real engine outputs from free extractive mode, source evidence, abstention and a known failure.
- `walkthrough_images/`: PNG pages for a visual walkthrough in the Devpost image gallery. These are walkthrough graphics, not screenshots of the Streamlit app.
- `demo_outputs.json`: full output records underlying the walkthrough.

## Complete in Devpost

1. Open https://ai-openbuild.devpost.com/ and resume the existing Course Compass draft. Do not create a duplicate entry.
2. Check the title, tagline, story, built-with tags and repository URL against the supplied copy.
3. Upload the walkthrough images. Link the PDF from the repository's submission folder once available. The event requests screenshots and a short video or visual walkthrough; this package supplies the visual walkthrough, while actual application screenshots are still needed to meet the wording literally.
4. Confirm the real team list and roles, student status, age and geographic eligibility, source-material rights, and rules/terms acceptance.
5. Add only verified live-demo/video URLs and actual live AI evaluation results. Do not label free-mode outputs as generated AI answers.
6. Review every field, accept the required declarations yourself, and click Submit. Verify that Devpost shows the entry as submitted; saving a draft is not submission.

## Evidence and remaining gaps

- Offline evaluation reproduced from commit `19723f976b5196f4f07683c36ff8ac784dfb8552`: 44/45 expected pages in top four, 8/8 correct abstentions, no label-validation failures.
- The questions form a tuned, AI-assisted development set. No student usage study or held-out evaluation is claimed.
- The known thesis word-count retrieval failure remains. Grounding can pass an irrelevant answer.
- The live evaluation ran on GitHub on 13 November: all 45 answerable questions returned AuthenticationError, zero answers were generated, and the eight unsupported questions were refused. The original workflow reported success despite these errors; the evaluator has now been corrected to return a nonzero status for provider failures. Replace or repair the OPENAI_API_KEY secret in GitHub, then rerun before claiming live AI success. Never paste the key into chat.
- No public app deployment or video was verified during this preparation.
- This workspace could not reach the Devpost UI because its network policy rejected the domain. The draft was neither edited nor submitted here.
- The current event page gives the deadline as 10 December 2026, 23:45 EST: **11 December 2026, 05:45 Vienna time**. Verify the timeline on the submission page before relying on it.

## Optional two-minute recording plan

- 0:00-0:15: explain the risk of a correct-looking answer from the wrong curriculum.
- 0:15-0:45: ask the same thesis-credit question in AI and Cybersecurity and Informatics; open the cited pages and show 23 versus 25 ECTS.
- 0:45-1:10: ask the English-language admission-level question in the English study area; show the German C1 evidence. Identify extractive mode if it returns German text.
- 1:10-1:25: ask the unsupported tuition-fee question; show the refusal.
- 1:25-1:45: demonstrate the failed word-count question and explain why a grounding pass is insufficient.
- 1:45-2:00: show the evaluation table, tuned-development-set caveat and next steps. Only call a segment an AI-mode demo if the provider actually generated its answer.

## Official references

- Event and checklist: https://ai-openbuild.devpost.com/
- Rules: https://ai-openbuild.devpost.com/rules
- Code and reproducibility: https://github.com/Jeeson-Kurian/university-rag-chatbot
