"""
JSON Schema definitions for configuration validation.

This module contains the schema definitions for each configuration type.
"""

# ETL Configuration Schema
ETL_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "integer"},
        # ADR: top-level scalar keys under ``etl:`` are NOT ETL entries. They must be
        # declared here so additionalProperties (which requires ``input``) skips them.
        "output_base_dir": {"type": "string"},
        "output_name": {"type": "string"},
    },
    "additionalProperties": {
        "type": "object",
        "required": ["input"],
        "properties": {
            "enabled": {"type": "boolean", "default": True},
            "description": {"type": "string"},
            "input": {
                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]
            },
            "output": {"type": "string"},
            "depends_on": {"type": "array", "items": {"type": "string"}, "default": []},
            "custom_class": {"type": "string"},
            "params": {"type": "object"},
        },
    },
}

# Split Configuration Schema
SPLIT_SCHEMA = {
    "type": "object",
    "properties": {
        "input_path": {"type": "string"},
        "target_column": {"type": "string"},
        "test_size": {"type": "number", "minimum": 0, "maximum": 1},
        "val_size": {"type": "number", "minimum": 0, "maximum": 1},
        "random_state": {"type": "integer"},
        "splits_dir": {"type": "string"},
        "method": {
            "type": "string",
            "enum": [
                "stratified",
                "random",
                "time_series",
                "group_based",
                "stratified_time",
                "none",
            ],
        },
        "group_column": {"type": "string"},
        "date_column": {"type": "string"},
        "train_period": {
            "oneOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]
        },
        "val_period": {"oneOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
        "test_period": {
            "oneOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]
        },
        "save_splits": {"type": "boolean"},
        "unlabeled_negatives": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "source_path": {"type": ["string", "null"]},
                "max_per_cutoff": {"type": "integer", "default": 1500},
                "random_state": {"type": "integer", "default": 42},
                "date_column": {"type": ["string", "null"]},
                "id_column": {"type": ["string", "null"]},
            },
        },
        "geo_stratify": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "column": {"type": ["string", "null"]},
                "strategy": {
                    "type": "string",
                    "enum": ["proportional", "equal", "capped"],
                },
                "max_per_stratum": {"type": ["integer", "null"]},
                "random_state": {"type": "integer", "default": 42},
            },
        },
    },
    "if": {"properties": {"method": {"const": "group_based"}}, "required": ["method"]},
    "then": {"required": ["group_column"]},
}

# Feature Engineering Configuration Schema
FEATURE_ENGINEERING_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string"},
                    "columns": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "params": {"type": "object"},
                },
            },
        },
    },
}

# Feature Selection Configuration Schema
FEATURE_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string"},
                    "columns": {"type": "string"},
                    "threshold": {"type": "number"},
                    "method": {"type": "string"},
                    "n_runs": {"type": "integer"},
                    "k": {"type": "integer"},
                    "random_state": {"type": "integer"},
                },
            },
        },
    },
}

# Model Configuration Schema
MODEL_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "lightgbm",
                "catboost",
                "xgboost",
                "neural_network",
                "lstm",
                "simple_trend",
                "simple_constant",
            ],
        },
        "name": {"type": "string"},
        "hyperparams": {"type": "object"},
        "class_weight": {
            "oneOf": [{"type": "string", "enum": ["balanced", "none"]}, {"type": "object"}]
        },
        "sampling": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "method": {
                    "type": "string",
                    "enum": ["oversample", "undersample", "smotetomek", "none"],
                },
                "strategy": {"type": "string"},
                "threshold": {"type": "number"},
            },
        },
        "hyperparam_search": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "method": {"type": "string", "enum": ["grid", "random", "bayesian"]},
                "n_iter": {"type": "integer"},
                "cv": {"type": ["integer", "string"], "enum": [3, 5, 10, "time_series"]},
                "n_splits": {"type": "integer"},
            },
        },
        "validation": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "method": {
                    "type": "string",
                    "enum": ["kfold", "stratified_kfold", "time_series_split"],
                },
                "n_splits": {"type": "integer"},
            },
        },
        "calibration": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "method": {
                    "type": "string",
                    "enum": ["isotonic", "sigmoid"],
                    "default": "sigmoid",
                },
                "cv": {"type": "integer", "default": 3},
            },
        },
    },
}

# Ensemble Configuration Schema
ENSEMBLE_SCHEMA = {
    "type": "object",
    "required": ["method"],
    "properties": {
        "method": {"type": "string", "enum": ["soft_voting", "stacking"]},
        "weights": {"type": "array", "items": {"type": "number"}},
        "meta_learner": {
            "oneOf": [
                {
                    "type": "string",
                    "enum": ["logistic_regression", "random_forest", "gradient_boosting"],
                },
                {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["logistic_regression", "random_forest", "gradient_boosting"],
                        },
                        "params": {"type": "object"},
                    },
                    "additionalProperties": False,
                },
            ]
        },
        "cv": {"type": "integer"},
        "use_val_as_oof": {"type": "boolean"},
    },
}

