"""
Tests for tca_procurement.py — Topological Contradiction Analysis for Procurement Fraud.

Covers:
  - Graph construction from contract data
  - All 8 contradiction detection types
  - Feedback trap / pay-to-play cycle detection
  - Graceful degradation when KD/TCA imports unavailable
  - Edge cases: zero fields, boundary values
"""
import sys
import os
import math
import pytest
import numpy as np

os.environ['SUNLIGHT_AUTH_ENABLED'] = 'false'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from tca_procurement import (
    build_contract_graph,
    analyze_contradictions,
    score_contract_tca,
    tca_score_for_pipeline,
    _node_id,
    _compute_edge_type_entropy,
    _compute_designedness,
    ContradictionEvidence,
    TCAScore,
    build_ecosystem_graph,
    analyze_ecosystem,
)
from tca import TopologicalGraph, EdgeType


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def clean_contract():
    """A legitimate contract with healthy procurement signals."""
    return {
        'contract_id': 'CLEAN-001',
        'vendor_name': 'LegitCorp',
        'agency_name': 'Department of Energy',
        'award_amount': 6_500_000,
        'num_offers': 5,
        'procurement_method': 'open',
        'is_sole_source': False,
        'tender_period_days': 30.0,
        'decision_period_days': 14.0,
        'has_donations': False,
        'donation_amount': 0,
        'amendment_count': 0,
    }


@pytest.fixture
def fraudulent_contract():
    """A contract with every red flag imaginable."""
    return {
        'contract_id': 'FRAUD-001',
        'vendor_name': 'ShellCorp',
        'agency_name': 'Department of Defense',
        'award_amount': 50_000_000,  # 5x+ the median comparable
        'num_offers': 1,
        'procurement_method': 'direct',
        'is_sole_source': True,
        'tender_period_days': 2.0,
        'decision_period_days': -5.0,
        'has_donations': True,
        'donation_amount': 100_000,
        'amendment_count': 5,
        'original_value': 10_000_000,
        'final_value': 50_000_000,
    }


@pytest.fixture
def comparables():
    """Realistic comparables centered around $6-8M."""
    return [5_000_000, 7_200_000, 6_800_000, 8_100_000, 5_500_000,
            6_300_000, 7_900_000, 6_100_000, 5_800_000, 7_500_000]


@pytest.fixture
def agency_contracts():
    """Set of contracts at a single agency for vendor concentration tests."""
    vendor_contracts = []
    for i in range(8):
        vendor_contracts.append({
            'contract_id': f'AG-{i:03d}',
            'vendor_name': 'DominantVendor' if i < 5 else f'Other_{i}',
            'agency_name': 'Department of Defense',
            'award_amount': 5_000_000 + i * 500_000,
        })
    return vendor_contracts


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

