"""
SUNLIGHT Corruption Risk Indicators (CRI)

Implements the Fazekas composite Corruption Risk Index methodology plus
additional indicators from OCP Red Flags Guide (2024) and GRAS.

Each indicator returns a standardized IndicatorResult:
- flag: 0 (clean), 1 (flagged), or None (indeterminate/GRAY)
- likelihood_ratio: Bayesian evidence weight for the posterior
- explanation: Human-readable reason for the flag
- data: Raw values used in computation

Design principle: Missing data → GRAY (None), not GREEN (0).
Absence of evidence is not evidence of absence.

References:
- Fazekas & Kocsis (2020). "Uncovering High-Level Corruption"
- OCP Red Flags Guide (2024), 73 indicators mapped to OCDS
- Fazekas, Tóth, Poltoratskaia (2023). Bulgaria WB Working Paper
- GRAS: Ortega, Fazekas, Vaz Mondo, Tóth, Braem Velasco (2023)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import math
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class IndicatorResult:
    """Standardized result from any indicator."""
    indicator_name: str
    flag: Optional[int]          # 0 = clean, 1 = flagged, None = indeterminate
    likelihood_ratio: float      # Bayesian evidence weight (1.0 = neutral)
    explanation: str
    data: dict = field(default_factory=dict)

    @property
    def is_flagged(self) -> bool:
        return self.flag == 1

    @property
    def is_indeterminate(self) -> bool:
        return self.flag is None

    @property
    def tier_label(self) -> str:
        if self.flag is None:
            return "GRAY"
        return "RED" if self.flag == 1 else "GREEN"


# ---------------------------------------------------------------------------
# 1. SINGLE BIDDING
# ---------------------------------------------------------------------------

def single_bidding(
    number_of_tenderers: Optional[int],
    procurement_method: Optional[str] = None,
    bid_count: Optional[int] = None,
) -> IndicatorResult:
    """
    Flag contracts where only one bid was received on a competitive tender.

    The single strongest predictor of corruption per Fazekas & Kocsis (2020).
    Correlated with perception-based corruption indices across European regions.

    Single bidding is both input and output of corruption:
    - Output: signals restricted competition
    - Input: enables recurring awards to connected firms

    Args:
        number_of_tenderers: OCDS tender/numberOfTenderers
        procurement_method: OCDS tender/procurementMethod
        bid_count: Count of bids/details entries (fallback)
    """
    # Determine effective bid count
    effective_count = number_of_tenderers
    if effective_count is None:
        effective_count = bid_count

    if effective_count is None:
        return IndicatorResult(
            indicator_name="single_bidding",
            flag=None,
            likelihood_ratio=1.0,
            explanation="Number of tenderers not available in data",
            data={"number_of_tenderers": None, "procurement_method": procurement_method}
        )

    # Non-competitive methods naturally have single bidder — don't flag
    if procurement_method in ("direct", "limited"):
        return IndicatorResult(
            indicator_name="single_bidding",
            flag=0,
            likelihood_ratio=1.0,
            explanation=f"Non-competitive procedure ({procurement_method}); single bidding expected",
            data={"number_of_tenderers": effective_count, "procurement_method": procurement_method}
        )

    if effective_count == 1:
        return IndicatorResult(
            indicator_name="single_bidding",
            flag=1,
            likelihood_ratio=3.0,  # Strong predictor per Fazekas
            explanation="Only one bid received on competitive tender — strongest single corruption predictor",
            data={"number_of_tenderers": effective_count, "procurement_method": procurement_method}
        )

    if effective_count == 2:
        # Two bidders still somewhat risky — allows cover bidding
        return IndicatorResult(
            indicator_name="single_bidding",
            flag=0,
            likelihood_ratio=1.5,  # Mild evidence
            explanation="Two bids received — low competition but not single bidding",
            data={"number_of_tenderers": effective_count, "procurement_method": procurement_method}
        )

    return IndicatorResult(
        indicator_name="single_bidding",
        flag=0,
        likelihood_ratio=0.7,  # Multiple bidders is weak evidence against corruption
        explanation=f"{effective_count} bids received — competitive",
        data={"number_of_tenderers": effective_count, "procurement_method": procurement_method}
    )


# ---------------------------------------------------------------------------
# 2. TENDER PERIOD ANALYZER
# ---------------------------------------------------------------------------

def tender_period_risk(
    tender_period_days: Optional[float],
    procurement_method: Optional[str] = None,
    jurisdiction_minimum: float = 15.0,
) -> IndicatorResult:
    """
    Flag abnormally short tender periods that prevent genuine competition.

    Short submission periods prevent eligible bidders from preparing bids,
    giving an advantage to the favored bidder who knew about the tender
    before it was published.

    Thresholds calibrated from Fazekas research:
    - < 7 days: Very short (LR 4.0) — almost certainly restrictive
    - < 15 days: Short (LR 2.0) — below EU minimum for most procedures
    - Jurisdiction minimums vary: EU open = 35 days, EU restricted = 30 days

    Args:
        tender_period_days: Days between publication and submission deadline
        procurement_method: To contextualize appropriate minimum
        jurisdiction_minimum: Configurable minimum for jurisdiction
    """
    if tender_period_days is None:
        return IndicatorResult(
            indicator_name="tender_period",
            flag=None,
            likelihood_ratio=1.0,
            explanation="Tender period dates not available in data",
            data={"tender_period_days": None}
        )

    if tender_period_days < 0:
        return IndicatorResult(
            indicator_name="tender_period",
            flag=1,
            likelihood_ratio=5.0,
            explanation=f"Negative tender period ({tender_period_days:.1f} days) — data error or backdated tender",
            data={"tender_period_days": tender_period_days}
        )

    if tender_period_days < 7:
        return IndicatorResult(
            indicator_name="tender_period",
            flag=1,
            likelihood_ratio=4.0,
            explanation=f"Extremely short tender period: {tender_period_days:.1f} days — severely restricts competition",
            data={"tender_period_days": tender_period_days, "threshold": 7}
        )

    if tender_period_days < jurisdiction_minimum:
        return IndicatorResult(
            indicator_name="tender_period",
            flag=1,
            likelihood_ratio=2.0,
            explanation=f"Short tender period: {tender_period_days:.1f} days (minimum: {jurisdiction_minimum})",
            data={"tender_period_days": tender_period_days, "threshold": jurisdiction_minimum}
        )

    return IndicatorResult(
        indicator_name="tender_period",
        flag=0,
        likelihood_ratio=0.8,
        explanation=f"Adequate tender period: {tender_period_days:.1f} days",
        data={"tender_period_days": tender_period_days}
    )


# ---------------------------------------------------------------------------
# 3. PROCEDURE TYPE RISK
# ---------------------------------------------------------------------------

# OCDS standard procurement method values
RISKY_METHODS = {"limited", "direct"}
COMPETITIVE_METHODS = {"open", "selective"}

def procedure_type_risk(
    procurement_method: Optional[str],
    procurement_method_details: Optional[str] = None,
) -> IndicatorResult:
    """
    Flag non-competitive procurement methods.

    Non-open procedures bypass competitive safeguards and allow
    contracting authorities to restrict who can bid.

    Per Fazekas: restricted/negotiated procedures are a CRI component
    because they reduce transparency and enable favoritism.

    Args:
        procurement_method: OCDS tender/procurementMethod
        procurement_method_details: Free text for additional context
    """
    if procurement_method is None:
        return IndicatorResult(
            indicator_name="procedure_type",
            flag=None,
            likelihood_ratio=1.0,
            explanation="Procurement method not specified in data",
            data={"procurement_method": None}
        )

    method_lower = procurement_method.lower().strip()

    if method_lower == "direct":
        return IndicatorResult(
            indicator_name="procedure_type",
            flag=1,
            likelihood_ratio=2.5,
            explanation="Direct award — no competitive process",
            data={"procurement_method": procurement_method, "details": procurement_method_details}
        )

    if method_lower == "limited":
        return IndicatorResult(
            indicator_name="procedure_type",
            flag=1,
            likelihood_ratio=2.0,
            explanation="Limited/restricted procedure — competition constrained",
            data={"procurement_method": procurement_method, "details": procurement_method_details}
        )

    if method_lower == "selective":
        # Selective is between open and limited — mild risk
        return IndicatorResult(
            indicator_name="procedure_type",
            flag=0,
            likelihood_ratio=1.3,
            explanation="Selective procedure — pre-qualified bidders only",
            data={"procurement_method": procurement_method, "details": procurement_method_details}
        )

    if method_lower == "open":
        return IndicatorResult(
            indicator_name="procedure_type",
            flag=0,
            likelihood_ratio=0.7,
            explanation="Open competitive procedure",
            data={"procurement_method": procurement_method, "details": procurement_method_details}
        )

    # Unknown method — don't penalize but note it
    return IndicatorResult(
        indicator_name="procedure_type",
        flag=None,
        likelihood_ratio=1.0,
        explanation=f"Unrecognized procurement method: {procurement_method}",
        data={"procurement_method": procurement_method, "details": procurement_method_details}
    )


# ---------------------------------------------------------------------------
# 4. DECISION PERIOD RISK
# ---------------------------------------------------------------------------

def decision_period_risk(
    decision_period_days: Optional[float],
) -> IndicatorResult:
    """
    Flag abnormal decision periods (award date minus tender deadline).

    Extremely short decision periods suggest pre-arranged outcomes —
    the authority already knew who would win before evaluating bids.

    Extremely long decision periods may indicate renegotiation or
    manipulation of evaluation criteria after seeing the bids.

    Args:
        decision_period_days: Days between tender end and award date
    """
    if decision_period_days is None:
        return IndicatorResult(
            indicator_name="decision_period",
            flag=None,
            likelihood_ratio=1.0,
            explanation="Decision period not computable (missing dates)",
            data={"decision_period_days": None}
        )

    if decision_period_days < 0:
        return IndicatorResult(
            indicator_name="decision_period",
            flag=1,
            likelihood_ratio=4.0,
            explanation=f"Award date BEFORE tender deadline ({decision_period_days:.0f} days) — impossible or backdated",
            data={"decision_period_days": decision_period_days}
        )

    if decision_period_days < 1:
        return IndicatorResult(
            indicator_name="decision_period",
            flag=1,
            likelihood_ratio=3.0,
            explanation=f"Same-day award decision — suggests predetermined outcome",
            data={"decision_period_days": decision_period_days}
        )

    if decision_period_days > 180:
        return IndicatorResult(
            indicator_name="decision_period",
            flag=1,
            likelihood_ratio=1.5,
            explanation=f"Extremely long decision period: {decision_period_days:.0f} days — possible renegotiation",
            data={"decision_period_days": decision_period_days}
        )

    return IndicatorResult(
        indicator_name="decision_period",
        flag=0,
        likelihood_ratio=1.0,
        explanation=f"Normal decision period: {decision_period_days:.0f} days",
        data={"decision_period_days": decision_period_days}
    )


# ---------------------------------------------------------------------------
# 5. AMENDMENT ANALYZER
# ---------------------------------------------------------------------------

def amendment_risk(
    amendment_count: int = 0,
    original_value: Optional[float] = None,
    final_value: Optional[float] = None,
    value_increase_threshold: float = 0.30,
) -> IndicatorResult:
    """
    Flag contracts with suspicious amendment patterns.

    Contract amendments that substantially increase value suggest:
    - Initial lowball bid to win, then scope expansion
    - Planned cost overruns to extract more from public funds
    - Manipulation of the original justification

    OCP Red Flags Guide (2024): >30% value increase is flagged.
    GRAS flags "unjustified cost increases during execution."

    Args:
        amendment_count: Number of amendments on the contract
        original_value: Award/initial contract value
        final_value: Current/final contract value after amendments
        value_increase_threshold: Fraction increase to flag (default 30%)
    """
    if amendment_count == 0:
        return IndicatorResult(
            indicator_name="amendment",
            flag=0,
            likelihood_ratio=0.9,
            explanation="No amendments",
            data={"amendment_count": 0}
        )

    # Compute value change if possible
    value_change_pct = None
    if original_value and final_value and original_value > 0:
        value_change_pct = (final_value - original_value) / original_value

    if value_change_pct is not None and value_change_pct > value_increase_threshold:
        return IndicatorResult(
            indicator_name="amendment",
            flag=1,
            likelihood_ratio=2.0,
            explanation=(
                f"{amendment_count} amendment(s) increased value by "
                f"{value_change_pct:.0%} (threshold: {value_increase_threshold:.0%})"
            ),
            data={
                "amendment_count": amendment_count,
                "original_value": original_value,
                "final_value": final_value,
                "value_change_pct": value_change_pct,
            }
        )

    if amendment_count >= 3:
        return IndicatorResult(
            indicator_name="amendment",
            flag=1,
            likelihood_ratio=1.5,
            explanation=f"High number of amendments ({amendment_count}) — possible scope manipulation",
            data={"amendment_count": amendment_count, "value_change_pct": value_change_pct}
        )

    return IndicatorResult(
        indicator_name="amendment",
        flag=0,
        likelihood_ratio=1.0,
        explanation=f"{amendment_count} amendment(s) — within normal range",
        data={"amendment_count": amendment_count, "value_change_pct": value_change_pct}
    )


# ---------------------------------------------------------------------------
# 6. SPLIT PURCHASE DETECTOR
# ---------------------------------------------------------------------------

@dataclass
class SplitPurchaseContext:
    """Aggregated context for detecting split purchases per buyer."""
    buyer_id: str
    contracts: list[dict] = field(default_factory=list)


def detect_split_purchases(
    buyer_contracts: list[dict],
    threshold: float = 10000.0,
    proximity_pct: float = 0.05,
    time_window_days: int = 30,
    min_cluster_size: int = 3,
) -> list[IndicatorResult]:
    """
    Detect threshold manipulation through contract splitting.

    Officials split large procurements into smaller contracts just below
    the competitive threshold to avoid open bidding requirements.

    Example: 5 contracts of $9,900 each from same buyer in same month
    when threshold for competitive bidding is $10,000.

    OCP Red Flags Guide: "Manipulation of procurement thresholds"
    GRAS Category 1: "Split purchases to avoid thresholds"

    Args:
        buyer_contracts: List of dicts with keys: buyer_id, value, date, classification
        threshold: Procurement threshold for the jurisdiction
        proximity_pct: How close to threshold counts as "near" (5% = within $500 of $10K)
        time_window_days: Rolling window for clustering
        min_cluster_size: Minimum contracts to constitute a suspicious cluster
    """
    results = []

    # Group by buyer
    by_buyer = defaultdict(list)
    for contract in buyer_contracts:
        bid = contract.get("buyer_id")
        if bid:
            by_buyer[bid].append(contract)

    proximity_amount = threshold * proximity_pct
    lower_bound = threshold - proximity_amount

    for buyer_id, contracts in by_buyer.items():
        # Filter to near-threshold contracts
        near_threshold = [
            c for c in contracts
            if c.get("value") is not None and lower_bound <= c["value"] < threshold
        ]

        if len(near_threshold) < min_cluster_size:
            continue

        # Sort by date and find clusters within time window
        dated = [c for c in near_threshold if c.get("date") is not None]
        dated.sort(key=lambda x: x["date"])

        # Sliding window
        for i in range(len(dated)):
            cluster = [dated[i]]
            for j in range(i + 1, len(dated)):
                delta = (dated[j]["date"] - dated[i]["date"]).days
                if delta <= time_window_days:
                    cluster.append(dated[j])
                else:
                    break

            if len(cluster) >= min_cluster_size:
                total_value = sum(c.get("value", 0) for c in cluster)
                results.append(IndicatorResult(
                    indicator_name="split_purchase",
                    flag=1,
                    likelihood_ratio=2.5,
                    explanation=(
                        f"Buyer {buyer_id}: {len(cluster)} contracts totaling "
                        f"{total_value:,.0f} within {time_window_days} days, "
                        f"each just below threshold ({threshold:,.0f})"
                    ),
                    data={
                        "buyer_id": buyer_id,
                        "cluster_size": len(cluster),
                        "total_value": total_value,
                        "threshold": threshold,
                        "time_window_days": time_window_days,
                    }
                ))
                break  # One flag per buyer

    return results


# ---------------------------------------------------------------------------
# 7. BUYER CONCENTRATION (Winner's Share)
# ---------------------------------------------------------------------------

def buyer_concentration(
    buyer_id: str,
    supplier_contracts: dict[str, float],
    min_contracts: int = 5,
    concentration_threshold: float = 0.40,
) -> IndicatorResult:
    """
    Flag buyers where a single supplier captures a disproportionate share.

    Measures market capture: if one supplier repeatedly wins from the
    same buyer, it suggests a preferential relationship.

    Per Fazekas CRI: "Winner's contract share" — concentration of
    contracts at a single buyer going to one supplier.

    Also computes HHI (Herfindahl-Hirschman Index) for market
    concentration among the buyer's suppliers.

    Args:
        buyer_id: Identifier of the buying entity
        supplier_contracts: {supplier_id: total_contract_value}
        min_contracts: Minimum total contracts to evaluate
        concentration_threshold: Share above which to flag (40%)
    """
    if not supplier_contracts:
        return IndicatorResult(
            indicator_name="buyer_concentration",
            flag=None,
            likelihood_ratio=1.0,
            explanation="No supplier data available for this buyer",
            data={"buyer_id": buyer_id}
        )

    total_value = sum(supplier_contracts.values())
    if total_value <= 0:
        return IndicatorResult(
            indicator_name="buyer_concentration",
            flag=None,
            likelihood_ratio=1.0,
            explanation="Zero total contract value",
            data={"buyer_id": buyer_id}
        )

    n_suppliers = len(supplier_contracts)
    if n_suppliers < 2:
        return IndicatorResult(
            indicator_name="buyer_concentration",
            flag=1,
            likelihood_ratio=2.0,
            explanation=f"Buyer {buyer_id} has only 1 supplier — complete market capture",
            data={"buyer_id": buyer_id, "n_suppliers": 1, "hhi": 1.0}
        )

    # Calculate shares and HHI
    shares = {sid: val / total_value for sid, val in supplier_contracts.items()}
    hhi = sum(s ** 2 for s in shares.values())
    top_supplier = max(shares, key=shares.get)
    top_share = shares[top_supplier]

    if top_share > concentration_threshold:
        return IndicatorResult(
            indicator_name="buyer_concentration",
            flag=1,
            likelihood_ratio=2.0,
            explanation=(
                f"Supplier {top_supplier} captures {top_share:.0%} of buyer {buyer_id}'s "
                f"contracts (threshold: {concentration_threshold:.0%}). HHI: {hhi:.3f}"
            ),
            data={
                "buyer_id": buyer_id,
                "top_supplier": top_supplier,
                "top_share": top_share,
                "hhi": hhi,
                "n_suppliers": n_suppliers,
            }
        )

    return IndicatorResult(
        indicator_name="buyer_concentration",
        flag=0,
        likelihood_ratio=0.8,
        explanation=f"Buyer {buyer_id}: top supplier share {top_share:.0%}, HHI {hhi:.3f} — diversified",
        data={
            "buyer_id": buyer_id,
            "top_supplier": top_supplier,
            "top_share": top_share,
            "hhi": hhi,
            "n_suppliers": n_suppliers,
        }
    )


# ---------------------------------------------------------------------------
# COMPOSITE CRI
# ---------------------------------------------------------------------------

@dataclass
class CRIResult:
    """Composite Corruption Risk Index following Fazekas methodology."""
    cri_score: Optional[float]     # 0.0 to 1.0 average of binary flags
    indicator_results: list[IndicatorResult]
    n_indicators_available: int    # How many had data
    n_indicators_flagged: int      # How many were flagged
    n_indicators_total: int        # How many were computed
    tier: str                      # RED / YELLOW / GREEN / GRAY

    @property
    def summary(self) -> str:
        if self.cri_score is None:
            return f"CRI: INDETERMINATE ({self.n_indicators_available}/{self.n_indicators_total} indicators available)"
        return (
            f"CRI: {self.cri_score:.2f} [{self.tier}] — "
            f"{self.n_indicators_flagged}/{self.n_indicators_available} indicators flagged"
        )


def compute_cri(
    indicator_results: list[IndicatorResult],
    red_threshold: float = 0.50,
    yellow_threshold: float = 0.25,
    min_indicators: int = 3,
) -> CRIResult:
    """
    Compute composite Corruption Risk Index.

    Follows Fazekas methodology: CRI = average of binary indicator flags.
    Only uses indicators with data (flag is not None).

    If fewer than min_indicators have data, the CRI is GRAY —
    insufficient evidence for a meaningful composite score.

    Tiers:
    - RED: CRI >= 0.50 (half or more indicators flagged)
    - YELLOW: CRI >= 0.25
    - GREEN: CRI < 0.25
    - GRAY: fewer than min_indicators available

    Args:
        indicator_results: List of IndicatorResult from individual indicators
        red_threshold: CRI score for RED classification
        yellow_threshold: CRI score for YELLOW classification
        min_indicators: Minimum indicators with data for valid CRI
    """
    available = [r for r in indicator_results if r.flag is not None]
    flagged = [r for r in available if r.flag == 1]

    n_available = len(available)
    n_flagged = len(flagged)
    n_total = len(indicator_results)

    if n_available < min_indicators:
        return CRIResult(
            cri_score=None,
            indicator_results=indicator_results,
            n_indicators_available=n_available,
            n_indicators_flagged=n_flagged,
            n_indicators_total=n_total,
            tier="GRAY",
        )

    cri = n_flagged / n_available

    if cri >= red_threshold:
        tier = "RED"
    elif cri >= yellow_threshold:
        tier = "YELLOW"
    else:
        tier = "GREEN"

    return CRIResult(
        cri_score=cri,
        indicator_results=indicator_results,
        n_indicators_available=n_available,
        n_indicators_flagged=n_flagged,
        n_indicators_total=n_total,
        tier=tier,
    )


# ---------------------------------------------------------------------------
# COMBINED BAYESIAN LIKELIHOOD
# ---------------------------------------------------------------------------

def combined_likelihood_ratio(indicator_results: list[IndicatorResult]) -> float:
    """
    Combine all indicator likelihood ratios for Bayesian posterior update.

    Under independence assumption, posterior odds = prior odds × ∏(LR_i).
    This gives the multiplicative evidence update from all indicators.

    Returns the combined likelihood ratio (multiply with prior odds to get posterior odds).
    """
    combined_lr = 1.0
    for result in indicator_results:
        if result.flag is not None:  # Only use indicators with data
            combined_lr *= result.likelihood_ratio
    return combined_lr


# ---------------------------------------------------------------------------
# CONVENIENCE: Run all indicators on an ExtractedRelease
# ---------------------------------------------------------------------------

def analyze_release(extracted, price_flag: Optional[int] = None, price_lr: float = 1.0) -> CRIResult:
    """
    Run all CRI indicators on an ExtractedRelease and compute composite score.

    Args:
        extracted: ExtractedRelease from ocds_field_extractor
        price_flag: Result from existing price deviation engine (0, 1, or None)
        price_lr: Likelihood ratio from existing price deviation engine
    """
    results = []

    # 1. Single bidding
    results.append(single_bidding(
        number_of_tenderers=extracted.number_of_tenderers,
        procurement_method=extracted.procurement_method,
        bid_count=extracted.bid_count,
    ))

    # 2. Tender period
    results.append(tender_period_risk(
        tender_period_days=extracted.tender_period_days,
        procurement_method=extracted.procurement_method,
    ))

    # 3. Procedure type
    results.append(procedure_type_risk(
        procurement_method=extracted.procurement_method,
        procurement_method_details=extracted.procurement_method_details,
    ))

    # 4. Decision period
    results.append(decision_period_risk(
        decision_period_days=extracted.decision_period_days,
    ))

    # 5. Amendment
    results.append(amendment_risk(
        amendment_count=extracted.amendment_count,
        original_value=extracted.original_value,
        final_value=extracted.final_value,
    ))

    # 6. Price deviation (from existing engine)
    if price_flag is not None:
        results.append(IndicatorResult(
            indicator_name="price_deviation",
            flag=price_flag,
            likelihood_ratio=price_lr,
            explanation="Price deviation from existing statistical engine",
            data={"source": "bayesian_engine"}
        ))

    # Note: buyer_concentration and split_purchase are batch-level indicators
    # computed across all contracts for a buyer, not per-release.
    # They should be computed separately and merged.

    return compute_cri(results)
