---
status: accepted
---

# Deprecate the Global scope; the canonical model is Project-scoped

The web console predates multi-project workspaces: a "Global" scope exists where
Jobs/Runs carry no owning Project (`project_path` is null), the runner executes
them with no `chdir` (`web/runner.py:155-180`), and a special "global latest run
attribution" path exists. The multi-project workspace made Global redundant. We
decided to **deprecate Global**: the canonical model is **Project-scoped — every
Job and Run belongs to exactly one Project**. No new Global executions are
created; existing ones surface read-only.

## Considered options

- **Keep Global as a first-class scope (sandbox).** Rejected: two scoping models
  coexisting doubles ownership/attribution concepts and UI surface for no gain.
- **Deprecate Global (chosen).** One canonical model.
- **Migrate existing globals into a synthetic "default" Project.** Rejected: data
  migration plus murky "default" semantics, when deprecating (stop creating,
  keep legacy read-only) is enough.

## Consequences

**Realized in code (2026-07-14)** — commit `ecf9cdf`. `POST /jobs` no longer
enqueues Global jobs (always 400); the `/global` editor is deprecated with a
disabled submit. Legacy Global data remains read-only.

Stop enqueuing `project_path=NULL` Jobs; retire Global routes from prominent UI
(the sidebar) and degrade them to legacy/hidden. The special global-cwd and
global-attribution logic in the runner can be removed once no Global Jobs remain.
Existing Global data is preserved, read-only — not migrated, not deleted.
