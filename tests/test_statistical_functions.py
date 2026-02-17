"""
Tests for pure numpy statistical functions (norm_ppf, norm_cdf, percentileofscore).
These replace scipy and must be accurate to support prosecution-grade analysis.
"""
import math
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import norm_ppf, norm_cdf, percentileofscore


class TestNormPPF:
    """Inverse standard normal CDF (Abramowitz-Stegun approximation)."""

    def test_median_returns_zero(self):
        assert norm_ppf(0.5) == 0.0

    def test_symmetry(self):
        """norm_ppf(p) == -norm_ppf(1-p)"""
        for p in [0.01, 0.05, 0.10, 0.25, 0.40]:
            assert abs(norm_ppf(p) + norm_ppf(1 - p)) < 1e-6

    def test_known_quantiles(self):
        """Check against well-known z-values."""
        # z_0.025 ≈ -1.96, z_0.975 ≈ 1.96
        assert abs(norm_ppf(0.025) - (-1.96)) < 0.01
        assert abs(norm_ppf(0.975) - 1.96) < 0.01
        # z_0.05 ≈ -1.645
        assert abs(norm_ppf(0.05) - (-1.645)) < 0.01
        # z_0.01 ≈ -2.326
        assert abs(norm_ppf(0.01) - (-2.326)) < 0.01

    def test_extreme_tails(self):
        """Boundary behavior at 0 and 1."""
        assert norm_ppf(0) == float('-inf')
        assert norm_ppf(1) == float('inf')

    def test_monotonically_increasing(self):
        """PPF must be strictly increasing."""
        probs = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
        values = [norm_ppf(p) for p in probs]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]

    def test_roundtrip_with_cdf(self):
        """norm_cdf(norm_ppf(p)) ≈ p."""
        for p in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
            assert abs(norm_cdf(norm_ppf(p)) - p) < 0.005


class TestNormCDF:
    """Standard normal CDF (error function approximation)."""

    def test_at_zero(self):
        assert abs(norm_cdf(0) - 0.5) < 1e-6

    def test_symmetry(self):
        """CDF(x) + CDF(-x) = 1"""
        for x in [0.5, 1.0, 1.96, 2.5, 3.0]:
            assert abs(norm_cdf(x) + norm_cdf(-x) - 1.0) < 1e-6

    def test_known_values(self):
        """Standard normal CDF at common z-scores."""
        assert abs(norm_cdf(1.96) - 0.975) < 0.005
        assert abs(norm_cdf(-1.96) - 0.025) < 0.005
        assert abs(norm_cdf(1.0) - 0.8413) < 0.005
        assert abs(norm_cdf(2.0) - 0.9772) < 0.005
        assert abs(norm_cdf(3.0) - 0.9987) < 0.005

    def test_monotonically_increasing(self):
        zscores = [-3, -2, -1, 0, 1, 2, 3]
        values = [norm_cdf(z) for z in zscores]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]

    def test_approaches_bounds(self):
        """CDF approaches 0 for large negative, 1 for large positive."""
        assert norm_cdf(-5) < 0.001
        assert norm_cdf(5) > 0.999


class TestPercentileOfScore:
    """Percentile rank computation."""

    def test_minimum_value(self):
        data = np.array([1, 2, 3, 4, 5])
        assert percentileofscore(data, 1) == 20.0

    def test_maximum_value(self):
        data = np.array([1, 2, 3, 4, 5])
        assert percentileofscore(data, 5) == 100.0

    def test_below_all(self):
        data = np.array([10, 20, 30])
        assert percentileofscore(data, 1) == 0.0

    def test_above_all(self):
        data = np.array([10, 20, 30])
        assert percentileofscore(data, 100) == 100.0

    def test_empty_data(self):
        data = np.array([])
        assert percentileofscore(data, 5) == 0.0

    def test_median_of_odd(self):
        data = np.array([1, 2, 3, 4, 5])
        # 3 is at 60th percentile (3 out of 5 values <= 3)
        assert percentileofscore(data, 3) == 60.0
