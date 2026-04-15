"""
Unit tests for PopulationAnalyzer class in EDA module.

Tests cover:
- Initialization with default and custom parameters
- Invalid parameter validation
- Single population detection (no significant jumps)
- Multiple population detection (with significant jumps)
- Edge cases: constant series, NaN series, empty series
- Jump detection between percentiles
- Interpretation with and without target variable
- max_populations and min_population_pct limits
"""

import numpy as np
import pandas as pd
import pytest

from energizados.eda._population_segmenter import PopulationAnalyzer


class TestPopulationAnalyzerInit:
    """Tests for PopulationAnalyzer initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        analyzer = PopulationAnalyzer()
        assert analyzer.percentile_step == 0.5
        assert analyzer.jump_ratio_threshold == 5.0
        assert analyzer.max_populations == 5
        assert analyzer.min_population_pct == 0.5

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        analyzer = PopulationAnalyzer(
            percentile_step=1.0,
            jump_ratio_threshold=10.0,
            max_populations=3,
            min_population_pct=1.0,
        )
        assert analyzer.percentile_step == 1.0
        assert analyzer.jump_ratio_threshold == 10.0
        assert analyzer.max_populations == 3
        assert analyzer.min_population_pct == 1.0

    def test_init_invalid_percentile_step_low(self):
        """Test that percentile_step < 0.1 raises ValueError."""
        with pytest.raises(ValueError, match="percentile_step must be between 0.1 and 1.0"):
            PopulationAnalyzer(percentile_step=0.05)

    def test_init_invalid_percentile_step_high(self):
        """Test that percentile_step > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="percentile_step must be between 0.1 and 1.0"):
            PopulationAnalyzer(percentile_step=1.5)

    def test_init_invalid_jump_ratio_threshold_low(self):
        """Test that jump_ratio_threshold < 2.0 raises ValueError."""
        with pytest.raises(ValueError, match="jump_ratio_threshold must be at least 2.0"):
            PopulationAnalyzer(jump_ratio_threshold=1.5)

    def test_init_invalid_max_populations_low(self):
        """Test that max_populations < 2 raises ValueError."""
        with pytest.raises(ValueError, match="max_populations must be between 2 and 10"):
            PopulationAnalyzer(max_populations=1)

    def test_init_invalid_max_populations_high(self):
        """Test that max_populations > 10 raises ValueError."""
        with pytest.raises(ValueError, match="max_populations must be between 2 and 10"):
            PopulationAnalyzer(max_populations=11)

    def test_init_invalid_min_population_pct_low(self):
        """Test that min_population_pct < 0.1 raises ValueError."""
        with pytest.raises(ValueError, match="min_population_pct must be between 0.1 and 10.0"):
            PopulationAnalyzer(min_population_pct=0.05)

    def test_init_invalid_min_population_pct_high(self):
        """Test that min_population_pct > 10.0 raises ValueError."""
        with pytest.raises(ValueError, match="min_population_pct must be between 0.1 and 10.0"):
            PopulationAnalyzer(min_population_pct=15.0)


