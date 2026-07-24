# KnowBe4 Wordmark Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder "KB4" square + plain-text "KnowBe4" title in the login and student pages with the approved wordmark logo, and add a matching browser-tab favicon.

**Architecture:** Both pages are static, self-contained HTML files with inline `<style>` blocks (no shared stylesheet, no build step). Each file gets its own copy of the same `.wordmark` CSS rules and the same inline-SVG favicon `<link>`, following the existing pattern of duplicated inline styles per file.

**Tech Stack:** Static HTML/CSS/vanilla JS, served by FastAPI's `StaticFiles` mount at `/ui` (`backend/app/main.py:16`). No test framework covers this static frontend — verification is manual, via a running server.

## Global Constraints

- Design source of truth: `docs/superpowers/specs/2026-07-24-knowbe4-logo-design.md` — colors, font stack, and markup shape below are copied verbatim from it.
- No new font loads — `font-family: 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;` only.
- No separate icon/lockup asset — wordmark only, favicon is generated inline from the same badge shape/colors.
- Dark variant (default `.wordmark`): `Know` `#ffffff`, `Be` `#f59e0b`, badge bg `#f59e0b` / text `#0f2149`.
- Light variant (`.wordmark--light`): `Know` `#0f2149`, `Be` `#ea8a3b`, badge bg `#ea8a3b` / text `#ffffff`.

---

### Task 1: Apply wordmark + favicon to `backend/static/index.html`

**Files:**
- Modify: `backend/static/index.html`

**Interfaces:**
- Produces: `.wordmark` / `.wordmark--light` CSS classes and `wm-know` / `wm-be` / `wm-4` markup pattern, reused identically in Task 2.

- [ ] **Step 1: Add the wordmark CSS block**

In the `<style>` block, immediately after the `:root { ... }` block (`backend/static/index.html:7-18`), insert:

```css
  .wordmark {
    font-family: 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .wordmark .wm-know { color: #ffffff; }
  .wordmark .wm-be { color: #f59e0b; }
  .wordmark .wm-4 {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 0.78em;
    height: 0.78em;
    margin-left: 0.06em;
    border-radius: 50%;
    background: #f59e0b;
    color: #0f2149;
    font-size: 0.62em;
    font-weight: 800;
    vertical-align: middle;
  }
  .wordmark.wordmark--light .wm-know { color: #0f2149; }
  .wordmark.wordmark--light .wm-be { color: #ea8a3b; }
  .wordmark.wordmark--light .wm-4 { background: #ea8a3b; color: #ffffff; }
```

- [ ] **Step 2: Remove the placeholder square logo and its CSS**

Delete the `.login-brand .login-logo` rule block (`backend/static/index.html:52-64`):

```css
  .login-brand .login-logo {
    width: 40px;
    height: 40px;
    margin: 0 0 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 700;
    color: #0f2149;
    background: #fff;
  }
```

Delete the corresponding `<div class="login-logo">KB4</div>` element (`backend/static/index.html:403`).

- [ ] **Step 3: Replace the plain-text heading with the wordmark markup**

Change (`backend/static/index.html:404`):

```html
    <h1>KnowBe4</h1>
```

to:

```html
    <h1><span class="wordmark"><span class="wm-know">Know</span><span class="wm-be">Be</span><span class="wm-4">4</span></span></h1>
```

This is the dark/default variant — no `wordmark--light` — matching the navy `.login-brand` background.

- [ ] **Step 4: Add the favicon link**

In `<head>`, after the `<title>KnowBe4</title>` line (`backend/static/index.html:5`), insert:

```html
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='32' fill='%23f59e0b'/%3E%3Ctext x='32' y='45' font-family='sans-serif' font-size='36' font-weight='800' text-anchor='middle' fill='%230f2149'%3E4%3C/text%3E%3C/svg%3E" />
```

- [ ] **Step 5: Manually verify in a browser**

Run:
```bash
cd backend
.venv/Scripts/activate
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/ui/index.html`. Confirm:
- The navy login panel shows "Know" in white, "Be" in amber, and "4" in an amber circle badge with navy text — no separate square logo above it.
- The browser tab shows the amber circle "4" favicon.
- Switching between the Teacher/Student login tabs still works (unrelated JS untouched).

- [ ] **Step 6: Commit**

```bash
git add backend/static/index.html
git commit -m "feat: apply KnowBe4 wordmark logo and favicon to login page"
```

---

### Task 2: Apply wordmark + favicon to `backend/static/student.html`

**Files:**
- Modify: `backend/static/student.html`

**Interfaces:**
- Consumes: the same `.wordmark` / `wm-know` / `wm-be` / `wm-4` markup pattern produced in Task 1 (this file has its own independent `<style>` block, so the CSS is duplicated here, not shared).

- [ ] **Step 1: Add the wordmark CSS block**

In the `<style>` block, immediately after the existing `body { ... }` rule (`backend/static/student.html:7`), insert:

```css
  .wordmark {
    font-family: 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .wordmark .wm-know { color: #ffffff; }
  .wordmark .wm-be { color: #f59e0b; }
  .wordmark .wm-4 {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 0.78em;
    height: 0.78em;
    margin-left: 0.06em;
    border-radius: 50%;
    background: #f59e0b;
    color: #0f2149;
    font-size: 0.62em;
    font-weight: 800;
    vertical-align: middle;
  }
  .wordmark.wordmark--light .wm-know { color: #0f2149; }
  .wordmark.wordmark--light .wm-be { color: #ea8a3b; }
  .wordmark.wordmark--light .wm-4 { background: #ea8a3b; color: #ffffff; }
```

- [ ] **Step 2: Replace the plain-text heading with the wordmark markup**

Change (`backend/static/student.html:21`):

```html
  <h1>KnowBe4 — Student login</h1>
```

to:

```html
  <h1><span class="wordmark wordmark--light"><span class="wm-know">Know</span><span class="wm-be">Be</span><span class="wm-4">4</span></span> — Student login</h1>
```

This uses the `wordmark--light` variant, matching this page's plain white background (`backend/static/student.html:7` sets no explicit background, defaulting to white).

- [ ] **Step 3: Add the favicon link**

In `<head>`, after the `<title>KnowBe4</title>` line (`backend/static/student.html:5`), insert the same favicon link as Task 1:

```html
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='32' fill='%23f59e0b'/%3E%3Ctext x='32' y='45' font-family='sans-serif' font-size='36' font-weight='800' text-anchor='middle' fill='%230f2149'%3E4%3C/text%3E%3C/svg%3E" />
```

- [ ] **Step 4: Manually verify in a browser**

With the same `uvicorn` server from Task 1 still running, open `http://127.0.0.1:8000/ui/student.html`. Confirm:
- The heading shows "Know" in navy, "Be" in orange/amber, "4" in an amber circle badge with white text, followed by " — Student login" in normal text.
- The browser tab shows the same amber circle "4" favicon as the login page.

- [ ] **Step 5: Commit**

```bash
git add backend/static/student.html
git commit -m "feat: apply KnowBe4 wordmark logo and favicon to student page"
```
