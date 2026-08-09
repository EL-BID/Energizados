---
name: run-experiment
description: Run a full Energizados training experiment (validate → ETL → train) and surface the key metrics from the JSON report. Use when you want to kick off a pipeline run and see results.
---

You are running a full Energizados ML experiment.

## Step 1: Confirm Scope

Ask the user (skip if already clear from context):
- Run ETL? (default: yes, unless already processed)
- Run training? (default: yes)
- Custom experiment name? (default: auto-generated timestamp)

## Step 2: Validate Config

Run config validation first — fail fast before a long training job:

```bash
energizados validate etl,train
```

If validation fails, stop and show the error. Do NOT proceed to step 3.

## Step 3: Run ETL (if requested)

```bash
energizados run etl
```

Show a summary of which ETLs ran and their output paths.

## Step 4: Run Training

```bash
energizados run train
```

If a custom name was provided:
```bash
energizados run train -n {experiment_name}
```

### Verbosity & Debugging

`energizados run` accepts repeated `-v` flags to raise the log level — use these when a step fails, behaves unexpectedly, or you need framework internals:

```bash
energizados run etl -v        # INFO  — framework progress messages
energizados run train -vv     # DEBUG — detailed step/adapter internals
energizados run train -vvv    # DEBUG (same level as -vv; extra flags are harmless)
```

Behavior:
- **Without `-v`**: only a one-line error is printed on failure.
- **With `-v` / `-vv`**: the full exception traceback is printed on failure (`-vv` also shows local variables).
- **In verbose mode** the run also auto-writes a `<run_dir>/run.log` file with the complete log trace.

## Step 5: Find and Surface Results

After training completes, find the most recent run directory:

```bash
ls -t output/ | head -1
```

Then read the JSON report:
```bash
cat output/{run_dir}/reports/evaluation/evaluation_report.json
```

Display a clean metrics summary:

```
## Experiment Results: {run_dir}

| Metric     | Val   | Test  |
|------------|-------|-------|
| AUC        | ...   | ...   |
| Precision  | ...   | ...   |
| Recall     | ...   | ...   |
| F1         | ...   | ...   |

**Threshold used**: {threshold}
**Model**: {model_type}
**Report**: output/{run_dir}/reports/evaluation/evaluation_report.html
```

## Step 6: Next Steps

Suggest:
- Open the HTML report for interactive charts
- Run `/ml-config-reviewer` if metrics are below expectations
- Tag the run with `/commit` if results look good
