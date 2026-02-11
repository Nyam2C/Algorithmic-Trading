# Code Review Handoff

## Task

사용자가 오랜만에 프로젝트에 돌아와서 **전체 코드베이스를 순차적으로 리뷰**하고 있음. 파일별로 읽고 → 구조 요약 + 잘 된 점 + 관찰 포인트(P1/P2/P3)를 설명 → brainstorms 문서에 관찰 포인트 기록.

## Approach (What Worked)

1. **모듈 단위로 파일을 병렬 Read** → 리뷰 요약을 사용자에게 출력
2. **관찰 포인트는 `docs/brainstorms/code-review-observations.md`에 누적 기록** (P1/P2/P3 분류)
3. 사용자는 "응 다음 가자"로 다음 모듈 진행. 간결하게 요약하되 핵심 관찰 포인트는 빠짐없이 기록.
4. 모듈 순서: 최상위 → data → trading → ai → analytics → (여기서 중단)

## What's Been Completed (22 files reviewed)

### 1. 최상위 (Application 계층)
- ✅ `src/main.py` (362줄) — 진입점, 3서비스 동시 실행
- ✅ `src/config.py` (188줄) — Pydantic 환경변수 설정
- ✅ `src/bot_config.py` (315줄) — 멀티봇 설정 모델
- ✅ `src/config_loader.py` (150줄) — YAML 봇 설정 로더
- ✅ `src/bot_instance.py` (842줄) — 개별 봇 트레이딩 루프
- ✅ `src/bot_manager.py` (595줄) — 멀티봇 관리자

### 2. data/ (Domain)
- ✅ `src/data/indicators.py` (287줄) — 기술적 지표 계산
- ✅ `src/data/regime_detector.py` (242줄) — 시장 레짐 감지
- ✅ `src/data/multi_timeframe.py` (218줄) — 다중 타임프레임 분석
- ✅ `src/data/market_data_formatter.py` (291줄) — AI용 데이터 포맷터

### 3. trading/ (Application)
- ✅ `src/trading/executor.py` (586줄) — 주문 실행 엔진
- ✅ `src/trading/risk_manager.py` (303줄) — 리스크 관리
- ✅ `src/trading/trade_approval.py` (320줄) — 수동 승인 시스템

### 4. ai/ (Domain)
- ✅ `src/ai/gemini.py` (449줄) — Gemini API 클라이언트
- ✅ `src/ai/enhanced_gemini.py` (247줄) — 메모리 강화 Gemini
- ✅ `src/ai/ensemble.py` (380줄) — 앙상블 시그널
- ✅ `src/ai/rule_based.py` (121줄) — 룰 기반 시그널
- ✅ `src/ai/scoring.py` (445줄) — 지표 스코어링
- ✅ `src/ai/signals.py` (108줄) — 시그널 유틸리티

### 5. analytics/ (Domain)
- ✅ `src/analytics/trade_analyzer.py` (813줄) — 거래 이력 분석
- ✅ `src/analytics/memory_context.py` (444줄) — AI 메모리 컨텍스트
- ✅ `src/analytics/signal_tracker.py` (632줄) — 신호 추적

## What's Remaining (not yet reviewed)

### 6. exchange/ (Infrastructure)
- ❌ `src/exchange/binance.py` (~614줄) — Binance Futures API 클라이언트

### 7. storage/ (Infrastructure)
- ❌ `src/storage/trade_history.py` — PostgreSQL 거래 이력
- ❌ `src/storage/redis_state.py` (~609줄) — Redis 상태 저장
- ❌ `src/storage/audit_log.py` (~412줄) — 감사 로그

### 8. api/ (Presentation) — 여러 파일
- ❌ `src/api/main.py` — FastAPI 앱
- ❌ `src/api/config.py` — API 설정
- ❌ `src/api/dependencies.py` — DI
- ❌ `src/api/middleware/rate_limit.py` (~394줄) — Rate limiting
- ❌ `src/api/routes/analytics.py` (~404줄) — 분석 API
- ❌ `src/api/routes/bots.py` — 봇 관리 API
- ❌ `src/api/routes/dashboard.py` — 대시보드 API
- ❌ `src/api/routes/health.py` — 헬스체크
- ❌ `src/api/routes/n8n.py` — n8n 웹훅
- ❌ `src/api/schemas/` — Pydantic 모델 (bot.py, common.py, n8n.py)
- ❌ `src/api/services/` — 비즈니스 로직 (bot_service.py, n8n_callback.py)

