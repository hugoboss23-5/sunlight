"""
Tests for InstitutionalPipeline — the two-pass scoring engine.
Validates determinism, tier assignment, audit trail, and FDR integration.
"""
import numpy as np
import pytest
import hashlib
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from institutional_pipeline import (
    derive_contract_seed, compute_dataset_hash, compute_config_hash,
    _get_size_bin, _is_defense, _is_it,
    select_comparables_from_cache, score_contract, assign_tier,
    append_audit_entry, verify_audit_chain,
    InstitutionalPipeline, InstitutionalVerification,
)
from institutional_statistical_rigor import BootstrapAnalyzer


class TestDeterministicSeeding:
    """Contract-level seed derivation must be deterministic."""

    def test_same_inputs_same_seed(self):
        s1 = derive_contract_seed(42, 'CONTRACT-001')
        s2 = derive_contract_seed(42, 'CONTRACT-001')
        assert s1 == s2

    def test_different_contracts_different_seeds(self):
        s1 = derive_contract_seed(42, 'CONTRACT-001')
        s2 = derive_contract_seed(42, 'CONTRACT-002')
        assert s1 != s2

    def test_different_run_seeds_different_seeds(self):
        s1 = derive_contract_seed(42, 'CONTRACT-001')
        s2 = derive_contract_seed(99, 'CONTRACT-001')
        assert s1 != s2

    def test_seed_is_integer(self):
        s = derive_contract_seed(42, 'CONTRACT-001')
        assert isinstance(s, int)


class TestDatasetHash:
    """Dataset hashing for reproducibility verification."""

    def test_same_data_same_hash(self):
        contracts = [
            {'contract_id': 'A', 'raw_data_hash': 'abc'},
            {'contract_id': 'B', 'raw_data_hash': 'def'},
        ]
        h1 = compute_dataset_hash(contracts)
        h2 = compute_dataset_hash(contracts)
        assert h1 == h2

    def test_order_independent(self):
        """Hash should be the same regardless of input order."""
        c1 = [{'contract_id': 'A', 'raw_data_hash': 'abc'},
              {'contract_id': 'B', 'raw_data_hash': 'def'}]
        c2 = [{'contract_id': 'B', 'raw_data_hash': 'def'},
              {'contract_id': 'A', 'raw_data_hash': 'abc'}]
        assert compute_dataset_hash(c1) == compute_dataset_hash(c2)

    def test_different_data_different_hash(self):
        c1 = [{'contract_id': 'A', 'raw_data_hash': 'abc'}]
        c2 = [{'contract_id': 'A', 'raw_data_hash': 'xyz'}]
        assert compute_dataset_hash(c1) != compute_dataset_hash(c2)


class TestConfigHash:
    """Config hashing for run reproducibility."""

    def test_same_config_same_hash(self):
        config = {'n_bootstrap': 1000, 'fdr_alpha': 0.10}
        assert compute_config_hash(config) == compute_config_hash(config)

    def test_different_config_different_hash(self):
        c1 = {'n_bootstrap': 1000}
        c2 = {'n_bootstrap': 500}
        assert compute_config_hash(c1) != compute_config_hash(c2)


class TestHelperFunctions:
    """Utility functions used in the pipeline."""

    def test_size_bin_zero(self):
        assert _get_size_bin(0) == 0
        assert _get_size_bin(-100) == 0

    def test_size_bin_millions(self):
        assert _get_size_bin(1_000_000) == 6
        assert _get_size_bin(10_000_000) == 7
        assert _get_size_bin(100_000_000) == 8

    def test_is_defense_positive(self):
        assert _is_defense('Department of Defense') is True
        assert _is_defense('DOD - Army') is True
        assert _is_defense('Department of the Navy') is True
        assert _is_defense('Air Force Research Lab') is True

    def test_is_defense_negative(self):
        assert _is_defense('Department of Energy') is False
        assert _is_defense('NASA') is False
        assert _is_defense(None) is False

    def test_is_it_positive(self):
        assert _is_it('IT systems integration') is True
        assert _is_it('Software development services') is True
        assert _is_it('Computer hardware procurement') is True
        assert _is_it('Technology infrastructure') is True

    def test_is_it_negative(self):
        assert _is_it('Vehicle maintenance') is False
        assert _is_it('Building construction') is False
        assert _is_it(None) is False


class TestComparableSelection:
    """Comparable contract selection from agency cache."""

    def test_excludes_self(self):
        cache = {'DOD': [('C1', 5e6), ('C2', 6e6), ('C3', 7e6)]}
        result = select_comparables_from_cache('C1', 'DOD', 5e6, cache)
        assert len(result) == 2  # C2 and C3 only

    def test_missing_agency_returns_empty(self):
        cache = {'DOD': [('C1', 5e6)]}
        result = select_comparables_from_cache('X', 'NASA', 5e6, cache)
        assert result == []

    def test_size_bin_filtering(self):
        """Should prefer contracts in same size bin."""
        cache = {'DOD': [
            ('C1', 5_000_000),
            ('C2', 6_000_000),
            ('C3', 50_000_000),  # Different size bin
            ('C4', 500_000_000),  # Very different
        ]}
        result = select_comparables_from_cache('TARGET', 'DOD', 7_000_000, cache)
        # Should include C1, C2 (same bin) and C3 (adjacent bin)
        assert len(result) >= 2


