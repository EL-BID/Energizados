"""
Unit tests for OutlierDetector class in EDA module.

Tests cover:
- IQR method with normal and outlier data
- Z-score method with edge cases (std=0)
- Modified Z-score method (MAD-based)
- Alert threshold triggering
- Sample values limiting
- Invalid method validation
"""

import numpy as np
import pandas as pd
import pytest

from energizados.eda._outlier_detector import OutlierDetector


class TestOutlierDetectorInit:
    """Tests for OutlierDetector initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        detector = OutlierDetector()
        assert detector.methods == ["iqr", "zscore"]
        assert detector.iqr_multiplier == 1.5
        assert detector.zscore_threshold == 3.0
        assert detector.modified_zscore_threshold == 3.5
        assert detector.alert_threshold_pct == 10.0
        assert detector.max_sample_values == 20

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        detector = OutlierDetector(
            methods=["iqr", "zscore", "modified_zscore"],
            iqr_multiplier=3.0,
            zscore_threshold=2.5,
            modified_zscore_threshold=3.0,
            alert_threshold_pct=5.0,
            max_sample_values=10,
        )
        assert detector.methods == ["iqr", "zscore", "modified_zscore"]
        assert detector.iqr_multiplier == 3.0
        assert detector.zscore_threshold == 2.5
        assert detector.modified_zscore_threshold == 3.0
        assert detector.alert_threshold_pct == 5.0
        assert detector.max_sample_values == 10

    def test_init_invalid_method(self):
        """Test that invalid method names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid method 'invalid'"):
            OutlierDetector(methods=["iqr", "invalid"])

    def test_init_single_method(self):
        """Test initialization with a single method."""
        detector = OutlierDetector(methods=["iqr"])
        assert detector.methods == ["iqr"]


