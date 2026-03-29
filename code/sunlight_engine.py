#!/usr/bin/env python3
"""
SUNLIGHT — Structural Verification Engine for Public Procurement
================================================================

WHAT THIS DOES:
    Takes a procurement contract (JSON) → runs 7 structural gates →
    outputs a verdict: PASS or BLOCKED, with every finding explained.

HOW IT WORKS:
    Each gate checks ONE structural joint where money vanishes in procurement.
    A "finding" = a contradiction between what the contract CLAIMS and what
    the structure SHOWS. Findings are not opinions — they're measurable
    structural facts.

THE 7 GATES:
    1. NEED    — Is the stated need structurally justified?
    2. SPEC    — Are specifications open or rigged toward one vendor?
    3. ENTITY  — Is the winning entity structurally legitimate?
    4. COMPETE — Was there real competition or fabricated competition?
    5. PRICE   — Is the price structurally defensible?
    6. AWARD   — Does one actor control too many decision points?
    7. PAYMENT — Is there evidence of delivery matching disbursement?

RIM: This is the engine. Everything else is plumbing to feed it data
and display the output. If you understand this file, you understand Sunlight.

Usage:
    python sunlight_engine.py                     # run demo contracts
    python sunlight_engine.py contract.json       # analyze a real contract
    python sunlight_engine.py --batch folder/     # analyze a folder of contracts
"""

import json
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Finding:
    """One structural contradiction found by a gate."""
    gate: str
    severity: str          # "critical" | "major" | "minor"
    description: str
    evidence: dict
    confidence: float      # 0.0 to 1.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Verdict:
    """The final output of Sunlight for one contract."""
    contract_id: str
    verdict: str               # "PASS" | "BLOCKED" | "REVIEW"
    findings: list
    confidence: float
    recovery_estimate_usd: float
    gate_results: dict
    analyzed_at: str
    summary: str

    def to_dict(self):
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# THE 7 GATES
# Each gate: gate(contract) → list[Finding]
# Empty list = nothing wrong. Findings = structural contradictions detected.
# ═══════════════════════════════════════════════════════════════════════════════

def gate_need(c: dict) -> list:
    """GATE 1 — NEED: Is there a documented justification for this procurement?"""
    findings = []
    desc = c.get("description", "").strip()
    needs_assessment = c.get("needs_assessment", None)

    if len(desc) < 10:
        findings.append(Finding(
            gate="NEED", severity="critical",
            description="Contract has no meaningful description of what is being procured.",
            evidence={"description_length": len(desc), "description": desc},
            confidence=0.95))

    if not needs_assessment:
        findings.append(Finding(
            gate="NEED", severity="major",
            description="No needs assessment or justification document referenced.",
            evidence={"needs_assessment": None}, confidence=0.70))

    vague_terms = ["various", "miscellaneous", "as needed", "general", "sundry", "other"]
    vague_hits = [t for t in vague_terms if t in desc.lower()]
    if vague_hits and c.get("amount", 0) > 100_000:
        findings.append(Finding(
            gate="NEED", severity="major",
            description=f"High-value contract uses vague terms: {vague_hits}. Structurally consistent with fabricated need.",
            evidence={"vague_terms": vague_hits, "amount": c.get("amount")},
            confidence=0.60))
    return findings


def gate_spec(c: dict) -> list:
    """GATE 2 — SPECIFICATION: Are specs open or rigged for one vendor?"""
    findings = []
    sole_source = c.get("sole_source", False)
    desc = c.get("description", "").lower()

    if sole_source and not c.get("sole_source_justification"):
        findings.append(Finding(
            gate="SPEC", severity="critical",
            description="Sole-source procurement with no documented justification.",
            evidence={"sole_source": True, "justification": None}, confidence=0.90))

    brand_signals = ["proprietary", "brand-name", "compatible only with", "must be identical to", "no substitutes"]
    brand_hits = [s for s in brand_signals if s in desc]
    if brand_hits:
        findings.append(Finding(
            gate="SPEC", severity="major",
            description=f"Specification contains restrictive language: {brand_hits}. May be tailored to exclude competition.",
            evidence={"restrictive_terms": brand_hits}, confidence=0.65))
    return findings


