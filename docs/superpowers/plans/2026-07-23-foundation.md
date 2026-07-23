# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend foundation — data model, database migrations, and auth — that every later pipeline (whole-child assessment, dashboard, topic-readiness) builds on.

**Architecture:** FastAPI backend with SQLAlchemy 2.0 models and Alembic migrations, backed by SQLite for local dev/test (file-based, zero-install — swapped in for the hackathon timeline; see note below). Two separate auth flows on the same JWT mechanism: teachers use email+password; students use a teacher-assigned numeric PIN scoped to their own record, since most students are too young for email-based accounts. No frontend in this plan — every deliverable is verified via FastAPI's test client against a real SQLite test database. The React app starts in the dashboard plan, which needs a UI shell anyway.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, SQLite (file-based), Pydantic v2 / pydantic-settings, passlib[bcrypt], python-jose[cryptography], pytest, httpx.

**Database note (2026-07-23):** The spec (§2) calls for Postgres, but this machine has no Docker and the native Postgres installer host was blocked by the local network — a dead end not worth spending hackathon time on. SQLite needs no install/service and is used here instead. SQLAlchemy/Alembic abstract most of the difference; the one real risk is Alembic's `ALTER TABLE` limitations on SQLite (it doesn't support most in-place alters), which don't bite here since every migration in this plan is an initial `CREATE TABLE`. Revisit before a real multi-user deployment.

## Global Constraints

- Backend is Python (FastAPI); data layer is SQLite for now, see the database note above — per spec §2 (originally Postgres).
- Single-school pilot: every table carries `school_id` so multi-school isolation can be added later without a rewrite — per spec §2, §7.
- Each student has their own individual device/login (not shared classroom devices) — per spec §2.
- Grade tiers are Early (K-5, represented as grade_level 0-5) and Late (6-12) — per spec §2.
- COPPA/FERPA-style compliance (consent, retention policy) is explicitly deferred for this pilot; data minimization and role-based access are still followed as defaults — per spec §2, §9.

---

## File Structure

```
backend/
  app/
    __init__.py
    main.py                    # FastAPI app, router registration
    config.py                  # Settings (env-driven)
    database.py                # Engine, SessionLocal, Base, get_db
    models/
      __init__.py
      school.py                 # School
      teacher.py                 # Teacher
      school_class.py            # SchoolClass (avoids "class" keyword clash)
      student.py                  # Student, grade_tier()
      skill_dimension.py          # SkillDimension
    schemas/
      __init__.py
      auth.py                    # Token, TeacherSignupIn, TeacherLoginIn, StudentLoginIn
      teacher.py                  # TeacherOut
      school_class.py             # ClassCreateIn, ClassOut, RosterOut
      student.py                  # StudentCreateIn, StudentOut, StudentCreatedOut
    auth/
      __init__.py
      security.py                # hash/verify password+pin, create/decode JWT
      dependencies.py             # get_current_teacher, get_current_student
    routers/
      __init__.py
      health.py
      teacher_auth.py             # signup, login, /teachers/me
      student_auth.py             # login, /auth/student/me
      classes.py                  # create class, roster, add student
    seed/
      __init__.py
      skill_dimensions.py         # SKILL_DIMENSIONS seed list
  alembic/
    env.py
    versions/                     # generated migrations
  alembic.ini
  tests/
    conftest.py
    test_health.py
    test_models_school_teacher.py
    test_models_class_student.py
    test_skill_dimensions.py
    test_teacher_auth.py
    test_classes.py
    test_student_auth.py
  requirements.txt
  .env.example
  .gitignore
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.get_settings() -> Settings` (fields: `database_url: str`, `test_database_url: str`, `secret_key: str`, `access_token_expire_minutes: int`, `student_token_expire_minutes: int`)
- Produces: `app.database.Base` (declarative base), `app.database.engine`, `app.database.get_db` (FastAPI dependency yielding a `Session`)
- Produces: `app.main.app` (the FastAPI instance)
- Produces: `tests/conftest.py` fixtures `db_session` and `client`, reused by every later test file in this plan.

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi>=0.111,<1.0
uvicorn[standard]>=0.30,<1.0
sqlalchemy>=2.0,<3.0
alembic>=1.13,<2.0
pydantic>=2.7,<3.0
pydantic-settings>=2.3,<3.0
passlib[bcrypt]>=1.7,<2.0
python-jose[cryptography]>=3.3,<4.0
pytest>=8.2,<9.0
httpx>=0.27,<1.0
```

- [ ] **Step 2: Create `backend/.env.example`**

```
DATABASE_URL=sqlite:///./data/k12_assessment.db
TEST_DATABASE_URL=sqlite:///./data/k12_assessment_test.db
SECRET_KEY=change-me-in-real-deployments
ACCESS_TOKEN_EXPIRE_MINUTES=720
STUDENT_TOKEN_EXPIRE_MINUTES=120
```

Copy it: `cp backend/.env.example backend/.env` (Windows PowerShell: `Copy-Item backend/.env.example backend/.env`)

- [ ] **Step 3: Create `backend/.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
data/
```

- [ ] **Step 4: Create the data directory for the SQLite files**

Run:
```bash
mkdir -p backend/data
```

Expected: `backend/data/` exists (empty — SQLAlchemy creates the `.db` files inside it on first connection; this directory is gitignored, not the files themselves, per Step 3).

- [ ] **Step 5: Create `backend/app/__init__.py`** (empty file)

- [ ] **Step 6: Create `backend/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str
    secret_key: str
    access_token_expire_minutes: int = 720
    student_token_expire_minutes: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Create `backend/app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 8: Create `backend/app/routers/__init__.py`** (empty file)

- [ ] **Step 9: Create `backend/app/routers/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 10: Create `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
```

