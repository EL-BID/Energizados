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

        valid_methods = ["over", "undersample", "smotetomek", "none"]

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

        valid_ensemble_methods = ["soft_voting", "stacking", "weighted_voting"]

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
