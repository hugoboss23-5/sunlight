"""
SUNLIGHT SQLite → PostgreSQL Data Migration
=============================================

Transfers all data from SQLite to PostgreSQL with:
- Type conversions (TEXT dates → TIMESTAMPTZ, REAL → NUMERIC)
- Data cleanup ("None" strings → NULL, 0 offers → NULL)
- Batch inserts for performance
- Progress tracking
- Post-migration count verification

Prerequisites:
    pip install psycopg2-binary

Usage:
    python 002_data_migration.py --sqlite ../data/sunlight.db --pg "postgresql://user:pass@host/sunlight"

    DRY RUN (no writes):
    python 002_data_migration.py --sqlite ../data/sunlight.db --pg "..." --dry-run
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone


def get_pg_conn(dsn: str):
    """Get a PostgreSQL connection."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    return psycopg2.connect(dsn)


def migrate_contracts(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate contracts table."""
    print("\n[contracts] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT contract_id, award_amount, vendor_name, agency_name,
               description, start_date, raw_data_hash
        FROM contracts
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    batch = []
    for r in rows:
        cid, amt, vendor, agency, desc, sdate, rhash = r
        # Clean start_date
        sdate = _parse_date(sdate)
        batch.append((cid, amt, vendor, agency, desc or '', sdate, rhash))

    _batch_insert(pg, """
        INSERT INTO contracts (contract_id, award_amount, vendor_name,
            agency_name, description, start_date, raw_data_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (contract_id) DO NOTHING
    """, batch, "contracts")

    pg_conn.commit()
    return len(rows)


def migrate_contracts_clean(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate contracts_clean with data cleanup."""
    print("\n[contracts_clean] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT contract_id, award_amount, vendor_name, agency_name,
               description, start_date, end_date, award_type,
               num_offers, extent_competed
        FROM contracts_clean
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    batch = []
    none_fixed = 0
    zero_offers_fixed = 0

    for r in rows:
        cid, amt, vendor, agency, desc, sdate, edate, atype, noffers, competed = r

        # Fix "None" strings → NULL
        if atype == 'None' or atype == '':
            atype = None
            none_fixed += 1
        if competed == 'None' or competed == '':
            competed = None
            none_fixed += 1
        if desc == 'None':
            desc = None

        # Fix num_offers = 0 → NULL (means unknown, not zero)
        if noffers == 0:
            noffers = None
            zero_offers_fixed += 1

        sdate = _parse_date(sdate)
        edate = _parse_date(edate)

        batch.append((cid, amt, vendor, agency, desc or '', sdate, edate,
                       atype, noffers, competed))

    _batch_insert(pg, """
        INSERT INTO contracts_clean (contract_id, award_amount, vendor_name,
            agency_name, description, start_date, end_date, award_type,
            num_offers, extent_competed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (contract_id) DO NOTHING
    """, batch, "contracts_clean")

    pg_conn.commit()
    print(f"  Fixed {none_fixed} 'None' strings → NULL")
    print(f"  Fixed {zero_offers_fixed} zero offers → NULL")
    return len(rows)


def migrate_analysis_runs(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate analysis_runs."""
    print("\n[analysis_runs] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT run_id, started_at, completed_at, status, run_seed,
               config_json, config_hash, dataset_hash, n_contracts,
               n_scored, n_errors, summary_json, fdr_n_tests,
               fdr_n_significant, fdr_alpha, model_version,
               code_commit_hash, environment_json
        FROM analysis_runs
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    for r in rows:
        (rid, started, completed, status, seed, config, chash, dhash,
         ncon, nscored, nerr, summary, fdrt, fdrs, fdra, mver, cchash, envj) = r

        # Map status
        status = status.upper()
        if status not in ('RUNNING', 'COMPLETED', 'ABORTED', 'FAILED'):
            status = 'ABORTED'

        pg.execute("""
            INSERT INTO analysis_runs (run_id, started_at, completed_at, status,
                run_seed, config_json, config_hash, dataset_hash, n_contracts,
                n_scored, n_errors, summary_json, fdr_n_tests, fdr_n_significant,
                fdr_alpha, model_version, code_commit_hash, environment_json)
            VALUES (%s, %s, %s, %s::run_status, %s, %s::jsonb, %s, %s, %s,
                    %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (run_id) DO NOTHING
        """, (rid, started, completed, status, seed,
              config or '{}', chash, dhash, ncon,
              nscored or 0, nerr or 0, summary or '{}',
              fdrt, fdrs, fdra, mver, cchash, envj or '{}'))

    pg_conn.commit()
    return len(rows)


def migrate_contract_scores(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate contract_scores (dropping dead columns)."""
    print("\n[contract_scores] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT score_id, contract_id, run_id, fraud_tier, triage_priority,
               confidence_score, markup_pct, markup_ci_lower, markup_ci_upper,
               raw_zscore, log_zscore, bootstrap_percentile, percentile_ci_lower,
               percentile_ci_upper, bayesian_prior, bayesian_likelihood_ratio,
               bayesian_posterior, raw_pvalue, fdr_adjusted_pvalue, survives_fdr,
               comparable_count, insufficient_comparables, selection_params_json,
               scored_at
        FROM contract_scores
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    batch = []
    for r in rows:
        (sid, cid, rid, tier, prio, conf, mpct, mcil, mciu,
         rz, lz, bpct, pcil, pciu, bpri, blr, bpos,
         rpv, fapv, sfdr, cc, insuf, spj, sat) = r

        # Normalize tier
        tier = (tier or 'GRAY').upper()
        if tier not in ('RED', 'YELLOW', 'GREEN', 'GRAY'):
            tier = 'GRAY'

        batch.append((
            sid, cid, rid, tier, prio or 9999, conf or 0,
            mpct, mcil, mciu, rz, lz, bpct, pcil, pciu,
            bpri, blr, bpos, rpv, fapv,
            bool(sfdr), cc or 0, bool(insuf),
            spj, sat,
        ))

    _batch_insert(pg, """
        INSERT INTO contract_scores (
            score_id, contract_id, run_id, fraud_tier, triage_priority,
            confidence_score, markup_pct, markup_ci_lower, markup_ci_upper,
            raw_zscore, log_zscore, bootstrap_percentile, percentile_ci_lower,
            percentile_ci_upper, bayesian_prior, bayesian_likelihood_ratio,
            bayesian_posterior, raw_pvalue, fdr_adjusted_pvalue, survives_fdr,
            comparable_count, insufficient_comparables, selection_params_json,
            scored_at)
        VALUES (%s, %s, %s, %s::fraud_tier, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (score_id) DO NOTHING
    """, batch, "contract_scores")

    pg_conn.commit()
    return len(rows)


def migrate_audit_log(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate audit_log (consolidating redundant columns)."""
    print("\n[audit_log] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT log_id, sequence_number, timestamp, action_type,
               entity_id, previous_log_hash, current_log_hash,
               run_id, details
        FROM audit_log ORDER BY sequence_number
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    for r in rows:
        lid, seq, ts, atype, eid, plh, clh, rid, details = r
        pg.execute("""
            INSERT INTO audit_log (log_id, sequence_number, timestamp,
                action_type, entity_id, previous_log_hash, current_log_hash,
                run_id, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (log_id) DO NOTHING
        """, (lid, seq, ts, atype or '', eid, plh, clh, rid,
              details or '{}'))

    pg_conn.commit()
    return len(rows)


def migrate_political_donations(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate political_donations."""
    print("\n[political_donations] Migrating...")
    c = sqlite_conn.cursor()
    c.execute("""
        SELECT vendor_name, recipient_name, amount, date, cycle, source
        FROM political_donations
    """)
    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run:
        print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    for r in rows:
        vendor, recipient, amt, dt, cycle, src = r
        dt = _parse_date(dt) if dt else None
        pg.execute("""
            INSERT INTO political_donations (vendor_name, recipient_name,
                amount, donation_date, cycle, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (vendor_name, recipient_name, cycle) DO NOTHING
        """, (vendor, recipient, amt, dt, cycle, src or 'UNKNOWN'))

    pg_conn.commit()
    return len(rows)


def migrate_api_keys(sqlite_conn, pg_conn, dry_run: bool):
    """Migrate api_keys."""
    print("\n[api_keys] Migrating...")
    c = sqlite_conn.cursor()
    try:
        c.execute("""
            SELECT key_id, key_hash, client_name, created_at, expires_at,
                   revoked_at, is_active, rate_limit, rate_window, scopes, notes
            FROM api_keys
        """)
    except sqlite3.OperationalError:
        print("  Table does not exist in source. Skipping.")
        return 0

    rows = c.fetchall()
    print(f"  Source rows: {len(rows)}")

    if dry_run or not rows:
        if dry_run:
            print("  [DRY RUN] Skipping insert.")
        return len(rows)

    pg = pg_conn.cursor()
    for r in rows:
        (kid, khash, cname, cat, eat, rat, active,
         rlimit, rwindow, scopes, notes) = r
        pg.execute("""
            INSERT INTO api_keys (key_id, key_hash, client_name, created_at,
                expires_at, revoked_at, is_active, rate_limit, rate_window,
                scopes, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (key_id) DO NOTHING
        """, (kid, khash, cname, cat, eat, rat, bool(active),
              rlimit, rwindow, scopes, notes))

    pg_conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(val):
    """Parse various date formats to ISO string or None."""
    if not val or val == 'None' or val == '':
        return None
    # Already ISO format
    if 'T' in str(val) or len(str(val)) == 10:
        return str(val)
    return str(val)


def _batch_insert(cursor, sql, rows, table_name, batch_size=5000):
    """Insert rows in batches with progress."""
    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        try:
            cursor.executemany(sql, batch)
        except Exception:
            # Fall back to individual inserts on batch failure
            for row in batch:
                try:
                    cursor.execute(sql, row)
                except Exception as e:
                    print(f"  WARNING: Skipped row in {table_name}: {e}")
        done = min(i + batch_size, total)
        if total > batch_size:
            print(f"  Progress: {done}/{total} ({done*100//total}%)")


def verify_counts(sqlite_conn, pg_conn):
    """Verify row counts match after migration."""
    print("\n" + "=" * 60)
    print("VERIFICATION: Row Counts")
    print("=" * 60)

    tables = [
        ('contracts', 'contracts'),
        ('contracts_clean', 'contracts_clean'),
        ('analysis_runs', 'analysis_runs'),
        ('contract_scores', 'contract_scores'),
        ('audit_log', 'audit_log'),
        ('political_donations', 'political_donations'),
        ('api_keys', 'api_keys'),
    ]

    all_ok = True
    for sqlite_table, pg_table in tables:
        sc = sqlite_conn.cursor()
        try:
            sc.execute(f"SELECT COUNT(*) FROM {sqlite_table}")
            sqlite_count = sc.fetchone()[0]
        except sqlite3.OperationalError:
            sqlite_count = 0

        pc = pg_conn.cursor()
        pc.execute(f"SELECT COUNT(*) FROM {pg_table}")
        pg_count = pc.fetchone()[0]

        match = "OK" if sqlite_count == pg_count else "MISMATCH"
        if sqlite_count != pg_count:
            all_ok = False
        print(f"  {pg_table:<25} SQLite={sqlite_count:<10} PG={pg_count:<10} {match}")

    print(f"\n  {'ALL COUNTS MATCH' if all_ok else 'SOME COUNTS DIFFER — investigate'}")
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SUNLIGHT SQLite → PostgreSQL Migration")
    parser.add_argument('--sqlite', required=True, help='Path to SQLite database')
    parser.add_argument('--pg', required=True, help='PostgreSQL connection string')
    parser.add_argument('--dry-run', action='store_true', help='Read-only — no writes')
    args = parser.parse_args()

    print("=" * 60)
    print("SUNLIGHT Data Migration: SQLite → PostgreSQL")
    print("=" * 60)
    print(f"  Source: {args.sqlite}")
    print(f"  Target: {args.pg.split('@')[0]}@...")  # Hide credentials
    print(f"  Mode:   {'DRY RUN' if args.dry_run else 'LIVE'}")

    sqlite_conn = sqlite3.connect(args.sqlite)
    pg_conn = get_pg_conn(args.pg)

    t0 = time.time()

    counts = {}
    counts['contracts'] = migrate_contracts(sqlite_conn, pg_conn, args.dry_run)
    counts['contracts_clean'] = migrate_contracts_clean(sqlite_conn, pg_conn, args.dry_run)
    counts['analysis_runs'] = migrate_analysis_runs(sqlite_conn, pg_conn, args.dry_run)
    counts['contract_scores'] = migrate_contract_scores(sqlite_conn, pg_conn, args.dry_run)
    counts['audit_log'] = migrate_audit_log(sqlite_conn, pg_conn, args.dry_run)
    counts['political_donations'] = migrate_political_donations(sqlite_conn, pg_conn, args.dry_run)
    counts['api_keys'] = migrate_api_keys(sqlite_conn, pg_conn, args.dry_run)

    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    total = sum(counts.values())
    for table, count in counts.items():
        print(f"  {table:<25} {count:>10,} rows")
    print(f"  {'TOTAL':<25} {total:>10,} rows")
    print(f"  Elapsed: {elapsed:.1f}s")

    if not args.dry_run:
        verify_counts(sqlite_conn, pg_conn)

    sqlite_conn.close()
    pg_conn.close()

    print(f"\n{'DRY RUN complete — no data written.' if args.dry_run else 'Migration complete.'}")


if __name__ == "__main__":
    main()
