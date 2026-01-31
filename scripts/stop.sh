#!/bin/bash
# =============================================================================
# stop.sh - 모든 Docker 서비스 종료
# =============================================================================
# Usage: ./scripts/stop.sh [--volumes|-v]
#   --volumes, -v: 볼륨까지 함께 삭제 (DB 데이터 포함)
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

# Compose 파일 경로
COMPOSE_FILES="-f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml -f deploy/docker-compose.api.yml -f deploy/docker-compose.monitoring.yml"

echo ""
echo "============================================"
echo "  Algorithmic Trading - Stop All Services"
echo "============================================"
echo ""

case "${1:-}" in
    --volumes|-v)
        warn "볼륨 포함 삭제 모드 (DB 데이터가 삭제됩니다)"
        echo ""
        read -p "정말로 모든 데이터를 삭제하시겠습니까? (y/N) " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            info "모든 서비스 및 볼륨 삭제 중..."
            docker compose $COMPOSE_FILES down -v --remove-orphans
            success "모든 서비스와 볼륨이 삭제되었습니다"
        else
            info "취소되었습니다"
            exit 0
        fi
        ;;
    "")
        info "모든 서비스 종료 중..."
        docker compose $COMPOSE_FILES down --remove-orphans
        success "모든 서비스가 종료되었습니다"
        ;;
    --help|-h)
        echo "Usage: ./scripts/stop.sh [options]"
        echo ""
        echo "Options:"
        echo "  (none)        서비스만 종료 (볼륨 유지)"
        echo "  --volumes, -v 볼륨까지 함께 삭제 (DB 데이터 포함)"
        echo "  --help, -h    도움말"
        echo ""
        ;;
    *)
        echo -e "${RED}[ERROR]${NC} 알 수 없는 옵션: $1"
        echo "사용법: ./scripts/stop.sh [--volumes|-v]"
        exit 1
        ;;
esac

echo ""
