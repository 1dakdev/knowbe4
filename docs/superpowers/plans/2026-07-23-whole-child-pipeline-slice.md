# Whole-Child Pipeline Thin Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest end-to-end version of the platform's actual pitch — a teacher triggers question generation for a student, Gemini generates a math word problem scaled to the student's grade, the student answers it, Gemini grades it, and the score shows up on the teacher's roster.

**Architecture:** One new SQLAlchemy model (`AssessmentItem`) covering a question's full lifecycle from generation through grading. A thin `app/llm/gemini.py` wrapper around the Gemini API (structured JSON output) that the router calls and tests monkeypatch. Three new endpoints (generate, answer, list-pending) plus one existing endpoint extended (roster now includes each student's latest score). Two static HTML pages (teacher "Assess" button + score display; a new standalone student answer page).

**Tech Stack:** Same as the Foundation plan (FastAPI, SQLAlchemy 2.0, Alembic, SQLite), plus `google-genai` for Gemini API access.

## Global Constraints

- Every table still carries a path back to `school_id` — `AssessmentItem` reaches it via `student_id` → `Student.school_id`, so it does not need its own `school_id` column (per Foundation plan's Global Constraints, satisfied transitively).
- Local dev/test database is SQLite, not Postgres (see Foundation plan's deviation note, commit `f4e998b`) — nothing in this plan changes that.
- This slice covers exactly one skill dimension (`math_reasoning`), one question per manual trigger, numeric free-text answers only — per the design spec's Scope section, no recurring scheduler, no other dimensions, no `SkillScoreHistory` table yet.
- Gemini calls must never be made from the test suite — tests monkeypatch `app.llm.gemini`'s functions (or the module's `_client()` helper), per the spec's Testing section.
- Generation and grading are all-or-nothing: a Gemini failure must not leave a half-written `AssessmentItem` (no question) or a half-graded one (student stuck) — surfaces as `502`.

---

## File Structure

```
backend/
  app/
    config.py                          # add gemini_api_key setting
    llm/
      __init__.py
      gemini.py                        # generate_math_question, grade_answer, GeminiError
    models/
      assessment_item.py                # AssessmentItem, latest_score_for_student()
    schemas/
      assessment.py                     # AssessmentQuestionOut, AssessmentAnswerIn, AssessmentGradedOut
      student.py                        # MODIFY: StudentOut gains latest_score
    routers/
      assessments.py                    # generate / answer / pending endpoints
      classes.py                        # MODIFY: get_roster includes latest_score
    main.py                             # MODIFY: register assessments.router
  alembic/
    env.py                              # MODIFY: import assessment_item
    versions/                           # new migration for assessment_items table
  static/
    index.html                          # MODIFY: "Assess" button + score display
    student.html                        # new: student login + answer page
  tests/
    test_gemini.py                      # new
    test_assessments.py                 # new
    test_classes.py                     # MODIFY: add latest_score test
  requirements.txt                      # add google-genai
  .env.example                          # add GEMINI_API_KEY
```

---

### Task 1: AssessmentItem model, migration, and latest_score helper

**Files:**
- Create: `backend/app/models/assessment_item.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/tests/test_models_assessment_item.py`

**Interfaces:**
- Consumes: `app.database.Base` (Foundation Task 1); `app.models.student.Student`, `app.models.skill_dimension.SkillDimension` (Foundation Tasks 3-4)
- Produces: `app.models.assessment_item.AssessmentItem` (fields: `id: int`, `student_id: int`, `skill_dimension_id: int`, `question_text: str`, `correct_answer: str`, `student_answer: str | None`, `score: int | None`, `feedback: str | None`, `created_at: datetime`, `answered_at: datetime | None`)
- Produces: `app.models.assessment_item.latest_score_for_student(student_id: int, db: Session) -> int | None`, consumed by Task 4

- [ ] **Step 1: Write the failing test — `backend/tests/test_models_assessment_item.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.assessment_item import AssessmentItem, latest_score_for_student
from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.skill_dimension import SkillDimension
from app.models.student import Student
from app.models.teacher import Teacher


@pytest.fixture()
def student_and_dimension(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    teacher = Teacher(
        school_id=school.id, email="t@riverside.example", hashed_password="hashed", full_name="Teacher"
    )
    db_session.add(teacher)
    db_session.flush()
    school_class = SchoolClass(school_id=school.id, teacher_id=teacher.id, name="Grade 4", grade_level=4)
    db_session.add(school_class)
    db_session.flush()
    student = Student(
        school_id=school.id, class_id=school_class.id, full_name="Maya Chen", grade_level=4,
        pin_hash="hashed-pin",
    )
    db_session.add(student)
    dimension = SkillDimension(
        key="math_reasoning", name="Mathematical Reasoning", rubric_description="0-100: ..."
    )
    db_session.add(dimension)
    db_session.flush()
    return student, dimension


def test_create_assessment_item(db_session, student_and_dimension):
    student, dimension = student_and_dimension

    item = AssessmentItem(
        student_id=student.id,
        skill_dimension_id=dimension.id,
        question_text="What is 2 + 2?",
        correct_answer="4",
    )
    db_session.add(item)
    db_session.flush()

    assert item.id is not None
    assert item.score is None
    assert item.answered_at is None


def test_assessment_item_requires_existing_student(db_session, student_and_dimension):
    _student, dimension = student_and_dimension

    db_session.add(
        AssessmentItem(
            student_id=999999,
            skill_dimension_id=dimension.id,
            question_text="What is 2 + 2?",
            correct_answer="4",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_latest_score_for_student_returns_none_when_no_scores(db_session, student_and_dimension):
    student, _dimension = student_and_dimension
    assert latest_score_for_student(student.id, db_session) is None


def test_latest_score_for_student_returns_most_recent_score(db_session, student_and_dimension):
    student, dimension = student_and_dimension

    db_session.add(
        AssessmentItem(
            student_id=student.id, skill_dimension_id=dimension.id, question_text="Q1",
            correct_answer="4", score=60,
        )
    )
    db_session.flush()
    db_session.add(
        AssessmentItem(
            student_id=student.id, skill_dimension_id=dimension.id, question_text="Q2",
            correct_answer="4", score=90,
        )
    )
    db_session.flush()

    assert latest_score_for_student(student.id, db_session) == 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_assessment_item.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.assessment_item'`

- [ ] **Step 3: Create `backend/app/models/assessment_item.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from app.models.skill_dimension import SkillDimension
from app.models.student import Student


class AssessmentItem(Base):
    __tablename__ = "assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    skill_dimension_id: Mapped[int] = mapped_column(ForeignKey("skill_dimensions.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    student_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["Student"] = relationship()
    skill_dimension: Mapped["SkillDimension"] = relationship()


def latest_score_for_student(student_id: int, db: Session) -> int | None:
    item = (
        db.query(AssessmentItem)
        .filter(AssessmentItem.student_id == student_id, AssessmentItem.score.isnot(None))
        .order_by(AssessmentItem.created_at.desc())
        .first()
    )
    return item.score if item else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models_assessment_item.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Register the model in Alembic — modify `backend/alembic/env.py`**

Change:
```python
from app.models import school, school_class, skill_dimension, student, teacher  # noqa: F401 — ensures models register on Base.metadata
```
to:
```python
from app.models import (  # noqa: F401 — ensures models register on Base.metadata
    assessment_item,
    school,
    school_class,
    skill_dimension,
    student,
    teacher,
)
```

- [ ] **Step 6: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create assessment_items"
alembic upgrade head
```

Expected: a new file under `backend/alembic/versions/` containing `create_table('assessment_items', ...)` with foreign keys to `students` and `skill_dimensions`, and an index on `student_id`; `alembic upgrade head` completes without error.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/assessment_item.py backend/alembic backend/tests/test_models_assessment_item.py
git commit -m "feat: add AssessmentItem model and latest_score_for_student helper"
```

---

### Task 2: Gemini client wrapper

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/gemini.py`
- Create: `backend/tests/test_gemini.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Foundation Task 1)
- Produces: `app.llm.gemini.generate_math_question(grade_level: int) -> dict` (keys: `question_text: str`, `correct_answer: str`)
- Produces: `app.llm.gemini.grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> dict` (keys: `score: int`, `feedback: str`)
- Produces: `app.llm.gemini.GeminiError` (exception, raised on any generation/grading failure)
- Produces: `app.llm.gemini._client()` — the monkeypatch seam tests use to avoid real network calls

- [ ] **Step 1: Add `gemini_api_key` to Settings — modify `backend/app/config.py`**

Change:
```python
    access_token_expire_minutes: int = 720
    student_token_expire_minutes: int = 120
```
to:
```python
    access_token_expire_minutes: int = 720
    student_token_expire_minutes: int = 120
    gemini_api_key: str = ""
```

- [ ] **Step 2: Add `GEMINI_API_KEY` to `backend/.env.example`**

Append:
```
GEMINI_API_KEY=your-gemini-api-key-here
```

Add the same line (with your real key) to your local `backend/.env` — it is not committed, and required to actually call Gemini. Tests do not need a real value since they never call the network (see Step 3 below).

- [ ] **Step 3: Write the failing test — `backend/tests/test_gemini.py`**

```python
import pytest

from app.llm import gemini


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text):
        self._text = text

    def generate_content(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.models = _FakeModels(text)


def test_generate_math_question_parses_response(monkeypatch):
    fake_json = '{"question_text": "What is 2 + 2?", "correct_answer": "4"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_math_question(grade_level=1)

    assert result == {"question_text": "What is 2 + 2?", "correct_answer": "4"}


def test_generate_math_question_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.generate_math_question(grade_level=1)


def test_grade_answer_parses_response(monkeypatch):
    fake_json = '{"score": 90, "feedback": "Correct, well done."}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.grade_answer(
        question_text="What is 2 + 2?",
        correct_answer="4",
        student_answer="4",
        rubric="0-100: ability to reason through grade-appropriate quantitative problems.",
    )

    assert result == {"score": 90, "feedback": "Correct, well done."}


