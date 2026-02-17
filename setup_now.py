import sqlite3, json, hashlib, sys

def hash_it(d):
    if isinstance(d, str):
        try: d = json.loads(d)
        except: return hashlib.sha256(d.encode()).hexdigest()
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',',':')).encode()).hexdigest()

conn = sqlite3.connect('data/sunlight.db')
c = conn.cursor()

# Migration
try:
    c.execute("SELECT 1 FROM analysis_runs LIMIT 1")
    print("Already migrated")
except:
    c.executescript("""
    CREATE TABLE analysis_runs (run_id TEXT PRIMARY KEY, started_at TEXT, completed_at TEXT, status TEXT, model_version TEXT, config_json TEXT, config_hash TEXT, run_seed INTEGER, environment_json TEXT, code_commit_hash TEXT, dataset_hash TEXT, contracts_analyzed INTEGER, fdr_n_tests INTEGER, fdr_n_significant INTEGER, fdr_alpha REAL);
    CREATE TABLE contract_scores (score_id TEXT PRIMARY KEY, contract_id TEXT, run_id TEXT, raw_data_hash TEXT, fraud_tier TEXT, confidence_score INTEGER, markup_pct REAL, bayesian_posterior REAL, raw_pvalue REAL, fdr_adjusted_pvalue REAL, survives_fdr BOOLEAN, triage_priority INTEGER, analyzed_at TEXT, UNIQUE(contract_id, run_id));
    CREATE TABLE audit_log (log_id TEXT PRIMARY KEY, sequence_number INTEGER UNIQUE, timestamp TEXT, action_type TEXT, entity_id TEXT, previous_log_hash TEXT, current_log_hash TEXT);
    """)
    conn.commit()
    print("Migration done")

# Add hash column
try:
    c.execute("ALTER TABLE contracts ADD COLUMN raw_data_hash TEXT")
    conn.commit()
except: pass

# Backfill hashes
c.execute("SELECT contract_id, raw_data FROM contracts WHERE raw_data_hash IS NULL OR raw_data_hash = ''")
rows = c.fetchall()
print(f"Hashing {len(rows)} contracts...")
c.executemany("UPDATE contracts SET raw_data_hash = ? WHERE contract_id = ?", [(hash_it(r[1]), r[0]) for r in rows])
conn.commit()
print(f"Done! All contracts hashed.")
conn.close()
