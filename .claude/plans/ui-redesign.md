# UI Redesign — Web Console

Goal: lift the web console UI into a clean, modern data-app, grounded in the
domain model (`CONTEXT.md`).
The UI hangs off the model, not the other way around.

## Design system (Foundation)

- **Stack (kept):** Bootstrap 5.3, HTMX 1.9.10, Plotly.
- **Token layer:** CSS custom properties for color, spacing, radius, shadow,
  typography, layered on top of Bootstrap (override `--bs-*` vars). Single
  source of truth for theming.
- **Theme:** neutral data-app; **light + dark** with a persisted toggle
  (localStorage); token-driven so dark mode costs nothing extra.
- **Primary:** índigo `#6366f1`.
- **Type:** Inter (UI) + monospace (code, config, IDs).
- **Icons:** Bootstrap Icons.
- **Density:** compact tables.
- **TODO (tracked, not in Foundation):** self-host Bootstrap/HTMX/Icons/Inter
  to drop CDNs; add a `/ui` style-guide page.

## Information architecture (from the domain model)

- **App shell:** sidebar of **Projects**.
- **Per Project:** Jobs and Runs grouped by **Run type** (etl / eda /
  inference / training).
- **Compare:** type-scoped, defaults to TrainingRun.
- **Retrain:** surface the `derived_from` lineage (Run → Run).
- **Global:** degraded to legacy/hidden (ADR-0002).
- **States:** loading, empty, and out-of-band (OOB) on every async surface.

## Phasing

1. **Foundation** — design tokens, light/dark toggle, app shell (sidebar +
   base refactor). Enabler for everything else. (No CDN removal, no per-page
   restyle yet.)
2. **Hero** — `project_detail`: the showcase page (project header, Jobs/Runs
   by type, latest training summary, lineage snippet).
3. **Rollout** — apply the system across remaining templates; add
   loading/empty/OOB states; `/ui` style guide.

## Decisions log

Design system + pulido · Bootstrap + token layer · data-app moderna neutra ·
light + dark con toggle · índigo #6366f1 · sidebar app shell · tablas
compactas · Inter + mono · Bootstrap Icons · capa moderada de macros ·
Foundation → hero → rollout · hero = project_detail · loading + empty + OOB ·
self-host TODO · /ui style guide · 4 extras.

## Out of scope (separate effort)

Realizing the web domain divergences in code — ETL/EDA emitting typed Runs,
persisting `derived_from` (ADRs 0001/0003). The UI assumes them; the backend
work is tracked separately.
