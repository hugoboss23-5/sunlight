"""
Standalone Topological Contradiction Analysis (TCA) Engine.

Zero external dependencies. Pure Python + stdlib.

Models any system as a typed directed graph with 7 edge types derived from
the chestohedron gate cycle: MIRRORS, INHERITS, BOUNDS, EXPRESSES, VERIFIES,
REMOVES, SEEKS. Analysis detects structural contradictions, feedback traps,
bottlenecks, and dead ends. solve() inverts: given a broken topology, it
prescribes the minimum structural changes to restore health.

The 7 edge types are non-negotiable. They are the irreducible set of
relationships in any designed system.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# EDGE TYPES — the 7 irreducible relationships
# =============================================================================

class EdgeType(Enum):
    MIRRORS = "MIRRORS"
    INHERITS = "INHERITS"
    BOUNDS = "BOUNDS"
    EXPRESSES = "EXPRESSES"
    VERIFIES = "VERIFIES"
    REMOVES = "REMOVES"
    SEEKS = "SEEKS"


# =============================================================================
# GRAPH PRIMITIVES
# =============================================================================

@dataclass
class EdgeRelation:
    """A typed, weighted, directed edge."""
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    grounded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TopologicalNode:
    """A node in the TCA graph."""
    node_id: str
    label: str
    edges: Dict[str, List[EdgeRelation]] = field(default_factory=lambda: defaultdict(list))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_edge(self, relation: EdgeRelation) -> None:
        self.edges[relation.edge_type.value].append(relation)

    def get_edges_by_type(self, edge_type: EdgeType) -> List[EdgeRelation]:
        return self.edges.get(edge_type.value, [])

    def all_edges(self) -> List[EdgeRelation]:
        out: List[EdgeRelation] = []
        for rels in self.edges.values():
            out.extend(rels)
        return out

    @property
    def degree(self) -> int:
        return sum(len(rels) for rels in self.edges.values())


class TopologicalGraph:
    """Directed typed graph — the substrate for TCA analysis."""

    def __init__(self) -> None:
        self._nodes: Dict[str, TopologicalNode] = {}

    @property
    def nodes(self) -> Dict[str, TopologicalNode]:
        return self._nodes

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def add_node(self, label: str, node_id: Optional[str] = None,
                 metadata: Optional[Dict] = None) -> TopologicalNode:
        nid = node_id or label
        if nid not in self._nodes:
            self._nodes[nid] = TopologicalNode(
                node_id=nid, label=label,
                metadata=metadata or {},
            )
        return self._nodes[nid]

    def get_node(self, node_id: str) -> Optional[TopologicalNode]:
        return self._nodes.get(node_id)

    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType,
                 weight: float = 1.0, grounded: bool = False,
                 metadata: Optional[Dict] = None) -> None:
        src = self._nodes.get(source_id)
        if src is None:
            src = self.add_node(label=source_id, node_id=source_id)
        if target_id not in self._nodes:
            self.add_node(label=target_id, node_id=target_id)
        src.add_edge(EdgeRelation(
            target_id=target_id, edge_type=edge_type,
            weight=weight, grounded=grounded,
            metadata=metadata or {},
        ))

    def total_edge_count(self) -> int:
        return sum(n.degree for n in self._nodes.values())

    def edge_type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {et.value: 0 for et in EdgeType}
        for node in self._nodes.values():
            for rels in node.edges.values():
                for rel in rels:
                    counts[rel.edge_type.value] += len([rel])
        return counts

    def adjacency_list(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = defaultdict(list)
        for nid, node in self._nodes.items():
            for rel in node.all_edges():
                adj[nid].append(rel.target_id)
        return dict(adj)

    def reverse_adjacency(self) -> Dict[str, List[str]]:
        rev: Dict[str, List[str]] = defaultdict(list)
        for nid, node in self._nodes.items():
            for rel in node.all_edges():
                rev[rel.target_id].append(nid)
        return dict(rev)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {
                nid: {
                    "label": n.label,
                    "edges": {
                        et: [{"target": r.target_id, "weight": r.weight,
                              "grounded": r.grounded} for r in rels]
                        for et, rels in n.edges.items()
                    },
                    "metadata": n.metadata,
                }
                for nid, n in self._nodes.items()
            },
            "node_count": self.node_count,
            "edge_count": self.total_edge_count(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopologicalGraph":
        g = cls()
        for nid, ndata in data.get("nodes", {}).items():
            g.add_node(label=ndata.get("label", nid), node_id=nid,
                       metadata=ndata.get("metadata", {}))
        for nid, ndata in data.get("nodes", {}).items():
            for et_str, edges in ndata.get("edges", {}).items():
                try:
                    et = EdgeType(et_str)
                except ValueError:
                    continue
                for e in edges:
                    g.add_edge(nid, e["target"], et,
                               weight=e.get("weight", 1.0),
                               grounded=e.get("grounded", False))
        return g


# =============================================================================
# CYCLE DETECTION (DFS-based)
# =============================================================================

def detect_cycles(graph: TopologicalGraph) -> List[List[str]]:
    """Find all simple cycles in the graph using Johnson's-style DFS."""
    adj = graph.adjacency_list()
    all_nodes = list(graph.nodes.keys())
    cycles: List[List[str]] = []
    visited_global: Set[frozenset] = set()

    for start in all_nodes:
        stack: List[Tuple[str, List[str], Set[str]]] = [(start, [start], {start})]
        while stack:
            current, path, visited = stack.pop()
            for neighbor in adj.get(current, []):
                if neighbor == start and len(path) > 1:
                    cycle = path + [start]
                    sig = frozenset(zip(cycle[:-1], cycle[1:]))
                    if sig not in visited_global:
                        visited_global.add(sig)
                        cycles.append(cycle)
                elif neighbor not in visited and neighbor >= start:
                    stack.append((neighbor, path + [neighbor], visited | {neighbor}))
    return cycles