class TestOutlierDetectorDetect:
    """Tests for OutlierDetector.detect() method."""

    @pytest.fixture
    def normal_series(self):
        """Create a series with no significant outliers."""
        np.random.seed(42)
        return pd.Series(np.random.normal(100, 15, 1000))

    @pytest.fixture
    def outlier_series(self):
        """Create a series with known outliers."""
        np.random.seed(42)
        normal = np.random.normal(100, 15, 900)
        outliers = np.array([500, -300, 600, -400, 550])
        return pd.Series(np.concatenate([normal, outliers]))

    @pytest.fixture
    def constant_series(self):
        """Create a series with all identical values (edge case)."""
        return pd.Series([100] * 100)

    @pytest.fixture
    def nan_series(self):
        """Create a series with NaN values."""
        np.random.seed(42)
        values = np.random.normal(100, 15, 100)
        values[[5, 10, 15]] = np.nan
        return pd.Series(values)

    def test_detect_normal_series_iqr(self, normal_series):
        """Test IQR detection on normal series - should find minimal outliers."""
        detector = OutlierDetector(methods=["iqr"])
        results = detector.detect(normal_series)

        assert "iqr" in results
        assert results["iqr"]["method"] == "iqr"
        assert results["iqr"]["outlier_count"] < 50  # Less than 5%
        assert results["iqr"]["outlier_pct"] < 5.0
        assert isinstance(results["iqr"]["sample_values"], list)

    def test_detect_outlier_series_iqr(self, outlier_series):
        """Test IQR detection on series with outliers."""
        detector = OutlierDetector(methods=["iqr"], iqr_multiplier=1.5)
        results = detector.detect(outlier_series)

        assert "iqr" in results
        assert results["iqr"]["outlier_count"] >= 5  # At least our 5 outliers
        assert results["iqr"]["outlier_pct"] > 0.5  # At least 0.5%
        assert "fences" in results["iqr"]
        assert "lower" in results["iqr"]["fences"]
        assert "upper" in results["iqr"]["fences"]

    def test_detect_zscore_normal_series(self, normal_series):
        """Test z-score detection on normal series."""
        detector = OutlierDetector(methods=["zscore"], zscore_threshold=3.0)
        results = detector.detect(normal_series)

        assert "zscore" in results
        assert results["zscore"]["method"] == "zscore"
        assert results["zscore"]["outlier_count"] < 30  # Less than 3%
        assert "mean" in results["zscore"]
        assert "std" in results["zscore"]
        assert "threshold" in results["zscore"]
        assert results["zscore"]["threshold"] == 3.0

    def test_detect_zscore_constant_series(self, constant_series):
        """Test z-score detection on constant series (std=0 edge case)."""
        detector = OutlierDetector(methods=["zscore"])
        results = detector.detect(constant_series)

        assert "zscore" in results
        assert results["zscore"]["outlier_count"] == 0  # No outliers when std=0
        assert results["zscore"]["std"] == 0.0

    def test_detect_modified_zscore_normal_series(self, normal_series):
        """Test modified z-score (MAD-based) detection on normal series."""
        detector = OutlierDetector(methods=["modified_zscore"])
        results = detector.detect(normal_series)

        assert "modified_zscore" in results
        assert results["modified_zscore"]["method"] == "modified_zscore"
        assert results["modified_zscore"]["outlier_count"] < 50
        assert "median" in results["modified_zscore"]
        assert "mad" in results["modified_zscore"]

    def test_detect_modified_zscore_constant_series(self, constant_series):
        """Test modified z-score on constant series (MAD=0 edge case)."""
        detector = OutlierDetector(methods=["modified_zscore"])
        results = detector.detect(constant_series)

        assert "modified_zscore" in results
        assert results["modified_zscore"]["outlier_count"] == 0  # No outliers when MAD=0
        assert results["modified_zscore"]["mad"] == 0.0

    def test_detect_nan_series(self, nan_series):
        """Test that NaN values are properly handled."""
        detector = OutlierDetector(methods=["iqr"])
        results = detector.detect(nan_series)

        assert "iqr" in results
        # Results should be based on non-NaN values only
        assert results["iqr"]["outlier_count"] >= 0

    def test_detect_empty_series(self):
        """Test detection on empty series (all NaN)."""
        detector = OutlierDetector(methods=["iqr"])
        empty_series = pd.Series([np.nan, np.nan, np.nan])
        results = detector.detect(empty_series)

        assert results == {}  # Empty result for empty series

    def test_detect_multiple_methods(self, outlier_series):
        """Test running multiple methods simultaneously."""
        detector = OutlierDetector(methods=["iqr", "zscore", "modified_zscore"])
        results = detector.detect(outlier_series)

        assert "iqr" in results
        assert "zscore" in results
        assert "modified_zscore" in results
        # Each method should have the required keys
        for method in results:
            assert "outlier_count" in results[method]
            assert "outlier_pct" in results[method]
            assert "sample_values" in results[method]
            assert "has_alert" in results[method]


class TestOutlierDetectorAlerts:
    """Tests for alert threshold functionality."""

    def test_alert_threshold_not_triggered(self):
        """Test that alert is not triggered when outlier % < threshold."""
        np.random.seed(42)
        series = pd.Series(np.random.normal(100, 15, 1000))
        detector = OutlierDetector(methods=["iqr"], alert_threshold_pct=10.0)
        results = detector.detect(series)

        assert results["iqr"]["has_alert"] is False

    def test_alert_threshold_triggered(self):
        """Test that alert is triggered when outlier % >= threshold."""
        np.random.seed(42)
        normal = np.random.normal(100, 15, 850)
        # Add 15% outliers
        outliers = np.random.uniform(500, 1000, 150)
        series = pd.Series(np.concatenate([normal, outliers]))

        detector = OutlierDetector(methods=["iqr"], alert_threshold_pct=10.0)
        results = detector.detect(series)

        assert results["iqr"]["outlier_pct"] >= 10.0
        assert results["iqr"]["has_alert"] is True


