# Development Setup

This guide covers setting up a development environment for contributing to the Energizados framework.

## Prerequisites

- Python 3.10 or higher
- Git
- [Poetry](https://python-poetry.org/) 2.x (recommended), [uv](https://docs.astral.sh/uv/), or any virtual environment tool (venv, conda)

> 💡 **No Python installed yet?** uv can fetch it for you — and uv's standalone
> installer needs no Python either:
>
> ```bash
> # Install uv (one-time, no Python required)
> curl -LsSf https://astral.sh/uv/install.sh | sh   # Windows: powershell -c "irm https://astral.sh/uv | iex"
>
> # Download and manage a Python interpreter
> uv python install 3.10
> ```
>
> Any other method (python.org installer, apt, brew, pyenv, conda) works too — see
> the [Installation guide](../getting-started/installation.md).

## Clone the Repository

```bash
git clone https://github.com/EL-BID/Energizados.git
cd energizados
```

## Set Up the Environment

### Option A: Poetry (recommended)

The repository tracks dependencies with a `poetry.lock` file, so Poetry gives you a
reproducible environment that matches the rest of the team. Poetry creates and
manages the virtual environment for you — no manual activation step required.

```bash
# Install Poetry (one-time setup)
pip install poetry

# Create the environment and install dependencies from the lock file,
# including dev tools (linters, pytest, MkDocs)
poetry install --extras dev

# Run commands inside the environment...
poetry run pytest

# ...or activate it once and work normally
poetry shell
```

Add more extras if you need them (each one extends the base install):

```bash
poetry install --extras "dev web"   # + FastAPI/uvicorn (web console)
poetry install --extras "dev all"   # + catboost, tensorflow, xgboost (heavy)
```

> 💡 **Tip:** To keep the virtual environment inside the project folder (`.venv/`),
> run `poetry config virtualenvs.in-project true` once before installing.

**Keeping the lock in sync:** after editing `pyproject.toml`, run `poetry lock` and
commit the updated `poetry.lock` together with your change.

### Option B: uv

[uv](https://docs.astral.sh/uv/) is a drop-in, much faster replacement for
`venv` + `pip`. Like Option C, it installs from the loose constraints in
`pyproject.toml` — not the pinned `poetry.lock` — but setup takes seconds
instead of minutes.

```bash
# Install uv (one-time setup)
pip install uv   # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Create the environment and install dev dependencies
uv venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Add extras the same way as pip
uv pip install -e ".[dev,web]"
```

> ⚠️ Prefer `uv pip` commands over `uv sync` here: `uv sync` would create a
> `uv.lock` file the repository does not track. The team's lock file is
> `poetry.lock` (Option A).

### Option C: venv + pip

Works with the Python standard library alone — no extra tools. Installs from the
loose constraints in `pyproject.toml` instead of the pinned `poetry.lock` — your
environment may differ from the team's.

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

Either way you get the framework itself plus the development tools: linters, test
runners, and the MkDocs documentation system.

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
poetry run pytest   # Option A (or plain `pytest` inside `poetry shell`)
pytest              # Options B/C (inside the activated environment)
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
energizados validate etl,train
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
- [Extending Framework](extending/custom-etl.md) - Customizing the framework
- [User Guide](../user-guide/project-structure.md) - End-user documentation

---

← [Advanced Topics](architecture.md) | [Contributing](contributing.md) →