# =============================================================================
# BRIDGE DETECTION
# =============================================================================

def detect_bridges(graph: TopologicalGraph) -> List[Tuple[str, str]]:
    """Find bridge edges whose removal disconnects the undirected version."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            adj[nid].add(rel.target_id)
            adj[rel.target_id].add(nid)

    disc: Dict[str, int] = {}
    low: Dict[str, int] = {}
    bridges: List[Tuple[str, str]] = []
    timer = [0]

    def dfs(u: str, parent: Optional[str]) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in adj.get(u, set()):
            if v not in disc:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.append((u, v))
            elif v != parent:
                low[u] = min(low[u], disc[v])

    for n in graph.nodes:
        if n not in disc:
            dfs(n, None)

    return bridges


# =============================================================================
# ISOLATION DETECTION
# =============================================================================

def detect_isolated(graph: TopologicalGraph) -> List[str]:
    """Find nodes with no incoming or outgoing edges."""
    has_outgoing = set()
    has_incoming = set()
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            has_outgoing.add(nid)
            has_incoming.add(rel.target_id)
    return [nid for nid in graph.nodes if nid not in has_outgoing and nid not in has_incoming]


# =============================================================================
# BETWEENNESS CENTRALITY
# =============================================================================

def betweenness_centrality(graph: TopologicalGraph) -> Dict[str, float]:
    """Brandes' algorithm for betweenness centrality on directed graph."""
    nodes = list(graph.nodes.keys())
    adj = graph.adjacency_list()
    cb: Dict[str, float] = {n: 0.0 for n in nodes}

    for s in nodes:
        S: List[str] = []
        P: Dict[str, List[str]] = {n: [] for n in nodes}
        sigma: Dict[str, int] = {n: 0 for n in nodes}
        sigma[s] = 1
        d: Dict[str, int] = {n: -1 for n in nodes}
        d[s] = 0
        Q: deque = deque([s])

        while Q:
            v = Q.popleft()
            S.append(v)
            for w in adj.get(v, []):
                if w not in d or d[w] < 0:
                    if w in d:
                        pass
                    else:
                        d[w] = -1
                    if d[w] < 0:
                        Q.append(w)
                        d[w] = d[v] + 1
                if d.get(w, -1) == d[v] + 1:
                    sigma[w] = sigma.get(w, 0) + sigma[v]
                    P[w].append(v)

        delta: Dict[str, float] = {n: 0.0 for n in nodes}
        while S:
            w = S.pop()
            for v in P.get(w, []):
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]

    n = len(nodes)
    if n > 2:
        norm = 1.0 / ((n - 1) * (n - 2))
        for k in cb:
            cb[k] *= norm

    return cb


