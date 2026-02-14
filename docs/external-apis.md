# 외부 API 엔드포인트 레퍼런스

이 문서는 시스템이 사용하는 모든 외부 API 엔드포인트를 기록합니다.

---

## 봇 코어 (src/)

### Binance Futures API

python-binance 라이브러리(`AsyncClient`)를 통해 호출합니다.

| 용도 | 엔드포인트 | 메서드 | 인증 | 호출 위치 |
|------|-----------|--------|------|----------|
| 현재 가격 | `/fapi/v1/ticker/price` | GET | API Key | `binance.py:get_current_price()` |
| 캔들 데이터 | `/fapi/v1/klines` | GET | API Key | `binance.py:get_klines()` |
| 포지션 조회 | `/fapi/v2/positionRisk` | GET | API Key + Signature | `binance.py:get_position()` |
| 잔고 조회 | `/fapi/v2/balance` | GET | API Key + Signature | `binance.py:get_balance()` |
| 레버리지 설정 | `/fapi/v1/leverage` | POST | API Key + Signature | `binance.py:set_leverage()` |
| 마진 타입 설정 | `/fapi/v1/marginType` | POST | API Key + Signature | `binance.py:set_margin_type()` |
| 주문 생성 | `/fapi/v1/order` | POST | API Key + Signature | `binance.py:place_order()` |
| 미체결 주문 조회 | `/fapi/v1/openOrders` | GET | API Key + Signature | `binance.py:get_open_orders()` |
| 주문 취소 | `/fapi/v1/allOpenOrders` | DELETE | API Key + Signature | `binance.py:cancel_all_orders()` |

**Base URL:**
- Testnet: `https://testnet.binancefuture.com`
- Mainnet: `https://fapi.binance.com`

**Rate Limit:** 1200 req/min (가중치 기반)

**문서:** https://binance-docs.github.io/apidocs/futures/en/

---

### Google Gemini AI

google-genai 라이브러리를 통해 호출합니다.

| 용도 | 엔드포인트 | 메서드 | 인증 | 호출 위치 |
|------|-----------|--------|------|----------|
| AI 시그널 생성 | `/v1beta/models/{model}:generateContent` | POST | API Key | `gemini.py:generate_signal()` |
| AI 메모리 분석 | `/v1beta/models/{model}:generateContent` | POST | API Key | `enhanced_gemini.py:generate_signal()` |

**Base URL:** `https://generativelanguage.googleapis.com`

**모델:** `gemini-2.5-flash` (환경변수 `GEMINI_MODEL`로 변경 가능)

**Rate Limit:** 무료 — 15 RPM / 100만 토큰/일

**문서:** https://ai.google.dev/gemini-api/docs

---

### Discord Webhook

aiohttp로 직접 호출합니다.

| 용도 | 엔드포인트 | 메서드 | 인증 | 호출 위치 |
|------|-----------|--------|------|----------|
| 알림 전송 | `/api/webhooks/{id}/{token}` | POST | URL에 토큰 포함 | `main.py:send_discord_embed()` |

**Base URL:** `https://discord.com`

**Rate Limit:** 30 req/min per webhook

**문서:** https://discord.com/developers/docs/resources/webhook

---

### Discord Bot (Gateway)

discord.py 라이브러리를 통해 WebSocket 연결합니다.

| 용도 | 엔드포인트 | 프로토콜 | 인증 | 호출 위치 |
|------|-----------|---------|------|----------|
| 봇 명령 수신 | `/gateway/bot` | WebSocket | Bot Token | `discord_bot/client.py` |

**Base URL:** `wss://gateway.discord.gg`

**문서:** https://discord.com/developers/docs/topics/gateway

---

## n8n 워크플로우 (workflows/)

### Alternative.me — Fear & Greed Index

| 용도 | URL | 메서드 | 인증 | 워크플로우 |
|------|-----|--------|------|-----------|
| Fear & Greed 지수 | `https://api.alternative.me/fng/` | GET | 불필요 | data-enrichment |

