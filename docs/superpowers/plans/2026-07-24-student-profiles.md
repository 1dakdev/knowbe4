# Student Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize question generation/grading beyond `math_reasoning` to 8 skill dimensions, add a one-click "assess full profile" flow, and build a teacher-facing student profile view (per-dimension scores + an AI-synthesized strengths/struggles/learning-style narrative).

**Architecture:** `app/llm/gemini.py`'s math-specific `generate_math_question` becomes a dimension-generic `generate_question`; a new bulk endpoint fans out one generation call per buildable dimension (best-effort, partial success is normal); a new profile endpoint aggregates each dimension's latest graded result plus a fresh Gemini-synthesized summary. The student page is extended to work through multiple pending questions instead of stopping after one.

**Tech Stack:** Same as prior plans (FastAPI, SQLAlchemy 2.0, SQLite, `google-genai`). No new dependencies.

## Global Constraints

- Only 8 of the 11 seeded skill dimensions are buildable: `math_reasoning`, `reading_comprehension`, `critical_thinking`, `creative_thinking`, `written_communication`, `collaboration`, `social_awareness`, `emotional_intelligence`. The other 3 (`reading_fluency`, `verbal_communication`, `attention_focus`) require audio or session-behavior tracking this platform doesn't have — per the design spec's Scope, they must never be silently faked; the profile marks them `available: false`.
- The bulk "assess full profile" endpoint is best-effort: one dimension's `GeminiError` must not fail the whole request or discard other dimensions' successes — per the design spec, it always returns 200 with a `created`/`failed` breakdown.
- `AssessmentItem.correct_answer` stays `NOT NULL`; open-ended dimensions store `""`, not `NULL`. No migration in this plan.
- Gemini calls must never be made from the test suite — same mocking pattern as the existing suite (monkeypatch `_client()` or the router-level `gemini_client` reference).
- `backend/static/index.html` and `backend/static/student.html` currently have **uncommitted, actively-changing content** from concurrent work outside this plan (a visual redesign). Tasks 4 and 5 must read the file's actual current content before editing — do not assume it matches any snippet shown in this plan verbatim, and do not revert or clobber unrelated parts of the redesign. Commit the whole file each time (same as prior plans handled this) — there's no separate git history to preserve for it.

---

## File Structure

```
backend/
  app/
    llm/
      gemini.py                # MODIFY: generate_math_question -> generate_question; grade_answer prompt tweak; new synthesize_profile_summary
    models/
      assessment_item.py       # MODIFY: add latest_result_for_student_dimension()
    schemas/
      assessment.py            # MODIFY: add AssessProfileOut, DimensionResultOut, ProfileOut
    routers/
      assessments.py            # MODIFY: generate_assessment uses generate_question; add assess_profile and get_profile endpoints
  static/
    student.html                # MODIFY: loop through multiple pending questions
    index.html                  # MODIFY: student-name click opens profile view
  tests/
    test_gemini.py               # MODIFY: rename/extend for generate_question; add synthesize_profile_summary tests
    test_assessments.py          # MODIFY: update _stub_generate; add bulk + profile endpoint tests
```

---

### Task 1: Generalize Gemini question generation and grading

**Files:**
- Modify: `backend/app/llm/gemini.py`
- Modify: `backend/app/routers/assessments.py`
- Modify: `backend/tests/test_gemini.py`
- Modify: `backend/tests/test_assessments.py`

**Interfaces:**
- Consumes: nothing new (same `app.config.get_settings()` as before)
- Produces: `app.llm.gemini.generate_question(dimension_key: str, dimension_name: str, rubric_description: str, grade_level: int) -> dict` (keys: `question_text: str`, `correct_answer: str` — `""` for every dimension except `math_reasoning`), replacing `generate_math_question`
- Modifies: `app.llm.gemini.grade_answer(...)` — same signature, but the prompt no longer implies a "correct answer to match" when `correct_answer == ""`
- Produces: `app.llm.gemini.synthesize_profile_summary(results: list[dict]) -> str`, where each dict is `{"dimension_name": str, "score": int, "feedback": str}` — consumed by Task 3

- [ ] **Step 1: Update the failing tests — replace the `generate_math_question` tests in `backend/tests/test_gemini.py` with `generate_question` tests, and add `synthesize_profile_summary` tests**

Replace the two `test_generate_math_question_*` tests with:

