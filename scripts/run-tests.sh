#!/bin/bash
# =============================================================================
# 테스트 실행 스크립트
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  Running Tests - High-Win Survival System"
echo "============================================================"
echo ""

# Python 명령어 확인
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Python not found!"
    exit 1
fi

# 옵션 파싱
COVERAGE=true
VERBOSE=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --no-cov) COVERAGE=false ;;
        -v|--verbose) VERBOSE="-vv" ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# 테스트 실행
echo -e "${BLUE}[INFO]${NC} Running pytest..."
echo ""

if [ "$COVERAGE" = true ]; then
    $PYTHON_CMD -m pytest $VERBOSE
else
    $PYTHON_CMD -m pytest $VERBOSE --no-cov
fi

TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo "Coverage report generated in: htmlcov/index.html"
        echo "Open with: open htmlcov/index.html"
    fi
else
    echo -e "${YELLOW}✗ Some tests failed${NC}"
    exit 1
fi

echo ""
