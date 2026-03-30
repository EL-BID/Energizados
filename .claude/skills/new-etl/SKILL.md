---
name: new-etl
description: Scaffold a new ETL block for config/etl.yaml. Guides through name, mode (concat/merge/incremental), inputs, outputs, and dependencies. Produces valid YAML ready to paste.
---

You are helping the user add a new ETL to `config/etl.yaml` in the Energizados framework.

## Step 1: Gather Requirements

Ask the user (in one message, all at once):
1. **ETL name** — snake_case identifier (e.g., `consumos_2024`)
2. **Mode** — `concat` (stack files vertically), `merge` (join files horizontally), or `incremental` (record-level filtering by a key column)
3. **Input path(s)** — one or more file paths, glob patterns, or `@other_etl` references
4. **Output path** — where to write the result. For `incremental` mode this should be a directory (no extension).
5. **Depends on** — other ETL names this one needs to run first (leave empty if none)
6. If mode is `merge`: **merge_config** — `how` (left/right/inner/outer) and `on` (column name)
7. If mode is `incremental`: **incremental_key** — the datetime or numeric column used to detect new records (e.g. `fecha_actualizacion`)

## Step 2: Validate

Before generating output, check:
- Name is snake_case, no spaces
- If mode is `merge` and only 1 input → error: merge needs ≥2 inputs
- If mode is `merge` and no `merge_config` → error: required
- If mode is `incremental` and no `incremental_key` → error: required
- For `concat`/`merge`: output path ends in `.parquet`
- For `incremental`: output path is a directory (no `.parquet` extension)
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

### For incremental mode:
```yaml
  {name}:
    enabled: true
    description: "{description}"
    input: "{glob_pattern}"          # e.g. "data/raw/consumos_*.csv"
    output: "{output_dir}/"          # directory — partitions written inside
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "incremental"
      incremental_key: "{key_column}"  # datetime column used to filter new records
      partition_by:
        - year    # derived automatically from incremental_key
        - month   # derived automatically from incremental_key (zero-padded: "01".."12")
      overwrite: false
      state_file: ".cache/etl_states/{name}.json"
      # last_processed: "2024-01-01"  # optional: initial cutoff on first run
    depends_on: [{depends_on_list}]
```

**How incremental works:**
- First run: processes all records (or records after `last_processed` if set), stores `max(incremental_key)` in `state_file`
- Subsequent runs: only keeps records where `incremental_key > stored_max`
- `year` and `month` are derived automatically from `incremental_key` (datetime) when not already in the DataFrame

## Step 4: Remind

After generating the block, remind the user:
- To add it under the `etl:` key in `config/etl.yaml`
- That `@etl_name` syntax can be used as an input reference to another ETL's output
- For incremental mode: the state file path should be committed to `.gitignore` or kept in `.cache/`
- To run `energizados validate etl` to check the config before running
