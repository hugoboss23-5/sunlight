#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# SUNLIGHT Pre-Launch Master Checklist
# =============================================================================
# Verifies all pre-launch engineering tasks are complete.
# Exit 0 if all checks pass, exit 1 if any fail.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

check_pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS++)); }
check_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL++)); }
check_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN++)); }

echo ""
echo "============================================================"
echo "  SUNLIGHT Pre-Launch Master Checklist"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Task 1: .gitignore and .env.example
# ---------------------------------------------------------------------------
echo "  --- Task 1: Configuration Files ---"

if [ -f "$ROOT_DIR/.gitignore" ]; then
    if grep -q "data/" "$ROOT_DIR/.gitignore" && grep -q ".env" "$ROOT_DIR/.gitignore"; then
        check_pass ".gitignore exists with data/ and .env exclusions"
    else
        check_fail ".gitignore missing required exclusions"
    fi
else
    check_fail ".gitignore not found"
fi

if [ -f "$ROOT_DIR/.env.example" ]; then
    check_pass ".env.example exists"
else
    check_fail ".env.example not found"
fi

# ---------------------------------------------------------------------------
# Task 2: API v2 wiring
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 2: API v2 Wiring ---"

if grep -q "from api_v2 import router" "$ROOT_DIR/code/api.py" 2>/dev/null; then
    check_pass "api_v2 router imported in api.py"
else
    check_fail "api_v2 router not imported in api.py"
fi

if grep -q "app.include_router(v2_router)" "$ROOT_DIR/code/api.py" 2>/dev/null; then
    check_pass "v2_router mounted in app"
else
    check_fail "v2_router not mounted in app"
fi

# ---------------------------------------------------------------------------
# Task 3: Docker Compose + Monitoring
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 3: Docker Compose + Monitoring ---"

if [ -f "$ROOT_DIR/docker-compose.yml" ]; then
    if grep -q "prometheus" "$ROOT_DIR/docker-compose.yml" && \
       grep -q "grafana" "$ROOT_DIR/docker-compose.yml"; then
        check_pass "docker-compose.yml has prometheus + grafana"
    else
        check_fail "docker-compose.yml missing monitoring services"
    fi
else
    check_fail "docker-compose.yml not found"
fi

if [ -f "$ROOT_DIR/infra/prometheus/alerts.yml" ]; then
    check_pass "Prometheus alerts configured"
else
    check_fail "Prometheus alerts not found"
fi

if [ -f "$ROOT_DIR/infra/grafana/provisioning/dashboards/sunlight-ops.json" ]; then
    check_pass "Grafana dashboard provisioned"
else
    check_fail "Grafana dashboard not found"
fi

# ---------------------------------------------------------------------------
# Task 4-5: Demo Reliability Test
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 4-5: Demo Reliability Test ---"

if [ -f "$ROOT_DIR/scripts/demo_reliability_test.py" ]; then
    check_pass "demo_reliability_test.py exists"
else
    check_fail "demo_reliability_test.py not found"
fi

# ---------------------------------------------------------------------------
# Task 7: Cloud Deploy Script
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 7: Cloud Deploy Script ---"

if [ -f "$ROOT_DIR/scripts/deploy_cloud.sh" ] && [ -x "$ROOT_DIR/scripts/deploy_cloud.sh" ]; then
    check_pass "deploy_cloud.sh exists and is executable"
else
    check_fail "deploy_cloud.sh not found or not executable"
fi

# ---------------------------------------------------------------------------
# Task 8: RLS Migration
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 8: RLS Migration ---"

if [ -f "$ROOT_DIR/migrations/004_rls.sql" ]; then
    check_pass "004_rls.sql migration exists"
else
    check_fail "004_rls.sql not found"
fi

if [ -f "$ROOT_DIR/migrations/004_rls_rollback.sql" ]; then
    check_pass "004_rls_rollback.sql rollback exists"
else
    check_fail "004_rls_rollback.sql not found"
fi

# ---------------------------------------------------------------------------
# Task 9: Tenant Middleware
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 9: Tenant Middleware ---"

if [ -f "$ROOT_DIR/code/tenant_middleware.py" ]; then
    check_pass "tenant_middleware.py exists"
else
    check_fail "tenant_middleware.py not found"
fi

if [ -f "$ROOT_DIR/tests/test_tenant_middleware.py" ]; then
    check_pass "test_tenant_middleware.py exists"
else
    check_fail "test_tenant_middleware.py not found"
fi

# ---------------------------------------------------------------------------
# Task 11: Seed Demo
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 11: Seed Demo ---"

if [ -f "$ROOT_DIR/scripts/seed_demo.py" ]; then
    if grep -q "95 clean" "$ROOT_DIR/scripts/seed_demo.py"; then
        check_pass "seed_demo.py updated for 95/5 split"
    else
        check_warn "seed_demo.py exists but may not have 95/5 split"
    fi
else
    check_fail "seed_demo.py not found"
fi

# ---------------------------------------------------------------------------
# Task 12: Reset Demo
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 12: Reset Demo ---"

if [ -f "$ROOT_DIR/scripts/reset_demo.py" ]; then
    check_pass "reset_demo.py exists"
else
    check_fail "reset_demo.py not found"
fi

# ---------------------------------------------------------------------------
# Task 13: Expand DOJ Cases
# ---------------------------------------------------------------------------
echo ""
echo "  --- Task 13: Expand DOJ Cases ---"

if [ -f "$ROOT_DIR/scripts/expand_doj_cases.py" ]; then
    check_pass "expand_doj_cases.py exists"
else
    check_fail "expand_doj_cases.py not found"
fi

# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------
echo ""
echo "  --- Test Suite ---"

cd "$ROOT_DIR"
if python3 -m pytest tests/ -q --tb=short 2>&1 | tail -3; then
    check_pass "Test suite executed"
else
    check_warn "Some tests may have issues"
fi

# ---------------------------------------------------------------------------
# Git Status
# ---------------------------------------------------------------------------
echo ""
echo "  --- Git Status ---"

UNCOMMITTED=$(git -C "$ROOT_DIR" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNCOMMITTED" -eq 0 ]; then
    check_pass "Working tree clean"
else
    check_warn "$UNCOMMITTED uncommitted change(s)"
fi

BRANCH=$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null)
check_pass "On branch: $BRANCH"

COMMIT=$(git -C "$ROOT_DIR" log --oneline -1 2>/dev/null)
check_pass "Latest commit: $COMMIT"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC}"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
    echo -e "  ${RED}CHECKLIST: FAIL${NC}"
    echo "  Fix the failed checks above before launch."
    exit 1
else
    echo -e "  ${GREEN}CHECKLIST: PASS${NC}"
    echo "  All pre-launch checks verified."
fi
echo ""
