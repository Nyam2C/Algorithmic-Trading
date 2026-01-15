# High-Win Survival System

**Sprint 1: Paper Trading MVP**

Binance Testnet + Gemini AI 기반 비트코인 선물 자동매매 시스템

---

## 🎯 프로젝트 개요

- **목표**: 높은 승률 기반의 초단기 비트코인 선물 자동매매
- **철학**: 승률 우선, 노이즈 회피, 기계적 실행
- **현재 단계**: Sprint 1 - Binance Testnet 모의투자

---

## 🚀 빠른 시작

### 환경 설정 (최초 1회)

```bash
# 올인원 CLI (권장 ⭐)
./scripts/bot.sh setup           # 환경 설정
./scripts/bot.sh docker          # Docker 실행
./scripts/bot.sh test            # 테스트
./scripts/bot.sh help            # 도움말

### 개별 스크립트
./scripts/setup.sh               # 환경 설정

**자동으로 하는 일:**
- ✅ Python 3.11+ 버전 확인
- ✅ Python 의존성 설치
- ✅ .env 파일 생성 (대화형)
- ✅ Docker 환경 설정
- ✅ 데이터베이스 초기화
- ✅ 테스트 실행 (64개 테스트)

**자세한 설정 가이드**: [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

---

### 방법 1: Docker로 실행 (권장 ⭐)

**한 줄로 모든 것을 자동화!**

```bash
# Python 스크립트 (Windows/Linux/Mac)
./scripts/bot.sh docker

# 또는 Bash 스크립트 (Linux/Mac)
./scripts/bot.sh docker
```

**자동으로 하는 일:**
- ✅ Docker 설치 확인
- ✅ .env 파일 생성 및 검증
- ✅ Docker 이미지 빌드
- ✅ PostgreSQL + Trading Bot 컨테이너 실행
- ✅ 실시간 로그 표시

**종료:**
```bash
docker compose down
```

---

### 방법 2: 로컬에서 직접 실행

```bash
# Python 스크립트 (의존성 자동 설치)
./scripts/bot.sh run

# 또는 Bash 스크립트 (Linux/Mac)
./scripts/bot.sh run

# 또는 직접 실행
pip install -r requirements.txt
python -m src.main
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

### .env 파일 설정

처음 실행하면 `.env.example`이 자동으로 복사되어 `.env` 파일이 생성됩니다.

```bash
# Binance Testnet
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_SECRET_KEY=your_actual_secret_key_here

# Gemini AI
GEMINI_API_KEY=your_actual_gemini_key_here

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url
```

---

## 📦 프로젝트 구조