class TestGraphConstruction:
    """Test build_contract_graph produces correct topology."""

    def test_core_nodes_created(self, clean_contract, comparables):
        g = build_contract_graph(clean_contract, comparables)
        nodes = g.nodes
        assert _node_id("contract", "CLEAN-001") in nodes
        assert _node_id("vendor", "LegitCorp") in nodes
        assert _node_id("agency", "Department_of_Energy") in nodes

    def test_express_edges_exist(self, clean_contract, comparables):
        g = build_contract_graph(clean_contract, comparables)
        agency_nid = _node_id("agency", "Department_of_Energy")
        contract_nid = _node_id("contract", "CLEAN-001")
        agency_node = g.nodes[agency_nid]
        express_edges = agency_node.get_edges_by_type(EdgeType.EXPRESSES)
        targets = [e.target_id for e in express_edges]
        assert contract_nid in targets

    def test_market_price_node_with_comparables(self, clean_contract, comparables):
        g = build_contract_graph(clean_contract, comparables)
        market_nid = _node_id("market", "CLEAN-001")
        assert market_nid in g.nodes

    def test_no_market_node_without_comparables(self, clean_contract):
        g = build_contract_graph(clean_contract, [])
        market_nid = _node_id("market", "CLEAN-001")
        assert market_nid not in g.nodes

    def test_no_market_node_with_insufficient_comparables(self, clean_contract):
        g = build_contract_graph(clean_contract, [1_000_000, 2_000_000])
        market_nid = _node_id("market", "CLEAN-001")
        assert market_nid not in g.nodes

    def test_competition_node_with_multiple_offers(self, clean_contract, comparables):
        g = build_contract_graph(clean_contract, comparables)
        verify_nid = _node_id("verify", "CLEAN-001_competition")
        assert verify_nid in g.nodes

    def test_single_bid_creates_seeks_edge(self, comparables):
        contract = {
            'contract_id': 'SB-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 5_000_000, 'num_offers': 1,
        }
        g = build_contract_graph(contract, comparables)
        sb_nid = _node_id("flag", "SB-001_single_bid")
        assert sb_nid in g.nodes

    def test_sole_source_creates_removes_edge(self, comparables):
        contract = {
            'contract_id': 'SS-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 5_000_000, 'procurement_method': 'direct',
            'is_sole_source': True,
        }
        g = build_contract_graph(contract, comparables)
        threshold_nid = _node_id("threshold", "SS-001_competitive")
        contract_nid = _node_id("contract", "SS-001")
        node = g.nodes[contract_nid]
        removes = node.get_edges_by_type(EdgeType.REMOVES)
        targets = [e.target_id for e in removes]
        assert threshold_nid in targets

    def test_timeline_bounds_healthy(self, comparables):
        contract = {
            'contract_id': 'TL-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 5_000_000, 'tender_period_days': 30.0,
        }
        g = build_contract_graph(contract, comparables)
        tl_nid = _node_id("timeline", "TL-001_tender")
        node = g.nodes[tl_nid]
        bounds = node.get_edges_by_type(EdgeType.BOUNDS)
        assert len(bounds) > 0, "Healthy tender period should create BOUNDS edge"

    def test_timeline_removes_rushed(self, comparables):
        contract = {
            'contract_id': 'TL-002', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 5_000_000, 'tender_period_days': 3.0,
        }
        g = build_contract_graph(contract, comparables)
        tl_nid = _node_id("timeline", "TL-002_tender")
        node = g.nodes[tl_nid]
        removes = node.get_edges_by_type(EdgeType.REMOVES)
        assert len(removes) > 0, "Rushed tender period should create REMOVES edge"

    def test_donation_creates_seeks_cycle(self, comparables):
        contract = {
            'contract_id': 'DON-001', 'vendor_name': 'DonorCorp', 'agency_name': 'Agency',
            'award_amount': 5_000_000, 'has_donations': True, 'donation_amount': 50_000,
        }
        g = build_contract_graph(contract, comparables)
        don_nid = _node_id("donation", "DonorCorp_Agency")
        assert don_nid in g.nodes

    def test_amendment_inflation_creates_removes(self, comparables):
        contract = {
            'contract_id': 'AM-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 10_000_000, 'amendment_count': 3,
            'original_value': 5_000_000, 'final_value': 10_000_000,
        }
        g = build_contract_graph(contract, comparables)
        amend_nid = _node_id("amendment", "AM-001")
        assert amend_nid in g.nodes
        node = g.nodes[amend_nid]
        removes = node.get_edges_by_type(EdgeType.REMOVES)
        assert len(removes) > 0, "100% amendment inflation should create REMOVES"

    def test_vendor_concentration(self, comparables, agency_contracts):
        # DominantVendor has 5/8 contracts at DoD
        contract = {
            'contract_id': 'VC-001', 'vendor_name': 'DominantVendor',
            'agency_name': 'Department of Defense', 'award_amount': 6_000_000,
        }
        g = build_contract_graph(contract, comparables, agency_contracts)
        hist_nid = _node_id("history", "DominantVendor_Department_of_Defense")
        assert hist_nid in g.nodes


# =============================================================================
# CONTRADICTION DETECTION — ALL 8 TYPES
# =============================================================================