```python
def test_generate_question_math_reasoning_returns_numeric_answer(monkeypatch):
    fake_json = '{"question_text": "What is 2 + 2?", "correct_answer": "4"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_question(
        dimension_key="math_reasoning",
        dimension_name="Mathematical Reasoning",
        rubric_description="0-100: ability to reason through grade-appropriate quantitative problems.",
        grade_level=3,
    )

    assert result == {"question_text": "What is 2 + 2?", "correct_answer": "4"}


def test_generate_question_open_ended_returns_empty_correct_answer(monkeypatch):
    fake_json = '{"question_text": "How would you comfort a friend who is upset?"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_question(
        dimension_key="emotional_intelligence",
        dimension_name="Emotional Intelligence",
        rubric_description="0-100: judgment in scenario-based items about recognizing and responding to emotions.",
        grade_level=3,
    )

    assert result == {
        "question_text": "How would you comfort a friend who is upset?",
        "correct_answer": "",
    }


def test_generate_question_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.generate_question(
            dimension_key="math_reasoning",
            dimension_name="Mathematical Reasoning",
            rubric_description="rubric",
            grade_level=1,
        )
```

Keep the existing `test_grade_answer_parses_response` and `test_grade_answer_wraps_errors` tests as-is, and add:

```python
def test_grade_answer_with_no_correct_answer_still_grades(monkeypatch):
    fake_json = '{"score": 75, "feedback": "Thoughtful, could be more specific."}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.grade_answer(
        question_text="How would you comfort a friend who is upset?",
        correct_answer="",
        student_answer="I would sit with them and listen.",
        rubric="0-100: judgment in scenario-based items about recognizing and responding to emotions.",
    )

    assert result == {"score": 75, "feedback": "Thoughtful, could be more specific."}


def test_synthesize_profile_summary_parses_response(monkeypatch):
    fake_text = "This student shows strong emotional intelligence and solid math reasoning."
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_text))

    result = gemini.synthesize_profile_summary(
        [
            {"dimension_name": "Mathematical Reasoning", "score": 90, "feedback": "Excellent work."},
            {"dimension_name": "Emotional Intelligence", "score": 85, "feedback": "Thoughtful responses."},
        ]
    )

    assert result == fake_text


def test_synthesize_profile_summary_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.synthesize_profile_summary(
            [{"dimension_name": "Mathematical Reasoning", "score": 90, "feedback": "Excellent."}]
        )
```

Note: `_FakeResponse`/`_FakeModels`/`_FakeClient` already exist at the top of `test_gemini.py` from the prior plan — reuse them as-is. `synthesize_profile_summary` returns plain text (`response.text`), not JSON, so `_FakeClient(fake_text)` works directly with the existing fakes (they just set `.text` on the response).

- [ ] **Step 2: Run tests to verify the new/changed ones fail**

Run: `pytest tests/test_gemini.py -v`
Expected: FAIL — `AttributeError: module 'app.llm.gemini' has no attribute 'generate_question'` (and similarly for `synthesize_profile_summary`)

- [ ] **Step 3: Replace `generate_math_question` with `generate_question` in `backend/app/llm/gemini.py`**

Replace the entire `generate_math_question` function with:

```python
def generate_question(
    dimension_key: str, dimension_name: str, rubric_description: str, grade_level: int
) -> dict:
    if dimension_key == "math_reasoning":
        prompt = (
            f"Generate one math word problem appropriate for a student in grade {grade_level} "
            "(grade 0 means kindergarten). The problem must have a single numeric correct answer. "
            "Keep it to 1-2 sentences. Scale difficulty to the grade: grades 0-2 use single-step "
            "addition/subtraction with numbers under 20; grades 3-5 use multi-digit arithmetic or "
            "simple multiplication/division; grades 6-8 use multi-step arithmetic or basic algebra; "
            "grades 9-12 use algebra, geometry, or multi-step reasoning."
        )
        schema = {
            "type": "object",
            "properties": {
                "question_text": {"type": "string"},
                "correct_answer": {"type": "string"},
            },
            "required": ["question_text", "correct_answer"],
        }
    else:
        prompt = (
            f"Generate one open-ended assessment question for the skill dimension "
            f"'{dimension_name}' (rubric: {rubric_description}), appropriate for a student in "
            f"grade {grade_level} (grade 0 means kindergarten). Keep it to 2-4 sentences, "
            "including any scenario or short passage needed. The question should have no single "
            "correct answer — it will be graded qualitatively against the rubric."
        )
        schema = {
            "type": "object",
            "properties": {"question_text": {"type": "string"}},
            "required": ["question_text"],
        }

    try:
        client = _client()
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        data = json.loads(response.text)
        if dimension_key == "math_reasoning":
            return {"question_text": data["question_text"], "correct_answer": str(data["correct_answer"])}
        return {"question_text": data["question_text"], "correct_answer": ""}
    except Exception as exc:
        raise GeminiError(f"Question generation failed: {exc}") from exc
```

