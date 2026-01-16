#!/bin/bash
# ===========================================
# 빠른 테스트 - DB + 모니터링만
# ===========================================
# API 키 없이도 실행 가능

set -e

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

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

cd "$(dirname "$0")/.."

print_header "빠른 테스트 (API 키 불필요)"

print_info "시작하는 서비스:"
echo "  - PostgreSQL (DB)"
echo "  - Loki (로그 저장소)"
echo "  - Grafana (대시보드)"
echo ""

# Docker Compose 실행
print_info "서비스 시작 중..."
docker compose \
    -f docker-compose.yml \
    -f docker-compose.monitoring.yml \
    up -d postgres loki grafana promtail

echo ""
print_info "서비스 시작 대기 중 (30초)..."
sleep 10

# PostgreSQL Health Check
print_info "PostgreSQL 확인 중..."
for i in {1..10}; do
    if docker exec trading-db pg_isready -U trading > /dev/null 2>&1; then
        print_success "PostgreSQL 준비 완료"
        break
    fi
    echo "  대기 중... ($i/10)"
    sleep 2
done

# Grafana Health Check
print_info "Grafana 확인 중..."
for i in {1..10}; do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "Grafana 준비 완료"
        break
    fi
    echo "  대기 중... ($i/10)"
    sleep 2
done

# Loki Health Check
print_info "Loki 확인 중..."
for i in {1..10}; do
    if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
        print_success "Loki 준비 완료"
        break
    fi
    echo "  대기 중... ($i/10)"
    sleep 2
done

echo ""
print_header "테스트 성공!"

echo ""
print_success "모든 서비스가 정상 작동 중입니다!"
echo ""
echo "📊 Grafana 대시보드:"
echo "   URL: ${GREEN}http://localhost:3000${NC}"
echo "   ID:  ${GREEN}admin${NC}"
echo "   PW:  ${GREEN}admin123${NC}"
echo ""
echo "🗄️  PostgreSQL 접속:"
echo "   ${GREEN}docker exec -it trading-db psql -U trading -d trading${NC}"
echo ""
echo "📝 데이터베이스 테이블 확인:"
echo "   ${GREEN}docker exec -it trading-db psql -U trading -d trading -c '\\dt'${NC}"
echo ""
echo "🔍 Loki 상태:"
echo "   ${GREEN}curl http://localhost:3100/ready${NC}"
echo ""
echo "📋 실행 중인 컨테이너:"
docker ps --filter "name=trading" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "🛑 테스트 종료:"
echo "   ${GREEN}docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down${NC}"
echo ""
