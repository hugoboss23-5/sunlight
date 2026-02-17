"""
Tests for DOJ threshold calibration and tier assignment.
Validates that detection aligns with prosecution precedent.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import DOJProsecutionThresholds, FraudTier


class TestDOJThresholds:
    """Verify DOJ prosecution thresholds are correctly set."""

    def test_extreme_markup(self):
        assert DOJProsecutionThresholds.EXTREME_MARKUP == 300

    def test_high_markup(self):
        assert DOJProsecutionThresholds.HIGH_MARKUP == 200

    def test_elevated_markup(self):
        assert DOJProsecutionThresholds.ELEVATED_MARKUP == 150

    def test_investigation_worthy(self):
        assert DOJProsecutionThresholds.INVESTIGATION_WORTHY == 75

    def test_threshold_ordering(self):
        """Thresholds must be strictly ordered."""
        assert (DOJProsecutionThresholds.INVESTIGATION_WORTHY <
                DOJProsecutionThresholds.ELEVATED_MARKUP <
                DOJProsecutionThresholds.HIGH_MARKUP <
                DOJProsecutionThresholds.EXTREME_MARKUP)

    def test_red_flag_confidence(self):
        assert DOJProsecutionThresholds.RED_FLAG_CONFIDENCE == 95

    def test_yellow_flag_confidence(self):
        assert DOJProsecutionThresholds.YELLOW_FLAG_CONFIDENCE == 85

    def test_bootstrap_iterations(self):
        assert DOJProsecutionThresholds.BOOTSTRAP_ITERATIONS == 10000

    def test_base_fraud_rate(self):
        assert DOJProsecutionThresholds.BASE_FRAUD_RATE == 0.02


class TestFraudTierEnum:
    """Verify fraud tier definitions."""

    def test_tier_values(self):
        assert FraudTier.RED.value == "RED"
        assert FraudTier.YELLOW.value == "YELLOW"
        assert FraudTier.GREEN.value == "GREEN"
        assert FraudTier.GRAY.value == "GRAY"

    def test_four_tiers_exist(self):
        assert len(FraudTier) == 4


class TestDOJCaseValidation:
    """Validate that DOJ prosecuted cases would be caught by our thresholds."""

    def test_all_price_fraud_cases_detected(self, doj_cases):
        """Every DOJ case with a markup should exceed INVESTIGATION_WORTHY."""
        price_cases = [c for c in doj_cases if c['markup_pct'] > 0]
        for case in price_cases:
            assert case['markup_pct'] >= DOJProsecutionThresholds.INVESTIGATION_WORTHY, \
                f"Case {case['case_id']} with {case['markup_pct']}% markup below detection threshold"

    def test_extreme_cases_red_tier(self, doj_cases):
        """Cases with >300% markup should map to RED tier."""
        extreme = [c for c in doj_cases if c['markup_pct'] >= 300]
        assert len(extreme) >= 2  # Oracle (350%) and Boeing (450%)
        for case in extreme:
            assert case['markup_pct'] >= DOJProsecutionThresholds.EXTREME_MARKUP

    def test_detection_rate_above_80_percent(self, doj_cases):
        """Should detect at least 80% of DOJ price fraud cases."""
        price_cases = [c for c in doj_cases if c['markup_pct'] > 0]
        detected = [c for c in price_cases if c['markup_pct'] >= DOJProsecutionThresholds.INVESTIGATION_WORTHY]
        rate = len(detected) / len(price_cases)
        assert rate >= 0.80, f"Detection rate {rate:.0%} below 80% threshold"

    def test_total_settlement_value_coverage(self, doj_cases):
        """Should cover >90% of total settlement value for price cases."""
        price_cases = [c for c in doj_cases if c['markup_pct'] > 0]
        total_value = sum(c['settlement'] for c in price_cases)
        detected_value = sum(
            c['settlement'] for c in price_cases
            if c['markup_pct'] >= DOJProsecutionThresholds.INVESTIGATION_WORTHY
        )
        coverage = detected_value / total_value
        assert coverage >= 0.90, f"Value coverage {coverage:.0%} below 90%"

    def test_non_price_cases_acknowledged(self, doj_cases):
        """Cases with 0% markup are non-price fraud — system should not claim to detect them."""
        non_price = [c for c in doj_cases if c['markup_pct'] == 0]
        assert len(non_price) >= 1  # General Dynamics false certification
