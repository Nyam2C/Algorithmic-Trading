# Discord Bot Commands

Discord를 통한 트레이딩 봇 원격 모니터링 및 제어

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

## 사용 가능한 명령어

### 📊 모니터링 명령어

#### `/status` - 봇 상태 확인
현재 봇의 실행 상태와 포지션 요약을 확인합니다.

**응답 내용:**
- 봇 실행 상태 (Running/Stopped)
- Uptime
- 현재 가격
- 현재 포지션 (있을 경우)
- 마지막 신호

#### `/position` - 현재 포지션 상세
현재 열려있는 포지션의 상세 정보를 확인합니다.

**응답 내용:**
- 포지션 방향 (LONG/SHORT)
- 진입 가격 및 사이즈
- TP/SL 가격
- 타임컷 남은 시간
- 현재 PnL (USD 및 %)

#### `/stats [hours]` - 거래 통계
지정한 시간 동안의 거래 통계를 확인합니다.

**파라미터:**
- `hours` (선택): 조회 기간 (기본값: 24시간)

**응답 내용:**
- 총 거래 수
- 승률 (승리/패배)
- 총 손익
- 최고/최악 거래
- LONG/SHORT 비율

#### `/history [count]` - 최근 거래 내역
최근 완료된 거래 내역을 확인합니다.

**파라미터:**
- `count` (선택): 조회할 거래 수 (기본값: 5, 최대: 10)

**응답 내용:**
- 각 거래의 진입/청산 가격
- 청산 이유 (TP/SL/TIMECUT)
- PnL (USD 및 %)
- 거래 시간

### 🎮 제어 명령어

#### `/stop` - 봇 일시 정지
새로운 포지션 진입을 중지합니다.

**기능:**
- 새 포지션 진입 차단
- 기존 포지션은 유지 (TP/SL 작동)
- 재시작 전까지 WAIT 신호만 생성

**주의:** 기존 포지션은 자동으로 관리됩니다.

#### `/start` - 봇 재시작
일시 정지된 봇을 재시작합니다.

**기능:**
- 일시 정지 해제
- 정상 거래 재개
- 일시 정지 기간 표시

#### `/emergency` - 긴급 청산
현재 포지션을 즉시 Market 가격으로 청산하고 봇을 정지합니다.

**기능:**
- 현재 포지션 Market 청산
- 봇 자동 일시 정지
- 긴급 상황 대응용

**주의:** 신중하게 사용하세요. Market 가격으로 즉시 청산됩니다.

### 🔧 유틸리티

#### `/ping` - 응답 확인
봇이 정상적으로 응답하는지 확인합니다.

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

## 보안 고려사항

### 권한 제어
- 특정 채널에서만 명령어 허용 가능
- 특정 사용자만 제어 명령어 실행 가능
- Rate limiting (권장: 1분에 10회)

### 민감 정보 보호
- API 키는 환경 변수로 관리
- 봇 토큰 노출 주의
- 프로덕션 환경에서는 HTTPS 사용

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

## 다음 단계

- [ ] 권한 시스템 추가 (특정 사용자만 제어 가능)
- [ ] Rate limiting 구현
- [ ] 실시간 알림 개선
- [ ] 대시보드 추가 (웹 UI)
