# Monitoring Stack

Grafana + Loki + Promtail + Prometheus 기반 모니터링 시스템

---

## 개요

트레이딩 봇의 실시간 로그 수집, 메트릭 모니터링, 시각화를 제공하는 통합 모니터링 스택입니다.

**구성 요소:**
- **Loki**: 로그 저장소 (30일 보관)
- **Promtail**: 로그 수집 에이전트
- **Grafana**: 대시보드 및 시각화
- **Prometheus**: 메트릭 수집 및 저장 (30일 보관)

---

## 빠른 시작

### 1. 모니터링 스택 시작

```bash
# 서비스 시작 (모니터링 포함)
./scripts/start.sh

# 또는 직접 실행
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.monitoring.yml up -d
```

### 2. 접속 정보

| 서비스 | URL | 인증 | 비고 |
|--------|-----|------|------|
| Grafana | http://localhost:3000 | admin / (env var) | 외부 노출 |
| Prometheus | http://localhost:9090 | 없음 | localhost만 |
| Loki | http://localhost:3100 | 없음 | localhost만 |
| /metrics | http://localhost:8000/metrics | Bearer (선택) | METRICS_AUTH_TOKEN |

### 3. 대시보드 확인

Grafana 좌측 메뉴 → Dashboards에서 다음 대시보드 확인:

1. **Trading Overview** - 거래 현황 및 신호 분포
2. **AI Signals** - AI 신호 분석 및 신뢰도
3. **System Health** - 시스템 상태 및 에러 로그
4. **Docker Container Logs** - 컨테이너별 로그 검색 및 분석
5. **Account Overview** - 계좌 잔고, 승률, 드로다운 모니터링

---

## 대시보드 설명

### 1. Trading Overview (11개 패널)

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| LONG 신호 (24h) | Loki | `count_over_time({signal="LONG"}[24h])` |
| SHORT 신호 (24h) | Loki | `count_over_time({signal="SHORT"}[24h])` |
| WAIT 신호 (24h) | Loki | `count_over_time({signal="WAIT"}[24h])` |
| 신호 분포 (24h) | Loki | LONG/SHORT/WAIT 비율 파이차트 |
| 거래 타임라인 | Loki | 진입/청산 로그 타임라인 |
| 신호 발생 빈도 (시간별) | Loki | 시간대별 신호 히스토그램 |
| Discord 알림 | Loki | Discord 전송 로그 |
| 시간당 거래 빈도 | Prometheus | `rate(trading_trades_total[1h])` |
| 전체 승률 | Prometheus | `trading_win_rate` 게이지 (빨강<40%, 노랑<60%, 초록>=60%) |
| Position PnL % | Prometheus | `trading_position_pnl_percent` |
| 루프 소요시간 | Prometheus | `trading_loop_duration_seconds` |

---

### 2. AI Signals (10개 패널)

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| 신호 분포 (24h) | Prometheus | `increase(trading_signal_total[24h])` 파이차트 |
| 평균 신뢰도 (1h) | Prometheus | `trading_signal_confidence` 게이지 (빨강<0.5, 노랑<0.75, 초록>=0.75) |
| 신호 발생 추이 | Prometheus | `rate(trading_signal_total[5m])` 시계열 |
| LONG 신호 로그 | Loki | `{signal="LONG"}` 상세 로그 |
| SHORT 신호 로그 | Loki | `{signal="SHORT"}` 상세 로그 |
| RSI 추이 | Prometheus | `trading_rsi` 시계열 |
| AI 응답시간 | Prometheus | `trading_ai_latency_seconds` |
| 시그널 신뢰도 | Prometheus | `trading_signal_confidence` 시계열 |
| 시그널 소스별 카운트 | Prometheus | `trading_signal_total` by source |
| AI 결정 로그 | Loki | `{job="trading-ai-signals"}` 프롬프트/응답/이유 |

---

### 3. System Health (11개 패널)

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| 에러 발생 (1h) | Loki | 에러 카운트 (노랑>=5, 빨강>=10) |
| Bot Status | Prometheus | `increase(trading_loop_total[10m])` — UP/DOWN 판단 |
| API 평균 지연시간 | Prometheus | `trading_api_latency_seconds` 평균 (노랑>=1s, 빨강>=5s) |
| Discord 알림 (1h) | Loki | Discord 알림 성공 횟수 |
| 에러 로그 | Loki | 실시간 에러 로그 스트림 |
| 로그 레벨별 발생 빈도 | Loki | info/warning/error 시계열 |
| 에러 발생률 | Loki | 에러 발생률 추이 |
| API 호출 로그 | Loki | API 호출 상세 로그 |
| API 지연시간 p95 | Prometheus | `histogram_quantile(0.95, trading_api_latency_seconds_bucket)` |
| 루프 실행 빈도 | Prometheus | `rate(trading_loop_total[5m])` |
| 에러 로그 상세 | Loki | 에러 타입별 상세 로그 |

