#!/usr/bin/env python3
"""
SUNLIGHT Demo Environment Seed Script
=======================================

Creates a self-contained demo database with:
- 100 anonymized contracts across 5 agencies (mix of clean and flagged)
- Political donation records for suspect vendors
- Pre-run detection analysis with full statistical evidence
- Sample detection reports (JSON + Markdown) for flagged contracts

Usage:
    python scripts/seed_demo.py                  # Creates data/demo.db
    python scripts/seed_demo.py --out /tmp/demo  # Custom output directory

A prospect can see SUNLIGHT working in 5 minutes:
    1. Run this script (~30 seconds)
    2. Start the API: SUNLIGHT_DB_PATH=data/demo.db python -m uvicorn code.api:app
    3. Open http://localhost:8000/docs — Swagger UI with live data
    4. Try: GET /reports/triage — see flagged contracts ranked by priority
    5. Try: GET /reports/detection/{id}?format=markdown — read a full report
"""

import os
import sys
import sqlite3
import hashlib
import json
import random
import time
from datetime import datetime, timezone, timedelta

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from institutional_pipeline import InstitutionalPipeline
from detection_report import generate_detection_report, render_markdown

# ---------------------------------------------------------------------------
# Anonymized demo contract data
# ---------------------------------------------------------------------------

AGENCIES = [
    'DEPARTMENT OF DEFENSE',
    'DEPARTMENT OF ENERGY',
    'DEPARTMENT OF HEALTH AND HUMAN SERVICES',
    'DEPARTMENT OF HOMELAND SECURITY',
    'DEPARTMENT OF TRANSPORTATION',
]

# Realistic vendor names (anonymized)
VENDORS = [
    'Apex Defense Systems', 'Blackrock Logistics LLC', 'Citadel Technical Services',
    'Dynamic Solutions Group', 'Eagle Point Engineering', 'Frontier Security Inc',
    'Guardian Technologies', 'Horizon Systems Corp', 'Integrity Services LLC',
    'Jackson & Associates', 'Keystone Infrastructure', 'Liberty Consulting Group',
    'Meridian Research Partners', 'Northbridge Analytics', 'Olympus Procurement',
    'Pacific Rim Solutions', 'Quantum Defense Corp', 'Redline Support Services',
    'Sentinel Operations Inc', 'Trident Aerospace', 'United Systems Group',
    'Vanguard Technical LLC', 'Westfield Logistics', 'Xenon Engineering',
    'Yorktown Defense', 'Zenith Consulting',
]

# Contract descriptions by agency
DESCRIPTIONS = {
    'DEPARTMENT OF DEFENSE': [
        'Logistics support and supply chain management',
        'IT systems modernization and cybersecurity upgrade',
        'Vehicle fleet maintenance and repair services',
        'Communications infrastructure deployment',
        'Training and simulation systems',
        'Spare parts procurement and inventory management',
        'Base operations and facilities maintenance',
        'Intelligence analysis software development',
        'Weapons systems testing and evaluation',
        'Personnel security screening services',
    ],
    'DEPARTMENT OF ENERGY': [
        'Solar panel array installation and maintenance',
        'Wind turbine component replacement',
        'Nuclear facility decommissioning support',
        'Grid modernization consulting services',
        'Energy efficiency retrofit program',
        'Radiation monitoring equipment supply',
        'Research laboratory equipment procurement',
        'Environmental remediation services',
    ],
    'DEPARTMENT OF HEALTH AND HUMAN SERVICES': [
        'Electronic health records system implementation',
        'Clinical trial data management platform',
        'Public health surveillance software',
        'Medical device procurement and distribution',
        'Healthcare facility construction management',
        'Pharmaceutical supply chain consulting',
        'Telehealth infrastructure deployment',
    ],
    'DEPARTMENT OF HOMELAND SECURITY': [
        'Border surveillance technology systems',
        'Cybersecurity incident response services',
        'Biometric identification system upgrade',
        'Emergency communications network',
        'Port security screening equipment',
        'Threat assessment analytics platform',
        'Disaster response logistics coordination',
    ],
    'DEPARTMENT OF TRANSPORTATION': [
        'Highway bridge inspection and repair',
        'Air traffic control system modernization',
        'Rail safety monitoring equipment',
        'Maritime navigation system upgrade',
        'Transportation data analytics platform',
        'Vehicle crash testing and safety analysis',
        'Public transit fleet electrification',
    ],
}

