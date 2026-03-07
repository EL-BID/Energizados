#!/usr/bin/env python
"""Script to run inference using a trained model.

Usage:
    python src/run/03_inference.py --run-dir output/train-20240101_1200
"""

import argparse
import pickle
from pathlib import Path

from energizados.core.pipeline import ConfigPipelineBuilder

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

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    feature_engineering = None
    if feature_engineering_path.exists():
        with open(feature_engineering_path, "rb") as f:
            feature_engineering = pickle.load(f)

    builder = ConfigPipelineBuilder(config_path="config/inference.yaml")
    pipeline = builder.build()

    # Inject trained artifacts into context before running
    pipeline.context["model"] = model
    if feature_engineering is not None:
        pipeline.context["feature_engineering"] = feature_engineering

    results = pipeline.run()
    print("Inference completed")
