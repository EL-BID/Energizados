"""
Default Feature Pipeline Implementation.

DEPRECATED: Este módulo ha sido renombrado a `feature_engineering`.
Las importaciones aquí se redirigen al nuevo módulo para backward compatibility.

Se recomienda usar:
    from energizados.feature_engineering.default import DefaultFeatureEngineering
"""

# Importar desde el nuevo módulo para backward compatibility
from energizados.feature_engineering.default import (
    DefaultFeatureEngineering,
    get_preprocesor,
)

# Alias para backward compatibility
DefaultFeaturePipeline = DefaultFeatureEngineering

__all__ = [
    "DefaultFeatureEngineering",
    "DefaultFeaturePipeline",
    "get_preprocesor",
]
