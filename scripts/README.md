# Scripts

실행 및 관리 스크립트 (3개)

---

## 스크립트 목록

| 스크립트 | 용도 |
|----------|------|
| `setup.sh` | 전체 환경 설정 |
| `start.sh` | Docker 서비스 관리 |
| `test.sh` | CI 테스트 |

---

## 1. setup.sh - 환경 설정

**최초 1회 실행** (환경 변수 + 의존성 + Docker 빌드)

```bash
./scripts/setup.sh
```

**수행 작업:**
1. `.env` 파일 생성/검증
2. Python 의존성 설치
3. Docker 확인
4. 디렉토리 생성
5. Docker 이미지 빌드

---

## 2. start.sh - 서비스 관리

**Docker 전체 스택 실행/관리**

```bash
# 서비스 시작
./scripts/start.sh

# 서비스 중지
./scripts/start.sh --stop

# 로그 보기
./scripts/start.sh --logs

# 상태 확인
./scripts/start.sh --status

# 도움말
./scripts/start.sh --help
```

**실행되는 서비스:**
- Trading Bot
- PostgreSQL
- Go Backend API
- Grafana + Loki + Promtail (모니터링)

**접속 정보:**
- Grafana: http://localhost:3000 (admin/admin123)
- Backend: http://localhost:8080/api/health
- Database: localhost:5432

---

## 3. test.sh - 테스트

**pytest 기반 테스트**

```bash
# 빠른 테스트 (기본)
./scripts/test.sh

# 커버리지 포함
./scripts/test.sh --coverage

# CI 환경 (lint + type + coverage)
./scripts/test.sh --ci

# 도움말
./scripts/test.sh --help
```

---

## 빠른 시작

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

---

## 트러블슈팅

### 실행 권한 에러
```bash
chmod +x scripts/*.sh
```

### Docker 에러
```bash
# Docker 실행 확인
docker info

# Docker 재시작 (Linux)
sudo systemctl restart docker
```

### .env 에러
```bash
# .env 파일 확인
cat .env

# 예시 파일에서 복사
cp .env.example .env
```

---

## 관련 문서

- [../docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md) - 상세 설정 가이드
- [../docs/TEST_GUIDE.md](../docs/TEST_GUIDE.md) - 테스트 가이드

---

**마지막 업데이트:** 2026-01-20
