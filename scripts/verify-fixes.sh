#!/usr/bin/env bash
#
# verify-fixes.sh <group>
#
# 按修复组别运行对应验证层级。
# 返回 0 = 通过，非 0 = 失败。

set -euo pipefail

GROUP="${1:-}"
if [[ -z "$GROUP" ]]; then
  echo "Usage: verify-fixes.sh <group>"
  echo "  group: 1-5"
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
info()  { echo -e "${YELLOW}[INFO]${NC} $*"; }

# ── L1: TypeScript 类型检查 ──────────────────────────────────────────
run_l1() {
  info "L1: TypeScript type check..."
  cd "$PROJECT_ROOT/frontend"
  if npm run typecheck 2>&1; then
    pass "TypeScript type check"
    return 0
  else
    fail "TypeScript type check"
    return 1
  fi
}

# ── L2: 后端单元测试（无外部依赖） ───────────────────────────────────
run_l2() {
  info "L2: Backend unit tests (no infra)..."
  cd "$PROJECT_ROOT/backend"
  if pytest tests/test_schemas.py tests/test_services.py tests/test_auth.py tests/test_keycloak_auth.py tests/test_review_api.py -v 2>&1; then
    pass "Backend unit tests"
    return 0
  else
    fail "Backend unit tests"
    return 1
  fi
}

# ── L3: 后端完整测试（需要 Redis / PostgreSQL） ──────────────────────
run_l3() {
  info "L3: Backend full test suite..."
  cd "$PROJECT_ROOT/backend"
  if pytest -v 2>&1; then
    pass "Backend full test suite"
    return 0
  else
    fail "Backend full test suite"
    return 1
  fi
}

# ── L4: Python 导入检查 ──────────────────────────────────────────────
run_l4() {
  info "L4: Python import check..."
  cd "$PROJECT_ROOT/backend"
  if python -c "from app.main import app; print('OK')" 2>&1; then
    pass "Python import check"
    return 0
  else
    fail "Python import check"
    return 1
  fi
}

# ── 按组别执行 ───────────────────────────────────────────────────────
echo "========================================"
echo "  Verify Group $GROUP"
echo "========================================"

EXIT_CODE=0

case "$GROUP" in
  1)
    # 第 1 组：前端数据安全 → L1
    run_l1 || EXIT_CODE=$?
    ;;
  2)
    # 第 2 组：认证安全（后端 + 前端 + Docker） → L4, L2, L1
    run_l4 || EXIT_CODE=$?
    run_l2 || EXIT_CODE=$?
    run_l1 || EXIT_CODE=$?
    ;;
  3)
    # 第 3 组：可靠性（后端 + 前端） → L2, L1
    run_l2 || EXIT_CODE=$?
    run_l1 || EXIT_CODE=$?
    ;;
  4)
    # 第 4 组：基础设施 → L4, L2
    run_l4 || EXIT_CODE=$?
    run_l2 || EXIT_CODE=$?
    ;;
  5)
    # 第 5 组：防御性改进 → L1, L2
    run_l1 || EXIT_CODE=$?
    run_l2 || EXIT_CODE=$?
    ;;
  *)
    echo "Unknown group: $GROUP (expected 1-5)"
    exit 1
    ;;
esac

echo "========================================"
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Group $GROUP verification PASSED"
else
  fail "Group $GROUP verification FAILED"
fi
exit $EXIT_CODE