# =============================================================================
# HEALTH COMPUTATION
# =============================================================================

@dataclass
class GraphHealth:
    """Structural health metrics for a TCA graph."""
    cycles: List[List[str]]
    cycle_count: int
    bridges: List[Tuple[str, str]]
    bridge_count: int
    isolated: List[str]
    isolation_count: int
    clustering: float


def _clustering_coefficient(graph: TopologicalGraph) -> float:
    """Average local clustering coefficient (undirected interpretation)."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            adj[nid].add(rel.target_id)
            adj[rel.target_id].add(nid)

    if not adj:
        return 0.0

    coeffs: List[float] = []
    for v, neighbors in adj.items():
        k = len(neighbors)
        if k < 2:
            coeffs.append(0.0)
            continue
        links = 0
        nlist = list(neighbors)
        for i in range(len(nlist)):
            for j in range(i + 1, len(nlist)):
                if nlist[j] in adj.get(nlist[i], set()):
                    links += 1
        coeffs.append(2.0 * links / (k * (k - 1)))

    return sum(coeffs) / len(coeffs) if coeffs else 0.0


def compute_health(graph: TopologicalGraph) -> GraphHealth:
    """Compute full structural health of a TCA graph."""
    cycles = detect_cycles(graph)
    bridges = detect_bridges(graph)
    isolated = detect_isolated(graph)
    clustering = _clustering_coefficient(graph)

    return GraphHealth(
        cycles=cycles,
        cycle_count=len(cycles),
        bridges=bridges,
        bridge_count=len(bridges),
        isolated=isolated,
        isolation_count=len(isolated),
        clustering=clustering,
    )


# =============================================================================
# ANALYZE — the main TCA diagnostic
# =============================================================================

@dataclass
class TCAAnalysis:
    """Full TCA analysis result for any system graph."""
    confidence: float
    contradiction_count: int
    contradictions: List[Dict[str, Any]]
    feedback_traps: List[List[str]]
    dead_ends: List[str]
    star_topologies: List[Dict[str, Any]]
    load_bearing_nodes: List[Dict[str, Any]]
    grounding_ratio: float
    edge_type_entropy: float
    health: GraphHealth
    centrality: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": self.confidence,
            "contradiction_count": self.contradiction_count,
            "contradictions": self.contradictions,
            "feedback_traps": [list(c) for c in self.feedback_traps],
            "dead_ends": self.dead_ends,
            "star_topologies": self.star_topologies,
            "load_bearing_nodes": self.load_bearing_nodes,
            "grounding_ratio": self.grounding_ratio,
            "edge_type_entropy": self.edge_type_entropy,
            "health": {
                "cycle_count": self.health.cycle_count,
                "bridge_count": self.health.bridge_count,
                "isolation_count": self.health.isolation_count,
                "clustering": round(self.health.clustering, 4),
            },
        }


def _edge_type_entropy(graph: TopologicalGraph) -> float:
    """Shannon entropy of edge type distribution, normalized 0-1."""
    counts: Dict[str, int] = {et.value: 0 for et in EdgeType}
    total = 0
    for node in graph.nodes.values():
        for rels in node.edges.values():
            for rel in rels:
                counts[rel.edge_type.value] += 1
                total += 1
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    max_entropy = math.log2(len(EdgeType))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _find_contradictions(graph: TopologicalGraph) -> List[Dict[str, Any]]:
    """Find structural contradictions: REMOVES edges opposing other edge types."""
    contradictions: List[Dict[str, Any]] = []
    for nid, node in graph.nodes.items():
        for rel in node.get_edges_by_type(EdgeType.REMOVES):
            target = graph.get_node(rel.target_id)
            if not target:
                continue
            opposing = []
            # Check if source->target has non-REMOVES edges too (direct contradiction)
            for other_rel in node.all_edges():
                if (other_rel.target_id == rel.target_id and
                        other_rel.edge_type != EdgeType.REMOVES):
                    opposing.append(other_rel.edge_type.value)
            # Check if any other node has positive edges to target
            for other_nid, other_node in graph.nodes.items():
                if other_nid == nid:
                    continue
                for other_rel in other_node.all_edges():
                    if (other_rel.target_id == rel.target_id and
                            other_rel.edge_type in (EdgeType.VERIFIES, EdgeType.BOUNDS,
                                                     EdgeType.EXPRESSES)):
                        opposing.append(f"{other_nid}:{other_rel.edge_type.value}")

            contradictions.append({
                "source": nid,
                "target": rel.target_id,
                "weight": rel.weight,
                "opposing_edges": opposing,
                "severity": min(rel.weight / 3.0, 1.0),
            })
    return contradictions


def _find_dead_ends(graph: TopologicalGraph) -> List[str]:
    """Nodes with incoming edges but no outgoing edges (sinks)."""
    has_outgoing = set()
    has_incoming = set()
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            has_outgoing.add(nid)
            has_incoming.add(rel.target_id)
    return [nid for nid in graph.nodes if nid in has_incoming and nid not in has_outgoing]


def _find_star_topologies(graph: TopologicalGraph,
                          threshold: float = 0.3) -> List[Dict[str, Any]]:
    """Nodes where betweenness centrality indicates a bottleneck."""
    btwn = betweenness_centrality(graph)
    stars: List[Dict[str, Any]] = []
    for nid, score in btwn.items():
        if score > threshold:
            node = graph.get_node(nid)
            stars.append({
                "node_id": nid,
                "label": node.label if node else nid,
                "betweenness": round(score, 4),
                "degree": node.degree if node else 0,
            })
    return sorted(stars, key=lambda x: x["betweenness"], reverse=True)


def _find_load_bearing(graph: TopologicalGraph) -> List[Dict[str, Any]]:
    """Nodes whose removal would disconnect the graph (articulation points)."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            adj[nid].add(rel.target_id)
            adj[rel.target_id].add(nid)

    disc: Dict[str, int] = {}
    low: Dict[str, int] = {}
    parent: Dict[str, Optional[str]] = {}
    ap: Set[str] = set()
    timer = [0]

    def dfs(u: str) -> None:
        children = 0
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in adj.get(u, set()):
            if v not in disc:
                children += 1
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])
                if parent.get(u) is None and children > 1:
                    ap.add(u)
                if parent.get(u) is not None and low[v] >= disc[u]:
                    ap.add(u)
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])

    for n in graph.nodes:
        if n not in disc:
            parent[n] = None
            dfs(n)

    result: List[Dict[str, Any]] = []
    for nid in ap:
        node = graph.get_node(nid)
        result.append({
            "node_id": nid,
            "label": node.label if node else nid,
            "degree": node.degree if node else 0,
        })
    return result


