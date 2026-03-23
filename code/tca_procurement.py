"""
TCA-SUNLIGHT Integration — Topological Contradiction Analysis for Procurement Fraud.

Models procurement as a typed graph using chestohedron edge types.
Fraud creates structural contradictions in the procurement topology.
Healthy procurement has specific topological invariants — violations map to risk.

Edge type mapping (chestohedron gates -> procurement relationships):
  MIRRORS   — Expected vs actual price (market comparison)
  INHERITS  — Vendor history patterns (track record)
  BOUNDS    — Regulatory thresholds (spending limits, bid requirements, timelines)
  EXPRESSES — Awarded contracts (the transaction itself)
  VERIFIES  — Audit/oversight checks (competition, review, approval)
  REMOVES   — Rejected bids, disqualifications, contradictions
  SEEKS     — Pending reviews, unverified claims

Topological invariants of healthy procurement:
  1. Every EXPRESS has at least one VERIFY (oversight coverage)
  2. MIRRORS weights ~ 1.0 (prices match market)
  3. BOUNDS edges satisfied (thresholds respected)
  4. REMOVES edges exist (real competition happened)
  5. No feedback traps (pay-to-play cycles)
  6. No vendor star topology (concentration)
  7. Edge type diversity (all oversight mechanisms present)

Thesis: topology over substance. If the structure is broken, the system is broken.

Uses standalone tca.py engine — zero external dependencies.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from tca import (
    TopologicalGraph, TopologicalNode, EdgeType, EdgeRelation,
    compute_health, betweenness_centrality, detect_cycles,
    detect_bridges, detect_isolated, analyze as tca_analyze,
    solve as tca_solve, _edge_type_entropy,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ContradictionEvidence:
    """A single topological contradiction found in procurement data."""
    violation_type: str
    severity: float               # 0.0 to 1.0
    likelihood_ratio: float       # Bayesian evidence weight
    description: str
    nodes_involved: List[str]
    edge_types_involved: List[str]
    gate_violated: str            # Which chestohedron gate is violated

    @property
    def is_critical(self) -> bool:
        return self.severity >= 0.7


@dataclass
class TCAScore:
    """TCA-based fraud risk score for a contract."""
    tca_risk_score: float
    tca_likelihood_ratio: float
    contradiction_count: int
    critical_contradiction_count: int
    contradictions: List[ContradictionEvidence]
    topological_health: Dict[str, Any]
    verdict: str                  # "clean", "suspicious", "structurally_fraudulent"
    edge_type_entropy: float
    designedness: float

    @property
    def summary(self) -> str:
        if not self.contradictions:
            return "No topological contradictions detected"
        critical = [c for c in self.contradictions if c.is_critical]
        return (
            f"{self.contradiction_count} contradictions "
            f"({len(critical)} critical), "
            f"TCA risk: {self.tca_risk_score:.2f}, "
            f"LR: {self.tca_likelihood_ratio:.2f}"
        )


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def _node_id(node_type: str, identifier: str) -> str:
    safe = str(identifier).replace(" ", "_")[:60]
    return f"{node_type}:{safe}"


def build_contract_graph(
    contract: Dict[str, Any],
    comparables: List[float],
    agency_contracts: List[Dict[str, Any]] = None,
) -> TopologicalGraph:
    """
    Build a TCA graph modeling one contract's procurement topology.

    The graph captures the structural relationships that SHOULD exist
    in healthy procurement and identifies where they're broken.
    """
    g = TopologicalGraph()

    cid = contract.get('contract_id', 'unknown')
    vendor = contract.get('vendor_name', 'unknown_vendor')
    agency = contract.get('agency_name', 'unknown_agency')
    amount = contract.get('award_amount', 0)

    # === Core Nodes ===
    g.add_node(label=f"Contract:{cid}", node_id=_node_id("contract", cid))
    g.add_node(label=f"Vendor:{vendor}", node_id=_node_id("vendor", vendor))
    g.add_node(label=f"Agency:{agency}", node_id=_node_id("agency", agency))

    contract_nid = _node_id("contract", cid)
    vendor_nid = _node_id("vendor", vendor)
    agency_nid = _node_id("agency", agency)

    # === EXPRESS: Agency awards contract to vendor ===
    g.add_edge(agency_nid, contract_nid, EdgeType.EXPRESSES, weight=1.0)
    g.add_edge(contract_nid, vendor_nid, EdgeType.EXPRESSES, weight=1.0)

    # === MIRRORS: Price comparison ===
    if comparables and len(comparables) >= 3:
        sorted_comp = sorted(comparables)
        mid = len(sorted_comp) // 2
        if len(sorted_comp) % 2 == 0:
            median_price = (sorted_comp[mid - 1] + sorted_comp[mid]) / 2.0
        else:
            median_price = float(sorted_comp[mid])

        market_nid = _node_id("market", cid)
        g.add_node(label=f"MarketPrice:{median_price:.0f}", node_id=market_nid)

        if median_price > 0:
            ratio = amount / median_price
            mirror_weight = 1.0 / (1.0 + abs(ratio - 1.0))
        else:
            mirror_weight = 0.0

        g.add_edge(contract_nid, market_nid, EdgeType.MIRRORS, weight=mirror_weight)

        # Extreme divergence = contradiction
        if median_price > 0 and amount / median_price > 2.0:
            g.add_edge(
                contract_nid, market_nid, EdgeType.REMOVES,
                weight=min(amount / median_price - 1.0, 5.0),
            )

    # === BOUNDS: Competitive threshold ===
    threshold_nid = _node_id("threshold", f"{cid}_competitive")
    g.add_node(label="Threshold:CompetitiveBid", node_id=threshold_nid)

    is_sole_source = contract.get('is_sole_source', False)
    procurement_method = contract.get('procurement_method')

    if procurement_method in ('direct', 'limited') or is_sole_source:
        g.add_edge(contract_nid, threshold_nid, EdgeType.REMOVES, weight=2.0)
    else:
        g.add_edge(threshold_nid, contract_nid, EdgeType.BOUNDS, weight=1.0)

    # === VERIFIES / REMOVES: Competition ===
    num_offers = contract.get('num_offers')
    if num_offers is not None and num_offers > 1:
        comp_nid = _node_id("verify", f"{cid}_competition")
        g.add_node(label=f"Competition:{num_offers}bids", node_id=comp_nid)
        g.add_edge(
            comp_nid, contract_nid, EdgeType.VERIFIES,
            weight=min(num_offers / 3.0, 2.0),
        )
        # Rejected bids = evidence of competition
        rej_nid = _node_id("rejected", cid)
        g.add_node(label=f"RejectedBids:{num_offers - 1}", node_id=rej_nid)
        g.add_edge(rej_nid, vendor_nid, EdgeType.REMOVES, weight=1.0)
        g.add_edge(rej_nid, contract_nid, EdgeType.VERIFIES, weight=0.5)

    elif num_offers == 1:
        sb_nid = _node_id("flag", f"{cid}_single_bid")
        g.add_node(label="SingleBid:NoCompetition", node_id=sb_nid)
        g.add_edge(sb_nid, contract_nid, EdgeType.SEEKS, weight=0.5)
        g.add_edge(sb_nid, threshold_nid, EdgeType.REMOVES, weight=1.5)

    # === BOUNDS: Timeline constraints ===
    tender_days = contract.get('tender_period_days')
    if tender_days is not None:
        tl_nid = _node_id("timeline", f"{cid}_tender")
        g.add_node(label=f"TenderPeriod:{tender_days:.0f}days", node_id=tl_nid)
        if tender_days >= 15.0:
            g.add_edge(tl_nid, contract_nid, EdgeType.BOUNDS, weight=1.0, grounded=True)
        elif tender_days < 7:
            g.add_edge(tl_nid, contract_nid, EdgeType.REMOVES, weight=3.0)
        else:
            g.add_edge(tl_nid, contract_nid, EdgeType.REMOVES, weight=1.5)

    decision_days = contract.get('decision_period_days')
    if decision_days is not None:
        dec_nid = _node_id("timeline", f"{cid}_decision")
        g.add_node(label=f"DecisionPeriod:{decision_days:.0f}days", node_id=dec_nid)
        if decision_days < 0:
            g.add_edge(dec_nid, contract_nid, EdgeType.REMOVES, weight=4.0)
        elif decision_days < 1:
            g.add_edge(dec_nid, contract_nid, EdgeType.REMOVES, weight=2.5)
        else:
            g.add_edge(dec_nid, contract_nid, EdgeType.VERIFIES, weight=0.5)

    # === INHERITS: Vendor history / concentration ===
    if agency_contracts:
        vendor_contracts = [
            c for c in agency_contracts
            if c.get('vendor_name') == vendor and c.get('contract_id') != cid
        ]
        if vendor_contracts:
            hist_nid = _node_id("history", f"{vendor}_{agency}")
            g.add_node(
                label=f"VendorHistory:{len(vendor_contracts)}contracts",
                node_id=hist_nid,
            )
            g.add_edge(contract_nid, hist_nid, EdgeType.INHERITS, weight=1.0)

            total_agency = len(agency_contracts)
            vendor_share = len(vendor_contracts) / total_agency if total_agency > 0 else 0
            if vendor_share > 0.4:
                g.add_edge(
                    hist_nid, agency_nid, EdgeType.REMOVES,
                    weight=vendor_share * 3.0,
                )

    # === SEEKS / FEEDBACK TRAP: Political donations ===
    has_donations = contract.get('has_donations', False)
    donation_amount = contract.get('donation_amount', 0)
    if has_donations and donation_amount > 0:
        don_nid = _node_id("donation", f"{vendor}_{agency}")
        g.add_node(label=f"Donation:${donation_amount:,.0f}", node_id=don_nid)
        g.add_edge(vendor_nid, don_nid, EdgeType.EXPRESSES, weight=1.0)
        g.add_edge(don_nid, agency_nid, EdgeType.SEEKS, weight=2.0)
        # Creates cycle: vendor -> donation -> agency -> contract -> vendor

    # === INHERITS: Amendment history ===
    amendment_count = contract.get('amendment_count', 0)
    original_value = contract.get('original_value')
    final_value = contract.get('final_value')
    if amendment_count > 0 and original_value and final_value and original_value > 0:
        amend_nid = _node_id("amendment", cid)
        g.add_node(label=f"Amendments:{amendment_count}", node_id=amend_nid)
        value_change = (final_value - original_value) / original_value
        g.add_edge(amend_nid, contract_nid, EdgeType.INHERITS, weight=1.0)
        if value_change > 0.3:
            g.add_edge(
                amend_nid, contract_nid, EdgeType.REMOVES,
                weight=min(value_change * 3.0, 5.0),
            )

    return g


# =============================================================================
# CONTRADICTION ANALYSIS
# =============================================================================

def analyze_contradictions(
    graph: TopologicalGraph,
    contract_id: str,
) -> List[ContradictionEvidence]:
    """
    Analyze a procurement graph for topological contradictions.
    Each contradiction type maps to a specific fraud pattern.
    """
    contradictions: List[ContradictionEvidence] = []
    nodes = graph.nodes
    contract_nid = _node_id("contract", contract_id)

    if not nodes:
        return contradictions

    # --- 1. REMOVES edges = direct contradictions ---
    for nid, node in nodes.items():
        for edge in node.get_edges_by_type(EdgeType.REMOVES):
            target = nodes.get(edge.target_id)
            if not target:
                continue

            src = node.label
            tgt = target.label

            if "MarketPrice" in tgt or "MarketPrice" in src:
                contradictions.append(ContradictionEvidence(
                    violation_type="price_mirror_break",
                    severity=min(edge.weight / 3.0, 1.0),
                    likelihood_ratio=1.0 + edge.weight,
                    description=(
                        f"Price topology broken: {src} contradicts {tgt}. "
                        f"Contract price diverges from market (weight {edge.weight:.1f})."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES", "MIRRORS"],
                    gate_violated="MIRROR",
                ))

            elif "Threshold" in tgt or "SingleBid" in src:
                contradictions.append(ContradictionEvidence(
                    violation_type="competition_bypass",
                    severity=min(edge.weight / 2.5, 1.0),
                    likelihood_ratio=1.0 + edge.weight * 0.8,
                    description=(
                        f"Competition topology broken: {src} undermines {tgt}. "
                        f"Competitive safeguards circumvented."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES", "BOUNDS"],
                    gate_violated="BOUND",
                ))

            elif "TenderPeriod" in src or "DecisionPeriod" in src:
                contradictions.append(ContradictionEvidence(
                    violation_type="timeline_violation",
                    severity=min(edge.weight / 3.0, 1.0),
                    likelihood_ratio=1.0 + edge.weight * 0.7,
                    description=(
                        f"Timeline topology broken: {src} contradicts normal procedure. "
                        f"Abnormal timing suggests predetermined outcome."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES", "BOUNDS"],
                    gate_violated="BOUND",
                ))

            elif "VendorHistory" in src:
                contradictions.append(ContradictionEvidence(
                    violation_type="vendor_concentration",
                    severity=min(edge.weight / 3.0, 1.0),
                    likelihood_ratio=1.0 + edge.weight * 0.5,
                    description=(
                        f"Vendor topology broken: {src} shows market capture at {tgt}. "
                        f"Single vendor dominates procurement."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES", "INHERITS"],
                    gate_violated="INHERIT",
                ))

            elif "Amendments" in src:
                contradictions.append(ContradictionEvidence(
                    violation_type="amendment_inflation",
                    severity=min(edge.weight / 3.0, 1.0),
                    likelihood_ratio=1.0 + edge.weight * 0.6,
                    description=(
                        f"Amendment topology broken: {src} contradicts original value. "
                        f"Significant post-award value increase."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES", "INHERITS"],
                    gate_violated="INHERIT",
                ))

            elif "RejectedBids" in src:
                # Rejected bids REMOVING a vendor is healthy — skip
                continue

            else:
                contradictions.append(ContradictionEvidence(
                    violation_type="structural_contradiction",
                    severity=min(edge.weight / 3.0, 0.8),
                    likelihood_ratio=1.0 + edge.weight * 0.4,
                    description=f"{src} contradicts {tgt} (weight {edge.weight:.1f})",
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["REMOVES"],
                    gate_violated="REMOVE",
                ))

    # --- 2. Missing VERIFY = unverified award ---
    contract_node = nodes.get(contract_nid)
    if contract_node:
        has_verification = False
        for nid, node in nodes.items():
            for edge in node.get_edges_by_type(EdgeType.VERIFIES):
                if edge.target_id == contract_nid:
                    has_verification = True
                    break
            if has_verification:
                break

        if not has_verification:
            contradictions.append(ContradictionEvidence(
                violation_type="unverified_award",
                severity=0.6,
                likelihood_ratio=2.0,
                description=(
                    f"No VERIFY edge reaches {contract_node.label}. "
                    f"Award has no topological verification — "
                    f"no competition, no audit, no review."
                ),
                nodes_involved=[contract_nid],
                edge_types_involved=["VERIFIES"],
                gate_violated="VERIFY",
            ))

    # --- 3. Feedback traps (cycles through EXPRESS) ---
    health = compute_health(graph)
    for cycle in health.cycles:
        has_express = False
        has_donation = False
        cycle_labels = []
        for nid in cycle[:-1]:
            node = nodes.get(nid)
            if node:
                cycle_labels.append(node.label)
                if "Donation" in node.label:
                    has_donation = True
                for rels in node.edges.values():
                    for rel in rels:
                        if rel.edge_type == EdgeType.EXPRESSES:
                            has_express = True

        if has_express and has_donation:
            contradictions.append(ContradictionEvidence(
                violation_type="pay_to_play_cycle",
                severity=0.9,
                likelihood_ratio=4.0,
                description=(
                    f"Feedback trap: {' -> '.join(cycle_labels)}. "
                    f"Donation creates cycle with contract award — pay-to-play topology."
                ),
                nodes_involved=cycle,
                edge_types_involved=["EXPRESSES", "SEEKS"],
                gate_violated="VERIFY",
            ))
        elif has_express and len(cycle) > 2:
            contradictions.append(ContradictionEvidence(
                violation_type="feedback_trap",
                severity=0.5,
                likelihood_ratio=1.5,
                description=(
                    f"Cycle in procurement topology: {' -> '.join(cycle_labels)}. "
                    f"Self-reinforcing structure without external validation."
                ),
                nodes_involved=cycle,
                edge_types_involved=["EXPRESSES"],
                gate_violated="VERIFY",
            ))

    # --- 4. Vendor bottleneck (star topology) ---
    if len(nodes) >= 4:
        btwn = betweenness_centrality(graph)
        for nid, score in btwn.items():
            node = nodes.get(nid)
            if node and score > 0.4 and "Vendor" in node.label:
                contradictions.append(ContradictionEvidence(
                    violation_type="vendor_bottleneck",
                    severity=min(score, 1.0),
                    likelihood_ratio=1.0 + score,
                    description=(
                        f"{node.label} has betweenness centrality {score:.2f} — "
                        f"single point of failure in procurement topology."
                    ),
                    nodes_involved=[nid],
                    edge_types_involved=["EXPRESSES", "INHERITS"],
                    gate_violated="BOUND",
                ))

    # --- 5. High-weight SEEKS = unproven assumptions ---
    for nid, node in nodes.items():
        for edge in node.get_edges_by_type(EdgeType.SEEKS):
            target = nodes.get(edge.target_id)
            if target and edge.weight > 1.0:
                contradictions.append(ContradictionEvidence(
                    violation_type="unproven_relationship",
                    severity=min(edge.weight / 3.0, 0.5),
                    likelihood_ratio=1.0 + edge.weight * 0.3,
                    description=(
                        f"{node.label} -> {target.label} is assumed but unproven "
                        f"(SEEKS, weight {edge.weight:.1f})."
                    ),
                    nodes_involved=[nid, edge.target_id],
                    edge_types_involved=["SEEKS"],
                    gate_violated="SEEK",
                ))

    return contradictions


# =============================================================================
# TOPOLOGICAL METRICS
# =============================================================================

def _compute_edge_type_entropy(graph: TopologicalGraph) -> float:
    """Shannon entropy of edge type distribution, normalized 0-1."""
    return _edge_type_entropy(graph)


def _compute_designedness(graph: TopologicalGraph) -> float:
    """How 'designed' the procurement topology looks. Higher = more structured oversight."""
    nodes = graph.nodes
    total_edges = graph.total_edge_count()

    if total_edges == 0:
        return 0.0

    edge_type_counts = graph.edge_type_counts()
    ete = _edge_type_entropy(graph)

    verifies = edge_type_counts.get("VERIFIES", 0)
    expresses = edge_type_counts.get("EXPRESSES", 0)
    verify_coverage = min(verifies / max(expresses, 1), 1.0)

    removes = edge_type_counts.get("REMOVES", 0)
    contradiction_density = removes / total_edges
    contradiction_balance = max(0.0, 1.0 - abs(contradiction_density - 0.10) * 5)

    bounds = edge_type_counts.get("BOUNDS", 0)
    bounds_coverage = min(bounds / max(expresses, 1), 1.0)

    return (
        ete * 0.25 +
        verify_coverage * 0.30 +
        bounds_coverage * 0.20 +
        contradiction_balance * 0.15 +
        min(1.0, len(nodes) / 10.0) * 0.10
    )


# =============================================================================
# CLASSIFY PROCUREMENT — high-level TCA verdict
# =============================================================================

def classify_procurement(
    contract: Dict[str, Any],
    comparables: List[float],
    agency_contracts: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    High-level procurement classification using TCA topology.

    Returns a dict with verdict, contradiction flags, and structural metrics.
    This replaces the old heuristic build_contract_graph pattern matching.
    """
    graph = build_contract_graph(contract, comparables, agency_contracts)
    contradictions = analyze_contradictions(graph, contract.get('contract_id', 'unknown'))

    flags = set()
    for c in contradictions:
        if c.violation_type == "price_mirror_break":
            flags.add("PRICE_MIRROR_BREAK")
        elif c.violation_type == "competition_bypass":
            flags.add("NO_COMPETITION")
        elif c.violation_type == "vendor_concentration":
            flags.add("VENDOR_CONCENTRATION")
        elif c.violation_type == "timeline_violation":
            flags.add("FISCAL_TRAP")
        elif c.violation_type == "unverified_award":
            flags.add("SOLE_SOURCE")
        elif c.violation_type == "pay_to_play_cycle":
            flags.add("PAY_TO_PLAY")
        elif c.violation_type == "amendment_inflation":
            flags.add("AMENDMENT_INFLATION")

    n = len(flags)
    if n == 0:
        verdict = "HONEST"
    elif n <= 2:
        verdict = "SUSPICIOUS"
    else:
        verdict = "STRUCTURALLY_FRAUDULENT"

    return {
        "verdict": verdict,
        "flags": sorted(flags),
        "flag_count": n,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "graph": graph,
    }


