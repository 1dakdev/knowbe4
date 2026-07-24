# Whole-Child Pipeline — Thin Vertical Slice Design

## Purpose

The platform's actual pitch — per
[`2026-07-23-student-assessment-platform-design.md`](2026-07-23-student-assessment-platform-design.md)
— is that autonomous agents generate, deliver, and grade assessments so
teachers just consume results. Nothing built so far (Foundation: auth +
roster; the minimal roster UI) touches that loop. This slice builds the
smallest possible end-to-end version of it — one skill dimension, one
question, one grade — so there is something to demo that shows the actual
idea, ahead of building out the full whole-child pipeline (all 11
dimensions, recurring cycles, trend deltas) or the topic-readiness pipeline.

## Scope

In:
- Teacher triggers question generation for one student, for the
  `math_reasoning` skill dimension
- Gemini generates a word problem scaled to the student's `grade_level`,
  with a single numeric correct answer
- Student answers via their own login; Gemini grades the answer 0-100
  against the dimension's `rubric_description`, with brief feedback
- Teacher's roster shows each student's latest score
- Minimal student-facing page to answer a pending question

Out (explicitly deferred):
- The other 10 skill dimensions
- Recurring/scheduled generation — this slice uses a manual trigger endpoint
  a teacher calls; a real scheduler is separate future work
- Trend charts, trend deltas, decline alerts — this slice produces single
  scores, not a history to trend over yet
- Topic-readiness pipeline (unrelated, separate pipeline per spec)
- Early-tier delivery treatment (narrated audio/video via Azure
  Speech/Remotion) — question is plain text for every grade in this slice
- Multi-question sessions, retries, or question banks — one question per
  trigger, answered once

## Data model

One new table:

```
AssessmentItem
  id: int
  student_id: FK -> students.id
  skill_dimension_id: FK -> skill_dimensions.id
  question_text: str
  correct_answer: str          # numeric, stored as string (e.g. "7")
  student_answer: str | null   # filled when the student answers
  score: int | null            # 0-100, filled when graded
  feedback: str | null         # 1-2 sentence reasoning from Gemini
  created_at: datetime
  answered_at: datetime | null
```

One row covers a question's full lifecycle, from generation through
grading. No separate `SkillScoreHistory` table yet — with one item per
manual trigger, it would just mirror this table 1:1. `SkillScoreHistory`
becomes worth splitting out once there's an actual recurring cycle to
aggregate into trends (a future pipeline plan's concern).

## Backend

New module `app/llm/gemini.py`:
- `generate_math_question(grade_level: int) -> {question_text: str, correct_answer: str}`
- `grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> {score: int, feedback: str}`

Both call the Gemini API with structured/JSON output (so the response
parses reliably rather than needing free-text scraping). New config:
`GEMINI_API_KEY` added to `Settings` and `.env`/`.env.example`. New
dependency: `google-genai` in `requirements.txt`.

New endpoints:
- `POST /classes/{class_id}/students/{student_id}/assessments` (Bearer,
  teacher, must own the class) → calls `generate_math_question`, creates a
  pending `AssessmentItem`, returns `{id, question_text}` — never the
  correct answer.
- `POST /assessments/{item_id}/answer` (Bearer, student, must own the item)
  → body `{answer: str}` → calls `grade_answer`, stores
  `student_answer`/`score`/`feedback`/`answered_at`, returns
  `{score, feedback}`.
- `GET /auth/student/assessments/pending` (Bearer, student) → the calling
  student's own unanswered items.

`GET /classes/{class_id}` (existing roster endpoint) is extended: each
student in the response gains `latest_score: int | null` (their most
recent `AssessmentItem.score`, null if they have none yet).

## Frontend

- **Teacher page** (`backend/static/index.html`, existing): each roster row
  gets an "Assess" button → calls the trigger endpoint, shows a "Question
  sent" confirmation inline. Each row also shows `latest_score` next to the
  student's name when present.
- **Student page** (new: `backend/static/student.html`), same `/ui/` mount,
  standalone (not linked from the teacher page — opened directly for the
  demo):
  - Login view: student ID + PIN → `POST /auth/student/login`
  - Question view: `GET /auth/student/assessments/pending`; if a pending
    item exists, show its `question_text` and a numeric input →
    `POST /assessments/{item_id}/answer` → replace with the returned
    `score`/`feedback`. If none pending, show "No questions right now."

## Error handling

- Gemini call failures (network, rate limit, malformed/unparseable
  response) surface as a `502` to the caller. Generation either fully
  succeeds (item created) or nothing is created — no half-written pending
  item with a missing question. Grading either fully succeeds (item
  updated) or the item is left unanswered so the student can retry.

## Testing

- Gemini calls are mocked/stubbed in the test suite — no real API calls in
  tests (avoids flakiness, cost, rate limits during CI/local runs). The two
  `app/llm/gemini.py` functions are the seam: tests override them (same
  dependency-override pattern already used for `get_db` in
  `tests/conftest.py`) and assert on how the endpoints handle their output,
  including the Gemini-failure path.
- Frontend: manual verification in a browser, consistent with how the
  existing static pages are tested (no test framework for the static
  pages).
