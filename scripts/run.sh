#!/bin/bash
# =============================================================================
# High-Win Survival System - 통합 실행 스크립트
# Sprint 1: Paper Trading MVP
# =============================================================================

set -e  # 에러 발생 시 즉시 중단

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
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

# 배너 출력
print_banner() {
    echo ""
    echo "============================================================"
    echo "   High-Win Survival System - Sprint 1 MVP"
    echo "   Binance Testnet + Gemini AI Trading Bot"
    echo "============================================================"
    echo ""
}

# Python 버전 체크
check_python() {
    log_info "Python 버전 확인 중..."

    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python이 설치되어 있지 않습니다."
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log_success "Python 버전: $PYTHON_VERSION"
}

# 의존성 설치
install_dependencies() {
    log_info "의존성 패키지 설치 중..."

    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt 파일이 없습니다."
        exit 1
    fi

    $PYTHON_CMD -m pip install --upgrade pip -q
    $PYTHON_CMD -m pip install -r requirements.txt -q

    log_success "의존성 설치 완료"
}

# .env 파일 체크
check_env_file() {
    log_info ".env 파일 확인 중..."

    if [ ! -f ".env" ]; then
        log_warning ".env 파일이 없습니다. .env.example을 복사합니다..."
        cp .env.example .env
        log_warning ".env 파일을 생성했습니다. API 키를 입력해주세요!"
        echo ""
        echo "필수 설정 항목:"
        echo "  - BINANCE_API_KEY (Binance Testnet API 키)"
        echo "  - BINANCE_SECRET_KEY (Binance Testnet Secret 키)"
        echo "  - GEMINI_API_KEY (Gemini AI API 키)"
        echo "  - DISCORD_WEBHOOK_URL (Discord Webhook URL)"
        echo ""
        read -p ".env 파일 편집을 완료했으면 Enter를 눌러주세요..." dummy
    else
        log_success ".env 파일 존재"
    fi
}

# API 키 검증
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

    if [ -z "$DISCORD_WEBHOOK_URL" ] || [ "$DISCORD_WEBHOOK_URL" == "https://discord.com/api/webhooks/your-webhook-url" ]; then
        MISSING_KEYS+=("DISCORD_WEBHOOK_URL")
    fi

    if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
        log_error "다음 API 키가 설정되지 않았습니다:"
        for key in "${MISSING_KEYS[@]}"; do
            echo "  - $key"
        done
        echo ""
        echo "API 키 발급 방법:"
        echo "  1. Binance Testnet: https://testnet.binancefuture.com"
        echo "  2. Gemini AI: https://aistudio.google.com/apikey"
        echo "  3. Discord Webhook: Discord 서버 설정 > 연동 > 웹후크"
        echo ""
        exit 1
    fi

    log_success "API 키 검증 완료"
}

# Import 테스트
test_imports() {
    log_info "모듈 Import 테스트 중..."

    $PYTHON_CMD -c "from src.config import get_config" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "✓ src.config"
    else
        log_error "✗ src.config - Import 실패"
        exit 1
    fi

    $PYTHON_CMD -c "from src.exchange.binance import BinanceTestnetClient" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "✓ src.exchange.binance"
    else
        log_error "✗ src.exchange.binance - Import 실패"
        exit 1
    fi

    $PYTHON_CMD -c "from src.data.indicators import analyze_market" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "✓ src.data.indicators"
    else
        log_error "✗ src.data.indicators - Import 실패"
        exit 1
    fi

    $PYTHON_CMD -c "from src.ai.gemini import GeminiSignalGenerator" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "✓ src.ai.gemini"
    else
        log_error "✗ src.ai.gemini - Import 실패"
        exit 1
    fi

    $PYTHON_CMD -c "from src.trading.executor import TradingExecutor" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "✓ src.trading.executor"
    else
        log_error "✗ src.trading.executor - Import 실패"
        exit 1
    fi

    log_success "모든 모듈 Import 성공"
}

# 봇 실행
run_bot() {
    log_info "트레이딩 봇 시작..."
    echo ""
    echo "============================================================"
    echo "  봇이 실행됩니다. Ctrl+C로 중지할 수 있습니다."
    echo "============================================================"
    echo ""

    $PYTHON_CMD -m src.main
}

# 메인 실행
main() {
    print_banner

    # 1. Python 체크
    check_python

    # 2. 의존성 설치 (--skip-install 옵션으로 생략 가능)
    if [[ "$1" != "--skip-install" ]]; then
        install_dependencies
    else
        log_info "의존성 설치 건너뜀 (--skip-install)"
    fi

    # 3. .env 파일 체크
    check_env_file

    # 4. API 키 검증
    validate_api_keys

    # 5. Import 테스트
    test_imports

    echo ""
    log_success "모든 사전 체크 완료! 봇을 시작합니다..."
    echo ""
    sleep 2

    # 6. 봇 실행
    run_bot
}

# 스크립트 실행
main "$@"