### 9. discord_bot/ (Presentation) — 가장 큰 모듈
- ❌ `src/discord_bot/bot.py` (~1,829줄) — 봇 코어 (가장 큰 파일)
- ❌ `src/discord_bot/client.py` (~649줄)
- ❌ `src/discord_bot/commands/control.py` — 제어 명령어
- ❌ `src/discord_bot/commands/monitoring.py` — 모니터링 명령어
- ❌ `src/discord_bot/commands/multibot.py` — 멀티봇 명령어
- ❌ `src/discord_bot/permissions.py` — 권한 시스템
- ❌ `src/discord_bot/embeds.py` (~473줄) — UI 컴포넌트
- ❌ `src/discord_bot/views.py` (~467줄) — Discord Views
- ❌ `src/discord_bot/constants.py`
- ❌ `src/discord_bot/utils.py`

### 10. utils/ (공통)
- ❌ `src/utils/circuit_breaker.py` (~396줄)
- ❌ `src/utils/retry.py`
- ❌ `src/utils/logging.py`

### 11. backtest/ (Domain)
- ❌ `src/backtest/engine.py` (~598줄)
- ❌ `src/backtest/slippage.py`

### 12. metrics/ (Infrastructure)
- ❌ `src/metrics/prometheus.py`

## Output File

모든 관찰 포인트는 아래 파일에 누적 기록 중:

**`docs/brainstorms/code-review-observations.md`**

이 파일을 먼저 읽고, 이어서 나머지 모듈을 같은 형식으로 리뷰 + 기록하면 됨.

## Review Format (Per Module)

사용자에게 출력하는 포맷:

```
## N. `src/모듈/파일.py` 리뷰 (줄수)

**역할**: 한 줄 설명

**구조 요약**: (큰 파일은 트리 구조로)

**잘 된 점**: (3~5개 bullet)

**관찰 포인트**: (P1/P2/P3 분류, brainstorms에 기록됨 메모)
```

brainstorms 파일에 추가하는 포맷:

```markdown
## src/모듈/파일.py

- **[P2] 제목**: 줄번호. 설명.
- **[P3] 제목**: 줄번호. 설명.
```

## Key Recurring Themes Found So Far

리뷰 중 반복 발견된 주요 패턴:

1. **미통합 기능 (P2)**: `MultiTimeframeAnalyzer`, `TradeApprovalManager`, `EnsembleSignalGenerator`, `SignalTracker`가 구현되어 있지만 `bot_instance.py` 트레이딩 루프에 연결 안 됨. CLAUDE.md에서 핵심 설계로 명시한 기능들.
2. **코드 중복 (P2)**: executor의 open_position 2개, gemini의 build_market_prompt 2개, trade_analyzer의 pattern/worst 메서드 등.
3. **Pydantic v1/v2 혼재 (P2)**: config.py는 `@validator`, bot_config.py는 `@field_validator`.
4. **PnL 계산 분산 (P2)**: executor, bot_instance, market_data_formatter에서 각각 다른 방식으로 PnL 계산. 레버리지 반영 여부 불일치.
5. **assert 사용 (P3)**: 프로덕션 코드에서 `assert` 사용. `-O` 플래그로 무시됨.

## Instructions for Next Agent

1. `docs/brainstorms/code-review-observations.md`를 읽어 기존 기록 확인
2. 위 "What's Remaining" 목록 순서대로 파일 Read → 리뷰 → 사용자에게 출력 → brainstorms 파일에 관찰 포인트 추가
3. 모든 모듈 완료 후, 사용자에게 전체 요약 (P1/P2/P3 카운트, 주요 테마) 제공
4. 사용자가 "응 다음 가자"로 진행 의사 표시. 한 번에 모듈 단위(2~4파일)씩 진행.
