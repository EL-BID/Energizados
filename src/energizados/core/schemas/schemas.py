"""
JSON Schema definitions for configuration validation.

This module contains the schema definitions for each configuration type.
"""

# ETL Configuration Schema
ETL_SCHEMA = {
    "type": "object",
    "additionalProperties": {
        "type": "object",
        "required": ["input", "output"],
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
            "enum": ["stratified", "random", "time_series", "group_based"],
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
                    "enum": ["smote", "undersample", "oversample", "none"],
                },
                "strategy": {"type": "string"},
            },
        },
        "hyperparam_search": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "method": {"type": "string", "enum": ["grid", "random", "bayesian"]},
                "n_iter": {"type": "integer"},
                "cv": {"type": "integer"},
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
        "method": {"type": "string", "enum": ["soft_voting", "stacking", "weighted_voting"]},
        "weights": {"type": "array", "items": {"type": "number"}},
        "meta_learner": {
            "type": "string",
            "enum": ["logistic_regression", "random_forest", "gradient_boosting"],
        },
        "cv": {"type": "integer"},
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
                        "strategy": {
                            "type": "string",
                            "enum": ["cost_benefit", "operational", "precision_recall"],
                        },
                        "params": {"type": "object"},
                    },
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
                "strategy": {
                    "type": "string",
                    "enum": ["cost_benefit", "operational", "precision_recall"],
                },
                "params": {"type": "object"},
            },
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
        "threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "custom_class": {"type": "string"},
        "params": {"type": "object"},
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

# EDA Configuration Schema
EDA_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "column_detection": EDA_COLUMN_DETECTION_SCHEMA,
        "data_sources": EDA_DATA_SOURCE_SCHEMA,
        "sections": {"type": "object"},
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
