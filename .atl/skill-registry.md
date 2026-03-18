# Skill Registry

## User Skills (Global)

| Skill | Trigger | Description |
|-------|---------|-------------|
| `sdd-init` | "sdd init", "iniciar sdd", "openspec init" | Initialize SDD context in a project |
| `sdd-explore` | Orchestrator launches explore phase; `/sdd-explore <topic>` | Explore and investigate ideas before committing to a change |
| `sdd-propose` | Orchestrator launches propose phase; `/sdd-propose` | Create a change proposal with intent, scope, and approach |
| `sdd-spec` | Orchestrator launches spec phase; `/sdd-spec` | Write specifications with requirements and scenarios |
| `sdd-design` | Orchestrator launches design phase; `/sdd-design` | Create technical design document with architecture decisions |
| `sdd-tasks` | Orchestrator launches tasks phase; `/sdd-tasks` | Break down a change into an implementation task checklist |
| `sdd-apply` | Orchestrator launches apply phase; `/sdd-apply` | Implement tasks from the change following specs and design |
| `sdd-verify` | Orchestrator launches verify phase; `/sdd-verify` | Validate that implementation matches specs, design, and tasks |
| `sdd-archive` | Orchestrator launches archive phase; `/sdd-archive` | Sync delta specs to main specs and archive a completed change |
| `go-testing` | Writing Go tests, using teatest, adding test coverage | Go testing patterns for Gentleman.Dots, including Bubbletea TUI testing |
| `skill-creator` | User asks to create a new skill or document patterns for AI | Creates new AI agent skills following the Agent Skills spec |

## Skill Paths (Global)

| Skill | Path |
|-------|------|
| `sdd-init` | `~/.config/opencode/skills/sdd-init/SKILL.md` |
| `sdd-explore` | `~/.config/opencode/skills/sdd-explore/SKILL.md` |
| `sdd-propose` | `~/.config/opencode/skills/sdd-propose/SKILL.md` |
| `sdd-spec` | `~/.config/opencode/skills/sdd-spec/SKILL.md` |
| `sdd-design` | `~/.config/opencode/skills/sdd-design/SKILL.md` |
| `sdd-tasks` | `~/.config/opencode/skills/sdd-tasks/SKILL.md` |
| `sdd-apply` | `~/.config/opencode/skills/sdd-apply/SKILL.md` |
| `sdd-verify` | `~/.config/opencode/skills/sdd-verify/SKILL.md` |
| `sdd-archive` | `~/.config/opencode/skills/sdd-archive/SKILL.md` |
| `go-testing` | `~/.config/opencode/skills/go-testing/SKILL.md` |
| `skill-creator` | `~/.config/opencode/skills/skill-creator/SKILL.md` |

## Project Conventions

### Stack

- **Language**: Python 3.10+
- **Package manager**: pip / setuptools (pyproject.toml + setuptools)
- **Version**: 0.1.2.dev0
- **Entry point**: `energizados` CLI (`energizados.cli.main:cli`)

### Code Quality

- **Formatter**: black (line-length 100)
- **Linter**: ruff (E, F, I, N, W rules), flake8
- **Security**: bandit (`.code_quality/bandit.yaml`)
- **Type Checker**: mypy (python 3.10, check_untyped_defs=true)
- **Import Sorter**: isort (--profile black)
- **Pre-commit**: isort → black → bandit → flake8 → prettier (yaml)

### Testing

- **Framework**: pytest + pytest-cov
- **Config**: `pyproject.toml` → `[tool.pytest.ini_options]`
- **Coverage**: htmlcov output, source=src, `tests/` directory
- **Markers**: slow, integration, unit
- **Run**: `pytest` (includes coverage by default)
- **IMPORTANT**: `--strict-markers` and `--strict-config` are on — always declare markers

### ML Stack

- **Models**: LightGBM 4.6, CatBoost 1.2.8 (optional), TensorFlow ≥2.17 (optional)
- **Sampling**: imbalanced-learn 0.12 (RandomUnderSampler, RandomOverSampler)
- **Feature selection**: boruta 0.4.3, sklearn-based (correlation, constant)
- **Time series FE**: tsfel 0.1.9
- **Data**: pandas 2.x + pyarrow 19.x (parquet format)
- **Ensemble**: stacking (meta-learner) or soft voting

### Architecture Patterns

- **ETL**: orchestrator + dependency graph (YAML config), `SourceETL` for concat/merge
- **Feature engineering**: preprocessing + feature selection pipeline under `training.yaml`
- **Builder pattern**: `core/builders/` (PipelineDirector replaces ConfigPipelineBuilder)
- **JSON Schema validation**: `core/schemas/` for YAML configs
- **Model training**: `TrainingStep` with single/ensemble/multi-model modes
- **Ensemble**: `EnsembleModel` — stacking or soft voting, `use_val_as_oof` toggle
- **EDA**: `DatasetExplorer` → 7-phase HTML report
- **CLI**: click + rich
- **Output**: per-run in `output/train-YYYYMMDD_HHMM/`
- **Security**: `secure_pickle.py` (SHA-256 verified), `import_utils.py` (allowlist)

### Language Conventions

- Documentation: English
- Domain feature names: Spanish (`actividad`, `tipo_tarifa`, `zona`)
- Class/method names: English
- **Logging**: `logging` module only — NO `print()`
- **Commits**: Conventional commits format, no AI attribution

## Project Convention Files

| File | Purpose |
|------|---------|
| `AGENTS.md` / `CLAUDE.md` | Primary AI assistant instructions and full architecture reference |
| `pyproject.toml` | Package config, linters, testing, coverage, mypy |
| `.pre-commit-config.yaml` | Pre-commit hooks (isort, black, bandit, flake8, prettier) |
| `PRD-01.md` | Product Requirements Document |

## Key Source Paths

| Path | Description |
|------|-------------|
| `src/energizados/` | Framework source root |
| `src/energizados/core/` | Pipeline, builders, schemas, exceptions |
| `src/energizados/core/builders/` | PipelineDirector and builder classes |
| `src/energizados/core/schemas/` | JSON Schema for YAML config validation |
| `src/energizados/core/steps/` | SplitStep, TrainingStep |
| `src/energizados/preprocessing/` | Feature transformers (ToDummy, TeEncoder, CardinalityReducer, TsfelVars, ExtraVars, MinMaxScalerRow, CastDtype) |
| `src/energizados/modeling/` | LGBMModel, CATModel, NNModel, LSTMNNModel, EnsembleModel, simple models |
| `src/energizados/feature_engineering/` | DefaultFeatureEngineering (preprocessing + selection) |
| `src/energizados/feature_selection/` | BorutaSelector, CorrelationSelector, ConstantSelector |
| `src/energizados/evaluation/` | DefaultEvaluator, metrics, PlotGenerator, ReportGenerator, run index |
| `src/energizados/inference/` | BaseInference, DefaultInference |
| `src/energizados/etl/` | BaseETL, SourceETL, ETLOrchestrator |
| `src/energizados/eda/` | DatasetExplorer + 7 analyzers + HTML report |
| `src/energizados/cli/` | CLI commands (main, init, run, validate) |
| `tests/` | Test suite |
| `templates/` | Project init templates (including training.yaml.tpl) |
