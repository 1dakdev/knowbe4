# Minimal Roster UI — Design

## Purpose

A quick, real (not mocked) visual look at the Foundation backend's teacher/roster flow, ahead of the full React dashboard planned separately. Not a step toward that dashboard — throwaway-acceptable, plain HTML/JS, fastest path to "see it in a browser."

## Scope

In:
- Teacher login (email + password)
- List the logged-in teacher's own classes
- Click a class → view its roster (student name + grade)
- Add a student to a class inline, showing the one-time PIN the API returns

Out (no backing data or out of scope for this pass):
- Student login / student-facing UI
- Skill scores, trend charts, agent-generated summaries, decline alerts, topic-readiness — all depend on pipelines not yet built
- Class creation UI (classes already exist from the earlier demo; not worth a form for a throwaway page)
- Any build tooling (React, bundler, npm) — plain HTML/JS only

## Backend change

One new endpoint, following the existing pattern in `app/routers/classes.py`:

- `GET /classes` (Bearer, teacher) → `200 list[ClassOut]` — the calling teacher's own classes (filter `SchoolClass.teacher_id == current_teacher.id`), reusing the existing `ClassOut` schema and `get_current_teacher` dependency.

## Frontend

- Single static file: `backend/static/index.html` (inline `<script>`, inline `<style>`, no framework).
- Served by FastAPI via `StaticFiles` mounted at `/` (or `/ui`) in `app/main.py`.
- Client-side state: JWT held in a JS variable (not persisted) — page reload requires re-login, which is fine for a throwaway demo page.
- Views (all in one page, toggled by JS, no routing library):
  1. **Login view** — email/password form → `POST /auth/teacher/login` → store token → switch to Classes view.
  2. **Classes view** — `GET /classes` → list of classes, each clickable → switch to Roster view.
  3. **Roster view** — `GET /classes/{id}` → student list (name, grade); "Add student" form (name, grade) → `POST /classes/{id}/students` → show returned PIN in a dismissible banner ("Maya Chen's PIN: 3735 — write this down, it won't be shown again").
- Errors (401, 409, etc.) surface as a plain inline message near the relevant form — no toast library.

## Testing

- Backend: one test for `GET /classes` in `tests/test_classes.py` (returns only the calling teacher's classes, matching the existing ownership test pattern in that file).
- Frontend: manual verification in a browser (no test framework for a throwaway static page) — login, see classes, open roster, add a student, confirm PIN shown once.