def gate_entity(c: dict) -> list:
    """GATE 3 — ENTITY: Is the winning vendor structurally legitimate?"""
    findings = []
    vendor = c.get("vendor", {})
    award_date = c.get("award_date", "")

    if not vendor.get("name"):
        findings.append(Finding(
            gate="ENTITY", severity="critical",
            description="No vendor/recipient identified on contract.",
            evidence={"vendor": vendor}, confidence=0.95))
        return findings

    incorporation_date = vendor.get("incorporation_date", "")
    if incorporation_date and award_date:
        try:
            inc = datetime.fromisoformat(incorporation_date)
            awd = datetime.fromisoformat(award_date)
            age_days = (awd - inc).days
            amount = c.get("amount", 0)
            if age_days < 180 and amount > 500_000:
                findings.append(Finding(
                    gate="ENTITY", severity="critical",
                    description=f"Vendor incorporated {age_days} days before ${amount:,.0f} award. Shell company indicator.",
                    evidence={"vendor_age_days": age_days, "amount": amount,
                              "incorporation_date": incorporation_date, "award_date": award_date},
                    confidence=0.80))
        except (ValueError, TypeError):
            pass

    if not vendor.get("address") and not vendor.get("registration_id"):
        findings.append(Finding(
            gate="ENTITY", severity="major",
            description="Vendor has no registered address or registration ID on file.",
            evidence={"vendor_name": vendor.get("name")}, confidence=0.60))
    return findings


def gate_competition(c: dict) -> list:
    """GATE 4 — COMPETITION: Was there genuine competitive bidding?"""
    findings = []
    bids = c.get("bids", [])
    num_bidders = c.get("number_of_bidders", len(bids))
    method = c.get("procurement_method", "").lower()

    if num_bidders <= 1 and method in ["open", "competitive", "selective", ""]:
        findings.append(Finding(
            gate="COMPETITION", severity="critical",
            description=f"Only {num_bidders} bidder(s) on a '{method or 'unspecified'}' procurement. Structurally indistinguishable from sole-source.",
            evidence={"number_of_bidders": num_bidders, "procurement_method": method},
            confidence=0.85))

    if len(bids) >= 3:
        amounts = [b.get("amount", 0) for b in bids if b.get("amount")]
        if amounts and min(amounts) > 0:
            spread = (max(amounts) - min(amounts)) / min(amounts)
            if spread < 0.03:
                findings.append(Finding(
                    gate="COMPETITION", severity="major",
                    description=f"All {len(amounts)} bids within {spread:.1%} of each other. Consistent with bid rotation or collusion.",
                    evidence={"bid_amounts": amounts, "spread_pct": round(spread * 100, 2)},
                    confidence=0.70))

    if len(bids) >= 2:
        for bid in bids:
            if not bid.get("winner", False):
                amt = bid.get("amount", 0)
                if amt > 0 and amt % 10000 == 0:
                    findings.append(Finding(
                        gate="COMPETITION", severity="minor",
                        description=f"Losing bid of exactly ${amt:,.0f} — round number consistent with placeholder/phantom bid.",
                        evidence={"bid_amount": amt, "bidder": bid.get("name", "unknown")},
                        confidence=0.40))
    return findings


def gate_price(c: dict) -> list:
    """GATE 5 — PRICE: Is the contract price structurally defensible?"""
    findings = []
    amount = c.get("amount", 0)
    comparable_avg = c.get("comparable_average", None)
    amendments = c.get("amendments", [])

    if comparable_avg and comparable_avg > 0 and amount > 0:
        markup = amount / comparable_avg
        if markup > 2.0:
            findings.append(Finding(
                gate="PRICE", severity="critical",
                description=f"Contract price ${amount:,.0f} is {markup:.1f}x the comparable average of ${comparable_avg:,.0f}.",
                evidence={"amount": amount, "comparable_average": comparable_avg, "markup_ratio": round(markup, 2)},
                confidence=min(0.90, 0.50 + (markup - 2.0) * 0.10)))
        elif markup > 1.5:
            findings.append(Finding(
                gate="PRICE", severity="major",
                description=f"Contract price ${amount:,.0f} is {markup:.1f}x the comparable average. Above normal range.",
                evidence={"amount": amount, "comparable_average": comparable_avg, "markup_ratio": round(markup, 2)},
                confidence=0.55))

    if amendments:
        total_amendments = sum(a.get("amount_change", 0) for a in amendments)
        if amount > 0 and total_amendments > 0:
            inflation = total_amendments / amount
            if inflation > 0.25:
                findings.append(Finding(
                    gate="PRICE", severity="critical",
                    description=f"Amendments increased contract value by {inflation:.0%} (${total_amendments:,.0f}). Consistent with low-ball-then-inflate pattern.",
                    evidence={"original_amount": amount, "total_amendment_value": total_amendments,
                              "inflation_pct": round(inflation * 100, 1), "num_amendments": len(amendments)},
                    confidence=0.75))
    return findings


