#!/usr/bin/env python3
"""
SUNLIGHT Vendor History Analyzer
Queries vendor contract history to build pattern evidence.
"""

import sqlite3
import json
import argparse
from pathlib import Path
from statistics import mean, stdev
import sys

TOP_5_VENDORS = ["JVYS", "OPTUM", "GENERAL DYNAMICS", "LOCKHEED MARTIN", "BELL TEXTRON"]
FLAGGED_CONTRACTS = {
    "JVYS": ["DAAH0102CR190"],
    "OPTUM": ["36C10G25K0180", "36C10G24K0098"],
    "GENERAL DYNAMICS": ["HHSM5000001"],
    "LOCKHEED MARTIN": ["N0002409C2303"],
    "BELL TEXTRON": ["N0001916C0003"],
}


def connect_db(db_path):
    if not Path(db_path).exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)
    return sqlite3.connect(db_path)


def get_vendor_history(conn, vendor_name, table="contracts_clean"):
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT contract_id, award_amount, agency_name, description, start_date, award_type
        FROM {table} WHERE UPPER(vendor_name) LIKE UPPER(?) ORDER BY start_date DESC
    """, (f"%{vendor_name}%",))
    return [{"contract_id": r[0], "award_amount": r[1], "agency_name": r[2], "description": r[3], "start_date": r[4], "award_type": r[5]} for r in cursor.fetchall()]


def analyze_vendor(conn, vendor_name):
    contracts = get_vendor_history(conn, vendor_name)
    if not contracts:
        return {"vendor": vendor_name, "status": "NOT_FOUND", "total_contracts": 0}
    amounts = [c["award_amount"] for c in contracts if c["award_amount"]]
    analysis = {"vendor": vendor_name, "total_contracts": len(contracts), "total_value": sum(amounts), "contracts": contracts}
    if len(amounts) >= 2:
        analysis["vendor_baseline"] = {"mean": mean(amounts), "min": min(amounts), "max": max(amounts)}
    flagged_ids = FLAGGED_CONTRACTS.get(vendor_name.upper(), [])
    analysis["flagged_contracts"] = [c for c in contracts if c["contract_id"] in flagged_ids]
    analysis["normal_contracts"] = [c for c in contracts if c["contract_id"] not in flagged_ids]
    if analysis["normal_contracts"] and analysis["flagged_contracts"]:
        normal_amounts = [c["award_amount"] for c in analysis["normal_contracts"] if c["award_amount"]]
        flagged_amounts = [c["award_amount"] for c in analysis["flagged_contracts"] if c["award_amount"]]
        if normal_amounts and flagged_amounts:
            normal_mean = mean(normal_amounts)
            flagged_mean = mean(flagged_amounts)
            deviation = ((flagged_mean - normal_mean) / normal_mean * 100) if normal_mean > 0 else 0
            analysis["pattern_evidence"] = {"normal_mean": normal_mean, "flagged_mean": flagged_mean, "deviation_pct": deviation, "strength": "STRONG" if len(analysis["normal_contracts"]) >= 3 else "MODERATE"}
    return analysis


def print_report(analysis):
    print("\n" + "=" * 70)
    print(f"VENDOR: {analysis['vendor']}")
    print("=" * 70)
    if analysis.get("status") == "NOT_FOUND":
        print("No contracts found")
        return
    print(f"Total contracts: {analysis['total_contracts']}")
    print(f"Total value: ${analysis['total_value']:,.0f}")
    if analysis.get("vendor_baseline"):
        print(f"Baseline mean: ${analysis['vendor_baseline']['mean']:,.0f}")
    print(f"\nFlagged contracts: {len(analysis.get('flagged_contracts', []))}")
    for c in analysis.get("flagged_contracts", []):
        print(f"  🔴 {c['contract_id']}: ${c['award_amount']:,.0f}")
    print(f"\nNormal contracts: {len(analysis.get('normal_contracts', []))}")
    for c in analysis.get("normal_contracts", [])[:3]:
        print(f"  ⚪ {c['contract_id']}: ${c['award_amount']:,.0f}")
    if len(analysis.get("normal_contracts", [])) > 3:
        print(f"  ... and {len(analysis['normal_contracts']) - 3} more")
    if analysis.get("pattern_evidence"):
        pe = analysis["pattern_evidence"]
        print(f"\nPATTERN EVIDENCE ({pe['strength']}):")
        print(f"  Normal contracts avg: ${pe['normal_mean']:,.0f}")
        print(f"  Flagged contracts avg: ${pe['flagged_mean']:,.0f}")
        print(f"  Deviation: {pe['deviation_pct']:,.0f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--vendor")
    parser.add_argument("--top5", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    conn = connect_db(args.db)
    if args.top5:
        for vendor in TOP_5_VENDORS:
            analysis = analyze_vendor(conn, vendor)
            print_report(analysis)
    elif args.vendor:
        analysis = analyze_vendor(conn, args.vendor)
        print_report(analysis)
    conn.close()


if __name__ == "__main__":
    main()
