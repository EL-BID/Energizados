# Energizados

A machine learning framework for detecting electricity theft (non-technical losses) in energy distribution systems.

## Quick Start

```bash
pip install energizados
energizados init my_project
cd my_project
energizados run etl,train
```

## Choose Your Path

!!! info "End User"
    Install via pip and use the CLI to train models and detect fraud.

    [Get Started →](getting-started/overview.md)

!!! info "Advanced User"
    Clone the repository, extend the framework, and contribute.

    [Explore Advanced →](advanced/architecture.md)

## What's Inside

- **ETL Framework** — Multiple ETLs with dependencies, configured via YAML
- **ML Models** — LightGBM, CatBoost, XGBoost, Neural Networks (Dense + LSTM), plus rule-based baselines
- **Feature Engineering** — Preprocessing, global transformers, and selection (Boruta, correlation, etc.)
- **EDA Module** — Interactive exploratory reports
- **Evaluation** — Metrics, plots, threshold calibration, and SHAP explainability
- **Web Console** — Async job runner for multi-project workflows

For the full model list and pipeline stages, see the [Overview](getting-started/overview.md).

## Stay Current

- [Releases](releases/v0.3.3.md) — per-version release notes
- [Changelog](https://github.com/EL-BID/Energizados/blob/master/CHANGELOG.md) — full change history

---

New projects ship with a sample dataset, so you can run the pipeline end-to-end immediately. Start with the [Installation guide](getting-started/installation.md).