def test_grade_answer_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.grade_answer(
            question_text="What is 2 + 2?", correct_answer="4", student_answer="4", rubric="rubric",
        )
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_gemini.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm'`

- [ ] **Step 5: Add `google-genai` to `backend/requirements.txt`**

Append:
```
google-genai>=1.0,<2.0
```

Install it: `pip install "google-genai>=1.0,<2.0"`

- [ ] **Step 6: Create `backend/app/llm/__init__.py`** (empty file)

- [ ] **Step 7: Create `backend/app/llm/gemini.py`**

```python
import json

from google import genai
from google.genai import types

from app.config import get_settings

_MODEL = "gemini-2.0-flash"


class GeminiError(Exception):
    pass


def _client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def generate_math_question(grade_level: int) -> dict:
    prompt = (
        f"Generate one math word problem appropriate for a student in grade {grade_level} "
        "(grade 0 means kindergarten). The problem must have a single numeric correct answer. "
        "Keep it to 1-2 sentences. Scale difficulty to the grade: grades 0-2 use single-step "
        "addition/subtraction with numbers under 20; grades 3-5 use multi-digit arithmetic or "
        "simple multiplication/division; grades 6-8 use multi-step arithmetic or basic algebra; "
        "grades 9-12 use algebra, geometry, or multi-step reasoning."
    )
    try:
        response = _client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "question_text": {"type": "string"},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["question_text", "correct_answer"],
                },
            ),
        )
        data = json.loads(response.text)
        return {"question_text": data["question_text"], "correct_answer": str(data["correct_answer"])}
    except Exception as exc:
        raise GeminiError(f"Question generation failed: {exc}") from exc


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
    try:
        response = _client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer"},
                        "feedback": {"type": "string"},
                    },
                    "required": ["score", "feedback"],
                },
            ),
        )
        data = json.loads(response.text)
        return {"score": int(data["score"]), "feedback": data["feedback"]}
    except Exception as exc:
        raise GeminiError(f"Grading failed: {exc}") from exc
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_gemini.py -v`
Expected: all 4 tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/config.py backend/app/llm backend/requirements.txt backend/.env.example backend/tests/test_gemini.py
git commit -m "feat: add Gemini client wrapper for question generation and grading"
```

---

### Task 3: Assessment endpoints (generate, answer, pending)

**Files:**
- Create: `backend/app/schemas/assessment.py`
- Create: `backend/app/routers/assessments.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_assessments.py`

**Interfaces:**
- Consumes: `app.models.assessment_item.AssessmentItem` (Task 1); `app.llm.gemini.generate_math_question`, `grade_answer`, `GeminiError` (Task 2); `app.auth.dependencies.get_current_teacher`, `get_current_student` (Foundation Tasks 6, 8); `app.models.school_class.SchoolClass`, `app.models.student.Student`, `app.models.skill_dimension.SkillDimension` (Foundation Tasks 2-4)
- Produces: `POST /classes/{class_id}/students/{student_id}/assessments` (Bearer, teacher, must own class+student) → 201 `AssessmentQuestionOut{id, question_text}`
- Produces: `POST /assessments/{item_id}/answer` (Bearer, student, must own item) → 200 `AssessmentGradedOut{score, feedback}`
- Produces: `GET /auth/student/assessments/pending` (Bearer, student) → 200 `list[AssessmentQuestionOut]`

- [ ] **Step 1: Write the failing test — `backend/tests/test_assessments.py`**

```python
from app.models.school import School
from app.models.skill_dimension import SkillDimension


