# K-12 Autonomous Student Assessment Platform

Gives teachers a fast, accurate picture of their students — both as whole
people (academic, cognitive, social-emotional skills) and as a class facing a
specific upcoming topic — without the teacher authoring, administering, or
grading anything themselves. Assessment generation, delivery, scoring, and
insight synthesis are meant to be done by autonomous agents; the teacher only
consumes results on a dashboard.

Full design: [`docs/superpowers/specs/2026-07-23-student-assessment-platform-design.md`](docs/superpowers/specs/2026-07-23-student-assessment-platform-design.md)

> Built as a hackathon submission (2026-07-23). Scope and stack choices below
> reflect that timeline, not a production deployment.

## Status

Only the **Foundation** is implemented: data model, database migrations, and
auth. No frontend yet, and none of the assessment-generation pipelines
(whole-child assessment, topic-readiness) exist yet — see
[`docs/superpowers/plans/2026-07-23-foundation.md`](docs/superpowers/plans/2026-07-23-foundation.md)
for what this covers.

What works today, via the API:
- Teacher signup / login (email + password)
- Student login (teacher-assigned numeric PIN, scoped to their own record)
- Teachers create classes and add students (each student gets a one-time PIN)
- Class roster view
- `SkillDimension` table seeded with the 11 dimensions the platform will
  eventually grade against

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **Auth:** JWT (python-jose), bcrypt password/PIN hashing (passlib)
- **Database:** SQLite for local dev/test (see note below)
- **Frontend, LLM pipelines, TTS/STT, video rendering:** not built yet —
  planned stack for those is in the design spec

**Note on the database:** the design spec calls for Postgres. Local dev runs
SQLite instead — Postgres install was blocked in this environment (no Docker,
blocked installer) and the swap kept the hackathon timeline unblocked. See
commit `f4e998b`.

## Getting started

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Interactive API docs (Swagger UI): http://localhost:8000/docs

Run the tests:

```bash
pytest -v
```

## Project layout

```
backend/
  app/
    models/       # SQLAlchemy models (School, Teacher, SchoolClass, Student, SkillDimension)
    schemas/       # Pydantic request/response schemas
    auth/          # password/PIN hashing, JWT, auth dependencies
    routers/       # FastAPI route handlers
    seed/          # seed data (the 11 skill dimensions)
  alembic/         # database migrations
  tests/
docs/
  superpowers/
    specs/         # design specs
    plans/         # implementation plans
```
