"""Test JSON Schema validation for configuration."""

from energizados.core.schemas.config_validator import ConfigValidator


class TestConfigSchemas:
    """Test JSON Schema validation for Energizados configurations."""

    def test_smotetomek_sampling_method_valid(self):
        """Verify that smotetomek is a valid sampling method in schema."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [
                    {
                        "type": "lightgbm",
                        "sampling": {"method": "smotetomek", "threshold": 0.5},
                    }
                ],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_all_sampling_methods_valid(self):
        """Verify all supported sampling methods are valid in schema."""
        validator = ConfigValidator()

        valid_methods = ["oversample", "undersample", "smotetomek", "none"]

        for method in valid_methods:
            config = {
                "train": {
                    "enabled": True,
                    "input_path": "data/test.parquet",
                    "target_column": "target",
                    "models": [
                        {
                            "type": "lightgbm",
                            "sampling": {"method": method, "threshold": 0.5},
                        }
                    ],
                }
            }

            errors = validator.validate_config(config)
            assert len(errors) == 0, f"Method '{method}' should be valid, got: {errors}"

    def test_invalid_sampling_method_rejected(self):
        """Verify that invalid sampling methods are rejected by the schema."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [
                    {
                        "type": "lightgbm",
                        "sampling": {"method": "invalid_method", "threshold": 0.5},
                    }
                ],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for invalid sampling method"
        assert any("sampling" in str(err).lower() or "method" in str(err).lower() for err in errors)

    def test_model_type_validation(self):
        """Verify that model types are validated correctly."""
        validator = ConfigValidator()

        valid_model_types = [
            "lightgbm",
            "catboost",
            "neural_network",
            "lstm",
            "simple_trend",
            "simple_constant",
        ]

        for model_type in valid_model_types:
            config = {
                "train": {
                    "enabled": True,
                    "input_path": "data/test.parquet",
                    "target_column": "target",
                    "models": [{"type": model_type}],
                }
            }

            errors = validator.validate_config(config)
            assert len(errors) == 0, f"Model type '{model_type}' should be valid, got: {errors}"

    def test_ensemble_method_validation(self):
        """Verify that ensemble methods are validated correctly."""
        validator = ConfigValidator()

        valid_ensemble_methods = ["soft_voting", "stacking"]

        for method in valid_ensemble_methods:
            config = {
                "train": {
                    "enabled": True,
                    "input_path": "data/test.parquet",
                    "target_column": "target",
                    "models": [
                        {"type": "lightgbm"},
                        {"type": "catboost"},
                    ],
                    "ensemble": {"method": method},
                }
            }

            errors = validator.validate_config(config)
            assert len(errors) == 0, f"Ensemble method '{method}' should be valid, got: {errors}"

    def test_shap_config_validation(self):
        """Verify that SHAP configuration is validated correctly in training schema."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [{"type": "lightgbm"}],
                "evaluation": {
                    "enabled": True,
                    "shap": {
                        "enabled": True,
                        "max_samples": 500,
                        "top_n_features": 20,
                        "plot_types": ["summary", "bar"],
                    },
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"SHAP config should be valid, got: {errors}"

    def test_shap_plot_types_validation(self):
        """Verify that SHAP plot types are validated correctly."""
        validator = ConfigValidator()

        valid_plot_types = [["summary"], ["bar"], ["summary", "bar"]]

        for plot_types in valid_plot_types:
            config = {
                "train": {
                    "enabled": True,
                    "input_path": "data/test.parquet",
                    "target_column": "target",
                    "models": [{"type": "lightgbm"}],
                    "evaluation": {
                        "enabled": True,
                        "shap": {
                            "enabled": True,
                            "plot_types": plot_types,
                        },
                    },
                }
            }

            errors = validator.validate_config(config)
            assert len(errors) == 0, f"SHAP plot types {plot_types} should be valid, got: {errors}"

    def test_eda_outliers_section_valid(self):
        """Verify that EDA outliers section configuration is valid."""
        validator = ConfigValidator()

        config = {
            "eda": {
                "enabled": True,
                "sections": {
                    "outliers": {
                        "enabled": True,
                        "methods": ["iqr", "zscore"],
                        "thresholds": {
                            "iqr": 1.5,
                            "zscore": 3.0,
                            "modified_zscore": 3.5,
                        },
                        "consumption_patterns": True,
                        "alert_threshold": 10.0,
                        "detailed_charts": True,
                    }
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"EDA outliers config should be valid, got: {errors}"

    def test_eda_outliers_all_methods_valid(self):
        """Verify all supported outlier methods are valid in EDA schema."""
        validator = ConfigValidator()

        valid_combinations = [
            ["iqr"],
            ["zscore"],
            ["modified_zscore"],
            ["iqr", "zscore"],
            ["iqr", "zscore", "modified_zscore"],
        ]

        for methods in valid_combinations:
            config = {
                "eda": {
                    "enabled": True,
                    "sections": {
                        "outliers": {
                            "enabled": True,
                            "methods": methods,
                        }
                    },
                }
            }

            errors = validator.validate_config(config)
            assert (
                len(errors) == 0
            ), f"EDA outliers methods {methods} should be valid, got: {errors}"

    def test_eda_outliers_invalid_method_rejected(self):
        """Verify that invalid outlier methods are rejected by EDA schema."""
        validator = ConfigValidator()

        config = {
            "eda": {
                "enabled": True,
                "sections": {
                    "outliers": {
                        "enabled": True,
                        "methods": ["invalid_method"],
                    }
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for invalid outlier method"
        assert any("outlier" in str(err).lower() or "method" in str(err).lower() for err in errors)

    def test_eda_outliers_thresholds_valid(self):
        """Verify that outlier threshold values are validated correctly."""
        validator = ConfigValidator()

        config = {
            "eda": {
                "enabled": True,
                "sections": {
                    "outliers": {
                        "enabled": True,
                        "thresholds": {
                            "iqr": 1.5,
                            "zscore": 3.0,
                            "modified_zscore": 3.5,
                        },
                        "alert_threshold": 10.0,
                    }
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"EDA outliers thresholds should be valid, got: {errors}"

    # T-S1 Tests: SPLIT_SCHEMA extensions for unlabeled_negatives and geo_stratify

    def test_split_unlabeled_negatives_valid(self):
        """Verify that unlabeled_negatives config passes validation."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "split": {
                    "method": "time_series",
                    "date_column": "fecha_inspeccion",
                    "train_period": ["2010-01-01", "2017-08-01"],
                    "val_period": ["2017-09-01", "2017-12-31"],
                    "test_period": ["2018-01-01", "2018-12-31"],
                    "unlabeled_negatives": {
                        "enabled": True,
                        "source_path": "data/unlabeled.parquet",
                        "max_per_cutoff": 1500,
                        "random_state": 42,
                        "date_column": "fecha_inspeccion",
                        "id_column": "cliente_id",
                    },
                },
                "models": [{"type": "lightgbm"}],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"unlabeled_negatives config should be valid, got: {errors}"

    def test_split_unlabeled_negatives_backward_compat(self):
        """Verify that split WITHOUT unlabeled_negatives still passes (backward compatible)."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "split": {
                    "method": "stratified",
                    "test_size": 0.2,
                    "val_size": 0.1,
                    "random_state": 42,
                },
                "models": [{"type": "lightgbm"}],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"Split without unlabeled_negatives should be valid, got: {errors}"

    def test_split_geo_stratify_valid(self):
        """Verify that geo_stratify config passes validation."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "split": {
                    "method": "stratified",
                    "test_size": 0.2,
                    "val_size": 0.1,
                    "geo_stratify": {
                        "enabled": True,
                        "column": "geo_cluster",
                        "strategy": "proportional",
                        "max_per_stratum": 5000,
                        "random_state": 42,
                    },
                },
                "models": [{"type": "lightgbm"}],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"geo_stratify config should be valid, got: {errors}"

    def test_split_geo_stratify_all_strategies_valid(self):
        """Verify all supported geo_stratify strategies are valid."""
        validator = ConfigValidator()

        valid_strategies = ["proportional", "equal", "capped"]

        for strategy in valid_strategies:
            config = {
                "train": {
                    "enabled": True,
                    "input_path": "data/test.parquet",
                    "target_column": "target",
                    "split": {
                        "method": "stratified",
                        "test_size": 0.2,
                        "geo_stratify": {
                            "enabled": True,
                            "column": "geo_cluster",
                            "strategy": strategy,
                        },
                    },
                    "models": [{"type": "lightgbm"}],
                }
            }

            errors = validator.validate_config(config)
            assert (
                len(errors) == 0
            ), f"geo_stratify strategy '{strategy}' should be valid, got: {errors}"

    def test_split_geo_stratify_invalid_strategy_rejected(self):
        """Verify that invalid geo_stratify strategy is rejected."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "split": {
                    "method": "stratified",
                    "test_size": 0.2,
                    "geo_stratify": {
                        "enabled": True,
                        "column": "geo_cluster",
                        "strategy": "invalid_strategy",
                    },
                },
                "models": [{"type": "lightgbm"}],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for invalid geo_stratify strategy"
        assert any("strategy" in str(err).lower() for err in errors)

    # T-S2 Tests: INFERENCE_SCHEMA extension for segment_thresholds

    def test_inference_segment_thresholds_valid(self):
        """Verify that segment_thresholds config passes validation."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "segment_thresholds": {
                    "enabled": True,
                    "path": "config/thresholds.yaml",
                    "fallback_threshold": 0.5,
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"segment_thresholds config should be valid, got: {errors}"

    def test_inference_segment_thresholds_backward_compat(self):
        """Verify that infer WITHOUT segment_thresholds still passes (backward compatible)."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
            }
        }

        errors = validator.validate_config(config)
        assert (
            len(errors) == 0
        ), f"Inference without segment_thresholds should be valid, got: {errors}"

    def test_inference_segment_thresholds_minimal(self):
        """Verify that segment_thresholds with just enabled field is valid."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "segment_thresholds": {
                    "enabled": False,
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"Minimal segment_thresholds config should be valid, got: {errors}"

    # T-SEG Tests: TRAINING_SCHEMA extension for evaluation.segmented_evaluation

    def test_training_segmented_evaluation_valid(self):
        """Verify that a well-formed segmented_evaluation config passes validation."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [{"type": "lightgbm"}],
                "evaluation": {
                    "enabled": True,
                    "segmented_evaluation": {
                        "enabled": True,
                        "by": ["zona", "region", "zona+region"],
                        "min_samples": 30,
                        "threshold_mode": "youden",
                        "recall_target": 0.8,
                    },
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"segmented_evaluation config should be valid, got: {errors}"

    def test_training_segmented_evaluation_invalid_enabled_type(self):
        """Verify that segmented_evaluation.enabled as a non-boolean is rejected."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [{"type": "lightgbm"}],
                "evaluation": {
                    "enabled": True,
                    "segmented_evaluation": {
                        "enabled": "yes",  # not a boolean
                        "by": ["zona"],
                    },
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for non-boolean segmented_evaluation.enabled"
        assert any("segmented_evaluation" in str(err).lower() for err in errors)

    def test_training_segmented_evaluation_invalid_min_samples_type(self):
        """Verify that segmented_evaluation.min_samples as a non-integer is rejected."""
        validator = ConfigValidator()

        config = {
            "train": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "target_column": "target",
                "models": [{"type": "lightgbm"}],
                "evaluation": {
                    "enabled": True,
                    "segmented_evaluation": {
                        "enabled": True,
                        "min_samples": "thirty",  # not an integer
                    },
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for non-integer segmented_evaluation.min_samples"
        assert any("segmented_evaluation" in str(err).lower() for err in errors)

    # T-INF2 Tests: INFERENCE_SCHEMA extensions for columns_filter, output_columns, output_base_dir

    def test_inference_columns_filter_valid(self):
        """Verify that columns_filter config passes validation."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "columns_filter": {
                    "zona": ["NORTE", "SUL"],
                    "consumo": {">": 100, "<=": 50000},
                    "_expr": "(zona != 'A') & (consumo > 200)",
                },
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"columns_filter config should be valid, got: {errors}"

    def test_inference_output_columns_valid(self):
        """Verify that output_columns config passes validation."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "output_columns": ["prediction", "probability", "cliente_id"],
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"output_columns config should be valid, got: {errors}"

    def test_inference_output_columns_invalid_type_rejected(self):
        """Verify that output_columns as a non-array is rejected."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "output_columns": "prediction",  # should be an array
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) > 0, "Expected errors for non-array output_columns"
        assert any("output_columns" in str(err).lower() for err in errors)

    def test_inference_output_base_dir_valid(self):
        """Verify that output_base_dir config passes validation."""
        validator = ConfigValidator()

        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/test.parquet",
                "output_path": "data/output.parquet",
                "model_path": "models/model.pkl",
                "output_base_dir": "output",
            }
        }

        errors = validator.validate_config(config)
        assert len(errors) == 0, f"output_base_dir config should be valid, got: {errors}"
