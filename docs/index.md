# Energizados

A machine learning framework for detecting non-technical losses (electricity theft) in energy distribution systems.

## Choose Your Path

!!! info "End User"
    Install via pip and use the CLI to train models and detect fraud.

    [Get Started →](getting-started/overview.md)

!!! info "Advanced User"
    Clone the repository, extend the framework, and contribute.

    [Explore Advanced →](advanced/architecture.md)

## Quick Install

```bash
pip install energizados
```

## What's Inside

Energizados provides a complete toolkit for electricity theft detection:

- **ETL Framework** — Configure multiple ETLs with dependencies using YAML
- **ML Models** — LightGBM, CatBoost, Neural Networks (Dense), LSTM, plus rule-based baselines
- **EDA Module** — Comprehensive exploratory data analysis with interactive reports
- **CLI** — Streamlined command-line interface for the entire pipeline

### Supported Models

| Model Type | Description | Best For |
|------------|-------------|----------|
| `lightgbm` | Gradient Boosting | Fast training, tabular data |
| `catboost` | CatBoost | Native categorical handling |
| `neural_network` | Feedforward Dense NN | Quick baseline with embeddings |
| `lstm` | LSTM | Sequential consumption patterns |
| `simple_trend` | Rule-based trend | Fast fraud rules, no ML |
| `simple_constant` | Rule-based constant | Detect constant meter readings |

The framework is designed for both quick prototyping and production deployment, with extensible architecture for custom preprocessing, feature engineering, and model implementations.
