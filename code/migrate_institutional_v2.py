import sqlite3, os, sys

def migrate(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    print("SUNLIGHT Schema Migration v2")
    print("=" * 60)

    cols = {
        'analysis_runs': [
            ("n_contracts","INTEGER"),("n_scored","INTEGER"),("n_errors","INTEGER"),
            ("summary_json","TEXT"),("run_seed","INTEGER"),("dataset_hash","TEXT"),
            ("config_hash","TEXT"),("config_json","TEXT"),("code_commit_hash","TEXT"),
            ("environment_json","TEXT"),
        ],
        'contract_scores': [
            ("tier","TEXT"),("markup_ci_lower","REAL"),("markup_ci_upper","REAL"),
            ("raw_zscore","REAL"),("log_zscore","REAL"),("bootstrap_percentile","REAL"),
            ("percentile_ci_lower","REAL"),("percentile_ci_upper","REAL"),
            ("bayesian_prior","REAL"),("bayesian_likelihood_ratio","REAL"),
            ("comparable_count","INTEGER"),("insufficient_comparables","BOOLEAN"),
            ("selection_params_json","TEXT"),("scored_at","TEXT"),
            ("triage_priority","INTEGER"),("markup_pct","REAL"),
            ("bayesian_posterior","REAL"),("raw_pvalue","REAL"),
            ("fdr_adjusted_pvalue","REAL"),("survives_fdr","BOOLEAN"),("run_id","TEXT"),
        ],
        'audit_log': [
            ("action","TEXT"),("run_id","TEXT"),("details","TEXT"),
            ("previous_hash","TEXT"),("entry_hash","TEXT"),
        ],
    }

    for table, columns in cols.items():
        print(f"\n[{table}]")
        for col_name, col_type in columns:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                print(f"  + Added: {col_name}")
            except Exception as e:
                if "duplicate" in str(e).lower():
                    print(f"  ✓ Exists: {col_name}")
                else:
                    print(f"  ⚠ {col_name}: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Migration complete.")

if __name__ == "__main__":
    db = 'data/sunlight.db' if os.path.exists('data/sunlight.db') else '../data/sunlight.db'
    migrate(db)
