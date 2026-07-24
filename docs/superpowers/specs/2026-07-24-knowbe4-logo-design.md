# KnowBe4 Wordmark Logo — Design

## Purpose

Replace the placeholder "KB4" square + plain-text "KnowBe4" title with an
official wordmark logo, used consistently across the app and as the browser
tab favicon.

## Wordmark

Text "KnowBe4" split into three styled parts:

- `Know` — base text color
- `Be` — amber accent
- `4` — set in a small rounded badge (acts as a standalone mark)

Typography: `font-family: 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
font-weight: 700; letter-spacing: -0.01em;`. No new font loads.

Two color variants, selected by a `.wordmark--light` modifier class:

| Part | Default (dark backgrounds, e.g. navy login panel) | `.wordmark--light` (white backgrounds) |
|---|---|---|
| `Know` | `#ffffff` | `#0f2149` |
| `Be` | `#f59e0b` | `#ea8a3b` |
| `4` badge background | `#f59e0b` | `#ea8a3b` |
| `4` badge text | `#0f2149` | `#ffffff` |

Badge (`4`): inline-flex circle, `width`/`height: 0.78em`, `border-radius:
50%`, `font-size: 0.62em`, `font-weight: 800`, `margin-left: 0.06em`,
vertically centered with the text.

Markup shape:

```html
<span class="wordmark"><!-- add "wordmark--light" on white backgrounds -->
  <span class="wm-know">Know</span><span class="wm-be">Be</span><span class="wm-4">4</span>
</span>
```

## Application

- **`backend/static/index.html`** — login panel (navy background,
  `.login-brand`): remove the existing `.login-logo` "KB4" square `<div>`;
  replace the plain `<h1>KnowBe4</h1>` with the wordmark markup (default/dark
  variant) inside the `<h1>`.
- **`backend/static/student.html`** — header (white background): replace the
  plain-text "KnowBe4" inside `<h1>KnowBe4 — Student login</h1>` with the
  wordmark markup (`.wordmark--light` variant), keeping
  `" — Student login"` as trailing plain text in the same `<h1>`.
- **Favicon** — add `<link rel="icon" type="image/svg+xml" href="data:...">`
  to both files' `<head>`, an inline SVG reusing the exact badge shape and
  colors (amber circle, navy "4"). No separate image file. This is what
  renders in the browser tab.

## Out of scope

- No standalone icon/lockup system — wordmark only, per prior decision.
- No changes to `<title>` text (already reads "KnowBe4" in both files).
- No app-wide design system audit — scoped to these two files.
