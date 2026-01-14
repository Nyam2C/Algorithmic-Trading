# 개발 계획서

**Project:** High-Win Survival System
**작성일:** 2025.12.15

---

## 1. 프로젝트 구조

```
Algorithmic-Trading/
├── .claude/
│   ├── TRADING_PLAN.md        # 트레이딩 전략 계획서
│   └── DEVELOPMENT_PLAN.md    # 개발 계획서 (현재 문서)
├── src/
│   ├── main.py                # 메인 실행 파일
│   ├── config.py              # 설정 관리
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── executor.py        # 주문 실행
│   │   ├── position.py        # 포지션 관리
│   │   └── monitor.py         # 익절/손절/타임컷 모니터링
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── gemini.py          # Gemini API 연동
│   │   ├── signals.py         # 매매 신호 생성
│   │   └── prompts/           # 프롬프트 템플릿
│   │       ├── system.txt     # 시스템 프롬프트
│   │       └── analysis.txt   # 분석 프롬프트
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetcher.py         # 시장 데이터 수집
│   │   └── indicators.py      # 기술적 지표 계산
│   ├── exchange/
│   │   ├── __init__.py
│   │   └── binance.py         # Binance API 래퍼
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── discord.py         # Discord 알림
│   ├── api/                   # FastAPI 백엔드
│   │   ├── __init__.py
│   │   ├── server.py          # FastAPI 앱
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py      # 헬스체크 엔드포인트
│   │       └── stats.py       # 통계 조회 엔드포인트
│   └── database/              # DB 관련
│       ├── __init__.py
│       ├── models.py          # SQLAlchemy 모델
│       ├── crud.py            # CRUD 함수
│       └── connection.py      # DB 연결 설정
├── tests/
│   ├── __init__.py
│   ├── test_trading.py
│   ├── test_ai.py
│   └── test_exchange.py
├── backtest/
│   ├── __init__.py
│   ├── simulator.py           # 백테스트 시뮬레이터
│   ├── data_loader.py         # 과거 데이터 로드
│   └── analysis.py            # 결과 분석
├── configs/                   # 봇별 설정 파일
│   ├── .env.btc               # BTC 보수형 봇 (MVP)
│   ├── .env.eth               # ETH 중간 봇
│   └── .env.sol               # SOL 공격형 봇
├── n8n/                       # n8n 워크플로우
│   └── workflows/
├── logs/                      # 로그 파일
├── .env                       # 공통 환경 변수
├── .env.example               # 환경 변수 템플릿
├── requirements.txt           # 의존성
├── Dockerfile                 # Docker 이미지 정의
├── docker-compose.yml         # Docker Compose 설정 (멀티봇)
├── .dockerignore              # Docker 빌드 제외 파일
└── README.md                  # 프로젝트 설명
```

---

## 2. 기술 스택

| 분류 | 기술 | 용도 |
|------|------|------|
| 언어 | Python 3.11+ | 메인 개발 |
| AI | Google Gemini API | 매매 신호 생성 |
| 거래소 | Binance Futures API | 주문 실행 |
| 알림 | Discord Bot API | 실시간 알림 |
| 서버 | AWS EC2 | 24시간 운영 |
| 컨테이너 | Docker | 환경 일관성, 배포 |
| 오케스트레이션 | n8n | 멀티봇 관리, 워크플로우 |
| **백엔드** | **FastAPI** | **헬스체크 API, 통계 조회** |
| **DB** | **PostgreSQL** | **거래 기록 저장** |
| **ORM** | **SQLAlchemy** | **DB 모델 관리** |
| 스케줄링 | APScheduler | 주기적 실행 |

---

## 3. 핵심 모듈 설계

### 3.1 Trading Executor (`src/trading/executor.py`)

```python
class TradingExecutor:
    """주문 실행 담당"""

    def open_position(side: str, amount: float) -> Order:
        """포지션 진입 (Maker 주문)"""

    def close_position(position_id: str) -> Order:
        """포지션 청산"""

    def set_take_profit(price: float) -> Order:
        """익절가 설정"""

    def set_stop_loss(price: float) -> Order:
        """손절가 설정"""
```

### 3.2 Position Monitor (`src/trading/monitor.py`)

```python
class PositionMonitor:
    """포지션 모니터링 및 타임컷 관리"""

    def check_time_cut(position: Position) -> bool:
        """2시간 타임컷 체크"""

    def check_conditional_extension(position: Position) -> bool:
        """조건부 연장 판단 (+0.1% 이상 수익 시)"""

    def execute_time_cut(position: Position) -> None:
        """타임컷 실행"""
```

