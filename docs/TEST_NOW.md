# 🧪 API 키 없이 지금 바로 테스트하기

API 키가 없어도 **Docker Compose 계층화**와 **자동 초기화**가 제대로 작동하는지 확인할 수 있습니다.

---

## ✅ 방법 1: 구조 검증 (가장 빠름 - 10초)

Docker Compose 파일들이 제대로 작성되었는지 검증합니다.

```bash
./scripts/test-structure.sh
```

**확인 내용:**
- ✅ 파일 구조 (5개 docker-compose 파일)
- ✅ 문법 검증 (docker compose config)
- ✅ 서비스 구성 (postgres, loki, grafana, backend 등)
- ✅ 네트워크 설정 (trading_net)
- ✅ DB 자동 초기화 설정
- ✅ Health Check 설정

**예상 결과:**
```
✅ docker-compose.yml 존재
✅ docker-compose.dev.yml 존재
✅ docker-compose.monitoring.yml 존재
✅ docker-compose.backend.yml 존재
✅ docker-compose.prod.yml 존재
✅ 기본 구성 - 문법 OK
✅ 개발 환경 - 문법 OK
✅ 모니터링 - 문법 OK
✅ 백엔드 - 문법 OK
✅ 전체 스택 - 문법 OK
✅ 프로덕션 - 문법 OK
✅ PostgreSQL 자동 초기화 설정됨
✅ Health Check 설정됨 (4 개)
```

---

## ✅ 방법 2: 실제 실행 테스트 (1분)

DB + 모니터링 스택을 실제로 실행해서 자동 초기화 확인합니다.

```bash
./scripts/test-quick.sh
```

**시작되는 서비스:**
- 🗄️ PostgreSQL (DB)
- 📝 Loki (로그 저장소)
- 📊 Grafana (대시보드)
- 🚀 Promtail (로그 수집)

**확인 내용:**
- ✅ PostgreSQL이 자동으로 `db/init.sql` 실행
- ✅ 테이블 자동 생성 (trades, positions, signals 등)
- ✅ Grafana 자동 시작
- ✅ Loki 데이터소스 자동 연결
- ✅ 대시보드 3개 자동 Import

**예상 결과:**
```
✅ PostgreSQL 준비 완료
✅ Grafana 준비 완료
✅ Loki 준비 완료

📊 Grafana 대시보드:
   URL: http://localhost:3000
   ID:  admin
   PW:  admin123
```

---

## ✅ 방법 3: 수동 확인 (상세)

### 3-1. DB + 모니터링만 시작

```bash
docker compose \
    -f docker-compose.yml \
    -f docker-compose.monitoring.yml \
    up -d postgres loki grafana promtail
```

### 3-2. PostgreSQL 자동 초기화 확인

```bash
# DB 접속
docker exec -it trading-db psql -U trading -d trading

# 테이블 목록 확인
\dt

# 예상 결과:
#           List of relations
#  Schema |      Name       | Type  |  Owner
# --------+-----------------+-------+---------
#  public | ai_signals      | table | trading
#  public | positions       | table | trading
#  public | system_metrics  | table | trading
#  public | trades          | table | trading

# trades 테이블 구조 확인
\d trades

# 종료
\q
```

### 3-3. Grafana 자동 설정 확인

1. 브라우저에서 **http://localhost:3000** 접속
2. ID: `admin` / PW: `admin123` 로그인
3. 좌측 메뉴 → **Connections** → **Data sources**
   - ✅ **Loki** 데이터소스가 자동으로 추가되어 있어야 함
4. 좌측 메뉴 → **Dashboards**
   - ✅ **Trading Overview** (자동 Import)
   - ✅ **AI Signals Analysis** (자동 Import)
   - ✅ **System Health** (자동 Import)

### 3-4. Loki 상태 확인

```bash
curl http://localhost:3100/ready
# 예상 결과: ready
```

### 3-5. 실행 중인 컨테이너 확인

```bash
docker ps --filter "name=trading"
```

**예상 결과:**
```
CONTAINER ID   IMAGE                    STATUS         PORTS
abc123...      postgres:15-alpine       Up 2 minutes   0.0.0.0:5432->5432/tcp
def456...      grafana/grafana:10.2.3   Up 2 minutes   0.0.0.0:3000->3000/tcp
ghi789...      grafana/loki:2.9.3       Up 2 minutes   0.0.0.0:3100->3100/tcp
jkl012...      grafana/promtail:2.9.3   Up 2 minutes
```

### 3-6. 종료

```bash
docker compose \
    -f docker-compose.yml \
    -f docker-compose.monitoring.yml \
    down
```

---

## ✅ 방법 4: 계층화 테스트

각 조합별로 어떤 서비스가 시작되는지 확인합니다.

### 기본 (Bot + DB)
```bash
docker compose -f docker-compose.yml config --services
# 예상: postgres, trading-bot
```

### 개발 환경
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --services
# 예상: postgres, trading-bot
```

### 모니터링 추가
```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml config --services
# 예상: postgres, trading-bot, loki, promtail, grafana
```

### 백엔드 추가
```bash
docker compose -f docker-compose.yml -f docker-compose.backend.yml config --services
# 예상: postgres, trading-bot, backend
```

### 전체 스택
```bash
docker compose \
    -f docker-compose.yml \
    -f docker-compose.dev.yml \
    -f docker-compose.backend.yml \
    -f docker-compose.monitoring.yml \
    config --services

# 예상: postgres, trading-bot, backend, loki, promtail, grafana
```

---

## 🎯 무엇을 확인할 수 있나요?

### ✅ Docker Compose 계층화
- **5개 파일**이 제대로 분리되어 있는지
- **상황별 조합**이 문법 오류 없이 작동하는지
- **네트워크**가 공통으로 설정되었는지

### ✅ 자동 초기화
- **PostgreSQL**: `db/init.sql`이 자동 실행되는지
- **테이블**: trades, positions, signals 등이 자동 생성되는지
- **Grafana**: Loki 데이터소스가 자동 연결되는지
- **대시보드**: 3개가 자동 Import 되는지

### ✅ Health Check
- PostgreSQL, Grafana, Loki, Backend가 정상 작동하는지
- 의존성 순서대로 시작되는지 (postgres → bot → backend)

---

## 📋 체크리스트

테스트하면서 이것들을 확인하세요:

- [ ] `./scripts/test-structure.sh` 실행 → 모든 ✅ 확인
- [ ] `./scripts/test-quick.sh` 실행 → 서비스 시작 확인
- [ ] Grafana 접속 → Loki 데이터소스 자동 연결 확인
- [ ] Grafana → 대시보드 3개 자동 Import 확인
- [ ] PostgreSQL 접속 → 테이블 자동 생성 확인
- [ ] `docker ps` → 컨테이너 정상 실행 확인
- [ ] `docker compose down` → 정상 종료 확인

---

## 🔥 결과

모든 테스트가 통과하면:

✅ **원-커맨드 셋업 구현 완료**
✅ **Docker Compose 계층화 완료**
✅ **자동 초기화 (DB + 모니터링) 완료**

이제 API 키만 추가하면 실제 트레이딩 봇을 바로 실행할 수 있습니다! 🚀

---

## 💡 다음 단계

API 키를 추가한 후:

```bash
# .env 파일 편집
vim .env

# 전체 스택 실행
./scripts/start.sh
```

Happy Testing! 🎉

---

**마지막 업데이트:** 2026-02-14
