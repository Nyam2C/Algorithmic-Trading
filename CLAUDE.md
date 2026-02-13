# High-Win Survival System — CLAUDE.md

> **이 파일은 모든 AI 에이전트와 팀원이 세션 시작 시 반드시 읽는 단일 진실의 원천(Single Source of Truth)입니다.**
> 이 프로젝트는 **Compound Engineering** 방법론을 따릅니다.

---

## 행동 가이드라인

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

> 이 프로젝트에서는 Compound Engineering Plan 단계에서 이를 수행합니다.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

> 이 프로젝트의 TDD(RED→GREEN→REFACTOR) 워크플로우가 이 원칙의 구현체입니다.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## 프로젝트 개요

**High-Win Survival System**은 비트코인 선물 자동매매 봇입니다. Binance Futures에서 동작하며, 기술적 지표와 AI(Google Gemini)를 활용하여 매매 신호를 생성합니다.

**한 줄 설명**: `"A survival-first crypto trading bot that learns from its mistakes"`

**핵심 원칙**:

- **생존 우선**: 높은 승률보다 자본 보존 중심. 리스크 관리가 수익보다 우선.
- **AI 학습**: 과거 거래 데이터를 메모리로 주입하여 반복 실수 방지.
- **자동화**: 24/7 무인 운영, Discord 원격 제어.
- **모든 작업 단위가 다음 작업을 더 쉽게 만들어야 한다.**

**현재 상태**: 핵심 기능 구현 완료. 리팩토링 및 개선 진행 중 (`feature/phase5-integration-completion` 브랜치).

---

## 기술 스택 (확정)

| 구성요소 | 선택 | 이유 | 상태 |
| --- | --- | --- | --- |
| 런타임 | Python 3.10+ | 풍부한 금융 라이브러리 생태계 | ✅ |
| 거래소 API | python-binance | Binance Futures Testnet/Mainnet | ✅ |
| AI | Google Gemini (gemini-2.0-flash-exp) | 저비용 실시간 분석 | ✅ |
| 데이터베이스 | PostgreSQL (asyncpg) | 거래 이력 영구 저장 | ✅ |
| 캐시/상태 | Redis | 봇 상태 영구 저장 | ✅ |
| REST API | FastAPI | 비동기 고성능 API | ✅ |
| 알림/제어 | Discord Bot (discord.py) | 원격 모니터링 및 제어 | ✅ |
| 모니터링 | Prometheus + Grafana + Loki | 메트릭/로그 통합 | ✅ |
| 테스트 | pytest | 1860+ 테스트 | ✅ |
| 린터 | ruff | Rust 기반, 빠름 | ✅ |
| 타입 체크 | mypy | strict 모드 | ✅ |
| CI/CD | GitHub Actions | 자동 테스트 + codecov | ✅ |

---

## 핵심 설계 결정 (변경하지 말 것)

| 결정 | 선택 | 이유 |
| --- | --- | --- |
| 리스크 우선 | RiskManager가 모든 주문 전 검증 | 자본 보존이 최우선 |
| AI 메모리 주입 | 과거 거래 통계를 프롬프트에 포함 | 반복 실수 방지 |
| 레짐 감지 | 횡보장(RANGING)에서 진입 차단 | 손실 구간 자동 회피 |
| 다중 TF 필터 | 상위 타임프레임 추세 불일치 시 WAIT | 역추세 진입 방지 |
| 수동 승인 | 첫 N거래 수동 확인 | 프로덕션 안전장치 |
| 의존성 주입 | 생성자를 통한 DI | 테스트 용이성 |
| 계층 분리 | Presentation/Application/Domain/Infra | 관심사 분리 |
| 멀티봇 구조 | BotManager → BotInstance | 독립적 전략 실행 |

---

## 아키텍처

### 데이터 흐름

```
Binance Futures API
  ├─ 시세 데이터 수신 (5분봉)
  │
  ├─ [데이터] indicators.py → regime_detector.py → multi_timeframe.py
  ├─ [AI] enhanced_gemini.py (메모리 주입 + 시장 분석)
  ├─ [필터링] 레짐 + 다중 TF + AI 신호 교차 검증
  │
  ├─ [리스크] risk_manager.py → trade_approval.py
  ├─ [실행] executor.py → Binance API (주문)
  │
  ├─ [저장] trade_history.py → PostgreSQL
  ├─ [학습] trade_analyzer.py → memory_context.py → AI 메모리
  └─ [모니터] prometheus.py + audit_log.py + Discord 봇
```

### 계층 구조

| 계층 | 디렉토리 | 역할 |
| --- | --- | --- |
| Presentation | `discord_bot/`, `api/` | 사용자 인터페이스 |
| Application | `main.py`, `trading/` | 비즈니스 로직 조율 |
| Domain | `data/`, `ai/`, `analytics/` | 핵심 도메인 로직 |
| Infrastructure | `exchange/`, `storage/`, `metrics/` | 외부 시스템 연동 |

