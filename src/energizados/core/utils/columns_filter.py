"""Shared columns_filter utility for row-level filtering.

Used by both inference and training pipelines to apply consistent
row filtering based on column values, comparison operators, and
pandas query expressions.
"""

import logging
from typing import Any, Dict, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

_SUPPORTED_OPERATORS = {"==", "!=", ">", ">=", "<", "<=", "like"}


def validate_columns_filter(columns_filter: Any, context: str = "columns_filter") -> None:
    """Validate the structural grammar shared by row-filter configuration surfaces."""
    if not isinstance(columns_filter, dict):
        raise ValueError(
            f"{context}: filter must be a mapping, got {type(columns_filter).__name__}"
        )

    for column, filter_value in columns_filter.items():
        if column == "_expr":
            if not isinstance(filter_value, str):
                raise ValueError(f"{context}: _expr must be a string")
            continue
        if isinstance(filter_value, dict):
            for operator in filter_value:
                if operator not in _SUPPORTED_OPERATORS:
                    raise ValueError(
                        f"{context}: unknown operator '{operator}' for column '{column}'"
                    )


def apply_columns_filter(
    data: pd.DataFrame,
    columns_filter: Dict[str, Union[str, int, float, list, dict]],
    strict: bool = False,
) -> Tuple[pd.DataFrame, int]:
    """Apply columns_filter to a DataFrame.

    Supports three filter modes:
    1. Simple equality: ``column: "value"`` or ``column: ["val1", "val2"]``
    2. Comparison operators: ``column: {">": 250, "<=": 500}``
    3. Pandas query expression: ``_expr: "(zona == 'A') & (consumo >= 200)"``

    Args:
        data: Input DataFrame to filter.
        columns_filter: Dict mapping column names to filter values.
        strict: If True, raise on missing columns, unknown operators, or invalid
            expressions. If False, preserve the legacy warn/log-and-continue behavior.

    Returns:
        Tuple of (filtered DataFrame, number of rows removed).
    """
    if not columns_filter:
        return data, 0

    original_count = len(data)
    filtered_data = data.copy()

    if "_expr" in columns_filter:
        expr = columns_filter["_expr"]
        try:
            before_expr = len(filtered_data)
            filtered_data = filtered_data.query(expr)
            after_expr = len(filtered_data)
            logger.info(
                f"  • columns_filter._expr: filtered to {after_expr:,} records "
                f"(removed {before_expr - after_expr:,})"
            )
        except Exception as e:
            logger.error(f"  • columns_filter._expr: invalid expression '{expr}': {e}")
            if strict:
                raise ValueError(f"columns_filter._expr: invalid expression '{expr}': {e}") from e
        columns_filter_clean = {k: v for k, v in columns_filter.items() if k != "_expr"}
    else:
        columns_filter_clean = columns_filter

    for col_name, filter_value in columns_filter_clean.items():
        if col_name not in filtered_data.columns:
            message = f"columns_filter: column '{col_name}' not found"
            if strict:
                raise ValueError(message)
            logger.warning(f"  • {message}, skipping")
            continue

        if col_name.startswith("_"):
            continue

        if isinstance(filter_value, dict):
            for op, op_value in filter_value.items():
                if op == ">":
                    filtered_data = filtered_data[filtered_data[col_name] > op_value]
                elif op == "<":
                    filtered_data = filtered_data[filtered_data[col_name] < op_value]
                elif op == ">=":
                    filtered_data = filtered_data[filtered_data[col_name] >= op_value]
                elif op == "<=":
                    filtered_data = filtered_data[filtered_data[col_name] <= op_value]
                elif op == "!=":
                    filtered_data = filtered_data[filtered_data[col_name] != op_value]
                elif op == "==":
                    filtered_data = filtered_data[filtered_data[col_name] == op_value]
                elif op == "like":
                    filtered_data = filtered_data[
                        filtered_data[col_name]
                        .astype(str)
                        .str.contains(op_value, case=False, na=False)
                    ]
                else:
                    message = f"columns_filter.{col_name}: unknown operator '{op}'"
                    if strict:
                        raise ValueError(message)
                    logger.warning(f"  • {message}, skipping")
            logger.info(f"  • columns_filter.{col_name}: operators applied")
            continue

        if not isinstance(filter_value, list):
            filter_value = [filter_value]

        filtered_data = filtered_data[filtered_data[col_name].isin(filter_value)]

    removed = original_count - len(filtered_data)
    return filtered_data, removed
