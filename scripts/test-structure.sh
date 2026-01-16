#!/bin/bash
# ===========================================
# Docker Compose 구조 검증 스크립트
# ===========================================
# API 키 없이도 Docker Compose 계층화가
# 제대로 작동하는지 테스트

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

cd "$(dirname "$0")/.."

print_header "Docker Compose 구조 검증"

# 1. 파일 존재 확인
print_info "Step 1: 파일 구조 확인"
echo ""

FILES=(
    "docker-compose.yml"
    "docker-compose.dev.yml"
    "docker-compose.monitoring.yml"
    "docker-compose.backend.yml"
    "docker-compose.prod.yml"
    "scripts/setup-all.sh"
    "monitoring/init-monitoring.sh"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file 존재"
    else
        print_error "$file 없음"
        exit 1
    fi
done

echo ""

# 2. Docker Compose 문법 검증
print_info "Step 2: Docker Compose 문법 검증"
echo ""

CONFIGS=(
    "기본 구성:docker-compose.yml"
    "개발 환경:docker-compose.yml:docker-compose.dev.yml"
    "모니터링:docker-compose.yml:docker-compose.monitoring.yml"
    "백엔드:docker-compose.yml:docker-compose.backend.yml"
    "전체 스택:docker-compose.yml:docker-compose.dev.yml:docker-compose.backend.yml:docker-compose.monitoring.yml"
    "프로덕션:docker-compose.yml:docker-compose.prod.yml"
)

for config in "${CONFIGS[@]}"; do
    name="${config%%:*}"
    files="${config#*:}"

    # : 를 -f 로 변환
    compose_args=""
    IFS=':' read -ra FILE_ARRAY <<< "$files"
    for f in "${FILE_ARRAY[@]}"; do
        compose_args="$compose_args -f $f"
    done

    if docker compose $compose_args config > /dev/null 2>&1; then
        print_success "$name - 문법 OK"
    else
        print_error "$name - 문법 오류"
        echo "명령어: docker compose $compose_args config"
        exit 1
    fi
done

echo ""

# 3. 서비스 목록 확인
print_info "Step 3: 서비스 구성 확인"
echo ""

echo "📦 기본 구성 (docker-compose.yml):"
docker compose -f docker-compose.yml config --services | sed 's/^/  - /'

echo ""
echo "🔧 개발 환경 (+ dev.yml):"
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --services | sed 's/^/  - /'

echo ""
echo "📊 모니터링 추가 (+ monitoring.yml):"
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml config --services | sed 's/^/  - /'

echo ""
echo "⚡ 백엔드 추가 (+ backend.yml):"
docker compose -f docker-compose.yml -f docker-compose.backend.yml config --services | sed 's/^/  - /'

echo ""
echo "🚀 전체 스택:"
docker compose \
    -f docker-compose.yml \
    -f docker-compose.dev.yml \
    -f docker-compose.backend.yml \
    -f docker-compose.monitoring.yml \
    config --services | sed 's/^/  - /'

echo ""

# 4. 네트워크 확인
print_info "Step 4: 네트워크 구성 확인"
echo ""

NETWORK=$(docker compose -f docker-compose.yml config | grep "name: trading_net" || echo "")
if [ -n "$NETWORK" ]; then
    print_success "공통 네트워크 'trading_net' 설정됨"
else
    print_error "네트워크 설정 누락"
    exit 1
fi

echo ""

# 5. 볼륨 확인
print_info "Step 5: 볼륨 구성 확인"
echo ""

echo "볼륨 목록:"
docker compose \
    -f docker-compose.yml \
    -f docker-compose.monitoring.yml \
    config --volumes | sed 's/^/  - /'

echo ""

# 6. DB 초기화 스크립트 확인
print_info "Step 6: DB 자동 초기화 확인"
echo ""

if grep -q "db/init.sql:/docker-entrypoint-initdb.d/init.sql" docker-compose.yml; then
    print_success "PostgreSQL 자동 초기화 설정됨"
else
    print_error "DB 초기화 스크립트 마운트 누락"
fi

echo ""

# 7. Health Check 확인
print_info "Step 7: Health Check 확인"
echo ""

HEALTHCHECKS=$(docker compose \
    -f docker-compose.yml \
    -f docker-compose.monitoring.yml \
    -f docker-compose.backend.yml \
    config | grep -c "healthcheck:" || echo "0")

if [ "$HEALTHCHECKS" -gt 0 ]; then
    print_success "Health Check 설정됨 ($HEALTHCHECKS 개)"
else
    print_error "Health Check 없음"
fi

echo ""

# 8. 요약
print_header "검증 완료!"

echo ""
print_success "모든 Docker Compose 파일이 정상입니다!"
echo ""
echo "다음 단계:"
echo ""
echo "  1️⃣  DB + 모니터링만 테스트 (API 키 불필요):"
echo "     ${GREEN}docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d postgres loki grafana${NC}"
echo ""
echo "  2️⃣  Grafana 접속:"
echo "     ${GREEN}http://localhost:3000${NC} (admin/admin123)"
echo ""
echo "  3️⃣  PostgreSQL 접속:"
echo "     ${GREEN}docker exec -it trading-db psql -U trading -d trading${NC}"
echo ""
echo "  4️⃣  서비스 중지:"
echo "     ${GREEN}docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down${NC}"
echo ""
print_info "전체 스택 테스트: ./scripts/bot.sh dev:all (API 키 필요)"
echo ""
