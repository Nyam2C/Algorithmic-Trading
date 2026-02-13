# Documentation Index

Algorithmic Trading 프로젝트의 모든 문서는 이 폴더에서 관리됩니다.

---

## 빠른 시작

### 처음 사용하는 경우 (추천 순서)

#### 1. [QUICKSTART.md](QUICKSTART.md)
**30초 빠른 시작 가이드 (원-커맨드)**

- `./scripts/setup.sh` 한 번으로 전체 환경 설정
- `./scripts/start.sh` 한 번으로 서비스 시작
- Docker Compose 계층화 설명
- 사용 시나리오별 예시 (개발/모니터링/프로덕션)

**대상:** 빠르게 시작하고 싶은 모든 사용자

---

#### 2. [TEST_NOW.md](TEST_NOW.md)
**API 키 없이 지금 바로 테스트**

- 구조 검증: `./scripts/test-structure.sh`
- 실행 테스트: `./scripts/test-quick.sh`
- DB + 모니터링 자동 초기화 확인
- Docker Compose 계층화 작동 확인

**대상:** API 키가 없거나 구조만 먼저 확인하고 싶은 사용자

---

### 기존 사용자 가이드

#### [SETUP_GUIDE.md](SETUP_GUIDE.md)
**환경 설정 완벽 가이드**

- 초기 환경 설정 방법 (Python, Docker, DB)
- API 키 발급 가이드
- 설정 모드별 설명 (전체/개발/Docker)
- 트러블슈팅 가이드
- 고급 설정 옵션

**대상:** 상세한 설정이 필요한 사용자

---

#### [TEST_GUIDE.md](TEST_GUIDE.md)
**테스트 실행 및 작성 가이드**

- 테스트 실행 방법
- 1860+ 테스트 케이스 설명
- 코드 커버리지 확인
- 테스트 작성 가이드 (Unit/Async/Mock/Fixture)
- 디버깅 방법

**대상:** 개발자, 테스트 작성자

---

### 모니터링 가이드

#### [../monitoring/README.md](../monitoring/README.md)
**모니터링 시스템 사용 가이드**

- Grafana + Loki + Promtail 설치 및 설정
- 3개 대시보드 설명 (Trading Overview, AI Signals, System Health)
- LogQL 쿼리 예시
- 트러블슈팅 및 관리 명령어

**대상:** 모니터링 시스템을 설정하고 사용하는 사용자

---

### 개발 문서 (../.claude/)

프로젝트 루트의 `.claude/` 폴더에 있는 문서:

#### [PROJECT_OVERVIEW.md](../.claude/PROJECT_OVERVIEW.md)
- 전체 아키텍처 및 모듈 상세
- 구현 체크리스트 (Phase 5-9)
- API 레퍼런스, 멀티봇 아키텍처

#### [CLAUDE.md](../.claude/CLAUDE.md)
- 코딩 컨벤션 및 개발 원칙
- 테스트/리뷰 기준
- Common Pitfalls

---

## 문서 읽는 순서

### 처음 시작하는 경우 (원-커맨드 방식)
1. **[QUICKSTART.md](QUICKSTART.md)** - 30초 빠른 시작
2. **[TEST_NOW.md](TEST_NOW.md)** - API 키 없이 테스트
3. **[../README.md](../README.md)** - 프로젝트 개요

### 상세 설정이 필요한 경우
1. **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - 환경 설정
2. **[TEST_GUIDE.md](TEST_GUIDE.md)** - 테스트 방법

### 개발하는 경우
1. **[TEST_GUIDE.md](TEST_GUIDE.md)** - 테스트 방법
2. **[../.claude/PROJECT_OVERVIEW.md](../.claude/PROJECT_OVERVIEW.md)** - 전체 아키텍처 및 구현 상세

---

---

## 문서별 주요 내용

### QUICKSTART.md (원-커맨드)
```
- 30초 빠른 시작: ./scripts/setup.sh
- 서비스 시작: ./scripts/start.sh
- 테스트 실행: ./scripts/test.sh
- Docker Compose 계층화 설명
- 사용 시나리오 (개발, 모니터링, 통합 테스트)
- 자동 초기화 (DB + 모니터링)
```

### TEST_NOW.md (API 키 불필요)
```
- 구조 검증: ./scripts/test-structure.sh (10초)
- 실행 테스트: ./scripts/test-quick.sh (1분)
- DB 자동 초기화 확인
- Grafana 자동 설정 확인
- Docker Compose 계층화 작동 확인
```

### SETUP_GUIDE.md
```
- 시스템 요구사항 (Python 3.10+, Docker)
- API 키 발급 (Binance, Gemini, Discord)
- 설정 스크립트 사용법
- 데이터베이스 초기화
- 검증 및 테스트 실행
- 트러블슈팅 (20+ 문제 해결법)
```

### TEST_GUIDE.md
```
- 테스트 실행 (./scripts/run-tests.sh)
- 테스트 구조 (conftest.py, test_*.py)
- 커버리지 목표 (94%+)
- 1860+ 테스트 케이스 상세
- CI/CD 통합
- 테스트 작성 패턴
```

---

## 문서 유지보수

### 문서 업데이트가 필요한 경우
- 새로운 기능 추가 시
- API 변경 시
- 설정 옵션 변경 시
- 새로운 트러블슈팅 케이스 발견 시

### 문서 작성 원칙
- 명확하고 간결하게
- 코드 예제 포함
- 스크린샷/다이어그램 활용 (필요시)
- 단계별 가이드 제공
- 트러블슈팅 섹션 포함

---

## 추가 예정 문서

- **API_REFERENCE.md** - FastAPI 엔드포인트 문서
- **DEPLOYMENT.md** - 프로덕션 배포 가이드
- **BACKUP.md** - 백업 및 복구 가이드
- **SECURITY.md** - 보안 설정 가이드

---

## 외부 참조

### 공식 문서
- [Python](https://docs.python.org/3/)
- [Docker](https://docs.docker.com/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [pytest](https://docs.pytest.org/)

### API 문서
- [Binance Futures](https://binance-docs.github.io/apidocs/futures/en/)
- [Google Gemini AI](https://ai.google.dev/docs)
- [Discord Webhooks](https://discord.com/developers/docs/resources/webhook)

### 라이브러리
- [python-binance](https://python-binance.readthedocs.io/)
- [ta (Technical Analysis)](https://technical-analysis-library-in-python.readthedocs.io/)
- [pandas](https://pandas.pydata.org/docs/)

---

## 문서 구조

```
docs/
├── README.md              # 이 파일 (문서 인덱스)
├── QUICKSTART.md          # 원-커맨드 빠른 시작
├── TEST_NOW.md            # API 키 없이 테스트
├── SETUP_GUIDE.md         # 상세 설정 가이드
└── TEST_GUIDE.md          # 테스트 가이드
```

---

**문서 버전:** 3.0
**마지막 업데이트:** 2026-02-14