- [ ] **Step 4: Update `grade_answer`'s prompt to handle an empty `correct_answer` — modify `backend/app/llm/gemini.py`**

Replace the `grade_answer` function's body (keep the signature and the `try`/`except` structure) — change:

```python
def grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> dict:
    prompt = (
        f"Question: {question_text}\n"
        f"Correct answer: {correct_answer}\n"
        f"Student's answer: {student_answer}\n"
        f"Grading rubric: {rubric}\n\n"
        "Score the student's answer from 0 to 100 based on correctness (a numeric answer "
        "equivalent to the correct answer should score highly) and give one brief sentence of "
        "feedback explaining the score."
    )
```

to:

```python
def grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> dict:
    if correct_answer:
        answer_line = f"Correct answer: {correct_answer}\n"
        correctness_note = "a numeric answer equivalent to the correct answer should score highly"
    else:
        answer_line = ""
        correctness_note = "there is no single correct answer — grade based solely on the rubric"
    prompt = (
        f"Question: {question_text}\n"
        f"{answer_line}"
        f"Student's answer: {student_answer}\n"
        f"Grading rubric: {rubric}\n\n"
        f"Score the student's answer from 0 to 100 based on correctness ({correctness_note}) "
        "and give one brief sentence of feedback explaining the score."
    )
```

- [ ] **Step 5: Add `synthesize_profile_summary` — append to `backend/app/llm/gemini.py`**

```python
def synthesize_profile_summary(results: list[dict]) -> str:
    lines = "\n".join(
        f"- {r['dimension_name']}: {r['score']}/100 — {r['feedback']}" for r in results
    )
    prompt = (
        "Here are a student's assessment results across several skill dimensions:\n"
        f"{lines}\n\n"
        "Write a short paragraph (3-4 sentences) for their teacher summarizing this student's "
        "strengths, where they're struggling, and how they seem to learn best, based only on "
        "this data. Be specific and actionable, not generic."
    )
    try:
        client = _client()
        response = client.models.generate_content(model=_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as exc:
        raise GeminiError(f"Profile summary failed: {exc}") from exc
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_gemini.py -v`
Expected: all tests PASS (7 total: the 3 `generate_question` tests, `grade_answer_parses_response`, `grade_answer_wraps_errors`, `grade_answer_with_no_correct_answer_still_grades`, both `synthesize_profile_summary` tests)

- [ ] **Step 7: Update the call site — modify `backend/app/routers/assessments.py`**

In `generate_assessment`, change:

```python
    try:
        generated = gemini_client.generate_math_question(student.grade_level)
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Question generation failed")
```

to:

```python
    try:
        generated = gemini_client.generate_question(
            dimension_key=dimension.key,
            dimension_name=dimension.name,
            rubric_description=dimension.rubric_description,
            grade_level=student.grade_level,
        )
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Question generation failed")
```

- [ ] **Step 8: Update the existing test's mock target — modify `backend/tests/test_assessments.py`**

In the `_stub_generate` helper, change:

```python
def _stub_generate(monkeypatch, question_text="What is 2 + 2?", correct_answer="4"):
    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.generate_math_question",
        lambda grade_level: {"question_text": question_text, "correct_answer": correct_answer},
    )
```

to:

```python
def _stub_generate(monkeypatch, question_text="What is 2 + 2?", correct_answer="4"):
    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.generate_question",
        lambda dimension_key, dimension_name, rubric_description, grade_level: {
            "question_text": question_text,
            "correct_answer": correct_answer,
        },
    )
```

Also update the one other reference in that file, in `test_generate_assessment_returns_502_on_gemini_failure`:

```python
    def _raise(grade_level):
        raise GeminiError("boom")

    monkeypatch.setattr("app.routers.assessments.gemini_client.generate_math_question", _raise)
```

to:

```python
    def _raise(dimension_key, dimension_name, rubric_description, grade_level):
        raise GeminiError("boom")

    monkeypatch.setattr("app.routers.assessments.gemini_client.generate_question", _raise)
```

