# 🚀 Quick Start Guide

원-커맨드로 전체 환경을 설정하고 실행하는 가이드입니다.

## 📋 요구사항

- Docker & Docker Compose
- Git
- (선택) Python 3.11+
- (선택) Go 1.21+

## ⚡ 30초 빠른 시작

```bash
# 1. 저장소 클론
git clone <repository-url>
cd Algorithmic-Trading

# 2. 전체 환경 설정 (최초 1회)
./scripts/bot.sh setup

# 3. 원하는 스택 선택 실행
./scripts/bot.sh dev:all        # 전체 스택
./scripts/bot.sh dev:monitor    # 봇 + 모니터링
./scripts/bot.sh dev            # 봇만 (빠름)
```

---

## 🎯 명령어 가이드

### Setup (최초 1회)

```bash
./scripts/bot.sh setup
```

**자동으로 수행:**
- ✅ `.env` 파일 생성 (없으면)
- ✅ Python 의존성 설치 확인
- ✅ Go 의존성 확인 (백엔드)
- ✅ Docker 환경 확인
- ✅ 로그 디렉토리 생성

---

### 개발 환경 실행

#### 1️⃣ 봇만 실행 (가장 빠름)

```bash
./scripts/bot.sh dev
```

**시작되는 서비스:**
- 🤖 Trading Bot
- 🗄️ PostgreSQL

**시작 시간:** ~10초
**메모리:** ~500MB

---

#### 2️⃣ 봇 + 모니터링

```bash
./scripts/bot.sh dev:monitor
```

**시작되는 서비스:**
- 🤖 Trading Bot
- 🗄️ PostgreSQL
- 📊 Grafana (http://localhost:3000)
- 📝 Loki
- 🚀 Promtail

**시작 시간:** ~20초
**메모리:** ~1.5GB

**Grafana 접속:**
- URL: http://localhost:3000
- ID: admin
- PW: admin123

---

#### 3️⃣ 봇 + Go API 백엔드

```bash
./scripts/bot.sh dev:backend
```

**시작되는 서비스:**
- 🤖 Trading Bot
- 🗄️ PostgreSQL
- ⚡ Go API Server (http://localhost:8080)

**시작 시간:** ~15초
**메모리:** ~800MB

**API 확인:**
```bash
curl http://localhost:8080/api/health
```

---

#### 4️⃣ 전체 스택 (All-in-One)

```bash
./scripts/bot.sh dev:all
```

**시작되는 서비스:**
- 🤖 Trading Bot
- 🗄️ PostgreSQL
- ⚡ Go API Server
- 📊 Grafana
- 📝 Loki
- 🚀 Promtail

**시작 시간:** ~30초
**메모리:** ~2GB

**접속 정보:**
- Backend API: http://localhost:8080/api/health
- Grafana: http://localhost:3000 (admin/admin123)
- PostgreSQL: localhost:5432

---

### 중지 및 관리

```bash
# 전체 중지
./scripts/bot.sh dev:down

# 전체 로그 확인
./scripts/bot.sh dev:logs

# 봇 로그만 확인
docker logs -f trading-bot

# 상태 확인
./scripts/bot.sh status

# 임시 파일 정리
./scripts/bot.sh clean
```

---

### 프로덕션 실행

```bash
./scripts/bot.sh prod
```

**주의사항:**
- ⚠️ TESTNET=false (실제 거래)
- ⚠️ 실행 전 확인 프롬프트
- ⚠️ restart: always 적용
- ⚠️ 리소스 제한 적용

---

## 📊 Docker Compose 계층 구조

프로젝트는 상황별로 최적화된 Docker Compose 파일들을 조합하여 사용합니다.

```
docker-compose.yml              # 기본 (Bot + DB)
docker-compose.dev.yml          # 개발 환경
docker-compose.monitoring.yml   # 모니터링
docker-compose.backend.yml      # Go API
docker-compose.prod.yml         # 프로덕션
```

### 조합 예시

```bash
# Bot + DB만
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Bot + DB + Monitoring
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.monitoring.yml up

# 전체 스택
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.backend.yml \
  -f docker-compose.monitoring.yml up
```

---

## 🔧 자동 초기화

### DB 자동 초기화

PostgreSQL 컨테이너가 시작되면 자동으로:
- ✅ `db/init.sql` 실행
- ✅ 테이블 생성 (trades, positions, signals 등)
- ✅ 인덱스 생성
- ✅ 확장 기능 활성화

### 모니터링 자동 초기화

Grafana/Loki 컨테이너가 시작되면 자동으로:
- ✅ Loki 데이터소스 연결
- ✅ 대시보드 3개 자동 Import
  - Trading Overview
  - AI Signals Analysis
  - System Health
- ✅ Provisioning 설정 적용

---

## 🎯 사용 시나리오

### 시나리오 1: AI 신호 로직 개발

```bash
# 빠른 시작 (10초)
./scripts/bot.sh dev

# 코드 수정
vim src/ai/gemini_ai.py

# 재시작
docker restart trading-bot

# 로그 확인
docker logs -f trading-bot
```

---

### 시나리오 2: 모니터링 대시보드 확인

```bash
# 모니터링 포함 시작
./scripts/bot.sh dev:monitor

# Grafana 접속
open http://localhost:3000

# 대시보드 확인
# - Trading Overview
# - AI Signals
# - System Health
```

---

### 시나리오 3: Go API 개발

```bash
# 백엔드 포함 시작
./scripts/bot.sh dev:backend

# API 테스트
curl http://localhost:8080/api/health
curl http://localhost:8080/api/v1/bot/status

# Go 코드 수정
vim backend/cmd/api/main.go

# 재빌드 & 재시작
docker compose -f docker-compose.yml \
  -f docker-compose.backend.yml up -d --build backend
```

---

### 시나리오 4: 통합 테스트

```bash
# 전체 스택 시작
./scripts/bot.sh dev:all

# 테스트 실행
./scripts/bot.sh test

# 로그 확인
./scripts/bot.sh dev:logs
```

---

## 📖 자세한 문서

- 전체 문서: [README.md](README.md)
- DB 스키마: [db/README.md](db/README.md)
- 모니터링: [monitoring/README.md](monitoring/README.md)
- Go 백엔드: [backend/README.md](backend/README.md)
- 개발 가이드: [.claude/DEVELOPMENT_PLAN.md](.claude/DEVELOPMENT_PLAN.md)

---

## ❓ 문제 해결

### Docker가 시작되지 않을 때

```bash
# Docker 데몬 확인
docker info

# WSL2 (Windows)의 경우
# Docker Desktop에서 WSL Integration 활성화
```

### .env 파일 오류

```bash
# .env 파일 재생성
rm .env
./scripts/bot.sh setup

# 필수 변수 확인
cat .env
```

### 포트 충돌

```bash
# 이미 사용 중인 포트 확인
lsof -i :3000  # Grafana
lsof -i :5432  # PostgreSQL
lsof -i :8080  # Backend API

# 해당 프로세스 종료 또는 docker-compose.yml에서 포트 변경
```

---

## 🎉 완료!

이제 원-커맨드로 전체 환경을 관리할 수 있습니다.

```bash
./scripts/bot.sh setup      # 최초 1회
./scripts/bot.sh dev:all    # 전체 시작
./scripts/bot.sh dev:down   # 전체 중지
```

Happy Trading! 🚀
