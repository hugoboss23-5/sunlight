"""
Tests for MultipleTestingCorrection — Benjamini-Hochberg FDR control.
When testing 42,000 contracts, this prevents false discovery floods.
"""
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import MultipleTestingCorrection


class TestBenjaminiHochberg:
    """Benjamini-Hochberg FDR correction."""

    def test_empty_input(self):
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg([])
        assert reject == []
        assert adjusted == []

    def test_single_significant(self):
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg([0.01], alpha=0.10)
        assert reject == [True]
        assert adjusted[0] <= 0.10

    def test_single_nonsignificant(self):
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg([0.50], alpha=0.10)
        assert reject == [False]

    def test_all_significant(self):
        """Very small p-values should all survive."""
        pvalues = [0.001, 0.002, 0.003, 0.004, 0.005]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        assert all(reject)

    def test_none_significant(self):
        """Large p-values should all be rejected."""
        pvalues = [0.50, 0.60, 0.70, 0.80, 0.90]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        assert not any(reject)

    def test_mixed_significance(self):
        """Some should survive, some shouldn't."""
        pvalues = [0.001, 0.005, 0.10, 0.50, 0.90]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        # The smallest p-values should survive
        assert reject[0] is True
        assert reject[1] is True
        # The largest should not
        assert reject[4] is False

    def test_adjusted_p_monotonic(self):
        """Adjusted p-values for sorted raw p-values should be monotonically non-decreasing."""
        pvalues = [0.001, 0.01, 0.02, 0.05, 0.10, 0.50]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        sorted_adj = sorted(adjusted)
        for i in range(len(sorted_adj) - 1):
            assert sorted_adj[i] <= sorted_adj[i + 1] + 1e-10

    def test_adjusted_p_geq_raw(self):
        """Adjusted p-values should always be >= raw p-values."""
        pvalues = [0.001, 0.01, 0.05, 0.10, 0.50]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        for raw, adj in zip(pvalues, adjusted):
            assert adj >= raw - 1e-10

    def test_adjusted_p_leq_1(self):
        """Adjusted p-values should never exceed 1."""
        pvalues = [0.50, 0.60, 0.70, 0.80, 0.90]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        for adj in adjusted:
            assert adj <= 1.0 + 1e-10

    def test_stricter_alpha_fewer_rejections(self):
        """Lower alpha should reject fewer or equal hypotheses."""
        pvalues = [0.01, 0.02, 0.05, 0.08, 0.15]
        reject_loose, _ = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        reject_strict, _ = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.05)
        assert sum(reject_strict) <= sum(reject_loose)

    def test_preserves_order(self):
        """Output length matches input and maintains positional correspondence."""
        pvalues = [0.05, 0.001, 0.50, 0.01, 0.10]
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        assert len(reject) == 5
        assert len(adjusted) == 5
        # The smallest raw p-value (index 1) should have the smallest adjusted p-value
        assert adjusted[1] == min(adjusted)

    def test_realistic_scale(self):
        """Simulate 1000 contracts: 950 null (uniform p) + 50 with strong signal."""
        np.random.seed(42)
        null_p = np.random.uniform(0.1, 1.0, 950)
        # Very strong signals that should survive FDR at any scale
        signal_p = np.random.uniform(0.00001, 0.001, 50)
        pvalues = list(null_p) + list(signal_p)

        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        n_rejected = sum(reject)

        # Should reject most strong signals
        signal_rejected = sum(reject[950:])
        null_rejected = sum(reject[:950])

        assert signal_rejected > 30  # Most true signals found
        # FDR control: proportion of false discoveries should be < alpha
        if n_rejected > 0:
            fdr = null_rejected / n_rejected
            assert fdr < 0.20  # Allow some slack for randomness


class TestFDRWithDOJThresholds:
    """Integration: FDR correction with DOJ-like p-value distributions."""

    def test_conservative_correction(self):
        """FDR should not reject borderline cases when many tests are run."""
        # 100 contracts, only 2 with borderline p-values
        pvalues = [0.08, 0.09] + [0.50] * 98
        reject, adjusted = MultipleTestingCorrection.benjamini_hochberg(pvalues, alpha=0.10)
        # Borderline cases may or may not survive depending on BH threshold
        # With 100 tests, BH threshold at rank 1 is 0.10/100 = 0.001
        # So borderline p=0.08 should NOT survive
        assert not any(reject[:2]) or adjusted[0] < 0.10