def _seed_math_dimension(db_session):
    if db_session.query(SkillDimension).filter(SkillDimension.key == "math_reasoning").first() is None:
        db_session.add(
            SkillDimension(
                key="math_reasoning",
                name="Mathematical Reasoning",
                rubric_description="0-100: ability to reason through grade-appropriate quantitative problems.",
            )
        )
        db_session.commit()


def _setup_class_with_student(client, db_session, email="assess@riverside.example"):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()
    _seed_math_dimension(db_session)

    client.post(
        "/teachers/signup", json={"email": email, "password": "correct-horse", "full_name": "Teacher"}
    )
    login = client.post("/auth/teacher/login", json={"email": email, "password": "correct-horse"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    class_response = client.post("/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers)
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    ).json()
    return headers, class_id, student_response["id"], student_response["pin"]


def _stub_generate(monkeypatch, question_text="What is 2 + 2?", correct_answer="4"):
    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.generate_math_question",
        lambda grade_level: {"question_text": question_text, "correct_answer": correct_answer},
    )


def test_teacher_generates_assessment_for_student(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)

    response = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["question_text"] == "What is 2 + 2?"
    assert "correct_answer" not in body
    assert "id" in body


def test_generate_assessment_requires_owned_student(client, db_session, monkeypatch):
    headers_a, class_id_a, student_id_a, _pin = _setup_class_with_student(
        client, db_session, email="a@riverside.example"
    )
    client.post(
        "/teachers/signup", json={"email": "b@riverside.example", "password": "correct-horse", "full_name": "B"}
    )
    login_b = client.post(
        "/auth/teacher/login", json={"email": "b@riverside.example", "password": "correct-horse"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    _stub_generate(monkeypatch)

    response = client.post(
        f"/classes/{class_id_a}/students/{student_id_a}/assessments", headers=headers_b
    )

    assert response.status_code == 404


def test_generate_assessment_returns_502_on_gemini_failure(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)

    from app.llm.gemini import GeminiError

    def _raise(grade_level):
        raise GeminiError("boom")

    monkeypatch.setattr("app.routers.assessments.gemini_client.generate_math_question", _raise)

    response = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    assert response.status_code == 502


def test_student_answers_assessment_and_gets_graded(client, db_session, monkeypatch):
    headers, class_id, student_id, pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    item = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers).json()

    student_login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.grade_answer",
        lambda question_text, correct_answer, student_answer, rubric: {
            "score": 100, "feedback": "Correct!",
        },
    )

    response = client.post(f"/assessments/{item['id']}/answer", json={"answer": "4"}, headers=student_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 100
    assert body["feedback"] == "Correct!"


def test_student_cannot_answer_another_students_assessment(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    item = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers).json()

    other = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Other Student", "grade_level": 4}, headers=headers
    ).json()
    other_login = client.post(
        "/auth/student/login", json={"student_id": other["id"], "pin": other["pin"]}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.post(f"/assessments/{item['id']}/answer", json={"answer": "4"}, headers=other_headers)

    assert response.status_code == 404


def test_pending_assessments_lists_only_unanswered(client, db_session, monkeypatch):
    headers, class_id, student_id, pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    student_login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    response = client.get("/auth/student/assessments/pending", headers=student_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["question_text"] == "What is 2 + 2?"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assessments.py -v`
Expected: FAIL with `404 Not Found` / route errors (routes don't exist yet)

- [ ] **Step 3: Create `backend/app/schemas/assessment.py`**

```python
from pydantic import BaseModel


class AssessmentQuestionOut(BaseModel):
    id: int
    question_text: str

    model_config = {"from_attributes": True}


class AssessmentAnswerIn(BaseModel):
    answer: str


class AssessmentGradedOut(BaseModel):
    score: int
    feedback: str
```

- [ ] **Step 4: Create `backend/app/routers/assessments.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_student, get_current_teacher
from app.database import get_db
from app.llm import gemini as gemini_client
from app.llm.gemini import GeminiError
from app.models.assessment_item import AssessmentItem
from app.models.school_class import SchoolClass
from app.models.skill_dimension import SkillDimension
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.assessment import AssessmentAnswerIn, AssessmentGradedOut, AssessmentQuestionOut

router = APIRouter()

_MATH_DIMENSION_KEY = "math_reasoning"


def _get_owned_student(class_id: int, student_id: int, teacher: Teacher, db: Session) -> Student:
    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    student = db.get(Student, student_id)
    if student is None or student.class_id != school_class.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.post(
    "/classes/{class_id}/students/{student_id}/assessments",
    response_model=AssessmentQuestionOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_assessment(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(class_id, student_id, current_teacher, db)
    dimension = db.query(SkillDimension).filter(SkillDimension.key == _MATH_DIMENSION_KEY).first()
    if dimension is None:
        raise HTTPException(status_code=500, detail="math_reasoning skill dimension not seeded")

    try:
        generated = gemini_client.generate_math_question(student.grade_level)
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Question generation failed")

    item = AssessmentItem(
        student_id=student.id,
        skill_dimension_id=dimension.id,
        question_text=generated["question_text"],
        correct_answer=generated["correct_answer"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/assessments/{item_id}/answer", response_model=AssessmentGradedOut)
def answer_assessment(
    item_id: int,
    payload: AssessmentAnswerIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    item = db.get(AssessmentItem, item_id)
    if item is None or item.student_id != current_student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    if item.answered_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already answered")

    dimension = db.get(SkillDimension, item.skill_dimension_id)

    try:
        graded = gemini_client.grade_answer(
            question_text=item.question_text,
            correct_answer=item.correct_answer,
            student_answer=payload.answer,
            rubric=dimension.rubric_description,
        )
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Grading failed")

    item.student_answer = payload.answer
    item.score = graded["score"]
    item.feedback = graded["feedback"]
    item.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    return AssessmentGradedOut(score=item.score, feedback=item.feedback)


@router.get("/auth/student/assessments/pending", response_model=list[AssessmentQuestionOut])
def list_pending_assessments(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return (
        db.query(AssessmentItem)
        .filter(AssessmentItem.student_id == current_student.id, AssessmentItem.answered_at.is_(None))
        .all()
    )
```

- [ ] **Step 5: Register the router — modify `backend/app/main.py`**

Change:
```python
from app.routers import classes, health, student_auth, teacher_auth
```
to:
```python
from app.routers import assessments, classes, health, student_auth, teacher_auth
```

And add, alongside the other `app.include_router(...)` calls (before the `app.mount(...)` line):
```python
app.include_router(assessments.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_assessments.py -v`
Expected: all 6 tests PASS

- [ ] **Step 7: Run the full test suite**

Run: `pytest -v`
Expected: every test so far PASSES (no regressions)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/assessment.py backend/app/routers/assessments.py backend/app/main.py backend/tests/test_assessments.py
git commit -m "feat: add assessment generation, answering, and pending-list endpoints"
```

---

### Task 4: Roster shows latest score

**Files:**
- Modify: `backend/app/schemas/student.py`
- Modify: `backend/app/routers/classes.py`
- Modify: `backend/tests/test_classes.py`

**Interfaces:**
- Consumes: `app.models.assessment_item.latest_score_for_student` (Task 1)
- Produces: `app.schemas.student.StudentOut` gains `latest_score: int | None = None`, consumed by any later plan reading roster/student output

- [ ] **Step 1: Write the failing test — append to `backend/tests/test_classes.py`**

```python
def test_roster_shows_latest_score(client, db_session):
    from app.models.assessment_item import AssessmentItem
    from app.models.skill_dimension import SkillDimension

    token = _signup_and_login(client, db_session, email="scores@riverside.example")
    headers = {"Authorization": f"Bearer {token}"}

    class_id = client.post(
        "/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers
    ).json()["id"]
    student_id = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    ).json()["id"]

    dimension = SkillDimension(
        key="math_reasoning", name="Mathematical Reasoning", rubric_description="0-100: ..."
    )
    db_session.add(dimension)
    db_session.flush()
    db_session.add(
        AssessmentItem(
            student_id=student_id, skill_dimension_id=dimension.id, question_text="Q1",
            correct_answer="4", score=60,
        )
    )
    db_session.flush()
    db_session.add(
        AssessmentItem(
            student_id=student_id, skill_dimension_id=dimension.id, question_text="Q2",
            correct_answer="4", score=90,
        )
    )
    db_session.commit()

    roster = client.get(f"/classes/{class_id}", headers=headers)

    assert roster.status_code == 200
    students = roster.json()["students"]
    assert students[0]["latest_score"] == 90


def test_roster_shows_null_latest_score_when_no_assessments(client, db_session):
    token = _signup_and_login(client, db_session, email="noscores@riverside.example")
    headers = {"Authorization": f"Bearer {token}"}

    class_id = client.post(
        "/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers
    ).json()["id"]
    client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    )

    roster = client.get(f"/classes/{class_id}", headers=headers)

    assert roster.status_code == 200
    assert roster.json()["students"][0]["latest_score"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classes.py -v -k latest_score`
Expected: FAIL — `latest_score` key missing from response, or `KeyError`

- [ ] **Step 3: Add `latest_score` to `StudentOut` — modify `backend/app/schemas/student.py`**

Change:
```python
class StudentOut(BaseModel):
    id: int
    full_name: str
    grade_level: int

    model_config = {"from_attributes": True}
```
to:
```python
class StudentOut(BaseModel):
    id: int
    full_name: str
    grade_level: int
    latest_score: int | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Populate it in the roster endpoint — modify `backend/app/routers/classes.py`**

Add this import alongside the existing model imports:
```python
from app.models.assessment_item import latest_score_for_student
```

And add this import alongside the existing schema imports:
```python
from app.schemas.student import StudentOut
```

Change `get_roster`'s body from:
```python
    school_class = _get_owned_class(class_id, current_teacher, db)
    students = db.query(Student).filter(Student.class_id == school_class.id).all()
    return RosterOut(
        id=school_class.id,
        name=school_class.name,
        grade_level=school_class.grade_level,
        students=students,
    )
```
to:
```python
    school_class = _get_owned_class(class_id, current_teacher, db)
    students = db.query(Student).filter(Student.class_id == school_class.id).all()
    student_outs = [
        StudentOut(
            id=s.id,
            full_name=s.full_name,
            grade_level=s.grade_level,
            latest_score=latest_score_for_student(s.id, db),
        )
        for s in students
    ]
    return RosterOut(
        id=school_class.id,
        name=school_class.name,
        grade_level=school_class.grade_level,
        students=student_outs,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_classes.py -v`
Expected: all tests PASS, including the 2 new ones

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: every test so far PASSES (no regressions)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/student.py backend/app/routers/classes.py backend/tests/test_classes.py
git commit -m "feat: show each student's latest assessment score on the roster"
```

---

### Task 5: Teacher page — "Assess" button and score display

**Files:**
- Modify: `backend/static/index.html`

**Interfaces:**
- Consumes: `POST /classes/{class_id}/students/{student_id}/assessments` (Task 3); `GET /classes/{class_id}` now returning `latest_score` per student (Task 4)

- [ ] **Step 1: Update the roster rendering and add the "Assess" button — modify `backend/static/index.html`**

Find the roster-rendering block inside `openRoster()`:
```javascript
      for (const student of roster.students) {
        const item = document.createElement("li");
        item.className = "roster-item";
        item.innerHTML = `<span>${student.full_name}</span><span>Grade ${student.grade_level}</span>`;
        list.appendChild(item);
      }
```

Replace it with:
```javascript
      for (const student of roster.students) {
        const item = document.createElement("li");
        item.className = "roster-item";
        const scoreText = student.latest_score === null ? "No score yet" : `Score: ${student.latest_score}`;
        item.innerHTML = `<span>${student.full_name} (grade ${student.grade_level})</span><span>${scoreText}</span>`;
        const assessButton = document.createElement("button");
        assessButton.textContent = "Assess";
        assessButton.addEventListener("click", async () => {
          assessButton.disabled = true;
          assessButton.textContent = "Sending...";
          try {
            await api(`/classes/${currentClassId}/students/${student.id}/assessments`, { method: "POST" });
            assessButton.textContent = "Question sent";
          } catch (err) {
            assessButton.textContent = "Assess";
            assessButton.disabled = false;
            showError("roster-error", err.message);
          }
        });
        item.appendChild(assessButton);
        list.appendChild(item);
      }
```

- [ ] **Step 2: Manually verify in a browser**

Run (from `backend/`):
```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000/ui/`, log in as a teacher, open a class with a student in it, and confirm:
- Each student row shows "No score yet" (or a number, if they already have one) and an "Assess" button
- Clicking "Assess" calls the endpoint and the button changes to "Question sent" (requires a real `GEMINI_API_KEY` in `.env` to succeed — if the request fails, an error message appears near the roster instead of the button changing, without crashing the page)

- [ ] **Step 3: Commit**

```bash
git add backend/static/index.html
git commit -m "feat: add Assess button and score display to the teacher roster page"
```

---

### Task 6: Student answer page

**Files:**
- Create: `backend/static/student.html`

**Interfaces:**
- Consumes: `POST /auth/student/login` (Foundation Task 8); `GET /auth/student/assessments/pending`, `POST /assessments/{item_id}/answer` (Task 3)

- [ ] **Step 1: Create `backend/static/student.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Student assessment (demo)</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; color: #1a1a1a; }
  h1 { font-size: 1.25rem; }
  form { display: flex; flex-direction: column; gap: 8px; margin: 16px 0; }
  input { padding: 8px; font-size: 1rem; }
  button { padding: 8px; font-size: 1rem; cursor: pointer; }
  .error { color: #b00020; font-size: 0.9rem; }
  .question { background: #f5f5f5; padding: 12px; margin: 12px 0; }
  .result { background: #e6f4ea; border: 1px solid #34a853; padding: 12px; margin: 12px 0; }
  [hidden] { display: none; }
</style>
</head>
<body>

<section id="login-view">
  <h1>Student login</h1>
  <form id="login-form">
    <input type="number" id="login-student-id" placeholder="Student ID" required />
    <input type="text" id="login-pin" placeholder="PIN" required />
    <button type="submit">Log in</button>
  </form>
  <p class="error" id="login-error" hidden></p>
</section>

<section id="question-view" hidden>
  <h1>Your question</h1>
  <div id="no-question" hidden>No questions right now.</div>
  <div id="question-box" hidden>
    <p class="question" id="question-text"></p>
    <form id="answer-form">
      <input type="number" id="answer-input" placeholder="Your answer" required />
      <button type="submit">Submit answer</button>
    </form>
  </div>
  <div class="result" id="result-box" hidden>
    <p id="result-score"></p>
    <p id="result-feedback"></p>
  </div>
  <p class="error" id="question-error" hidden></p>
</section>

<script>
  let token = null;
  let currentItemId = null;

  const views = {
    login: document.getElementById("login-view"),
    question: document.getElementById("question-view"),
  };

  function showView(name) {
    for (const key in views) views[key].hidden = key !== name;
  }

  function showError(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.hidden = false;
  }

  function clearError(elementId) {
    document.getElementById(elementId).hidden = true;
  }

  async function api(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (token) headers.Authorization = "Bearer " + token;
    const response = await fetch(path, Object.assign({}, options, { headers }));
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = (body && body.detail) || `Request failed (${response.status})`;
      throw new Error(message);
    }
    return body;
  }

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearError("login-error");
    const studentId = document.getElementById("login-student-id").value;
    const pin = document.getElementById("login-pin").value;
    try {
      const result = await api("/auth/student/login", {
        method: "POST",
        body: JSON.stringify({ student_id: Number(studentId), pin }),
      });
      token = result.access_token;
      showView("question");
      await loadPendingQuestion();
    } catch (err) {
      showError("login-error", err.message);
    }
  });

  async function loadPendingQuestion() {
    clearError("question-error");
    document.getElementById("result-box").hidden = true;
    try {
      const pending = await api("/auth/student/assessments/pending");
      if (pending.length === 0) {
        document.getElementById("no-question").hidden = false;
        document.getElementById("question-box").hidden = true;
        return;
      }
      currentItemId = pending[0].id;
      document.getElementById("question-text").textContent = pending[0].question_text;
      document.getElementById("no-question").hidden = true;
      document.getElementById("question-box").hidden = false;
    } catch (err) {
      showError("question-error", err.message);
    }
  }

  document.getElementById("answer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearError("question-error");
    const answerInput = document.getElementById("answer-input");
    try {
      const result = await api(`/assessments/${currentItemId}/answer`, {
        method: "POST",
        body: JSON.stringify({ answer: answerInput.value }),
      });
      document.getElementById("question-box").hidden = true;
      document.getElementById("result-score").textContent = `Score: ${result.score}`;
      document.getElementById("result-feedback").textContent = result.feedback;
      document.getElementById("result-box").hidden = false;
      answerInput.value = "";
    } catch (err) {
      showError("question-error", err.message);
    }
  });
</script>

</body>
</html>
```

- [ ] **Step 2: Manually verify in a browser**

With the server still running (`uvicorn app.main:app --reload` from `backend/`), and after using the teacher page to click "Assess" on a student:

1. Open `http://localhost:8000/ui/student.html`
2. Log in with that student's ID and PIN (the PIN was shown once when the student was created via the teacher page)
3. Confirm the question text appears
4. Submit a numeric answer and confirm a score + feedback message appears
5. Reload the page, log in again, and confirm "No questions right now." shows (since the question is now answered)

- [ ] **Step 3: Commit**

```bash
git add backend/static/student.html
git commit -m "feat: add student-facing page to answer pending assessment questions"
```

---

## Definition of done

- `pytest -v` passes with zero failures (all Gemini calls mocked, no real network calls made by the test suite).
- A teacher can click "Assess" on a student in the roster page and a real question is generated via Gemini, scaled to that student's grade level.
- A student can log into the student page, see that question, submit a numeric answer, and see a score (0-100) and brief feedback, both generated by Gemini.
- The teacher's roster page shows that student's latest score after the round-trip.
- A Gemini failure (bad API key, network error, malformed response) surfaces as a clean error in both the API (502) and the UI (inline error message), without leaving a broken half-written `AssessmentItem`.
