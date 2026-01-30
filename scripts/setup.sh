#!/bin/bash
# =============================================================================
# setup.sh - 전체 환경 설정
# =============================================================================
# 환경 변수 + Python 의존성 + Docker + DB 초기화
# Usage: ./scripts/setup.sh
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

echo ""
echo "============================================"
echo "  Algorithmic Trading - Setup"
echo "============================================"
echo ""

# -----------------------------------------------------------------------------
# 1. 환경 변수 (.env)
# -----------------------------------------------------------------------------
info "Step 1/5: 환경 변수 설정"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn ".env 파일 생성됨 - API 키를 입력하세요!"
        echo ""
        echo "  필수 항목:"
        echo "    - BINANCE_API_KEY"
        echo "    - BINANCE_SECRET_KEY"
        echo "    - GEMINI_API_KEY"
        echo "    - DB_PASSWORD"
        echo ""
        read -p "  .env 편집 후 Enter를 누르세요..."
    else
        error ".env.example 파일이 없습니다"
    fi
fi

source .env

# 필수 변수 검증
REQUIRED=("BINANCE_API_KEY" "BINANCE_SECRET_KEY" "DB_PASSWORD")
MISSING=()

for var in "${REQUIRED[@]}"; do
    val="${!var}"
    if [ -z "$val" ] || [[ "$val" == *"your_"* ]]; then
        MISSING+=("$var")
    fi
done

if [ ${#MISSING[@]} -ne 0 ]; then
    error "환경 변수 미설정: ${MISSING[*]}"
fi

success "환경 변수 OK"

# -----------------------------------------------------------------------------
# 2. Python 의존성
# -----------------------------------------------------------------------------
info "Step 2/5: Python 의존성 설치"

if ! command -v python3 &> /dev/null; then
    error "Python3가 설치되어 있지 않습니다"
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
info "Python $PYTHON_VERSION"

if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt --quiet
    success "Python 의존성 설치 완료"
else
    warn "requirements.txt 없음 - 건너뜀"
fi

# -----------------------------------------------------------------------------
# 3. Docker 확인
# -----------------------------------------------------------------------------
info "Step 3/5: Docker 확인"

if ! command -v docker &> /dev/null; then
    error "Docker가 설치되어 있지 않습니다"
fi

if ! docker info &> /dev/null 2>&1; then
    error "Docker 데몬이 실행되지 않았습니다"
fi

success "Docker OK"

# -----------------------------------------------------------------------------
# 4. 디렉토리 생성
# -----------------------------------------------------------------------------
info "Step 4/5: 디렉토리 생성"

mkdir -p logs
success "logs/ 디렉토리 준비됨"

# -----------------------------------------------------------------------------
# 5. Docker 이미지 빌드
# -----------------------------------------------------------------------------
info "Step 5/5: Docker 이미지 빌드"

docker compose -f deploy/docker-compose.yml build --quiet
success "Docker 이미지 빌드 완료"

# -----------------------------------------------------------------------------
# 완료
# -----------------------------------------------------------------------------
echo ""
echo "============================================"
echo -e "  ${GREEN}Setup 완료!${NC}"
echo "============================================"
echo ""
echo "  다음 명령어로 서비스를 시작하세요:"
echo ""
echo -e "    ${GREEN}./scripts/start.sh${NC}"
echo ""
