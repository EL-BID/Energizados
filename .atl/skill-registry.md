# Skill Registry

## User Skills (Global)

| Skill | Trigger | Description |
|-------|---------|-------------|
| `sdd-init` | "sdd init", "iniciar sdd" | Initialize SDD context in a project |
| `sdd-explore` | `/sdd-explore <topic>` | Explore and investigate ideas before committing to a change |
| `sdd-propose` | `/sdd-propose <change>` | Create a change proposal |
| `sdd-spec` | `/sdd-spec` | Write specifications with requirements and scenarios |
| `sdd-design` | `/sdd-design` | Create technical design document |
| `sdd-tasks` | `/sdd-tasks` | Break down a change into implementation tasks |
| `sdd-apply` | `/sdd-apply` | Implement tasks from the change |
| `sdd-verify` | `/sdd-verify` | Validate implementation against specs |
| `sdd-archive` | `/sdd-archive` | Archive a completed change |
| `go-testing` | Go tests, teatest | Go testing patterns for Bubbletea TUI testing |
| `skill-creator` | Create new skill | Create new AI agent skills |

## Skill Paths (Global)

| Skill | Path |
|-------|------|
| `sdd-init` | `~/.claude/skills/sdd-init/SKILL.md` |
| `sdd-explore` | `~/.claude/skills/sdd-explore/SKILL.md` |
| `sdd-propose` | `~/.claude/skills/sdd-propose/SKILL.md` |
| `sdd-spec` | `~/.claude/skills/sdd-spec/SKILL.md` |
| `sdd-design` | `~/.claude/skills/sdd-design/SKILL.md` |
| `sdd-tasks` | `~/.claude/skills/sdd-tasks/SKILL.md` |
| `sdd-apply` | `~/.claude/skills/sdd-apply/SKILL.md` |
| `sdd-verify` | `~/.claude/skills/sdd-verify/SKILL.md` |
| `sdd-archive` | `~/.claude/skills/sdd-archive/SKILL.md` |
| `go-testing` | `~/.claude/skills/go-testing/SKILL.md` |
| `skill-creator` | `~/.claude/skills/skill-creator/SKILL.md` |

## Project Conventions

### Stack

- **Language**: Python 3.10+
- **Package manager**: pip / setuptools
- **Package config**: `pyproject.toml`

### Code Quality

- **Formatter**: black (line-length 100)
- **Linter**: ruff, flake8, bandit
- **Type Checker**: mypy (python 3.10)
- **Import Sorter**: isort
- **Pre-commit**: Configured with isort, black, bandit, flake8, prettier

### Testing

- **Framework**: pytest + pytest-cov
- **Config**: `pyproject.toml` → `[tool.pytest.ini_options]`
- **Coverage**: htmlcov output, `tests/` directory
- **Markers**: slow, integration, unit

### ML Stack

- LightGBM 4.6, CatBoost 1.2.8, scikit-learn 1.4.2
- imbalanced-learn 0.12 (sampling strategies)
- tsfel 0.1.9 (time series feature extraction)
- boruta 0.4.3 (feature selection)
- pandas 2.x + pyarrow (data)

### Architecture Patterns

- ETL framework with orchestrator and dependency management (YAML config)
- Feature engineering pipeline: preprocessing + feature selection
- Builder pattern for pipeline construction (`core/builders/`)
- JSON Schema validation for YAML configs (`core/schemas/`)
- Model training with hyperparameter search (RandomizedSearchCV)
- Ensemble models: stacking and soft voting
- EDA module generating interactive HTML reports
- CLI via click + rich
- Output per-run in `output/train-YYYYMMDD_HHMM/`

### Language Conventions

- Documentation: English
- Code: Spanish variable names for domain features (actividad, tipo_tarifa, zona), English class/method names
- No `print()` — use Python `logging` module
- Conventional commits format

## Project Convention Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Primary AI assistant instructions and full architecture reference |
| `pyproject.toml` | Package config, linters, testing, coverage |
| `.pre-commit-config.yaml` | Pre-commit hooks (isort, black, bandit, flake8) |

## Key Source Paths

| Path | Description |
|------|-------------|
| `src/energizados/` | Framework source |
| `src/energizados/core/` | Pipeline, builders, schemas |
| `src/energizados/preprocessing/` | Feature transformers |
| `src/energizados/modeling/` | Supervised + ensemble models |
| `src/energizados/feature_engineering/` | FE pipeline |
| `src/energizados/feature_selection/` | Selection methods |
| `src/energizados/evaluation/` | Metrics, plots, reports |
| `src/energizados/inference/` | Inference pipeline |
| `src/energizados/etl/` | ETL framework |
| `src/energizados/eda/` | EDA module |
| `src/energizados/cli/` | CLI commands |
| `tests/` | Test suite |
| `PRD-01.md` | Product Requirements Document |
| `GAP-ANALYSIS-01.md` | Gap analysis vs production systems |
| `ROADMAP-01.md` | 12-18 month roadmap |
