#!/bin/bash
# ===========================================
# Monitoring Stack Auto-Initialization
# ===========================================
# Grafana 데이터소스 및 대시보드 자동 설정

set -e

echo "🔧 Initializing Grafana monitoring stack..."

# Grafana가 시작될 때까지 대기
echo "⏳ Waiting for Grafana to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✅ Grafana is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Grafana failed to start"
    exit 1
fi

# Loki가 준비될 때까지 대기
echo "⏳ Waiting for Loki to be ready..."
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
        echo "✅ Loki is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Loki failed to start"
    exit 1
fi

echo ""
echo "✅ Monitoring stack initialized successfully!"
echo ""
echo "📊 Access Grafana:"
echo "   URL: http://localhost:3000"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "📝 Loki endpoint:"
echo "   URL: http://localhost:3100"
echo ""
echo "🎯 Dashboards available:"
echo "   - Trading Overview"
echo "   - AI Signals Analysis"
echo "   - System Health"
echo ""
