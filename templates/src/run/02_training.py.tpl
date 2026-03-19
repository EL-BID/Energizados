#!/usr/bin/env python
"""Script to run training (includes feature engineering)."""

from energizados.core.pipeline import ConfigPipelineBuilder

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    config_paths = ["config/train.yaml"]
    builder = ConfigPipelineBuilder(
        config_path=config_paths[0],
        config_paths=config_paths,
    )
    results = builder.run()

    if builder._run_dir:
        print(f"✓ Training completed")
        print(f"  Run directory: {builder._run_dir}")
        print(f"  Index: {builder._run_dir.parent / 'index.html'}")
    else:
        print("✓ Training completed")
