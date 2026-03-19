#!/usr/bin/env python3
"""
SUNLIGHT Live OCDS Ingestion — fetch real procurement data, score, and report.

Fetches contracts from a live OCDS API (UK Contracts Finder), transforms via
the OCDS adapter, ingests into a fresh database, runs the scoring pipeline,
and outputs:
  - Tier distribution summary
  - Top 10 most anomalous contracts
  - Full results CSV
  - Individual detection reports for top 10 flagged contracts
"""

import csv
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from ocds_adapter import transform_releases
from institutional_pipeline import InstitutionalPipeline
from detection_report import generate_detection_report
from case_builder import build_case_package
from sunlight_logging import get_logger

logger = get_logger("ingest_live")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

UK_OCDS_BASE = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
TARGET_CONTRACTS = 500
PAGE_SIZE = 100  # contracts per API call
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ocds_uk_live.db")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "uk_ocds_live")
CSV_PATH = os.path.join(REPORTS_DIR, "all_scores.csv")
SUMMARY_PATH = os.path.join(REPORTS_DIR, "summary.json")


# ---------------------------------------------------------------------------
# Step 0: Create database with schema
# ---------------------------------------------------------------------------

def create_db(db_path):
    """Create a fresh database with SUNLIGHT schema."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE contracts (
        contract_id TEXT PRIMARY KEY,
        award_amount REAL,
        vendor_name TEXT,
        agency_name TEXT,
        description TEXT,
        start_date TEXT,
        location TEXT,
        raw_data TEXT,
        raw_data_hash TEXT
    )""")

    c.execute("""CREATE TABLE political_donations (
        vendor_name TEXT,
        recipient_name TEXT,
        amount REAL,
        date TEXT,
        cycle TEXT,
        source TEXT
    )""")

    c.execute("""CREATE TABLE analysis_runs (
        run_id TEXT PRIMARY KEY,
        started_at TEXT,
        completed_at TEXT,
        status TEXT,
        run_seed INTEGER,
        config_json TEXT,
        config_hash TEXT,
        dataset_hash TEXT,
        contracts_analyzed INTEGER,
        n_contracts INTEGER,
        n_scored INTEGER,
        n_errors INTEGER,
        code_commit_hash TEXT,
        environment_json TEXT,
        model_version TEXT,
        summary_json TEXT,
        fdr_n_tests INTEGER,
        fdr_n_significant INTEGER
    )""")

    c.execute("""CREATE TABLE contract_scores (
        score_id TEXT PRIMARY KEY,
        contract_id TEXT,
        run_id TEXT,
        fraud_tier TEXT,
        tier TEXT,
        triage_priority INTEGER,
        confidence_score INTEGER,
        raw_pvalue REAL,
        fdr_adjusted_pvalue REAL,
        survives_fdr INTEGER,
        markup_pct REAL,
        markup_ci_lower REAL,
        markup_ci_upper REAL,
        raw_zscore REAL,
        log_zscore REAL,
        bootstrap_percentile REAL,
        percentile_ci_lower REAL,
        percentile_ci_upper REAL,
        bayesian_prior REAL,
        bayesian_likelihood_ratio REAL,
        bayesian_posterior REAL,
        comparable_count INTEGER,
        insufficient_comparables INTEGER,
        selection_params_json TEXT,
        scored_at TEXT,
        analyzed_at TEXT,
        UNIQUE(contract_id, run_id)
    )""")

    c.execute("""CREATE TABLE audit_log (
        log_id TEXT PRIMARY KEY,
        sequence_number INTEGER UNIQUE,
        timestamp TEXT,
        action_type TEXT,
        entity_id TEXT,
        previous_log_hash TEXT,
        current_log_hash TEXT,
        action TEXT,
        run_id TEXT,
        details TEXT,
        previous_hash TEXT,
        entry_hash TEXT
    )""")

    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Step 1: Fetch OCDS releases from UK Contracts Finder
# ---------------------------------------------------------------------------

def fetch_releases(target_count, page_size=100):
    """Fetch OCDS releases from the UK Contracts Finder API."""
    all_releases = []
    url = f"{UK_OCDS_BASE}?limit={page_size}"
    page = 0

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        while len(all_releases) < target_count and url:
            page += 1
            print(f"  Fetching page {page} ({len(all_releases)} releases so far)...")

            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break

            releases = data.get("releases", [])
            if not releases:
                print(f"  No more releases on page {page}")
                break

            all_releases.extend(releases)
            url = data.get("links", {}).get("next", "")
            time.sleep(0.3)  # Be polite to the API

    return all_releases[:target_count]


# ---------------------------------------------------------------------------
# Step 2: Transform + ingest
# ---------------------------------------------------------------------------

