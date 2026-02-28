"""
Column Resolver for Multi-Step Feature Selection.

Resolves column patterns (literal, glob, regex, @step_ref, ! exclusion)
against an available column list.
"""

import fnmatch
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ColumnResolver:
    """
    Resolves column patterns against a list of available columns.

    Supported pattern types:
    - ``@step_name``    → columns from that step's result
    - ``re:pattern``    → regex match via re.search against available columns
    - ``*``, ``?``, ``[`` present → glob via fnmatch.fnmatch
    - Otherwise        → exact match (silently empty if not found)
    - ``!`` prefix     → puts resolved set into exclusion set

    Output preserves original DataFrame column order and deduplicates.

    Args:
        available_columns: All columns present in the dataset being processed.
        step_results: Mapping from step name to the list of columns it selected.
    """

    def __init__(
        self,
        available_columns: List[str],
        step_results: Optional[Dict[str, List[str]]] = None,
    ):
        self.available_columns = list(available_columns)
        self.step_results = step_results or {}

    def resolve(self, patterns: List[str]) -> List[str]:
        """
        Resolve a list of patterns into an ordered, deduplicated column list.

        Args:
            patterns: List of pattern strings (may include ``!`` prefix).

        Returns:
            Ordered list of column names (include_set - exclude_set),
            preserving original column order.
        """
        include_set: set = set()
        exclude_set: set = set()

        for pattern in patterns:
            if pattern.startswith("!"):
                raw = pattern[1:]
                resolved = self._resolve_single(raw)
                exclude_set.update(resolved)
            else:
                resolved = self._resolve_single(pattern)
                include_set.update(resolved)

        final = include_set - exclude_set
        # Preserve order from available_columns
        return [c for c in self.available_columns if c in final]

    def _resolve_single(self, pattern: str) -> List[str]:
        """
        Resolve a single pattern (without ``!`` prefix) to a list of columns.

        Args:
            pattern: A pattern string.

        Returns:
            List of matching column names.

        Raises:
            KeyError: If ``@step_name`` references an unknown step.
            re.error: If ``re:pattern`` is an invalid regular expression.
        """
        if pattern.startswith("@"):
            return self._resolve_step_ref(pattern[1:])
        if pattern.startswith("re:"):
            return self._resolve_regex(pattern[3:])
        if any(c in pattern for c in ("*", "?", "[")):
            return self._resolve_glob(pattern)
        return self._resolve_literal(pattern)

    def _resolve_literal(self, name: str) -> List[str]:
        """Exact column name match. Returns empty list if not found."""
        if name in self.available_columns:
            return [name]
        return []

    def _resolve_glob(self, pattern: str) -> List[str]:
        """fnmatch glob pattern match against available columns."""
        return [c for c in self.available_columns if fnmatch.fnmatch(c, pattern)]

    def _resolve_regex(self, pattern: str) -> List[str]:
        """
        Regex match (re.search) against available columns.

        Raises:
            re.error: If the pattern is invalid.
        """
        compiled = re.compile(pattern)
        return [c for c in self.available_columns if compiled.search(c)]

    def _resolve_step_ref(self, step_name: str) -> List[str]:
        """
        Return columns from a prior step's result.

        Raises:
            KeyError: If step_name is not in step_results.
        """
        if step_name not in self.step_results:
            raise KeyError(f"Step reference '@{step_name}' not found. " f"Available steps: {list(self.step_results.keys())}")
        return list(self.step_results[step_name])