---

## 디렉토리 구조

```
Algorithmic-Trading/
├── .claude/
│   ├── CLAUDE.md                    # ✅ 에이전트 소스 오브 트루스 (이 파일)
│   └── PROJECT_OVERVIEW.md          # ✅ 상세 구현 문서
├── src/
│   ├── main.py                      # ✅ 진입점 & 메인 루프
│   ├── config.py                    # ✅ 환경 설정 관리
│   ├── bot_config.py                # ✅ 멀티봇 설정 모델
│   ├── bot_instance.py              # ✅ 개별 봇 인스턴스
│   ├── bot_manager.py               # ✅ 멀티봇 관리자
│   ├── ai/                          # ✅ Gemini AI 분석
│   ├── analytics/                   # ✅ 거래 분석 + 메모리
│   ├── api/                         # ✅ FastAPI REST API
│   ├── backtest/                    # ✅ 백테스트 프레임워크
│   ├── data/                        # ✅ 기술적 지표 + 레짐 감지
│   ├── discord_bot/                 # ✅ Discord 봇 + 권한
│   ├── exchange/                    # ✅ Binance API 클라이언트
│   ├── metrics/                     # ✅ Prometheus 메트릭
│   ├── storage/                     # ✅ PostgreSQL + Redis + 감사 로그
│   ├── trading/                     # ✅ 주문 실행 + 리스크 관리
│   └── utils/                       # ✅ 재시도, 로깅
├── tests/                           # ✅ 테스트 (1860+)
├── docs/
│   ├── plans/                       # Phase별 계획 문서
│   ├── solutions/                   # 문제 해결 기록
│   └── brainstorms/                 # 설계 브레인스토밍
├── db/migrations/                   # DB 마이그레이션
├── deploy/                          # Docker Compose
├── monitoring/                      # Grafana + Loki 설정
├── scripts/                         # 운영 스크립트
└── workflows/                       # n8n 워크플로우
```

---

## Compound Engineering 4단계 루프

모든 기능 개발은 이 루프를 따릅니다. **Plan과 Review에 80%, Work와 Compound에 20%** 시간을 배분합니다.

### 1. Plan (계획)

- [ ] 요구사항 파악 (무엇을, 왜, 제약조건)
- [ ] `.claude/PROJECT_OVERVIEW.md` 읽어 현재 상태 확인
- [ ] 코드베이스에서 유사 패턴 조사
- [ ] 영향받는 파일과 접근 방식 설계
- [ ] 계획의 완전성 검증

### 2. Work (실행)

- [ ] 격리된 환경 설정 (git branch)
- [ ] **테스트 먼저 작성** (TDD: RED → GREEN → REFACTOR)
- [ ] 계획을 단계별로 실행
- [ ] 검증 실행: `pytest` → `ruff check` → `mypy`
- [ ] 진행 상황 추적 및 이슈 대응

### 3. Review (검토)

- [ ] 변경 사항을 P1/P2/P3로 분류하여 검토
- [ ] 보안 취약점 확인 (OWASP Top 10)
- [ ] 리스크 관리 로직 영향도 검증
- [ ] 발견 사항 해결 후 정확성 재검증

### 4. Compound (축적)

- [ ] 잘 된 점과 안 된 점 기록 → Common Pitfalls 업데이트
- [ ] `.claude/PROJECT_OVERVIEW.md` 상태 업데이트
- [ ] 이 CLAUDE.md에 새로운 패턴/교훈 반영
- [ ] 시스템이 다음에 자동으로 잡을 수 있는지 검증

---

## 필수 규칙

### 개발 요청 시 필수 사이클

사용자가 기능 개발/구현/추가를 요청하면 **반드시** Compound Engineering 루프를 따르세요:

1. **Plan**: `.claude/PROJECT_OVERVIEW.md` 읽고 현재 위치 확인
2. **Work**: 테스트 작성 → 기능 구현 → 테스트 통과
3. **Review**: `python3.10 -m pytest tests/ -v` → `ruff check src/ tests/` → `mypy src/`
4. **Compound**: `.claude/PROJECT_OVERVIEW.md` 업데이트 + 교훈 기록

### 상태 확인 요청 시

"상태", "진행", "현황" 등의 단어가 포함되면 **반드시** `.claude/PROJECT_OVERVIEW.md`를 먼저 읽으세요.

---

## 커맨드 레퍼런스

### 개발 커맨드

```bash
python3.10 -m pytest tests/ -v           # 테스트 실행
ruff check src/ tests/                    # 린트 체크
mypy src/                                 # 타입 체크
python3.10 -m src.main                    # 봇 실행
```

