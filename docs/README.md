# Documentation

High-Win Survival System 프로젝트 문서 모음

---

## 📚 문서 목록

### 사용자 가이드

#### [SETUP_GUIDE.md](SETUP_GUIDE.md)
**환경 설정 완벽 가이드**

- 초기 환경 설정 방법 (Python, Docker, DB)
- API 키 발급 가이드
- 설정 모드별 설명 (전체/개발/Docker)
- 트러블슈팅 가이드
- 고급 설정 옵션

**대상:** 처음 프로젝트를 설정하는 사용자

---

#### [TEST_GUIDE.md](TEST_GUIDE.md)
**테스트 실행 및 작성 가이드**

- 테스트 실행 방법
- 64개 테스트 케이스 설명
- 코드 커버리지 확인
- 테스트 작성 가이드 (Unit/Async/Mock/Fixture)
- 디버깅 방법

**대상:** 개발자, 테스트 작성자

---

#### [QUICK_START.md](QUICK_START.md)
**빠른 참조용 명령어 모음**

- 자주 사용하는 명령어 치트시트
- 설정/실행/테스트/DB 명령어
- Docker 명령어
- 트러블슈팅 빠른 해결법

**대상:** 반복 작업 시 빠른 참조가 필요한 사용자

---

### 개발 계획 문서 (../.claude/)

프로젝트 루트의 `.claude/` 폴더에 있는 개발 계획 문서:

#### TRADING_PLAN.md
- 트레이딩 전략 상세 설명
- 리스크 관리 방법
- 파라미터 설정 근거

#### DEVELOPMENT_PLAN.md
- 전체 개발 로드맵
- 스프린트별 목표
- 아키텍처 설계

#### IMPLEMENTATION_PLAN.md
- 스프린트별 구현 계획
- 완료 체크리스트
- 기술 스택 선정 이유

#### PROMPT_ENGINEERING.md
- Gemini AI 프롬프트 설계
- 신호 생성 로직
- 프롬프트 최적화 방법

---

## 📖 문서 읽는 순서

### 처음 시작하는 경우
1. **[../README.md](../README.md)** - 프로젝트 개요
2. **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - 환경 설정
3. **[QUICK_START.md](QUICK_START.md)** - 명령어 참조

### 개발하는 경우
1. **[TEST_GUIDE.md](TEST_GUIDE.md)** - 테스트 방법
2. **[../.claude/DEVELOPMENT_PLAN.md](../.claude/DEVELOPMENT_PLAN.md)** - 개발 계획
3. **[../.claude/IMPLEMENTATION_PLAN.md](../.claude/IMPLEMENTATION_PLAN.md)** - 구현 가이드

### 전략 이해하는 경우
1. **[../.claude/TRADING_PLAN.md](../.claude/TRADING_PLAN.md)** - 트레이딩 전략
2. **[../.claude/PROMPT_ENGINEERING.md](../.claude/PROMPT_ENGINEERING.md)** - AI 프롬프트

---

## 🔍 문서별 주요 내용

### SETUP_GUIDE.md
```
- 시스템 요구사항 (Python 3.11+, Docker)
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
- 64개 테스트 케이스 상세
- CI/CD 통합
- 테스트 작성 패턴
```

### QUICK_START.md
```
- 초기 설정 명령어
- 실행 명령어 (Docker/로컬)
- 테스트 명령어
- DB 명령어
- Docker 명령어
- 트러블슈팅 빠른 해결
```

---

## 🛠️ 문서 유지보수

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

## 📝 추가 예정 문서

### Sprint 2+
- **API_REFERENCE.md** - FastAPI 엔드포인트 문서
- **DEPLOYMENT.md** - 프로덕션 배포 가이드
- **MONITORING.md** - 모니터링 및 알림 설정
- **BACKUP.md** - 백업 및 복구 가이드
- **SECURITY.md** - 보안 설정 가이드

---

## 🔗 외부 참조

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

**문서 버전:** 1.0
**마지막 업데이트:** 2026-01-16
**상태:** Sprint 1 완료
