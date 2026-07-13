---
status: accepted
---

# Run is a generalized pipeline-output bundle, not a training-only concept

The web console's "Run" was effectively training-only: the framework core's
`RunManager` only tracks training executions (`RunMetadata` carries
`val_auc`/`val_f1`/`model_types`), and ETL/EDA Jobs write directly under
`output/<type>/` without producing a run directory (`web/runner.py:140`). We
decided to adopt the industry-standard meaning (MLflow / dbt / Airflow): **a Run
is the persisted output bundle of *any* successful Job**, regardless of pipeline
type — a typed concept (`TrainingRun` / `ETLRun` / `EDARun` / `InferenceRun`),
where only same-type Runs are meaningfully comparable. This unifies browsability
of every execution output under one term and aligns the vocabulary with its
ubiquitous MLOps meaning.

## Considered options

- **Run = training-only (status quo).** Recommended at modeling time, rejected:
  leaves ETL/EDA outputs second-class and under-uses a term that the ecosystem
  already treats as generic.
- **Run = any output (chosen).** One typed concept for all execution outputs.

## Consequences

This decision documents intent **not yet fully realized in code**. Making it real
requires: ETL/EDA Jobs to start emitting typed Runs (run dir + metadata) instead
of writing bare to `output/<type>/`; `RunManager` to generalize beyond training;
and Compare Runs to become type-scoped (compare only same-type Runs, training by
default). Run metadata becomes type-discriminated — training-specific fields
(AUC, F1) no longer apply to every Run.