def gate_award(c: dict) -> list:
    """GATE 6 — AWARD: Does one person control too many decision points? (Political patron signature)"""
    findings = []
    roles = c.get("decision_roles", {})

    if roles:
        need_author = (roles.get("need_author") or "").lower().strip()
        evaluator = (roles.get("bid_evaluator") or "").lower().strip()
        approver = (roles.get("award_approver") or "").lower().strip()
        oversight = (roles.get("oversight_officer") or "").lower().strip()

        actors = {}
        for role, name in [("need_author", need_author), ("bid_evaluator", evaluator),
                           ("award_approver", approver), ("oversight_officer", oversight)]:
            if name:
                actors.setdefault(name, []).append(role)

        for actor, their_roles in actors.items():
            if len(their_roles) >= 3:
                findings.append(Finding(
                    gate="AWARD", severity="critical",
                    description=f"Single actor '{actor}' controls {len(their_roles)} decision points: {their_roles}. Political patron signature — oversight structurally removed.",
                    evidence={"actor": actor, "roles": their_roles}, confidence=0.85))
            elif len(their_roles) == 2:
                findings.append(Finding(
                    gate="AWARD", severity="major",
                    description=f"Actor '{actor}' holds dual roles: {their_roles}. Separation of duties compromised.",
                    evidence={"actor": actor, "roles": their_roles}, confidence=0.65))

    if not roles.get("oversight_officer"):
        findings.append(Finding(
            gate="AWARD", severity="major",
            description="No oversight officer documented for this award.",
            evidence={"oversight_officer": None}, confidence=0.60))
    return findings


def gate_payment(c: dict) -> list:
    """GATE 7 — PAYMENT: Does disbursement match delivery?"""
    findings = []
    payments = c.get("payments", [])
    deliverables = c.get("deliverables", [])

    if payments and not deliverables:
        total_paid = sum(p.get("amount", 0) for p in payments)
        findings.append(Finding(
            gate="PAYMENT", severity="critical",
            description=f"${total_paid:,.0f} disbursed with zero documented deliverables. Consistent with phantom delivery.",
            evidence={"total_paid": total_paid, "deliverables_count": 0}, confidence=0.80))

    for p in payments:
        pay_date = p.get("date", "")
        for d in deliverables:
            del_date = d.get("completion_date", "")
            if pay_date and del_date:
                try:
                    pd = datetime.fromisoformat(pay_date)
                    dd = datetime.fromisoformat(del_date)
                    if pd < dd:
                        gap = (dd - pd).days
                        findings.append(Finding(
                            gate="PAYMENT", severity="major",
                            description=f"Payment of ${p.get('amount', 0):,.0f} made {gap} days before deliverable '{d.get('name', '?')}' was completed.",
                            evidence={"payment_date": pay_date, "delivery_date": del_date, "gap_days": gap},
                            confidence=0.70))
                except (ValueError, TypeError):
                    pass
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# VERDICT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

ALL_GATES = [
    ("NEED", gate_need), ("SPEC", gate_spec), ("ENTITY", gate_entity),
    ("COMPETITION", gate_competition), ("PRICE", gate_price),
    ("AWARD", gate_award), ("PAYMENT", gate_payment),
]

