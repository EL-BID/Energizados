---
status: accepted
---

# Lineage is Run→Run (derived_from), separate from Job retry

Re-deriving an experiment ("retrain from a Run") and re-running a failed Job
("retry") were both tracked at the Job level or implicitly. The retrain flow
(`web/app.py:2212`) enqueues a new Job that re-runs the source Run's merged
config but stores **no Run→Run link** — experiment lineage was unqueryable. We
decided to model two distinct relationships at the level each belongs: **Retry**
is Job→Job (`retried_from`, an execution-retry concept); **Retrain** is Run→Run
(`derived_from`, an experiment-derivation concept). A Run knows the Run it was
retrained from.

## Considered options

- **Keep lineage implicit at the Job level (status quo).** Rejected: the most
  user-valuable question — "which Run was this retrained from?" — requires
  reconstructing a chain through Jobs and configs.
- **Run→Run `derived_from`, separate from Job `retried_from` (chosen).** Each
  relationship lives at its natural level.
- **Introduce an `Experiment` grouping concept (MLflow-style).** Rejected as
  over-modelling for now; deferred until a real need (e.g. sweep grouping)
  appears.

## Consequences

Requires persisting `derived_from` (on RunMetadata or in the job/run store) and
the retrain flow recording the source Run. The UI gains an experiment-lineage
view (Run A → Run B → Run C). Retry and Retrain remain two non-overlapping
relationships — do not collapse `retried_from` and `derived_from` into one field.