- [ ] **Step 11: Create `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base, get_db
from app.main import app

settings = get_settings()
_connect_args = {"check_same_thread": False} if settings.test_database_url.startswith("sqlite") else {}
engine = create_engine(settings.test_database_url, connect_args=_connect_args)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 12: Create `backend/tests/test_health.py`**

```python
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 13: Install dependencies and run the test**

Run:
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
pytest tests/test_health.py -v
```

Expected: `test_health_check PASSED`

- [ ] **Step 14: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/.gitignore backend/app backend/tests
git commit -m "chore: scaffold FastAPI backend with health check"
```

---

### Task 2: School and Teacher models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/school.py`
- Create: `backend/app/models/teacher.py`
- Modify: `backend/app/database.py` (none needed — models import `Base` from it)
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/tests/test_models_school_teacher.py`

**Interfaces:**
- Consumes: `app.database.Base` (Task 1)
- Produces: `app.models.school.School` (fields: `id: int`, `name: str`)
- Produces: `app.models.teacher.Teacher` (fields: `id: int`, `school_id: int`, `email: str` unique, `hashed_password: str`, `full_name: str`)

- [ ] **Step 1: Write the failing test — `backend/tests/test_models_school_teacher.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.school import School
from app.models.teacher import Teacher


def test_create_school_and_teacher(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()

    teacher = Teacher(
        school_id=school.id,
        email="ms.jones@riverside.example",
        hashed_password="hashed",
        full_name="Ms. Jones",
    )
    db_session.add(teacher)
    db_session.flush()

    assert teacher.id is not None
    assert teacher.school_id == school.id


def test_teacher_email_must_be_unique(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()

    db_session.add(
        Teacher(
            school_id=school.id,
            email="dupe@riverside.example",
            hashed_password="hashed",
            full_name="First Teacher",
        )
    )
    db_session.flush()

    db_session.add(
        Teacher(
            school_id=school.id,
            email="dupe@riverside.example",
            hashed_password="hashed",
            full_name="Second Teacher",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_school_teacher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Create `backend/app/models/__init__.py`** (empty file)

- [ ] **Step 4: Create `backend/app/models/school.py`**

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 5: Create `backend/app/models/teacher.py`**

```python
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_models_school_teacher.py -v`
Expected: both tests PASS

- [ ] **Step 7: Initialize Alembic**

Run:
```bash
cd backend
alembic init alembic
```

- [ ] **Step 8: Replace `backend/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
from app.models import school, teacher  # noqa: F401 — ensures models register on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 9: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create schools and teachers"
alembic upgrade head
```

Expected: a new file under `backend/alembic/versions/` containing `create_table('schools', ...)` and `create_table('teachers', ...)`; `alembic upgrade head` completes without error.

- [ ] **Step 10: Commit**

```bash
git add backend/app/models backend/alembic backend/alembic.ini backend/tests/test_models_school_teacher.py
git commit -m "feat: add School and Teacher models with initial migration"
```

---

### Task 3: SchoolClass and Student models

**Files:**
- Create: `backend/app/models/school_class.py`
- Create: `backend/app/models/student.py`
- Modify: `backend/alembic/env.py:7` (add import of new models so autogenerate sees them)
- Create: `backend/tests/test_models_class_student.py`

**Interfaces:**
- Consumes: `app.database.Base`, `app.models.school.School`, `app.models.teacher.Teacher` (Task 2)
- Produces: `app.models.school_class.SchoolClass` (fields: `id: int`, `school_id: int`, `teacher_id: int`, `name: str`, `grade_level: int`)
- Produces: `app.models.student.Student` (fields: `id: int`, `school_id: int`, `class_id: int`, `full_name: str`, `grade_level: int`, `pin_hash: str`)
- Produces: `app.models.student.grade_tier(grade_level: int) -> str` returning `"early"` (0-5) or `"late"` (6-12)

- [ ] **Step 1: Write the failing test — `backend/tests/test_models_class_student.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.student import Student, grade_tier
from app.models.teacher import Teacher


@pytest.fixture()
def school_and_teacher(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    teacher = Teacher(
        school_id=school.id,
        email="teacher@riverside.example",
        hashed_password="hashed",
        full_name="Ms. Jones",
    )
    db_session.add(teacher)
    db_session.flush()
    return school, teacher


def test_create_class_and_student(db_session, school_and_teacher):
    school, teacher = school_and_teacher

    school_class = SchoolClass(
        school_id=school.id, teacher_id=teacher.id, name="Grade 4 Homeroom", grade_level=4
    )
    db_session.add(school_class)
    db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=school_class.id,
        full_name="Maya Chen",
        grade_level=4,
        pin_hash="hashed-pin",
    )
    db_session.add(student)
    db_session.flush()

    assert student.id is not None
    assert student.class_id == school_class.id


def test_student_requires_existing_class(db_session, school_and_teacher):
    school, _teacher = school_and_teacher

    db_session.add(
        Student(
            school_id=school.id,
            class_id=999999,
            full_name="Ghost Student",
            grade_level=4,
            pin_hash="hashed-pin",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "grade_level,expected_tier",
    [(0, "early"), (5, "early"), (6, "late"), (12, "late")],
)
def test_grade_tier(grade_level, expected_tier):
    assert grade_tier(grade_level) == expected_tier
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_class_student.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.school_class'`

- [ ] **Step 3: Create `backend/app/models/school_class.py`**

```python
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 4: Create `backend/app/models/student.py`**

```python
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)


def grade_tier(grade_level: int) -> str:
    return "early" if grade_level <= 5 else "late"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models_class_student.py -v`
Expected: all 4 tests (2 + 2 parametrized... actually 2 + 4 parametrized cases = 6) PASS

- [ ] **Step 6: Register the new models in Alembic — modify `backend/alembic/env.py`**

Change:
```python
from app.models import school, teacher  # noqa: F401 — ensures models register on Base.metadata
```
to:
```python
from app.models import school, school_class, student, teacher  # noqa: F401 — ensures models register on Base.metadata
```

- [ ] **Step 7: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create school_classes and students"
alembic upgrade head
```

Expected: migration creates `school_classes` and `students` tables with foreign keys to `schools`, `teachers`, and `school_classes`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/school_class.py backend/app/models/student.py backend/alembic backend/tests/test_models_class_student.py
git commit -m "feat: add SchoolClass and Student models with grade_tier helper"
```

---

### Task 4: SkillDimension model and seed data

**Files:**
- Create: `backend/app/models/skill_dimension.py`
- Create: `backend/app/seed/__init__.py`
- Create: `backend/app/seed/skill_dimensions.py`
- Modify: `backend/alembic/env.py:7` (add import)
- Create: `backend/tests/test_skill_dimensions.py`

**Interfaces:**
- Consumes: `app.database.Base` (Task 1)
- Produces: `app.models.skill_dimension.SkillDimension` (fields: `id: int`, `key: str` unique, `name: str`, `rubric_description: str`)
- Produces: `app.seed.skill_dimensions.SKILL_DIMENSIONS: list[dict]` (11 entries, each `{"key": ..., "name": ..., "rubric_description": ...}`), consumed by the Alembic data migration in this task and by later plans that grade against these dimensions.

- [ ] **Step 1: Write the failing test — `backend/tests/test_skill_dimensions.py`**

```python
from app.models.skill_dimension import SkillDimension
from app.seed.skill_dimensions import SKILL_DIMENSIONS


def test_seed_list_has_eleven_dimensions():
    assert len(SKILL_DIMENSIONS) == 11
    keys = [d["key"] for d in SKILL_DIMENSIONS]
    assert len(keys) == len(set(keys))  # all unique
    assert "math_reasoning" in keys
    assert "reading_fluency" in keys
    assert "emotional_intelligence" in keys


def test_create_skill_dimension(db_session):
    dim = SkillDimension(
        key="math_reasoning",
        name="Mathematical Reasoning",
        rubric_description="0-100 scale: ...",
    )
    db_session.add(dim)
    db_session.flush()
    assert dim.id is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_dimensions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.skill_dimension'`

- [ ] **Step 3: Create `backend/app/models/skill_dimension.py`**

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SkillDimension(Base):
    __tablename__ = "skill_dimensions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rubric_description: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 4: Create `backend/app/seed/__init__.py`** (empty file)

- [ ] **Step 5: Create `backend/app/seed/skill_dimensions.py`**

```python
SKILL_DIMENSIONS = [
    {
        "key": "math_reasoning",
        "name": "Mathematical Reasoning",
        "rubric_description": "0-100: ability to reason through grade-appropriate quantitative and logical problems.",
    },
    {
        "key": "reading_comprehension",
        "name": "Reading Comprehension",
        "rubric_description": "0-100: understanding of grade-appropriate written passages.",
    },
    {
        "key": "reading_fluency",
        "name": "Reading Fluency",
        "rubric_description": "0-100: pace, accuracy, and pronunciation when reading aloud.",
    },
    {
        "key": "critical_thinking",
        "name": "Critical Thinking",
        "rubric_description": "0-100: ability to analyze, question, and evaluate information or arguments.",
    },
    {
        "key": "creative_thinking",
        "name": "Creative Thinking",
        "rubric_description": "0-100: originality and flexibility in generating ideas or solutions.",
    },
    {
        "key": "verbal_communication",
        "name": "Verbal Communication",
        "rubric_description": "0-100: clarity and effectiveness of spoken responses.",
    },
    {
        "key": "written_communication",
        "name": "Written Communication",
        "rubric_description": "0-100: clarity and effectiveness of written responses.",
    },
    {
        "key": "collaboration",
        "name": "Collaboration",
        "rubric_description": "0-100: judgment in scenario-based items about working with others.",
    },
    {
        "key": "social_awareness",
        "name": "Social Awareness",
        "rubric_description": "0-100: judgment in scenario-based items about reading social situations.",
    },
    {
        "key": "emotional_intelligence",
        "name": "Emotional Intelligence",
        "rubric_description": "0-100: judgment in scenario-based items about recognizing and responding to emotions.",
    },
    {
        "key": "attention_focus",
        "name": "Attention/Focus",
        "rubric_description": "0-100: sustained engagement across an assessment session, most relevant for early tier.",
    },
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_skill_dimensions.py -v`
Expected: both tests PASS

- [ ] **Step 7: Register the model in Alembic — modify `backend/alembic/env.py`**

Change:
```python
from app.models import school, school_class, student, teacher  # noqa: F401 — ensures models register on Base.metadata
```
to:
```python
from app.models import school, school_class, skill_dimension, student, teacher  # noqa: F401 — ensures models register on Base.metadata
```

- [ ] **Step 8: Generate the schema migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create skill_dimensions"
```

- [ ] **Step 9: Create a data migration to seed the 11 rows**

Run:
```bash
alembic revision -m "seed skill_dimensions data"
```

Open the generated file under `backend/alembic/versions/` (the newest one). Alembic has already filled in `revision`, `down_revision`, `branch_labels`, and `depends_on` at the top — do not change those four lines. Add one import, one table helper, and fill in the two function bodies:

```python
from app.seed.skill_dimensions import SKILL_DIMENSIONS

skill_dimensions_table = sa.table(
    "skill_dimensions",
    sa.column("key", sa.String),
    sa.column("name", sa.String),
    sa.column("rubric_description", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(skill_dimensions_table, SKILL_DIMENSIONS)


def downgrade() -> None:
    op.execute("DELETE FROM skill_dimensions")
```

The import goes at the top of the file alongside the existing `from alembic import op` / `import sqlalchemy as sa` lines. The `skill_dimensions_table` definition and both function bodies replace Alembic's auto-generated (empty) `upgrade()`/`downgrade()` stubs.

- [ ] **Step 10: Apply both migrations**

Run:
```bash
alembic upgrade head
```

Expected: no errors. Verify with the `sqlite3` CLI (or Python): `sqlite3 backend/data/k12_assessment.db "SELECT count(*) FROM skill_dimensions;"` returns `11`.

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/skill_dimension.py backend/app/seed backend/alembic backend/tests/test_skill_dimensions.py
git commit -m "feat: add SkillDimension model and seed the 11 skill dimensions"
```

---

### Task 5: Password/PIN hashing and JWT utilities

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1)
- Produces: `app.auth.security.hash_secret(secret: str) -> str`
- Produces: `app.auth.security.verify_secret(secret: str, hashed: str) -> bool`
- Produces: `app.auth.security.create_access_token(subject: str, role: str, expires_minutes: int, extra_claims: dict | None = None) -> str`
- Produces: `app.auth.security.decode_access_token(token: str) -> dict` (raises `jose.JWTError` on invalid/expired token)

- [ ] **Step 1: Write the failing test — `backend/tests/test_security.py`**

```python
import pytest
from jose import jwt

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_secret,
    verify_secret,
)
from app.config import get_settings


def test_hash_and_verify_secret_roundtrip():
    hashed = hash_secret("1234")
    assert hashed != "1234"
    assert verify_secret("1234", hashed) is True
    assert verify_secret("wrong", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="42", role="teacher", expires_minutes=10)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "teacher"


def test_decode_rejects_tampered_token():
    token = create_access_token(subject="42", role="teacher", expires_minutes=10)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.JWTError):
        decode_access_token(tampered)


def test_create_access_token_with_extra_claims():
    token = create_access_token(
        subject="7", role="student", expires_minutes=10, extra_claims={"class_id": 3}
    )
    payload = decode_access_token(token)
    assert payload["class_id"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Create `backend/app/auth/__init__.py`** (empty file)

- [ ] **Step 4: Create `backend/app/auth/security.py`**

```python
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGORITHM = "HS256"


def hash_secret(secret: str) -> str:
    return _pwd_context.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    return _pwd_context.verify(secret, hashed)


def create_access_token(
    subject: str, role: str, expires_minutes: int, extra_claims: dict | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/security.py backend/tests/test_security.py
git commit -m "feat: add password/PIN hashing and JWT helpers"
```

---

### Task 6: Teacher signup and login

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/teacher.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/routers/teacher_auth.py`
- Modify: `backend/app/main.py` (register the new router)
- Create: `backend/tests/test_teacher_auth.py`

**Interfaces:**
- Consumes: `app.models.school.School`, `app.models.teacher.Teacher` (Task 2); `app.auth.security.*` (Task 5); `app.database.get_db` (Task 1)
- Produces: `POST /teachers/signup` — body `TeacherSignupIn{email, password, full_name}` → 201 `TeacherOut{id, email, full_name}`
- Produces: `POST /auth/teacher/login` — body `TeacherLoginIn{email, password}` → 200 `Token{access_token, token_type}`
- Produces: `GET /teachers/me` (Bearer auth) → 200 `TeacherOut`
- Produces: `app.auth.dependencies.get_current_teacher` — FastAPI dependency, injectable by later routers/plans, returns the authenticated `Teacher` ORM instance or raises `HTTPException(401)`

- [ ] **Step 1: Write the failing test — `backend/tests/test_teacher_auth.py`**

```python
from app.models.school import School


def _seed_school(db_session) -> School:
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    return school


def test_signup_creates_teacher(client, db_session):
    _seed_school(db_session)
    db_session.commit()

    response = client.post(
        "/teachers/signup",
        json={"email": "ms.jones@riverside.example", "password": "correct-horse", "full_name": "Ms. Jones"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ms.jones@riverside.example"
    assert "password" not in body


def test_signup_rejects_duplicate_email(client, db_session):
    _seed_school(db_session)
    db_session.commit()

    client.post(
        "/teachers/signup",
        json={"email": "dupe@riverside.example", "password": "correct-horse", "full_name": "First"},
    )
    response = client.post(
        "/teachers/signup",
        json={"email": "dupe@riverside.example", "password": "another-pass", "full_name": "Second"},
    )
    assert response.status_code == 409


def test_login_with_correct_credentials(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "login@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )

    response = client.post(
        "/auth/teacher/login", json={"email": "login@riverside.example", "password": "correct-horse"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_rejects_wrong_password(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "wrongpass@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )

    response = client.post(
        "/auth/teacher/login", json={"email": "wrongpass@riverside.example", "password": "not-it"}
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "me@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "me@riverside.example", "password": "correct-horse"}
    )
    token = login.json()["access_token"]

    ok = client.get("/teachers/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "me@riverside.example"

    unauthorized = client.get("/teachers/me")
    assert unauthorized.status_code == 401

    bad_token = client.get("/teachers/me", headers={"Authorization": "Bearer garbage"})
    assert bad_token.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_teacher_auth.py -v`
Expected: FAIL with `404 Not Found` / route errors (routes don't exist yet)

- [ ] **Step 3: Create `backend/app/schemas/__init__.py`** (empty file)

- [ ] **Step 4: Create `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr


class TeacherSignupIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class TeacherLoginIn(BaseModel):
    email: EmailStr
    password: str


class StudentLoginIn(BaseModel):
    student_id: int
    pin: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 5: Create `backend/app/schemas/teacher.py`**

```python
from pydantic import BaseModel


class TeacherOut(BaseModel):
    id: int
    email: str
    full_name: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Create `backend/app/auth/dependencies.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models.teacher import Teacher

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise unauthorized
    if payload.get("role") != "teacher":
        raise unauthorized
    teacher = db.get(Teacher, int(payload["sub"]))
    if teacher is None:
        raise unauthorized
    return teacher
```

- [ ] **Step 7: Create `backend/app/routers/teacher_auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_teacher
from app.auth.security import create_access_token, hash_secret, verify_secret
from app.config import get_settings
from app.database import get_db
from app.models.school import School
from app.models.teacher import Teacher
from app.schemas.auth import TeacherLoginIn, TeacherSignupIn, Token
from app.schemas.teacher import TeacherOut

router = APIRouter()


@router.post("/teachers/signup", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def signup(payload: TeacherSignupIn, db: Session = Depends(get_db)):
    existing = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    school = db.query(School).first()
    if school is None:
        raise HTTPException(status_code=500, detail="No school configured for this pilot")

    teacher = Teacher(
        school_id=school.id,
        email=payload.email,
        hashed_password=hash_secret(payload.password),
        full_name=payload.full_name,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.post("/auth/teacher/login", response_model=Token)
def login(payload: TeacherLoginIn, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    teacher = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if teacher is None or not verify_secret(payload.password, teacher.hashed_password):
        raise unauthorized

    settings = get_settings()
    token = create_access_token(
        subject=str(teacher.id), role="teacher", expires_minutes=settings.access_token_expire_minutes
    )
    return Token(access_token=token)


@router.get("/teachers/me", response_model=TeacherOut)
def me(current_teacher: Teacher = Depends(get_current_teacher)):
    return current_teacher
```

- [ ] **Step 8: Register the router — modify `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import health, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_teacher_auth.py -v`
Expected: all 5 tests PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas backend/app/auth/dependencies.py backend/app/routers/teacher_auth.py backend/app/main.py backend/tests/test_teacher_auth.py
git commit -m "feat: add teacher signup, login, and /teachers/me"
```

---

### Task 7: Class creation and roster management

**Files:**
- Create: `backend/app/schemas/school_class.py`
- Create: `backend/app/schemas/student.py`
- Create: `backend/app/routers/classes.py`
- Modify: `backend/app/main.py` (register the new router)
- Create: `backend/tests/test_classes.py`

**Interfaces:**
- Consumes: `app.auth.dependencies.get_current_teacher` (Task 6); `app.models.school_class.SchoolClass`, `app.models.student.Student` (Task 3); `app.auth.security.hash_secret` (Task 5)
- Produces: `POST /classes` (Bearer, teacher) — body `ClassCreateIn{name, grade_level}` → 201 `ClassOut{id, name, grade_level}`
- Produces: `GET /classes/{class_id}` (Bearer, teacher, must own class) → 200 `RosterOut{id, name, grade_level, students: list[StudentOut]}`
- Produces: `POST /classes/{class_id}/students` (Bearer, teacher, must own class) — body `StudentCreateIn{full_name, grade_level}` → 201 `StudentCreatedOut{id, full_name, grade_level, pin}` (plaintext `pin` returned only here, once)

- [ ] **Step 1: Write the failing test — `backend/tests/test_classes.py`**

```python
from app.models.school import School


def _signup_and_login(client, db_session, email="teacher@riverside.example") -> str:
    school = db_session.query(School).first()
    if school is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()

    client.post(
        "/teachers/signup", json={"email": email, "password": "correct-horse", "full_name": "Teacher"}
    )
    login = client.post("/auth/teacher/login", json={"email": email, "password": "correct-horse"})
    return login.json()["access_token"]


def test_create_class_and_add_student(client, db_session):
    token = _signup_and_login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    class_response = client.post(
        "/classes", json={"name": "Grade 4 Homeroom", "grade_level": 4}, headers=headers
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students",
        json={"full_name": "Maya Chen", "grade_level": 4},
        headers=headers,
    )
    assert student_response.status_code == 201
    body = student_response.json()
    assert body["full_name"] == "Maya Chen"
    assert len(body["pin"]) == 4
    assert body["pin"].isdigit()

    roster = client.get(f"/classes/{class_id}", headers=headers)
    assert roster.status_code == 200
    roster_body = roster.json()
    assert roster_body["name"] == "Grade 4 Homeroom"
    assert len(roster_body["students"]) == 1
    assert roster_body["students"][0]["full_name"] == "Maya Chen"
    assert "pin" not in roster_body["students"][0]


def test_teacher_cannot_view_another_teachers_class(client, db_session):
    token_a = _signup_and_login(client, db_session, email="teacher.a@riverside.example")
    token_b = _signup_and_login(client, db_session, email="teacher.b@riverside.example")

    class_response = client.post(
        "/classes",
        json={"name": "Teacher A's Class", "grade_level": 4},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    class_id = class_response.json()["id"]

    response = client.get(f"/classes/{class_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 404


def test_create_class_requires_auth(client, db_session):
    response = client.post("/classes", json={"name": "No Auth Class", "grade_level": 4})
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classes.py -v`
Expected: FAIL with `404 Not Found` (routes don't exist yet)

- [ ] **Step 3: Create `backend/app/schemas/school_class.py`**

```python
from pydantic import BaseModel

from app.schemas.student import StudentOut


class ClassCreateIn(BaseModel):
    name: str
    grade_level: int


class ClassOut(BaseModel):
    id: int
    name: str
    grade_level: int

    model_config = {"from_attributes": True}


class RosterOut(ClassOut):
    students: list[StudentOut]
```

- [ ] **Step 4: Create `backend/app/schemas/student.py`**

```python
from pydantic import BaseModel


class StudentCreateIn(BaseModel):
    full_name: str
    grade_level: int


class StudentOut(BaseModel):
    id: int
    full_name: str
    grade_level: int

    model_config = {"from_attributes": True}


class StudentCreatedOut(StudentOut):
    pin: str
```

- [ ] **Step 5: Create `backend/app/routers/classes.py`**

```python
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_teacher
from app.auth.security import hash_secret
from app.database import get_db
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.school_class import ClassCreateIn, ClassOut, RosterOut
from app.schemas.student import StudentCreateIn, StudentCreatedOut

router = APIRouter()


def _get_owned_class(class_id: int, teacher: Teacher, db: Session) -> SchoolClass:
    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return school_class


@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreateIn,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = SchoolClass(
        school_id=current_teacher.school_id,
        teacher_id=current_teacher.id,
        name=payload.name,
        grade_level=payload.grade_level,
    )
    db.add(school_class)
    db.commit()
    db.refresh(school_class)
    return school_class


@router.get("/classes/{class_id}", response_model=RosterOut)
def get_roster(
    class_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    students = db.query(Student).filter(Student.class_id == school_class.id).all()
    return RosterOut(
        id=school_class.id,
        name=school_class.name,
        grade_level=school_class.grade_level,
        students=students,
    )


@router.post(
    "/classes/{class_id}/students", response_model=StudentCreatedOut, status_code=status.HTTP_201_CREATED
)
def add_student(
    class_id: int,
    payload: StudentCreateIn,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    pin = f"{secrets.randbelow(10000):04d}"

    student = Student(
        school_id=school_class.school_id,
        class_id=school_class.id,
        full_name=payload.full_name,
        grade_level=payload.grade_level,
        pin_hash=hash_secret(pin),
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return StudentCreatedOut(
        id=student.id, full_name=student.full_name, grade_level=student.grade_level, pin=pin
    )
```

- [ ] **Step 6: Register the router — modify `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import classes, health, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
app.include_router(classes.router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_classes.py -v`
Expected: all 3 tests PASS

- [ ] **Step 8: Run the full test suite**

Run: `pytest -v`
Expected: every test in the suite so far PASSES (no regressions from earlier tasks)

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/school_class.py backend/app/schemas/student.py backend/app/routers/classes.py backend/app/main.py backend/tests/test_classes.py
git commit -m "feat: add class creation and roster management with student PIN generation"
```

---

### Task 8: Student PIN login

**Files:**
- Create: `backend/app/routers/student_auth.py`
- Modify: `backend/app/main.py` (register the new router)
- Modify: `backend/app/auth/dependencies.py` (add `get_current_student`)
- Create: `backend/tests/test_student_auth.py`

**Interfaces:**
- Consumes: `app.models.student.Student` (Task 3); `app.auth.security.verify_secret`, `create_access_token` (Task 5); `app.schemas.auth.StudentLoginIn` (Task 6)
- Produces: `POST /auth/student/login` — body `StudentLoginIn{student_id, pin}` → 200 `Token`
- Produces: `GET /auth/student/me` (Bearer, student) → 200 `StudentOut`
- Produces: `app.auth.dependencies.get_current_student` — FastAPI dependency returning the authenticated `Student` ORM instance or raising `HTTPException(401)`, for use by later plans' student-facing routes

- [ ] **Step 1: Write the failing test — `backend/tests/test_student_auth.py`**

```python
from app.models.school import School


def _create_class_with_student(client, db_session):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()

    client.post(
        "/teachers/signup",
        json={"email": "roster@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "roster@riverside.example", "password": "correct-horse"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    class_response = client.post("/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers)
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    )
    student_body = student_response.json()
    return student_body["id"], student_body["pin"]


def test_student_login_with_correct_pin(client, db_session):
    student_id, pin = _create_class_with_student(client, db_session)

    response = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_student_login_rejects_wrong_pin(client, db_session):
    student_id, _pin = _create_class_with_student(client, db_session)

    response = client.post("/auth/student/login", json={"student_id": student_id, "pin": "0000"})
    assert response.status_code == 401


def test_student_login_rejects_unknown_student_id(client, db_session):
    response = client.post("/auth/student/login", json={"student_id": 999999, "pin": "1234"})
    assert response.status_code == 401


def test_student_me_requires_valid_student_token(client, db_session):
    student_id, pin = _create_class_with_student(client, db_session)
    login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    token = login.json()["access_token"]

    ok = client.get("/auth/student/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["full_name"] == "Maya Chen"

    unauthorized = client.get("/auth/student/me")
    assert unauthorized.status_code == 401


def test_teacher_token_cannot_access_student_me(client, db_session):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "cross@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "cross@riverside.example", "password": "correct-horse"}
    )
    teacher_token = login.json()["access_token"]

    response = client.get("/auth/student/me", headers={"Authorization": f"Bearer {teacher_token}"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_auth.py -v`
Expected: FAIL with `404 Not Found` (routes don't exist yet)

- [ ] **Step 3: Add `get_current_student` — modify `backend/app/auth/dependencies.py`**

Add this import at the top alongside the existing `Teacher` import:
```python
from app.models.student import Student
```

Append this function at the end of the file:
```python
def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Student:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise unauthorized
    if payload.get("role") != "student":
        raise unauthorized
    student = db.get(Student, int(payload["sub"]))
    if student is None:
        raise unauthorized
    return student
```

- [ ] **Step 4: Create `backend/app/routers/student_auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_student
from app.auth.security import create_access_token, verify_secret
from app.config import get_settings
from app.database import get_db
from app.models.student import Student
from app.schemas.auth import StudentLoginIn, Token
from app.schemas.student import StudentOut

router = APIRouter()


@router.post("/auth/student/login", response_model=Token)
def login(payload: StudentLoginIn, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    student = db.get(Student, payload.student_id)
    if student is None or not verify_secret(payload.pin, student.pin_hash):
        raise unauthorized

    settings = get_settings()
    token = create_access_token(
        subject=str(student.id),
        role="student",
        expires_minutes=settings.student_token_expire_minutes,
        extra_claims={"class_id": student.class_id},
    )
    return Token(access_token=token)


@router.get("/auth/student/me", response_model=StudentOut)
def me(current_student: Student = Depends(get_current_student)):
    return current_student
```

- [ ] **Step 5: Register the router — modify `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import classes, health, student_auth, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
app.include_router(classes.router)
app.include_router(student_auth.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_student_auth.py -v`
Expected: all 5 tests PASS

- [ ] **Step 7: Run the full test suite**

Run: `pytest -v`
Expected: every test across all 8 tasks PASSES

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/student_auth.py backend/app/auth/dependencies.py backend/app/main.py backend/tests/test_student_auth.py
git commit -m "feat: add student PIN login and get_current_student dependency"
```

---

## Definition of done

- `pytest -v` passes with zero failures against a real SQLite test database.
- A teacher can sign up, log in, create a class, add a student (receiving that student's one-time PIN), and view the roster.
- A student can log in with `student_id` + PIN and fetch their own profile.
- `SkillDimension` table contains the 11 seeded rows, ready for the whole-child pipeline plan to grade against.
- Every table carries (directly or via FK) a path back to `school_id`, ready for future multi-school support.
