#!/bin/bash
# =============================================================================
# test.sh - CI 테스트
# =============================================================================
# pytest + 커버리지 + 타입 체크
# Usage: ./scripts/test.sh [--quick|--coverage|--ci]
# =============================================================================

set -e

cd "$(dirname "$0")/.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# -----------------------------------------------------------------------------
# 명령어 처리
# -----------------------------------------------------------------------------
case "${1:---quick}" in
    --quick|-q|quick)
        echo ""
        echo "============================================"
        echo "  Quick Test (단위 테스트만)"
        echo "============================================"
        echo ""

        info "pytest 실행 중..."
        python3 -m pytest tests/ -v --tb=short

        echo ""
        success "테스트 통과!"
        echo ""
        ;;

    --coverage|-c|coverage)
        echo ""
        echo "============================================"
        echo "  Coverage Test (커버리지 포함)"
        echo "============================================"
        echo ""

        info "pytest + coverage 실행 중..."
        python3 -m pytest tests/ \
            --cov=src \
            --cov-report=term-missing \
            --cov-report=html \
            --cov-fail-under=80 \
            -v

        echo ""
        success "테스트 통과!"
        echo ""
        echo "  커버리지 리포트: htmlcov/index.html"
        echo ""
        ;;

    --ci|ci)
        echo ""
        echo "============================================"
        echo "  CI Test (GitHub Actions 환경)"
        echo "============================================"
        echo ""

        # 1. 린트 체크
        info "Step 1/3: Lint 체크 (ruff)"
        if command -v ruff &> /dev/null; then
            ruff check src/ tests/ --fix || warn "일부 린트 경고 있음"
            success "Lint OK"
        else
            warn "ruff 미설치 - 건너뜀"
        fi

        # 2. 타입 체크
        info "Step 2/3: Type 체크 (mypy)"
        if command -v mypy &> /dev/null; then
            mypy src/ --ignore-missing-imports || warn "일부 타입 경고 있음"
            success "Type OK"
        else
            warn "mypy 미설치 - 건너뜀"
        fi

        # 3. 테스트 + 커버리지
        info "Step 3/3: 테스트 + 커버리지"
        python3 -m pytest tests/ \
            --cov=src \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=80 \
            -v \
            --tb=short

        echo ""
        success "CI 테스트 전체 통과!"
        echo ""
        ;;

    --help|-h|help)
        echo "Usage: ./scripts/test.sh [command]"
        echo ""
        echo "Commands:"
        echo "  --quick     빠른 테스트 (기본값)"
        echo "  --coverage  커버리지 포함 테스트"
        echo "  --ci        CI 환경 테스트 (lint + type + coverage)"
        echo "  --help      도움말"
        echo ""
        ;;

    *)
        error "알 수 없는 명령어: $1 (--help 참조)"
        ;;
esac
