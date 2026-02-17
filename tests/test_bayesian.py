"""
Tests for BayesianFraudPrior — DOJ-calibrated Bayesian probability estimation.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import BayesianFraudPrior


class TestBaseRates:
    """Verify DOJ-calibrated base rates are correct."""

    def test_overall_base_rate(self):
        assert BayesianFraudPrior.BASE_RATES['overall'] == 0.02

    def test_mega_contract_rate(self):
        assert BayesianFraudPrior.BASE_RATES['mega_contract'] == 0.035

    def test_sole_source_rate(self):
        assert BayesianFraudPrior.BASE_RATES['sole_source'] == 0.045

    def test_donations_rate(self):
        assert BayesianFraudPrior.BASE_RATES['with_donations'] == 0.08

    def test_detector_sensitivity(self):
        assert BayesianFraudPrior.DETECTOR_PERFORMANCE['sensitivity'] == 0.90

    def test_detector_specificity(self):
        assert BayesianFraudPrior.DETECTOR_PERFORMANCE['specificity'] == 0.95


class TestPosteriorCalculation:
    """Test Bayesian posterior probability computation."""

    def test_no_risk_factors_uses_base_rate(self):
        """Vanilla contract uses 2% base rate."""
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={}
        )
        assert result.prior_probability == 0.02

    def test_mega_contract_increases_prior(self):
        """Mega contract should increase the prior."""
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={'is_mega_contract': True}
        )
        assert result.prior_probability > 0.02

    def test_defense_increases_prior(self):
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={'is_defense': True}
        )
        assert result.prior_probability > 0.02

    def test_sole_source_increases_prior(self):
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={'is_sole_source': True}
        )
        assert result.prior_probability > 0.02

    def test_donations_dramatically_increase_prior(self):
        """Political donations should cause the largest prior increase."""
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={'has_political_donations': True}
        )
        # 2% * 4.0 = 8%
        assert result.prior_probability >= 0.08

    def test_multiple_risk_factors_compound(self):
        """Multiple risk factors should compound (multiplicative)."""
        bp = BayesianFraudPrior()
        single = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={'is_mega_contract': True}
        )
        multiple = bp.calculate_posterior(
            statistical_confidence=50,
            contract_characteristics={
                'is_mega_contract': True,
                'is_defense': True,
                'is_sole_source': True
            }
        )
        assert multiple.prior_probability > single.prior_probability

    def test_prior_capped_at_50_percent(self):
        """Prior should never exceed 50% regardless of risk factors."""
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(
            statistical_confidence=99,
            contract_characteristics={
                'is_mega_contract': True,
                'is_defense': True,
                'is_it_services': True,
                'is_sole_source': True,
                'has_political_donations': True
            }
        )
        assert result.prior_probability <= 0.50

    def test_higher_confidence_higher_posterior(self):
        """Higher statistical confidence should yield higher posterior."""
        bp = BayesianFraudPrior()
        low = bp.calculate_posterior(30, {})
        high = bp.calculate_posterior(95, {})
        assert high.posterior_probability > low.posterior_probability

    def test_posterior_between_0_and_1(self):
        """Posterior must always be a valid probability."""
        bp = BayesianFraudPrior()
        for conf in [0, 10, 50, 90, 100]:
            result = bp.calculate_posterior(conf, {})
            assert 0 <= result.posterior_probability <= 1.0

    def test_likelihood_ratio_positive(self):
        """Likelihood ratio should be positive."""
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(80, {'is_mega_contract': True})
        assert result.likelihood_ratio > 0

    def test_result_has_interpretation(self):
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(80, {})
        assert len(result.interpretation) > 0

    def test_result_has_base_rate_source(self):
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(80, {'is_mega_contract': True})
        assert "Mega contract" in result.base_rate_source

    def test_result_to_dict(self):
        bp = BayesianFraudPrior()
        result = bp.calculate_posterior(80, {})
        d = result.to_dict()
        assert 'prior_probability' in d
        assert 'posterior_probability' in d
        assert 'likelihood_ratio' in d


class TestBaseRateAdjustment:
    """Test the internal _get_adjusted_base_rate method."""

    def test_empty_characteristics(self):
        bp = BayesianFraudPrior()
        rate = bp._get_adjusted_base_rate({})
        assert rate == 0.02

    def test_mega_multiplier(self):
        bp = BayesianFraudPrior()
        rate = bp._get_adjusted_base_rate({'is_mega_contract': True})
        assert abs(rate - 0.02 * 1.75) < 1e-6

    def test_defense_multiplier(self):
        bp = BayesianFraudPrior()
        rate = bp._get_adjusted_base_rate({'is_defense': True})
        assert abs(rate - 0.02 * 1.25) < 1e-6

    def test_donations_multiplier(self):
        bp = BayesianFraudPrior()
        rate = bp._get_adjusted_base_rate({'has_political_donations': True})
        assert abs(rate - 0.02 * 4.0) < 1e-6

    def test_all_factors_capped(self):
        bp = BayesianFraudPrior()
        rate = bp._get_adjusted_base_rate({
            'is_mega_contract': True,
            'is_defense': True,
            'is_it_services': True,
            'is_sole_source': True,
            'has_political_donations': True
        })
        assert rate <= 0.50
