# SUNLIGHT PostgreSQL Migration Plan

**Date:** 2026-02-17
**Status:** PREPARED — Not executed
**Target:** PostgreSQL 16+

---

## 1. Current State (SQLite)

| Table | Rows | Purpose | Migrate? |
|---|---|---|---|
| `contracts` | 42,593 | Primary scoring table | YES |
| `contracts_clean` | 337,021 | Extended dataset (independent source) | YES |
| `contract_scores` | 56,556 | Scores from completed runs | YES |
| `analysis_runs` | 10 | Pipeline run metadata | YES |
| `audit_log` | 16 | Cryptographic hash chain | YES |
| `political_donations` | 4 | Vendor donation data | YES |
| `api_keys` | 0+ | API authentication | YES |
| `api_usage` | 0+ | Request logging | YES |
| `analysis_results` | 0 | **EMPTY — superseded** | NO (drop) |
| `contract_amendments` | 0 | **EMPTY — never populated** | NO (drop) |

---

## 2. Schema Changes for Production

### 2.1 Type improvements
- `TEXT` dates → `TIMESTAMPTZ` (proper timezone handling)
- `REAL` amounts → `NUMERIC(18,2)` (exact decimal for financial data)
- `TEXT` hashes → `CHAR(64)` for SHA-256, `CHAR(16)` for short hashes
- `TEXT` JSON fields → `JSONB` (indexable, queryable)
- `INTEGER` booleans → `BOOLEAN`
- `TEXT` enums → PostgreSQL `ENUM` types

### 2.2 Schema fixes from audit
- Drop dead columns: `contracts.location`, `contracts.raw_data`, `contract_scores.raw_data_hash`
- Drop redundant `contract_scores.tier` (keep `fraud_tier`)
- Drop redundant audit_log columns (`previous_hash`/`entry_hash` — keep `previous_log_hash`/`current_log_hash`)
- Drop empty tables: `analysis_results`, `contract_amendments`
- Add proper foreign key constraints
- Add `NOT NULL` constraints where appropriate

### 2.3 New features
- `ENUM` types for `fraud_tier`, `run_status`
- Partitioning `contract_scores` by `run_id` for large-scale analysis
- `api_usage` partitioned by month (high-volume table)
- Full-text search on `contracts.description`
- Row-level security for multi-tenant access

---

## 3. Migration Scripts

| File | Purpose |
|---|---|
| `001_schema.sql` | Create all tables, types, indexes, constraints |
| `002_data_migration.py` | ETL from SQLite → PostgreSQL with validation |
| `003_verify.sql` | Post-migration verification queries |

---

## 4. Execution Plan

1. **Pre-migration:** Back up SQLite database
2. **Run `001_schema.sql`** on target PostgreSQL instance
3. **Run `002_data_migration.py`** to transfer and transform data
4. **Run `003_verify.sql`** to validate counts, constraints, hash chain
5. **Update application:** Set `DATABASE_URL` env var, swap SQLite driver for asyncpg/psycopg
6. **Smoke test:** Run API test suite against PostgreSQL backend
7. **Cutover:** Point production to PostgreSQL

---

## 5. Risk Assessment

| Risk | Mitigation |
|---|---|
| "None" strings in `contracts_clean` | Migration script converts to NULL |
| `num_offers = 0` meaning "unknown" | Migration script converts to NULL |
| Audit hash chain breakage | Verify chain integrity before AND after migration |
| FDR recomputation needed | Not needed — stored scores are deterministic |
| Timezone inconsistencies | Migration normalizes all timestamps to UTC |
| Large `contracts_clean` table (337K) | Batch insert with progress tracking |
