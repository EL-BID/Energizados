"""
Base Feature Pipeline Module.

DEPRECATED: Este módulo ha sido renombrado a `feature_engineering`.
Las importaciones aquí se redirigen al nuevo módulo para backward compatibility.

Se recomienda usar:
    from energizados.feature_engineering.base import BaseFeatureEngineering
"""

# Importar desde el nuevo módulo para backward compatibility
from energizados.feature_engineering.base import BaseFeatureEngineering

# Alias para backward compatibility
BaseFeaturePipeline = BaseFeatureEngineering

__all__ = ["BaseFeatureEngineering", "BaseFeaturePipeline"]
