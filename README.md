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
- [Domain Glossary (CONTEXT.md)](CONTEXT.md) - Ubiquitous-language glossary: the single source of truth for framework terms (Pipeline, Step, Context, Model, Run, Job, Project, ...)

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



## Acknowledgments / Reconocimientos

**Copyright © [2025]. Inter-American Development Bank ("IDB"). Authorized Use.**  
The procedures and results obtained based on the execution of this software are those programmed by the developers and do not necessarily reflect the views of the IDB, its Board of Executive Directors or the countries it represents.

**Copyright © [2025]. Banco Interamericano de Desarrollo ("BID"). Uso Autorizado.**  
Los procedimientos y resultados obtenidos con la ejecución de este software son los programados por los desarrolladores y no reflejan necesariamente las opiniones del BID, su Directorio Ejecutivo ni los países que representa.

### Support and Usage Documentation / Documentación de Soporte y Uso

**Copyright © [2025]. Inter-American Development Bank ("IDB").** The Support and Usage Documentation is licensed under the Creative Commons License CC-BY 4.0 license. The opinions expressed in the Support and Usage Documentation are those of its authors and do not necessarily reflect the opinions of the IDB, its Board of Executive Directors, or the countries it represents.

**Copyright © [2025]. Banco Interamericano de Desarrollo (BID).** La Documentación de Soporte y Uso está licenciada bajo la licencia Creative Commons CC-BY 4.0. Las opiniones expresadas en la Documentación de Soporte y Uso son las de sus autores y no reflejan necesariamente las opiniones del BID, su Directorio Ejecutivo ni los países que representa.

### AI-Powered Services Disclaimer / Exención de responsabilidad por Servicios Impulsados por IA

The Software may include features which use, are powered by, or are an artificial intelligence system (“AI-Powered Services”), and as a result, the services provided via the Software may not be completely error-free or up to date. Additionally, the User acknowledges that due to the incorporation of AI-Powered Services in the Software, the Software may not dynamically (in “real time”) retrieve information and that, consequently, the output provided to the User may not account for events, updates, or other facts that have occurred or become available after the Software was trained. Accordingly, the User acknowledges that the use of the Software, and that any actions taken or reliance on such products, are at the User’s own risk, and the User acknowledges that the User must independently verify any information provided by the Software.

El Software puede incluir funciones que utilizan, están impulsadas por o son un sistema de inteligencia artificial (“Servicios Impulsados por IA”) y, como resultado, los servicios proporcionados a través del Software pueden no estar completamente libres de errores ni actualizados. Además, el Usuario reconoce que, debido a la incorporación de Servicios Impulsados por IA en el Software, este puede no recuperar información dinámicamente (en “tiempo real”) y que, en consecuencia, la información proporcionada al Usuario puede no reflejar eventos, actualizaciones u otros hechos que hayan ocurrido o estén disponibles después del entrenamiento del Software. En consecuencia, el Usuario reconoce que el uso del Software, y que cualquier acción realizada o la confianza depositada en dichos productos, se realiza bajo su propio riesgo, y reconoce que debe verificar de forma independiente cualquier información proporcionada por el Software.
