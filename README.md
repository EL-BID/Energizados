# Energizados

> Machine learning framework for detecting electricity theft in energy distribution networks.

[![PyPI version](https://badge.fury.io/py/energizados.svg)](https://pypi.org/project/energizados/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BID-blue.svg)](LICENSE.md)
[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg)](docs/)

**Energizados** is a machine learning framework for detecting non-technical losses (electricity theft) in energy distribution networks. It provides a complete pipeline from ETL processing through model training, evaluation, and inference.

## ✨ Features

- **ETL Framework**: Multi-source data processing with dependencies via YAML configuration
- **ML Models**: LightGBM, CatBoost, Neural Networks, LSTM, and ensemble methods
- **EDA Module**: Interactive HTML reports for exploratory data analysis
- **CLI Tools**: Complete command-line interface for pipeline orchestration

## 🚀 Quick Start

```bash
pip install energizados
energizados init my_project
cd my_project
energizados run --config config/etls.yaml --config config/training.yaml
```

## 📖 Documentation

- [Getting Started](docs/getting-started/introduction.md) - Installation and project setup
- [User Guide](docs/user-guide/) - Complete framework documentation
- [Tutorials](docs/tutorials/) - Hands-on examples and walkthroughs
- [Advanced](docs/advanced/) - Extending and customizing the framework

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Licensed under the BID License - see [LICENSE.md](LICENSE.md) for details.
