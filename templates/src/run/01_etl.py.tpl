#!/usr/bin/env python
"""Script para ejecutar ETLs."""

from energizados.core.pipeline import ConfigPipelineBuilder

if __name__ == "__main__":
    builder = ConfigPipelineBuilder(config_path="config/etls.yaml")
    pipeline = builder.build()
    results = pipeline.run()
    print("✓ ETLs completadas")
