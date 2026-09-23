"""Regression tests for fill_empty_values_cycle.

The axis-1 ffill/bfill consolidates the consumption block to float64. When some
consumption columns are int64 (no NaNs) and others are float64 (missing cycles),
pandas 3.x (Copy-on-Write) raises ``TypeError: Invalid value ... for dtype
'int64'`` on the old ``df.loc[:, cols] = ...ffill(axis=1)`` pattern, while
pandas 2.x silently upcast. The fix assigns via wholesale column replacement
after normalizing the block to float64.
"""

import numpy as np
import pandas as pd

from energizados.preprocessing.preprocessing import fill_empty_values_cycle


class TestFillEmptyValuesCycle:
    """Test suite for fill_empty_values_cycle."""

    def test_mixed_int64_float64_consumption_columns(self):
        """Regression: mixed int64/float64 consumption cols must not raise.

        Fails on pandas 3.x with the old .loc assignment (lossy write into the
        int64 column) and produced version-dependent dtypes on pandas 2.x.
        """
        df = pd.DataFrame(
            {
                "3_anterior": [10.0, np.nan, 30.0, np.nan],
                "2_anterior": [1, 2, 3, 4],  # int64: column without NaNs
                "1_anterior": [np.nan, 5.0, np.nan, np.nan],
                "zona": ["norte", "sur", "este", "oeste"],
            }
        )

        result = fill_empty_values_cycle(df, cant_ciclos_validos=3)

        # Forward fill (left to right) then backward fill across periods
        assert result["3_anterior"].tolist() == [10.0, 2.0, 30.0, 4.0]
        assert result["2_anterior"].tolist() == [1.0, 2.0, 3.0, 4.0]
        assert result["1_anterior"].tolist() == [1.0, 5.0, 3.0, 4.0]
        # Consumption block ends uniformly float64 on every pandas version
        consumption = result[["3_anterior", "2_anterior", "1_anterior"]]
        assert (consumption.dtypes == "float64").all()
        # Non-consumption columns are untouched
        assert result["zona"].tolist() == ["norte", "sur", "este", "oeste"]

    def test_all_nan_row_stays_nan(self):
        """A row with every consumption value missing cannot be filled."""
        df = pd.DataFrame(
            {
                "3_anterior": [np.nan, 10.0],
                "2_anterior": [np.nan, np.nan],
                "1_anterior": [np.nan, 2.0],
            }
        )

        result = fill_empty_values_cycle(df, cant_ciclos_validos=3)

        assert result.iloc[0].isna().all()
        assert result.iloc[1].tolist() == [10.0, 10.0, 2.0]

    def test_complete_columns_are_unchanged(self):
        """A fully populated consumption block passes through unchanged."""
        df = pd.DataFrame(
            {
                "3_anterior": [1.0, 2.0],
                "2_anterior": [3.0, 4.0],
                "1_anterior": [5.0, 6.0],
            }
        )

        original = df.copy()

        result = fill_empty_values_cycle(df, cant_ciclos_validos=3)

        pd.testing.assert_frame_equal(result, original)
