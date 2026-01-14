# 구현 계획서

**Project:** High-Win Survival System
**작성일:** 2025.12.16

---

## 1. 개발 방식

**애자일 + MVP 우선**
- 최소 기능 먼저 → 빠르게 실행 → 피드백 → 개선
- 완벽한 설계보다 동작하는 코드
- 각 스프린트마다 실행 가능한 결과물

---

## 2. MVP vs 확장 기능

### MVP (Sprint 1-4)
| 기능 | 설명 | 필수 |
|------|------|------|
| Binance 연동 | 현재가, 캔들, 주문 | ✅ |
| Gemini 신호 | LONG/SHORT/WAIT | ✅ |
| 주문 실행 | Maker 지정가 | ✅ |
| TP/SL | 자동 설정 | ✅ |
| 타임컷 | 2시간 기본 | ✅ |
| Discord 알림 | 진입/청산/에러 | ✅ |
| Docker 배포 | EC2 운영 | ✅ |

### 확장 (Sprint 5+)
| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 백테스트 | 과거 데이터 검증 | 중 |
| 조건부 타임컷 | 연장/조기청산 | 중 |
| 슬래시 명령어 | /status, /report | 하 |
| 멀티봇 | ETH, SOL | 하 |
| n8n | 오케스트레이션 | 하 |

---

## 3. 스프린트 상세

### Sprint 0: 데브옵스 환경 구축 ⬅️ 현재
**목표:** CI/CD + Docker + AWS 인프라 먼저 셋팅

| 태스크 | 상세 | 상태 |
|--------|------|------|
| 프로젝트 구조 | src/, tests/, configs/ 생성 | ⬜ |
| Git 설정 | README, .gitignore | ⬜ |
| Dockerfile | Python 3.11 이미지 | ⬜ |
| docker-compose | 봇 + PostgreSQL | ⬜ |
| .env.example | 환경 변수 템플릿 | ⬜ |
| 로컬 Docker 테스트 | Hello World 컨테이너 실행 | ⬜ |
| AWS EC2 생성 | t3.micro 인스턴스 | ⬜ |
| EC2 Docker 설치 | Docker + Docker Compose | ⬜ |
| GitHub Actions | CI/CD 파이프라인 | ⬜ |
| 배포 스크립트 | deploy.sh 작성 | ⬜ |
| 모니터링 설정 | Discord Webhook 테스트 | ⬜ |

**완료 조건:**
```
로컬 Docker 빌드 → GitHub Push → EC2 자동 배포 → Discord 알림
```

**학습 목표:**
- Docker 컨테이너화 경험
- AWS EC2 인프라 구축
- CI/CD 파이프라인 구성
- 로그 관리 및 모니터링

---

### Sprint 1: 데이터 연동
**목표:** Binance + Gemini 연결

| 태스크 | 상세 | 상태 |
|--------|------|------|
| requirements.txt | 의존성 정의 | ⬜ |
| Binance 연결 | API 클라이언트 | ⬜ |
| 현재가 조회 | get_current_price() | ⬜ |
| 캔들 조회 | get_klines() (2시간) | ⬜ |
| 지표 계산 | RSI, MA, ATR | ⬜ |
| Gemini 연결 | API 클라이언트 | ⬜ |
| 프롬프트 작성 | 시스템 + 분석 | ⬜ |
| 신호 생성 | LONG/SHORT/WAIT 파싱 | ⬜ |
| Docker 빌드 | 컨테이너에서 실행 | ⬜ |
| EC2 배포 | 실제 환경 테스트 | ⬜ |

**완료 조건:**
```
EC2에서: BTCUSDT 데이터 → Gemini 분석 → Discord로 신호 출력
```

---

### Sprint 2: 주문 실행
**목표:** Paper Trading 가능

| 태스크 | 상세 | 상태 |
|--------|------|------|
| 레버리지 설정 | 15x 격리 | ⬜ |
| 포지션 조회 | 현재 포지션 확인 | ⬜ |
| Maker 주문 | 지정가 진입 | ⬜ |
| 주문 체결 대기 | 미체결 처리 | ⬜ |
| TP 주문 | +0.4% 익절 | ⬜ |
| SL 주문 | -0.4% 손절 | ⬜ |
| 청산 로직 | 포지션 종료 | ⬜ |

**완료 조건:**
```
Paper Trading: 진입 → TP 또는 SL 체결 확인
```

---

### Sprint 3: 자동화 + DB
**목표:** 24시간 무인 실행 + 거래 기록

| 태스크 | 상세 | 상태 |
|--------|------|------|
| DB 모델 | Trade, BotStatus | ⬜ |
| DB 연결 | SQLAlchemy async | ⬜ |
| 거래 기록 | 진입/청산 저장 | ⬜ |
| 메인 루프 | 5분 주기 실행 | ⬜ |
| 포지션 체크 | 중복 진입 방지 | ⬜ |
| 타임컷 | 2시간 후 청산 | ⬜ |
| Discord 봇 | 연결 설정 | ⬜ |
| 진입 알림 | Embed 메시지 | ⬜ |
| 청산 알림 | 손익 표시 | ⬜ |
| 에러 알림 | 에러 발생 시 | ⬜ |
| 재시도 로직 | API 실패 3회 | ⬜ |
| 로깅 | loguru 설정 | ⬜ |
| EC2 배포 | 운영 환경 전환 | ⬜ |