```
Algorithmic-Trading/
├── src/                          # 소스 코드
│   ├── config.py                 # 설정 관리
│   ├── main.py                   # 메인 실행 파일
│   ├── exchange/
│   │   └── binance.py            # Binance Testnet 클라이언트
│   ├── data/
│   │   └── indicators.py         # 기술적 지표 (RSI, MA, ATR)
│   ├── ai/
│   │   ├── prompts/              # AI 프롬프트
│   │   │   ├── system.txt        # 시스템 프롬프트
│   │   │   └── analysis.txt      # 분석 프롬프트
│   │   ├── gemini.py             # Gemini AI 클라이언트
│   │   └── signals.py            # 신호 파싱
│   └── trading/
│       └── executor.py           # 주문 실행
├── tests/                        # 테스트 (64개, 94% 커버리지)
│   ├── conftest.py               # Pytest 설정
│   ├── test_config.py
│   ├── test_indicators.py
│   ├── test_signals.py
│   └── test_executor.py
├── docs/                         # 📚 문서
│   ├── README.md                 # 문서 목록
│   ├── SETUP_GUIDE.md            # 환경 설정 가이드
│   ├── TEST_GUIDE.md             # 테스트 가이드
│   └── QUICK_START.md            # 명령어 치트시트
├── db/                           # 🗄️ 데이터베이스
│   ├── README.md                 # DB 문서
│   ├── init.sql                  # 스키마 정의
│   └── setup.sh                  # DB 초기화 스크립트
├── scripts/                      # 🔧 실행 스크립트
│   ├── bot.sh                    # ⭐ 올인원 CLI (권장)
│   ├── setup.sh                  # 환경 설정
│   ├── run.sh                    # 로컬 실행
│   ├── start-docker.sh           # Docker 실행
│   └── run-tests.sh              # 테스트 실행
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
- **진입**: 시장가 주문 (Sprint 1 단순화)
- **익절/손절**: ±0.4% (15배 레버리지 기준 ±6% ROE)
- **레버리지**: 15배 (격리 모드)
- **포지션 크기**: 시드의 5%

### 5. Discord 알림
- 봇 시작/중지 알림
- 진입/청산 알림 (Embed 형식)
- 에러 발생 알림

---

## 📊 트레이딩 파라미터

| 항목 | 설정값 | 비고 |
|------|--------|------|
| 심볼 | BTCUSDT | 비트코인/USDT 선물 |
| 레버리지 | 15배 (격리) | 청산가 거리 6.7% |
| 진입 비중 | 5% | 시드의 5% |
| 익절 | +0.4% | ROE +6.0% |
| 손절 | -0.4% | ROE -6.0% |
| 타임컷 | 2시간 | Sprint 2에서 구현 예정 |
| 루프 주기 | 5분 | 300초 간격 |

---

## 🧪 테스트

### 테스트 실행

**전체 테스트 스위트 (64개 테스트)**

```bash
# Bash 스크립트 (권장)
./scripts/run-tests.sh

# 또는 직접 pytest 실행
pytest

# 커버리지 리포트 확인
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

**테스트 커버리지**: 94%+ (src/ 모듈)

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

## 📝 Sprint 1 완료 체크리스트

- [x] ✅ src/config.py - 설정 관리
- [x] ✅ src/exchange/binance.py - Binance Testnet 클라이언트
- [x] ✅ src/data/indicators.py - 기술적 지표 계산
- [x] ✅ src/ai/gemini.py - Gemini AI 클라이언트
- [x] ✅ src/ai/signals.py - 신호 파싱
- [x] ✅ src/trading/executor.py - 주문 실행
- [x] ✅ src/main.py - 메인 루프 통합
- [x] ✅ run.py / run.sh - 통합 실행 스크립트
- [x] ✅ setup.py / setup.sh - 환경 설정 스크립트
- [x] ✅ tests/ - 테스트 스위트 (64개 테스트, 94% 커버리지)
- [x] ✅ db/init.sql - 데이터베이스 스키마
- [x] ✅ SETUP_GUIDE.md - 환경 설정 가이드
- [x] ✅ TEST_GUIDE.md - 테스트 가이드

### 실행 테스트 체크리스트
- [ ] Binance Testnet 데이터 수집 확인
- [ ] Gemini AI 신호 생성 확인 (LONG/SHORT/WAIT)
- [ ] Testnet 주문 생성 확인
- [ ] Discord 알림 수신 확인
- [ ] 3회 이상 정상 실행 확인

---

## 🔜 다음 단계 (Sprint 2)

Sprint 1이 완료되면 다음 기능을 추가합니다:

- [ ] **Maker 지정가 주문** - 수수료 0.02% (vs 시장가 0.05%)
- [ ] **타임컷 모니터링** - 2시간 후 자동 청산
- [ ] **조건부 타임컷** - 수익 +0.1% 시 30분 연장
- [ ] **DB 거래 기록** - PostgreSQL에 거래 내역 저장
- [ ] **24시간 무인 운영** - 안정화 및 에러 핸들링 강화
- [ ] **FastAPI 백엔드** - 헬스체크 API 엔드포인트

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
- Sprint 3에서 실전 전환 예정
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

**마지막 업데이트**: 2026-01-15
**현재 버전**: Sprint 1 MVP
**라이선스**: Private
