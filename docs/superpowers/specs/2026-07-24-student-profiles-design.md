# Student Profiles — Design

## Purpose

The teacher currently sees only a single "latest score" per student, from a single skill dimension (`math_reasoning`). A real student profile — strengths, struggles, how they learn best — needs scores across multiple dimensions to synthesize anything meaningful. This builds that: generalizing question generation/grading beyond math, a one-click way to assess a student across all buildable dimensions, and a profile view that shows the breakdown plus an AI-synthesized narrative.

This is one of four subsystems in the broader "what a teacher sees on login" vision (status-colored roster, topic-readiness guidance, student profiles, intervention list — see conversation, not yet its own spec). This slice covers student profiles only.

## Scope

In:
- Generalizing `app/llm/gemini.py` to generate/grade questions for 8 of the platform's 11 seeded skill dimensions: `math_reasoning`, `reading_comprehension`, `critical_thinking`, `creative_thinking`, `written_communication`, `collaboration`, `social_awareness`, `emotional_intelligence`.
- A teacher-triggered bulk endpoint that generates one question per buildable dimension for a student, best-effort (partial success is a normal outcome, not an error).
- A student-facing flow to answer multiple pending questions in sequence, not just one.
- A teacher-facing profile endpoint + view: per-dimension latest score/feedback, the 3 unbuildable dimensions shown as unavailable, and a Gemini-synthesized narrative summary.

Out (explicitly deferred):
- **reading_fluency, verbal_communication** — both require audio (speech-to-text/read-aloud scoring), which this platform doesn't have (no Azure Speech integration built).
- **attention_focus** — not a question-answerable dimension at all; it's a session-behavior metric (sustained engagement across a session) that nothing currently tracks.
- Trend history / score-over-time charts — profile shows only each dimension's *latest* score, same as the roster does today. No `SkillScoreHistory` table yet.
- Narrative caching/storage — the synthesized summary is regenerated on every profile view, not stored. Simpler for now; means repeated views repeat the Gemini cost. Acceptable trade-off for this slice.
- The other three subsystems from the broader vision (status-colored roster, topic-readiness pipeline, intervention list) — separate, not part of this design.
- A real recurring/scheduled trigger — "Assess full profile" stays a manual teacher-triggered button, consistent with the existing single-question flow.

## Data model

No schema change. `AssessmentItem.correct_answer` (already `NOT NULL String`) is simply `""` for the 7 open-ended dimensions — grading for those is rubric-only, with no answer to match against.

## Backend: Gemini generalization

`app/llm/gemini.py`:
- `generate_math_question(grade_level)` is replaced by `generate_question(dimension_key: str, dimension_name: str, rubric_description: str, grade_level: int) -> {question_text, correct_answer}`.
  - For `dimension_key == "math_reasoning"`, behavior matches today exactly: numeric word problem, `correct_answer` is a real number string.
  - For the other 7, the prompt asks for one open-ended question suited to `rubric_description` and `grade_level` (e.g., a scenario for `emotional_intelligence`, a short passage + question for `reading_comprehension`), and `correct_answer` is always returned as `""`.
- `grade_answer(question_text, correct_answer, student_answer, rubric)` — when `correct_answer == ""`, the prompt drops "must match the correct answer" framing and grades purely against `rubric`, still returning `{score, feedback}` 0-100.

## Backend: bulk generation endpoint

`POST /classes/{class_id}/students/{student_id}/assess-profile` (Bearer, teacher, must own class+student):
- Iterates the 8 buildable dimensions (seeded `SkillDimension` rows, looked up by key). For each: calls `generate_question`, and on success creates a pending `AssessmentItem`; on `GeminiError`, skips that dimension and records the failure — does not abort the batch.
- Response: `{created: list[str], failed: list[str]}` — dimension keys in each bucket. No single dimension's failure raises a 502; the endpoint always returns 200 (or 201) with this breakdown, even if `created` is empty.

## Backend: profile endpoint

`GET /classes/{class_id}/students/{student_id}/profile` (Bearer, teacher, must own class+student):
- For each of the 8 buildable dimensions: `{key, name, latest_score: int | null, latest_feedback: str | null}` (null if the student has no graded `AssessmentItem` for that dimension yet — including if one is still pending/unanswered).
- For the 3 unbuildable dimensions: `{key, name, available: false}`.
- `summary: str` — one Gemini call synthesizing strengths / struggles / how the student learns best, built from whatever scored (non-null) dimensions exist. If zero dimensions are scored yet, `summary` is a fixed string like `"Not enough data yet — assess this student to generate a profile."` (no Gemini call made in that case, since there'd be nothing to synthesize from).

## Frontend: student page

Change from "show `pending[0]`, answer it, done" to a loop: after a successful answer, re-fetch `GET /auth/student/assessments/pending`; if more remain, show the next one; if none remain, show a completion state ("All done — nice work!"). Same single-question-at-a-time UI per step, just repeated.

## Frontend: teacher page

Clicking a student's name (not the existing "Assess" button, which still does the single math-only assessment) opens a profile view:
- The 8 scored dimensions, each showing name + score (or "Not yet assessed") + feedback.
- The 3 unavailable dimensions, visually grayed out, labeled "Not available yet."
- The narrative summary.
- An "Assess full profile" button (calls the bulk endpoint), showing which dimensions succeeded/failed after it returns.

## Error handling

- `generate_question`/`grade_answer` failures behave as today for the single-dimension flows (surfaces as 502, no partial `AssessmentItem` writes).
- The bulk endpoint never surfaces a Gemini failure as an HTTP error — partial success is the expected, normal outcome, reported in the response body.
- The profile endpoint's narrative-synthesis Gemini call: if it fails, `summary` falls back to a fixed string ("Couldn't generate a summary right now — try again shortly.") rather than failing the whole profile request; the per-dimension scores still return normally.

## Testing

- Gemini calls remain mocked in all tests, same pattern as the existing suite (monkeypatch `_client()` or the router-level `gemini_client` reference).
- Bulk endpoint: test that partial failure (mock 2 of 8 dimension calls to raise `GeminiError`) still returns 200 with the correct `created`/`failed` split, and that successful ones actually persisted as `AssessmentItem` rows.
- Profile endpoint: test with zero, partial, and full dimension coverage; test the 3 unavailable dimensions always show `available: false` regardless of data; test the zero-data fallback summary (no Gemini call needed/mocked for that case).
- Frontend: manual verification only, consistent with the existing static pages (no test framework for them).
