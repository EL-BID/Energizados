"""
Multi-Step Feature Selection Pipeline.

Provides FeatureSelectionPipeline (orchestrator) and SelectionStep (set composition).
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

import pandas as pd

from energizados.feature_selection.base import BaseFeatureSelector
from energizados.feature_selection.column_resolver import ColumnResolver

logger = logging.getLogger(__name__)

# Default mapping from method name to selector class (populated lazily to avoid
# importing heavy deps at module load time).
_DEFAULT_METHOD_MAP: Optional[Dict[str, type]] = None


def _get_default_method_map() -> Dict[str, type]:
    global _DEFAULT_METHOD_MAP
    if _DEFAULT_METHOD_MAP is None:
        from energizados.feature_selection.methods import (
            BorutaSelector,
            CategoricalSelector,
            ConstantSelector,
            CorrelationSelector,
            MutualInformationSelector,
        )

        _DEFAULT_METHOD_MAP = {
            "boruta": BorutaSelector,
            "categorical": CategoricalSelector,
            "correlation": CorrelationSelector,
            "constant": ConstantSelector,
            "mutual_info": MutualInformationSelector,
        }
    return _DEFAULT_METHOD_MAP


class SelectionStep:
    """
    Set-composition step (no ML fitting involved).

    Combines column lists from prior steps and/or literals/globs/regex
    via union, intersection, or difference.

    Args:
        operation: One of ``"union"``, ``"intersection"``, or ``"difference"``.
        patterns: Column patterns (literals, globs, regex, @refs, ! exclusions).
    """

    def __init__(self, operation: str, patterns: List[str]):
        valid_ops = ("union", "intersection", "difference")
        if operation not in valid_ops:
            raise ValueError(f"operation must be one of {valid_ops}, got '{operation}'")
        self.operation = operation
        self.patterns = patterns
        self.selected_features_: Optional[List[str]] = None

    def fit_with_resolver(
        self, resolver: ColumnResolver, available_columns: List[str]
    ) -> "SelectionStep":
        """
        Resolve patterns and compute the selected column set.

        Args:
            resolver: A ColumnResolver with current step_results populated.
            available_columns: All columns available at this point (defines ordering).

        Returns:
            self
        """
        positives: List[str] = []
        negatives: List[str] = []
        for p in self.patterns:
            (negatives if p.startswith("!") else positives).append(p)

        # Resolve each positive pattern into its own set
        positive_sets: List[set] = [set(resolver._resolve_single(p)) for p in positives]
        # Resolve exclusions
        exclude_set: set = set()
        for neg in negatives:
            exclude_set.update(resolver._resolve_single(neg[1:]))

        if not positive_sets:
            result_set: set = set()
        elif self.operation == "union":
            result_set = set.union(*positive_sets)
        elif self.operation == "intersection":
            result_set = positive_sets[0]
            for s in positive_sets[1:]:
                result_set = result_set & s
        else:  # difference
            result_set = positive_sets[0]
            for s in positive_sets[1:]:
                result_set = result_set - s

        result_set -= exclude_set

        # Preserve order from available_columns
        self.selected_features_ = [c for c in available_columns if c in result_set]
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.selected_features_ is None:
            raise ValueError("Call fit_with_resolver() before transform()")
        return X[self.selected_features_]


class FeatureSelectionPipeline(BaseFeatureSelector):
    """
    Orchestrates a multi-step feature selection pipeline.

    Each step can be an ML-based selector (boruta, correlation, constant)
    scoped to a subset of columns, or a set-composition step (selection)
    that combines results from prior steps.

    The final output is defined by the last step's selected columns.

    Args:
        steps_config: List of step configuration dicts. Each dict must have:
            - ``name`` (str): unique step identifier
            - ``method`` (str): selector method or ``"selection"``
            - ``params`` (dict, optional): constructor kwargs for ML methods
            - ``columns`` (list, optional): column patterns to scope this step
            - ``operation`` (str): required when ``method == "selection"``
        method_map: Override or extend the default method → class mapping.

    Example::

        cfg = [
            {"name": "const", "method": "constant", "params": {"threshold": 0.99}},
            {
                "name": "final",
                "method": "selection",
                "operation": "union",
                "columns": ["@const", "zona"],
            },
        ]
        pipeline = FeatureSelectionPipeline(cfg)
        pipeline.fit(X_train, y_train)
        X_selected = pipeline.transform(X_train)
    """

    def __init__(
        self,
        steps_config: List[Dict],
        method_map: Optional[Dict[str, Type]] = None,
    ):
        self.steps_config = steps_config
        self._method_map = method_map
        self.selected_features_: Optional[List[str]] = None
        self._step_results: Dict[str, List[str]] = {}
        self._step_selectors: Dict[str, BaseFeatureSelector] = {}

    @property
    def method_map(self) -> Dict[str, type]:
        if self._method_map is None:
            return _get_default_method_map()
        return self._method_map

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FeatureSelectionPipeline":
        """
        Run all steps sequentially, fitting ML selectors on scoped columns.

        Args:
            X: Preprocessed feature DataFrame.
            y: Target series.

        Returns:
            self
        """
        self._step_results = {}
        available_columns = list(X.columns)
        last_name: Optional[str] = None

        for step_cfg in self.steps_config:
            name = step_cfg["name"]
            method = step_cfg["method"]
            params = step_cfg.get("params", {})
            col_patterns = step_cfg.get("columns", None)

            resolver = ColumnResolver(available_columns, self._step_results)

            # Resolve scope
            if col_patterns is not None:
                scoped_columns = resolver.resolve(col_patterns)
            else:
                scoped_columns = list(available_columns)

            if not scoped_columns:
                logger.warning(f"Feature selection step '{name}': empty column scope, skipping.")
                self._step_results[name] = []
                last_name = name
                continue

            if method == "selection":
                operation = step_cfg.get("operation", "union")
                step = SelectionStep(operation=operation, patterns=col_patterns or [])
                step.fit_with_resolver(resolver, available_columns)
                self._step_results[name] = step.selected_features_
            else:
                if method not in self.method_map:
                    raise ValueError(
                        f"Unknown feature selection method '{method}'. "
                        f"Available: {list(self.method_map.keys())}"
                    )
                selector_cls = self.method_map[method]
                selector = selector_cls(**params)
                selector.fit(X[scoped_columns], y)
                self._step_results[name] = selector.selected_features_
                self._step_selectors[name] = selector

            selected = self._step_results[name]
            dropped = [c for c in scoped_columns if c not in selected]
            logger.info(
                f"Step '{name}' ({method}): {len(selected)}/{len(scoped_columns)} columns selected"
            )
            logger.info(f"  Input:  {scoped_columns}")
            logger.info(f"  Output: {selected}")
            if dropped:
                logger.info(f"  Dropped: {dropped}")
            last_name = name

        if last_name is not None:
            self.selected_features_ = self._step_results[last_name]
        else:
            self.selected_features_ = list(available_columns)

        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Return X filtered to the final step's selected columns.

        Args:
            X: Feature DataFrame (must contain all selected columns).

        Returns:
            pd.DataFrame with only the selected columns.
        """
        if self.selected_features_ is None:
            raise ValueError("Call fit() before transform()")
        return X[self.selected_features_]

    def get_selected_features(self) -> List[str]:
        """Return the list of columns selected by the last step."""
        if self.selected_features_ is None:
            raise ValueError("Call fit() before get_selected_features()")
        return self.selected_features_

    def save_audit_log(self, path: Path) -> None:
        """
        Serialize step results + per-step audit stats to JSON.

        Creates a JSON file containing:
        - steps: List of steps with name, method, selected features, and audit stats
        - final_selected_count: Number of features selected
        - final_selected_features: List of final selected features

        Args:
            path: Path where to save the audit log JSON file.
        """
        steps_data = []

        for step_cfg in self.steps_config:
            name = step_cfg["name"]
            method = step_cfg["method"]

            selected_features = self._step_results.get(name, [])
            audit_stats = {}

            # Get audit stats from selector if available
            if name in self._step_selectors:
                selector = self._step_selectors[name]
                audit_stats = selector.get_audit_stats()

            step_data = {
                "name": name,
                "method": method,
                "selected_count": len(selected_features),
                "selected_features": selected_features,
                "audit_stats": audit_stats,
            }
            steps_data.append(step_data)

        audit_log = {
            "steps": steps_data,
            "final_selected_count": len(self.selected_features_) if self.selected_features_ else 0,
            "final_selected_features": self.selected_features_ if self.selected_features_ else [],
        }

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(audit_log, f, indent=2)

        logger.info(f"Feature selection audit log saved to: {path}")
