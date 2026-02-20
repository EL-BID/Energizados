"""
Modeling Module for Energizados Framework.

Este módulo proporciona implementaciones de modelos de Machine Learning
para la detección de fraude energético.
"""

# Importar nuevos componentes del framework (sin dependencias externas pesadas)
from energizados.modeling.registry import ModelRegistry

# Importar modelos originales de forma opcional según dependencias
try:
    from energizados.modeling.feature_selection import (  # noqa: F401
        feature_selection_by_boruta,
        feature_selection_by_constant,
        feature_selection_by_correlation,
    )

    _feature_selection_available = True
except ImportError:
    _feature_selection_available = False

try:
    from energizados.modeling.simple_models import (  # noqa: F401
        ChangeTrendPercentajeIdentifierWide,
        ConstantConsumptionClassifierWide,
    )

    _simple_models_available = True
except ImportError:
    _simple_models_available = False

try:
    from energizados.modeling.supervised_models import (  # noqa: F401
        CATModel,
        LGBMModel,
        LSTMNNModel,
        NNModel,
    )

    _supervised_models_available = True
except ImportError:
    _supervised_models_available = False

try:
    from energizados.modeling.adapters import (  # noqa: F401
        CATModelAdapter,
        LGBMModelAdapter,
        LSTMNNModelAdapter,
        NNModelAdapter,
        SimpleConstantAdapter,
        SimpleTrendAdapter,
    )

    _adapters_available = True
except ImportError:
    _adapters_available = False

__all__ = [
    "ModelRegistry",
]

# Agregar a __all__ solo lo que esté disponible
if _feature_selection_available:
    __all__.extend(
        [
            "feature_selection_by_correlation",
            "feature_selection_by_constant",
            "feature_selection_by_boruta",
        ]
    )

if _simple_models_available:
    __all__.extend(
        [
            "ChangeTrendPercentajeIdentifierWide",
            "ConstantConsumptionClassifierWide",
        ]
    )

if _supervised_models_available:
    __all__.extend(
        [
            "LGBMModel",
            "CATModel",
            "NNModel",
            "LSTMNNModel",
        ]
    )

if _adapters_available:
    __all__.extend(
        [
            "LGBMModelAdapter",
            "CATModelAdapter",
            "NNModelAdapter",
            "LSTMNNModelAdapter",
            "SimpleTrendAdapter",
            "SimpleConstantAdapter",
        ]
    )