class TestPopulationAnalyzerAnalyze:
    """Tests for PopulationAnalyzer.analyze() method."""

    @pytest.fixture
    def normal_series(self):
        """Create a series with no significant jumps (single population)."""
        np.random.seed(42)
        return pd.Series(np.random.normal(100, 15, 1000))

    @pytest.fixture
    def multi_population_series(self):
        """Create a series with three distinct populations."""
        np.random.seed(42)
        # Population 1: 0-1000, normal around 50 (80% of data)
        pop1 = np.random.normal(50, 10, 800)
        # Population 2: 1000-1100, normal around 5000 (15% of data)
        pop2 = np.random.normal(5000, 500, 150)
        # Population 3: 1100-1150, extreme outliers (5% of data)
        pop3 = np.random.uniform(100000, 1000000, 50)
        return pd.Series(np.concatenate([pop1, pop2, pop3]))

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

    @pytest.fixture
    def empty_series(self):
        """Create an empty series."""
        return pd.Series([], dtype=float)

    @pytest.fixture
    def target_series(self):
        """Create a binary target series for interpretation tests."""
        np.random.seed(42)
        return pd.Series(np.random.choice([0, 1], size=1000, p=[0.95, 0.05]))

    def test_analyze_normal_series_single_population(self, normal_series):
        """Test that a normal distribution is detected as single population."""
        analyzer = PopulationAnalyzer(jump_ratio_threshold=5.0)
        results = analyzer.analyze(normal_series)

        assert results["has_multiple_populations"] is False
        assert len(results["populations"]) == 1
        assert results["populations"][0]["percentile_range"] == "P0–P100"
        assert results["populations"][0]["pct_rows"] == 100.0

    def test_analyze_multi_population_series(self, multi_population_series):
        """Test that multiple populations are detected when jumps exist."""
        analyzer = PopulationAnalyzer(jump_ratio_threshold=5.0)
        results = analyzer.analyze(multi_population_series)

        assert results["has_multiple_populations"] is True
        assert len(results["populations"]) > 1
        assert len(results["jumps"]) > 0

        # Check that populations have correct structure
        for pop in results["populations"]:
            assert "range" in pop
            assert "percentile_range" in pop
            assert "row_count" in pop
            assert "pct_rows" in pop
            assert "interpretation" in pop

    def test_analyze_with_target(self, multi_population_series, target_series):
        """Test that target rate is included when target is provided."""
        analyzer = PopulationAnalyzer(jump_ratio_threshold=5.0)
        results = analyzer.analyze(multi_population_series, target=target_series)

        # Check that interpretations include target rate (look for "target rate" substring)
        interpretations = [pop["interpretation"] for pop in results["populations"]]
        for interp in interpretations:
            assert "target rate" in interp.lower()

    def test_analyze_without_target(self, multi_population_series):
        """Test that interpretation works without target."""
        analyzer = PopulationAnalyzer(jump_ratio_threshold=5.0)
        results = analyzer.analyze(multi_population_series)

        assert len(results["populations"]) > 0
        # Interpretations should not reference target
        for pop in results["populations"]:
            assert "Target rate:" not in pop["interpretation"]

    def test_analyze_constant_series(self, constant_series):
        """Test analysis of constant series (no variation)."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(constant_series)

        # Constant series should have single population
        assert results["has_multiple_populations"] is False
        assert len(results["populations"]) == 1

    def test_analyze_nan_series(self, nan_series):
        """Test that NaN values are handled correctly."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(nan_series)

        # Should analyze non-NaN values only
        assert len(results["populations"]) > 0

    def test_analyze_empty_series(self, empty_series):
        """Test that empty series returns empty results."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(empty_series)

        assert results["has_multiple_populations"] is False
        assert len(results["populations"]) == 0
        assert len(results["jumps"]) == 0

    def test_analyze_high_jump_threshold(self, multi_population_series):
        """Test that high jump_threshold detects fewer populations."""
        analyzer_low = PopulationAnalyzer(jump_ratio_threshold=3.0)
        analyzer_high = PopulationAnalyzer(jump_ratio_threshold=20.0)

        results_low = analyzer_low.analyze(multi_population_series)
        results_high = analyzer_high.analyze(multi_population_series)

        # Higher threshold should detect fewer or equal populations
        assert len(results_low["populations"]) >= len(results_high["populations"])

    def test_max_populations_limit(self, multi_population_series):
        """Test that max_populations parameter is respected."""
        analyzer = PopulationAnalyzer(max_populations=3, jump_ratio_threshold=2.0)
        results = analyzer.analyze(multi_population_series)

        assert len(results["populations"]) <= 3

    def test_min_population_pct_filtering(self, multi_population_series):
        """Test that tiny populations are filtered out."""
        analyzer = PopulationAnalyzer(min_population_pct=5.0)
        results = analyzer.analyze(multi_population_series)

        # All populations should have at least min_population_pct
        for pop in results["populations"]:
            assert pop["pct_rows"] >= 5.0

    def test_jump_detection_structure(self, multi_population_series):
        """Test that detected jumps have correct structure."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_population_series)

        for jump in results["jumps"]:
            assert "from_percentile" in jump
            assert "to_percentile" in jump
            assert "from_value" in jump
            assert "to_value" in jump
            assert "ratio" in jump

            # Check that ratio is at least threshold
            assert jump["ratio"] >= analyzer.jump_ratio_threshold

            # Check that percentiles are ordered
            assert jump["from_percentile"] < jump["to_percentile"]

    def test_jumps_sorted_by_ratio(self, multi_population_series):
        """Test that jumps are sorted by ratio in descending order."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_population_series)

        if len(results["jumps"]) > 1:
            ratios = [jump["ratio"] for jump in results["jumps"]]
            assert ratios == sorted(ratios, reverse=True)

    def test_percentiles_dict_structure(self, multi_population_series):
        """Test that percentiles dict has correct structure."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_population_series)

        percentiles = results["percentiles"]
        assert isinstance(percentiles, dict)

        # Check that keys are percentiles (0-100)
        for p in percentiles.keys():
            assert 0 <= p <= 100

        # Check that values are numbers
        for v in percentiles.values():
            assert isinstance(v, (int, float))

    def test_population_ranges_contiguous(self, multi_population_series):
        """Test that population ranges are contiguous."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_population_series)

        populations = results["populations"]
        if len(populations) > 1:
            # Check that population percentile ranges are contiguous
            for i in range(len(populations) - 1):
                curr_max = populations[i]["range"][1]
                next_min = populations[i + 1]["range"][0]
                # Allow small gap due to rounding
                assert abs(curr_max - next_min) < 1.0

    def test_population_pct_rows_sum_to_100(self, multi_population_series):
        """Test that population row percentages sum to approximately 100%."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_population_series)

        populations = results["populations"]
        total_pct = sum(pop["pct_rows"] for pop in populations)

        # Should sum to approximately 100% (allow 1% tolerance)
        assert 99.0 <= total_pct <= 101.0