# Median contract amounts per agency (realistic ranges)
AGENCY_MEDIANS = {
    'DEPARTMENT OF DEFENSE': 6_500_000,
    'DEPARTMENT OF ENERGY': 2_200_000,
    'DEPARTMENT OF HEALTH AND HUMAN SERVICES': 3_500_000,
    'DEPARTMENT OF HOMELAND SECURITY': 4_000_000,
    'DEPARTMENT OF TRANSPORTATION': 2_800_000,
}


def generate_demo_contracts(rng):
    """Generate 100 contracts with a realistic mix of clean and flagged."""
    contracts = []
    contract_num = 0

    for agency in AGENCIES:
        median = AGENCY_MEDIANS[agency]
        prefix = agency.split()[-1][:3].upper()
        descs = DESCRIPTIONS[agency]
        n_normal = 16  # 80 normal contracts total

        # Normal contracts: 0.5x to 1.5x median (Gaussian around median)
        for i in range(n_normal):
            contract_num += 1
            amount = max(100_000, int(rng.gauss(median, median * 0.25)))
            vendor = rng.choice(VENDORS)
            desc = rng.choice(descs)
            days_ago = rng.randint(30, 730)
            start_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')

            contracts.append({
                'contract_id': f'DEMO-{prefix}-{contract_num:03d}',
                'award_amount': amount,
                'vendor_name': vendor,
                'agency_name': agency,
                'description': desc,
                'start_date': start_date,
                'is_flagged': False,
            })

        # Flagged contracts: inflated amounts (2x-6x median)
        flag_profiles = [
            # (multiplier, vendor, flag_reason)
            (2.5, None, 'elevated_markup'),    # YELLOW candidate
            (3.5, None, 'high_markup'),         # YELLOW/RED candidate
            (5.0, None, 'extreme_markup'),      # RED candidate
            (4.0, None, 'high_with_donations'), # RED with political donations
        ]

        for mult, vendor_override, reason in flag_profiles:
            contract_num += 1
            amount = int(median * mult)
            vendor = vendor_override or rng.choice(VENDORS[:8])  # Repeat vendors for realism
            desc = rng.choice(descs)
            days_ago = rng.randint(30, 365)
            start_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')

            contracts.append({
                'contract_id': f'DEMO-{prefix}-{contract_num:03d}',
                'award_amount': amount,
                'vendor_name': vendor,
                'agency_name': agency,
                'description': desc,
                'start_date': start_date,
                'is_flagged': True,
                'flag_reason': reason,
            })

    return contracts


def create_demo_db(db_path):
    """Create a fresh demo database with full schema."""
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

    c.execute("""CREATE TABLE contract_amendments (
        amendment_id TEXT PRIMARY KEY,
        contract_id TEXT,
        modification_number TEXT,
        base_amount REAL,
        current_amount REAL,
        growth_percentage REAL,
        description TEXT,
        effective_date TEXT
    )""")

    # Indexes for query performance
    c.execute("CREATE INDEX idx_contracts_agency ON contracts(agency_name)")
    c.execute("CREATE INDEX idx_contracts_vendor ON contracts(vendor_name)")
    c.execute("CREATE INDEX idx_contracts_amount ON contracts(award_amount)")
    c.execute("CREATE INDEX idx_scores_run ON contract_scores(run_id)")
    c.execute("CREATE INDEX idx_scores_tier ON contract_scores(fraud_tier)")
    c.execute("CREATE INDEX idx_scores_contract ON contract_scores(contract_id)")
    c.execute("CREATE INDEX idx_audit_seq ON audit_log(sequence_number)")

    conn.commit()
    conn.close()