class TestContradictionDetection:
    """Each of the 8 contradiction types fires on crafted input."""

    def test_price_mirror_break(self, comparables):
        """Price 5x+ the median triggers price_mirror_break."""
        contract = {
            'contract_id': 'PMB-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 50_000_000,  # ~7.5x median of ~6.5M
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'PMB-001')
        types = [c.violation_type for c in contradictions]
        assert 'price_mirror_break' in types

    def test_competition_bypass(self, comparables):
        """Sole source + single bid triggers competition_bypass."""
        contract = {
            'contract_id': 'CB-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_500_000, 'procurement_method': 'direct',
            'is_sole_source': True, 'num_offers': 1,
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'CB-001')
        types = [c.violation_type for c in contradictions]
        assert 'competition_bypass' in types

    def test_timeline_violation(self, comparables):
        """Rushed tender period triggers timeline_violation."""
        contract = {
            'contract_id': 'TV-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_500_000, 'tender_period_days': 3.0,
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'TV-001')
        types = [c.violation_type for c in contradictions]
        assert 'timeline_violation' in types

    def test_negative_decision_period(self, comparables):
        """Negative decision period triggers timeline_violation."""
        contract = {
            'contract_id': 'ND-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_500_000, 'decision_period_days': -3.0,
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'ND-001')
        types = [c.violation_type for c in contradictions]
        assert 'timeline_violation' in types

    def test_vendor_concentration_contradiction(self, comparables):
        """Vendor with >40% of agency contracts triggers vendor_concentration."""
        agency_contracts = [
            {'contract_id': f'VC-{i}', 'vendor_name': 'Monopolist' if i < 6 else f'Other_{i}',
             'agency_name': 'Agency', 'award_amount': 5_000_000}
            for i in range(10)
        ]
        contract = {
            'contract_id': 'VC-TARGET', 'vendor_name': 'Monopolist',
            'agency_name': 'Agency', 'award_amount': 6_000_000,
        }
        g = build_contract_graph(contract, comparables, agency_contracts)
        contradictions = analyze_contradictions(g, 'VC-TARGET')
        types = [c.violation_type for c in contradictions]
        assert 'vendor_concentration' in types

    def test_amendment_inflation(self, comparables):
        """Large post-award value increase triggers amendment_inflation."""
        contract = {
            'contract_id': 'AI-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 20_000_000, 'amendment_count': 4,
            'original_value': 5_000_000, 'final_value': 20_000_000,  # 300% growth
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'AI-001')
        types = [c.violation_type for c in contradictions]
        assert 'amendment_inflation' in types

    def test_unverified_award(self):
        """Contract with no competition and no audit triggers unverified_award."""
        contract = {
            'contract_id': 'UA-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 5_000_000,
            # No num_offers, no tender_period, no competition signals
        }
        g = build_contract_graph(contract, [])  # No comparables either
        contradictions = analyze_contradictions(g, 'UA-001')
        types = [c.violation_type for c in contradictions]
        assert 'unverified_award' in types

    def test_pay_to_play_cycle(self, comparables):
        """Donation + contract creates pay_to_play_cycle or feedback_trap."""
        contract = {
            'contract_id': 'PTP-001', 'vendor_name': 'DonorVendor',
            'agency_name': 'CorruptAgency', 'award_amount': 10_000_000,
            'has_donations': True, 'donation_amount': 100_000,
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'PTP-001')
        types = [c.violation_type for c in contradictions]
        assert 'pay_to_play_cycle' in types or 'feedback_trap' in types, \
            f"Expected pay-to-play or feedback trap, got: {types}"

    def test_unproven_relationship(self, comparables):
        """Single bid creates high-weight SEEKS -> unproven_relationship."""
        contract = {
            'contract_id': 'UP-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_500_000, 'num_offers': 1,
            'has_donations': True, 'donation_amount': 50_000,
        }
        g = build_contract_graph(contract, comparables)
        contradictions = analyze_contradictions(g, 'UP-001')
        types = [c.violation_type for c in contradictions]
        assert 'unproven_relationship' in types


# =============================================================================
# FEEDBACK TRAP (CYCLE DETECTION)
# =============================================================================

class TestFeedbackTraps:
    """Test cycle detection in procurement topology."""

    def test_donation_cycle_detected(self, comparables):
        """Vendor -> Donation -> Agency -> Contract -> Vendor = pay-to-play."""
        contract = {
            'contract_id': 'CYC-001', 'vendor_name': 'CycleCorp',
            'agency_name': 'CycleAgency', 'award_amount': 8_000_000,
            'has_donations': True, 'donation_amount': 200_000,
        }
        score = score_contract_tca(contract, comparables)
        cycle_types = [c.violation_type for c in score.contradictions
                       if 'cycle' in c.violation_type or 'trap' in c.violation_type]
        assert len(cycle_types) > 0, "Donation cycle should be detected"

    def test_clean_contract_no_cycles(self, clean_contract, comparables):
        score = score_contract_tca(clean_contract, comparables)
        cycle_types = [c.violation_type for c in score.contradictions
                       if 'cycle' in c.violation_type or 'trap' in c.violation_type]
        assert len(cycle_types) == 0, "Clean contract should have no cycles"


