# n8n 워크플로우 템플릿

이 디렉토리에는 트레이딩 봇과 n8n을 연동하기 위한 워크플로우 템플릿이 포함되어 있습니다.

## 설계 원칙

n8n은 **봇이 하지 않는 고유 가치**를 제공합니다:

- **외부 데이터 수집**: Fear & Greed, 펀딩레이트 등 (봇 외부 소스)
- **리포팅**: 일간 보고서 자동 생성
- **에스컬레이션**: 에러 감지 → 알림 → 미복구 시 인시던트 로그
- **저널링**: 거래 기록을 Notion에 자동 저장
- **헬스 모니터링**: 주기적 상태 점검

## 워크플로우 목록

### 1. daily-report.json
매일 09:00에 거래 통계를 수집하여 Discord + Notion으로 전송합니다.

**흐름:**
1. Cron 09:00 트리거
2. 봇 API에서 요약/패턴/봇 목록 수집
3. 리포트 포맷팅
4. Discord Webhook 전송 + Notion 페이지 생성

### 2. alert-escalation.json
봇 콜백 이벤트를 수신하여 에러는 에스컬레이션하고 거래는 알림합니다.

**흐름:**
1. 봇 콜백 Webhook 수신
2. event_type 분기 (error / trade)
3. error: Discord 즉시 알림 → 5분 대기 → 헬스 체크 → 미복구 시 Notion 인시던트 로그
4. trade: Discord 거래 알림

### 3. data-enrichment.json
4시간마다 외부 시장 데이터를 수집하여 봇에 전송합니다.

**흐름:**
1. Cron 4시간 트리거
2. Fear & Greed Index (alternative.me) + Binance 펀딩레이트 수집
3. 데이터 정규화
4. `POST /api/n8n/market-context`로 전송

### 4. trade-journal-notion.json
거래 콜백을 수신하여 Notion 데이터베이스에 거래 기록을 저장합니다.

**흐름:**
1. 봇 콜백 Webhook 수신
2. trade 이벤트 필터링
3. 거래 데이터 포맷팅
4. Notion API로 페이지 생성

### 5. health-monitor.json
5분마다 봇 시스템 상태를 점검하고 이상 시 알림합니다.

**흐름:**
1. Cron 5분 트리거
2. `GET /health` 호출
3. 비정상 시: 봇 상세 상태 조회 → Discord 알림 + Notion 인시던트 로그

## 설치 방법

1. n8n에 로그인합니다.
2. Workflows > Import from File을 선택합니다.
3. 원하는 JSON 파일을 업로드합니다.
4. 환경 변수를 설정합니다.

## 환경 변수

| 변수명 | 설명 | 필수 | 사용 워크플로우 |
|--------|------|------|----------------|
| `TRADING_BOT_API_URL` | API 서버 URL | ✅ | 전체 |
| `N8N_API_KEY` | n8n 전용 API 키 | ✅ | data-enrichment |
| `API_KEY` | 일반 API 키 | ✅ | daily-report, health-monitor |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 URL | ✅ | daily-report, alert-escalation, health-monitor |
| `NOTION_API_KEY` | Notion API 키 | ⬜ | daily-report, alert-escalation, trade-journal, health-monitor |
| `NOTION_DATABASE_ID` | Notion 데이터베이스 ID | ⬜ | daily-report, alert-escalation, trade-journal, health-monitor |

## API 엔드포인트

### 시그널 수신
```http
POST /api/n8n/signal
X-N8N-API-Key: <key>
Content-Type: application/json

{
  "bot_name": "btc-bot",
  "signal": "LONG",
  "source": "tradingview",
  "confidence": 0.85,
  "metadata": {
    "strategy": "rsi_divergence",
    "timeframe": "1h"
  }
}
```

### 시장 컨텍스트 수신
```http
POST /api/n8n/market-context
X-N8N-API-Key: <key>
Content-Type: application/json

{
  "fear_greed_index": 75,
  "funding_rate": 0.0003,
  "whale_alerts": [{"amount_usd": 50000000, "type": "transfer"}],
  "custom_data": {"btc_dominance": 55.2},
  "source": "n8n"
}
```

## 콜백 이벤트

봇에서 n8n으로 보내는 콜백 이벤트 (N8N_WEBHOOK_URL 설정 시 활성화):

### signal
```json
{
  "event_type": "signal",
  "bot_name": "btc-bot",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "signal": "LONG",
    "price": 50000.0,
    "confidence": 0.85
  }
}
```

### trade
```json
{
  "event_type": "trade",
  "bot_name": "btc-bot",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "action": "OPEN",
    "side": "LONG",
    "price": 50000.0,
    "quantity": 0.01
  }
}
```

### error
```json
{
  "event_type": "error",
  "bot_name": "btc-bot",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "error": "API connection failed",
    "error_type": "ConnectionError",
    "context": "fetch_market_data"
  }
}
```

### status
```json
{
  "event_type": "status",
  "bot_name": "btc-bot",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "is_running": true,
    "is_paused": false,
    "current_price": 50000.0,
    "position": {
      "side": "LONG",
      "entry_price": 49500.0
    }
  }
}
```