# Training Configuration Schema
TRAINING_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "input_path": {"type": "string"},
        "target_column": {"type": "string"},
        "output_dir": {"type": "string"},
        "output_base_dir": {"type": "string"},
        "output_name": {"type": "string"},
        "split": SPLIT_SCHEMA,
        "feature_engineering": FEATURE_ENGINEERING_SCHEMA,
        "feature_selection": FEATURE_SELECTION_SCHEMA,
        "models": {"type": "array", "items": MODEL_CONFIG_SCHEMA},
        "ensemble": ENSEMBLE_SCHEMA,
        "evaluation": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "output_dir": {"type": "string"},
                "model_path": {"type": "string"},
                "feature_engineering_path": {"type": "string"},
                "target_column": {"type": "string"},
                "threshold": {"type": "number", "minimum": 0, "maximum": 1},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "generate_plots": {"type": "boolean"},
                "generate_html_report": {"type": "boolean"},
                "generate_json_report": {"type": "boolean"},
                "calibration": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "strategy": {
                            "type": "string",
                            "enum": ["cost_benefit", "operational", "precision_recall"],
                        },
                        "params": {"type": "object"},
                    },
                },
                "segment_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column names to compute per-segment evaluation metrics",
                },
                "segmented_evaluation": {
                    "type": "object",
                    "description": "Per-segment evaluation with column combos and configurable threshold modes",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "by": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Columns or combos (use '+' to combine, e.g. 'zona+region')",
                        },
                        "min_samples": {"type": "integer", "minimum": 0, "default": 30},
                        "threshold_mode": {
                            "type": "string",
                            "enum": [
                                "global",
                                "youden",
                                "f1_optimal",
                                "recall_target",
                                "segment",
                            ],
                            "default": "global",
                        },
                        "recall_target": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": 0.8,
                        },
                        "thresholds_output_dir": {
                            "type": "string",
                            "description": (
                                "Directory where segment_thresholds_*.json "
                                "files are written. Defaults to the trained "
                                "model's directory (models/). Set an explicit "
                                "path to override."
                            ),
                        },
                    },
                },
                "shap": {
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "Enable SHAP value computation and plots",
                            "default": False,
                        },
                        "max_samples": {
                            "type": "integer",
                            "description": "Maximum number of samples for SHAP computation (background + test)",
                            "minimum": 50,
                            "default": 500,
                        },
                        "top_n_features": {
                            "type": "integer",
                            "description": "Number of top features to display in SHAP plots",
                            "minimum": 1,
                            "default": 20,
                        },
                        "plot_types": {
                            "type": "array",
                            "description": "Which SHAP plot types to generate",
                            "items": {
                                "type": "string",
                                "enum": ["summary", "bar"],
                            },
                            "default": ["summary", "bar"],
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
    },
}

# Evaluation Configuration Schema (legacy, standalone)
EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "input_path": {"type": "string"},
        "output_dir": {"type": "string"},
        "model_path": {"type": "string"},
        "feature_engineering_path": {"type": "string"},
        "target_column": {"type": "string"},
        "threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "metrics": {"type": "array", "items": {"type": "string"}},
        "generate_plots": {"type": "boolean"},
        "generate_html_report": {"type": "boolean"},
        "generate_json_report": {"type": "boolean"},
        "calibration": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "strategy": {
                    "type": "string",
                    "enum": ["cost_benefit", "operational", "precision_recall"],
                },
                "params": {"type": "object"},
            },
        },
        "shap": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Enable SHAP value computation and plots",
                    "default": False,
                },
                "max_samples": {
                    "type": "integer",
                    "description": "Maximum number of samples for SHAP computation (background + test)",
                    "minimum": 50,
                    "default": 500,
                },
                "top_n_features": {
                    "type": "integer",
                    "description": "Number of top features to display in SHAP plots",
                    "minimum": 1,
                    "default": 20,
                },
                "plot_types": {
                    "type": "array",
                    "description": "Which SHAP plot types to generate",
                    "items": {
                        "type": "string",
                        "enum": ["summary", "bar"],
                    },
                    "default": ["summary", "bar"],
                },
            },
            "additionalProperties": False,
        },
        "segment_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Column names to compute per-segment evaluation metrics",
        },
    },
}

