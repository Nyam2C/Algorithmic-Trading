#!/bin/bash
# ===========================================
# GitHub Actions CI - Local Test
# ===========================================
# GitHub Actions의 CI 파이프라인을 로컬에서 테스트

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}=============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

cd "$(dirname "$0")/.."

print_header "GitHub Actions CI - Local Test"

# 에러 카운터
ERRORS=0

# 1. Python 버전 확인
print_header "Step 1/6: Python Version Check"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        print_success "Python $PYTHON_VERSION (OK)"
    else
        print_error "Python $PYTHON_VERSION (Need 3.11+)"
        ERRORS=$((ERRORS + 1))
    fi
else
    print_error "Python not found"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 2. 의존성 설치
print_header "Step 2/6: Install Dependencies"

print_info "Installing dependencies..."
pip3 install -r requirements.txt --quiet 2>&1 | grep -v "Requirement already satisfied" || true
pip3 install pytest pytest-asyncio pytest-cov ruff mypy pip-audit --quiet 2>&1 | grep -v "Requirement already satisfied" || true

print_success "Dependencies installed"
echo ""

# 3. Security Scan
print_header "Step 3/6: Security Scan (pip-audit)"

if command -v pip-audit &> /dev/null; then
    if pip-audit --strict 2>&1; then
        print_success "No vulnerabilities found"
    else
        print_warning "Vulnerabilities found (non-blocking)"
    fi
else
    print_warning "pip-audit not installed, skipping security scan"
fi

echo ""

# 4. Lint Check
print_header "Step 4/6: Lint Check (ruff)"

if command -v ruff &> /dev/null; then
    if ruff check src/ 2>&1; then
        print_success "Lint check passed"
    else
        print_error "Lint check failed"
        ERRORS=$((ERRORS + 1))
    fi
else
    print_warning "ruff not installed, skipping lint"
fi

echo ""

# 5. Type Check
print_header "Step 5/6: Type Check (mypy)"

if command -v mypy &> /dev/null; then
    if mypy src/ --ignore-missing-imports --no-error-summary 2>&1; then
        print_success "Type check passed"
    else
        print_warning "Type hints incomplete (non-blocking)"
    fi
else
    print_warning "mypy not installed, skipping type check"
fi

echo ""

# 6. Tests with Coverage
print_header "Step 6/6: Run Tests with Coverage"

if command -v pytest &> /dev/null; then
    if [ -d "tests" ]; then
        # Run pytest (explicitly without coverage to avoid conflicts with pytest.ini)
        pytest tests/ -v --tb=short --cov=src --cov-report=term-missing
        TEST_EXIT=$?
        if [ $TEST_EXIT -eq 0 ]; then
            print_success "All tests passed"
        else
            print_error "Tests failed"
            ERRORS=$((ERRORS + 1))
        fi
    else
        print_warning "tests/ directory not found, skipping tests"
    fi
else
    print_warning "pytest not installed, skipping tests"
fi

echo ""

# 결과 요약
print_header "Test Summary"

if [ $ERRORS -eq 0 ]; then
    print_success "All CI checks passed! ✨"
    echo ""
    echo "This code is ready for:"
    echo "  - git push"
    echo "  - Pull Request"
    echo ""
    exit 0
else
    print_error "CI checks failed with $ERRORS error(s)"
    echo ""
    echo "Please fix the errors before:"
    echo "  - git push"
    echo "  - Pull Request"
    echo ""
    exit 1
fi
