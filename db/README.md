# Database

PostgreSQL 데이터베이스 스키마 및 설정 파일

---

## 📁 구조

```
db/
├── init.sql           # 데이터베이스 스키마 (테이블, 인덱스, 트리거)
├── setup.sh           # 데이터베이스 자동 초기화 스크립트
├── data/              # 데이터 파일 (gitignored)
├── backups/           # 백업 파일 (gitignored)
└── README.md          # 이 파일
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

### 현재 테이블 (Sprint 1)

#### 1. `trades` - 거래 내역
```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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

---

### 미래 테이블 (Sprint 2+ Backend)

#### 5. `users` - 사용자 관리
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    username VARCHAR(50) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(20) CHECK (role IN ('admin', 'user', 'viewer')),
    api_key VARCHAR(100) UNIQUE,
    is_active BOOLEAN,
    ...
);
```

**용도:** 웹 인터페이스 사용자 인증 및 관리

#### 6. `bot_configs` - 봇 설정
```sql
CREATE TABLE bot_configs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    bot_name VARCHAR(50),
    symbol VARCHAR(20),
    leverage INT,
    position_size_pct, take_profit_pct, stop_loss_pct,
    is_active BOOLEAN,
    ...
);
```

**용도:** 사용자별 멀티 봇 설정 관리

#### 7. `notifications` - 알림
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    message TEXT,
    notification_type VARCHAR(20),
    is_read BOOLEAN,
    send_discord, send_email, send_telegram,
    ...
);
```

**용도:** 멀티 채널 알림 시스템

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

### 봇 상태 확인
```sql
-- 현재 봇 상태
SELECT * FROM bot_status WHERE bot_name = 'high-win-bot';

-- 가동 시간 및 성과
SELECT
    bot_name,
    is_running,
    total_trades,
    winning_trades,
    ROUND(100.0 * winning_trades / NULLIF(total_trades, 0), 2) AS win_rate,
    total_pnl,
    uptime_seconds / 3600 AS uptime_hours
FROM bot_status;
```

---

## 🔄 마이그레이션 (향후)

Sprint 2에서 Alembic 도입 예정:

```bash
# Alembic 초기화
alembic init alembic

# 마이그레이션 생성
alembic revision --autogenerate -m "Add backend tables"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1
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

-- 신호 조회 최적화
CREATE INDEX idx_signals_timestamp ON ai_signals(timestamp DESC);
CREATE INDEX idx_signals_trade_id ON ai_signals(trade_id);

-- 시장 데이터 조회 최적화
CREATE INDEX idx_market_data_symbol_timestamp ON market_data(symbol, timestamp DESC);
```

---

## 🧹 유지보수

### 테이블 정리
```sql
-- 오래된 시장 데이터 삭제 (30일 이상)
DELETE FROM market_data
WHERE timestamp < NOW() - INTERVAL '30 days';

-- 오래된 알림 삭제 (읽음 + 90일 이상)
DELETE FROM notifications
WHERE is_read = TRUE
  AND created_at < NOW() - INTERVAL '90 days';
```

### 통계 업데이트
```sql
-- PostgreSQL 통계 갱신
ANALYZE trades;
ANALYZE ai_signals;
ANALYZE market_data;
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

**스키마 버전:** 1.0 (Sprint 1)
**마지막 업데이트:** 2026-01-16
