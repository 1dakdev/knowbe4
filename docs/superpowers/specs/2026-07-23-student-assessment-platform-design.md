# K-12 Autonomous Student Assessment Platform — Design

## 1. Purpose

Give teachers and tutors a fast, accurate picture of the students they're about to teach — both as whole people (academic, cognitive, and social-emotional skills) and as a class facing a specific upcoming topic — without the teacher having to author, administer, or grade anything themselves. All assessment generation, delivery, scoring, and insight synthesis is done by autonomous agents; the teacher only consumes results on a dashboard.

## 2. Scope for this first build

- **Grade tiers:** Early (K–5) and Late (6–12). Same backend pipeline, different delivery UI:
  - Early: narrated/video question delivery, short game-like sessions (attention-span aware), audio input supported.
  - Late: self-directed, primarily text-based.
- **Tenancy:** Single school/pilot. Data model includes a `school_id` on every table so multi-school isolation can be added later without restructuring, but no multi-tenant admin/isolation logic is built now.
- **Delivery setting:** Each student has their own device and login (not shared classroom devices).
- **Compliance (COPPA/FERPA-style):** Explicitly deferred for this pilot. Data minimization and role-based access are still followed as good defaults, but formal consent flows, retention policies, and district data-ownership agreements are out of scope until the platform moves toward real deployment.
- **Stack:** Python backend (FastAPI), Postgres, a scheduler (APScheduler or Celery+Redis) for recurring/triggered pipeline runs, a React web frontend.
  - **LLM (generation/grading/synthesis):** Google Gemini API (free tier for dev/pilot). Fallback for heavy local testing: Ollama running an open-source model, no key required.
  - **Text-to-speech & speech-to-text:** Azure AI Speech free tier — one account covers both narration audio (early-tier delivery) and read-aloud transcription/fluency scoring. Fallback for STT: local Whisper, no key required, useful once free-tier audio-minute quotas get tight during testing.
  - **Video/visual rendering (early-tier delivery):** Remotion — a self-hosted, open-source React-based rendering framework, not a generative video API. The agent fills a template (question text, images, TTS audio timing) and Remotion renders it to MP4 deterministically. No per-call cost, no API key. Static illustrations, if needed, from Pollinations.ai (free, keyless).

## 3. Skill dimensions

Each dimension has a fixed rubric/scoring scale (0–100 or proficiency bands), defined once and reused every cycle. Because assessment items are freshly generated each cycle rather than pulled from a fixed bank, **all grading is against the dimension's rubric, not relative item difficulty** — this is what keeps growth/decline trends meaningful over time.

- Mathematical reasoning
- Reading comprehension
- Reading fluency (from read-aloud passages — pace, accuracy, pronunciation)
- Critical thinking
- Creative thinking
- Verbal communication
- Written communication
- Collaboration
- Social awareness
- Emotional intelligence
- Attention/focus (early tier especially)

Traits that don't map cleanly to a quiz (EQ, social awareness, collaboration) are assessed via **scenario-based judgment items** ("what would you do if...", picture-based social scenarios), scored by an LLM against the dimension's rubric — same mechanism as everything else, just a different item type.

## 4. Shared engine

Both pipelines below are the same underlying engine, configured two different ways — not two separate systems. Shared components:

