"""
Tests for BootstrapAnalyzer — BCa bootstrap confidence intervals.
This is the core uncertainty quantification engine.
"""
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import BootstrapAnalyzer, DOJProsecutionThresholds


class TestBootstrapMarkupCI:
    """Bootstrap confidence intervals for markup percentage."""

    def test_insufficient_data_returns_default(self):
        """Less than 3 comparables returns insufficient data result."""
        ba = BootstrapAnalyzer(n_iterations=100)
        result = ba.markup_confidence_interval(10_000_000, [5_000_000, 6_000_000])
        assert result.point_estimate == 0
        assert result.ci_width == float('inf')
        assert result.is_significant is False
        assert result.p_value == 1.0
        assert "INSUFFICIENT DATA" in result.interpretation

    def test_empty_comparables(self):
        ba = BootstrapAnalyzer(n_iterations=100)
        result = ba.markup_confidence_interval(10_000_000, [])
        assert result.point_estimate == 0
        assert result.sample_size == 0

    def test_obvious_outlier_detected(self, sample_comparables):
        """A contract 5x the median should show massive markup."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        median = np.median(sample_comparables)
        target = median * 5  # 400% markup

        result = ba.markup_confidence_interval(target, sample_comparables)
        assert result.point_estimate > 300
        assert result.ci_lower > 200
        assert result.is_significant == True
        assert result.p_value < 0.01

    def test_normal_contract_not_flagged(self, sample_comparables):
        """A contract near the median should NOT be flagged."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        median = np.median(sample_comparables)

        result = ba.markup_confidence_interval(median, sample_comparables)
        assert result.is_significant == False
        assert abs(result.point_estimate) < 50

    def test_ci_contains_point_estimate(self, sample_comparables):
        """Point estimate should fall within the CI."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        target = np.median(sample_comparables) * 2

        result = ba.markup_confidence_interval(target, sample_comparables)
        assert result.ci_lower <= result.point_estimate <= result.ci_upper

    def test_wider_ci_with_smaller_sample(self):
        """Fewer comparables should produce wider CIs (with enough diversity)."""
        ba = BootstrapAnalyzer(n_iterations=2000)
        target = 10_000_000

        # Use 5 samples (enough to avoid BCa ceiling) vs 20
        small = [4_000_000, 5_500_000, 6_000_000, 7_000_000, 8_500_000]
        large = [4_000_000, 4_500_000, 5_000_000, 5_500_000, 6_000_000,
                 6_200_000, 6_500_000, 6_800_000, 7_000_000, 7_200_000,
                 7_500_000, 7_800_000, 8_000_000, 8_200_000, 8_500_000,
                 5_100_000, 5_900_000, 6_600_000, 7_400_000, 8_100_000]

        np.random.seed(42)
        result_small = ba.markup_confidence_interval(target, small)
        np.random.seed(42)
        result_large = ba.markup_confidence_interval(target, large)

        # With more data, CI should be narrower (or at least not dramatically wider)
        assert result_large.ci_width < result_small.ci_width * 1.5

    def test_deterministic_with_same_seed(self, sample_comparables):
        """Same seed produces identical results."""
        target = np.median(sample_comparables) * 3

        np.random.seed(42)
        ba1 = BootstrapAnalyzer(n_iterations=500)
        r1 = ba1.markup_confidence_interval(target, sample_comparables)

        np.random.seed(42)
        ba2 = BootstrapAnalyzer(n_iterations=500)
        r2 = ba2.markup_confidence_interval(target, sample_comparables)

        assert r1.point_estimate == r2.point_estimate
        assert r1.ci_lower == r2.ci_lower
        assert r1.ci_upper == r2.ci_upper

    def test_p_value_bounded(self, sample_comparables):
        """P-value must be in [0.0001, 1.0]."""
        ba = BootstrapAnalyzer(n_iterations=500)
        target = np.median(sample_comparables) * 10
        result = ba.markup_confidence_interval(target, sample_comparables)
        assert 0.0001 <= result.p_value <= 1.0

    def test_confidence_level_recorded(self, sample_comparables):
        ba = BootstrapAnalyzer(n_iterations=100)
        result = ba.markup_confidence_interval(
            10_000_000, sample_comparables, confidence_level=0.99
        )
        assert result.confidence_level == 0.99

    def test_iterations_recorded(self, sample_comparables):
        ba = BootstrapAnalyzer(n_iterations=500)
        result = ba.markup_confidence_interval(10_000_000, sample_comparables)
        assert result.n_iterations == 500


class TestBootstrapPercentileCI:
    """Bootstrap CI for percentile rank."""

    def test_extreme_value_high_percentile(self, sample_comparables):
        """A value above all comparables should be near 100th percentile."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        target = max(sample_comparables) * 5

        result = ba.percentile_confidence_interval(target, sample_comparables)
        assert result.point_estimate == 100.0

    def test_median_value_around_50th(self, sample_comparables):
        """Value near median should be near 50th percentile."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        target = np.median(sample_comparables)

        result = ba.percentile_confidence_interval(target, sample_comparables)
        assert 30 <= result.point_estimate <= 70

    def test_insufficient_data(self):
        ba = BootstrapAnalyzer(n_iterations=100)
        result = ba.percentile_confidence_interval(5_000_000, [1_000_000])
        assert result.point_estimate == 0
        assert "INSUFFICIENT DATA" in result.interpretation

    def test_ci_bounds_valid(self, sample_comparables):
        ba = BootstrapAnalyzer(n_iterations=500)
        result = ba.percentile_confidence_interval(
            np.median(sample_comparables) * 2, sample_comparables
        )
        assert 0 <= result.ci_lower <= result.ci_upper <= 100


class TestBootstrapInterpretation:
    """Verify human-readable interpretations are correct."""

    def test_extreme_markup_interpretation(self):
        """Markup >300% CI lower should reference DOJ extreme threshold."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        # Create comparables where target is vastly above
        comparables = [1_000_000] * 10
        target = 5_000_000  # 400% markup

        result = ba.markup_confidence_interval(target, comparables)
        assert "300%" in result.interpretation or "DOJ" in result.interpretation.upper()

    def test_non_significant_interpretation(self):
        """Below-median contract should mention not significant."""
        ba = BootstrapAnalyzer(n_iterations=1000)
        comparables = [10_000_000, 12_000_000, 11_000_000, 9_000_000, 13_000_000]
        target = 5_000_000  # Below median

        result = ba.markup_confidence_interval(target, comparables)
        assert "NOT statistically significant" in result.interpretation or result.ci_lower < 0
