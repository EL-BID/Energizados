#!/usr/bin/env python
"""Script to run inference using a trained model.

Usage:
    python src/run/03_inference.py --run-dir output/train-20240101_1200

The script auto-resolves model and feature engineering paths from the
run directory and passes them as config overrides to ConfigPipelineBuilder.
"""

import argparse
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from energizados.core.pipeline import ConfigPipelineBuilder
from energizados.core.utils.secure_pickle import secure_load

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    parser = argparse.ArgumentParser(description="Run inference using a trained model")
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to a training run directory (e.g. output/train-20240101_1200)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    model_path = run_dir / "models" / "model.pkl"
    feature_engineering_path = run_dir / "models" / "feature_engineering.pkl"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    # Load config and merge resolved paths
    config_path = "config/infer.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Inject resolved paths into infer section
    infer_config = config.setdefault("infer", {})
    infer_config["model_path"] = str(model_path)
    if feature_engineering_path.exists():
        infer_config["feature_engineering_path"] = str(feature_engineering_path)

    builder = ConfigPipelineBuilder(config=config, config_paths=[config_path])
    pipeline = builder.build()

    results = pipeline.run()
    logger.info("Inference completed")
