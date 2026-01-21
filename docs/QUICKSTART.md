# 🚀 Quick Start Guide

원-커맨드로 전체 환경을 설정하고 실행하는 가이드입니다.

## 📋 요구사항

- Docker & Docker Compose
- Git
- Python 3.10+
- (선택) Go 1.21+

## ⚡ 30초 빠른 시작

```bash
# 1. 저장소 클론
git clone <repository-url>
cd Algorithmic-Trading

# 2. 전체 환경 설정 (최초 1회)
./scripts/setup.sh

# 3. 서비스 시작
./scripts/start.sh

# 4. 상태 확인
./scripts/start.sh --status

# 5. 로그 보기
./scripts/start.sh --logs
```

---

## 🎯 명령어 가이드

### Setup (최초 1회)

```bash
./scripts/setup.sh
```

**자동으로 수행:**
- ✅ `.env` 파일 생성 (없으면)
- ✅ Python 의존성 설치 확인
- ✅ Docker 환경 확인
- ✅ 로그 디렉토리 생성

---

### 서비스 시작

```bash
./scripts/start.sh
```

**시작되는 서비스:**
- 🤖 Trading Bot
- 🗄️ PostgreSQL

---

### 서비스 관리

```bash
# 서비스 시작
./scripts/start.sh

# 서비스 중지
./scripts/start.sh --stop

# 로그 보기
./scripts/start.sh --logs

# 상태 확인
./scripts/start.sh --status
```

---

### 테스트 실행

```bash
# 빠른 테스트
./scripts/test.sh

# 커버리지 포함
./scripts/test.sh --coverage

# CI 환경 (lint + type + coverage)
./scripts/test.sh --ci
```

---

### Grafana 접속 (모니터링)

**URL:** http://localhost:3000
**ID:** admin
**PW:** admin123

---

### 프로덕션 실행

```bash
# 프로덕션 모드 (.env에서 TESTNET=false 설정 필요)
./scripts/start.sh
```

**주의사항:**
- ⚠️ BINANCE_TESTNET=false (실제 거래)
- ⚠️ 실전 API 키 필요
- ⚠️ 충분한 Testnet 검증 후 전환

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
# 서비스 시작
./scripts/start.sh

# 코드 수정
vim src/ai/gemini.py

# 재시작
docker restart trading-bot

# 로그 확인
docker logs -f trading-bot
```

---

### 시나리오 2: 모니터링 대시보드 확인

```bash
# 서비스 시작
./scripts/start.sh

# Grafana 접속
open http://localhost:3000

# 대시보드 확인
# - Trading Overview
# - AI Signals
# - System Health
```

---

### 시나리오 3: 테스트 실행

```bash
# 테스트 실행
./scripts/test.sh

# 커버리지 포함
./scripts/test.sh --coverage

# 로그 확인
./scripts/start.sh --logs
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
./scripts/setup.sh

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
./scripts/setup.sh          # 최초 1회
./scripts/start.sh          # 서비스 시작
./scripts/start.sh --stop   # 서비스 중지
./scripts/test.sh           # 테스트 실행
```

Happy Trading! 🚀

---

**마지막 업데이트:** 2026-01-21
**상태:** Phase 2 Testnet 검증 진행 중
