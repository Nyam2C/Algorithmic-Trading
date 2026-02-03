# High-Win Survival System

Binance Futures + Gemini AI 기반 비트코인 선물 자동매매 시스템

---

## 🎯 프로젝트 개요

**High-Win Survival System**은 24시간 무인 운영이 가능한 비트코인 선물 자동매매 봇입니다.

### 핵심 철학
- **생존 우선**: 수익보다 자본 보존을 우선시합니다
- **승률 우선**: 불확실한 시장에서는 진입하지 않습니다
- **기계적 실행**: 감정 없이 규칙대로 매매합니다

### 시스템이 제공하는 것

**1. AI 기반 자동매매**
- Gemini AI와 기술적 지표(RSI, MA, ATR)를 결합한 매매 시그널 생성
- 과거 거래 성과를 학습하여 AI 판단에 반영하는 메모리 시스템

**2. 철저한 리스크 관리**
- 일일 손실 -5% 도달 시 자동 거래 정지
- 3연패 시 30분 쿨다운으로 감정적 거래 방지
- 최대 드로다운 10% 모니터링

**3. 시장 상황 인식**
- 마켓 레짐 감지: 상승/하락/횡보장 구분, 횡보장에서는 진입 회피
- 다중 타임프레임 분석: 상위 타임프레임과 충돌하는 시그널 필터링

**4. 멀티봇 운영**
- 여러 봇을 동시에 관리 (BTC, ETH 등 심볼별 또는 전략별)
- 봇별 위험도 설정 (보수적/중간/공격적)
- REST API로 봇 생성/삭제/제어

**5. 24/7 원격 제어 (Discord)**
- 대시보드, 상태, 포지션, 통계 조회
- 일시정지, 재시작, 긴급청산 원격 명령
- 거래 진입/청산 실시간 알림

**6. 실시간 모니터링**
- Prometheus 메트릭 + Grafana 대시보드
- 거래 수, PnL, API 지연시간 등 시각화

**7. 프로덕션 안전장치**
- 수동 승인 모드: 프로덕션 전환 시 첫 N거래 수동 확인
- 메인넷 전환 시 별도 확인 플래그 필수
- 모든 거래 및 봇 이벤트 감사 로그 기록

**8. 전략 검증**
- 백테스트 엔진으로 과거 데이터 시뮬레이션
- 승률, 총손익, 최대 드로다운 등 성과 분석

---

## 🚀 빠른 시작

```bash
# 1. 환경 설정 (최초 1회)
./scripts/setup.sh

# 2. 서비스 시작
./scripts/start.sh

# 3. 상태 확인
./scripts/start.sh --status

# 4. 로그 보기
./scripts/start.sh --logs
```

