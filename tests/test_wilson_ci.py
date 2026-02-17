"""
Tests for Wilson score confidence interval (used in FPR estimation).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import FalsePositiveFramework


class TestWilsonCI:
    """Wilson score interval for proportions."""

    @pytest.fixture
    def fpf(self, temp_db):
        return FalsePositiveFramework(temp_db)

    def test_zero_successes(self, fpf):
        """0/100 should give CI near [0, ~0.04]."""
        lower, upper = fpf._wilson_ci(0, 100)
        assert lower == 0
        assert 0 < upper < 0.10

    def test_all_successes(self, fpf):
        """100/100 should give CI near [0.96, 1]."""
        lower, upper = fpf._wilson_ci(100, 100)
        assert 0.90 < lower <= 1.0
        assert upper == pytest.approx(1.0, abs=1e-10)

    def test_half_successes(self, fpf):
        """50/100 should center around 0.50."""
        lower, upper = fpf._wilson_ci(50, 100)
        assert 0.35 < lower < 0.50
        assert 0.50 < upper < 0.65

    def test_zero_n(self, fpf):
        lower, upper = fpf._wilson_ci(0, 0)
        assert lower == 0
        assert upper == 1

    def test_ci_contains_proportion(self, fpf):
        """CI should contain the observed proportion."""
        for k in [0, 5, 25, 50, 75, 95, 100]:
            lower, upper = fpf._wilson_ci(k, 100)
            p = k / 100
            assert lower <= p + 1e-10 and upper >= p - 1e-10

    def test_larger_n_narrower_ci(self, fpf):
        """Larger sample should give narrower CI."""
        l_small, u_small = fpf._wilson_ci(5, 50)
        l_large, u_large = fpf._wilson_ci(10, 100)
        assert (u_large - l_large) <= (u_small - l_small) + 0.01