def _grounding_ratio(graph: TopologicalGraph) -> float:
    """Fraction of edges that are grounded (anchored to external evidence)."""
    total = 0
    grounded = 0
    for node in graph.nodes.values():
        for rel in node.all_edges():
            total += 1
            if rel.grounded:
                grounded += 1
    return grounded / total if total > 0 else 0.0


def analyze(graph: TopologicalGraph) -> TCAAnalysis:
    """
    Full TCA analysis of a typed graph.

    Returns structural diagnostics: contradictions, feedback traps,
    dead ends, star topologies, load-bearing nodes, grounding ratio,
    edge type entropy, and graph health metrics.
    """
    health = compute_health(graph)
    contradictions = _find_contradictions(graph)
    dead_ends = _find_dead_ends(graph)
    stars = _find_star_topologies(graph)
    load_bearing = _find_load_bearing(graph)
    grounding = _grounding_ratio(graph)
    entropy = _edge_type_entropy(graph)
    centrality = betweenness_centrality(graph)

    # Feedback traps = cycles containing EXPRESSES or SEEKS edges
    feedback_traps: List[List[str]] = []
    for cycle in health.cycles:
        cycle_edges_types: Set[str] = set()
        for i in range(len(cycle) - 1):
            src_node = graph.get_node(cycle[i])
            if src_node:
                for rel in src_node.all_edges():
                    if rel.target_id == cycle[i + 1]:
                        cycle_edges_types.add(rel.edge_type.value)
        if "EXPRESSES" in cycle_edges_types or "SEEKS" in cycle_edges_types:
            feedback_traps.append(cycle)

    # Confidence: high entropy + low contradictions + high grounding = high confidence
    contradiction_penalty = min(len(contradictions) * 0.1, 0.5)
    trap_penalty = min(len(feedback_traps) * 0.15, 0.3)
    confidence = max(0.0, min(1.0,
        entropy * 0.3 + grounding * 0.3 + (1 - contradiction_penalty) * 0.25 +
        (1 - trap_penalty) * 0.15
    ))

    return TCAAnalysis(
        confidence=round(confidence, 4),
        contradiction_count=len(contradictions),
        contradictions=contradictions,
        feedback_traps=feedback_traps,
        dead_ends=dead_ends,
        star_topologies=stars,
        load_bearing_nodes=load_bearing,
        grounding_ratio=round(grounding, 4),
        edge_type_entropy=round(entropy, 4),
        health=health,
        centrality=centrality,
    )


