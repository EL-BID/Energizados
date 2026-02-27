#!/usr/bin/env python
"""Script para ejecutar ETLs."""

from energizados.core.pipeline import ConfigPipelineBuilder

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    builder = ConfigPipelineBuilder(config_path="config/etls.yaml")
    pipeline = builder.build()
    results = pipeline.run()
    print("✓ ETLs completadas")