# =============================================================================
# TCA SCORING FUNCTION
# =============================================================================

def score_contract_tca(
    contract: Dict[str, Any],
    comparables: List[float],
    agency_contracts: List[Dict[str, Any]] = None,
) -> TCAScore:
    """
    TCA-based fraud risk scoring for a single contract.

    Models the contract's procurement topology, finds contradictions,
    and converts them to a risk score with evidence trails.

    Returns a TCAScore whose likelihood_ratio integrates with the
    existing Bayesian pipeline.
    """
    cid = contract.get('contract_id', 'unknown')

    graph = build_contract_graph(contract, comparables, agency_contracts)
    contradictions = analyze_contradictions(graph, cid)

    health = compute_health(graph)
    ete = _compute_edge_type_entropy(graph)
    designedness = _compute_designedness(graph)

    # --- Score computation ---
    if not contradictions:
        risk_score = 0.0
        combined_lr = 0.8  # Slight evidence AGAINST fraud
    else:
        total_severity = sum(c.severity for c in contradictions)
        max_severity = max(c.severity for c in contradictions)

        # Risk = weighted blend of worst contradiction and total load
        risk_score = min(
            1.0,
            max_severity * 0.6 + (total_severity / max(len(contradictions) * 2, 1)) * 0.4,
        )

        # Multiply individual LRs (capped to prevent runaway)
        combined_lr = 1.0
        for c in contradictions:
            combined_lr *= c.likelihood_ratio
        combined_lr = min(combined_lr, 50.0)

    # Low designedness = less oversight = amplify risk
    if designedness < 0.3:
        risk_score = min(1.0, risk_score * 1.2)
        combined_lr *= 1.1

    critical_count = sum(1 for c in contradictions if c.is_critical)
    if critical_count >= 2 or risk_score >= 0.7:
        verdict = "structurally_fraudulent"
    elif len(contradictions) >= 2 or risk_score >= 0.4:
        verdict = "suspicious"
    else:
        verdict = "clean"

    return TCAScore(
        tca_risk_score=round(risk_score, 4),
        tca_likelihood_ratio=round(combined_lr, 4),
        contradiction_count=len(contradictions),
        critical_contradiction_count=critical_count,
        contradictions=contradictions,
        topological_health={
            "cycles": health.cycle_count,
            "bridges": health.bridge_count,
            "isolated": health.isolation_count,
            "node_count": graph.node_count,
            "edge_count": graph.total_edge_count(),
        },
        verdict=verdict,
        edge_type_entropy=round(ete, 4),
        designedness=round(designedness, 4),
    )