- [ ] **Step 9: Run the full test suite**

Run: `pytest -v`
Expected: every test passes (no regressions in `test_assessments.py`, `test_classes.py`, etc.)

- [ ] **Step 10: Commit**

```bash
git add backend/app/llm/gemini.py backend/app/routers/assessments.py backend/tests/test_gemini.py backend/tests/test_assessments.py
git commit -m "feat: generalize Gemini question generation beyond math_reasoning"
```

---

### Task 2: Bulk "assess full profile" endpoint

**Files:**
- Modify: `backend/app/schemas/assessment.py`
- Modify: `backend/app/routers/assessments.py`
- Modify: `backend/tests/test_assessments.py`

**Interfaces:**
- Consumes: `app.llm.gemini.generate_question`, `GeminiError` (Task 1); `app.models.skill_dimension.SkillDimension`, `app.models.assessment_item.AssessmentItem` (Foundation, prior plan)
- Produces: `POST /classes/{class_id}/students/{student_id}/assess-profile` (Bearer, teacher, must own class+student) → 200 `AssessProfileOut{created: list[str], failed: list[str]}`

- [ ] **Step 1: Write the failing test — append to `backend/tests/test_assessments.py`**

```python
_PROFILE_DIMENSIONS = [
    ("reading_comprehension", "Reading Comprehension", "0-100: understanding of grade-appropriate written passages."),
    ("critical_thinking", "Critical Thinking", "0-100: ability to analyze, question, and evaluate information or arguments."),
    ("creative_thinking", "Creative Thinking", "0-100: originality and flexibility in generating ideas or solutions."),
    ("written_communication", "Written Communication", "0-100: clarity and effectiveness of written responses."),
    ("collaboration", "Collaboration", "0-100: judgment in scenario-based items about working with others."),
    ("social_awareness", "Social Awareness", "0-100: judgment in scenario-based items about reading social situations."),
    ("emotional_intelligence", "Emotional Intelligence", "0-100: judgment in scenario-based items about recognizing and responding to emotions."),
]


def _seed_all_profile_dimensions(db_session):
    _seed_math_dimension(db_session)
    for key, name, rubric in _PROFILE_DIMENSIONS:
        if db_session.query(SkillDimension).filter(SkillDimension.key == key).first() is None:
            db_session.add(SkillDimension(key=key, name=name, rubric_description=rubric))
    db_session.commit()


def test_assess_profile_creates_one_item_per_buildable_dimension(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _seed_all_profile_dimensions(db_session)
    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.generate_question",
        lambda dimension_key, dimension_name, rubric_description, grade_level: {
            "question_text": f"Question for {dimension_key}",
            "correct_answer": "4" if dimension_key == "math_reasoning" else "",
        },
    )

    response = client.post(f"/classes/{class_id}/students/{student_id}/assess-profile", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert sorted(body["created"]) == sorted(
        [
            "math_reasoning", "reading_comprehension", "critical_thinking", "creative_thinking",
            "written_communication", "collaboration", "social_awareness", "emotional_intelligence",
        ]
    )
    assert body["failed"] == []

    items = db_session.query(AssessmentItem).filter(AssessmentItem.student_id == student_id).all()
    assert len(items) == 8


def test_assess_profile_reports_partial_failure(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _seed_all_profile_dimensions(db_session)

    from app.llm.gemini import GeminiError

    def _flaky(dimension_key, dimension_name, rubric_description, grade_level):
        if dimension_key in ("critical_thinking", "collaboration"):
            raise GeminiError("boom")
        return {"question_text": f"Question for {dimension_key}", "correct_answer": ""}

    monkeypatch.setattr("app.routers.assessments.gemini_client.generate_question", _flaky)

    response = client.post(f"/classes/{class_id}/students/{student_id}/assess-profile", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert sorted(body["failed"]) == ["collaboration", "critical_thinking"]
    assert len(body["created"]) == 6
    assert "critical_thinking" not in body["created"]
    assert "collaboration" not in body["created"]


def test_assess_profile_requires_owned_student(client, db_session, monkeypatch):
    headers_a, class_id_a, student_id_a, _pin = _setup_class_with_student(
        client, db_session, email="profile-a@riverside.example"
    )
    _seed_all_profile_dimensions(db_session)
    client.post(
        "/teachers/signup",
        json={"email": "profile-b@riverside.example", "password": "correct-horse", "full_name": "B"},
    )
    login_b = client.post(
        "/auth/teacher/login", json={"email": "profile-b@riverside.example", "password": "correct-horse"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    response = client.post(
        f"/classes/{class_id_a}/students/{student_id_a}/assess-profile", headers=headers_b
    )

    assert response.status_code == 404
```