# =============================================================================
# CASCADE ANALYSIS — what breaks if a node is removed
# =============================================================================

@dataclass
class CascadeResult:
    """Impact analysis of removing a node."""
    removed_node: str
    edges_lost: int
    nodes_disconnected: List[str]
    contradiction_delta: int
    new_dead_ends: List[str]


def cascade_analysis(graph: TopologicalGraph, node_id: str) -> CascadeResult:
    """
    Simulate removing a node and measure the structural impact.
    Does not modify the original graph.
    """
    if node_id not in graph.nodes:
        return CascadeResult(
            removed_node=node_id, edges_lost=0,
            nodes_disconnected=[], contradiction_delta=0, new_dead_ends=[],
        )

    # Count edges lost
    target_node = graph.nodes[node_id]
    edges_lost = target_node.degree
    for nid, node in graph.nodes.items():
        if nid == node_id:
            continue
        for rel in node.all_edges():
            if rel.target_id == node_id:
                edges_lost += 1

    # Build reduced adjacency and find disconnected components
    adj_before: Dict[str, Set[str]] = defaultdict(set)
    adj_after: Dict[str, Set[str]] = defaultdict(set)
    for nid, node in graph.nodes.items():
        for rel in node.all_edges():
            adj_before[nid].add(rel.target_id)
            adj_before[rel.target_id].add(nid)
            if nid != node_id and rel.target_id != node_id:
                adj_after[nid].add(rel.target_id)
                adj_after[rel.target_id].add(nid)

    remaining = [n for n in graph.nodes if n != node_id]
    if not remaining:
        return CascadeResult(
            removed_node=node_id, edges_lost=edges_lost,
            nodes_disconnected=[], contradiction_delta=0, new_dead_ends=[],
        )

    # BFS to find connected component from first remaining node
    visited: Set[str] = set()
    queue = deque([remaining[0]])
    visited.add(remaining[0])
    while queue:
        v = queue.popleft()
        for w in adj_after.get(v, set()):
            if w not in visited and w in graph.nodes and w != node_id:
                visited.add(w)
                queue.append(w)

    disconnected = [n for n in remaining if n not in visited]

    # Contradiction delta
    contradictions_before = len(_find_contradictions(graph))

    # New dead ends
    outgoing_after: Set[str] = set()
    incoming_after: Set[str] = set()
    for nid, node in graph.nodes.items():
        if nid == node_id:
            continue
        for rel in node.all_edges():
            if rel.target_id != node_id:
                outgoing_after.add(nid)
                incoming_after.add(rel.target_id)

    dead_before = set(_find_dead_ends(graph))
    dead_after = {nid for nid in graph.nodes
                  if nid != node_id and nid in incoming_after and nid not in outgoing_after}
    new_dead_ends = list(dead_after - dead_before)

    return CascadeResult(
        removed_node=node_id,
        edges_lost=edges_lost,
        nodes_disconnected=disconnected,
        contradiction_delta=-contradictions_before,  # All contradictions involving this node vanish
        new_dead_ends=new_dead_ends,
    )


