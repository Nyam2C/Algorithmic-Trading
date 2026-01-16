#!/bin/bash
# ===========================================
# One-Command Setup Script
# ===========================================
# 전체 환경 자동 초기화:
# - 환경 변수 확인/생성
# - Python 의존성 설치
# - Go 의존성 설치 (백엔드)
# - Docker 이미지 빌드
# - DB 초기화

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."

print_header "Algorithmic Trading - Setup"

# 1. 환경 변수 확인
print_header "Step 1/6: Environment Variables"

if [ ! -f .env ]; then
    print_info ".env file not found. Creating from .env.example..."
    cp .env.example .env
    print_success ".env file created"
    print_error "⚠️  Please edit .env file and add your API keys!"
    echo ""
    echo "Required variables:"
    echo "  - BINANCE_API_KEY"
    echo "  - BINANCE_SECRET_KEY"
    echo "  - GEMINI_API_KEY"
    echo "  - DB_PASSWORD"
    echo ""
    read -p "Press Enter after editing .env file..."
else
    print_success ".env file exists"
fi

# 환경 변수 로드
source .env

# 필수 변수 확인
REQUIRED_VARS=("BINANCE_API_KEY" "BINANCE_SECRET_KEY" "GEMINI_API_KEY" "DB_PASSWORD")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your_${var,,}" ] || [[ "${!var}" == *"your_"* ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    print_error "Missing or invalid environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    print_info "Please edit .env file and set these variables"
    exit 1
fi

print_success "All required environment variables are set"

# 2. Python 의존성 확인
print_header "Step 2/6: Python Dependencies"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"

    if [ -f requirements.txt ]; then
        print_info "Installing Python dependencies..."
        pip3 install -r requirements.txt --quiet
        print_success "Python dependencies installed"
    fi
else
    print_error "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# 3. Go 백엔드 확인 (선택사항)
print_header "Step 3/6: Go Backend (Optional)"

if [ -d "backend" ]; then
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        print_success "$GO_VERSION found"

        cd backend
        print_info "Downloading Go dependencies..."
        go mod download
        print_success "Go dependencies ready"
        cd ..
    else
        print_info "Go not installed. Backend will run in Docker only."
    fi
else
    print_info "Backend directory not found. Skipping."
fi

# 4. Docker 확인
print_header "Step 4/6: Docker Environment"

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker daemon not running. Please start Docker."
    exit 1
fi

print_success "Docker is ready"

# 5. 로그 디렉토리 생성
print_header "Step 5/6: Directory Setup"

mkdir -p logs
print_success "Log directory created"

# 6. 요약
print_header "Setup Complete!"

echo ""
print_success "Environment is ready!"
echo ""
echo "Next steps:"
echo ""
echo "  Development (Bot + DB only):"
echo "    ${GREEN}./scripts/bot.sh dev${NC}"
echo ""
echo "  Development (Bot + DB + Monitoring):"
echo "    ${GREEN}./scripts/bot.sh dev:monitor${NC}"
echo ""
echo "  Development (Full Stack):"
echo "    ${GREEN}./scripts/bot.sh dev:all${NC}"
echo ""
echo "  Production:"
echo "    ${GREEN}./scripts/bot.sh prod${NC}"
echo ""
print_info "For more commands: ./scripts/bot.sh help"
echo ""