**자세한 설정 가이드**: [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

---

### 스크립트 사용법

| 스크립트 | 용도 |
|----------|------|
| `./scripts/setup.sh` | 전체 환경 설정 (최초 1회) |
| `./scripts/start.sh` | Docker 서비스 관리 |
| `./scripts/stop.sh` | Docker 서비스 중지 |
| `./scripts/test.sh` | CI 테스트 |

```bash
# 서비스 관리
./scripts/start.sh              # 시작
./scripts/start.sh --stop       # 중지
./scripts/start.sh --logs       # 로그 보기
./scripts/start.sh --status     # 상태 확인

# 테스트
./scripts/test.sh               # 빠른 테스트
./scripts/test.sh --coverage    # 커버리지 포함
./scripts/test.sh --ci          # CI 환경 (lint + type + coverage)
```

**서비스 종료:**
```bash
./scripts/start.sh --stop
```

---

## ⚙️ 사전 준비

### 시스템 요구사항

- **Python 3.11+** (필수)
- **Docker & Docker Compose** (Docker 실행 시 필수)
- **Git** (선택)

### 필수 API 키 발급

실행 전에 다음 API 키를 발급받아 `.env` 파일에 입력해야 합니다:

#### 1. Binance Testnet API 키
- 🔗 https://testnet.binancefuture.com
- 계정 생성 후 **API Management**에서 API 키 생성
- **권한**: 선물 거래 활성화 (출금 권한 비활성화)

#### 2. Gemini AI API 키
- 🔗 https://aistudio.google.com/apikey
- Google 계정으로 로그인
- **Create API Key** 클릭

#### 3. Discord Webhook URL
- Discord 서버 설정 > **연동** > **웹후크**
- 새 웹후크 생성 후 URL 복사

#### 4. Discord Bot Token (선택사항)
- 🔗 https://discord.com/developers/applications
- **New Application** 클릭 후 봇 생성
- **Bot** 메뉴에서 **Add Bot** 클릭
- **Reset Token** 클릭하여 토큰 복사
- **OAuth2** > **URL Generator**에서 `bot`, `applications.commands` 권한 선택
- 생성된 URL로 서버에 봇 초대

### .env 파일 설정

처음 실행하면 `.env.example`이 자동으로 복사되어 `.env` 파일이 생성됩니다.

```bash
# Binance Testnet
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_SECRET_KEY=your_actual_secret_key_here

# Gemini AI
GEMINI_API_KEY=your_actual_gemini_key_here

# Discord Webhook (알림용)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Discord Bot (원격 제어용 - 선택사항)
DISCORD_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:password@localhost:5432/trading
```

---

## 📦 프로젝트 구조

```
Algorithmic-Trading/
├── src/                          # 소스 코드
│   ├── config.py                 # 설정 관리
│   ├── main.py                   # 메인 실행 파일
│   ├── bot_config.py             # 멀티봇 설정 모델
│   ├── bot_instance.py           # 개별 봇 인스턴스
│   ├── bot_manager.py            # 멀티봇 관리자
│   ├── api/                      # REST API
│   │   ├── main.py               # FastAPI 앱 팩토리
│   │   └── routes/               # API 라우터
│   ├── analytics/                # 거래 분석
│   │   ├── trade_analyzer.py     # 거래 이력 분석기
│   │   └── memory_context.py     # AI 메모리 컨텍스트
│   ├── ai/                       # AI 신호 생성
│   │   ├── gemini.py             # Gemini AI 클라이언트
│   │   ├── enhanced_gemini.py    # 메모리 주입 Gemini
│   │   ├── rule_based.py         # 규칙 기반 신호
│   │   ├── signals.py            # 신호 파싱
│   │   └── prompts/              # AI 프롬프트
│   ├── backtest/                 # 백테스트 프레임워크
│   │   └── engine.py             # 백테스트 엔진
│   ├── data/                     # 데이터 처리
│   │   ├── indicators.py         # 기술적 지표 (RSI, MA, ATR)
│   │   ├── regime_detector.py    # 마켓 레짐 감지
│   │   └── multi_timeframe.py    # 다중 타임프레임 분석
│   ├── exchange/                 # 거래소 API
│   │   └── binance.py            # Binance Testnet 클라이언트
│   ├── metrics/                  # 모니터링 메트릭
│   │   └── prometheus.py         # Prometheus 메트릭
│   ├── storage/                  # 데이터 저장
│   │   ├── trade_history.py      # PostgreSQL 거래 기록
│   │   ├── redis_state.py        # Redis 상태 관리
│   │   └── audit_log.py          # 감사 로그
│   ├── trading/                  # 주문 실행
│   │   ├── executor.py           # 주문 실행
│   │   ├── risk_manager.py       # 리스크 관리
│   │   └── trade_approval.py     # 수동 승인 시스템
│   ├── discord_bot/              # Discord 봇
│   │   └── bot.py                # 원격 제어 UI
│   └── utils/                    # 유틸리티
│       ├── retry.py              # 재시도 데코레이터
│       └── logging.py            # JSON 구조화 로깅
├── tests/                        # 테스트 (481개, 65% 커버리지)
├── deploy/                       # 🐳 Docker 배포
│   ├── docker-compose.yml        # 통합 서비스 (Bot + API)
│   ├── docker-compose.dev.yml    # 개발 환경
│   └── docker-compose.monitoring.yml # 모니터링
├── docs/                         # 📚 문서
├── db/                           # 🗄️ 데이터베이스
│   ├── init.sql                  # 초기 스키마
│   └── migrations/               # 마이그레이션
│       ├── 001_multi_bot.sql     # 멀티봇 지원
│       ├── 002_analytics_views.sql # 분석용 뷰
│       └── 003_audit_logs.sql    # 감사 로그
├── scripts/                      # 🔧 실행 스크립트
├── .claude/                      # 개발 계획 문서
├── requirements.txt              # Python 의존성
├── .env.example                  # 환경 변수 템플릿
└── README.md                     # 이 파일
```

---

## 🤖 시스템 동작 방식

### 1. 데이터 수집
- Binance Testnet에서 BTCUSDT 현재가, 캔들 데이터 수집
- 5분봉 24개 (2시간 데이터)

### 2. 기술적 지표 계산
- **RSI (14)**: 과매수/과매도 판단
- **MA (7, 25, 99)**: 추세 방향
- **ATR (14)**: 변동성 측정
- **Volume**: 거래량 분석

### 3. AI 신호 생성
- Gemini 2.0 Flash 모델 사용
- 출력: `LONG` / `SHORT` / `WAIT`
- 승률 우선 전략 (불확실하면 WAIT)

### 4. 주문 실행
- **진입**: 시장가 주문
- **익절/손절**: ±0.4% (15배 레버리지 기준 ±6% ROE)
- **레버리지**: 15배 (격리 모드)
- **포지션 크기**: 시드의 5%

### 5. Discord 알림 & 봇 제어
- 봇 시작/중지 알림
- 진입/청산 알림 (Embed 형식)
- 에러 발생 알림
- **Discord 봇 UI** (선택사항):
  - `/대시보드` - 인터랙티브 버튼 UI로 빠른 조회
  - `/상태`, `/포지션`, `/통계`, `/내역` - 실시간 정보 조회
  - `/일시정지`, `/재시작`, `/긴급청산` - 원격 봇 제어
  - 한글 및 영어 명령어 모두 지원

---

## 🎮 Discord 봇 제어 (선택사항)

Discord 봇을 설정하면 채팅으로 봇을 원격 제어할 수 있습니다.

### 📊 대시보드 (추천)

```
/대시보드
```

버튼 UI가 표시되며 한 번의 클릭으로 모든 정보에 접근할 수 있습니다:

```
┌─────────────────────────────────────────┐
│  🤖 트레이딩 봇 대시보드                  │
│                                         │
│  상태: 실행 중 | 가격: $43,250          │
│  포지션: 🟢 LONG @ $43,100             │
│  마지막 신호: LONG (2분 전)             │
└─────────────────────────────────────────┘

[📊 상태] [📍 포지션] [📈 통계] [📜 내역]
[⏸️ 일시정지]  [▶️ 재시작]   [🚨 긴급청산]
```

### 💬 명령어 목록

#### 정보 조회
| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/상태` | 봇 실행 상태 및 포지션 요약 | 가동시간, 현재가, 포지션 |
| `/포지션` | 현재 포지션 상세 정보 | 진입가, TP/SL, PnL, 타임컷 |
| `/통계` | 거래 통계 (기본 24시간) | 승률, 총 PnL, 최고/최악 거래 |
| `/내역` | 최근 거래 내역 (기본 5개) | 진입/청산가, PnL, 시간 |

#### 봇 제어 (확인 필요)
| 명령어 | 설명 | 효과 |
|--------|------|------|
| `/일시정지` | 봇 일시 정지 | 새 포지션 진입 중지, 기존 포지션 유지 |
| `/재시작` | 봇 재시작 | 정상 거래 재개 |
| `/긴급청산` | 긴급 포지션 청산 | 현재 포지션 즉시 시장가 청산 + 봇 정지 |

**참고**: 제어 명령어는 확인 대화상자가 표시되며, "예" 클릭 시에만 실행됩니다.

### 🌐 영어 명령어

모든 명령어는 한글과 영어를 모두 지원합니다:
- `/dashboard` (대시보드)
- `/status` (상태)
- `/position` (포지션)
- `/stats` (통계)
- `/history` (내역)
- `/stop` (일시정지)
- `/start` (재시작)
- `/emergency` (긴급청산)

---

## 📊 트레이딩 파라미터

| 항목 | 설정값 | 비고 |
|------|--------|------|
| 심볼 | BTCUSDT | 비트코인/USDT 선물 |
| 레버리지 | 15배 (격리) | 청산가 거리 6.7% |
| 진입 비중 | 5% | 시드의 5% |
| 익절 | +0.4% | ROE +6.0% |
| 손절 | -0.4% | ROE -6.0% |
| 타임컷 | 2시간 | 구현 완료 |
| 루프 주기 | 5분 | 300초 간격 |

---

## 🧪 테스트

### 테스트 실행

**전체 테스트 스위트 (355개 테스트)**

```bash
# 빠른 테스트
./scripts/test.sh

# 커버리지 포함
./scripts/test.sh --coverage

# CI 환경 (lint + type + coverage)
./scripts/test.sh --ci

# 커버리지 리포트 확인
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

**테스트 커버리지**: 65%+ (src/ 모듈)

자세한 테스트 가이드: [TEST_GUIDE.md](docs/TEST_GUIDE.md)

---

### Import 테스트
```bash
python -c "from src.config import get_config; print('✓ Config OK')"
python -c "from src.exchange.binance import BinanceTestnetClient; print('✓ Binance OK')"
python -c "from src.ai.gemini import GeminiSignalGenerator; print('✓ Gemini OK')"
```

### 전체 플로우 테스트
```bash
python -m src.main
```

**예상 동작:**
1. Discord에 봇 시작 알림 수신 ✅
2. 5분마다 시장 데이터 수집 및 분석 ✅
3. Gemini AI 신호 생성 (LONG/SHORT/WAIT) ✅
4. 신호에 따라 포지션 진입 ✅
5. 기존 포지션 TP/SL 체크 및 청산 ✅

---

## 🛠️ 트러블슈팅

### API 키 에러
```
[ERROR] 다음 API 키가 설정되지 않았습니다: BINANCE_API_KEY
```
**해결**: `.env` 파일에 올바른 API 키 입력

### Import 에러
```
ModuleNotFoundError: No module named 'src'
```
**해결**: 프로젝트 루트 디렉토리에서 실행
```bash
cd /path/to/Algorithmic-Trading
python -m src.main
```

### Binance API 에러
```
binance.exceptions.BinanceAPIException: Invalid API-key
```
**해결**: Testnet API 키가 맞는지 확인 (실전 API 키와 다름)

### Gemini API 에러
```
google.genai.errors.APIError: API key not valid
```
**해결**: Gemini API 키 재발급 또는 갱신

---

## 📊 모니터링 (Grafana + Loki)

모니터링은 `./scripts/start.sh` 실행 시 자동으로 시작됩니다.

### Grafana 접속

```
URL: http://localhost:3000
ID: admin
PW: admin123
```

### 대시보드

모니터링 시스템에는 3개의 대시보드가 포함되어 있습니다:

1. **Trading Overview** - 전체 거래 현황
2. **AI Signals** - AI 신호 분석
3. **System Health** - 시스템 상태

### 서비스 상태 확인

```bash
./scripts/start.sh --status    # 전체 상태 확인
./scripts/start.sh --logs      # 로그 스트리밍
```

**자세한 가이드**: [monitoring/README.md](monitoring/README.md)

---

## 🔧 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 거래소 | Binance Futures API (Testnet/Mainnet) |
| AI | Google Gemini 2.0 Flash |
| DB | PostgreSQL + Redis |
| API | FastAPI |
| 모니터링 | Prometheus + Grafana + Loki |
| 알림/제어 | Discord Bot |
| 컨테이너 | Docker Compose |
| 테스트 | pytest (481개 테스트, 65% 커버리지) |

---

## 📚 관련 문서

### 📖 사용자 가이드

문서는 [docs/](docs/) 폴더에 있습니다:

- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** - 환경 설정 완벽 가이드
- **[TEST_GUIDE.md](docs/TEST_GUIDE.md)** - 테스트 실행 및 작성 가이드
- **[README.md](README.md)** - 프로젝트 개요 (현재 문서)

### 개발 계획 문서 (.claude/)

프로젝트의 상세한 계획 문서는 `.claude/` 폴더에 있습니다:

- **TRADING_PLAN.md** - 트레이딩 전략 상세
- **DEVELOPMENT_PLAN.md** - 개발 계획 및 아키텍처
- **IMPLEMENTATION_PLAN.md** - 스프린트별 구현 계획
- **PROMPT_ENGINEERING.md** - Gemini AI 프롬프트 설계

---

## ⚠️ 주의사항

- 현재는 **Binance Testnet** 모드입니다 (실제 자금 없음)
- 메인넷 전환 시 MAINNET_CONFIRMATION 환경변수 필요
- 실전 전 충분한 Testnet 검증 필수 (50회 이상 거래)
- API 키는 절대 Git에 커밋하지 마세요 (`.env`는 `.gitignore`에 포함)

---

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. Python 버전 3.8 이상
2. 모든 API 키가 올바르게 설정됨
3. 인터넷 연결 정상
4. Binance Testnet 서버 정상 작동 여부

---

**마지막 업데이트**: 2026-02-03
