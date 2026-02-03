# Database

PostgreSQL 데이터베이스 스키마 및 설정 파일

---

## 📁 구조

```
db/
├── init.sql              # 데이터베이스 스키마 (테이블, 인덱스, 트리거)
├── setup.sh              # 데이터베이스 자동 초기화 스크립트
├── migrations/           # 마이그레이션 파일
│   ├── 001_multi_bot.sql       # 멀티봇 지원
│   ├── 002_analytics_views.sql # AI 메모리 분석 함수
│   └── 003_audit_logs.sql      # 감사 로그
├── data/                 # 데이터 파일 (gitignored)
├── backups/              # 백업 파일 (gitignored)
└── README.md             # 이 파일
```

---

## 🚀 데이터베이스 초기화

### 자동 초기화 (권장)

```bash
# 프로젝트 루트에서
./db/setup.sh
```

**자동으로 하는 일:**
- PostgreSQL 연결 확인
- 데이터베이스 생성 (없을 경우)
- 스키마 초기화 (테이블, 인덱스, 트리거)
- 초기 데이터 삽입
- 테이블 검증

### 수동 초기화

```bash
# Docker 사용 시
docker compose up -d db
docker cp db/init.sql trading-db:/tmp/init.sql
docker compose exec db psql -U postgres -d trading -f /tmp/init.sql

# 로컬 PostgreSQL
psql -U postgres -f db/init.sql
```

---

## 📊 데이터베이스 스키마

### 현재 테이블

#### 1. `trades` - 거래 내역
```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES bot_configs(id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) CHECK (side IN ('LONG', 'SHORT')),
    entry_price DECIMAL(20, 8),
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8),
    leverage INT,
    pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 4),
    entry_time TIMESTAMP WITH TIME ZONE,
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason VARCHAR(20),
    status VARCHAR(20) CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    ...
);
```

**용도:** 모든 거래의 진입, 청산, 손익 추적

#### 2. `ai_signals` - AI 신호 기록
```sql
CREATE TABLE ai_signals (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES bot_configs(id),
    symbol VARCHAR(20) NOT NULL,
    signal VARCHAR(10) CHECK (signal IN ('LONG', 'SHORT', 'WAIT')),
    confidence DECIMAL(5, 2),
    price DECIMAL(20, 8),
    rsi DECIMAL(10, 2),
    ma_7, ma_25, ma_99, atr, volume_ratio,
    raw_response TEXT,
    action_taken BOOLEAN,
    trade_id UUID REFERENCES trades(id),
    timestamp TIMESTAMP WITH TIME ZONE,
    ...
);
```

**용도:** AI가 생성한 모든 신호와 지표 저장

#### 3. `market_data` - 시장 데이터
```sql
CREATE TABLE market_data (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    open, high, low, close, volume,
    rsi, ma_7, ma_25, ma_99, atr,
    timestamp TIMESTAMP WITH TIME ZONE,
    timeframe VARCHAR(10) DEFAULT '5m',
    ...
);
```

**용도:** OHLCV 데이터 및 계산된 지표 저장

#### 4. `bot_status` - 봇 상태
```sql
CREATE TABLE bot_status (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES bot_configs(id),
    bot_name VARCHAR(50) UNIQUE,
    is_running BOOLEAN,
    current_position VARCHAR(10),
    active_trade_id UUID REFERENCES trades(id),
    total_trades INT,
    winning_trades, losing_trades,
    total_pnl DECIMAL(20, 8),
    last_heartbeat TIMESTAMP,
    last_error TEXT,
    ...
);
```

**용도:** 봇의 현재 상태, 통계, 헬스체크

#### 5. `bot_configs` - 봇 설정
```sql
CREATE TABLE bot_configs (
    id UUID PRIMARY KEY,
    bot_name VARCHAR(50) UNIQUE,
    symbol VARCHAR(20),
    leverage INT,
    position_size_pct, take_profit_pct, stop_loss_pct,
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high')),
    rsi_oversold, rsi_overbought, volume_threshold,
    is_active BOOLEAN,
    is_testnet BOOLEAN,
    description TEXT,
    ...
);
```

**용도:** 멀티봇 설정 및 위험도 관리

---

## 🔄 Migrations

### 마이그레이션 파일

| 파일 | 설명 |
|------|------|
| `001_multi_bot.sql` | 멀티봇 지원 스키마 확장 |
| `002_analytics_views.sql` | AI 메모리 분석용 뷰 및 함수 |
| `003_audit_logs.sql` | 감사 로그 테이블 |

### 마이그레이션 실행

```bash
# Docker 사용 시
docker compose exec db psql -U trading -d trading -f /docker-entrypoint-initdb.d/migrations/001_multi_bot.sql
docker compose exec db psql -U trading -d trading -f /docker-entrypoint-initdb.d/migrations/002_analytics_views.sql

# 로컬 PostgreSQL
psql -U postgres -d trading -f db/migrations/001_multi_bot.sql
psql -U postgres -d trading -f db/migrations/002_analytics_views.sql
```

### 001_multi_bot.sql

**주요 변경:**
- `bot_configs` 테이블 확장 (risk_level, RSI 파라미터 등)
- `trades`, `ai_signals`, `bot_status`에 `bot_id` 컬럼 추가
- 위험도별 기본 설정 뷰 (`bot_configs_with_defaults`)
- 봇별 거래 통계 뷰 (`bot_trading_stats`)
- 예시 봇 설정 삽입 (btc-conservative, eth-balanced, sol-aggressive)