class TestScoreContract:
    """Individual contract scoring."""

    def test_insufficient_comparables(self):
        contract = {
            'contract_id': 'TEST-001',
            'award_amount': 5_000_000,
            'agency_name': 'DOD',
            'description': 'Test',
            'comparables': [1_000_000],  # Only 1
        }
        ba = BootstrapAnalyzer(n_iterations=100)
        result = score_contract(contract, 42, {}, ba)
        assert result['insufficient_comparables'] is True
        assert result['raw_pvalue'] is None

    def test_sufficient_comparables_produces_scores(self):
        contract = {
            'contract_id': 'TEST-002',
            'award_amount': 10_000_000,
            'agency_name': 'DOD',
            'description': 'IT systems',
            'comparables': [5e6, 6e6, 7e6, 8e6, 9e6],
        }
        ba = BootstrapAnalyzer(n_iterations=100)
        result = score_contract(contract, 42, {'confidence_level': 0.95, 'min_comparables': 3}, ba)
        assert result['insufficient_comparables'] is False
        assert result['raw_pvalue'] is not None
        assert result['markup_pct'] is not None
        assert result['bayesian_posterior'] is not None

    def test_deterministic_scoring(self):
        """Same seed + same data = same result."""
        contract = {
            'contract_id': 'DET-001',
            'award_amount': 15_000_000,
            'agency_name': 'DOD',
            'description': 'Equipment',
            'comparables': [5e6, 6e6, 7e6, 8e6, 9e6, 10e6],
        }
        ba = BootstrapAnalyzer(n_iterations=200)
        config = {'confidence_level': 0.95, 'min_comparables': 3}

        r1 = score_contract(contract, 12345, config, ba)
        r2 = score_contract(contract, 12345, config, ba)

        assert r1['raw_pvalue'] == r2['raw_pvalue']
        assert r1['markup_pct'] == r2['markup_pct']
        assert r1['bayesian_posterior'] == r2['bayesian_posterior']


class TestTierAssignment:
    """Tier classification based on statistical evidence."""

    def test_gray_for_insufficient(self):
        score = {'insufficient_comparables': True, 'comparable_count': 1}
        tier, priority = assign_tier(score, None, False)
        assert tier == 'GRAY'

    def test_green_for_no_evidence(self):
        score = {
            'insufficient_comparables': False,
            'markup_ci_lower': -10,
            'bayesian_posterior': 0.01,
            'percentile_ci_lower': 30,
            'comparable_count': 10,
        }
        tier, priority = assign_tier(score, 0.5, False)
        assert tier == 'GREEN'

    def test_red_for_extreme_markup(self):
        """CI lower > 300% should always be RED."""
        score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 350,
            'bayesian_posterior': 0.90,
            'percentile_ci_lower': 99,
            'comparable_count': 10,
        }
        tier, priority = assign_tier(score, 0.001, True)
        assert tier == 'RED'

    def test_yellow_for_moderate_evidence(self):
        score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 100,
            'bayesian_posterior': 0.55,
            'percentile_ci_lower': 86,
            'comparable_count': 10,
        }
        tier, priority = assign_tier(score, 0.05, False)
        assert tier == 'YELLOW'

    def test_green_when_ci_below_gate_despite_other_signals(self):
        """ci<=55 gate: even with high posterior/percentile, low ci blocks YELLOW."""
        score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 30,
            'bayesian_posterior': 0.55,
            'percentile_ci_lower': 92,
            'comparable_count': 10,
        }
        tier, priority = assign_tier(score, 0.05, False)
        assert tier == 'GREEN'

    def test_green_for_percentile_80(self):
        """pci=80 is below the pci>90 threshold, should not contribute a signal."""
        score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 0,
            'bayesian_posterior': 0.10,
            'percentile_ci_lower': 80,
            'comparable_count': 10,
        }
        tier, priority = assign_tier(score, 0.5, False)
        assert tier == 'GREEN'

    def test_red_priority_lower_than_yellow(self):
        """RED cases should have lower (better) triage priority."""
        red_score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 350,
            'bayesian_posterior': 0.95,
            'percentile_ci_lower': 99,
            'comparable_count': 10,
        }
        yellow_score = {
            'insufficient_comparables': False,
            'markup_ci_lower': 100,
            'bayesian_posterior': 0.55,
            'percentile_ci_lower': 86,
            'comparable_count': 10,
        }
        _, red_priority = assign_tier(red_score, 0.001, True)
        _, yellow_priority = assign_tier(yellow_score, 0.05, False)
        assert red_priority < yellow_priority


