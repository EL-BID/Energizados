"""
Modeling Module for Energizados Framework.

This module provides Machine Learning model implementations
for energy fraud detection.
"""

# Import new framework components (without heavy external dependencies)
from energizados.modeling.registry import ModelRegistry

# Import original models optionally based on dependencies
try:
    from energizados.feature_selection import (  # noqa: F401
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

try:
    from energizados.modeling.ensemble import EnsembleModel  # noqa: F401

    _ensemble_available = True
except ImportError:
    _ensemble_available = False

__all__ = [
    "ModelRegistry",
]

# Add to __all__ only what is available
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

if _ensemble_available:
    __all__.append("EnsembleModel")