def seed_contracts(db_path, contracts):
    """Insert contracts and political donations into the demo database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Track vendors with political donation flags
    donation_vendors = set()

    for con in contracts:
        raw_hash = hashlib.sha256(
            f"{con['contract_id']}:{con['award_amount']}:{con['vendor_name']}".encode()
        ).hexdigest()

        c.execute(
            "INSERT INTO contracts VALUES (?,?,?,?,?,?,?,?,?)",
            (con['contract_id'], con['award_amount'], con['vendor_name'],
             con['agency_name'], con['description'], con['start_date'],
             None, None, raw_hash),
        )

        # Add political donations for flagged contracts with that reason
        if con.get('flag_reason') == 'high_with_donations':
            donation_vendors.add(con['vendor_name'])

    # Insert political donations for suspect vendors
    committees = [
        'Senate Armed Services Committee',
        'House Appropriations Subcommittee',
        'Senate Energy Committee',
        'House Homeland Security Committee',
    ]
    rng = random.Random(42)
    for vendor in donation_vendors:
        n_donations = rng.randint(2, 5)
        for _ in range(n_donations):
            c.execute(
                "INSERT INTO political_donations VALUES (?,?,?,?,?,?)",
                (vendor, rng.choice(committees),
                 rng.randint(50_000, 500_000),
                 f'202{rng.randint(3,5)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}',
                 f'202{rng.randint(3,5)}', 'DEMO_DATA'),
            )

    conn.commit()
    conn.close()
    return donation_vendors


def run_analysis(db_path):
    """Run the full scoring pipeline on demo contracts."""
    pipeline = InstitutionalPipeline(db_path)
    result = pipeline.run(
        run_seed=12345,
        config={
            'n_bootstrap': 1000,
            'fdr_alpha': 0.10,
        },
        verbose=False,
    )
    return result


def generate_sample_reports(db_path, out_dir, run_id):
    """Generate sample detection reports for all RED and YELLOW contracts."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(
        "SELECT contract_id, fraud_tier FROM contract_scores "
        "WHERE run_id = ? AND fraud_tier IN ('RED', 'YELLOW') "
        "ORDER BY triage_priority ASC",
        (run_id,),
    )
    flagged = c.fetchall()
    conn.close()

    reports_dir = os.path.join(out_dir, 'sample_reports')
    os.makedirs(reports_dir, exist_ok=True)

    generated = []
    for contract_id, tier in flagged:
        # JSON report
        report = generate_detection_report(db_path, contract_id, run_id=run_id)
        json_path = os.path.join(reports_dir, f'detection_{contract_id}.json')
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # Markdown report
        md_content = render_markdown(report)
        md_path = os.path.join(reports_dir, f'detection_{contract_id}.md')
        with open(md_path, 'w') as f:
            f.write(md_content)

        generated.append({'contract_id': contract_id, 'tier': tier})

    return generated