class TestAuditChain:
    """Cryptographic audit trail integrity."""

    def test_single_entry(self, temp_db):
        eh = append_audit_entry(temp_db, 'TEST_ACTION', {'key': 'value'}, 'run_001')
        assert isinstance(eh, str)
        assert len(eh) == 64  # SHA-256 hex

    def test_chain_verification_valid(self, temp_db):
        append_audit_entry(temp_db, 'ACTION_1', {'step': 1}, 'run_001')
        append_audit_entry(temp_db, 'ACTION_2', {'step': 2}, 'run_001')
        append_audit_entry(temp_db, 'ACTION_3', {'step': 3}, 'run_001')

        valid, msg = verify_audit_chain(temp_db)
        assert valid is True
        assert '3 entries' in msg

    def test_empty_chain_valid(self, temp_db):
        valid, msg = verify_audit_chain(temp_db)
        assert valid is True

    def test_tamper_detection(self, temp_db):
        """Modifying an audit entry should break the chain."""
        append_audit_entry(temp_db, 'ACTION_1', {'step': 1}, 'run_001')
        append_audit_entry(temp_db, 'ACTION_2', {'step': 2}, 'run_001')

        # Tamper with the first entry
        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute("UPDATE audit_log SET details='{\"tampered\": true}' WHERE sequence_number=1")
        conn.commit()
        conn.close()

        valid, msg = verify_audit_chain(temp_db)
        assert valid is False


class TestPipelineIntegration:
    """End-to-end pipeline tests with temp database."""

    def test_full_pipeline_run(self, populated_db):
        """Run pipeline on test data and verify results."""
        pipeline = InstitutionalPipeline(populated_db)
        result = pipeline.run(run_seed=42, config={'n_bootstrap': 100}, verbose=False)

        assert result['n_scored'] > 0
        assert result['n_errors'] == 0
        assert result['run_seed'] == 42
        assert 'tier_counts' in result
        assert result['tier_counts'].get('GRAY', 0) + result['tier_counts'].get('GREEN', 0) + \
               result['tier_counts'].get('YELLOW', 0) + result['tier_counts'].get('RED', 0) == result['n_scored']

    def test_pipeline_determinism(self, populated_db):
        """Two runs with the same seed should produce identical tier counts.

        Uses different run seeds to avoid run_id collision (same-second timing),
        but verifies that the statistical outputs are seed-deterministic.
        """
        pipeline = InstitutionalPipeline(populated_db)
        r1 = pipeline.run(run_seed=42, config={'n_bootstrap': 100}, verbose=False)
        # Use seed 43 to get a different run_id, then compare dataset/config hashes
        # and re-run scoring logic to verify determinism
        import time
        time.sleep(1.1)  # Ensure different run_id timestamp
        r2 = pipeline.run(run_seed=42, config={'n_bootstrap': 100}, verbose=False)

        assert r1['tier_counts'] == r2['tier_counts']
        assert r1['dataset_hash'] == r2['dataset_hash']
        assert r1['config_hash'] == r2['config_hash']

    def test_pipeline_creates_audit_trail(self, populated_db):
        pipeline = InstitutionalPipeline(populated_db)
        pipeline.run(run_seed=42, config={'n_bootstrap': 100}, verbose=False)

        valid, msg = verify_audit_chain(populated_db)
        assert valid is True

    def test_verification_passes(self, populated_db):
        pipeline = InstitutionalPipeline(populated_db)
        result = pipeline.run(run_seed=42, config={'n_bootstrap': 100}, verbose=False)

        verifier = InstitutionalVerification(populated_db)
        verification = verifier.verify_run(result['run_id'], verbose=False)
        assert verification['all_passed'] is True

    def test_outlier_detected(self, populated_db):
        """The DOD-OUTLIER contract (5x median) should be flagged YELLOW or RED."""
        pipeline = InstitutionalPipeline(populated_db)
        result = pipeline.run(run_seed=42, config={'n_bootstrap': 200}, verbose=False)

        conn = sqlite3.connect(populated_db)
        c = conn.cursor()
        c.execute(
            "SELECT fraud_tier, markup_pct FROM contract_scores WHERE contract_id='DOD-OUTLIER' AND run_id=?",
            (result['run_id'],)
        )
        row = c.fetchone()
        conn.close()

        assert row is not None
        tier, markup = row
        assert tier in ('YELLOW', 'RED'), f"Outlier was classified as {tier} with markup {markup}%"

    def test_limit_parameter(self, populated_db):
        """Limit should restrict number of contracts analyzed."""
        pipeline = InstitutionalPipeline(populated_db)
        result = pipeline.run(run_seed=42, config={'n_bootstrap': 100}, limit=5, verbose=False)
        assert result['n_scored'] == 5
