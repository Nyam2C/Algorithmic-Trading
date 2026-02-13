# Discord Bot Commands

Discord를 통한 트레이딩 봇 원격 모니터링 및 제어

---

## 설정 방법

### 1. Discord Bot 생성

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. "New Application" 클릭
3. 좌측 메뉴에서 "Bot" → "Add Bot"
4. "Reset Token"으로 토큰 복사
5. Privileged Gateway Intents에서 "MESSAGE CONTENT INTENT" 활성화

### 2. Bot 초대

1. 좌측 "OAuth2" → "URL Generator"
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Send Messages`, `Use Slash Commands`
4. 생성된 URL로 서버에 봇 초대

### 3. 환경 변수 설정

`.env` 파일에 추가:
```bash
DISCORD_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://trading:devpassword123@localhost:5432/trading
```

---

## 사용 가능한 명령어

### 📊 모니터링 명령어 (8개)

모든 명령어는 한글 전용입니다. 파일: `commands/monitoring.py`

| 명령어 | 설명 | 파라미터 |
|--------|------|----------|
| `/대시보드` | 인터랙티브 버튼 UI 대시보드 | - |
| `/상태 [봇이름?]` | 봇 상태 조회 (생략 시 전체 목록) | 봇이름 (선택) |
| `/포지션 [봇이름?]` | 현재 포지션 상세 정보 | 봇이름 (선택) |
| `/수익 [기간] [봇이름?]` | 거래 수익 리포트 | 기간: 일간/주간/월간 |
| `/내역 [개수]` | 최근 거래 내역 | 개수 (기본 5, 최대 10) |
| `/계정` | 계정 잔고 및 전체 포지션 | - |
| `/프롬프트 [봇이름?]` | 마지막 AI 프롬프트 및 응답 | 봇이름 (선택) |
| `/핑` | 봇 응답 확인 | - |

---

### 🎮 제어 명령어 (3개)

권한 레벨에 따라 접근이 제한됩니다. 파일: `commands/control.py`

| 명령어 | 설명 | 권한 |
|--------|------|------|
| `/제어 <대상> <동작>` | 봇 시작/정지/일시정지/재개 | 시작/정지: ADMIN, 일시정지/재개: TRADER |
| `/긴급청산 <대상>` | 포지션 즉시 시장가 청산 + 봇 정지 | ADMIN |
| `/알림 [유형] [설정]` | 알림 설정 관리 (진입/청산/일간/에러) | TRADER |

**대상**: 봇 이름 또는 "전체"



---

## 대시보드 UI

`/대시보드` 명령어로 인터랙티브 대시보드를 표시합니다.

```
┌────────────────────────────────────────────┐
│  🤖 트레이딩 봇 대시보드                     │
│                                            │
│  상태: ✅ 실행 중 | 가격: $95,123.45        │
│  포지션: 🟢 LONG @ $94,800.00              │
│  마지막 신호: LONG (5분 전)                 │
│                                            │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │📊 상태 │ │📍포지션│ │📈 통계 │ │📜 내역 ││
│  └────────┘ └────────┘ └────────┘ └────────┘│
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │⏸️ 일시정지│ │▶️ 재시작 │ │🚨긴급청산│    │
│  └──────────┘ └──────────┘ └──────────┘    │
└────────────────────────────────────────────┘
```

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DISCORD_BOT_TOKEN` | Discord 봇 토큰 | (필수) |
| `DATABASE_URL` | PostgreSQL 연결 문자열 | (필수) |

---

## PostgreSQL 데이터베이스

거래 기록은 PostgreSQL에 저장됩니다.

### Docker로 실행 (권장)

```bash
docker run -d \
  --name postgres-trading \
  -e POSTGRES_PASSWORD=devpassword123 \
  -e POSTGRES_DB=trading_bot \
  -p 5432:5432 \
  postgres:15
```

### 테이블 스키마

`trades` 테이블이 자동으로 생성됩니다:
- 진입/청산 정보
- PnL 데이터
- 전략 파라미터 (RSI, MA, Volume)
- 타임스탬프

---

## 보안 고려사항

### 권한 제어
- 특정 채널에서만 명령어 허용 가능
- 특정 사용자만 제어 명령어 실행 가능
- Rate limiting (권장: 1분에 10회)

### 민감 정보 보호
- API 키는 환경 변수로 관리
- 봇 토큰 노출 주의
- 프로덕션 환경에서는 HTTPS 사용

---

## 문제 해결

### 봇이 응답하지 않음
1. Discord Bot Token 확인
2. Bot이 서버에 초대되었는지 확인
3. Bot이 slash command 권한을 가지고 있는지 확인
4. 로그 확인: `logs/bot_output.log`

### 데이터베이스 연결 오류
1. PostgreSQL이 실행 중인지 확인: `docker ps | grep postgres`
2. DATABASE_URL이 올바른지 확인
3. 데이터베이스가 생성되었는지 확인

### 명령어가 표시되지 않음
1. Bot을 재시작하여 명령어 sync
2. Discord 앱을 재시작
3. 서버 설정에서 Bot의 권한 확인

---

## 관련 문서

- [../api/README.md](../api/README.md) - REST API 문서
- [../../docs/SETUP_GUIDE.md](../../docs/SETUP_GUIDE.md) - 설정 가이드
- [../../db/README.md](../../db/README.md) - 데이터베이스 스키마

---

**버전:** 2.0
**마지막 업데이트:** 2026-02-14
