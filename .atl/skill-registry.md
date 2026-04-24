# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Creating a PR, opening a pull request, preparing changes for review | branch-pr | ~/.claude/skills/branch-pr/SKILL.md |
| Writing Go tests, using teatest, adding test coverage, Bubbletea TUI testing | go-testing | ~/.claude/skills/go-testing/SKILL.md |
| Creating a GitHub issue, reporting a bug, requesting a feature | issue-creation | ~/.claude/skills/issue-creation/SKILL.md |
| "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen" | judgment-day | ~/.claude/skills/judgment-day/SKILL.md |
| Creating a new skill, adding agent instructions, documenting patterns for AI | skill-creator | ~/.claude/skills/skill-creator/SKILL.md |

## Project Skills

| Trigger | Skill | Path |
|---------|-------|------|
| "generate results", "experiment results", "create experiment report", "results report", "experiment analysis", "generate _results.md" | experiment-results | .claude/skills/experiment-results/SKILL.md |
| Adding a new ETL block to etl.yaml, scaffolding ETL config | new-etl | .claude/skills/new-etl/SKILL.md |
| "new experiments", "create experiments", "nuevos experimentos", "crear experimentos", "experiment design", "experiment roadmap", "set up experiments" | new-experiments | .claude/skills/new-experiments/SKILL.md |
| Running a training experiment, kick off pipeline run, see experiment results | run-experiment | .claude/skills/run-experiment/SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### branch-pr
- Every PR MUST link a `status:approved` issue — use `Closes #N`, `Fixes #N`, or `Resolves #N` in the body
- Branch name MUST match `^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$`
- PR body MUST include: linked issue, exactly one `type:*` label, summary (1-3 bullets), changes table, test plan, contributor checklist
- Run `shellcheck` on all modified shell scripts before opening the PR
- Commits MUST follow conventional commits: `type(scope): description`
- Never add `Co-Authored-By` trailers to commits
- Four automated checks must pass: issue reference, `status:approved` label, `type:*` label, shellcheck

### go-testing
- Use table-driven tests: `tests := []struct{ name, input, expected string; wantErr bool }{ ... }`
- Run subtests with `t.Run(tt.name, func(t *testing.T) { ... })` for each case
- For Bubbletea TUI: use `teatest` — create model with `teatest.NewTestModel(t, model, opts...)`
- Use `tm.WaitFor(...)` to assert on output; `tm.Send(...)` to send messages
- Use golden files (`testdata/*.golden`) for complex output assertions; update with `-update` flag
- Never use `time.Sleep` in tests — use `WaitFor` with a timeout instead
- Prefer `require` over `assert` when the test cannot continue after failure

### issue-creation
- Blank issues are disabled — MUST use a template (bug report or feature request)
- Every issue gets `status:needs-review` automatically on creation
- A maintainer MUST add `status:approved` before any PR can be opened
- Search for duplicates before creating a new issue
- Questions go to Discussions, not issues
- Bug report required fields: Pre-flight checks, Bug Description, Steps to Reproduce, Expected Behavior, Actual Behavior, OS
- Feature request required fields: Pre-flight checks, Feature Description, Problem it Solves, Proposed Solution, Acceptance Criteria

### judgment-day
- Launch TWO independent judge sub-agents in parallel (never sequential, never do the review yourself)
- Each judge receives the same target but works independently — no cross-contamination
- Resolve the skill registry BEFORE launching judges; inject matching compact rules into BOTH judge prompts AND the fix agent prompt
- Synthesize findings as: Confirmed (both found), Suspect A/B (one found), Contradiction (disagree)
- Apply fixes via a dedicated Fix Agent (not the orchestrator) after synthesis
- Re-judge after fixes — max 2 iterations, then escalate unresolved contradictions to the user
- If no registry exists, warn user and proceed with generic review only

### skill-creator
- Skill files go in `skills/{skill-name}/SKILL.md` with frontmatter: `name`, `description` (include "Trigger:" text), `license`, `metadata.author`, `metadata.version`
- Optional: `assets/` for templates/schemas, `references/` for doc links
- Compact rules are the most important output — 5-15 lines, actionable only, no motivation or examples
- Description MUST include a "Trigger:" line so the registry can match it
- Do NOT create a skill for trivial, one-off, or already-documented patterns

