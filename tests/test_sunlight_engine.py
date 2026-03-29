#!/usr/bin/env python3
"""
SUNLIGHT ENGINE — TEST SUITE
=============================
Tests that sunlight_engine.py does what it claims to do.

If any test fails, the engine is lying.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from sunlight_engine import analyze, Finding, Verdict

PASS_COUNT = 0
FAIL_COUNT = 0

def assert_eq(name, actual, expected):
    global PASS_COUNT, FAIL_COUNT
    if actual == expected:
        PASS_COUNT += 1
        print(f"  [PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}")
        print(f"         expected: {expected}")
        print(f"         got:      {actual}")

def assert_true(name, condition):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}")

def assert_in(name, needle, haystack):
    global PASS_COUNT, FAIL_COUNT
    if needle in haystack:
        PASS_COUNT += 1
        print(f"  [PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name} — '{needle}' not found")

# ═══════════════════════════════════════════════════════════════
# TEST 1: Clean contract gets PASS or REVIEW (never BLOCKED)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 1: Clean contract should not be BLOCKED ===")
clean = {
    "id": "T-CLEAN",
    "description": "Supply of 500 textbooks for District 4 primary schools per MoE curriculum.",
    "amount": 75_000, "currency": "USD",
    "procurement_method": "open", "award_date": "2025-03-01",
    "needs_assessment": "NA-2025-100", "sole_source": False,
    "number_of_bidders": 4,
    "bids": [
        {"name": "BookWorld", "amount": 75_000, "winner": True},
        {"name": "EduSupply", "amount": 82_000, "winner": False},
        {"name": "PageCraft", "amount": 91_500, "winner": False},
        {"name": "LearnBooks", "amount": 78_000, "winner": False},
    ],
    "comparable_average": 70_000,
    "vendor": {"name": "BookWorld Inc", "incorporation_date": "2015-06-01",
               "address": "10 Library Lane", "registration_id": "BW-2015"},
    "decision_roles": {"need_author": "Dr. Amara", "bid_evaluator": "Procurement Team",
                       "award_approver": "Director Keita", "oversight_officer": "Audit Unit"},
    "deliverables": [{"name": "500 textbooks delivered", "completion_date": "2025-05-01"}],
    "payments": [{"amount": 75_000, "date": "2025-05-15"}],
    "amendments": [], "specifications": {},
}
v = analyze(clean)
assert_true("Clean contract not BLOCKED", v.verdict != "BLOCKED")
assert_eq("Clean contract recovery is $0", v.recovery_estimate_usd, 0.0)
assert_true("Clean contract has 0 critical findings",
            all(f["severity"] != "critical" for f in v.findings))


# ═══════════════════════════════════════════════════════════════
# TEST 2: Shell company detection (entity gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 2: Shell company must be caught ===")
shell_co = {
    "id": "T-SHELL", "description": "IT infrastructure upgrade.",
    "amount": 2_000_000, "award_date": "2025-10-01",
    "needs_assessment": "NA-X", "procurement_method": "open",
    "number_of_bidders": 2, "bids": [],
    "vendor": {"name": "NewCo LLC", "incorporation_date": "2025-07-01",
               "address": None, "registration_id": None},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "servers", "completion_date": "2025-12-01"}],
    "payments": [{"amount": 2_000_000, "date": "2026-01-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(shell_co)
entity_findings = [f for f in v.findings if f["gate"] == "ENTITY"]
assert_true("Shell company detected", len(entity_findings) >= 1)
assert_true("Shell company is critical severity",
            any(f["severity"] == "critical" for f in entity_findings))
assert_in("Finding mentions age", "92 days", entity_findings[0]["description"])


# ═══════════════════════════════════════════════════════════════
# TEST 3: Political patron detection (award gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 3: Political patron must be caught ===")
patron = {
    "id": "T-PATRON", "description": "Road construction project.",
    "amount": 5_000_000, "award_date": "2025-06-01",
    "needs_assessment": "NA-Y", "procurement_method": "selective",
    "number_of_bidders": 3, "bids": [],
    "vendor": {"name": "RoadCo", "incorporation_date": "2018-01-01",
               "address": "123 Main", "registration_id": "RC-18"},
    "decision_roles": {
        "need_author": "Governor Mbeki",
        "bid_evaluator": "Governor Mbeki",
        "award_approver": "Governor Mbeki",
        "oversight_officer": None,
    },
    "deliverables": [{"name": "50km road", "completion_date": "2026-06-01"}],
    "payments": [{"amount": 5_000_000, "date": "2025-07-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(patron)
award_findings = [f for f in v.findings if f["gate"] == "AWARD"]
assert_true("Political patron detected", len(award_findings) >= 1)
patron_finding = [f for f in award_findings if "3 decision points" in f["description"]]
assert_true("Patron controls 3+ roles", len(patron_finding) >= 1)
assert_eq("Verdict is BLOCKED", v.verdict, "BLOCKED")


# ═══════════════════════════════════════════════════════════════
# TEST 4: Phantom delivery detection (payment gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 4: Phantom delivery must be caught ===")
phantom = {
    "id": "T-PHANTOM", "description": "Medical supply procurement.",
    "amount": 800_000, "award_date": "2025-04-01",
    "needs_assessment": "NA-Z", "procurement_method": "open",
    "number_of_bidders": 2, "bids": [],
    "vendor": {"name": "MedSupply", "incorporation_date": "2019-01-01",
               "address": "456 Health Rd", "registration_id": "MS-19"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [],
    "payments": [{"amount": 400_000, "date": "2025-05-01"},
                 {"amount": 400_000, "date": "2025-06-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(phantom)
pay_findings = [f for f in v.findings if f["gate"] == "PAYMENT"]
assert_true("Phantom delivery detected", len(pay_findings) >= 1)
assert_true("Phantom is critical", any(f["severity"] == "critical" for f in pay_findings))
assert_in("Mentions zero deliverables", "zero documented deliverables",
          pay_findings[0]["description"])


# ═══════════════════════════════════════════════════════════════
# TEST 5: Bid rigging / collusion detection (competition gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 5: Bid collusion must be caught ===")
rigged = {
    "id": "T-RIGGED", "description": "Office furniture procurement.",
    "amount": 300_000, "award_date": "2025-05-01",
    "needs_assessment": "NA-F", "procurement_method": "open",
    "number_of_bidders": 4,
    "bids": [
        {"name": "FurnCo", "amount": 300_000, "winner": True},
        {"name": "DeskWorld", "amount": 305_000, "winner": False},
        {"name": "ChairPlus", "amount": 302_000, "winner": False},
        {"name": "OfficePro", "amount": 307_000, "winner": False},
    ],
    "vendor": {"name": "FurnCo", "incorporation_date": "2017-01-01",
               "address": "1 Chair St", "registration_id": "FC-17"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "furniture", "completion_date": "2025-07-01"}],
    "payments": [{"amount": 300_000, "date": "2025-08-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(rigged)
comp_findings = [f for f in v.findings if f["gate"] == "COMPETITION"]
collusion = [f for f in comp_findings if "collusion" in f["description"].lower()
             or "rotation" in f["description"].lower()]
assert_true("Bid clustering detected", len(collusion) >= 1)
# All bids within 2.3% — should trigger
spread = (307_000 - 300_000) / 300_000
assert_true(f"Spread {spread:.1%} < 3% threshold", spread < 0.03)


# ═══════════════════════════════════════════════════════════════
# TEST 6: Price markup detection (price gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 6: 3x price markup must be caught ===")
markup = {
    "id": "T-MARKUP", "description": "Vehicle fleet maintenance contract.",
    "amount": 900_000, "award_date": "2025-08-01",
    "needs_assessment": "NA-V", "procurement_method": "open",
    "number_of_bidders": 2, "bids": [],
    "comparable_average": 300_000,
    "vendor": {"name": "AutoFix", "incorporation_date": "2016-01-01",
               "address": "9 Motor Way", "registration_id": "AF-16"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "maintenance", "completion_date": "2025-12-01"}],
    "payments": [{"amount": 900_000, "date": "2026-01-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(markup)
price_findings = [f for f in v.findings if f["gate"] == "PRICE"]
assert_true("Price markup detected", len(price_findings) >= 1)
assert_true("Markup is critical", any(f["severity"] == "critical" for f in price_findings))
assert_true("Evidence shows 3.0x ratio",
            any(f["evidence"].get("markup_ratio") == 3.0 for f in price_findings))


# ═══════════════════════════════════════════════════════════════
# TEST 7: Amendment inflation detection (price gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 7: 40% amendment inflation must be caught ===")
inflated = {
    "id": "T-INFLATE", "description": "Building renovation project.",
    "amount": 1_000_000, "award_date": "2025-03-01",
    "needs_assessment": "NA-B", "procurement_method": "open",
    "number_of_bidders": 3, "bids": [],
    "vendor": {"name": "BuildIt", "incorporation_date": "2014-01-01",
               "address": "7 Brick Rd", "registration_id": "BI-14"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "renovation", "completion_date": "2025-09-01"}],
    "payments": [{"amount": 1_400_000, "date": "2025-10-01"}],
    "amendments": [
        {"description": "Scope change 1", "amount_change": 250_000},
        {"description": "Material escalation", "amount_change": 150_000},
    ],
    "specifications": {},
}
v = analyze(inflated)
price_findings = [f for f in v.findings if f["gate"] == "PRICE"]
inflation_f = [f for f in price_findings if "amendment" in f["description"].lower()
               or "inflate" in f["description"].lower()]
assert_true("Amendment inflation detected", len(inflation_f) >= 1)
assert_true("40% inflation flagged as critical",
            any(f["severity"] == "critical" for f in inflation_f))


# ═══════════════════════════════════════════════════════════════
# TEST 8: Single bidder on open tender (competition gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 8: Single bidder on open tender must be caught ===")
single = {
    "id": "T-SINGLE", "description": "Security services for government buildings.",
    "amount": 500_000, "award_date": "2025-06-01",
    "needs_assessment": "NA-S", "procurement_method": "open",
    "number_of_bidders": 1, "bids": [{"name": "GuardCo", "amount": 500_000, "winner": True}],
    "vendor": {"name": "GuardCo", "incorporation_date": "2013-01-01",
               "address": "1 Safe St", "registration_id": "GC-13"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "12mo security", "completion_date": "2026-06-01"}],
    "payments": [{"amount": 500_000, "date": "2025-07-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(single)
comp = [f for f in v.findings if f["gate"] == "COMPETITION"]
assert_true("Single bidder flagged", len(comp) >= 1)
assert_true("Single bidder is critical", any(f["severity"] == "critical" for f in comp))

# ═══════════════════════════════════════════════════════════════
# TEST 9: Sole source without justification (spec gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 9: Sole source without justification ===")
sole = {
    "id": "T-SOLE", "description": "Proprietary software license renewal.",
    "amount": 200_000, "award_date": "2025-09-01",
    "needs_assessment": "NA-L", "procurement_method": "direct",
    "sole_source": True, "sole_source_justification": None,
    "number_of_bidders": 1, "bids": [],
    "vendor": {"name": "SoftCorp", "incorporation_date": "2010-01-01",
               "address": "5 Code Ave", "registration_id": "SC-10"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "license key", "completion_date": "2025-09-15"}],
    "payments": [{"amount": 200_000, "date": "2025-09-20"}],
    "amendments": [], "specifications": {},
}
v = analyze(sole)
spec_findings = [f for f in v.findings if f["gate"] == "SPEC"]
assert_true("Sole source no-justification caught", len(spec_findings) >= 1)
assert_true("Sole source is critical", any(f["severity"] == "critical" for f in spec_findings))

# ═══════════════════════════════════════════════════════════════
# TEST 10: Vague high-value need (need gate)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 10: Vague description on high-value contract ===")
vague = {
    "id": "T-VAGUE", "description": "Various sundry items as needed for general operations.",
    "amount": 3_000_000, "award_date": "2025-01-01",
    "needs_assessment": None, "procurement_method": "open",
    "number_of_bidders": 2, "bids": [],
    "vendor": {"name": "StuffCo", "incorporation_date": "2012-01-01",
               "address": "1 Stuff Rd", "registration_id": "ST-12"},
    "decision_roles": {"need_author": "A", "bid_evaluator": "B",
                       "award_approver": "C", "oversight_officer": "D"},
    "deliverables": [{"name": "items", "completion_date": "2025-06-01"}],
    "payments": [{"amount": 3_000_000, "date": "2025-07-01"}],
    "amendments": [], "specifications": {},
}
v = analyze(vague)
need_findings = [f for f in v.findings if f["gate"] == "NEED"]
assert_true("Vague terms detected", any("vague" in f["description"].lower() for f in need_findings))
assert_true("Missing needs assessment caught",
            any("needs assessment" in f["description"].lower() for f in need_findings))

# ═══════════════════════════════════════════════════════════════
# TEST 11: Empty contract doesn't crash
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 11: Empty contract -- no crash ===")
try:
    v = analyze({})
    assert_true("Empty contract returns a verdict", v.verdict in ["PASS", "REVIEW", "BLOCKED"])
    assert_true("Empty contract has contract_id", v.contract_id == "UNKNOWN")
except Exception as e:
    FAIL_COUNT += 1
    print(f"  [FAIL] Empty contract crashed: {e}")


# ═══════════════════════════════════════════════════════════════
# TEST 12: Verdict logic — BLOCKED requires critical findings
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 12: BLOCKED verdict requires critical findings ===")
# Clean contract from test 1 should never be BLOCKED
v_clean = analyze(clean)
has_critical = any(f["severity"] == "critical" for f in v_clean.findings)
assert_true("No critical -> not BLOCKED", not has_critical and v_clean.verdict != "BLOCKED")

# Patron contract from test 3 has criticals → must be BLOCKED
v_patron = analyze(patron)
has_critical = any(f["severity"] == "critical" for f in v_patron.findings)
assert_true("Critical findings -> BLOCKED", has_critical and v_patron.verdict == "BLOCKED")

# ═══════════════════════════════════════════════════════════════
# TEST 13: Recovery estimate scales with severity
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 13: Recovery estimate is non-zero on BLOCKED ===")
v_dirty = analyze(patron)  # patron has criticals
assert_true("BLOCKED contract has recovery > 0", v_dirty.recovery_estimate_usd > 0)
v_clean = analyze(clean)
assert_eq("Clean contract recovery is $0", v_clean.recovery_estimate_usd, 0.0)

# ═══════════════════════════════════════════════════════════════
# TEST 14: All 7 gates always run
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 14: All 7 gates present in every verdict ===")
expected_gates = {"NEED", "SPEC", "ENTITY", "COMPETITION", "PRICE", "AWARD", "PAYMENT"}
for cid, contract in [("clean", clean), ("patron", patron), ("empty", {})]:
    v = analyze(contract)
    actual_gates = set(v.gate_results.keys())
    assert_eq(f"All 7 gates present for {cid}", actual_gates, expected_gates)


# ═══════════════════════════════════════════════════════════════
# TEST 15: JSON serialization works (output is usable)
# ═══════════════════════════════════════════════════════════════
print("\n=== TEST 15: Verdict serializes to valid JSON ===")
import json
v = analyze(patron)
try:
    j = json.dumps(v.to_dict())
    parsed = json.loads(j)
    assert_true("JSON round-trip works", parsed["contract_id"] == "T-PATRON")
    assert_true("Findings survive serialization", len(parsed["findings"]) > 0)
except Exception as e:
    FAIL_COUNT += 1
    print(f"  [FAIL] JSON serialization failed: {e}")


# ═══════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = PASS_COUNT + FAIL_COUNT
print(f"  RESULTS: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
if FAIL_COUNT == 0:
    print("  ALL TESTS PASSED")
else:
    print(f"  {FAIL_COUNT} TEST(S) FAILED")
print("=" * 60 + "\n")
sys.exit(FAIL_COUNT)
