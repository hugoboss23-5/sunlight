# SUNLIGHT PostgreSQL Migration Results

**Date:** 2026-02-18
**Source:** SQLite (data/sunlight.db)
**Target:** PostgreSQL 16.x (local)
**Duration:** 46.3 seconds

---

## Migration Summary

| Table | Rows | Status |
|---|---|---|
| contracts | 42,593 | OK |
| contracts_clean | 337,021 | OK |
| analysis_runs | 10 | OK |
| contract_scores | 56,556 | OK |
| audit_log | 16 | OK |
| political_donations | 4 | OK |
| api_keys | 0 | OK |
| **TOTAL** | **436,200** | **ALL MATCH** |

---

## Data Cleanup Applied

| Fix | Count |
|---|---|
| "None" strings → NULL | 17,684 |
| Zero offers → NULL | 128,789 |

---

## Verification Results (11 Queries)

| # | Check | Result |
|---|---|---|
| 1 | Row counts match | PASS |
| 2 | No "None" strings in contracts_clean | PASS (0) |
| 3 | No zero offers in contracts_clean | PASS (0) |
| 4 | Enum types enforced (fraud_tier, run_status) | PASS |
| 5 | Foreign key integrity (no orphan scores) | PASS (0) |
| 6 | Audit hash chain unbroken | PASS (0 breaks) |
| 7 | No stale RUNNING runs | PASS (0) |
| 8 | Financial precision (no float artifacts) | PASS (0) |
| 9 | JSONB fields valid | PASS (0 invalid) |
| 10 | All 50 indexes present | PASS |
| 11 | Summary statistics cross-checked | PASS |

---

## Tier Distribution (PostgreSQL)

| Tier | Count | Pct |
|---|---|---|
| GREEN | 29,917 | 52.9% |
| YELLOW | 21,192 | 37.5% |
| RED | 5,426 | 9.6% |
| GRAY | 21 | 0.0% |

**FDR Survival:** 26,963 survive / 29,593 don't

---

## Fallback

SQLite database retained at `data/sunlight.db` as fallback. Application code continues to use SQLite for API operations. PostgreSQL is ready for production cutover.