Add `from app.models.skill_dimension import SkillDimension` to the top of `test_assessments.py` if it isn't already imported (check first — `_seed_math_dimension` already uses it, so it should already be there).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assessments.py -v -k assess_profile`
Expected: FAIL with `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add `AssessProfileOut` — modify `backend/app/schemas/assessment.py`**

Append:

```python
class AssessProfileOut(BaseModel):
    created: list[str]
    failed: list[str]
```

- [ ] **Step 4: Add the endpoint — modify `backend/app/routers/assessments.py`**

Add this constant near `_MATH_DIMENSION_KEY`:

```python
_PROFILE_DIMENSION_KEYS = [
    "math_reasoning",
    "reading_comprehension",
    "critical_thinking",
    "creative_thinking",
    "written_communication",
    "collaboration",
    "social_awareness",
    "emotional_intelligence",
]
```

Add this import: `from app.schemas.assessment import AssessProfileOut` alongside the existing schema import (combine into one `from app.schemas.assessment import (...)` line).

Add the endpoint (after `generate_assessment`):

```python
@router.post("/classes/{class_id}/students/{student_id}/assess-profile", response_model=AssessProfileOut)
def assess_profile(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(class_id, student_id, current_teacher, db)

    created: list[str] = []
    failed: list[str] = []
    for dimension_key in _PROFILE_DIMENSION_KEYS:
        dimension = db.query(SkillDimension).filter(SkillDimension.key == dimension_key).first()
        if dimension is None:
            failed.append(dimension_key)
            continue
        try:
            generated = gemini_client.generate_question(
                dimension_key=dimension.key,
                dimension_name=dimension.name,
                rubric_description=dimension.rubric_description,
                grade_level=student.grade_level,
            )
        except GeminiError:
            failed.append(dimension_key)
            continue

        item = AssessmentItem(
            student_id=student.id,
            skill_dimension_id=dimension.id,
            question_text=generated["question_text"],
            correct_answer=generated["correct_answer"],
        )
        db.add(item)
        created.append(dimension_key)

    db.commit()
    return AssessProfileOut(created=created, failed=failed)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_assessments.py -v -k assess_profile`
Expected: all 3 new tests PASS

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: every test passes

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/assessment.py backend/app/routers/assessments.py backend/tests/test_assessments.py
git commit -m "feat: add best-effort bulk assess-profile endpoint"
```

---

### Task 3: Student profile endpoint

**Files:**
- Modify: `backend/app/models/assessment_item.py`
- Modify: `backend/app/schemas/assessment.py`
- Modify: `backend/app/routers/assessments.py`
- Modify: `backend/tests/test_assessments.py`

**Interfaces:**
- Consumes: `app.llm.gemini.synthesize_profile_summary` (Task 1); `app.models.skill_dimension.SkillDimension`
- Produces: `app.models.assessment_item.latest_result_for_student_dimension(student_id: int, dimension_id: int, db: Session) -> AssessmentItem | None`
- Produces: `GET /classes/{class_id}/students/{student_id}/profile` (Bearer, teacher, must own class+student) → 200 `ProfileOut{student_id: int, dimensions: list[DimensionResultOut], summary: str}`

- [ ] **Step 1: Write the failing test — append to `backend/tests/test_assessments.py`**

```python
def test_profile_shows_unavailable_dimensions_and_zero_data_summary(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _seed_all_profile_dimensions(db_session)

    response = client.get(f"/classes/{class_id}/students/{student_id}/profile", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == student_id
    by_key = {d["key"]: d for d in body["dimensions"]}
    assert by_key["reading_fluency"]["available"] is False
    assert by_key["verbal_communication"]["available"] is False
    assert by_key["attention_focus"]["available"] is False
    assert by_key["math_reasoning"]["available"] is True
    assert by_key["math_reasoning"]["latest_score"] is None
    assert body["summary"] == "Not enough data yet — assess this student to generate a profile."


def test_profile_includes_scored_dimensions_and_gemini_summary(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _seed_all_profile_dimensions(db_session)

    dimension = db_session.query(SkillDimension).filter(SkillDimension.key == "math_reasoning").first()
    db_session.add(
        AssessmentItem(
            student_id=student_id, skill_dimension_id=dimension.id, question_text="Q",
            correct_answer="4", student_answer="4", score=95, feedback="Great job.",
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.synthesize_profile_summary",
        lambda results: "This student excels at math reasoning.",
    )

    response = client.get(f"/classes/{class_id}/students/{student_id}/profile", headers=headers)

    assert response.status_code == 200
    body = response.json()
    by_key = {d["key"]: d for d in body["dimensions"]}
    assert by_key["math_reasoning"]["latest_score"] == 95
    assert by_key["math_reasoning"]["latest_feedback"] == "Great job."
    assert body["summary"] == "This student excels at math reasoning."


def test_profile_requires_owned_student(client, db_session, monkeypatch):
    headers_a, class_id_a, student_id_a, _pin = _setup_class_with_student(
        client, db_session, email="profileview-a@riverside.example"
    )
    _seed_all_profile_dimensions(db_session)
    client.post(
        "/teachers/signup",
        json={"email": "profileview-b@riverside.example", "password": "correct-horse", "full_name": "B"},
    )
    login_b = client.post(
        "/auth/teacher/login", json={"email": "profileview-b@riverside.example", "password": "correct-horse"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    response = client.get(f"/classes/{class_id_a}/students/{student_id_a}/profile", headers=headers_b)

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assessments.py -v -k profile`
Expected: FAIL — `404 Not Found` for the two `/profile` tests (the `assess_profile` tests from Task 2 should already pass)

- [ ] **Step 3: Add `latest_result_for_student_dimension` — modify `backend/app/models/assessment_item.py`**

Append after `latest_score_for_student`:

```python
def latest_result_for_student_dimension(
    student_id: int, dimension_id: int, db: Session
) -> "AssessmentItem | None":
    return (
        db.query(AssessmentItem)
        .filter(
            AssessmentItem.student_id == student_id,
            AssessmentItem.skill_dimension_id == dimension_id,
            AssessmentItem.score.isnot(None),
        )
        .order_by(AssessmentItem.created_at.desc())
        .first()
    )
```

- [ ] **Step 4: Add `DimensionResultOut` and `ProfileOut` — modify `backend/app/schemas/assessment.py`**

Append:

```python
class DimensionResultOut(BaseModel):
    key: str
    name: str
    available: bool = True
    latest_score: int | None = None
    latest_feedback: str | None = None


class ProfileOut(BaseModel):
    student_id: int
    dimensions: list[DimensionResultOut]
    summary: str
```

- [ ] **Step 5: Add the endpoint — modify `backend/app/routers/assessments.py`**

Add this constant near `_PROFILE_DIMENSION_KEYS` (note: this is the full 11, in the same seeded order, unlike `_PROFILE_DIMENSION_KEYS` which is only the 8 buildable ones):

```python
_UNAVAILABLE_DIMENSION_KEYS = {"reading_fluency", "verbal_communication", "attention_focus"}
```

Update the import line from Step 4 of Task 2 to also bring in `DimensionResultOut` and `ProfileOut` (combine into the existing multi-name import from `app.schemas.assessment`).

Add the endpoint (after `assess_profile`):

```python
@router.get("/classes/{class_id}/students/{student_id}/profile", response_model=ProfileOut)
def get_profile(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(class_id, student_id, current_teacher, db)

    all_dimensions = db.query(SkillDimension).all()
    results: list[DimensionResultOut] = []
    scored_for_summary: list[dict] = []
    for dimension in all_dimensions:
        if dimension.key in _UNAVAILABLE_DIMENSION_KEYS:
            results.append(DimensionResultOut(key=dimension.key, name=dimension.name, available=False))
            continue

        latest = latest_result_for_student_dimension(student.id, dimension.id, db)
        if latest is None:
            results.append(DimensionResultOut(key=dimension.key, name=dimension.name))
            continue

        results.append(
            DimensionResultOut(
                key=dimension.key,
                name=dimension.name,
                latest_score=latest.score,
                latest_feedback=latest.feedback,
            )
        )
        scored_for_summary.append(
            {"dimension_name": dimension.name, "score": latest.score, "feedback": latest.feedback}
        )

    if not scored_for_summary:
        summary = "Not enough data yet — assess this student to generate a profile."
    else:
        try:
            summary = gemini_client.synthesize_profile_summary(scored_for_summary)
        except GeminiError:
            summary = "Couldn't generate a summary right now — try again shortly."

    return ProfileOut(student_id=student.id, dimensions=results, summary=summary)
```

Add this import: `from app.models.assessment_item import latest_result_for_student_dimension` alongside the existing `AssessmentItem` import from that module.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_assessments.py -v -k profile`
Expected: all 5 tests PASS (3 from Task 2, 2 new — `test_profile_requires_owned_student` is the 3rd new one, so 6 total matching `-k profile` including `assess_profile` ones since "profile" substring matches both — that's fine, just confirm none fail)

- [ ] **Step 7: Run the full test suite**

Run: `pytest -v`
Expected: every test passes

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/assessment_item.py backend/app/schemas/assessment.py backend/app/routers/assessments.py backend/tests/test_assessments.py
git commit -m "feat: add student profile endpoint with per-dimension scores and AI summary"
```

---

### Task 4: Student page — answer multiple pending questions in sequence

**Files:**
- Modify: `backend/static/student.html`

**Interfaces:**
- Consumes: `GET /auth/student/assessments/pending`, `POST /assessments/{item_id}/answer` (existing, unchanged by this plan)

**Important:** this file has uncommitted changes from concurrent work outside this plan (a visual redesign). Read its actual current content before editing. The change described below is a **functional** one — apply it to whatever the current markup/JS looks like, preserving the existing visual design; do not assume the exact code shown here matches what's on disk.

- [ ] **Step 1: Read the current file and locate the pending-question logic**

Find the function that fetches `/auth/student/assessments/pending` and displays the first item (likely named something like `loadPendingQuestion`), and the answer-submission handler that currently shows a result and stops.

- [ ] **Step 2: Change the "answer submitted" behavior to advance to the next pending question instead of stopping**

The functional change: today, after a successful `POST /assessments/{item_id}/answer`, the page shows the score/feedback and stays there. Change it so that after showing the result briefly (or immediately, whichever fits the current design's pattern for transient state), it re-fetches `GET /auth/student/assessments/pending`:
- If more pending items remain, load and display the next one (same as how the first one is currently loaded) — the student answers it the same way.
- If none remain, show a completion state (e.g., "All done — nice work!") instead of the empty/no-question state used before any assessment existed, if the current design distinguishes those; if not, reusing the existing "no pending question" state is acceptable.

Reference shape of the change (adapt names/structure to match the actual current file):

```javascript
document.getElementById("answer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError("question-error");
  const answerInput = document.getElementById("answer-input");
  try {
    const result = await api(`/assessments/${currentItemId}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer: answerInput.value }),
    });
    // show result as today, then:
    answerInput.value = "";
    await loadPendingQuestion(); // re-fetches and advances to the next pending item, or shows "done"
  } catch (err) {
    showError("question-error", err.message);
  }
});
```

`loadPendingQuestion()` itself doesn't need new logic beyond what it already does (fetch pending, show the first one or a "none pending" state) — calling it again after each answer is what makes it advance, since the just-answered item no longer appears in the pending list.

- [ ] **Step 3: Manually verify in a browser**

Run (from `backend/`):
```bash
uvicorn app.main:app --reload
```

Seed a student with 2+ pending questions (e.g., via the teacher page's "Assess full profile" once Task 2 is deployed, or manually via `curl` against `POST /classes/{class_id}/students/{student_id}/assessments` twice for two different dimensions if Task 2 isn't merged yet). Log in as that student at `http://localhost:8000/ui/student.html`, answer the first question, and confirm the second one appears without needing to reload the page. Answer it too, and confirm a "done" state appears.

