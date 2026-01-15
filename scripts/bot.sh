#!/bin/bash
# =============================================================================
# High-Win Survival System - All-in-One CLI
# =============================================================================
# 모든 기능을 하나의 스크립트로 통합
#
# Usage:
#     ./scripts/bot.sh setup        # 환경 설정
#     ./scripts/bot.sh run          # 로컬 실행
#     ./scripts/bot.sh docker       # Docker 실행
#     ./scripts/bot.sh test         # 테스트 실행
#     ./scripts/bot.sh db           # DB 초기화
#     ./scripts/bot.sh help         # 도움말
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    print_header "High-Win Survival System CLI"

    echo "사용법:"
    echo "  ./scripts/bot.sh <command> [options]"
    echo ""
    echo "명령어:"
    echo "  setup         전체 환경 설정 (최초 1회)"
    echo "  run           로컬에서 봇 실행"
    echo "  docker        Docker로 봇 실행 (권장)"
    echo "  test          테스트 실행"
    echo "  db            데이터베이스 초기화"
    echo "  logs          로그 확인"
    echo "  stop          봇 중지 (Docker)"
    echo "  restart       봇 재시작 (Docker)"
    echo "  status        봇 상태 확인"
    echo "  monitoring    모니터링 스택 관리 (start/stop/restart/logs)"
    echo "  clean         임시 파일 정리"
    echo "  help          이 도움말 표시"
    echo ""
    echo "옵션:"
    echo "  --dev         개발 모드"
    echo "  --verbose     상세 로그"
    echo ""
    echo "예시:"
    echo "  ./scripts/bot.sh setup           # 최초 설정"
    echo "  ./scripts/bot.sh docker          # Docker 실행"
    echo "  ./scripts/bot.sh test            # 테스트"
    echo "  ./scripts/bot.sh logs            # 로그 확인"
    echo ""
}

cmd_setup() {
    print_header "환경 설정"

    if [ "$1" == "--dev" ]; then
        ./scripts/setup.sh --dev
    else
        ./scripts/setup.sh --all
    fi
}

cmd_run() {
    print_header "로컬 실행"
    ./scripts/run.sh "$@"
}

cmd_docker() {
    print_header "Docker 실행"
    ./scripts/start-docker.sh "$@"
}

cmd_test() {
    print_header "테스트 실행"
    ./scripts/run-tests.sh "$@"
}

cmd_db() {
    print_header "데이터베이스 초기화"
    ./db/setup.sh
}

cmd_logs() {
    print_info "로그 확인 중..."

    if docker ps | grep -q trading-bot; then
        # Docker 로그
        docker compose logs -f bot
    else
        # 로컬 로그
        if [ -f "logs/bot.log" ]; then
            tail -f logs/bot.log
        else
            print_error "로그 파일을 찾을 수 없습니다: logs/bot.log"
            exit 1
        fi
    fi
}

cmd_stop() {
    print_info "봇 중지 중..."
    docker compose down
    print_success "봇이 중지되었습니다"
}

cmd_restart() {
    print_info "봇 재시작 중..."
    docker compose restart bot
    print_success "봇이 재시작되었습니다"

    echo ""
    read -p "로그를 확인하시겠습니까? (y/N): " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        docker compose logs -f bot
    fi
}

cmd_status() {
    print_header "봇 상태"

    echo -e "${BLUE}Docker 컨테이너:${NC}"
    if docker ps | grep -q trading; then
        docker ps | grep trading
        echo ""
        print_success "봇이 실행 중입니다"
    else
        print_info "실행 중인 컨테이너가 없습니다"
    fi

    echo ""
    echo -e "${BLUE}시스템 정보:${NC}"
    echo "Python: $(python3 --version 2>&1 || echo 'Not found')"
    echo "Docker: $(docker --version 2>&1 || echo 'Not found')"
    echo "Database: $(docker ps | grep postgres &>/dev/null && echo 'Running' || echo 'Stopped')"
}

cmd_monitoring() {
    local subcommand=$1

    case $subcommand in
        start)
            print_header "모니터링 스택 시작"
            print_info "Grafana + Loki + Promtail 시작 중..."
            docker compose -f monitoring/docker-compose.yml up -d

            echo ""
            print_success "모니터링 스택이 시작되었습니다"
            echo ""
            echo -e "${BLUE}접속 정보:${NC}"
            echo "  Grafana: http://localhost:3000"
            echo "  ID: admin"
            echo "  PW: admin123"
            echo ""
            echo -e "${BLUE}대시보드:${NC}"
            echo "  1. Trading Overview - 거래 현황"
            echo "  2. AI Signals - AI 신호 분석"
            echo "  3. System Health - 시스템 상태"
            ;;
        stop)
            print_header "모니터링 스택 중지"
            docker compose -f monitoring/docker-compose.yml down
            print_success "모니터링 스택이 중지되었습니다"
            ;;
        restart)
            print_header "모니터링 스택 재시작"
            docker compose -f monitoring/docker-compose.yml restart
            print_success "모니터링 스택이 재시작되었습니다"
            ;;
        logs)
            print_info "모니터링 로그 확인 중..."
            docker compose -f monitoring/docker-compose.yml logs -f
            ;;
        status)
            print_header "모니터링 스택 상태"
            docker compose -f monitoring/docker-compose.yml ps

            echo ""
            echo -e "${BLUE}서비스 상태:${NC}"

            # Loki 상태
            if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
                echo "  Loki: $(print_success '✓ Running')"
            else
                echo "  Loki: $(print_error '✗ Stopped')"
            fi

            # Grafana 상태
            if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
                echo "  Grafana: $(print_success '✓ Running')"
            else
                echo "  Grafana: $(print_error '✗ Stopped')"
            fi
            ;;
        *)
            print_error "알 수 없는 모니터링 명령어: $subcommand"
            echo ""
            echo "사용 가능한 명령어:"
            echo "  ./scripts/bot.sh monitoring start    # 시작"
            echo "  ./scripts/bot.sh monitoring stop     # 중지"
            echo "  ./scripts/bot.sh monitoring restart  # 재시작"
            echo "  ./scripts/bot.sh monitoring logs     # 로그 확인"
            echo "  ./scripts/bot.sh monitoring status   # 상태 확인"
            exit 1
            ;;
    esac
}

cmd_clean() {
    print_info "임시 파일 정리 중..."

    # Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true

    # Test artifacts
    rm -rf .pytest_cache htmlcov .coverage 2>/dev/null || true

    # Logs (선택)
    read -p "로그 파일도 삭제하시겠습니까? (y/N): " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf logs/*.log 2>/dev/null || true
        print_success "로그 파일 삭제됨"
    fi

    print_success "정리 완료"
}

# Main
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    COMMAND=$1
    shift

    case $COMMAND in
        setup)
            cmd_setup "$@"
            ;;
        run)
            cmd_run "$@"
            ;;
        docker|start)
            cmd_docker "$@"
            ;;
        test)
            cmd_test "$@"
            ;;
        db)
            cmd_db "$@"
            ;;
        logs)
            cmd_logs "$@"
            ;;
        stop)
            cmd_stop "$@"
            ;;
        restart)
            cmd_restart "$@"
            ;;
        status)
            cmd_status "$@"
            ;;
        monitoring)
            cmd_monitoring "$@"
            ;;
        clean)
            cmd_clean "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "알 수 없는 명령어: $COMMAND"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
