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
    print_header "Algorithmic Trading CLI"

    echo "사용법:"
    echo "  ./scripts/bot.sh <command> [options]"
    echo ""
    echo "🚀 빠른 시작 (One-Command):"
    echo "  setup         전체 환경 자동 설정 (최초 1회)"
    echo "  dev           봇만 실행 (빠른 개발)"
    echo "  dev:monitor   봇 + 모니터링"
    echo "  dev:backend   봇 + Go API 백엔드"
    echo "  dev:all       전체 스택 (Bot + DB + Backend + Monitoring)"
    echo "  dev:down      전체 중지"
    echo "  dev:logs      전체 로그"
    echo "  prod          프로덕션 실행"
    echo ""
    echo "📦 기본 명령어:"
    echo "  run           로컬에서 봇 실행"
    echo "  docker        Docker로 봇 실행"
    echo "  test          테스트 실행"
    echo "  test:ci       CI 테스트 (로컬에서 GitHub Actions 검증)"
    echo "  db            데이터베이스 초기화"
    echo "  logs          로그 확인"
    echo "  stop          봇 중지"
    echo "  restart       봇 재시작"
    echo "  status        봇 상태 확인"
    echo "  clean         임시 파일 정리"
    echo "  help          이 도움말 표시"
    echo ""
    echo "📊 모니터링:"
    echo "  monitoring start      모니터링 스택 시작"
    echo "  monitoring stop       모니터링 스택 중지"
    echo "  monitoring status     모니터링 상태 확인"
    echo ""
    echo "예시:"
    echo "  ./scripts/bot.sh setup           # 최초 설정 (1회)"
    echo "  ./scripts/bot.sh dev:all         # 전체 스택 시작"
    echo "  ./scripts/bot.sh dev:monitor     # 봇 + 모니터링만"
    echo "  ./scripts/bot.sh prod            # 프로덕션 실행"
    echo ""
}

cmd_setup() {
    print_header "전체 환경 설정"
    ./scripts/setup-all.sh "$@"
}

cmd_dev() {
    print_header "개발 환경 (Bot + DB)"
    print_info "Starting: Bot + PostgreSQL"
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
    print_success "Services started!"
    echo ""
    echo "  Bot: docker logs -f trading-bot"
    echo "  DB:  docker logs -f trading-db"
    echo ""
}

cmd_dev_monitor() {
    print_header "개발 환경 (Bot + DB + Monitoring)"
    print_info "Starting: Bot + PostgreSQL + Grafana + Loki"
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        -f docker-compose.monitoring.yml \
        up -d --build

    print_success "Services started!"
    echo ""
    echo "  Grafana:     http://localhost:3000 (admin/admin123)"
    echo "  Bot logs:    docker logs -f trading-bot"
    echo "  All logs:    ./scripts/bot.sh dev:logs"
    echo ""

    # 모니터링 초기화
    print_info "Initializing monitoring stack..."
    sleep 5
    ./monitoring/init-monitoring.sh
}

cmd_dev_backend() {
    print_header "개발 환경 (Bot + DB + Backend)"
    print_info "Starting: Bot + PostgreSQL + Go API"
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        -f docker-compose.backend.yml \
        up -d --build

    print_success "Services started!"
    echo ""
    echo "  Backend API: http://localhost:8080/api/health"
    echo "  Bot logs:    docker logs -f trading-bot"
    echo "  API logs:    docker logs -f trading-backend"
    echo ""
}

cmd_dev_all() {
    print_header "전체 스택 (Bot + DB + Backend + Monitoring)"
    print_info "Starting: All services"
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        -f docker-compose.backend.yml \
        -f docker-compose.monitoring.yml \
        up -d --build

    print_success "All services started!"
    echo ""
    echo "  Backend API: http://localhost:8080/api/health"
    echo "  Grafana:     http://localhost:3000 (admin/admin123)"
    echo "  Database:    localhost:5432"
    echo ""
    echo "  Logs:        ./scripts/bot.sh dev:logs"
    echo ""

    # 모니터링 초기화
    print_info "Initializing monitoring stack..."
    sleep 5
    ./monitoring/init-monitoring.sh
}

cmd_dev_down() {
    print_header "전체 스택 중지"
    print_info "Stopping all services..."
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        -f docker-compose.backend.yml \
        -f docker-compose.monitoring.yml \
        down

    print_success "All services stopped"
}

cmd_dev_logs() {
    print_info "전체 서비스 로그 확인 중..."
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        -f docker-compose.backend.yml \
        -f docker-compose.monitoring.yml \
        logs -f
}

cmd_prod() {
    print_header "프로덕션 실행"
    print_info "Starting production stack..."

    # 프로덕션 경고
    echo ""
    echo -e "${RED}⚠️  WARNING: Production mode will use REAL TRADING${NC}"
    echo -e "${RED}⚠️  Make sure TESTNET=false in .env${NC}"
    echo ""
    read -p "Continue? (yes/no): " response

    if [ "$response" != "yes" ]; then
        print_info "Aborted"
        exit 0
    fi

    docker compose \
        -f docker-compose.yml \
        -f docker-compose.prod.yml \
        -f docker-compose.monitoring.yml \
        up -d --build

    print_success "Production stack started!"
    echo ""
    echo "  Grafana:     http://localhost:3000"
    echo "  Logs:        docker compose logs -f"
    echo ""
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

cmd_test_ci() {
    print_header "CI 테스트 (로컬)"
    ./scripts/test-ci.sh "$@"
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
        dev)
            cmd_dev "$@"
            ;;
        dev:monitor)
            cmd_dev_monitor "$@"
            ;;
        dev:backend)
            cmd_dev_backend "$@"
            ;;
        dev:all)
            cmd_dev_all "$@"
            ;;
        dev:down)
            cmd_dev_down "$@"
            ;;
        dev:logs)
            cmd_dev_logs "$@"
            ;;
        prod)
            cmd_prod "$@"
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
        test:ci)
            cmd_test_ci "$@"
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