def ingest_contracts(db_path, releases):
    """Transform OCDS releases and insert into database."""
    contracts = transform_releases(releases, validate=True)
    print(f"  OCDS adapter produced {len(contracts)} valid contracts from {len(releases)} releases")

    conn = sqlite3.connect(db_path)
    inserted = 0
    skipped = 0
    seen_ids = set()

    for c in contracts:
        cid = c.contract_id
        if cid in seen_ids:
            skipped += 1
            continue
        seen_ids.add(cid)

        raw_hash = hashlib.sha256(
            f"{cid}:{c.award_amount}:{c.vendor_name}".encode()
        ).hexdigest()

        try:
            conn.execute(
                """INSERT OR IGNORE INTO contracts
                   (contract_id, award_amount, vendor_name, agency_name,
                    description, start_date, raw_data_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cid, c.award_amount, c.vendor_name, c.agency_name,
                 c.description, c.start_date, raw_hash),
            )
            if conn.total_changes:
                inserted += 1
        except Exception as e:
            skipped += 1

    conn.commit()

    # Verify actual count
    actual = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
    conn.close()

    return inserted, skipped, actual


# ---------------------------------------------------------------------------
# Step 3: Run scoring pipeline
# ---------------------------------------------------------------------------

def run_pipeline(db_path):
    """Run the SUNLIGHT scoring pipeline."""
    pipeline = InstitutionalPipeline(db_path)
    result = pipeline.run(
        run_seed=42,
        config={"n_bootstrap": 1000, "min_comparables": 3},
        verbose=True,
        calibration_profile="world_bank_global",  # UK data → use global profile
    )
    return result


# ---------------------------------------------------------------------------
# Step 4: Extract results and generate outputs
# ---------------------------------------------------------------------------

def extract_results(db_path, run_id):
    """Extract scored contracts and build summary."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(
        """SELECT cs.*, ct.vendor_name, ct.agency_name, ct.award_amount,
                  ct.description, ct.start_date
           FROM contract_scores cs
           JOIN contracts ct ON cs.contract_id = ct.contract_id
           WHERE cs.run_id = ?
           ORDER BY cs.triage_priority ASC""",
        (run_id,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def build_summary(scores, pipeline_result):
    """Build a summary dict."""
    tier_counts = {"RED": 0, "YELLOW": 0, "GREEN": 0, "GRAY": 0}
    for s in scores:
        tier = s.get("fraud_tier") or s.get("tier", "UNKNOWN")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    flagged = [s for s in scores if (s.get("fraud_tier") or s.get("tier")) in ("RED", "YELLOW")]
    flagged.sort(key=lambda x: x.get("triage_priority", 9999))

    # Top 10
    top10 = []
    for s in flagged[:10]:
        top10.append({
            "contract_id": s["contract_id"],
            "vendor_name": s.get("vendor_name", ""),
            "agency_name": s.get("agency_name", ""),
            "award_amount": s.get("award_amount", 0),
            "fraud_tier": s.get("fraud_tier") or s.get("tier"),
            "confidence_score": s.get("confidence_score", 0),
            "markup_pct": s.get("markup_pct"),
            "markup_ci_lower": s.get("markup_ci_lower"),
            "markup_ci_upper": s.get("markup_ci_upper"),
            "bayesian_posterior": s.get("bayesian_posterior"),
            "bootstrap_percentile": s.get("bootstrap_percentile"),
            "raw_zscore": s.get("raw_zscore"),
            "comparable_count": s.get("comparable_count"),
            "description": (s.get("description") or "")[:120],
        })

    # Value stats
    amounts = [s.get("award_amount", 0) for s in scores if s.get("award_amount")]
    flagged_amounts = [s.get("award_amount", 0) for s in flagged if s.get("award_amount")]

    return {
        "pipeline": pipeline_result,
        "tier_distribution": tier_counts,
        "total_scored": len(scores),
        "total_flagged": len(flagged),
        "flag_rate_pct": round(len(flagged) / max(len(scores), 1) * 100, 1),
        "value_stats": {
            "total_value": sum(amounts),
            "mean_value": round(np.mean(amounts), 2) if amounts else 0,
            "median_value": round(float(np.median(amounts)), 2) if amounts else 0,
            "flagged_value": sum(flagged_amounts),
        },
        "top_10_flagged": top10,
    }


def write_csv(scores, csv_path):
    """Write all scores to CSV."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    fields = [
        "contract_id", "vendor_name", "agency_name", "award_amount",
        "fraud_tier", "confidence_score", "triage_priority",
        "markup_pct", "markup_ci_lower", "markup_ci_upper",
        "raw_zscore", "log_zscore",
        "bootstrap_percentile", "bayesian_posterior",
        "raw_pvalue", "fdr_adjusted_pvalue", "survives_fdr",
        "comparable_count", "description",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for s in scores:
            row = {k: s.get(k) for k in fields}
            # Truncate description
            if row.get("description"):
                row["description"] = row["description"][:200]
            writer.writerow(row)


def write_detection_reports(db_path, top10, run_id, reports_dir):
    """Generate individual detection reports for top 10 flagged contracts."""
    reports_subdir = os.path.join(reports_dir, "detection_reports")
    os.makedirs(reports_subdir, exist_ok=True)

    for item in top10:
        cid = item["contract_id"]
        safe_name = cid.replace("/", "_").replace(":", "_")[:80]

        # Case package (markdown + JSON)
        try:
            pkg = build_case_package(db_path, cid, run_id=run_id)
            md_path = os.path.join(reports_subdir, f"{safe_name}.md")
            json_path = os.path.join(reports_subdir, f"{safe_name}.json")

            with open(md_path, "w") as f:
                f.write(pkg.to_markdown())
            with open(json_path, "w") as f:
                f.write(pkg.to_json())
        except Exception as e:
            print(f"  Warning: could not generate report for {cid}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("SUNLIGHT Live OCDS Ingestion — UK Contracts Finder")
    print("=" * 70)
    print()

    # Step 0: Create database
    print("[1/5] Creating fresh database...")
    db_path = create_db(DB_PATH)
    print(f"  Database: {db_path}")

    # Step 1: Fetch
    print(f"\n[2/5] Fetching ~{TARGET_CONTRACTS} OCDS releases from UK Contracts Finder...")
    t0 = time.time()
    releases = fetch_releases(TARGET_CONTRACTS * 2, PAGE_SIZE)  # Fetch extra since not all have awards
    fetch_time = time.time() - t0
    print(f"  Fetched {len(releases)} releases in {fetch_time:.1f}s")

    # Step 2: Ingest
    print(f"\n[3/5] Transforming + ingesting contracts...")
    inserted, skipped, actual = ingest_contracts(db_path, releases)
    print(f"  Inserted: {inserted} | Skipped: {skipped} | In DB: {actual}")

    if actual < 10:
        print("\nERROR: Too few contracts ingested. Cannot run meaningful analysis.")
        return

    # Step 3: Score
    print(f"\n[4/5] Running SUNLIGHT scoring pipeline on {actual} contracts...")
    t0 = time.time()
    pipeline_result = run_pipeline(db_path)
    score_time = time.time() - t0
    run_id = pipeline_result["run_id"]
    print(f"  Pipeline complete in {score_time:.1f}s")
    print(f"  Run ID: {run_id}")
    print(f"  Tier counts: {pipeline_result['tier_counts']}")

    # Step 4: Extract + report
    print(f"\n[5/5] Generating reports...")
    scores = extract_results(db_path, run_id)
    summary = build_summary(scores, pipeline_result)

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # CSV
    write_csv(scores, CSV_PATH)
    print(f"  CSV: {CSV_PATH} ({len(scores)} rows)")

    # Summary JSON
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  Summary: {SUMMARY_PATH}")

    # Detection reports for top 10
    top10 = summary["top_10_flagged"]
    write_detection_reports(db_path, top10, run_id, REPORTS_DIR)
    print(f"  Detection reports: {REPORTS_DIR}/detection_reports/ ({len(top10)} reports)")

    # Print summary
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    tc = summary["tier_distribution"]
    total = summary["total_scored"]
    print(f"\n  Contracts scored: {total}")
    print(f"  RED:    {tc.get('RED', 0):>4}  ({tc.get('RED', 0)/max(total,1)*100:.1f}%)")
    print(f"  YELLOW: {tc.get('YELLOW', 0):>4}  ({tc.get('YELLOW', 0)/max(total,1)*100:.1f}%)")
    print(f"  GREEN:  {tc.get('GREEN', 0):>4}  ({tc.get('GREEN', 0)/max(total,1)*100:.1f}%)")
    print(f"  GRAY:   {tc.get('GRAY', 0):>4}  ({tc.get('GRAY', 0)/max(total,1)*100:.1f}%)")
    print(f"\n  Flag rate: {summary['flag_rate_pct']}%")
    vs = summary["value_stats"]
    print(f"  Total value: £{vs['total_value']:,.0f}")
    print(f"  Flagged value: £{vs['flagged_value']:,.0f}")

    if top10:
        print(f"\n  TOP {len(top10)} MOST ANOMALOUS CONTRACTS:")
        print(f"  {'Tier':<7} {'Amount':>14} {'Markup%':>9} {'CI Lo':>8} {'Conf':>5} {'Vendor':<30} {'Agency':<25}")
        print(f"  {'-'*6} {'-'*14} {'-'*9} {'-'*8} {'-'*5} {'-'*30} {'-'*25}")
        for item in top10:
            tier = item["fraud_tier"]
            amt = item["award_amount"]
            markup = item.get("markup_pct")
            ci_lo = item.get("markup_ci_lower")
            conf = item.get("confidence_score", 0)
            vendor = (item.get("vendor_name") or "")[:30]
            agency = (item.get("agency_name") or "")[:25]
            markup_s = f"{markup:.0f}%" if markup is not None else "N/A"
            ci_s = f"{ci_lo:.0f}%" if ci_lo is not None else "N/A"
            print(f"  {tier:<7} £{amt:>13,.0f} {markup_s:>9} {ci_s:>8} {conf:>5.0f} {vendor:<30} {agency:<25}")

    print(f"\n  Files saved to: {REPORTS_DIR}/")
    print()


if __name__ == "__main__":
    main()