---

### 4. Docker Container Logs (5개 패널)

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| 컨테이너별 로그 볼륨 | Loki | 컨테이너별 로그 발생량 (스택 timeseries) |
| 로그 레벨 분포 | Loki | 선택된 컨테이너의 레벨별 분포 |
| stdout / stderr 분포 | Loki | 스트림별 로그 분포 |
| 컨테이너 로그 | Loki | 선택된 컨테이너의 로그 검색 |
| 에러 로그 (stderr) | Loki | stderr 스트림의 에러 로그 |

**Template Variables:** `` (컨테이너 선택), `` (로그 검색어)

---

### 5. Account Overview (11개 패널)

**My Assets:**

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| Total Balance | Prometheus | `trading_account_balance` (USDT) |
| Available Balance | Prometheus | `trading_available_balance` (USDT) |
| Unrealized PnL | Prometheus | `trading_unrealized_pnl` (USDT) |
| Daily PnL % | Prometheus | `trading_daily_pnl_pct` |

**Performance:**

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| Win Rate | Prometheus | `trading_win_rate` 게이지 (빨강<40%, 초록>=60%) |
| Drawdown | Prometheus | `trading_drawdown_pct` 게이지 (노랑>=3%, 빨강>=5%) |
| Total Trades | Prometheus | `trading_trades_total` 합계 |
| Open Positions | Prometheus | `trading_open_positions` |

**차트:**

| 패널 | 데이터소스 | 설명 |
|------|-----------|------|
| Balance Over Time | Prometheus | 잔고 변화 추이 시계열 |
| Daily PnL % | Prometheus | 일일 수익률 추이 |
| Unrealized PnL | Prometheus | 미실현 PnL 추이 |

**Template Variable:** `` (봇별 필터링)

---

## Prometheus 메트릭 레퍼런스

트레이딩 봇은 `/metrics` 엔드포인트에서 Prometheus 메트릭을 제공합니다.

### 메트릭 접근
```bash
curl http://localhost:8000/metrics

# 인증 설정 시
curl -H "Authorization: Bearer <token>" http://localhost:8000/metrics
```

### 전체 메트릭 목록 (22개)

| 메트릭 | 타입 | 레이블 | 설명 |
|--------|------|--------|------|
| `trading_trades_total` | Counter | bot_name, side, result | 총 거래 수 |
| `trading_trade_duration_seconds` | Histogram | bot_name | 거래 지속시간 (버킷: 10s~2h) |
| `trading_position_pnl_percent` | Gauge | bot_name | 현재 포지션 PnL % |
| `trading_api_latency_seconds` | Histogram | endpoint | API 지연시간 (버킷: 10ms~5s) |
| `trading_signal_confidence` | Gauge | bot_name | AI 시그널 신뢰도 (0-1) |
| `trading_loop_duration_seconds` | Histogram | bot_name | 루프 소요시간 (버킷: 0.5s~120s) |
| `trading_loop_total` | Counter | bot_name | 루프 실행 횟수 |
| `trading_signal_total` | Counter | bot_name, signal, source | 시그널 발생 수 |
| `trading_ai_latency_seconds` | Histogram | bot_name | Gemini AI 응답시간 (버킷: 0.5s~60s) |
| `trading_consecutive_wait_count` | Gauge | bot_name | 연속 WAIT 신호 수 |
| `trading_exchange_connected` | Gauge | bot_name | 거래소 연결 상태 (0/1) |
| `trading_circuit_breaker_state` | Gauge | breaker_name | 서킷브레이커 상태 (0=closed, 1=open) |
| `trading_open_positions` | Gauge | bot_name | 오픈 포지션 수 |
| `trading_bot_uptime_seconds` | Gauge | bot_name | 봇 가동시간 (초) |
| `trading_rsi` | Gauge | bot_name | RSI 값 (0-100) |
| `trading_account_balance` | Gauge | bot_name | 총 계좌 잔고 (USDT) |
| `trading_available_balance` | Gauge | bot_name | 가용 잔고 (USDT) |
| `trading_unrealized_pnl` | Gauge | bot_name | 미실현 PnL (USDT) |
| `trading_daily_pnl` | Gauge | bot_name | 일일 실현 PnL (USDT) |
| `trading_daily_pnl_pct` | Gauge | bot_name | 일일 PnL % |
| `trading_drawdown_pct` | Gauge | bot_name | 현재 드로다운 % |
| `trading_win_rate` | Gauge | bot_name | 승률 (0-1) |

---

## 주요 LogQL 쿼리

### 최근 신호 조회

```logql
{app="trading"} |= "SIGNAL"
```

### 에러 로그 조회

```logql
{app="trading", level="error"}
```