# =============================================================================
# SCORING FUNCTION
# =============================================================================

class TestScoring:
    """Test score_contract_tca and tca_score_for_pipeline."""

    def test_clean_contract_low_risk(self, clean_contract, comparables):
        score = score_contract_tca(clean_contract, comparables)
        assert score.tca_risk_score < 0.3
        assert score.verdict == "clean"
        assert score.tca_likelihood_ratio <= 1.0

    def test_fraudulent_contract_high_risk(self, fraudulent_contract, comparables):
        score = score_contract_tca(fraudulent_contract, comparables)
        assert score.tca_risk_score > 0.5
        assert score.verdict in ("suspicious", "structurally_fraudulent")
        assert score.tca_likelihood_ratio > 1.0

    def test_pipeline_interface_returns_tuple(self, clean_contract, comparables):
        result = tca_score_for_pipeline(clean_contract, comparables)
        assert isinstance(result, tuple)
        assert len(result) == 3
        risk, lr, details = result
        assert isinstance(risk, float)
        assert isinstance(lr, float)
        assert isinstance(details, dict)
        assert 'contradiction_count' in details
        assert 'verdict' in details
        assert 'violations' in details

    def test_severity_ordering(self, comparables):
        """More red flags = higher risk score."""
        mild = {'contract_id': 'M', 'vendor_name': 'V', 'agency_name': 'A',
                'award_amount': 10_000_000, 'procurement_method': 'direct'}
        severe = {'contract_id': 'S', 'vendor_name': 'V', 'agency_name': 'A',
                  'award_amount': 50_000_000, 'procurement_method': 'direct',
                  'is_sole_source': True, 'num_offers': 1,
                  'tender_period_days': 2.0, 'decision_period_days': -1.0,
                  'has_donations': True, 'donation_amount': 100_000,
                  'amendment_count': 5, 'original_value': 10_000_000,
                  'final_value': 50_000_000}
        mild_score = score_contract_tca(mild, comparables)
        severe_score = score_contract_tca(severe, comparables)
        assert severe_score.tca_risk_score > mild_score.tca_risk_score

    def test_lr_bounded(self, fraudulent_contract, comparables):
        """LR is capped at 50 before designedness multiplier (max effective ~55)."""
        score = score_contract_tca(fraudulent_contract, comparables)
        # Cap is 50.0 but low-designedness multiplier (* 1.1) can push to 55
        assert score.tca_likelihood_ratio <= 55.0

    def test_summary_property(self, fraudulent_contract, comparables):
        score = score_contract_tca(fraudulent_contract, comparables)
        assert "contradictions" in score.summary
        assert "TCA risk" in score.summary

    def test_no_contradictions_summary(self, clean_contract, comparables):
        score = score_contract_tca(clean_contract, comparables)
        if score.contradiction_count == 0:
            assert "No topological contradictions" in score.summary


# =============================================================================
# GRACEFUL DEGRADATION
# =============================================================================