- [ ] **Step 4: Commit**

```bash
git add backend/static/student.html
git commit -m "feat: let students work through multiple pending questions in one sitting"
```

---

### Task 5: Teacher page — student profile view

**Files:**
- Modify: `backend/static/index.html`

**Interfaces:**
- Consumes: `POST /classes/{class_id}/students/{student_id}/assess-profile` (Task 2), `GET /classes/{class_id}/students/{student_id}/profile` (Task 3)

**Important:** same caveat as Task 4 — this file has uncommitted, actively-changing content from concurrent work. Read its actual current content before editing; preserve the existing visual design; commit the whole file.

- [ ] **Step 1: Read the current file and locate the roster rendering**

Find where each student's roster row is built (the loop that creates one row per student with their name, score, and "Assess" button).

- [ ] **Step 2: Add a way to open a profile view from the roster**

Functional change: clicking a student's name (as opposed to the existing "Assess" button, which keeps doing the single math-only assessment unchanged) opens a profile view for that student. This can be a new view/section (following whatever view-switching pattern the file already uses — e.g., a `showView`-style function, or toggling `hidden` on sections) containing:

- The student's name as a heading.
- A list of the 8 buildable dimensions, each showing its name, and either its latest score + feedback, or "Not yet assessed" if `latest_score` is null.
- The 3 unavailable dimensions, visually de-emphasized (e.g., grayed out / reduced opacity), labeled "Not available yet."
- The `summary` text from the profile response.
- An "Assess full profile" button that calls `POST /classes/{class_id}/students/{student_id}/assess-profile`, and after it returns, shows which dimensions succeeded/failed (e.g., "Generated 6 of 8 questions — reading_comprehension and collaboration failed, try again") before re-fetching the profile to reflect any newly-pending items (scores will still show "Not yet assessed" until the student actually answers — that's expected, not a bug).
- A way back to the roster (consistent with however "back" navigation already works in the file, e.g. the existing roster-to-classes back button pattern).

Reference shape for the profile-fetching and rendering logic (adapt to match the actual current file's helper functions and CSS classes):

```javascript
async function openProfile(classId, studentId, studentName) {
  clearError("profile-error");
  try {
    const profile = await api(`/classes/${classId}/students/${studentId}/profile`);
    document.getElementById("profile-title").textContent = studentName;
    document.getElementById("profile-summary").textContent = profile.summary;
    const list = document.getElementById("profile-dimensions");
    list.innerHTML = "";
    for (const dim of profile.dimensions) {
      const item = document.createElement("li");
      if (!dim.available) {
        item.className = "dimension-unavailable";
        item.innerHTML = `<span>${dim.name}</span><span>Not available yet</span>`;
      } else if (dim.latest_score === null) {
        item.innerHTML = `<span>${dim.name}</span><span>Not yet assessed</span>`;
      } else {
        item.innerHTML = `<span>${dim.name}</span><span>${dim.latest_score} &mdash; ${dim.latest_feedback}</span>`;
      }
      list.appendChild(item);
    }
    showView("profile"); // or whatever the current view-switching mechanism is
  } catch (err) {
    showError("classes-error", err.message);
  }
}

document.getElementById("assess-full-profile").addEventListener("click", async () => {
  const button = document.getElementById("assess-full-profile");
  button.disabled = true;
  button.textContent = "Generating...";
  try {
    const result = await api(`/classes/${currentClassId}/students/${currentProfileStudentId}/assess-profile`, {
      method: "POST",
    });
    button.textContent = `Generated ${result.created.length} of ${result.created.length + result.failed.length}`;
    if (result.failed.length > 0) {
      showError("profile-error", `Failed: ${result.failed.join(", ")}`);
    }
  } catch (err) {
    showError("profile-error", err.message);
  } finally {
    button.disabled = false;
  }
});
```

- [ ] **Step 3: Manually verify in a browser**

Run (from `backend/`):
```bash
uvicorn app.main:app --reload
```

Log in as a teacher, open a class, click a student's name, and confirm the profile view appears with all 11 dimensions represented (8 real + 3 unavailable) and the zero-data summary message. Click "Assess full profile," confirm it reports success/failure counts, then (once the student answers via the student page) reopen the profile and confirm scores/feedback now appear for answered dimensions and the summary text has changed to a real synthesized paragraph.

- [ ] **Step 4: Commit**

```bash
git add backend/static/index.html
git commit -m "feat: add student profile view to the teacher page"
```

---

## Definition of done

- `pytest -v` passes with zero failures (all Gemini calls mocked).
- A teacher can click "Assess full profile" for a student and get questions generated across all 8 buildable dimensions in one request, with a clear report of any that failed.
- A student can answer multiple pending questions in one sitting on their page, one at a time, without reloading.
- A teacher can open a student's profile and see: real scores/feedback for answered dimensions, "Not yet assessed" for buildable-but-unanswered ones, "Not available yet" for the 3 unbuildable ones, and an AI-synthesized strengths/struggles/learning-style paragraph once at least one dimension is scored.
- A single dimension's Gemini failure (during bulk assessment or summary synthesis) never breaks the whole request — partial results are always usable.