### 3.3 AI Signal Generator (`src/ai/signals.py`)

```python
class SignalGenerator:
    """Gemini 기반 매매 신호 생성"""

    def analyze_market(data: MarketData) -> Signal:
        """시장 분석 후 LONG/SHORT/WAIT 반환"""

    def build_prompt(data: MarketData) -> str:
        """Gemini 프롬프트 생성"""
```

### 3.4 Data Fetcher (`src/data/fetcher.py`)

```python
class DataFetcher:
    """시장 데이터 수집"""

    def get_klines(symbol: str, interval: str, limit: int) -> DataFrame:
        """캔들 데이터 조회"""

    def get_current_price(symbol: str) -> float:
        """현재가 조회"""
```

### 3.5 Indicator Calculator (`src/data/indicators.py`)

```python
class IndicatorCalculator:
    """기술적 지표 계산"""

    def calculate_rsi(data: DataFrame, period: int) -> Series:
        """RSI 계산"""

    def calculate_ma(data: DataFrame, period: int) -> Series:
        """이동평균 계산"""

    def calculate_atr(data: DataFrame, period: int) -> Series:
        """ATR (변동성) 계산"""
```

### 3.6 FastAPI Server (`src/api/server.py`)

```python
from fastapi import FastAPI
from src.api.routes import health, stats

app = FastAPI(title="Trading Bot API")

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(stats.router, prefix="/stats", tags=["Stats"])
```

### 3.7 Health Check (`src/api/routes/health.py`)

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    """n8n 헬스체크용"""
    return {"status": "ok", "bot_name": BOT_NAME}

@router.get("/position")
async def current_position():
    """현재 포지션 상태"""
    return {"has_position": True, "side": "LONG", "pnl": 0.15}
```

### 3.8 Stats API (`src/api/routes/stats.py`)

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/today")
async def today_stats():
    """오늘 거래 통계"""
    return {"trades": 5, "wins": 3, "pnl": 1500}

@router.get("/total")
async def total_stats():
    """전체 통계"""
    return {"total_trades": 100, "win_rate": 0.55, "total_pnl": 25000}
```