**완료 조건:**
```
EC2에서 24시간 무인 실행, DB 기록, Discord 알림
```

---

### Sprint 4: 실전 투입
**목표:** Paper Trading → 실전

| 태스크 | 상세 | 상태 |
|--------|------|------|
| Paper Trading | 10회 시뮬레이션 | ⬜ |
| 소액 테스트 | 1% 비중 5회 | ⬜ |
| 성과 분석 | 승률, 손익 검증 | ⬜ |
| 파라미터 조정 | TP/SL 최적화 | ⬜ |
| 정규 운영 | 5% 비중 시작 | ⬜ |

**완료 조건:**
```
실제 거래 50회 이상, 승률 55%+ 달성
```

---

### Sprint 5+: 확장
**목표:** 기능 고도화

| 태스크 | 설명 | 우선순위 |
|--------|------|----------|
| 조건부 타임컷 | +0.1% 시 연장, -0.3% 시 조기청산 | 중 |
| 백테스트 | 3개월 데이터 시뮬레이션 | 중 |
| /status | 현재 포지션 조회 | 하 |
| /report | 오늘 거래 요약 | 하 |
| /stats | 전체 통계 | 하 |
| ETH 봇 | 중간 공격형 | 하 |
| SOL 봇 | 고변동성 공격형 | 하 |
| n8n | 멀티봇 오케스트레이션 | 하 |

---

## 4. 진행 상태

| Sprint | 목표 | 상태 | 진행률 | 데브옵스 경험 |
|--------|------|------|--------|---------------|
| Sprint 0 | **데브옵스 환경** | 🔄 진행 중 | 0% | ⭐⭐⭐⭐⭐ |
| Sprint 1 | 데이터 연동 | ⏳ 대기 | - | ⭐⭐ |
| Sprint 2 | 주문 실행 | ⏳ 대기 | - | ⭐ |
| Sprint 3 | 자동화 + DB | ⏳ 대기 | - | ⭐⭐⭐ |
| Sprint 4 | 실전 투입 | ⏳ 대기 | - | ⭐⭐ |
| Sprint 5+ | 확장 | ⏳ 대기 | - | ⭐⭐⭐⭐ |

---

## 5. 파일별 구현 순서

### Sprint 0 (데브옵스 우선!)
```
1. README.md                         # 프로젝트 소개
2. .gitignore                        # Git 설정
3. .env.example                      # 환경 변수 템플릿
4. Dockerfile                        # 컨테이너 이미지
5. docker-compose.yml                # PostgreSQL + 봇
6. .dockerignore                     # 빌드 최적화
7. scripts/deploy.sh                 # 배포 스크립트
8. .github/workflows/deploy.yml      # CI/CD 파이프라인
9. src/main.py                       # Hello World (최소)
10. requirements.txt                 # 기본 의존성
```

**데브옵스 학습 포인트:**
- Docker 멀티 스테이지 빌드
- Docker Compose 네트워크
- GitHub Actions CI/CD
- AWS EC2 SSH 배포
- 환경 변수 관리
- 로그 수집 (Docker logs)

### Sprint 1
```
1. src/config.py
2. src/exchange/binance.py
3. src/data/fetcher.py
4. src/data/indicators.py
5. src/ai/gemini.py
6. src/ai/prompts/system.txt
7. src/ai/prompts/analysis.txt
8. src/ai/signals.py
```

### Sprint 2
```
1. src/trading/executor.py
2. src/trading/position.py
```

### Sprint 3
```
1. src/database/models.py
2. src/database/connection.py
3. src/database/crud.py
4. src/trading/monitor.py
5. src/notifications/discord.py
6. src/main.py (완전체)
```

---

## 6. 다음 할 일

**Sprint 0 시작 (데브옵스 우선!):**
1. ~~문서 작성~~ ✅
2. **지금:** 프로젝트 폴더 구조 생성
3. Dockerfile + docker-compose.yml 작성
4. Hello World 컨테이너 로컬 실행
5. AWS EC2 생성 및 Docker 설치
6. GitHub Actions CI/CD 구성
7. 자동 배포 테스트

---

## 7. 데브옵스 학습 로드맵

### Phase 1: Docker 기초
- [ ] Dockerfile 작성 (Python 이미지)
- [ ] 로컬 빌드 및 실행
- [ ] docker-compose로 PostgreSQL 연동
- [ ] 볼륨 마운트 (logs, data)
- [ ] 환경 변수 관리

### Phase 2: AWS 인프라
- [ ] EC2 인스턴스 생성 (t3.micro)
- [ ] 보안 그룹 설정 (SSH, HTTP)
- [ ] SSH 키 생성 및 접속
- [ ] Docker 설치
- [ ] Git 설치

### Phase 3: CI/CD
- [ ] GitHub Actions 워크플로우
- [ ] EC2 SSH 배포 자동화
- [ ] 환경 변수 시크릿 관리
- [ ] 배포 성공/실패 알림

### Phase 4: 모니터링
- [ ] Docker logs 수집
- [ ] Discord Webhook 알림
- [ ] 헬스체크 엔드포인트
- [ ] 컨테이너 재시작 정책

### Phase 5: 고급 (Sprint 5+)
- [ ] n8n 오케스트레이션
- [ ] 멀티 컨테이너 관리
- [ ] 로드 밸런싱
- [ ] Blue-Green 배포
