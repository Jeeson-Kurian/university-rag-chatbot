# Student check (2–4 students, about 15 minutes each)

Goal: find out whether Course Compass helps real students with **their own** questions,
and whether its "checked" label can be trusted. Results go into `eval/student_results.csv`
and are reported as they are, including failures.

## Message to send

> Hi! I built a small AI assistant for the AAU curricula for a student hackathon and need
> 15 minutes of honest feedback. Open **<demo link>**, pick your programme, and ask 3 real
> questions you have had (or still have) about your curriculum: credits, thesis, exams,
> electives, admission, internships… in English, German or any language. For each one,
> please fill in one row of the sheet (or just reply with the answers). Wrong answers are
> just as useful as right ones. No personal data please.

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
3. Add any question that failed to a new file `eval/student_questions.jsonl` as a fresh
   held-out case; never edit the frozen held-out set.

The participants' names are not recorded. Ask each person for consent to use their
anonymous answers in the hackathon submission.
