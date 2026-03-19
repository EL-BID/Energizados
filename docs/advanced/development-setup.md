# Development Setup

This guide covers setting up a development environment for contributing to the Energizados framework.

## Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment tool (venv, conda, or similar)

## Clone the Repository

```bash
git clone https://github.com/EL-BID/energizados.git
cd energizados
```

## Create a Virtual Environment

```bash
# Using venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or using conda
conda create -n energizados python=3.10
conda activate energizados
```

## Install Development Dependencies

```bash
# Install the package in editable mode with all dev dependencies
pip install -e ".[dev]"
```

This installs the framework itself plus all development tools: linters, test runners, and the MkDocs documentation system.

## Pre-commit Hooks

### Installation

```bash
pre-commit install
```

### Configured Hooks

| Hook | Purpose | Configuration |
|------|-----------|---------------|
| **isort** | Sorts imports automatically | `--profile black`, line 100 |
| **black** | Formats Python code | line-length: 100 |
| **bandit** | Detects security vulnerabilities | config: `.code_quality/bandit.yaml` |
| **flake8** | Code linting (PEP8) | config: `.code_quality/.flake8` |
| **prettier** | Formats YAML files | No additional config |

### Running Manually

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run a specific hook
pre-commit run black --all-files
```

### Line Length

All formatters use **100 characters** line length:
- Black: configured in `pyproject.toml` → `[tool.black]`
- Ruff: configured in `pyproject.toml` → `[tool.ruff]`
- isort: configured with `--profile black` in `.pre-commit-config.yaml`

## Verify Installation

Run the test suite to ensure everything is set up correctly:

```bash
pytest
```

## Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** and test:
   ```bash
   # Run tests
   pytest

   # Run linting
   pre-commit run --all-files
   ```

3. **Commit changes** following [Conventional Commits](contributing.md#commit-messages):
   ```bash
   git add .
   git commit -m "feat(model): add custom model support"
   ```

4. **Push and create pull request**:
   ```bash
   git push origin feature/my-feature
   ```

## Running the Project

The project is primarily run through Jupyter notebooks:

```bash
# Start Jupyter Lab
jupyter lab
```

Main notebooks:
- `notebooks/ejecucion_paso_paso.ipynb` - Local execution
- `notebooks/colab_ejecucion_paso_paso.ipynb` - Google Colab execution

### Framework CLI

```bash
# Initialize a new project
energizados init mi_proyecto

# Run pipeline
energizados run etl,train

# Validate configuration
energizados validate --config config/etl.yaml --config config/train.yaml
```

## Working with Documentation

The documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/), included in the `dev` dependencies.

```bash
# Serve docs locally with live reload
mkdocs serve
# → http://127.0.0.1:8000

# Build static site
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

Documentation source files live in `docs/`. The site configuration is in `mkdocs.yml` at the project root.

!!! tip "Adding a new language"
    The `mkdocs.yml` has i18n configuration commented out and ready to enable.
    When adding Spanish or Portuguese translations, uncomment the `i18n` plugin block
    and install it with `pip install mkdocs-material[i18n]`.

## See Also

- [Contributing Guide](contributing.md) - Code quality standards and testing
- [Extending Framework](extending/) - Customizing the framework
- [User Guide](../user-guide/) - End-user documentation

---

← [Advanced Topics](../advanced/) | [Contributing](contributing.md) →