class TestOutlierDetectorSampleValues:
    """Tests for sample values limiting functionality."""

    def test_sample_values_limit_respected(self):
        """Test that sample values are limited to max_sample_values."""
        np.random.seed(42)
        normal = np.random.normal(100, 15, 900)
        outliers = np.random.uniform(500, 1000, 100)
        series = pd.Series(np.concatenate([normal, outliers]))

        detector = OutlierDetector(methods=["iqr"], max_sample_values=20)
        results = detector.detect(series)

        assert len(results["iqr"]["sample_values"]) <= 20

    def test_sample_values_content(self):
        """Test that sample values contain actual outlier values."""
        np.random.seed(42)
        # Use a larger dataset where outliers are clearly distinct
        normal = np.random.normal(100, 15, 100)
        outliers = np.array([500, 600, 700])
        series = pd.Series(np.concatenate([normal, outliers]))

        detector = OutlierDetector(methods=["iqr"], iqr_multiplier=1.5)
        results = detector.detect(series)

        # Should include the high outliers
        assert any(v > 300 for v in results["iqr"]["sample_values"])

    def test_sample_values_empty_when_no_outliers(self):
        """Test that sample_values is empty when no outliers are found."""
        detector = OutlierDetector(methods=["iqr"])
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        results = detector.detect(series)

        assert results["iqr"]["sample_values"] == []

    def test_custom_max_sample_values(self):
        """Test custom max_sample_values parameter."""
        np.random.seed(42)
        normal = np.random.normal(100, 15, 900)
        outliers = np.random.uniform(500, 1000, 100)
        series = pd.Series(np.concatenate([normal, outliers]))

        detector = OutlierDetector(methods=["iqr"], max_sample_values=5)
        results = detector.detect(series)

        assert len(results["iqr"]["sample_values"]) <= 5


class TestOutlierDetectorIQRDetails:
    """Tests for IQR method-specific details."""

    def test_iqr_multiplier_effect(self):
        """Test that larger iqr_multiplier detects fewer outliers."""
        np.random.seed(42)
        series = pd.Series(
            np.concatenate([np.random.normal(100, 15, 900), np.random.uniform(200, 300, 100)])
        )

        detector_1_5 = OutlierDetector(methods=["iqr"], iqr_multiplier=1.5)
        detector_3_0 = OutlierDetector(methods=["iqr"], iqr_multiplier=3.0)

        results_1_5 = detector_1_5.detect(series)
        results_3_0 = detector_3_0.detect(series)

        # More restrictive multiplier (3.0) should detect fewer outliers
        assert results_3_0["iqr"]["outlier_count"] <= results_1_5["iqr"]["outlier_count"]

    def test_iqr_fences_symmetric(self):
        """Test that IQR fences are symmetric around the IQR range."""
        np.random.seed(42)
        series = pd.Series(np.random.normal(100, 15, 1000))

        detector = OutlierDetector(methods=["iqr"])
        results = detector.detect(series)

        q1 = np.percentile(series, 25)
        q3 = np.percentile(series, 75)
        iqr = q3 - q1

        assert results["iqr"]["fences"]["lower"] == pytest.approx(q1 - 1.5 * iqr)
        assert results["iqr"]["fences"]["upper"] == pytest.approx(q3 + 1.5 * iqr)


class TestOutlierDetectorIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow(self):
        """Test complete workflow with realistic consumption data."""
        np.random.seed(42)

        # Simulate consumption data with some anomalies
        normal_consumption = np.random.uniform(100, 500, 950)
        anomalies = np.array([2000, 50, 2500, 10, 1800, 30, 2200])

        series = pd.Series(np.concatenate([normal_consumption, anomalies]))

        detector = OutlierDetector(
            methods=["iqr", "zscore", "modified_zscore"],
            iqr_multiplier=1.5,
            zscore_threshold=3.0,
            alert_threshold_pct=5.0,
            max_sample_values=20,
        )

        results = detector.detect(series)

        # Verify all methods returned results
        assert len(results) == 3

        # Verify IQR found outliers
        assert results["iqr"]["outlier_count"] > 0
        assert "fences" in results["iqr"]

        # Verify z-score found outliers
        assert results["zscore"]["outlier_count"] > 0
        assert "mean" in results["zscore"]
        assert "std" in results["zscore"]

        # Verify modified z-score found outliers
        assert results["modified_zscore"]["outlier_count"] > 0
        assert "median" in results["modified_zscore"]
        assert "mad" in results["modified_zscore"]

        # Verify sample values are limited
        for method in results:
            assert len(results[method]["sample_values"]) <= 20

        # Verify alert threshold is respected
        for method in results:
            has_alert = results[method]["outlier_pct"] >= 5.0
            assert results[method]["has_alert"] == has_alert