# =============================================================================
# STRUCTURAL DELTA — compare two graphs
# =============================================================================

@dataclass
class StructuralDelta:
    """Difference between two TCA graphs."""
    nodes_added: List[str]
    nodes_removed: List[str]
    edges_added: List[Dict[str, Any]]
    edges_removed: List[Dict[str, Any]]
    entropy_delta: float
    contradiction_delta: int
    confidence_delta: float


def structural_delta(graph_a: TopologicalGraph,
                     graph_b: TopologicalGraph) -> StructuralDelta:
    """Compare two graphs and return structural differences."""
    nodes_a = set(graph_a.nodes.keys())
    nodes_b = set(graph_b.nodes.keys())

    def _edge_set(g: TopologicalGraph) -> Set[Tuple[str, str, str]]:
        edges: Set[Tuple[str, str, str]] = set()
        for nid, node in g.nodes.items():
            for rel in node.all_edges():
                edges.add((nid, rel.target_id, rel.edge_type.value))
        return edges

    edges_a = _edge_set(graph_a)
    edges_b = _edge_set(graph_b)

    analysis_a = analyze(graph_a)
    analysis_b = analyze(graph_b)

    return StructuralDelta(
        nodes_added=list(nodes_b - nodes_a),
        nodes_removed=list(nodes_a - nodes_b),
        edges_added=[{"source": s, "target": t, "type": et}
                     for s, t, et in edges_b - edges_a],
        edges_removed=[{"source": s, "target": t, "type": et}
                       for s, t, et in edges_a - edges_b],
        entropy_delta=round(analysis_b.edge_type_entropy - analysis_a.edge_type_entropy, 4),
        contradiction_delta=analysis_b.contradiction_count - analysis_a.contradiction_count,
        confidence_delta=round(analysis_b.confidence - analysis_a.confidence, 4),
    )


# =============================================================================
# SOLVE — inverse TCA prescriptions
# =============================================================================

@dataclass
class TCAPrescription:
    """A single structural fix recommendation."""
    action: str  # "add_edge", "remove_edge", "add_node", "strengthen", "weaken"
    target: str
    edge_type: Optional[str] = None
    reason: str = ""
    priority: float = 0.0


@dataclass
class TCASolution:
    """Inverse TCA result: what structural changes would restore health."""
    prescriptions: List[TCAPrescription]
    current_confidence: float
    projected_confidence: float
    critical_gaps: List[str]


