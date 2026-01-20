#!/bin/bash
# =============================================================================
# start.sh - 모든 서비스 시작 (Docker)
# =============================================================================
# Bot + DB + Backend + Monitoring 전체 스택 실행
# Usage: ./scripts/start.sh [--stop|--logs|--status]
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

# Compose 파일 경로
COMPOSE_FILES="-f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml -f deploy/docker-compose.backend.yml -f deploy/docker-compose.monitoring.yml"

# -----------------------------------------------------------------------------
# 명령어 처리
# -----------------------------------------------------------------------------
case "${1:-start}" in
    start)
        echo ""
        echo "============================================"
        echo "  Algorithmic Trading - Start All Services"
        echo "============================================"
        echo ""

        # Docker 확인
        if ! docker info &> /dev/null 2>&1; then
            error "Docker가 실행되지 않았습니다"
        fi

        # .env 확인
        if [ ! -f .env ]; then
            error ".env 파일이 없습니다. ./scripts/setup.sh를 먼저 실행하세요"
        fi

        info "전체 스택 시작 중..."
        docker compose $COMPOSE_FILES up -d --build

        echo ""
        success "모든 서비스가 시작되었습니다!"
        echo ""
        echo "  서비스 접속:"
        echo "    - Grafana:  http://localhost:3000 (admin/admin123)"
        echo "    - Backend:  http://localhost:8080/api/health"
        echo "    - DB:       localhost:5432"
        echo ""
        echo "  명령어:"
        echo "    ./scripts/start.sh --logs    # 로그 보기"
        echo "    ./scripts/start.sh --status  # 상태 확인"
        echo "    ./scripts/start.sh --stop    # 중지"
        echo ""
        ;;

    --stop|-s|stop)
        info "모든 서비스 중지 중..."
        docker compose $COMPOSE_FILES down
        success "중지 완료"
        ;;

    --logs|-l|logs)
        info "로그 스트리밍 (Ctrl+C로 종료)"
        docker compose $COMPOSE_FILES logs -f
        ;;

    --status|status)
        echo ""
        echo "============================================"
        echo "  서비스 상태"
        echo "============================================"
        echo ""
        docker compose $COMPOSE_FILES ps
        echo ""

        # Health check
        echo "Health Checks:"

        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            echo -e "  Grafana:  ${GREEN}Running${NC}"
        else
            echo -e "  Grafana:  ${RED}Stopped${NC}"
        fi

        if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
            echo -e "  Backend:  ${GREEN}Running${NC}"
        else
            echo -e "  Backend:  ${RED}Stopped${NC}"
        fi

        if docker exec trading-db pg_isready -U trading > /dev/null 2>&1; then
            echo -e "  Database: ${GREEN}Running${NC}"
        else
            echo -e "  Database: ${RED}Stopped${NC}"
        fi

        if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
            echo -e "  Loki:     ${GREEN}Running${NC}"
        else
            echo -e "  Loki:     ${RED}Stopped${NC}"
        fi
        echo ""
        ;;

    --help|-h|help)
        echo "Usage: ./scripts/start.sh [command]"
        echo ""
        echo "Commands:"
        echo "  (none)    전체 서비스 시작"
        echo "  --stop    전체 서비스 중지"
        echo "  --logs    로그 스트리밍"
        echo "  --status  서비스 상태 확인"
        echo "  --help    도움말"
        echo ""
        ;;

    *)
        error "알 수 없는 명령어: $1 (--help 참조)"
        ;;
esac
