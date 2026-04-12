# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Writing Go tests, using teatest, adding test coverage | go-testing | /home/vvv/.claude/skills/go-testing/SKILL.md |
| User asks to create a new skill, add agent instructions, document patterns for AI | skill-creator | /home/vvv/.claude/skills/skill-creator/SKILL.md |
| Creating a pull request, opening a PR, preparing changes for review | branch-pr | /home/vvv/.claude/skills/branch-pr/SKILL.md |
| Creating a GitHub issue, reporting a bug, requesting a feature | issue-creation | /home/vvv/.claude/skills/issue-creation/SKILL.md |
| "judgment day", "dual review", "doble review", "juzgar", "adversarial review", "que lo juzguen" | judgment-day | /home/vvv/.claude/skills/judgment-day/SKILL.md |
| Adding a new ETL block to config/etl.yaml | new-etl | /home/vvv/Develop/bid/energizados/.claude/skills/new-etl/SKILL.md |
| Running a full Energizados pipeline experiment (validate → ETL → train) | run-experiment | /home/vvv/Develop/bid/energizados/.claude/skills/run-experiment/SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### skill-creator
- Structure: `skills/{skill-name}/SKILL.md` + optional `assets/` and `references/`
- Frontmatter requires: `name`, `description` (must include "Trigger:"), `license: Apache-2.0`, `metadata.author`, `metadata.version`
- `references/` must point to LOCAL files only — never web URLs
- Never add a Keywords section; agent searches frontmatter, not body
- Don't create for one-off tasks, trivial patterns, or where docs already exist
- After creating: add entry to the project's `AGENTS.md`
- Start with Critical Patterns; keep code examples minimal and focused

### judgment-day
- Launch EXACTLY TWO judge agents in PARALLEL (async) — never sequential, never solo
- Neither judge may know about the other — strict blind protocol, no cross-contamination
- Orchestrator synthesizes: Confirmed (both found), Suspect A/B (one only), Contradiction (disagree on same thing)
- WARNING (real) = normal user can trigger it → fix required; WARNING (theoretical) = contrived/unlikely scenario → report as INFO only, no fix, no re-judge
- Round 1: present verdict table, ASK user to confirm before fixing anything
- Only re-judge (Round 2+) if confirmed CRITICALs remain; real WARNINGs fixed inline without re-judge
- Resolve skill registry BEFORE launching judges; inject `## Project Standards` into BOTH judges AND Fix Agent
- After 2 fix iterations with remaining issues: ASK user whether to continue or escalate
- APPROVED = 0 confirmed CRITICALs + 0 confirmed real WARNINGs

### issue-creation
- MUST use a template (bug_report.yml or feature_request.yml) — blank issues are disabled
- Every issue gets `status:needs-review` automatically; maintainer must add `status:approved` before any PR
- Search for duplicates before creating any issue
- Questions go to Discussions, not issues
- Required fields for bugs: description, steps to reproduce, expected vs actual behavior, OS, agent, shell

### branch-pr
- Every PR MUST link an approved issue: `Closes #N`, `Fixes #N`, or `Resolves #N`
- Branch name regex: `^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$`
- Every PR MUST have exactly ONE `type:*` label (type:bug, type:feature, type:docs, type:refactor, type:chore, type:breaking-change)
- Conventional commits: `type(scope): description` — no `Co-Authored-By` trailers
- Run `shellcheck scripts/*.sh` on any modified shell scripts before pushing
- Linked issue MUST have `status:approved` label or automated checks will block merge

### go-testing
- Always use table-driven tests (`[]struct{ name, input, expected, wantErr }`) for multi-case scenarios
- TUI state changes: test `Model.Update()` directly with `tea.KeyMsg{}`
- Full TUI interaction flows: use `teatest.NewTestModel(t, m)` + `tm.Send()` + `tm.WaitFinished()`
- Visual output: golden files in `testdata/` with `-update` flag to regenerate
- File operations in tests: always use `t.TempDir()`, never a fixed path
- Always test both success and error code paths for any function returning `error`

### new-etl
- Ask ALL required questions in ONE message before generating any YAML
- Validate before generating: snake_case name; merge needs ≥2 inputs + `merge_config`; incremental needs `incremental_key`
- concat/merge → output must be a `.parquet` file; incremental → output must be a directory (no extension)
- Always use `custom_class: "energizados.etl.pipeline.SourceETL"` — no other class for standard ETLs
- `@etl_name` syntax references another ETL's output path automatically
- Remind user to add under the `etl:` key, validate with `energizados validate etl`, and gitignore state files

### run-experiment
- Always validate config FIRST: `energizados validate etl,train` — stop immediately if it fails
- Execution order is strict: validate → ETL → train; never skip validation
- After training, find latest run: `ls -t output/ | head -1`, then read `reports/evaluation/report.json`
- Display a clean metrics table with Train/Val/Test columns: AUC, Precision, Recall, F1
- Suggest HTML report for interactive charts, `/ml-config-reviewer` if metrics are below expectations

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | /home/vvv/Develop/bid/energizados/AGENTS.md | Main AI instructions — full architecture, ETL config, CLI, preprocessing, models, directory structure |
| pyproject.toml | /home/vvv/Develop/bid/energizados/pyproject.toml | Package config, linters (black/ruff/flake8/mypy), testing, coverage |
| .pre-commit-config.yaml | /home/vvv/Develop/bid/energizados/.pre-commit-config.yaml | Pre-commit hooks: isort → black → bandit → flake8 → prettier |

### Stack Summary (for quick injection)

- **Language**: Python 3.10+ | **Formatter**: black (line-length 100) | **Linter**: ruff + flake8 | **Type checker**: mypy
- **Logging**: `logging` module ONLY — never `print()`
- **Commits**: Conventional commits, no AI attribution, no `Co-Authored-By`
- **Models**: LightGBM, CatBoost, XGBoost (optional), TensorFlow/Keras (optional)
- **Data**: pandas 2.x + pyarrow, parquet format throughout
- **ETL**: SourceETL with concat/merge/incremental modes; always requires `custom_class`
- **Tests**: pytest + pytest-cov; `--strict-markers` on; always declare markers
- **Feature names**: Spanish (actividad, tipo_tarifa, zona); class/method names: English
