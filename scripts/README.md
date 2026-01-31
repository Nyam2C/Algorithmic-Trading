# Scripts

실행 및 관리 스크립트

---

## 스크립트 목록

| 스크립트 | 용도 |
|----------|------|
| `setup.sh` | 전체 환경 설정 (최초 1회) |
| `start.sh` | Docker 전체 스택 시작/관리 |
| `stop.sh` | Docker 서비스 종료 |
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

## 2. start.sh - 전체 스택 시작/관리

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

### Docker Compose 구성

`start.sh`는 다음 5개의 Docker Compose 파일을 조합하여 실행합니다:

| 파일 | 설명 |
|------|------|
| `deploy/docker-compose.yml` | 기본 서비스 (PostgreSQL, Trading Bot) |
| `deploy/docker-compose.dev.yml` | 개발 환경 설정 (포트, 볼륨) |
| `deploy/docker-compose.api.yml` | FastAPI REST API 서버 |
| `deploy/docker-compose.n8n.yml` | n8n 워크플로우 자동화 |
| `deploy/docker-compose.monitoring.yml` | Grafana + Loki + Promtail |

### 서비스 접속 정보

| 서비스 | URL | 설명 |
|--------|-----|------|
| **n8n** | http://localhost:5678 | 워크플로우 자동화 |
| **Grafana** | http://localhost:3000 | 로그 모니터링 (admin/admin123) |
| **API** | http://localhost:8000/health | REST API 헬스체크 |
| **API Docs** | http://localhost:8000/docs | Swagger UI (개발 모드) |
| **Database** | localhost:5432 | PostgreSQL |
| **Loki** | http://localhost:3100 | 로그 저장소 (내부) |

### 실행되는 서비스

1. **PostgreSQL** - 거래 데이터 저장
2. **Trading Bot** - 트레이딩 봇 (Python)
3. **FastAPI** - REST API 서버
4. **n8n** - 워크플로우 자동화
5. **Grafana** - 대시보드 및 시각화
6. **Loki** - 로그 저장소
7. **Promtail** - 로그 수집 에이전트

---

## 3. stop.sh - 서비스 종료

**Docker 전체 스택 종료**

```bash
# 서비스만 종료 (데이터 유지)
./scripts/stop.sh

# 볼륨까지 삭제 (DB 데이터 포함)
./scripts/stop.sh --volumes
./scripts/stop.sh -v

# 도움말
./scripts/stop.sh --help
```

---

## 4. test.sh - 테스트

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

# 5. 서비스 종료
./scripts/stop.sh
```

---

## 서비스 접속 후 할 일

### n8n 초기 설정
1. http://localhost:5678 접속
2. 계정 생성 (이메일, 비밀번호)
3. 워크플로우 임포트 또는 생성

### Grafana 대시보드 확인
1. http://localhost:3000 접속 (admin/admin123)
2. 좌측 Dashboards → Trading Overview 선택
3. 로그 스트리밍 확인

### API 테스트
```bash
# 헬스체크
curl http://localhost:8000/health

# 봇 목록 조회
curl http://localhost:8000/api/bots

# Swagger UI에서 테스트
# http://localhost:8000/docs
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

### 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :5678   # n8n
lsof -i :3000   # Grafana
lsof -i :8000   # API
lsof -i :5432   # PostgreSQL

# 프로세스 종료
kill -9 <PID>
```

### .env 에러
```bash
# .env 파일 확인
cat .env

# 예시 파일에서 복사
cp .env.example .env
```

### n8n 연결 실패
```bash
# n8n 컨테이너 로그 확인
docker logs trading-n8n

# n8n 재시작
docker restart trading-n8n
```

---

## 관련 문서

- [../docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md) - 상세 설정 가이드
- [../docs/TEST_GUIDE.md](../docs/TEST_GUIDE.md) - 테스트 가이드
- [../monitoring/README.md](../monitoring/README.md) - 모니터링 가이드

---

**마지막 업데이트:** 2026-01-31