class TestPopulationAnalyzerInterpretation:
    """Tests for population interpretation logic."""

    @pytest.fixture
    def multi_pop_series(self):
        """Create a series with two populations."""
        np.random.seed(42)
        pop1 = np.random.normal(100, 10, 800)
        pop2 = np.random.normal(10000, 500, 200)
        return pd.Series(np.concatenate([pop1, pop2]))

    @pytest.fixture
    def high_target_series(self, n=1000):
        """Create a target series with high target rate for first 800 rows."""
        target = np.zeros(n)
        target[:800] = np.random.choice([0, 1], 800, p=[0.7, 0.3])  # 30% target rate
        target[800:] = np.random.choice([0, 1], 200, p=[0.99, 0.01])  # 1% target rate
        return pd.Series(target)

    def test_lower_tail_interpretation(self, multi_pop_series):
        """Test that lower population is interpreted correctly."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_pop_series)

        # First population should be "Lower tail"
        assert "Lower tail" in results["populations"][0]["interpretation"]

    def test_upper_tail_interpretation(self, multi_pop_series):
        """Test that upper population is interpreted correctly."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_pop_series)

        # Last population should be "Upper tail"
        last_interp = results["populations"][-1]["interpretation"]
        assert "Upper tail" in last_interp

    def test_high_target_rate_interpretation(self, multi_pop_series, high_target_series):
        """Test that high target rates are reflected in interpretation."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_pop_series, target=high_target_series)

        # First population should have higher target rate mentioned
        first_interp = results["populations"][0]["interpretation"]
        assert "High target rate" in first_interp or "30%" in first_interp

    def test_low_target_rate_interpretation(self, multi_pop_series, high_target_series):
        """Test that low target rates are reflected in interpretation."""
        analyzer = PopulationAnalyzer()
        results = analyzer.analyze(multi_pop_series, target=high_target_series)

        # Last population should have lower target rate mentioned
        last_interp = results["populations"][-1]["interpretation"]
        # Might say "Low target rate" or show the percentage
        assert "Low target rate" in last_interp or "1%" in last_interp
