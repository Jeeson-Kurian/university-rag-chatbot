# Student check (2–4 students, about 15 minutes each)

Goal: find out whether Course Compass helps real students with **their own** questions,
and whether its "checked" label can be trusted. Results go into `eval/student_results.csv`
and are reported as they are, including failures.

## Message to send

> Hi! I built a small AI assistant for the AAU curricula for a student hackathon and need
> 15 minutes of honest feedback. Before opening the demo, write down three questions you
> genuinely have about your programme, in the language you would normally use. Then open
> **<demo link>**, select your programme and try those same questions. For each one,
> please fill in one row of the sheet (or just reply with the answers). Wrong answers are
> just as useful as right ones. No personal data please.

## Before running the evaluation

With the participants’ permission, preserve their original wording and assign each question an anonymous ID. Record the curriculum edition, expected fact and source page, or the reason the documents cannot answer it. Have a human check those labels against the curriculum before seeing any model output. Freeze the complete question set and labels in a dated snapshot and record its hash with the application revision. Keep unpublished participant material private.

## For each question (one row)

| Column | What to write |
|---|---|
| `programme` | AIandCybersecurity, Informatics, English or Business |
| `question` | Exactly what you typed |
| `language` | en / de / it / … |
| `answer_was` | `correct`, `partly`, `wrong`, `no_answer_but_it_exists`, `no_answer_correctly` |
| `label_shown` | The coloured label: `checked twice`, `words and numbers match`, `partly confirmed`, `not answered`, `contradicted`, `not in the documents` |
| `page_helped` | `yes` / `no`: did the highlighted page let you confirm the answer? |
| `seconds_to_answer` | Roughly how long until you were confident (reading the page included) |
| `would_use_again` | 1 (no) – 5 (definitely) |
| `comment` | Anything: confusing, missing, wrong, nice |

How to judge `answer_was`: compare with the official curriculum (the highlighted page is
fine if you trust it, or open the PDF). If unsure, write `partly` and explain in the comment.

## After collecting

1. Put the rows in `eval/student_results.csv` (template in this folder).
2. Run `python scripts/summarise_students.py` to produce `eval/STUDENT_RESULTS.md`.
3. Score the first run on the complete frozen set. For answerable questions, count the expected page in the top four separately from a correct answer supported by a citation. For unsupported questions, report appropriate abstention. Give counts and denominators for each measure.
4. For a disputed answer, have a second human check the question, expected fact, cited page and answer without seeing the model grade. Preserve the original scores, final judgement and reason. Report unresolved disagreements explicitly.
5. Keep difficult questions discovered during the session as regression cases. If a fix uses the pilot results, label the next run as a retest. A new first-run estimate requires fresh, unseen questions.

The participants' names are not recorded. Ask each person for consent to use their
anonymous answers in the hackathon submission and, separately, for permission to publish any verbatim text on GitHub. Record only material covered by that permission.