### 3.9 Database Models (`src/database/models.py`)

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Trade(Base):
    """거래 기록"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    bot_name = Column(String)           # btc, eth, sol
    symbol = Column(String)             # BTCUSDT
    side = Column(String)               # LONG, SHORT
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl = Column(Float)                 # 손익 (원)
    pnl_pct = Column(Float)             # 손익 (%)
    result = Column(String)             # TP, SL, TIMECUT
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    duration_minutes = Column(Integer)  # 보유 시간

class BotStatus(Base):
    """봇 상태"""
    __tablename__ = "bot_status"

    id = Column(Integer, primary_key=True)
    bot_name = Column(String, unique=True)
    is_active = Column(Integer, default=1)
    has_position = Column(Integer, default=0)
    current_side = Column(String)       # LONG, SHORT, None
    entry_price = Column(Float)
    last_updated = Column(DateTime)
```

---

## 4. API 설정

### 4.1 필요한 API 키

```env
# .env.example (Git에 포함)

# Binance
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key

# Gemini
GEMINI_API_KEY=your_gemini_api_key

# Discord
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CHANNEL_ID=your_channel_id
DISCORD_WEBHOOK_URL=your_webhook_url

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://trading:yourpassword@postgres:5432/trading
DB_PASSWORD=your_db_password

# FastAPI
API_HOST=0.0.0.0
API_PORT=8080

# n8n (멀티봇 Phase 8)
N8N_PASSWORD=your_n8n_password
```

### 4.2 봇별 설정 파일

> ⚠️ `configs/` 폴더는 `.gitignore`에 추가 (전략 수치 비공개)

**configs/.env.btc.example:** (Git에 포함, 값만 비움)
```env
# BTC 보수형 봇 설정
BOT_NAME=btc
SYMBOL=BTCUSDT
LEVERAGE=
POSITION_SIZE_PCT=
TAKE_PROFIT_PCT=
STOP_LOSS_PCT=
TIME_CUT_MINUTES=
EXTENSION_MINUTES=
EXTENSION_THRESHOLD=
EARLY_CUT_THRESHOLD=
```

**configs/.env.eth.example:**
```env
# ETH 중간 봇 설정
BOT_NAME=eth
SYMBOL=ETHUSDT
LEVERAGE=
POSITION_SIZE_PCT=
TAKE_PROFIT_PCT=
STOP_LOSS_PCT=
TIME_CUT_MINUTES=
EXTENSION_MINUTES=
EXTENSION_THRESHOLD=
EARLY_CUT_THRESHOLD=
```

**configs/.env.sol.example:**
```env
# SOL 공격형 봇 설정
BOT_NAME=sol
SYMBOL=SOLUSDT
LEVERAGE=
POSITION_SIZE_PCT=
TAKE_PROFIT_PCT=
STOP_LOSS_PCT=
TIME_CUT_MINUTES=
EXTENSION_MINUTES=
EXTENSION_THRESHOLD=
EARLY_CUT_THRESHOLD=
```

### 4.3 .gitignore 설정

```gitignore
# 환경 변수 (API 키)
.env
!.env.example

# 봇별 전략 설정 (수치 비공개)
configs/.env.*
!configs/.env.*.example
```

### 4.4 Binance API 권한
- ✅ 선물 거래 활성화
- ✅ API 거래 허용
- ❌ 출금 권한 비활성화 (보안)

---

## 5. 트레이딩 파라미터

```python
# src/config.py

TRADING_CONFIG = {
    # 자금 관리
    "TOTAL_CAPITAL": 1_000_000,      # 총 자본 (원)
    "POSITION_SIZE_PCT": 0.05,        # 진입 비중 (5%)
    "LEVERAGE": 15,                   # 레버리지

    # 익절/손절
    "TAKE_PROFIT_PCT": 0.004,         # 익절 (+0.4%)
    "STOP_LOSS_PCT": 0.004,           # 손절 (-0.4%)

    # 타임컷
    "TIME_CUT_MINUTES": 120,          # 기본 타임컷 (2시간)
    "EXTENSION_MINUTES": 30,          # 연장 시간
    "EXTENSION_THRESHOLD": 0.001,     # 연장 조건 (+0.1%)
    "EARLY_CUT_THRESHOLD": -0.003,    # 조기 청산 (-0.3%)

    # 거래 설정
    "SYMBOL": "BTCUSDT",
    "ORDER_TYPE": "LIMIT",            # Maker 주문
}
```

---

## 6. 메인 실행 흐름

```
┌─────────────────────────────────────────────────────────┐
│                      Main Loop                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   1. 데이터 수집        │
              │   - 2시간 캔들          │
              │   - RSI, MA, ATR       │
              └────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   2. AI 신호 생성       │
              │   - Gemini 분석        │
              │   - LONG/SHORT/WAIT    │
              └────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   3. 포지션 체크        │
              │   - 기존 포지션 있음?   │
              └────────────────────────┘
                     │           │
                  없음          있음
                     │           │
                     ▼           ▼
         ┌──────────────┐  ┌──────────────┐
         │ 4a. 진입     │  │ 4b. 모니터링  │
         │ - Maker 주문 │  │ - TP/SL 체크 │
         │ - TP/SL 설정 │  │ - 타임컷 체크│
         └──────────────┘  └──────────────┘
                     │           │
                     └─────┬─────┘
                           ▼
              ┌────────────────────────┐
              │   5. 알림 전송         │
              │   - Discord Embed     │
              └────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   6. 대기 (5분)        │
              └────────────────────────┘
                           │
                           └──────────► Loop
```

---

## 7. 에러 처리

| 상황 | 처리 |
|------|------|
| API 연결 실패 | 3회 재시도 후 Discord 알림 |
| 주문 실패 | 즉시 재시도, 실패 시 알림 |
| Gemini 응답 없음 | WAIT 처리 (진입 안 함) |
| 서버 재시작 | 기존 포지션 상태 복구 |

---

## 8. 의존성

```
# requirements.txt

# 거래소 & AI
python-binance>=1.0.0
google-generativeai>=0.3.0

# 데이터 분석
pandas>=2.0.0
numpy>=1.24.0
ta>=0.10.0              # 기술적 지표

# 백엔드 (FastAPI)
fastapi>=0.104.0
uvicorn>=0.24.0         # ASGI 서버
pydantic>=2.0.0         # 데이터 검증

# 데이터베이스
sqlalchemy>=2.0.0
asyncpg>=0.29.0         # PostgreSQL 비동기

# 알림 & 스케줄링
discord.py>=2.3.0
aiohttp>=3.9.0          # Discord 비동기
APScheduler>=3.10.0

# 유틸
python-dotenv>=1.0.0
loguru>=0.7.0

# 테스트
pytest>=7.0.0
pytest-asyncio>=0.21.0  # 비동기 테스트
httpx>=0.25.0           # FastAPI 테스트 클라이언트
```

---

## 9. Discord 봇 설계

### 9.1 알림 채널 구조
```
📁 Trading Bot Server
├── 📢 alerts          # 진입/청산 알림
├── 📊 daily-report    # 일일 리포트
├── ⚠️ errors          # 에러 알림
└── 🤖 bot-commands    # 슬래시 명령어
```

### 9.2 Embed 메시지 포맷

**진입 알림:**
```
┌─────────────────────────────┐
│ 🟢 LONG 진입                │
├─────────────────────────────┤
│ 심볼: BTCUSDT               │
│ 진입가: $104,250            │
│ 익절가: $104,615 (+0.35%)   │
│ 손절가: $103,677 (-0.55%)   │
│ 포지션: $750,000 (15x)      │
├─────────────────────────────┤
│ ⏰ 타임컷: 2시간 후          │
└─────────────────────────────┘
```

**청산 알림:**
```
┌─────────────────────────────┐
│ ✅ 익절 청산                 │
├─────────────────────────────┤
│ 진입가: $104,250            │
│ 청산가: $104,615            │
│ 수익: +2,625원 (+5.25%)     │
│ 보유시간: 47분              │
└─────────────────────────────┘
```

### 9.3 슬래시 명령어

| 명령어 | 설명 |
|--------|------|
| `/status` | 현재 포지션 상태 |
| `/report` | 오늘 거래 요약 |
| `/balance` | 계좌 잔고 |
| `/stats` | 전체 통계 (승률, 총 수익) |
| `/pause` | 봇 일시정지 |
| `/resume` | 봇 재개 |

---

## 10. Docker 배포

### 10.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY src/ ./src/
COPY backtest/ ./backtest/

# 환경 변수
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

CMD ["python", "-m", "src.main"]
```

### 10.2 docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL 데이터베이스
  postgres:
    image: postgres:15-alpine
    container_name: trading-db
    restart: always
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: trading
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trading"]
      interval: 10s
      timeout: 5s
      retries: 5

  trading-bot:
    build: .
    container_name: trading-bot
    restart: always
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  postgres_data:
```

### 10.3 .dockerignore

```
.git
.env
__pycache__
*.pyc
.pytest_cache
logs/
.claude/
tests/
*.md
```

### 10.4 배포 명령어

```bash
# 로컬 테스트
docker-compose up --build

# 백그라운드 실행
docker-compose up -d --build

# 로그 확인
docker logs -f trading-bot

# 재시작
docker-compose restart

# 중지
docker-compose down
```

### 10.5 AWS EC2 배포 순서

```bash
# 1. EC2 접속
ssh -i key.pem ec2-user@your-ip

# 2. Docker 설치
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -aG docker ec2-user

# 3. Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. 코드 배포
git clone your-repo
cd Algorithmic-Trading

# 5. 환경 변수 설정
cp .env.example .env
nano .env  # API 키 입력

# 6. 실행
docker-compose up -d --build
```

---

## 11. 멀티봇 아키텍처 (Phase 8)

### 11.1 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                        n8n                               │
│              (오케스트레이션 & 모니터링)                    │
├─────────────────────────────────────────────────────────┤
│  워크플로우:                                              │
│  - 매 5분: 각 봇 상태 체크                                │
│  - 매 1시간: 포트폴리오 밸런싱                             │
│  - 매일: 일일 리포트 생성                                  │
│  - 에러 시: Discord 알림                                  │
└─────────────────────────────────────────────────────────┘
              │              │              │
              ▼              ▼              ▼
┌──────────────────┬──────────────────┬──────────────────┐
│   BTC 보수형      │   ETH 중간       │   SOL 공격형     │
│   10x / 5%       │   15x / 5%       │   15x / 3%       │
│   TP 0.3%        │   TP 0.4%        │   TP 0.5%        │
│   안정적 베이스   │   중간 수익       │   고수익 추구    │
└──────────────────┴──────────────────┴──────────────────┘
              │              │              │
              └──────────────┴──────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Binance API    │
                    │  (단일 계정)     │
                    └─────────────────┘
```

### 11.2 봇별 전략 설정

| 봇 | 코인 | 레버리지 | 비중 | TP | SL | 역할 |
|----|------|----------|------|-----|-----|------|
| bot-btc | BTCUSDT | 10x | 5% | 0.3% | 0.3% | 안정적 베이스 (MVP) |
| bot-eth | ETHUSDT | 15x | 5% | 0.4% | 0.4% | 중간 공격 |
| bot-sol | SOLUSDT | 15x | 3% | 0.5% | 0.5% | 고변동성 공격 |

### 11.3 코인별 특성

| 코인 | 변동성 | AI 예측 난이도 | 특징 |
|------|--------|---------------|------|
| BTC | 낮음 | 쉬움 | 시장 대장, 안정적 |
| ETH | 중간 | 중간 | BTC 따라가며 변동성 큼 |
| SOL | 높음 | 어려움 | 급등락, 고수익/고위험 |

### 11.4 포트폴리오 구성

```
총 자본 배분:
- BTC 보수형: 50% (500,000원) - 안정적 베이스
- ETH 중간:   35% (350,000원) - 중간 수익
- SOL 공격형: 15% (150,000원) - 고수익 추구

→ 코인 분산으로 실질적 헷지
→ BTC 하락해도 SOL/ETH 상승 가능
→ 리스크 계층화 (보수 → 중간 → 공격)
```

### 11.5 멀티봇 docker-compose.yml

```yaml
version: '3.8'

services:
  # n8n 오케스트레이터
  n8n:
    image: n8nio/n8n
    container_name: n8n
    ports:
      - "5678:5678"
    volumes:
      - ./n8n_data:/home/node/.n8n
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    restart: always

  # 봇 1: BTC 보수형 (MVP)
  bot-btc:
    build: .
    container_name: bot-btc
    env_file: ./configs/.env.btc
    volumes:
      - ./logs/btc:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 5m
      timeout: 10s
      retries: 3

  # 봇 2: ETH 중간
  bot-eth:
    build: .
    container_name: bot-eth
    env_file: ./configs/.env.eth
    volumes:
      - ./logs/eth:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 5m
      timeout: 10s
      retries: 3

  # 봇 3: SOL 공격형
  bot-sol:
    build: .
    container_name: bot-sol
    env_file: ./configs/.env.sol
    volumes:
      - ./logs/sol:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 5m
      timeout: 10s
      retries: 3

  # 통합 Discord 봇
  discord-bot:
    build: ./discord
    container_name: discord-bot
    env_file: .env
    restart: always
```

### 11.6 n8n 워크플로우

**헬스체크 워크플로우:**
```
[Cron: 매 5분]
    → [HTTP: 각 봇 /health 체크]
    → [IF: 응답 없음]
        → [Discord: 에러 알림]
        → [Docker: 컨테이너 재시작]
```

**일일 리포트 워크플로우:**
```
[Cron: 매일 09:00]
    → [HTTP: 각 봇 /stats 조회]
    → [Aggregate: 통합 리포트 생성]
    → [Discord: Embed 메시지 전송]
```

**포트폴리오 밸런싱:**
```
[Cron: 매 1시간]
    → [HTTP: 각 봇 수익률 조회]
    → [IF: 특정 봇 손실 과다]
        → [HTTP: 해당 봇 일시정지]
        → [Discord: 알림]
```

### 11.7 봇별 설정 파일 예시

**configs/.env.btc:**
```env
BOT_NAME=btc
SYMBOL=BTCUSDT
LEVERAGE=10
POSITION_SIZE_PCT=0.05
TAKE_PROFIT_PCT=0.003
STOP_LOSS_PCT=0.003
```

**configs/.env.eth:**
```env
BOT_NAME=eth
SYMBOL=ETHUSDT
LEVERAGE=15
POSITION_SIZE_PCT=0.05
TAKE_PROFIT_PCT=0.004
STOP_LOSS_PCT=0.004
```

**configs/.env.sol:**
```env
BOT_NAME=sol
SYMBOL=SOLUSDT
LEVERAGE=15
POSITION_SIZE_PCT=0.03
TAKE_PROFIT_PCT=0.005
STOP_LOSS_PCT=0.005
```

---

## 12. 관련 문서

- [TRADING_PLAN.md](TRADING_PLAN.md) - 트레이딩 전략
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - 구현 계획/체크리스트
- [PROMPT_ENGINEERING.md](PROMPT_ENGINEERING.md) - AI 프롬프트 설계
