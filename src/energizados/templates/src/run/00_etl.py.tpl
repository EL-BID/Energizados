#!/usr/bin/env python
"""Script to run ETLs."""

import logging

from energizados.core.pipeline import ConfigPipelineBuilder

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    builder = ConfigPipelineBuilder(config_path="config/etl.yaml")
    pipeline = builder.build()
    results = pipeline.run()
    logger.info("ETLs completed")