### experiment-results
- Read ALL `evaluation_report.json` files from `output/{version}/exp/` subdirectories (fallback: `output/train-YYYYMMDD_HHMM/`)
- Extract: `metrics.auc`, `metrics.auc_val`, `metrics.precision`, `metrics.recall`, `metrics.f1`, `metrics.threshold`, `metrics.auc_diff`, `metrics.confusion_matrix`, `metrics.cumulative_gains`, `model_info.model_class`
- Group experiments by phase using naming convention `phaseX_expN_*`
- Generate TWO files: `_results.md` (full technical report) and `_slides_negocio.md` (business slide deck, 10-12 slides)
- Business section MUST include non-technical metric explanations, operational impact simulator using cumulative_gains deciles, and actionable recommendations
- `_slides_negocio.md`: generate AFTER `_results.md`; neutral professional tone (no colloquialisms); language matches project language
- AUC → "out of 100 pairs, model ranks fraud case correctly X times"; Precision → "X of 100 flagged clients actually committed fraud"

### new-etl
- Ask for all info in ONE message: name, mode, input(s), output, depends_on, plus mode-specific fields
- Validate before generating: `merge` needs ≥2 inputs + `merge_config`; `incremental` needs `incremental_key`; `concat`/`merge` output must end in `.parquet`; `incremental` output must be a directory (no extension)
- Use `custom_class: "energizados.etl.pipeline.SourceETL"` for all SourceETL blocks
- For incremental: output is `output_dir/partition=YYYY-MM/data.parquet`; state file goes in `.cache/etl_states/{name}.json`
- `@etl_name` syntax references another ETL's output as input
- Remind user to run `energizados validate etl` after pasting the block

### new-experiments
- Directory: `.proyects/{project}/config/{version}/` — never regenerate existing `etl.yaml`, `eda.yaml`, `infer.yaml`
- File naming: `fase{N}_exp{M}_{kebab-name}.yaml`; run names: `fase{N}-exp{M}-{kebab-name}`
- YAML header: 4-line comment block with phase, hypothesis, run command, dependency
- `geo_features` is NOT a global transformer — use `GeoFeaturesETL` in `etl.yaml` instead; never reference it under `global_transformers:`
- Class imbalance per model: LightGBM → `class_weight: "balanced"`; CatBoost → `auto_class_weights: "Balanced"` inside `hyperparams`; XGBoost → `class_weight: <float>` (scale_pos_weight)
- Winner selection: highest AUC test (not val); tiebreaker < 0.001 → prefer simpler model; carry winner forward unchanged to next phase
- Phase progression: Baselines → Sampling → Feature Engineering → Encoding → Selection → Tuning → Calibration → Ensemble
- `output_base_dir`: `"output/{version}/exp/"` shared across all YAMLs in a version
- Generate `_experiments.md` FIRST with roadmap, Mermaid diagram, "Decisiones Acumuladas" table, then generate all YAMLs

### run-experiment
- Always validate config FIRST: `energizados validate etl,train` — stop if validation fails
- Run sequence: validate → ETL (optional) → training
- Use `energizados run train -n {experiment_name}` when a custom name is provided
- After training, find the latest run: `ls -t output/ | head -1`, then read `output/{run_dir}/reports/evaluation/evaluation_report.json`
- Surface a clean metrics table: AUC val/test, Precision, Recall, F1, Threshold, Model type
- Suggest opening the HTML report and running `ml-config-reviewer` if metrics are below expectations

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| CLAUDE.md / AGENTS.md | /home/vvv/Develop/bid/energizados/CLAUDE.md | Project conventions, architecture, ETL config reference, preprocessing transformers, model training pipeline |
| CLAUDE.local.md | /home/vvv/Develop/bid/energizados/CLAUDE.local.md | Local-only: RTK token-killer commands (always prefix shell commands with `rtk`) |