- **Item-generation agent** — takes grade level (and, for topic-readiness, a topic) as input; calibrates question difficulty to that grade's expected rigor every time.
- **Media-rendering stage** (early tier only) — converts generated items into narrated audio (Azure TTS) + a templated animated video (Remotion renders a React template filled in with the item's text/images and the TTS audio timing — deterministic rendering, not generative video), so non-readers can understand what's being asked without reading text.
- **Read-aloud item type** (both tiers) — student reads a passage aloud (mic capture) → speech-to-text transcription (Azure Speech / local Whisper) → fluency scoring (pace/WPM, accuracy vs. source text, pronunciation) → narrated (early) or text (late) follow-up comprehension questions on the same passage, scored normally.
- **Delivery** — to the student's own login, self-paced; early-tier sessions kept short with game-like pacing to avoid confounding attention data with fatigue.
- **Grading agent** — objective grading for math/reading-with-answer-key items; LLM-rubric grading for open-ended, scenario, and fluency items.

## 5. Pipeline 1 — Whole-child assessment (recurring, fully autonomous)

Scheduled per class/school at a teacher-configurable cadence (default bi-weekly). A student's very first run happens before regular instruction starts, establishing a day-1 baseline that later cycles are measured against.

1. **Generate** — fresh, grade-appropriate items across all skill dimensions (quiz-style, scenario-based, and periodic read-aloud passages).
2. **Render** (early tier) — convert to narrated video/visual form.
3. **Deliver** — to each student's login.
4. **Grade** — score against each dimension's rubric.
5. **Aggregate** — update `SkillScoreHistory`; compute trend deltas vs. the prior cycle.
6. **Publish** — profile updates appear on the teacher dashboard automatically. No teacher action required at any step.

## 6. Pipeline 2 — Topic-readiness assessment (teacher-triggered, autonomous from there)

The teacher's only manual action in the entire platform: entering a topic + grade (e.g., "Algebra, Grade 4").

1. **Trigger** — teacher enters topic + grade.
2. **Generate** — agent creates *preparatory/prerequisite-skill* diagnostic items for that topic and grade — deliberately **not** questions from the topic itself (e.g., for Algebra: number sense, pattern recognition — not algebra problems).
3. **Deliver** — sent to the class.
4. **Grade** — scored into `TopicReadinessSession`, kept entirely separate from `SkillScoreHistory` (the whole-child track).
5. **Synthesize** — a second agent analyzes the class's results, clusters where students stand relative to the prerequisites, and produces **3 distinct teaching angles** (e.g. visual/diagrammatic, real-world analogy, hands-on/kinesthetic) calibrated to how *this* class actually clustered — not generic advice.
6. **Publish** — appears on the teacher dashboard, tied to that topic/class/date.

## 7. Data model

- `School`, `Teacher`, `Class` (roster), `Student`
- `SkillDimension` — the ~11 traits above, each with its rubric definition
- `AssessmentCycle` — one whole-child pipeline run for a student (timestamp, generated items, responses, per-dimension scores)
- `SkillScoreHistory` — time series per student per dimension; the growth/decline trend data
- `TopicReadinessSession` — one topic-readiness run (topic, grade, triggering teacher, generated diagnostic items, per-student results, class-level teaching guidance) — **never merged into `SkillScoreHistory`**

## 8. Teacher dashboard

- **Student profile page** — trend chart per skill dimension over time (growth/decline clearly marked), most recent scores, and a plain-language agent-generated summary each cycle (e.g., "Maya's math reasoning has improved steadily; her written communication dipped this cycle — worth a check-in").
- **Class roster view** — all students at a glance, sortable by dimension.
- **Proactive decline alerts** — the system flags (dashboard badge/notification) when a student's trend crosses a meaningful decline threshold, rather than relying on the teacher to notice by browsing.
- **Topic-readiness view** — per topic session: class-level prerequisite-readiness snapshot plus the 3 teaching angles, tied to the topic and date requested.
- **Flag-for-review control** — a lightweight "flag this question/suggestion" action available to teachers on any agent-generated item or recommendation. Doesn't require teacher action normally; exists as a trust/safety valve since content isn't human-vetted before reaching students.

## 9. Explicitly deferred (not in this build)

- COPPA/FERPA-style consent, retention, and data-ownership handling
- Multi-school/district tenancy and isolation
- Item-bank curation / human-vetted question review
- Shared-device delivery mode

## 10. Testing/validation approach

- Rubric-grading consistency: periodic spot-checks comparing agent-assigned scores against a human-reviewed sample, per skill dimension, to catch rubric drift before it corrupts trend data.
- Pipeline dry-runs with synthetic student data (no real minors) during development, given compliance work is deferred.
- Manual review of a sample of generated read-aloud fluency scores against known transcripts to validate the ASR + scoring approach before relying on it for trend data.
