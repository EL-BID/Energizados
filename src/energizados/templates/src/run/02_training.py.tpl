#!/usr/bin/env python
"""Script to run training (includes feature engineering)."""

import logging

from energizados.core.pipeline import ConfigPipelineBuilder

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    config_paths = ["config/train.yaml"]
    builder = ConfigPipelineBuilder(
        config_path=config_paths[0],
        config_paths=config_paths,
    )
    results = builder.run()

    if builder.run_dir:
        logger.info("Training completed")
        logger.info("Run directory: %s", builder.run_dir)
        logger.info("Index: %s", builder.run_dir.parent / "index.html")
    else:
        logger.info("Training completed")
