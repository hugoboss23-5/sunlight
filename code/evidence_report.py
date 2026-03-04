"""
SUNLIGHT Evidence Report Generator

Produces human-readable, investigation-ready reports for flagged contracts.
Designed for:
- Anti-corruption investigators who need to open a case file
- Auditors who need documented risk rationale
- Journalists who need sourced, explainable findings

Every claim in the report traces back to a specific OCDS field value
and a specific indicator with a published methodological basis.

Reports are structured as evidence packages:
1. Executive summary (one paragraph)
2. Risk classification with confidence
3. Indicator-by-indicator evidence
4. Raw data appendix
5. Methodology citations
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import json

from batch_pipeline import ContractScore, BatchPipeline


# ---------------------------------------------------------------------------
# Report templates
# ---------------------------------------------------------------------------

METHODOLOGY_CITATIONS = {
    "single_bidding": (
        "Fazekas, M. & Kocsis, G. (2020). 'Uncovering High-Level Corruption: "
        "Cross-National Objective Corruption Risk Indicators Using Public Procurement Data.' "
        "British Journal of Political Science, 50(1), 155-164. "
        "Single bidding is the strongest single predictor of corruption risk, "
        "correlated with perception-based indices across European regions."
    ),
    "tender_period": (
        "OCP Red Flags Guide (2024), Indicator RF-005: 'Short submission period.' "
        "Abnormally short tender periods prevent eligible bidders from preparing "
        "competitive bids, giving advantage to the pre-selected bidder. "
        "EU Directive 2014/24/EU sets minimum periods of 35 days (open) / 30 days (restricted)."
    ),
    "procedure_type": (
        "Fazekas, M., Tóth, I.J., & King, L.P. (2016). 'An Objective Corruption Risk Index.' "
        "European Journal on Criminal Policy and Research, 22, 369-397. "
        "Non-competitive procedures reduce transparency and enable discretionary favoritism."
    ),
    "decision_period": (
        "OCP Red Flags Guide (2024), Indicator RF-012: 'Abnormal decision period.' "
        "Extremely short decision periods suggest predetermined outcomes. "
        "Extremely long periods may indicate post-bid renegotiation or criterion manipulation."
    ),
    "amendment": (
        "OCP Red Flags Guide (2024), Indicator RF-031: 'Unjustified cost increases.' "
        "GRAS Category 3: Contract amendments increasing value by >30%. "
        "Lowball bids followed by scope expansion is a classic corruption scheme."
    ),
    "buyer_concentration": (
        "Fazekas CRI Component: 'Winner's contract share.' "
        "High concentration of a buyer's contracts going to one supplier "
        "indicates a preferential relationship. Measured via Herfindahl-Hirschman Index."
    ),
}


def _severity_label(cri_score: Optional[float], tier: str) -> str:
    if tier == "RED":
        return "HIGH RISK — Multiple corruption indicators flagged"
    elif tier == "YELLOW":
        return "ELEVATED RISK — Some corruption indicators present"
    elif tier == "GREEN":
        return "LOW RISK — No significant corruption indicators"
    else:
        return "INSUFFICIENT DATA — Cannot determine risk level"


def _confidence_statement(n_available: int, n_total: int) -> str:
    coverage = n_available / n_total if n_total > 0 else 0
    if coverage >= 0.8:
        return f"High confidence: {n_available}/{n_total} indicators had data ({coverage:.0%} coverage)"
    elif coverage >= 0.5:
        return f"Moderate confidence: {n_available}/{n_total} indicators had data ({coverage:.0%} coverage)"
    else:
        return f"Low confidence: only {n_available}/{n_total} indicators had data ({coverage:.0%} coverage)"


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------

def generate_text_report(score: ContractScore) -> str:
    """Generate a plain-text evidence report for a single contract."""
    lines = []

    # Header
    lines.append("=" * 72)
    lines.append("  SUNLIGHT EVIDENCE REPORT")
    lines.append(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 72)
    lines.append("")

    # Contract identification
    lines.append("CONTRACT IDENTIFICATION")
    lines.append("-" * 40)
    lines.append(f"  OCID:            {score.ocid}")
    lines.append(f"  Buyer:           {score.buyer_name or '—'} ({score.buyer_id or '—'})")
    lines.append(f"  Supplier:        {score.supplier_name or '—'} ({score.supplier_id or '—'})")
    lines.append(f"  Award Value:     {score.award_value:,.2f} {score.currency}" if score.award_value else "  Award Value:     —")
    lines.append(f"  Method:          {score.procurement_method or '—'}")
    lines.append(f"  Classification:  {score.main_classification or '—'}")
    lines.append("")

    # Risk classification
    lines.append("RISK CLASSIFICATION")
    lines.append("-" * 40)
    lines.append(f"  CRI Score:       {score.cri_score:.3f}" if score.cri_score is not None else "  CRI Score:       Indeterminate")
    lines.append(f"  Tier:            {score.cri_tier}")
    lines.append(f"  Severity:        {_severity_label(score.cri_score, score.cri_tier)}")
    lines.append(f"  Bayesian LR:     {score.combined_lr:.2f}x")
    lines.append(f"  Data Coverage:   {_confidence_statement(score.n_indicators_available, 6)}")
    lines.append(f"  Indicators:      {score.n_indicators_flagged} flagged / {score.n_indicators_available} evaluated")
    lines.append("")

    # Indicator evidence
    lines.append("INDICATOR EVIDENCE")
    lines.append("-" * 40)

    indicators = [
        ("single_bidding_flag", "SINGLE BIDDING", score.single_bidding_flag,
         f"Number of tenderers: {score.number_of_tenderers}" if score.number_of_tenderers else "No bid count data",
         "single_bidding"),
        ("tender_period_flag", "TENDER PERIOD", score.tender_period_flag,
         f"Tender period: {score.tender_period_days:.1f} days" if score.tender_period_days else "No tender period data",
         "tender_period"),
        ("procedure_type_flag", "PROCEDURE TYPE", score.procedure_type_flag,
         f"Method: {score.procurement_method}" if score.procurement_method else "No method data",
         "procedure_type"),
        ("decision_period_flag", "DECISION PERIOD", score.decision_period_flag,
         f"Decision period: {score.decision_period_days:.1f} days" if score.decision_period_days else "No decision period data",
         "decision_period"),
        ("amendment_flag", "AMENDMENTS", score.amendment_flag,
         f"Amendment count: {score.amendment_count}",
         "amendment"),
        ("buyer_concentration_flag", "BUYER CONCENTRATION", score.buyer_concentration_flag,
         "See buyer analysis section",
         "buyer_concentration"),
    ]

    for attr, label, flag, data_str, method_key in indicators:
        if flag == 1:
            status = "⚠ FLAGGED"
        elif flag == 0:
            status = "✓ CLEAR"
        else:
            status = "○ NO DATA"

        lines.append(f"  [{status}] {label}")
        lines.append(f"           Data: {data_str}")

        # Add explanation if flagged
        if flag == 1:
            matching_exp = [e for e in score.explanations if label.lower().replace(" ", "_") in e.lower() or
                          any(keyword in e.lower() for keyword in label.lower().split())]
            if matching_exp:
                lines.append(f"           Finding: {matching_exp[0]}")
            lines.append(f"           Methodology: {METHODOLOGY_CITATIONS.get(method_key, 'See references')[:120]}...")

        lines.append("")

    # Investigation recommendations
    if score.cri_tier == "RED":
        lines.append("RECOMMENDED ACTIONS")
        lines.append("-" * 40)
        if score.single_bidding_flag == 1:
            lines.append("  1. Verify whether other potential suppliers were available in this market segment")
            lines.append("     and whether any barriers to entry were artificially created.")
        if score.tender_period_flag == 1:
            lines.append("  2. Check whether the tender notice was pre-published through informal channels")
            lines.append("     before the official publication date.")
        if score.procedure_type_flag == 1:
            lines.append("  3. Review the justification for using non-competitive procedure.")
            lines.append("     Verify whether the legal basis cited was appropriate.")
        if score.decision_period_flag == 1:
            lines.append("  4. Examine the evaluation committee records. Check for evidence of")
            lines.append("     predetermined scoring or post-hoc criterion adjustment.")
        if score.amendment_flag == 1:
            lines.append("  5. Compare original scope of work with final deliverables.")
            lines.append("     Check whether amendments were anticipated in the original bid.")
        if score.buyer_concentration_flag == 1:
            lines.append("  6. Investigate the relationship between buyer officials and supplier.")
            lines.append("     Check for beneficial ownership connections, revolving doors, or campaign links.")
        lines.append("")

    # Raw data appendix
    lines.append("RAW DATA")
    lines.append("-" * 40)
    raw = {
        "ocid": score.ocid,
        "number_of_tenderers": score.number_of_tenderers,
        "tender_period_days": score.tender_period_days,
        "decision_period_days": score.decision_period_days,
        "procurement_method": score.procurement_method,
        "amendment_count": score.amendment_count,
        "award_value": score.award_value,
        "currency": score.currency,
        "cri_score": score.cri_score,
        "combined_lr": score.combined_lr,
        "fields_present": score.fields_present,
        "fields_missing": score.fields_missing,
    }
    lines.append(f"  {json.dumps(raw, indent=4, default=str)}")
    lines.append("")

    # Footer
    lines.append("=" * 72)
    lines.append("  METHODOLOGY REFERENCES")
    lines.append("  • Fazekas & Kocsis (2020), British Journal of Political Science")
    lines.append("  • OCP Red Flags for Integrity Guide (2024)")
    lines.append("  • GRAS: Ortega, Fazekas, Vaz Mondo, Tóth, Braem Velasco (2023)")
    lines.append("  • EU Directive 2014/24/EU")
    lines.append("")
    lines.append("  This report was generated by SUNLIGHT, an open procurement")
    lines.append("  integrity infrastructure tool. All indicators are based on")
    lines.append("  published, peer-reviewed methodologies applied to standardized")
    lines.append("  OCDS data. Flagged contracts require human investigation —")
    lines.append("  statistical signals are not proof of wrongdoing.")
    lines.append("=" * 72)

    return "\n".join(lines)


def generate_json_report(score: ContractScore) -> dict:
    """Generate a structured JSON evidence report."""
    return {
        "report_type": "SUNLIGHT_EVIDENCE_REPORT",
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "ocid": score.ocid,
            "buyer": {"id": score.buyer_id, "name": score.buyer_name},
            "supplier": {"id": score.supplier_id, "name": score.supplier_name},
            "value": {"amount": score.award_value, "currency": score.currency},
            "method": score.procurement_method,
            "classification": score.main_classification,
        },
        "risk_assessment": {
            "cri_score": score.cri_score,
            "tier": score.cri_tier,
            "severity": _severity_label(score.cri_score, score.cri_tier),
            "bayesian_likelihood_ratio": score.combined_lr,
            "confidence": _confidence_statement(score.n_indicators_available, 6),
            "indicators_flagged": score.n_indicators_flagged,
            "indicators_evaluated": score.n_indicators_available,
        },
        "indicators": {
            "single_bidding": {
                "flag": score.single_bidding_flag,
                "data": {"number_of_tenderers": score.number_of_tenderers},
                "methodology": METHODOLOGY_CITATIONS["single_bidding"],
            },
            "tender_period": {
                "flag": score.tender_period_flag,
                "data": {"tender_period_days": score.tender_period_days},
                "methodology": METHODOLOGY_CITATIONS["tender_period"],
            },
            "procedure_type": {
                "flag": score.procedure_type_flag,
                "data": {"procurement_method": score.procurement_method},
                "methodology": METHODOLOGY_CITATIONS["procedure_type"],
            },
            "decision_period": {
                "flag": score.decision_period_flag,
                "data": {"decision_period_days": score.decision_period_days},
                "methodology": METHODOLOGY_CITATIONS["decision_period"],
            },
            "amendment": {
                "flag": score.amendment_flag,
                "data": {"amendment_count": score.amendment_count},
                "methodology": METHODOLOGY_CITATIONS["amendment"],
            },
            "buyer_concentration": {
                "flag": score.buyer_concentration_flag,
                "data": {},
                "methodology": METHODOLOGY_CITATIONS["buyer_concentration"],
            },
        },
        "explanations": score.explanations,
        "disclaimer": (
            "This report identifies statistical risk signals based on published, "
            "peer-reviewed methodologies. Flagged contracts require human investigation. "
            "Statistical signals are not proof of wrongdoing."
        ),
    }


def generate_markdown_report(score: ContractScore) -> str:
    """Generate a Markdown evidence report (for web display or PDF conversion)."""
    lines = []

    tier_emoji = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢", "GRAY": "⚪"}
    emoji = tier_emoji.get(score.cri_tier, "⚪")

    lines.append(f"# SUNLIGHT Evidence Report")
    lines.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")

    lines.append(f"## {emoji} {score.cri_tier} — Contract {score.ocid}")
    lines.append("")

    # Quick stats
    cri_str = f"{score.cri_score:.3f}" if score.cri_score is not None else "N/A"
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| CRI Score | {cri_str} |")
    lines.append(f"| Tier | {score.cri_tier} |")
    lines.append(f"| Bayesian Evidence | {score.combined_lr:.1f}x |")
    lines.append(f"| Indicators Flagged | {score.n_indicators_flagged}/{score.n_indicators_available} |")
    lines.append(f"| Buyer | {score.buyer_name or '—'} |")
    lines.append(f"| Supplier | {score.supplier_name or '—'} |")
    val_str = f"{score.award_value:,.0f} {score.currency}" if score.award_value else "—"
    lines.append(f"| Award Value | {val_str} |")
    lines.append(f"| Method | {score.procurement_method or '—'} |")
    lines.append("")

    # Indicators
    lines.append(f"## Indicator Analysis")
    lines.append("")

    flag_map = {1: "⚠️ FLAGGED", 0: "✅ Clear", None: "◻️ No data"}

    indicators = [
        ("Single Bidding", score.single_bidding_flag, "single_bidding"),
        ("Tender Period", score.tender_period_flag, "tender_period"),
        ("Procedure Type", score.procedure_type_flag, "procedure_type"),
        ("Decision Period", score.decision_period_flag, "decision_period"),
        ("Amendments", score.amendment_flag, "amendment"),
        ("Buyer Concentration", score.buyer_concentration_flag, "buyer_concentration"),
    ]

    for label, flag, key in indicators:
        status = flag_map.get(flag, "◻️ Unknown")
        lines.append(f"### {status} {label}")
        if flag == 1:
            matching = [e for e in score.explanations if any(
                kw in e.lower() for kw in label.lower().split()
            )]
            if matching:
                lines.append(f"> {matching[0]}")
            lines.append(f"*Methodology: {METHODOLOGY_CITATIONS.get(key, '')}*")
        lines.append("")

    # Disclaimer
    lines.append("---")
    lines.append("*This report identifies statistical risk signals based on published, "
                 "peer-reviewed methodologies. Flagged contracts require human investigation. "
                 "Statistical signals are not proof of wrongdoing.*")

    return "\n".join(lines)


def generate_reports_for_tier(
    pipeline: BatchPipeline,
    tier: str = "RED",
    format: str = "text",
    max_reports: int = 20,
) -> list[str]:
    """Generate evidence reports for all contracts in a given tier."""
    filtered = [s for s in pipeline.scores if s.cri_tier == tier]
    filtered.sort(key=lambda x: (x.cri_score or 0, x.combined_lr), reverse=True)

    reports = []
    for score in filtered[:max_reports]:
        if format == "text":
            reports.append(generate_text_report(score))
        elif format == "markdown":
            reports.append(generate_markdown_report(score))
        elif format == "json":
            reports.append(json.dumps(generate_json_report(score), indent=2, default=str))

    return reports