### LONG 신호 개수 (24시간)

```logql
sum(count_over_time({app="trading", signal="LONG"} [24h]))
```

### 평균 신뢰도 (1시간)

```logql
{app="trading"} | json | confidence != "" | unwrap confidence | avg_over_time(1h)
```

### 거래 로그

```logql
{app="trading"} |= "TRADE" or "ORDER"
```

---

## 설정

### Loki 설정 (loki/loki-config.yml)

**주요 설정:**
- 보관 기간: 30일 (`retention_period: 720h`)
- 압축: 자동 압축 활성화
- 저장 위치: `/loki` (Docker 볼륨)

**수정 방법:**
```yaml
limits_config:
  retention_period: 720h  # 원하는 기간으로 변경 (시간 단위)
```

---

### Promtail 설정 (promtail/promtail-config.yml)

**수집 대상:**
- `logs/bot.json.log` - 메인 봇 로그
- `logs/error.json.log` - 에러 로그
- `logs/trade.json.log` - 거래 로그
- `logs/ai_signal.json.log` - AI 신호 로그
- Docker 컨테이너 로그 - 모든 컨테이너 자동 수집

**레이블:**
- `job`: 작업 이름 (trading-bot, trading-error, trading-trades, trading-ai-signals, docker-containers)
- `app`: 애플리케이션 이름 (trading)
- `env`: 환경 (testnet)
- `level`: 로그 레벨 (info, error, warning)
- `signal`: 신호 타입 (LONG, SHORT, WAIT)
- `container`: Docker 컨테이너 이름
- `stream`: 로그 스트림 (stdout, stderr)

---

### Prometheus 설정 (prometheus/prometheus.yml)

**주요 설정:**
- 스크래핑 간격: 15초
- 대상: `trading-bot:8000` (`/metrics` 엔드포인트)
- 보관 기간: 30일

**인증 설정 (선택):**

`METRICS_AUTH_TOKEN` 환경 변수 설정 시 `/metrics` 엔드포인트에 Bearer 인증이 적용됩니다.
Prometheus에서 인증 토큰을 사용하려면 `prometheus.yml`에서 주석을 해제하세요:

```yaml
scrape_configs:
  - job_name: 'trading-bot'
    authorization:
      credentials_file: /etc/prometheus/metrics_token
    static_configs:
      - targets: ['trading-bot:8000']
```

토큰은 `prometheus/metrics_token` 파일에 저장합니다.

---

### Grafana 설정

**초기 로그인 정보:**
- Username: `admin`
- Password: `admin123`

**보안 강화:**

최초 로그인 후 비밀번호를 변경하세요:
1. Grafana → 우측 상단 사용자 아이콘
2. Profile → Change Password

**환경 변수로 관리:**

[docker-compose.yml](docker-compose.yml)에서 수정:
```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=your_secure_password
```

---

## 파일 구조

```
monitoring/
├── docker-compose.yml                # Docker Compose 설정
├── init-monitoring.sh                # 초기화 스크립트
├── README.md                         # 이 파일
├── loki/
│   └── loki-config.yml               # Loki 설정
├── promtail/
│   └── promtail-config.yml           # Promtail 설정
├── prometheus/
│   ├── prometheus.yml                # Prometheus 스크래핑 설정
│   └── metrics_token                 # /metrics 인증 토큰 (선택)
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   ├── loki.yml              # Loki 데이터소스
    │   │   └── prometheus.yml        # Prometheus 데이터소스
    │   ├── dashboards/
    │   │   └── default.yml           # 대시보드 프로비저닝
    │   └── alerting/
    │       └── empty.yml             # 알림 설정 (미사용)
    └── dashboards/
        ├── trading-overview.json     # 거래 현황 대시보드
        ├── ai-signals.json           # AI 신호 대시보드
        ├── system-health.json        # 시스템 헬스 대시보드
        ├── docker-containers.json    # Docker 컨테이너 로그 대시보드
        └── account-overview.json     # 계좌 현황 대시보드
```

---

## 관리 명령어

### 시작

```bash
# 서비스 시작
./scripts/start.sh

# 또는
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.monitoring.yml up -d
```

### 중지

```bash
# 서비스 중지
./scripts/start.sh --stop

# 또는
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.monitoring.yml down
```

### 재시작

```bash
# 서비스 재시작
./scripts/start.sh --stop && ./scripts/start.sh

# 또는
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.monitoring.yml restart
```

### 로그 확인

```bash
# 모든 서비스 로그
docker compose -f monitoring/docker-compose.yml logs -f

# 특정 서비스 로그
docker compose -f monitoring/docker-compose.yml logs -f loki
docker compose -f monitoring/docker-compose.yml logs -f promtail
docker compose -f monitoring/docker-compose.yml logs -f grafana
docker compose -f monitoring/docker-compose.yml logs -f prometheus
```