def print_summary(contracts, result, reports, db_path):
    """Print a summary of the demo environment."""
    # Count actual tiers from DB
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT fraud_tier, COUNT(*) FROM contract_scores "
        "WHERE run_id = ? GROUP BY fraud_tier ORDER BY fraud_tier",
        (result['run_id'],),
    )
    tier_counts = dict(c.fetchall())

    c.execute(
        "SELECT cs.contract_id, cs.fraud_tier, cs.confidence_score, "
        "cs.markup_pct, co.vendor_name, co.agency_name, co.award_amount "
        "FROM contract_scores cs JOIN contracts co ON cs.contract_id = co.contract_id "
        "WHERE cs.run_id = ? AND cs.fraud_tier = 'RED' ORDER BY cs.triage_priority ASC",
        (result['run_id'],),
    )
    red_contracts = c.fetchall()

    c.execute(
        "SELECT cs.contract_id, cs.fraud_tier, cs.confidence_score, "
        "cs.markup_pct, co.vendor_name, co.agency_name, co.award_amount "
        "FROM contract_scores cs JOIN contracts co ON cs.contract_id = co.contract_id "
        "WHERE cs.run_id = ? AND cs.fraud_tier = 'YELLOW' ORDER BY cs.triage_priority ASC LIMIT 5",
        (result['run_id'],),
    )
    yellow_contracts = c.fetchall()
    conn.close()

    print()
    print('=' * 70)
    print('  SUNLIGHT Demo Environment — Ready')
    print('=' * 70)
    print()
    print(f'  Database:     {db_path}')
    print(f'  Contracts:    {len(contracts)}')
    print(f'  Run ID:       {result["run_id"]}')
    print(f'  Scored:       {result["n_scored"]}')
    print()
    print('  Tier Distribution:')
    for tier in ['RED', 'YELLOW', 'GREEN', 'GRAY']:
        count = tier_counts.get(tier, 0)
        bar = '#' * count
        print(f'    {tier:6s}  {count:3d}  {bar}')
    print()

    if red_contracts:
        print('  Top RED-Flagged Contracts:')
        print(f'    {"Contract":<20s} {"Vendor":<28s} {"Amount":>14s} {"Markup":>8s} {"Conf":>5s}')
        print(f'    {"─"*20} {"─"*28} {"─"*14} {"─"*8} {"─"*5}')
        for cid, tier, conf, markup, vendor, agency, amount in red_contracts[:5]:
            print(f'    {cid:<20s} {vendor[:27]:<28s} ${amount:>12,.0f} {markup:>7.0f}% {conf:>4d}')
        print()

    if yellow_contracts:
        print('  Top YELLOW-Flagged Contracts:')
        print(f'    {"Contract":<20s} {"Vendor":<28s} {"Amount":>14s} {"Markup":>8s} {"Conf":>5s}')
        print(f'    {"─"*20} {"─"*28} {"─"*14} {"─"*8} {"─"*5}')
        for cid, tier, conf, markup, vendor, agency, amount in yellow_contracts:
            print(f'    {cid:<20s} {vendor[:27]:<28s} ${amount:>12,.0f} {markup:>7.0f}% {conf:>4d}')
        print()

    print(f'  Sample Reports: {len(reports)} generated')
    if reports:
        for r in reports[:3]:
            print(f'    - {r["contract_id"]} ({r["tier"]})')
        if len(reports) > 3:
            print(f'    - ... and {len(reports) - 3} more')
    print()
    print('  Quick Start:')
    print(f'    SUNLIGHT_DB_PATH={db_path} uvicorn code.api:app --reload')
    print()
    print('  Then visit:')
    print('    http://localhost:8000/docs                          — Swagger UI')
    print('    http://localhost:8000/reports/triage                — Flagged queue')
    print('    http://localhost:8000/health                        — System health')
    if red_contracts:
        top_id = red_contracts[0][0]
        print(f'    http://localhost:8000/reports/detection/{top_id}?format=markdown')
    print()
    print('=' * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Seed a SUNLIGHT demo environment')
    parser.add_argument('--out', default=None, help='Output directory (default: data/)')
    parser.add_argument('--seed', type=int, default=2026, help='Random seed for reproducibility')
    args = parser.parse_args()

    # Resolve paths
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out or os.path.join(repo_root, 'data')
    os.makedirs(out_dir, exist_ok=True)
    db_path = os.path.join(out_dir, 'demo.db')

    print('SUNLIGHT Demo Seed')
    print('─' * 40)

    # Step 1: Generate contracts
    rng = random.Random(args.seed)
    print('[1/4] Generating 100 anonymized contracts...')
    contracts = generate_demo_contracts(rng)
    print(f'      {len(contracts)} contracts across {len(AGENCIES)} agencies')

    # Step 2: Create database and seed
    print(f'[2/4] Creating demo database: {db_path}')
    create_demo_db(db_path)
    donation_vendors = seed_contracts(db_path, contracts)
    n_flagged = sum(1 for c in contracts if c.get('is_flagged'))
    print(f'      {len(contracts)} contracts inserted ({n_flagged} intentionally inflated)')
    if donation_vendors:
        print(f'      {len(donation_vendors)} vendors with political donation records')

    # Step 3: Run analysis pipeline
    print('[3/4] Running detection pipeline (1,000 bootstrap iterations)...')
    t0 = time.time()
    result = run_analysis(db_path)
    elapsed = time.time() - t0
    tc = result['tier_counts']
    print(f'      Scored {result["n_scored"]} contracts in {elapsed:.1f}s')
    print(f'      RED: {tc.get("RED", 0)} | YELLOW: {tc.get("YELLOW", 0)} | GREEN: {tc.get("GREEN", 0)} | GRAY: {tc.get("GRAY", 0)}')

    # Step 4: Generate sample reports
    print('[4/4] Generating sample detection reports...')
    reports = generate_sample_reports(db_path, out_dir, result['run_id'])
    print(f'      {len(reports)} reports written to {os.path.join(out_dir, "sample_reports")}/')

    # Print summary
    print_summary(contracts, result, reports, db_path)


if __name__ == '__main__':
    main()
