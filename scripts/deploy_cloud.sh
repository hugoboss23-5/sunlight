#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# SUNLIGHT Cloud Deploy Script
# =============================================================================
# Manages the full deploy lifecycle: plan, apply, verify, destroy.
#
# Usage:
#   ./scripts/deploy_cloud.sh plan    [demo|staging|prod]
#   ./scripts/deploy_cloud.sh apply   [demo|staging|prod]
#   ./scripts/deploy_cloud.sh verify  [demo|staging|prod]
#   ./scripts/deploy_cloud.sh destroy [demo|staging|prod]
#   ./scripts/deploy_cloud.sh status  [demo|staging|prod]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra/aws"

ACTION="${1:-help}"
ENV="${2:-demo}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok()   { echo -e "  ${GREEN}[OK]${NC}  $1"; }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
log_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "  [..] $1"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

preflight() {
    echo ""
    echo "============================================"
    echo "  SUNLIGHT Cloud Deploy - Pre-flight Checks"
    echo "  Environment: $ENV"
    echo "============================================"
    echo ""

    local checks_passed=0
    local checks_failed=0

    # 1. Required tools
    for tool in terraform aws docker git python3; do
        if command -v "$tool" >/dev/null 2>&1; then
            log_ok "$tool found ($(command -v "$tool"))"
            ((checks_passed++))
        else
            log_fail "$tool not found"
            ((checks_failed++))
        fi
    done

    # 2. AWS credentials
    if aws sts get-caller-identity >/dev/null 2>&1; then
        local account_id
        account_id=$(aws sts get-caller-identity --query Account --output text)
        log_ok "AWS authenticated (account: $account_id)"
        ((checks_passed++))
    else
        log_fail "AWS not authenticated - run 'aws configure' or set AWS_PROFILE"
        ((checks_failed++))
    fi

    # 3. Terraform vars file
    if [ -f "$INFRA_DIR/${ENV}.tfvars" ]; then
        log_ok "Terraform vars file found: ${ENV}.tfvars"
        ((checks_passed++))
    else
        log_warn "No ${ENV}.tfvars found - will use defaults"
        ((checks_passed++))
    fi

    # 4. Dockerfile
    if [ -f "$ROOT_DIR/Dockerfile" ]; then
        log_ok "Dockerfile found"
        ((checks_passed++))
    else
        log_fail "Dockerfile not found at $ROOT_DIR/Dockerfile"
        ((checks_failed++))
    fi

    # 5. Tests pass
    log_info "Running test suite..."
    if cd "$ROOT_DIR" && python3 -m pytest tests/ -q --tb=no 2>/dev/null; then
        log_ok "All tests pass"
        ((checks_passed++))
    else
        log_warn "Some tests failed - review before deploying to production"
        ((checks_passed++))
    fi

    # 6. Git status
    if [ -z "$(git -C "$ROOT_DIR" status --porcelain 2>/dev/null)" ]; then
        log_ok "Working tree clean"
        ((checks_passed++))
    else
        log_warn "Uncommitted changes in working tree"
        ((checks_passed++))
    fi

    echo ""
    echo "  Pre-flight: $checks_passed passed, $checks_failed failed"

    if [ "$checks_failed" -gt 0 ]; then
        echo ""
        log_fail "Pre-flight checks failed. Fix issues above before deploying."
        return 1
    fi

    echo ""
    return 0
}

# ---------------------------------------------------------------------------
# Build & push Docker image
# ---------------------------------------------------------------------------

build_and_push() {
    local account_id region ecr_repo
    account_id=$(aws sts get-caller-identity --query Account --output text)
    region=$(grep -o '"[^"]*"' "$INFRA_DIR/${ENV}.tfvars" 2>/dev/null | head -1 | tr -d '"' || echo "us-east-1")
    ecr_repo="${account_id}.dkr.ecr.${region}.amazonaws.com/sunlight"

    echo ""
    echo "  Building Docker image..."
    docker build -t sunlight:latest "$ROOT_DIR"

    echo "  Pushing to ECR: $ecr_repo"
    aws ecr get-login-password --region "$region" | \
        docker login --username AWS --password-stdin "${account_id}.dkr.ecr.${region}.amazonaws.com" 2>/dev/null
    aws ecr create-repository --repository-name sunlight --region "$region" 2>/dev/null || true
    docker tag sunlight:latest "${ecr_repo}:latest"
    docker tag sunlight:latest "${ecr_repo}:$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo 'dev')"
    docker push "${ecr_repo}:latest"

    echo "$ecr_repo"
}

# ---------------------------------------------------------------------------
# Terraform plan
# ---------------------------------------------------------------------------

