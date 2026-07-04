"""
Pipeline API for Energizados.

This module re-exports the core Pipeline class and provides documentation
for the programmatic API.
"""

# Re-export core Pipeline (do not subclass or redefine)
from energizados.core.pipeline import Pipeline

__all__ = ["Pipeline", "from_dict", "plan"]

# Document the from_dict classmethod availability
from_dict = Pipeline.from_dict
plan = Pipeline.plan