### 운영 커맨드

```bash
./scripts/start.sh                        # 전체 스택 시작
./scripts/start.sh --status               # 상태 확인
curl http://localhost:8000/health          # API 헬스체크
curl http://localhost:8000/docs            # Swagger UI
```

---

## 코딩 컨벤션

### 네이밍 규칙

- 파일명: **snake_case** (`risk_manager.py`)
- 클래스명: **PascalCase** (`RiskManager`)
- 함수/메서드: **snake_case** (`calculate_pnl`)
- 상수: **UPPER_SNAKE_CASE** (`MAX_DAILY_LOSS`)
- Private: **언더스코어 접두사** (`_internal_method`)

### 표준 약어

`pnl` (Profit and Loss), `pct` (Percentage), `tp` (Take Profit), `sl` (Stop Loss), `rsi` (RSI), `atr` (ATR)

### 한글 사용 가이드

| 위치 | 허용 |
| --- | --- |
| 변수/함수명 | ❌ 금지 |
| 로그 메시지 | ✅ 권장 |
| 코드 주석 | ✅ 허용 |
| Docstring | ✅ 권장 |

### Git 커밋 메시지

[Conventional Commits](https://www.conventionalcommits.org/) 형식:

```
<type>(<scope>): <description>

[optional body]
```

**type**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `perf`

### 브랜치 네이밍

```
<type>/<short-description>
```

예시: `feature/ensemble-ai`, `fix/risk-manager-cooldown`, `docs/api-reference`

---

## 테스트 원칙

### TDD 워크플로우

**RED → GREEN → REFACTOR → DOCUMENT**

### 커버리지 목표

| 모듈 | 목표 |
| --- | --- |
| `src/trading/` | 95%+ |
| `src/exchange/` | 95%+ |
| `src/ai/` | 90%+ |
| `src/data/` | 90%+ |

---

## 리뷰 분류 기준 (P1/P2/P3)

| 등급 | 의미 | 예시 | 조치 |
| --- | --- | --- | --- |
| **P1** | CRITICAL — 반드시 수정 | 자금 손실 위험, 리스크 관리 우회, 보안 취약점 | 머지 전 즉시 수정 |
| **P2** | IMPORTANT — 수정 권장 | 잘못된 PnL 계산, 누락된 에러 핸들링, N+1 쿼리 | 이번 PR 또는 후속 PR에서 수정 |
| **P3** | MINOR — 개선 가능 | 미사용 변수, 네이밍 개선, 가드 절 권장 | 시간 여유 시 수정 |

---

## Common Pitfalls

> 구현 중 발견된 코딩 함정과 해결책을 여기에 축적합니다.
> 형식: `- **문제**: 설명 → **해결**: 설명`

- **문제**: WSL 환경에서 한국어 포함 경로(`/mnt/c/Users/박/...`)로 `Edit` 도구 사용 시 간헐적 `ENOENT` 에러 → **해결**: `Read` → `Write` 전체 덮어쓰기 또는 `Bash` sed -i 사용

---

## 문서 템플릿

### Solution 문서 (`docs/solutions/`)

```markdown
---
title: "해결한 문제의 제목"
date: YYYY-MM-DD
tags: [카테고리, 도메인, 문제-유형]
severity: P1 | P2 | P3
status: resolved
---

## 문제

## 원인

## 해결

## 예방

## 관련 문서
```

### Plan 문서 (`docs/plans/`)

```markdown
---
title: "기능/작업 제목"
date: YYYY-MM-DD
tags: [관련-도메인]
status: draft | approved | in-progress | completed
---

## 목표

## 배경

## 접근 방식

## 영향받는 파일

## 엣지 케이스

## 검증 방법
```

### Brainstorm 문서 (`docs/brainstorms/`)

```markdown
---
title: "주제"
date: YYYY-MM-DD
tags: [관련-키워드]
status: exploring | decided
---

## 질문

## 선택지

## 결정
```

---

## 50/50 규칙

- **50% 기능 개발**: 새로운 전략, AI 개선, 거래 로직 등 직접적 가치
- **50% 시스템 개선**: 테스트 보강, 리팩토링, 문서화, 모니터링 개선 등

시스템 개선은 낭비가 아니라 **복리 투자**입니다.

---

## 참조 자료

- **프로젝트 상세 문서**: `.claude/PROJECT_OVERVIEW.md`
- **DB 스키마**: `db/init.sql`, `db/migrations/`
- **배포 설정**: `deploy/docker-compose.yml`
- **모니터링**: `monitoring/`

---

_이 파일은 프로젝트와 함께 진화합니다. 새로운 패턴, 실수, 교훈을 발견하면 즉시 업데이트하세요._
