"""
Tests for StatisticalEvidence and ProsecutorEvidencePackage.
Evidence packages must be court-ready and complete.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_statistical_rigor import (
    BootstrapResult, BayesianResult, StatisticalEvidence, FraudTier,
    ProsecutorEvidencePackage,
)


class TestBootstrapResult:
    """BootstrapResult dataclass serialization."""

    def test_to_dict(self):
        r = BootstrapResult(
            point_estimate=150.0,
            ci_lower=120.0,
            ci_upper=180.0,
            ci_width=60.0,
            confidence_level=0.95,
            n_iterations=1000,
            sample_size=10,
            interpretation="Test",
            is_significant=True,
            p_value=0.001
        )
        d = r.to_dict()
        assert d['point_estimate'] == 150.0
        assert d['ci_lower'] == 120.0
        assert d['p_value'] == 0.001


class TestBayesianResult:
    """BayesianResult dataclass serialization."""

    def test_to_dict(self):
        r = BayesianResult(
            prior_probability=0.02,
            likelihood_ratio=18.0,
            posterior_probability=0.27,
            base_rate_source="Base fraud rate: 2%",
            sensitivity=0.90,
            specificity=0.95,
            interpretation="MODERATE fraud probability: 27.0%"
        )
        d = r.to_dict()
        assert d['prior_probability'] == 0.02
        assert d['posterior_probability'] == 0.27


class TestStatisticalEvidence:
    """StatisticalEvidence complete package."""

    def _make_evidence(self, tier=FraudTier.YELLOW, confidence=75):
        return StatisticalEvidence(
            contract_id='TEST-001',
            contract_amount=10_000_000,
            comparison_amounts=[5e6, 6e6, 7e6],
            sample_size=3,
            raw_zscore=2.5,
            log_zscore=2.1,
            raw_markup_pct=66.7,
            bootstrap_markup=BootstrapResult(
                point_estimate=66.7, ci_lower=40.0, ci_upper=95.0,
                ci_width=55.0, confidence_level=0.95, n_iterations=1000,
                sample_size=3, interpretation="Test", is_significant=False,
                p_value=0.05
            ),
            bootstrap_percentile=BootstrapResult(
                point_estimate=90.0, ci_lower=75.0, ci_upper=100.0,
                ci_width=25.0, confidence_level=0.95, n_iterations=1000,
                sample_size=3, interpretation="Test", is_significant=False,
                p_value=0.10
            ),
            bayesian_fraud_probability=BayesianResult(
                prior_probability=0.02, likelihood_ratio=10.0,
                posterior_probability=0.17, base_rate_source="Base",
                sensitivity=0.90, specificity=0.95, interpretation="Test"
            ),
            fdr_adjusted_pvalue=0.08,
            survives_fdr=False,
            tier=tier,
            confidence_score=confidence,
            reasoning=["Price analysis shows elevated markup"],
            legal_citations=["31 U.S.C. 3729(a)(1)(A)"],
            analysis_timestamp="2026-02-17T00:00:00",
            methodology_version="1.0.0-institutional"
        )

    def test_to_dict_has_all_fields(self):
        evidence = self._make_evidence()
        d = evidence.to_dict()
        assert d['contract_id'] == 'TEST-001'
        assert d['tier'] == 'YELLOW'  # Serialized as string
        assert d['raw_zscore'] == 2.5
        assert d['fdr_adjusted_pvalue'] == 0.08
        assert len(d['reasoning']) > 0
        assert len(d['legal_citations']) > 0

    def test_tier_serialized_as_string(self):
        evidence = self._make_evidence(tier=FraudTier.RED)
        d = evidence.to_dict()
        assert d['tier'] == 'RED'
        assert isinstance(d['tier'], str)

    def test_evidence_completeness(self):
        """All required fields for court presentation must be present."""
        evidence = self._make_evidence()
        d = evidence.to_dict()
        required_fields = [
            'contract_id', 'contract_amount', 'sample_size',
            'raw_zscore', 'log_zscore', 'raw_markup_pct',
            'bootstrap_markup', 'bootstrap_percentile',
            'bayesian_fraud_probability', 'fdr_adjusted_pvalue',
            'survives_fdr', 'tier', 'confidence_score',
            'reasoning', 'legal_citations',
            'analysis_timestamp', 'methodology_version',
        ]
        for field in required_fields:
            assert field in d, f"Missing required field: {field}"


class TestProsecutorEvidencePackage:
    """Evidence package generation from database."""

    def test_evidence_generation(self, populated_db):
        pkg = ProsecutorEvidencePackage(populated_db)
        contract = {
            'id': 'DOD-OUTLIER',
            'amount': 35_000_000,
            'vendor': 'SUSPECT_VENDOR',
            'agency': 'Department of Defense',
            'desc': 'Special project alpha',
            'has_donations': True,
            'is_sole_source': False,
        }
        evidence = pkg.generate_evidence(contract)

        assert evidence.contract_id == 'DOD-OUTLIER'
        assert evidence.contract_amount == 35_000_000
        assert evidence.sample_size > 0
        assert len(evidence.reasoning) > 0
        assert evidence.tier in (FraudTier.RED, FraudTier.YELLOW, FraudTier.GREEN, FraudTier.GRAY)

    def test_insufficient_comparables(self, temp_db):
        """Contract with no peers should return GRAY-like evidence."""
        # Insert a single contract in an agency with no peers
        import sqlite3
        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute(
            "INSERT INTO contracts VALUES (?,?,?,?,?,?,?,?,?)",
            ('LONE-001', 5_000_000, 'LONE_VENDOR', 'OBSCURE_AGENCY',
             'Unique service', '2025-01-01', None, None, 'abc')
        )
        conn.commit()
        conn.close()

        pkg = ProsecutorEvidencePackage(temp_db)
        evidence = pkg.generate_evidence({
            'id': 'LONE-001',
            'amount': 5_000_000,
            'vendor': 'LONE_VENDOR',
            'agency': 'OBSCURE_AGENCY',
            'desc': 'Unique service',
            'has_donations': False,
        })
        assert evidence.sample_size <= 1
