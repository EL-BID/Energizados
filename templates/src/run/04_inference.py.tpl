#!/usr/bin/env python
"""Script para ejecutar inferencia."""

from energizados.core.pipeline import ConfigPipelineBuilder

if __name__ == "__main__":
    builder = ConfigPipelineBuilder(config_path="config/inference.yaml")
    pipeline = builder.build()
    results = pipeline.run()
    print("✓ Inferencia completada")