class TestGracefulDegradation:
    """KD server unavailable should return neutral LR=1.0."""

    def test_pipeline_tca_fallback(self):
        """_compute_tca_for_score catches import/runtime errors and returns neutral."""
        # The institutional_pipeline._compute_tca_for_score wraps tca_score_for_pipeline
        # in a try/except and returns (0.0, 1.0, {}) on failure.
        # We test the actual pipeline function by importing it.
        from institutional_pipeline import _compute_tca_for_score
        # Pass a contract with no fields — if TCA crashes, it should degrade gracefully
        risk, lr, details = _compute_tca_for_score({}, [])
        # Either it returns a valid score or the fallback
        assert isinstance(risk, float)
        assert isinstance(lr, float)
        assert lr >= 0.0  # Should never be negative


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge cases: zero fields, boundary values."""

    def test_zero_fields_contract(self):
        """Contract with all fields empty/zero doesn't crash."""
        contract = {
            'contract_id': '', 'vendor_name': '', 'agency_name': '',
            'award_amount': 0,
        }
        score = score_contract_tca(contract, [])
        assert isinstance(score, TCAScore)
        assert score.tca_risk_score >= 0.0

    def test_none_fields_contract(self):
        """Contract with None values doesn't crash."""
        contract = {
            'contract_id': None, 'vendor_name': None, 'agency_name': None,
            'award_amount': 0,
        }
        score = score_contract_tca(contract, [])
        assert isinstance(score, TCAScore)

    def test_empty_contract_dict(self):
        """Completely empty dict doesn't crash."""
        score = score_contract_tca({}, [])
        assert isinstance(score, TCAScore)

    def test_boundary_tender_period_exactly_15(self, comparables):
        """Tender period exactly at boundary (15 days) should be BOUNDS (healthy)."""
        contract = {
            'contract_id': 'BP-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_000_000, 'tender_period_days': 15.0,
        }
        g = build_contract_graph(contract, comparables)
        tl_nid = _node_id("timeline", "BP-001_tender")
        node = g.nodes[tl_nid]
        bounds = node.get_edges_by_type(EdgeType.BOUNDS)
        assert len(bounds) > 0

    def test_boundary_tender_period_exactly_7(self, comparables):
        """Tender period exactly 7 days — between 7 and 15, should get REMOVES weight=1.5."""
        contract = {
            'contract_id': 'BP-002', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 6_000_000, 'tender_period_days': 7.0,
        }
        g = build_contract_graph(contract, comparables)
        tl_nid = _node_id("timeline", "BP-002_tender")
        node = g.nodes[tl_nid]
        removes = node.get_edges_by_type(EdgeType.REMOVES)
        assert len(removes) > 0

    def test_very_large_award_amount(self, comparables):
        """Extremely large amount doesn't cause overflow."""
        contract = {
            'contract_id': 'BIG-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': 999_999_999_999,
        }
        score = score_contract_tca(contract, comparables)
        assert not math.isnan(score.tca_risk_score)
        assert not math.isinf(score.tca_risk_score)

    def test_negative_award_amount(self, comparables):
        """Negative amount doesn't crash."""
        contract = {
            'contract_id': 'NEG-001', 'vendor_name': 'V', 'agency_name': 'A',
            'award_amount': -1_000_000,
        }
        score = score_contract_tca(contract, comparables)
        assert isinstance(score, TCAScore)

    def test_node_id_truncation(self):
        """Long identifiers get truncated to 60 chars."""
        long_name = "A" * 200
        nid = _node_id("vendor", long_name)
        # Format is "vendor:AAAA..." — type + colon + 60 chars
        assert len(nid) <= len("vendor:") + 60


# =============================================================================
# METRICS
# =============================================================================

class TestMetrics:

    def test_entropy_diverse_graph(self, clean_contract, comparables):
        """Graph with diverse edge types should have high entropy."""
        g = build_contract_graph(clean_contract, comparables)
        ete = _compute_edge_type_entropy(g)
        assert 0.0 < ete <= 1.0

    def test_designedness_clean_contract(self, clean_contract, comparables):
        """Clean contract with full oversight should have decent designedness."""
        g = build_contract_graph(clean_contract, comparables)
        d = _compute_designedness(g)
        assert 0.0 < d <= 1.0

    def test_empty_graph_entropy(self):
        """Empty graph has zero entropy."""
        assert _compute_edge_type_entropy(TopologicalGraph()) == 0.0

    def test_empty_graph_designedness(self):
        assert _compute_designedness(TopologicalGraph()) == 0.0


# =============================================================================
# ECOSYSTEM ANALYSIS
# =============================================================================

class TestEcosystem:

    def test_ecosystem_basic(self):
        contracts = [
            {'contract_id': f'E-{i}', 'vendor_name': f'V{i}', 'agency_name': 'TestAgency',
             'award_amount': 1_000_000 * (i + 1)}
            for i in range(5)
        ]
        result = analyze_ecosystem(contracts, 'TestAgency')
        assert result['contracts_analyzed'] == 5
        assert result['verdict'] in ('healthy', 'suspicious', 'fragile', 'critical')

    def test_ecosystem_insufficient_data(self):
        """Zero contracts => insufficient_data (1 contract creates 3 nodes, passes threshold)."""
        result = analyze_ecosystem([], 'A')
        assert result['verdict'] == 'insufficient_data'
