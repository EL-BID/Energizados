# Energizados

> Machine learning framework for detecting electricity theft in energy distribution networks.

[![PyPI version](https://badge.fury.io/py/energizados.svg)](https://pypi.org/project/energizados/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BID-blue.svg)](LICENSE.md)
[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg)](docs/)

**Energizados** is a machine learning framework for detecting non-technical losses (electricity theft) in energy
distribution networks. It provides a complete pipeline from ETL processing through model training, evaluation, and
inference.

## ✨ Features

| Capability            | Details                                                                                 |
|-----------------------|-----------------------------------------------------------------------------------------|
| **ETL Framework**     | Multi-source data processing with concat/merge/incremental modes and dependency management via YAML |
| **ML Models**         | LightGBM, CatBoost, XGBoost, Neural Networks, LSTM, IsolationForest + ensemble (stacking/soft voting) |
| **Preprocessing**     | Target encoding, one-hot, ordinal, cardinality reduction, tsfel time-series features    |
| **Feature Selection** | Boruta, correlation-based, constant-value selectors                                     |
| **EDA Module**        | Interactive HTML reports with IV/KS/Cramér's V analysis and segment drift detection     |
| **CLI Tools**         | `energizados init`, `run`, `validate`, `eda` commands for pipeline orchestration        |
| **Explainability**    | SHAP values for model interpretability and regulatory compliance                        |
| **Inference**         | Production-ready inference pipeline with batch processing support                       |

## 🚀 Quick Start

```bash
pip install energizados
energizados init my_project
cd my_project
energizados run etl,train
```

## 📖 Documentation

- [Getting Started](docs/getting-started/overview.md) - Installation and project setup
- [User Guide](docs/user-guide/) - Complete framework documentation
- [Tutorials](docs/tutorials/) - Hands-on examples and walkthroughs
- [Advanced](docs/advanced/) - Extending and customizing the framework

## 🤝 Contributing

Contributions are welcome! See [Contributing Guidelines](docs/advanced/contributing.md) for details.

## 📄 License

Licensed under the BID License - see [LICENSE.md](LICENSE.md) for details.

## Limitation of Liability

The IDB shall not be liable under any circumstances for any damage or compensation, whether moral or proprietary; direct
or indirect; incidental or special; or consequential, whether foreseen or unforeseen, that may arise:
i. Under any theory of liability, whether by contract, infringement of intellectual property rights, negligence or under
any other theory; and/or
ii. From the use of the Digital Tool, including, but not limited to, potential defects in the Digital Tool, or the loss
or inaccuracy of data of any kind. The foregoing includes expenses or damages associated with communication failures
and/or computer failures related to the use of the Digital Tool.