**응답 예시:**
```json
{"data": [{"value": "75", "value_classification": "Greed"}]}
```

**갱신 주기:** 1일 1회

**Rate Limit:** 명시 없음 (과도한 호출 자제)

**문서:** https://alternative.me/crypto/fear-and-greed-index/#api

---

### Binance — 펀딩레이트 (공개)

| 용도 | URL | 메서드 | 인증 | 워크플로우 |
|------|-----|--------|------|-----------|
| BTCUSDT 펀딩레이트 | `https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1` | GET | 불필요 | data-enrichment |

**응답 예시:**
```json
[{"symbol": "BTCUSDT", "fundingRate": "0.00030000", "fundingTime": 1700000000000}]
```

**갱신 주기:** 8시간 (00:00, 08:00, 16:00 UTC)

**문서:** https://binance-docs.github.io/apidocs/futures/en/#get-funding-rate-history

---

### Notion API

| 용도 | URL | 메서드 | 인증 | 워크플로우 |
|------|-----|--------|------|-----------|
| 페이지 생성 | `https://api.notion.com/v1/pages` | POST | Bearer Token | daily-report, alert-escalation, trade-journal, health-monitor |

**헤더:**
```
Authorization: Bearer {NOTION_API_KEY}
Notion-Version: 2022-06-28
```

**Rate Limit:** 3 req/sec

**문서:** https://developers.notion.com/reference/post-page

---

## 내부 API (봇 ↔ n8n)

n8n이 봇 API를 호출하거나, 봇이 n8n Webhook을 호출합니다.

### n8n → 봇

| 용도 | 엔드포인트 | 메서드 | 인증 | 워크플로우 |
|------|-----------|--------|------|-----------|
| 시장 컨텍스트 전송 | `/api/n8n/market-context` | POST | X-N8N-API-Key | data-enrichment |
| 거래 요약 조회 | `/api/analytics/summary` | GET | X-API-Key | daily-report |
| 패턴 분석 조회 | `/api/analytics/patterns` | GET | X-API-Key | daily-report |
| 봇 목록 조회 | `/api/bots` | GET | X-API-Key | daily-report |
| 헬스 체크 | `/health` | GET | 불필요 | health-monitor, alert-escalation |
| 봇 상세 헬스 | `/health/bots` | GET | X-API-Key | health-monitor |

### 봇 → n8n

| 용도 | 엔드포인트 | 메서드 | 인증 | 트리거 |
|------|-----------|--------|------|--------|
| 시그널 콜백 | `{N8N_WEBHOOK_URL}` | POST | 없음 | 시그널 발생 시 |
| 거래 콜백 | `{N8N_WEBHOOK_URL}` | POST | 없음 | 거래 체결 시 |
| 에러 콜백 | `{N8N_WEBHOOK_URL}` | POST | 없음 | 에러 발생 시 |

---

## 환경변수 요약

| 변수 | 용도 | 필수 |
|------|------|------|
| `BINANCE_API_KEY` | Binance Futures API | ✅ |
| `BINANCE_SECRET_KEY` | Binance Futures 서명 | ✅ |
| `GEMINI_API_KEY` | Google Gemini AI | ✅ |
| `DISCORD_WEBHOOK_URL` | Discord 알림 | ✅ |
| `DISCORD_BOT_TOKEN` | Discord 봇 명령 | ⬜ |
| `N8N_API_KEY` | n8n ↔ 봇 인증 | ⬜ (n8n 사용 시) |
| `N8N_WEBHOOK_URL` | 봇 → n8n 콜백 | ⬜ (n8n 사용 시) |
| `NOTION_API_KEY` | Notion API | ⬜ (Notion 사용 시) |
| `NOTION_DATABASE_ID` | Notion 데이터베이스 | ⬜ (Notion 사용 시) |