# =============================================================================
# ECOSYSTEM-LEVEL ANALYSIS (BATCH)
# =============================================================================

def build_ecosystem_graph(
    contracts: List[Dict[str, Any]],
    agency_name: str,
) -> TopologicalGraph:
    """
    Build a TCA graph for an entire agency's procurement ecosystem.
    Captures cross-contract patterns: vendor networks, split purchases,
    temporal clustering.
    """
    g = TopologicalGraph()

    agency_nid = _node_id("agency", agency_name)
    g.add_node(label=f"Agency:{agency_name}", node_id=agency_nid)

    vendor_nodes: Dict[str, str] = {}

    for contract in contracts:
        cid = contract.get('contract_id', 'unknown')
        vendor = contract.get('vendor_name', 'unknown')
        amount = contract.get('award_amount', 0)

        c_nid = _node_id("contract", cid)
        g.add_node(label=f"C:{cid}:{amount:.0f}", node_id=c_nid)
        g.add_edge(agency_nid, c_nid, EdgeType.EXPRESSES, weight=1.0)

        if vendor not in vendor_nodes:
            v_nid = _node_id("vendor", vendor)
            g.add_node(label=f"V:{vendor}", node_id=v_nid)
            vendor_nodes[vendor] = v_nid

        g.add_edge(c_nid, vendor_nodes[vendor], EdgeType.EXPRESSES, weight=1.0)
        g.add_edge(vendor_nodes[vendor], agency_nid, EdgeType.INHERITS, weight=0.5)

        if contract.get('has_donations', False):
            don_nid = _node_id("donation", f"{vendor}_{agency_name}")
            if not g.get_node(don_nid):
                g.add_node(label=f"Donation:{vendor}", node_id=don_nid)
                g.add_edge(vendor_nodes[vendor], don_nid, EdgeType.EXPRESSES, weight=1.0)
                g.add_edge(don_nid, agency_nid, EdgeType.SEEKS, weight=2.0)

    return g