### 002_analytics_views.sql

**주요 변경:**
- `trades_with_signals` 뷰 (거래 + AI 신호 조인)
- 6개 분석 함수 추가 (아래 참조)
- 성능 최적화 인덱스

---

## 📈 분석 함수

`002_analytics_views.sql`에서 제공하는 분석 함수:

### 1. `get_rsi_performance()`
RSI 구간별 거래 성과 분석

```sql
SELECT * FROM get_rsi_performance(NULL, 7);
-- 결과: rsi_zone, side, total_trades, win_rate, avg_pnl, ...
```

RSI 구간:
- `oversold`: RSI < 30
- `low`: 30 ≤ RSI < 40
- `neutral`: 40 ≤ RSI < 60
- `high`: 60 ≤ RSI < 70
- `overbought`: RSI ≥ 70

### 2. `get_hourly_performance()`
시간대별 거래 성과 분석

```sql
SELECT * FROM get_hourly_performance(NULL, 7);
-- 결과: hour_of_day, side, total_trades, win_rate, avg_pnl, ...
```

### 3. `get_current_streak()`
현재 연승/연패 계산

```sql
SELECT * FROM get_current_streak(NULL);
-- 결과: streak_type (WIN/LOSS), streak_count, last_trade_time
```

### 4. `get_trading_summary()`
종합 거래 통계

```sql
SELECT * FROM get_trading_summary(NULL, 7);
-- 결과: total_trades, win_rate, profit_factor, long_win_rate, short_win_rate, ...
```

### 5. `get_exit_reason_stats()`
청산 사유별 통계

```sql
SELECT * FROM get_exit_reason_stats(NULL, 7);
-- 결과: exit_reason (TP/SL/TIMECUT), side, total_trades, win_rate, ...
```

### 6. `trades_with_signals` 뷰
거래와 AI 신호를 조인한 분석용 뷰

```sql
SELECT * FROM trades_with_signals WHERE bot_id = 'xxx';
-- 결과: 거래 정보 + AI 신호 정보 + 계산된 필드 (is_winner, rsi_zone, ...)
```

---

## 🔍 유용한 쿼리

### 거래 통계
```sql
-- 전체 거래 요약
SELECT * FROM trading_stats;

-- 최근 10개 거래
SELECT * FROM trades
ORDER BY entry_time DESC
LIMIT 10;

-- 승률 계산
SELECT
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
    ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate
FROM trades
WHERE status = 'CLOSED';
```

### AI 신호 분석
```sql
-- 최근 신호 (뷰 사용)
SELECT * FROM recent_signals;

-- 신호별 성과
SELECT
    s.signal,
    COUNT(*) AS signal_count,
    SUM(CASE WHEN s.action_taken THEN 1 ELSE 0 END) AS actions_taken,
    AVG(t.pnl) AS avg_pnl
FROM ai_signals s
LEFT JOIN trades t ON s.trade_id = t.id
GROUP BY s.signal;
```

### 봇별 통계
```sql
-- 봇별 거래 통계
SELECT * FROM bot_trading_stats;

-- 특정 봇 상태
SELECT * FROM bot_status WHERE bot_name = 'btc-conservative';
```

---

## 🗄️ 백업 및 복구

### 백업

```bash
# Docker 사용 시
docker compose exec db pg_dump -U postgres trading > db/backups/backup_$(date +%Y%m%d_%H%M%S).sql

# 로컬
pg_dump -U postgres trading > db/backups/backup_$(date +%Y%m%d_%H%M%S).sql
```

### 복구

```bash
# Docker 사용 시
docker cp db/backups/backup_XXXXXX.sql trading-db:/tmp/restore.sql
docker compose exec db psql -U postgres -d trading -f /tmp/restore.sql

# 로컬
psql -U postgres -d trading -f db/backups/backup_XXXXXX.sql
```

---

## 📈 인덱스 및 성능

스키마에 이미 최적화된 인덱스 포함:

```sql
-- 거래 조회 최적화
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_bot_id ON trades(bot_id);

-- 신호 조회 최적화
CREATE INDEX idx_signals_timestamp ON ai_signals(timestamp DESC);
CREATE INDEX idx_signals_trade_id ON ai_signals(trade_id);
CREATE INDEX idx_ai_signals_bot_id ON ai_signals(bot_id);

-- 시장 데이터 조회 최적화
CREATE INDEX idx_market_data_symbol_timestamp ON market_data(symbol, timestamp DESC);
```

---

## 🔗 연결 정보

### Docker
```bash
# 컨테이너 접속
docker compose exec db psql -U postgres -d trading

# 연결 문자열
postgresql://postgres:postgres@db:5432/trading
```

### 로컬
```bash
# psql 접속
psql -h localhost -p 5432 -U postgres -d trading

# 연결 문자열
postgresql://postgres:postgres@localhost:5432/trading
```

---

## 📚 참고

- PostgreSQL 공식 문서: https://www.postgresql.org/docs/
- SQLAlchemy (향후): https://www.sqlalchemy.org/
- Alembic (향후): https://alembic.sqlalchemy.org/

---

**스키마 버전:** 3.0
**마지막 업데이트:** 2026-02-03
