# SUNLIGHT Security Audit Report

**Date:** 2026-02-18
**Auditor:** Automated + Manual Review
**Scope:** Dependencies, API endpoints, SQL injection, input validation, CORS, request limits

---

## 1. Dependency Audit (pip-audit)

| Package | Version | Vulnerability | Fix Version | Severity |
|---|---|---|---|---|
| pip | 25.2 | CVE-2025-8869 | 25.3 | Medium |
| pip | 25.2 | CVE-2026-1703 | 26.0 | Medium |

**Status:** pip itself has known CVEs. Not exploitable in production (pip is a build tool, not a runtime dependency). Update recommended: `pip install --upgrade pip`.

**All runtime dependencies (fastapi, uvicorn, numpy, pydantic, httpx, psycopg2-binary) have zero known vulnerabilities.**

---

## 2. SQL Injection Review

### Fixed (This Audit)

| File | Issue | Fix Applied |
|---|---|---|
| `code/ingestion.py:update_job()` | Dynamic column names from `**kwargs` | Added allowlist validation (`_ALLOWED_JOB_COLUMNS`) |

### Safe by Design

All API-facing SQL queries use parameterized placeholders (`?`):
- Contract lookups, inserts, score queries all use `?` parameters
- User input (agency, vendor, amounts) is always bound via parameters, never interpolated
- WHERE clause builders in `api.py` and `dashboard.py` use hardcoded condition strings with `?` placeholders for values

### Non-API Code (Lower Risk)

| File | Pattern | Risk | Status |
|---|---|---|---|
| `dashboard.py:get_system_health()` | `f"SELECT COUNT(*) FROM {table}"` | Low | Table names hardcoded in function |
| `institutional_pipeline.py` | `f"SELECT {col} FROM audit_log"` | Low | Column names hardcoded in loop |
| `data_quality_monitor.py` | Dynamic table/field params | Medium | Not exposed via API |
| `production_scraper.py` | Dynamic `date_column` | Medium | Offline scraper, not API-facing |

**Assessment:** No exploitable SQL injection vectors exist in API-facing code. Internal scripts use f-string patterns with hardcoded values — no user input reaches these paths.

---

## 3. Input Validation (Hardened This Audit)

### Pydantic Model Constraints Added

| Model | Field | Constraint |
|---|---|---|
| `ContractIn` | `contract_id` | max_length=100 |
| `ContractIn` | `award_amount` | le=1e15 (prevent overflow) |
| `ContractIn` | `vendor_name` | max_length=500 |
| `ContractIn` | `agency_name` | max_length=500 |
| `ContractIn` | `description` | max_length=10000 |
| `ContractIn` | `start_date` | max_length=30 |
| `AnalyzeSingleRequest` | All string fields | Same constraints as ContractIn |

### Pre-Existing Validations
- `award_amount > 0` enforced on all amount fields
- `n_bootstrap` bounded: `ge=100, le=50000`
- `fdr_alpha` bounded: `gt=0, lt=1`
- Pagination: `limit` capped at 500, `offset >= 0`

---

## 4. CORS Configuration (Added This Audit)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],  # Configurable via SUNLIGHT_CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
    max_age=3600,
)
```

**Production recommendation:** Set `SUNLIGHT_CORS_ORIGINS` to specific client domains (comma-separated). Default `*` is appropriate for development only.

---

## 5. Request Size Limits (Added This Audit)

- **Maximum request body:** 50 MB (enforced via HTTP middleware)
- Returns HTTP 413 for oversized requests
- Protects against memory exhaustion from large file uploads

---

## 6. Authentication & Authorization

| Feature | Status |
|---|---|
| API key authentication | Implemented (SHA-256 hashed, plaintext never stored) |
| Key rotation | Implemented (`POST /admin/keys/rotate`) |
| Key revocation | Implemented (`DELETE /admin/keys/{id}`) |
| Scope-based access | Implemented (read, analyze, admin) |
| Rate limiting | Implemented (sliding window, per-key) |
| Usage tracking | Implemented (per-request logging) |
| Auth bypass for dev | `SUNLIGHT_AUTH_ENABLED=false` env var |

**No issues found.** Key format: `sk_sunlight_<64 hex chars>`. Only SHA-256 hash stored in database.

---

## 7. Additional Security Measures

| Measure | Status |
|---|---|
| `.env` in `.gitignore` | Yes |
| No hardcoded credentials | Yes (all via environment variables) |
| Database files in `.gitignore` | Yes (`*.db`) |
| HTTPS enforcement | Not yet (requires reverse proxy — nginx/Caddy) |
| Audit trail integrity | SHA-256 hash chain, verified on every health check |
| Deterministic pipeline | SHA-256 seeds prevent manipulation of random processes |

---

## 8. Recommendations

### Immediate (Before Launch)
1. **Upgrade pip:** `pip install --upgrade pip` to resolve CVE-2025-8869 and CVE-2026-1703
2. **Set CORS origins:** Configure `SUNLIGHT_CORS_ORIGINS` for production domains
3. **Enable HTTPS:** Deploy behind nginx/Caddy with TLS certificates
4. **Set strong PostgreSQL password:** Replace default `changeme` in `.env`

### Post-Launch
5. **Add request logging:** Log IP addresses and user agents for security monitoring
6. **Implement key expiration enforcement:** Currently tracked but not auto-enforced
7. **Add WAF rules:** Rate limit by IP in addition to API key
8. **Periodic dependency scans:** Run `pip-audit` in CI pipeline weekly

---

## Summary

| Category | Status |
|---|---|
| Dependencies | 2 CVEs (pip only, non-runtime) |
| SQL Injection | No exploitable vectors |
| Input Validation | Hardened with length/range limits |
| CORS | Configured, env-controlled |
| Request Limits | 50 MB max |
| Authentication | Strong (SHA-256, scopes, rate limits) |
| Overall Risk | **LOW** |