### 상태 확인

```bash
# 컨테이너 상태
docker compose -f monitoring/docker-compose.yml ps

# Loki 상태
curl http://localhost:3100/ready

# Prometheus 상태 (targets)
curl http://localhost:9090/api/v1/targets

# Grafana 상태
curl http://localhost:3000/api/health
```

---

## 트러블슈팅

### Grafana에서 로그가 안 보일 때

**원인:** Promtail이 로그 파일을 찾지 못함

**해결:**
1. 로그 파일이 생성되었는지 확인:
   ```bash
   ls -la logs/*.json.log
   ```

2. Promtail 로그 확인:
   ```bash
   docker compose -f monitoring/docker-compose.yml logs promtail
   ```

3. 로그 파일 권한 확인:
   ```bash
   chmod 644 logs/*.json.log
   ```

---

### Grafana에서 Prometheus 데이터가 "No Data"일 때

**원인:** Prometheus가 `/metrics` 엔드포인트를 스크래핑하지 못함

**해결:**
1. Prometheus targets 상태 확인:
   ```bash
   curl http://localhost:9090/api/v1/targets | python3 -m json.tool
   ```

2. target이 DOWN이면 트레이딩 봇이 실행 중인지 확인:
   ```bash
   curl http://localhost:8000/metrics
   ```

3. `METRICS_AUTH_TOKEN` 설정 시 `prometheus.yml`의 인증 설정이 일치하는지 확인

---

### Loki가 시작되지 않을 때

**원인:** 볼륨 권한 문제

**해결:**
```bash
# 볼륨 재생성
docker compose -f monitoring/docker-compose.yml down -v
docker compose -f monitoring/docker-compose.yml up -d
```

---

### Grafana 대시보드가 비어있을 때

**원인:** 대시보드 프로비저닝 실패

**해결:**
1. Grafana 재시작:
   ```bash
   docker compose -f monitoring/docker-compose.yml restart grafana
   ```

2. 수동으로 대시보드 임포트:
   - Grafana → Dashboards → New → Import
   - [grafana/dashboards/](grafana/dashboards/) 폴더의 JSON 파일 업로드

---

### 포트 충돌

**증상:** 포트가 이미 사용 중이라는 에러

**해결:**

포트 변경 ([docker-compose.yml](docker-compose.yml)):
```yaml
grafana:
  ports:
    - "3001:3000"  # 3000 대신 3001 사용
```

---

## 리소스 사용량

### 메모리
- Loki: ~200MB
- Promtail: ~50MB
- Grafana: ~200MB
- Prometheus: ~200MB
- **총합: ~650MB**

### 디스크
- 로그 저장 (Loki): ~1GB/월 (압축 후)
- 메트릭 저장 (Prometheus): ~500MB/월
- Grafana 데이터: ~100MB
- **총합: ~1.6GB/월**

### CPU
- 평상시: < 5%
- 쿼리 실행 시: 10-20%

---

## 보안

### 네트워크 격리

모든 서비스는 내부 네트워크(`monitoring`)에서 동작:
```yaml
networks:
  monitoring:
    driver: bridge
```

Grafana만 포트 3000을 외부에 노출합니다.
Prometheus(9090)와 Loki(3100)는 localhost에서만 접근 가능합니다.

---

### 인증

**Grafana:**
- 기본 인증 활성화
- 회원가입 비활성화 (`GF_USERS_ALLOW_SIGN_UP=false`)
- 최초 로그인 시 비밀번호 변경 필수

**Loki:**
- 인증 비활성화 (`auth_enabled: false`)
- 내부 네트워크만 접근 가능

**Prometheus:**
- 인증 없음 (내부 네트워크만 접근 가능)
- `/metrics` 엔드포인트는 `METRICS_AUTH_TOKEN` 환경 변수로 선택적 Bearer 인증 가능

---

### 데이터

- 로그는 로컬에만 저장 (외부 전송 없음)
- API 키는 로그에 자동 마스킹됨
- 민감한 정보는 JSON 필드에서 제외

---

## 관련 문서

- **[../.claude/MONITORING_PLAN.md](../.claude/MONITORING_PLAN.md)** - 모니터링 계획 상세
- **[Loki 공식 문서](https://grafana.com/docs/loki/latest/)**
- **[Promtail 공식 문서](https://grafana.com/docs/loki/latest/clients/promtail/)**
- **[Grafana 공식 문서](https://grafana.com/docs/grafana/latest/)**
- **[Prometheus 공식 문서](https://prometheus.io/docs/)**
- **[LogQL 쿼리 가이드](https://grafana.com/docs/loki/latest/logql/)**
- **[PromQL 쿼리 가이드](https://prometheus.io/docs/prometheus/latest/querying/basics/)**

---

**버전**: 3.0
**최종 업데이트**: 2026-02-16