def analyze_ecosystem(
    contracts: List[Dict[str, Any]],
    agency_name: str,
) -> Dict[str, Any]:
    """
    Run TCA analysis on an agency's procurement ecosystem.
    Returns systemic risk: vendor concentration, pay-to-play, fragility.
    """
    graph = build_ecosystem_graph(contracts, agency_name)
    nodes = graph.nodes

    if len(nodes) < 3:
        return {"verdict": "insufficient_data", "contracts": len(contracts)}

    health = compute_health(graph)
    ete = _edge_type_entropy(graph)
    btwn = betweenness_centrality(graph)

    vendor_bottlenecks = []
    for nid, score in btwn.items():
        node = nodes.get(nid)
        if node and score > 0.3 and node.label.startswith("V:"):
            vendor_bottlenecks.append({
                "vendor": node.label[2:],
                "betweenness": round(score, 4),
            })

    pay_to_play = []
    for cycle in health.cycles:
        labels = [nodes[nid].label if nid in nodes else nid for nid in cycle[:-1]]
        has_donation = any("Donation" in label for label in labels)
        has_agency = any("Agency" in label for label in labels)
        if has_donation and has_agency:
            pay_to_play.append({"cycle": labels, "length": len(cycle) - 1})

    if len(pay_to_play) > 0:
        verdict = "critical"
    elif len(vendor_bottlenecks) > 2:
        verdict = "fragile"
    elif health.cycle_count > 3:
        verdict = "suspicious"
    else:
        verdict = "healthy"

    return {
        "agency": agency_name,
        "contracts_analyzed": len(contracts),
        "node_count": graph.node_count,
        "edge_count": graph.total_edge_count(),
        "verdict": verdict,
        "edge_type_entropy": round(ete, 4),
        "cycles": health.cycle_count,
        "bridges": health.bridge_count,
        "vendor_bottlenecks": vendor_bottlenecks,
        "pay_to_play_cycles": pay_to_play,
    }


# =============================================================================
# PIPELINE INTEGRATION HELPER
# =============================================================================

def tca_score_for_pipeline(
    contract: Dict,
    comparables: List[float],
    agency_contracts: List[Dict[str, Any]] = None,
) -> Tuple[float, float, Dict]:
    """
    Simplified interface for institutional_pipeline.py.

    Returns:
        (tca_risk_score, tca_likelihood_ratio, tca_details_dict)
    """
    tca = score_contract_tca(contract, comparables, agency_contracts)

    details = {
        "risk_score": tca.tca_risk_score,
        "likelihood_ratio": tca.tca_likelihood_ratio,
        "contradiction_count": tca.contradiction_count,
        "critical_count": tca.critical_contradiction_count,
        "verdict": tca.verdict,
        "entropy": tca.edge_type_entropy,
        "designedness": tca.designedness,
        "health": tca.topological_health,
        "violations": [
            {
                "type": c.violation_type,
                "severity": round(c.severity, 4),
                "lr": round(c.likelihood_ratio, 4),
                "gate": c.gate_violated,
                "description": c.description,
            }
            for c in tca.contradictions
        ],
    }

    return tca.tca_risk_score, tca.tca_likelihood_ratio, details
