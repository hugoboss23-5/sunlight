"""
Bootstrap Sensitivity Report: B=1000 vs B=500
Compares top-K overlap, tier flips, CI width shifts.
"""
import sqlite3, numpy as np, json, sys, os

def report(db_path, run_id_b1000, run_id_b500):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Load both runs
    def load(rid):
        c.execute("""SELECT contract_id, tier, triage_priority, raw_pvalue,
            fdr_adjusted_pvalue, markup_pct, markup_ci_lower, markup_ci_upper,
            bayesian_posterior, comparable_count
            FROM contract_scores WHERE run_id=? ORDER BY triage_priority, contract_id""", (rid,))
        return {r[0]: {'tier':r[1],'pri':r[2],'p':r[3],'q':r[4],'markup':r[5],
            'ci_lo':r[6],'ci_hi':r[7],'post':r[8],'n_comp':r[9]} for r in c.fetchall()}

    a = load(run_id_b1000)
    b = load(run_id_b500)
    conn.close()

    shared = set(a.keys()) & set(b.keys())
    print(f"Contracts compared: {len(shared)}")

    # Tier flips
    flips = [(cid, a[cid]['tier'], b[cid]['tier']) for cid in shared if a[cid]['tier'] != b[cid]['tier']]
    print(f"\nTIER FLIPS: {len(flips)} / {len(shared)} ({len(flips)/len(shared)*100:.1f}%)")
    if flips:
        for cid, t1, t2 in flips[:20]:
            print(f"  {cid}: {t1} -> {t2}")

    # Top-K overlap
    for k in [20, 50, 100]:
        top_a = sorted(shared, key=lambda x: a[x]['pri'])[:k]
        top_b = sorted(shared, key=lambda x: b[x]['pri'])[:k]
        overlap = len(set(top_a) & set(top_b))
        print(f"\nStability@{k}: {overlap}/{k} overlap ({overlap/k*100:.0f}%)")

    # CI width comparison
    widths_a = [a[c]['ci_hi'] - a[c]['ci_lo'] for c in shared if a[c]['ci_hi'] is not None and a[c]['ci_lo'] is not None]
    widths_b = [b[c]['ci_hi'] - b[c]['ci_lo'] for c in shared if b[c]['ci_hi'] is not None and b[c]['ci_lo'] is not None]
    print(f"\nCI WIDTH (B=1000): median={np.median(widths_a):.1f}%, p90={np.percentile(widths_a,90):.1f}%, p95={np.percentile(widths_a,95):.1f}%")
    print(f"CI WIDTH (B=500):  median={np.median(widths_b):.1f}%, p90={np.percentile(widths_b,90):.1f}%, p95={np.percentile(widths_b,95):.1f}%")

    # P-value correlation
    pvals_a = [a[c]['p'] for c in shared if a[c]['p'] is not None]
    pvals_b = [b[c]['p'] for c in shared if b[c]['p'] is not None]
    corr = np.corrcoef(pvals_a, pvals_b)[0,1]
    print(f"\nP-value correlation: {corr:.6f}")

    # Top-50 tier flips
    top50 = sorted(shared, key=lambda x: a[x]['pri'])[:50]
    top50_flips = sum(1 for c in top50 if a[c]['tier'] != b[c]['tier'])
    print(f"\nTop-50 tier flips: {top50_flips}/50 ({top50_flips/50*100:.1f}%)")
    print(f"\nSTOP-LINE CHECK: {'FAIL - >5% tier flips in top 50' if top50_flips > 2 else 'PASS - top 50 stable'}")

if __name__ == "__main__":
    db = 'data/sunlight.db' if os.path.exists('data/sunlight.db') else '../data/sunlight.db'
    if len(sys.argv) >= 3:
        report(db, sys.argv[1], sys.argv[2])
    else:
        print("Usage: python bootstrap_sensitivity.py <run_id_b1000> <run_id_b500>")
        print("\nAvailable runs:")
        conn = sqlite3.connect(db)
        for r in conn.execute("SELECT run_id, status, n_contracts, config_json FROM analysis_runs ORDER BY started_at").fetchall():
            print(f"  {r[0]}  status={r[1]}  n={r[2]}")
        conn.close()
