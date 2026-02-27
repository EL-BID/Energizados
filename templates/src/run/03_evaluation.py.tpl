#!/usr/bin/env python
"""Script para ejecutar evaluación del modelo."""

from energizados.core.pipeline import ConfigPipelineBuilder

if __name__ == "__main__":
    from energizados.cli.main import _setup_logging
    _setup_logging(1)

    builder = ConfigPipelineBuilder(config_path="config/training.yaml")
    pipeline = builder.build()
    results = pipeline.run()
    print("✓ Evaluación completada")