def analyze(contract: dict) -> Verdict:
    """Run all 7 gates on a contract. BLOCKED = any critical. REVIEW = major findings. PASS = clean."""
    all_findings = []
    gate_results = {}

    for gate_name, gate_fn in ALL_GATES:
        findings = gate_fn(contract)
        gate_results[gate_name] = {
            "status": "FAIL" if any(f.severity == "critical" for f in findings)
                      else "WARN" if findings else "PASS",
            "findings_count": len(findings),
        }
        all_findings.extend(findings)

    critical_count = sum(1 for f in all_findings if f.severity == "critical")
    major_count = sum(1 for f in all_findings if f.severity == "major")
    verdict = "BLOCKED" if critical_count > 0 else "REVIEW" if major_count >= 1 else "PASS"
    avg_confidence = (sum(f.confidence for f in all_findings) / len(all_findings)) if all_findings else 0.95

    amount = contract.get("amount", 0)
    recovery_pct = 0.80 if critical_count >= 3 else 0.50 if critical_count >= 1 else 0.20 if major_count >= 2 else 0.0
    recovery_estimate = amount * recovery_pct

    cid = contract.get("id", "UNKNOWN")
    if verdict == "PASS":
        summary = f"Contract {cid}: No structural contradictions detected."
    elif verdict == "REVIEW":
        summary = f"Contract {cid}: {len(all_findings)} structural concern(s) detected. Manual review recommended."
    else:
        summary = f"Contract {cid}: BLOCKED — {critical_count} critical structural contradiction(s). ${recovery_estimate:,.0f} at risk."

    return Verdict(
        contract_id=cid, verdict=verdict,
        findings=[f.to_dict() for f in all_findings],
        confidence=round(avg_confidence, 3),
        recovery_estimate_usd=round(recovery_estimate, 2),
        gate_results=gate_results,
        analyzed_at=datetime.now().isoformat() + "Z",
        summary=summary,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO CONTRACTS — synthetic but structurally realistic
# Contract A is clean. Contract B is dirty. Contract C is subtle.
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_CONTRACTS = [
    {
        "id": "CLEAN-001",
        "description": "Supply and installation of water purification equipment for rural health clinics in the Northern Province, per WHO standards.",
        "category": "goods", "amount": 340_000, "currency": "USD",
        "procurement_method": "open", "award_date": "2025-06-15",
        "needs_assessment": "NA-2025-0042", "sole_source": False,
        "number_of_bidders": 5,
        "bids": [
            {"name": "AquaPure International", "amount": 340_000, "winner": True},
            {"name": "WaterTech Solutions", "amount": 365_000, "winner": False},
            {"name": "CleanFlow Ltd", "amount": 412_000, "winner": False},
            {"name": "HydroSys GmbH", "amount": 380_000, "winner": False},
            {"name": "PureSource Inc", "amount": 355_000, "winner": False},
        ],
        "comparable_average": 290_000,
        "vendor": {"name": "AquaPure International", "incorporation_date": "2012-03-20",
                   "address": "45 Industrial Way, Zurich", "registration_id": "CHE-123.456.789"},
        "decision_roles": {"need_author": "Dr. Sarah Mensah", "bid_evaluator": "Procurement Unit Team",
                           "award_approver": "James Okonkwo", "oversight_officer": "Internal Audit Division"},
        "deliverables": [{"name": "Water purification units x 12", "completion_date": "2025-09-01"},
                         {"name": "Installation and training", "completion_date": "2025-10-15"}],
        "payments": [{"amount": 170_000, "date": "2025-09-15"}, {"amount": 170_000, "date": "2025-11-01"}],
        "amendments": [], "specifications": {},
    },
    {
        "id": "DIRTY-002",
        "description": "Various consulting services as needed for ministry operations.",
        "category": "services", "amount": 4_800_000, "currency": "USD",
        "procurement_method": "open", "award_date": "2025-12-29",
        "needs_assessment": None, "sole_source": False,
        "number_of_bidders": 1,
        "bids": [{"name": "Brightwell Advisory Group", "amount": 4_800_000, "winner": True}],
        "comparable_average": 1_200_000,
        "vendor": {"name": "Brightwell Advisory Group", "incorporation_date": "2025-08-15",
                   "address": None, "registration_id": None},
        "decision_roles": {"need_author": "Minister Jean-Pierre Bouasse",
                           "bid_evaluator": "Minister Jean-Pierre Bouasse",
                           "award_approver": "Minister Jean-Pierre Bouasse",
                           "oversight_officer": None},
        "deliverables": [],
        "payments": [{"amount": 4_800_000, "date": "2025-12-30"}],
        "amendments": [], "specifications": {},
    },
    {
        "id": "SUBTLE-003",
        "description": "Construction of primary school building, Block C extension, Greenfield District. Compatible only with existing modular system.",
        "category": "works", "amount": 2_100_000, "currency": "USD",
        "procurement_method": "selective", "award_date": "2025-07-10",
        "needs_assessment": "NA-2025-0088", "sole_source": False,
        "number_of_bidders": 3,
        "bids": [
            {"name": "Greenfield Construction Co", "amount": 2_100_000, "winner": True},
            {"name": "Atlas Builders", "amount": 2_160_000, "winner": False},
            {"name": "Omega Structures Ltd", "amount": 2_120_000, "winner": False},
        ],
        "comparable_average": 1_800_000,
        "vendor": {"name": "Greenfield Construction Co", "incorporation_date": "2020-01-15",
                   "address": "12 Main Street, Greenfield", "registration_id": "GF-2020-4455"},
        "decision_roles": {"need_author": "Education Committee", "bid_evaluator": "District Procurement Office",
                           "award_approver": "Thomas Ndala", "oversight_officer": "Thomas Ndala"},
        "deliverables": [{"name": "Foundation and structure", "completion_date": "2025-12-01"},
                         {"name": "Finishing and handover", "completion_date": "2026-03-01"}],
        "payments": [{"amount": 840_000, "date": "2025-08-01"},
                     {"amount": 840_000, "date": "2025-11-15"},
                     {"amount": 420_000, "date": "2026-03-15"}],
        "amendments": [{"description": "Additional foundation work", "amount_change": 380_000},
                       {"description": "Material cost adjustment", "amount_change": 210_000}],
        "specifications": {},
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def print_verdict(v: Verdict):
    """Print a verdict to the terminal in a readable format."""
    bar = "=" * 70
    print(f"\n{bar}")
    label = {"BLOCKED": "BLOCKED", "REVIEW": "REVIEW", "PASS": "PASS"}[v.verdict]
    icon = {"BLOCKED": "[X]", "REVIEW": "[?]", "PASS": "[OK]"}[v.verdict]
    print(f"  {icon} {label}  |  Contract: {v.contract_id}")
    print(f"  Confidence: {v.confidence:.0%}  |  Recovery estimate: ${v.recovery_estimate_usd:,.0f}")
    print(bar)

    print("\n  GATE RESULTS:")
    for gate_name, result in v.gate_results.items():
        status = result["status"]
        icon = "X" if status == "FAIL" else "!" if status == "WARN" else "ok"
        count = result["findings_count"]
        suffix = f"  ({count} finding{'s' if count != 1 else ''})" if count else ""
        print(f"    [{icon:>2}] {gate_name:<12} {status}{suffix}")

    if v.findings:
        print(f"\n  FINDINGS ({len(v.findings)}):")
        for i, f in enumerate(v.findings, 1):
            sev = f["severity"].upper()
            print(f"\n    {i}. [{f['gate']}] {sev} (confidence: {f['confidence']:.0%})")
            print(f"       {f['description']}")
    else:
        print("\n  No structural contradictions detected.")

    print(f"\n  SUMMARY: {v.summary}")
    print(bar)


def run_demo():
    """Run the 3 demo contracts and print results."""
    print("\n" + "=" * 70)
    print("  SUNLIGHT — Structural Verification Engine")
    print("  Running demo: 3 contracts (1 clean, 1 dirty, 1 subtle)")
    print("=" * 70)

    all_verdicts = []
    for contract in DEMO_CONTRACTS:
        verdict = analyze(contract)
        print_verdict(verdict)
        all_verdicts.append(verdict)

    report = {
        "engine": "SUNLIGHT v0.1",
        "run_at": datetime.now().isoformat() + "Z",
        "contracts_analyzed": len(all_verdicts),
        "verdicts": {
            "PASS": sum(1 for v in all_verdicts if v.verdict == "PASS"),
            "REVIEW": sum(1 for v in all_verdicts if v.verdict == "REVIEW"),
            "BLOCKED": sum(1 for v in all_verdicts if v.verdict == "BLOCKED"),
        },
        "total_recovery_estimate_usd": sum(v.recovery_estimate_usd for v in all_verdicts),
        "results": [v.to_dict() for v in all_verdicts],
    }
    return report


def run_file(path: str):
    """Analyze a single contract JSON file."""
    with open(path, "r") as f:
        contract = json.load(f)
    verdict = analyze(contract)
    print_verdict(verdict)
    return verdict.to_dict()


def run_batch(folder: str):
    """Analyze all .json files in a folder."""
    results = []
    for fp in sorted(Path(folder).glob("*.json")):
        print(f"\n  Processing: {fp.name}")
        with open(fp, "r") as f:
            contract = json.load(f)
        verdict = analyze(contract)
        print_verdict(verdict)
        results.append(verdict.to_dict())
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) == 1:
        report = run_demo()
        out_path = "sunlight_report.json"
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Report saved: {out_path}")
        print(f"  Total at risk: ${report['total_recovery_estimate_usd']:,.0f}")
        print()
    elif sys.argv[1] == "--batch":
        if len(sys.argv) < 3:
            print("Usage: python sunlight_engine.py --batch <folder>")
            sys.exit(1)
        run_batch(sys.argv[2])
    else:
        run_file(sys.argv[1])
