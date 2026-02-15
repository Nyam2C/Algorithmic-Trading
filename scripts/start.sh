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

# Compose 파일 경로 (통합: Bot + API 단일 프로세스)
COMPOSE_FILES="--env-file .env -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml -f deploy/docker-compose.n8n.yml -f deploy/docker-compose.monitoring.yml"
# 단독 monitoring compose (별도 프로젝트로 실행됐을 수 있음)
MONITORING_COMPOSE="-f monitoring/docker-compose.yml"

# -----------------------------------------------------------------------------
# 다른 compose 프로젝트의 충돌 컨테이너 정리
# -----------------------------------------------------------------------------
cleanup_conflicting_containers() {
    local containers="trading-loki trading-promtail trading-grafana trading-prometheus"
    for name in $containers; do
        # deploy 프로젝트가 아닌 다른 프로젝트 소속 컨테이너가 있으면 제거
        local project
        project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$name" 2>/dev/null || true)
        if [ -n "$project" ] && [ "$project" != "deploy" ]; then
            warn "충돌 컨테이너 제거: $name (project=$project)"
            docker rm -f "$name" > /dev/null 2>&1 || true
        fi
    done
}

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

        info "충돌 컨테이너 확인 중..."
        cleanup_conflicting_containers

        info "전체 스택 시작 중..."
        docker compose $COMPOSE_FILES up -d --build

        echo ""
        success "모든 서비스가 시작되었습니다!"
        echo ""
        echo "  서비스 접속:"
        echo "    - n8n:      http://localhost:5678 (워크플로우 자동화)"
        echo "    - Grafana:  http://localhost:3000 (admin/\${GRAFANA_ADMIN_PASSWORD:-changeme})"
        echo "    - API:      http://localhost:8000/health"
        echo "    - API Docs: http://localhost:8000/docs (debug 모드)"
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
        # 단독 monitoring 프로젝트도 함께 정리
        if docker compose $MONITORING_COMPOSE ps -q 2>/dev/null | grep -q .; then
            warn "단독 monitoring 프로젝트 컨테이너도 정리 중..."
            docker compose $MONITORING_COMPOSE down
        fi
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

        if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
            echo -e "  n8n:      ${GREEN}Running${NC}"
        else
            echo -e "  n8n:      ${RED}Stopped${NC}"
        fi

        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            echo -e "  Grafana:  ${GREEN}Running${NC}"
        else
            echo -e "  Grafana:  ${RED}Stopped${NC}"
        fi

        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "  API:      ${GREEN}Running${NC}"
        else
            echo -e "  API:      ${RED}Stopped${NC}"
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