def solve(graph: TopologicalGraph) -> TCASolution:
    """
    Inverse TCA: given a broken topology, prescribe minimum structural changes.

    Examines contradictions, missing verifications, feedback traps,
    bottlenecks, and dead ends, then generates prioritized prescriptions.
    """
    analysis = analyze(graph)
    prescriptions: List[TCAPrescription] = []
    critical_gaps: List[str] = []

    # 1. Fix contradictions: for each REMOVES edge, suggest adding VERIFIES
    for c in analysis.contradictions:
        prescriptions.append(TCAPrescription(
            action="add_edge",
            target=c["target"],
            edge_type="VERIFIES",
            reason=f"Contradiction at {c['source']}->{c['target']} (weight {c['weight']:.1f}). "
                   f"Add verification to validate or refute.",
            priority=c["severity"],
        ))

    # 2. Fix feedback traps: break cycles by adding BOUNDS
    for trap in analysis.feedback_traps:
        if len(trap) > 1:
            weakest_link = trap[0]  # Simplification: target first node
            prescriptions.append(TCAPrescription(
                action="add_edge",
                target=weakest_link,
                edge_type="BOUNDS",
                reason=f"Feedback trap: {' -> '.join(trap[:4])}{'...' if len(trap) > 4 else ''}. "
                       f"Add constraint to break self-reinforcing cycle.",
                priority=0.8,
            ))
            critical_gaps.append(f"Feedback trap of length {len(trap) - 1}")

    # 3. Fix dead ends: suggest adding outgoing edges
    for dead in analysis.dead_ends:
        node = graph.get_node(dead)
        label = node.label if node else dead
        prescriptions.append(TCAPrescription(
            action="add_edge",
            target=dead,
            edge_type="EXPRESSES",
            reason=f"Dead end: {label} receives input but produces nothing. "
                   f"Add outgoing edge to complete information flow.",
            priority=0.4,
        ))

    # 4. Fix bottlenecks: suggest redundancy
    for star in analysis.star_topologies:
        prescriptions.append(TCAPrescription(
            action="add_node",
            target=star["node_id"],
            reason=f"Bottleneck: {star['label']} (betweenness {star['betweenness']:.2f}). "
                   f"Add parallel path to reduce single-point-of-failure risk.",
            priority=0.6,
        ))

    # 5. Fix low grounding: suggest grounding ungrounded edges
    if analysis.grounding_ratio < 0.3:
        critical_gaps.append(f"Low grounding ratio: {analysis.grounding_ratio:.0%}")
        prescriptions.append(TCAPrescription(
            action="strengthen",
            target="*",
            reason=f"Only {analysis.grounding_ratio:.0%} of edges are grounded. "
                   f"Anchor claims to external evidence.",
            priority=0.7,
        ))

    # 6. Fix low entropy: suggest diversifying edge types
    if analysis.edge_type_entropy < 0.4:
        critical_gaps.append(f"Low edge type entropy: {analysis.edge_type_entropy:.2f}")
        counts = graph.edge_type_counts()
        missing = [et.value for et in EdgeType if counts.get(et.value, 0) == 0]
        if missing:
            prescriptions.append(TCAPrescription(
                action="add_edge",
                target="*",
                edge_type=missing[0],
                reason=f"Missing edge types: {', '.join(missing)}. "
                       f"System lacks structural diversity.",
                priority=0.5,
            ))

    # Sort by priority descending
    prescriptions.sort(key=lambda p: p.priority, reverse=True)

    # Project confidence improvement
    fix_bonus = min(len(prescriptions) * 0.05, 0.3)
    projected = min(1.0, analysis.confidence + fix_bonus)

    return TCASolution(
        prescriptions=prescriptions,
        current_confidence=analysis.confidence,
        projected_confidence=round(projected, 4),
        critical_gaps=critical_gaps,
    )