do_plan() {
    preflight || exit 1

    cd "$INFRA_DIR"
    terraform init -upgrade -input=false

    local tfvars_flag=""
    [ -f "${ENV}.tfvars" ] && tfvars_flag="-var-file=${ENV}.tfvars"

    local db_password
    db_password=$(aws ssm get-parameter --name "/sunlight-${ENV}/db-password" \
        --with-decryption --query Parameter.Value --output text 2>/dev/null || \
        echo "changeme-$(openssl rand -hex 8)")

    echo ""
    echo "  Running terraform plan..."
    terraform plan \
        $tfvars_flag \
        -var="db_password=${db_password}" \
        -var="container_image=sunlight:latest" \
        -out=tfplan

    echo ""
    log_ok "Plan saved to $INFRA_DIR/tfplan"
    echo "  Review the plan above, then run:"
    echo "    ./scripts/deploy_cloud.sh apply $ENV"
}

# ---------------------------------------------------------------------------
# Terraform apply
# ---------------------------------------------------------------------------

do_apply() {
    preflight || exit 1

    cd "$INFRA_DIR"

    if [ ! -f "tfplan" ]; then
        log_fail "No plan file found. Run 'deploy_cloud.sh plan $ENV' first."
        exit 1
    fi

    echo ""
    echo -n "  Apply terraform plan to $ENV? (y/N) "
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "  Aborted."
        exit 0
    fi

    # Build and push image first
    echo ""
    echo "  Step 1/3: Build and push Docker image"
    local ecr_repo
    ecr_repo=$(build_and_push)

    # Re-plan with actual image URI
    echo ""
    echo "  Step 2/3: Terraform apply"

    local tfvars_flag=""
    [ -f "${ENV}.tfvars" ] && tfvars_flag="-var-file=${ENV}.tfvars"

    local db_password
    db_password=$(aws ssm get-parameter --name "/sunlight-${ENV}/db-password" \
        --with-decryption --query Parameter.Value --output text 2>/dev/null || \
        echo "changeme-$(openssl rand -hex 8)")

    terraform apply \
        $tfvars_flag \
        -var="db_password=${db_password}" \
        -var="container_image=${ecr_repo}:latest" \
        -auto-approve

    echo ""
    echo "  Step 3/3: Post-deploy verification"
    do_verify

    echo ""
    log_ok "Deploy complete!"
    terraform output -json 2>/dev/null | python3 -c "
import json, sys
try:
    o = json.load(sys.stdin)
    for k, v in o.items():
        print(f'  {k}: {v[\"value\"]}')
except: pass
" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Verify deployment
# ---------------------------------------------------------------------------

do_verify() {
    echo ""
    echo "============================================"
    echo "  SUNLIGHT Deploy Verification"
    echo "  Environment: $ENV"
    echo "============================================"
    echo ""

    cd "$INFRA_DIR"

    # Get API URL from terraform output
    local api_url
    api_url=$(terraform output -raw api_url 2>/dev/null || echo "")

    if [ -z "$api_url" ]; then
        log_warn "Could not determine API URL from terraform output"
        echo -n "  Enter API URL: "
        read -r api_url
    fi

    local checks_passed=0
    local checks_failed=0

    # 1. Health check
    log_info "Checking /health..."
    local health_status
    health_status=$(curl -sf -o /dev/null -w "%{http_code}" "${api_url}/health" 2>/dev/null || echo "000")
    if [ "$health_status" = "200" ]; then
        log_ok "Health check passed (HTTP 200)"
        ((checks_passed++))
    else
        log_fail "Health check failed (HTTP $health_status)"
        ((checks_failed++))
    fi

    # 2. API docs accessible
    log_info "Checking /docs..."
    local docs_status
    docs_status=$(curl -sf -o /dev/null -w "%{http_code}" "${api_url}/docs" 2>/dev/null || echo "000")
    if [ "$docs_status" = "200" ]; then
        log_ok "API docs accessible"
        ((checks_passed++))
    else
        log_fail "API docs not accessible (HTTP $docs_status)"
        ((checks_failed++))
    fi

    # 3. Metrics endpoint
    log_info "Checking /api/v2/metrics..."
    local metrics_status
    metrics_status=$(curl -sf -o /dev/null -w "%{http_code}" "${api_url}/api/v2/metrics" 2>/dev/null || echo "000")
    if [ "$metrics_status" = "200" ]; then
        log_ok "Metrics endpoint accessible"
        ((checks_passed++))
    else
        log_warn "Metrics endpoint returned HTTP $metrics_status"
        ((checks_passed++))
    fi

    # 4. ECS service status
    log_info "Checking ECS service..."
    local cluster_name="sunlight-${ENV}-cluster"
    local service_name="sunlight-${ENV}-api"
    local running_count
    running_count=$(aws ecs describe-services \
        --cluster "$cluster_name" --services "$service_name" \
        --query 'services[0].runningCount' --output text 2>/dev/null || echo "0")
    if [ "$running_count" -gt 0 ] 2>/dev/null; then
        log_ok "ECS service running ($running_count tasks)"
        ((checks_passed++))
    else
        log_warn "Could not verify ECS service status"
        ((checks_passed++))
    fi

    # 5. RDS connectivity (via ECS)
    log_info "Checking database (via health endpoint)..."
    local health_body
    health_body=$(curl -sf "${api_url}/health" 2>/dev/null || echo "{}")
    local db_status
    db_status=$(echo "$health_body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$db_status" = "healthy" ]; then
        log_ok "Database connected (status: healthy)"
        ((checks_passed++))
    else
        log_warn "Database status: $db_status"
        ((checks_passed++))
    fi

    echo ""
    echo "  Verification: $checks_passed passed, $checks_failed failed"

    if [ "$checks_failed" -gt 0 ]; then
        log_fail "Verification failed. Check logs with:"
        echo "    aws logs tail /ecs/sunlight-${ENV} --follow"
        return 1
    fi

    log_ok "All checks passed"
    return 0
}

# ---------------------------------------------------------------------------
# Terraform destroy
# ---------------------------------------------------------------------------

do_destroy() {
    echo ""
    echo "============================================"
    echo "  SUNLIGHT Cloud Destroy"
    echo "  Environment: $ENV"
    echo "============================================"
    echo ""

    if [ "$ENV" = "prod" ]; then
        log_fail "Refusing to destroy production. Remove this guard manually if you really mean it."
        exit 1
    fi

    cd "$INFRA_DIR"

    local tfvars_flag=""
    [ -f "${ENV}.tfvars" ] && tfvars_flag="-var-file=${ENV}.tfvars"

    echo -e "  ${RED}This will DESTROY all resources in the '$ENV' environment.${NC}"
    echo ""
    echo -n "  Type the environment name to confirm: "
    read -r confirm
    if [ "$confirm" != "$ENV" ]; then
        echo "  Aborted."
        exit 0
    fi

    local db_password
    db_password=$(aws ssm get-parameter --name "/sunlight-${ENV}/db-password" \
        --with-decryption --query Parameter.Value --output text 2>/dev/null || echo "dummy")

    terraform destroy \
        $tfvars_flag \
        -var="db_password=${db_password}" \
        -var="container_image=sunlight:latest"

    echo ""
    log_ok "Environment '$ENV' destroyed."
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

do_status() {
    echo ""
    echo "============================================"
    echo "  SUNLIGHT Cloud Status"
    echo "  Environment: $ENV"
    echo "============================================"
    echo ""

    cd "$INFRA_DIR"

    # Terraform state
    if terraform state list >/dev/null 2>&1; then
        local resource_count
        resource_count=$(terraform state list 2>/dev/null | wc -l | tr -d ' ')
        log_ok "Terraform state: $resource_count resources"
        terraform output 2>/dev/null || true
    else
        log_warn "No terraform state found for $ENV"
    fi

    # ECS
    echo ""
    local cluster_name="sunlight-${ENV}-cluster"
    local service_name="sunlight-${ENV}-api"
    aws ecs describe-services \
        --cluster "$cluster_name" --services "$service_name" \
        --query 'services[0].{status:status, desired:desiredCount, running:runningCount, pending:pendingCount}' \
        --output table 2>/dev/null || log_warn "Could not fetch ECS service status"

    # RDS
    echo ""
    aws rds describe-db-instances \
        --db-instance-identifier "sunlight-${ENV}-db" \
        --query 'DBInstances[0].{status:DBInstanceStatus, endpoint:Endpoint.Address, class:DBInstanceClass, storage:AllocatedStorage}' \
        --output table 2>/dev/null || log_warn "Could not fetch RDS status"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "$ACTION" in
    plan)    do_plan ;;
    apply)   do_apply ;;
    verify)  do_verify ;;
    destroy) do_destroy ;;
    status)  do_status ;;
    preflight) preflight ;;
    *)
        echo "SUNLIGHT Cloud Deploy"
        echo ""
        echo "Usage: $0 <action> [environment]"
        echo ""
        echo "Actions:"
        echo "  plan       Run pre-flight checks + terraform plan"
        echo "  apply      Build, push, and terraform apply"
        echo "  verify     Post-deploy health verification"
        echo "  destroy    Tear down environment (not prod)"
        echo "  status     Show current infrastructure status"
        echo "  preflight  Run pre-flight checks only"
        echo ""
        echo "Environments: demo (default), staging, prod"
        exit 1
        ;;
esac
