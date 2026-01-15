#!/bin/bash
# =============================================================================
# High-Win Survival System - Docker 통합 실행 스크립트
# Docker 빌드 → 컨테이너 실행 → 봇 동작을 한 번에 처리
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo "============================================================"
    echo "   High-Win Survival System - Docker Deployment"
    echo "   One-Click Build & Run with Docker"
    echo "============================================================"
    echo ""
}

check_docker() {
    log_info "Docker 설치 확인 중..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다."
        echo ""
        echo "Docker 설치 방법:"
        echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
        echo "  Mac: https://docs.docker.com/desktop/install/mac-install/"
        echo "  Linux: https://docs.docker.com/engine/install/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker가 실행되고 있지 않습니다."
        echo "Docker Desktop을 시작해주세요."
        exit 1
    fi

    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    log_success "Docker 버전: $DOCKER_VERSION"
}

check_docker_compose() {
    log_info "Docker Compose 확인 중..."

    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        COMPOSE_VERSION=$(docker compose version | awk '{print $4}')
    elif docker-compose --version &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $4}' | sed 's/,//')
    else
        log_error "Docker Compose가 설치되어 있지 않습니다."
        exit 1
    fi

    log_success "Docker Compose 버전: $COMPOSE_VERSION"
}

check_env_file() {
    log_info ".env 파일 확인 중..."

    if [ ! -f ".env" ]; then
        log_warning ".env 파일이 없습니다. .env.example을 복사합니다..."
        cp .env.example .env
        log_warning ".env 파일을 생성했습니다."
        echo ""
        echo "⚠️  필수: .env 파일에 API 키를 입력해주세요!"
        echo ""
        echo "필수 항목:"
        echo "  - BINANCE_API_KEY"
        echo "  - BINANCE_SECRET_KEY"
        echo "  - GEMINI_API_KEY"
        echo "  - DISCORD_WEBHOOK_URL"
        echo ""
        read -p ".env 파일 편집을 완료했으면 Enter를 눌러주세요..." dummy
    else
        log_success ".env 파일 존재"
    fi
}

validate_api_keys() {
    log_info "API 키 검증 중..."

    source .env

    MISSING_KEYS=()

    if [ -z "$BINANCE_API_KEY" ] || [ "$BINANCE_API_KEY" == "your_binance_testnet_api_key" ]; then
        MISSING_KEYS+=("BINANCE_API_KEY")
    fi

    if [ -z "$BINANCE_SECRET_KEY" ] || [ "$BINANCE_SECRET_KEY" == "your_binance_testnet_secret_key" ]; then
        MISSING_KEYS+=("BINANCE_SECRET_KEY")
    fi

    if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" == "your_gemini_api_key" ]; then
        MISSING_KEYS+=("GEMINI_API_KEY")
    fi

    if [ -z "$DISCORD_WEBHOOK_URL" ] || [[ "$DISCORD_WEBHOOK_URL" == *"your-webhook-url"* ]]; then
        MISSING_KEYS+=("DISCORD_WEBHOOK_URL")
    fi

    if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
        log_error "다음 API 키가 설정되지 않았습니다:"
        for key in "${MISSING_KEYS[@]}"; do
            echo "  - $key"
        done
        echo ""
        echo "API 키 발급:"
        echo "  1. Binance Testnet: https://testnet.binancefuture.com"
        echo "  2. Gemini AI: https://aistudio.google.com/apikey"
        echo "  3. Discord Webhook: Discord 서버 > 설정 > 연동 > 웹후크"
        exit 1
    fi

    log_success "API 키 검증 완료"
}

stop_existing_containers() {
    log_info "기존 컨테이너 정리 중..."

    if $COMPOSE_CMD ps | grep -q "trading-bot"; then
        log_warning "기존 컨테이너를 중지합니다..."
        $COMPOSE_CMD down
        log_success "기존 컨테이너 중지 완료"
    else
        log_info "실행 중인 컨테이너 없음"
    fi
}

build_docker_image() {
    log_info "Docker 이미지 빌드 중..."
    echo ""

    $COMPOSE_CMD build --no-cache

    if [ $? -eq 0 ]; then
        log_success "Docker 이미지 빌드 완료"
    else
        log_error "Docker 이미지 빌드 실패"
        exit 1
    fi
}

start_containers() {
    log_info "Docker 컨테이너 시작 중..."
    echo ""

    # PostgreSQL 먼저 시작 (헬스체크 대기)
    log_info "PostgreSQL 컨테이너 시작..."
    $COMPOSE_CMD up -d postgres

    log_info "PostgreSQL 헬스체크 대기 중..."
    sleep 5

    # Trading Bot 시작
    log_info "Trading Bot 컨테이너 시작..."
    $COMPOSE_CMD up -d trading-bot

    if [ $? -eq 0 ]; then
        log_success "컨테이너 시작 완료"
    else
        log_error "컨테이너 시작 실패"
        exit 1
    fi
}

show_status() {
    echo ""
    log_info "실행 중인 컨테이너:"
    echo ""
    $COMPOSE_CMD ps
    echo ""
}

show_logs() {
    echo ""
    log_success "봇이 실행되었습니다!"
    echo ""
    echo "============================================================"
    echo "  로그 확인 방법:"
    echo "    docker compose logs -f trading-bot"
    echo ""
    echo "  컨테이너 중지:"
    echo "    docker compose down"
    echo ""
    echo "  컨테이너 재시작:"
    echo "    docker compose restart trading-bot"
    echo "============================================================"
    echo ""

    read -p "실시간 로그를 확인하시겠습니까? (y/N): " choice
    if [[ "$choice" =~ ^[Yy]$ ]]; then
        echo ""
        log_info "로그 스트리밍 시작 (Ctrl+C로 종료)"
        echo ""
        $COMPOSE_CMD logs -f trading-bot
    fi
}

main() {
    print_banner

    # 1. Docker 확인
    check_docker
    check_docker_compose

    # 2. .env 파일 확인
    check_env_file

    # 3. API 키 검증
    validate_api_keys

    # 4. 기존 컨테이너 정리
    stop_existing_containers

    # 5. Docker 이미지 빌드
    build_docker_image

    # 6. 컨테이너 시작
    start_containers

    # 7. 상태 확인
    show_status

    # 8. 로그 표시
    show_logs
}

main "$@"
