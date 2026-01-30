# n8n 워크플로우 템플릿

이 디렉토리에는 트레이딩 봇과 n8n을 연동하기 위한 워크플로우 템플릿이 포함되어 있습니다.

## 워크플로우 목록

### 1. tradingview-signal.json
TradingView 알림을 받아 봇에 시그널을 전송하는 워크플로우입니다.

**흐름:**
1. TradingView Webhook 수신
2. 시그널 파싱 (LONG/SHORT/WAIT)
3. API 시그널 전송 (`POST /api/n8n/signal`)
4. Discord 알림 (선택)

### 2. telegram-control.json
Telegram 봇 명령을 받아 트레이딩 봇을 제어하는 워크플로우입니다.

**지원 명령:**
- `/start [bot_name]` - 봇 시작
- `/stop [bot_name]` - 봇 정지
- `/pause [bot_name]` - 봇 일시정지
- `/resume [bot_name]` - 봇 재개
- `/status` - 전체 상태 조회
- `/emergency` - 긴급 청산

### 3. daily-report.json
매일 거래 통계를 생성하여 이메일/Slack으로 전송하는 워크플로우입니다.

**기능:**
- 24시간 거래 통계 수집
- PnL 요약 생성
- 이메일/Slack 알림

## 설치 방법

1. n8n에 로그인합니다.
2. Workflows > Import from File을 선택합니다.
3. 원하는 JSON 파일을 업로드합니다.
4. 환경 변수를 설정합니다:
   - `TRADING_BOT_API_URL`: API 서버 URL (예: `http://localhost:8000`)
   - `API_KEY`: API 인증 키 (설정한 경우)

## 환경 변수

워크플로우에서 사용하는 환경 변수:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `TRADING_BOT_API_URL` | API 서버 URL | `http://localhost:8000` |
| `API_KEY` | API 인증 키 | `your-api-key` |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 URL | `https://discord.com/api/webhooks/...` |
| `TELEGRAM_BOT_TOKEN` | Telegram 봇 토큰 | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Telegram 채팅 ID | `-1001234567890` |

## API 엔드포인트

### 시그널 수신
```http
POST /api/n8n/signal
Content-Type: application/json

{
  "bot_name": "btc-bot",          // 선택, 없으면 전체 봇
  "signal": "LONG",               // LONG, SHORT, WAIT, CLOSE
  "source": "tradingview",        // 시그널 소스
  "confidence": 0.85,             // 신뢰도 (0-1)
  "metadata": {                   // 선택
    "strategy": "rsi_divergence",
    "timeframe": "1h"
  }
}
```

### 명령 수신
```http
POST /api/n8n/command
Content-Type: application/json

{
  "bot_name": "btc-bot",          // 선택, 없으면 전체 봇
  "command": "start",             // start, stop, pause, resume, emergency_close
  "parameters": {}                // 선택
}
```

## 콜백 이벤트

봇에서 n8n으로 보내는 콜백 이벤트:

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
