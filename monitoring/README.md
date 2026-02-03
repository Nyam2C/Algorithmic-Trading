# Monitoring Stack

Grafana + Loki + Promtail 기반 로그 모니터링 시스템

---

## 🎯 개요

트레이딩 봇의 실시간 로그를 수집하고 시각화하는 모니터링 스택입니다.

**구성 요소:**
- **Loki**: 로그 저장소 (30일 보관)
- **Promtail**: 로그 수집 에이전트
- **Grafana**: 대시보드 및 시각화

---

## 🚀 빠른 시작

### 1. 모니터링 스택 시작

```bash
# 서비스 시작 (모니터링 포함)
./scripts/start.sh

# 또는 직접 실행
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.monitoring.yml up -d
```

### 2. Grafana 접속

```
URL: http://localhost:3000
ID: admin
PW: admin123
```

### 3. 대시보드 확인

Grafana 좌측 메뉴 → Dashboards에서 다음 대시보드 확인:

1. **Trading Overview** - 거래 현황 및 신호 분포
2. **AI Signals** - AI 신호 분석 및 신뢰도
3. **System Health** - 시스템 상태 및 에러 로그

---

## 📊 대시보드 설명

### 1. Trading Overview

**주요 패널:**
- LONG/SHORT/WAIT 신호 발생 횟수 (24시간)
- 신호 분포 파이 차트
- 거래 타임라인 (진입/청산)
- 신호 발생 빈도 (시간별)
- Discord 알림 로그

**용도:**
- 전체 트레이딩 활동 모니터링
- 신호 패턴 분석
- 거래 이력 추적

---

### 2. AI Signals

**주요 패널:**
- 신호 분포 (LONG/SHORT/WAIT 비율)
- 평균 신뢰도 게이지
- 신호 발생 추이
- LONG/SHORT 신호 상세 로그
- RSI 추이 차트

**용도:**
- AI 신호 품질 분석
- 신호 신뢰도 추적
- 기술적 지표 모니터링

---

### 3. System Health

**주요 패널:**
- 에러 발생 횟수 (1시간)
- Bot 상태 (HEARTBEAT)
- API 성공률
- Discord 알림 성공 횟수
- 에러 로그 (실시간)
- 로그 레벨별 발생 빈도
- 에러 발생률 추이
- API 호출 로그

**용도:**
- 시스템 안정성 모니터링
- 에러 추적 및 디버깅
- API 상태 확인

---

## 🔍 주요 LogQL 쿼리

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

## ⚙️ 설정

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
- `logs/bot.log` - 메인 봇 로그
- `logs/error.log` - 에러 로그
- `logs/trade.log` - 거래 로그
- `logs/ai_signal.log` - AI 신호 로그

**레이블:**
- `job`: 작업 이름 (trading-bot, trading-error 등)
- `app`: 애플리케이션 이름 (trading)
- `env`: 환경 (testnet)
- `level`: 로그 레벨 (info, error, warning)
- `signal`: 신호 타입 (LONG, SHORT, WAIT)

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

## 📁 파일 구조

```
monitoring/
├── docker-compose.yml              # Docker Compose 설정
├── README.md                       # 이 파일
├── loki/
│   └── loki-config.yml             # Loki 설정
├── promtail/
│   └── promtail-config.yml         # Promtail 설정
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── loki.yml            # Loki 데이터소스
    │   └── dashboards/
    │       └── default.yml          # 대시보드 프로비저닝
    └── dashboards/
        ├── trading-overview.json   # 거래 현황 대시보드
        ├── ai-signals.json         # AI 신호 대시보드
        └── system-health.json      # 시스템 헬스 대시보드
```

---

## 🛠️ 관리 명령어

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
```

### 상태 확인

```bash
# 컨테이너 상태
docker compose -f monitoring/docker-compose.yml ps

# Loki 상태
curl http://localhost:3100/ready

# Grafana 상태
curl http://localhost:3000/api/health
```

---

## 🐛 트러블슈팅

### Grafana에서 로그가 안 보일 때

**원인:** Promtail이 로그 파일을 찾지 못함

**해결:**
1. 로그 파일이 생성되었는지 확인:
   ```bash
   ls -la logs/
   ```

2. Promtail 로그 확인:
   ```bash
   docker compose -f monitoring/docker-compose.yml logs promtail
   ```

3. 로그 파일 권한 확인:
   ```bash
   chmod 644 logs/*.log
   ```

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

## 💰 리소스 사용량

### 메모리
- Loki: ~200MB
- Promtail: ~50MB
- Grafana: ~200MB
- **총합: ~450MB**

### 디스크
- 로그 저장: ~1GB/월 (압축 후)
- Grafana 데이터: ~100MB
- **총합: ~1.1GB/월**

### CPU
- 평상시: < 5%
- 쿼리 실행 시: 10-20%

---

## 🔒 보안

### 네트워크 격리

모든 서비스는 내부 네트워크(`monitoring`)에서 동작:
```yaml
networks:
  monitoring:
    driver: bridge
```

Grafana만 포트 3000을 외부에 노출합니다.

---

### 인증

**Grafana:**
- 기본 인증 활성화
- 회원가입 비활성화 (`GF_USERS_ALLOW_SIGN_UP=false`)
- 최초 로그인 시 비밀번호 변경 필수

**Loki:**
- 인증 비활성화 (`auth_enabled: false`)
- 내부 네트워크만 접근 가능

---

### 데이터

- 로그는 로컬에만 저장 (외부 전송 없음)
- API 키는 로그에 자동 마스킹됨
- 민감한 정보는 JSON 필드에서 제외

---

## 📈 Prometheus 메트릭

트레이딩 봇은 Prometheus 메트릭을 `/metrics` 엔드포인트에서 제공합니다.

### 메트릭 접근
```bash
curl http://localhost:8000/metrics
```

### 제공되는 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `trading_trades_total` | Counter | 총 거래 수 (bot_name, side, result 레이블) |
| `trading_position_pnl_percent` | Gauge | 현재 포지션 PnL % |
| `trading_trade_duration_seconds` | Histogram | 거래 지속시간 |
| `trading_api_latency_seconds` | Histogram | API 지연시간 |
| `trading_signal_confidence` | Gauge | 시그널 신뢰도 |

### Grafana에서 Prometheus 연동

1. Grafana → Configuration → Data Sources
2. Add data source → Prometheus
3. URL: `http://localhost:9090` (Prometheus 서버 실행 시)
4. Save & Test

---

## 📚 관련 문서

- **[../.claude/MONITORING_PLAN.md](../.claude/MONITORING_PLAN.md)** - 모니터링 계획 상세
- **[Loki 공식 문서](https://grafana.com/docs/loki/latest/)**
- **[Promtail 공식 문서](https://grafana.com/docs/loki/latest/clients/promtail/)**
- **[Grafana 공식 문서](https://grafana.com/docs/grafana/latest/)**
- **[LogQL 쿼리 가이드](https://grafana.com/docs/loki/latest/logql/)**

---

**버전**: 2.0
**최종 업데이트**: 2026-02-03