# Inference Configuration Schema
INFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "input_path": {"type": "string"},
        "output_path": {"type": "string"},
        "model_path": {"type": "string"},
        "feature_engineering_path": {"type": "string"},
        "output_include_input": {"type": "boolean"},
        "output_format": {"type": "string", "enum": ["csv", "parquet"]},
        "threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "custom_class": {"type": "string"},
        "params": {"type": "object"},
        "columns_filter": {
            "type": "object",
            "description": "Row-level filtering before feature engineering. Maps column -> scalar | list | {operator: value}, plus optional '_expr' pandas query string.",
        },
        "output_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Authoritative, self-sufficient final column selection for the output "
                "file, applied over the combined [input + prediction + probability + "
                "rule_*] frame. Input columns named here are included automatically "
                "(no output_include_input needed); unlisted columns are dropped (so "
                "omitting 'prediction' excludes it). If absent, ALL columns are "
                "written (input + prediction + probability + rule_*); the deprecated "
                "output_include_input flag is now a redundant no-op."
            ),
        },
        "output_base_dir": {"type": "string"},
        "output_name": {"type": "string"},
        "sort_by_probability": {"type": "boolean", "default": True},
        "segment_thresholds": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "path": {"type": ["string", "null"]},
                "fallback_threshold": {"type": ["number", "null"]},
            },
        },
        "business_rules": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "apply_to": {
                    "type": "object",
                    "properties": {
                        "column": {
                            "type": "string",
                            "default": "geo_region",
                            "description": "Column used to filter eligible rows. Defaults to 'geo_region'.",
                        },
                        "regions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Only rows whose apply_to.column value is in this list are eligible for rules. If omitted, rules apply to ALL rows.",
                        },
                    },
                },
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "condition": {
                                "type": "string",
                                "description": "Pandas query/eval expression. Must return a boolean Series. Use backticks for column names starting with digits (e.g. `3_anterior`). Use 'False' for stub rules that never trigger.",
                            },
                            "action": {
                                "type": "string",
                                "enum": ["flag", "override", "score_boost"],
                                "default": "flag",
                            },
                            "value": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "For score_boost: amount to add to probability (clipped to [0,1]). For override: probability is set to 1.0 (value ignored). For flag: ignored.",
                            },
                        },
                        "required": ["name", "condition", "action"],
                    },
                },
                "output": {
                    "type": "object",
                    "properties": {
                        "add_rule_columns": {
                            "type": "boolean",
                            "default": True,
                            "description": "If True, add rule_<name> (bool) and rule_<name>_value (float) columns to the output.",
                        },
                    },
                },
            },
        },
    },
}

# EDA Column Detection Schema
EDA_COLUMN_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id_col": {"type": ["string", "null"]},
        "date_col": {"type": ["string", "null"]},
        "lat_col": {"type": ["string", "null"]},
        "lon_col": {"type": ["string", "null"]},
        "zone_col": {"type": ["string", "null"]},
        "periods_suffix": {"type": "string"},
    },
}

# EDA Data Source Schema
EDA_DATA_SOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "primary": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "target_col": {"type": "string"}},
        },
        "secondary": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "join_on": {"type": "string"}},
            },
        },
    },
}

# EDA Output Configuration Schema
EDA_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "output_dir": {"type": "string"},
        "interactive": {"type": "boolean"},
        "static": {"type": "boolean"},
    },
}

# EDA Outliers Section Schema
EDA_OUTLIERS_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": True},
        "methods": {
            "type": "array",
            "items": {"type": "string", "enum": ["iqr", "zscore", "modified_zscore"]},
            "default": ["iqr", "zscore"],
        },
        "thresholds": {
            "type": "object",
            "properties": {
                "iqr": {"type": "number", "default": 1.5},
                "zscore": {"type": "number", "default": 3.0},
                "modified_zscore": {"type": "number", "default": 3.5},
            },
        },
        "consumption_patterns": {"type": "boolean", "default": True},
        "alert_threshold": {"type": "number", "default": 10.0},
        "detailed_charts": {"type": "boolean", "default": True},
    },
}

# EDA Configuration Schema
EDA_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "column_detection": EDA_COLUMN_DETECTION_SCHEMA,
        "data_sources": EDA_DATA_SOURCE_SCHEMA,
        "sections": {
            "type": "object",
            "properties": {
                "loading": {"type": "object"},
                "global_stats": {"type": "object"},
                "columns": {"type": "object"},
                "outliers": EDA_OUTLIERS_SECTION_SCHEMA,
                "target": {"type": "object"},
                "geospatial": {"type": "object"},
                "feature_importance": {"type": "object"},
                "segmentation": {"type": "object"},
                "related_columns": {"type": "object"},
                "numeric": {"type": "object"},
                "categorical": {"type": "object"},
            },
        },
        "output": EDA_OUTPUT_SCHEMA,
    },
}

# Full Pipeline Configuration Schema
PIPELINE_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "etl": ETL_SCHEMA,
        "split": SPLIT_SCHEMA,
        "train": TRAINING_SCHEMA,
        "evaluation": EVALUATION_SCHEMA,
        "infer": INFERENCE_SCHEMA,
        "eda": EDA_SCHEMA,
    },
}
