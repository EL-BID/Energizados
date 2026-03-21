---
name: new-etl
description: Scaffold a new ETL block for config/etl.yaml. Guides through name, mode (concat/merge), inputs, outputs, and dependencies. Produces valid YAML ready to paste.
---

You are helping the user add a new ETL to `config/etl.yaml` in the Energizados framework.

## Step 1: Gather Requirements

Ask the user (in one message, all at once):
1. **ETL name** — snake_case identifier (e.g., `consumos_2024`)
2. **Mode** — `concat` (stack files vertically) or `merge` (join files horizontally)
3. **Input path(s)** — one or more file paths or `@other_etl` references
4. **Output path** — where to write the result parquet
5. **Depends on** — other ETL names this one needs to run first (leave empty if none)
6. If mode is `merge`: **merge_config** — `how` (left/right/inner/outer) and `on` (column name)

## Step 2: Validate

Before generating output, check:
- Name is snake_case, no spaces
- If mode is `merge` and only 1 input → error: merge needs ≥2 inputs
- If mode is `merge` and no `merge_config` → error: required
- Output path ends in `.parquet`
- `depends_on` references exist in the existing config (if the user shared it)

## Step 3: Generate YAML Block

Produce the complete YAML block ready to paste into `config/etl.yaml` under the `etl:` key:

### For concat mode:
```yaml
  {name}:
    enabled: true
    description: "{description}"
    input:
      - "{input1}"
      # - "{input2}"  # add more if needed
    output: "{output}"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: [{depends_on_list}]
```

### For merge mode:
```yaml
  {name}:
    enabled: true
    description: "{description}"
    input:
      - "{input1}"
      - "{input2}"
    output: "{output}"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "{how}"
        on: "{on_column}"
    depends_on: [{depends_on_list}]
```

## Step 4: Remind

After generating the block, remind the user:
- To add it under the `etl:` key in `config/etl.yaml`
- That `@etl_name` syntax can be used as an input reference to another ETL's output
- To run `energizados validate etl` to check the config before running
