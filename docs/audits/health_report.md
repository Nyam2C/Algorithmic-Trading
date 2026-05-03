---
title: "Code Health Audit — 2026-05-03"
date: 2026-05-03
tags: [audit, dead-code, refactoring, code-health, security]
status: completed
---

# Code Health Audit

## 정정 노트 (2026-05-03 — 후속 검증)

본 리포트의 **P1-1 진단(Discord RBAC 미작동)은 부정확했습니다.** P1-2 처리 후 P1-1을 깊이 검증한 결과:

- audit-reporter는 `@requires_permission` **데코레이터** 부재만 보고 "RBAC 미작동" → "자금 손실 직결"로 진단했으나,
- 실제로는 `src/discord_bot/commands/control.py`에서 **모든 자금 영향 명령**(`/제어`, `/긴급청산`, `/알림`)이 본문에서 `check_permission()` 함수를 **인라인 호출**하여 권한을 검증 중이었습니다.
- 즉 보안 효과는 정상이며, 단지 데코레이터 vs 인라인 패턴의 구현 방식 차이일 뿐.

**실제 갭은** monitoring.py의 `/계정`(잔고), `/프롬프트`(AI 시스템 정보) 두 명령에 권한 체크가 없었던 점으로, **P2 (정보 노출)** 수준입니다. 이는 후속 커밋에서 인라인 패턴으로 닫혔습니다.

**교훈 (audit 도구의 한계):** 보안 진단은 단일 패턴(데코레이터)에만 의존하면 안 되고, 같은 효과를 내는 대안 패턴(inline 호출)도 함께 고려해야 합니다. 본 리포트 후속에 추가된 `tests/test_command_permissions.py`의 AST 메타 테스트가 미래의 동일한 false positive와 회귀를 방지합니다.

**P1 정정 후 카운트:** P1 1건(P1-2만 — 처리 완료), P2 7건(P1-1 → P2-7로 demote, 처리 완료), P3 9건.

---

## TL;DR

**전체 헬스 평가:** YELLOW (보안 운영 갭 2건 확인됨, 그 외 코드 위생은 GREEN 수준)

- P1 (즉시 수정 필요): **2건**
- P2 (이번 스프린트 권장): **6건**
- P3 (시간 여유 시): **9건**

**가장 시급한 3가지:**
1. **Discord RBAC 미적용** — `requires_permission` 데코레이터가 정의·테스트되어 있으나 실제 명령에 적용된 곳 0건. ADMIN/TRADER/VIEWER 구분이 사실상 동작하지 않음.
2. **감사 로그 호출 누락** — `log_bot_pause`/`log_bot_resume`/`log_config_change` 메서드가 운영 코드에서 한 번도 호출되지 않음. 봇 일시정지·재개·설정 변경이 audit trail에 남지 않음.
3. **BOCPD / LightGBM 모듈 미통합 데드코드** — `BOCPDDetector`, `LGBDeadZoneVerifier` 두 클래스 모두 인스턴스화 0건. `use_bocpd_regime`, `use_lightgbm_dead_zone` 플래그도 `bot_config.py` Pydantic 필드 외에 어디에서도 읽히지 않음.

**전체 리팩토링 필요 여부:** **NO** — 사용자가 우려한 "오래된 코드, 제대로 동작 안 할 수도 있다"는 전제는 **사실과 다릅니다.** 코드베이스 위생 상태는 매우 양호합니다:

| 객관 지표 | 결과 |
| --- | --- |
| 미사용 import (ruff F401/F811/F841) | **0건** |
| 순환 import | **0건** |
| TODO/FIXME/XXX/HACK | **0건** |
| 6개월+ 묵힌 모듈 | **0건** |
| 주석 처리된 코드 블록(3줄+) | **0건** |
| 테스트 수집 실패 | **0건 / 3022 테스트 정상 수집** |
| 테스트 매핑률 | **97.8% (89/91 모듈)** |
| `if False:` / dead branches | **0건** |

발견된 P1 2건은 **레거시 잔재가 아니라 운영/보안 통합 누락**이며, 해당 코드 자체는 정상 동작합니다. 따라서 전면 리팩토링이 아닌 **타겟 수정**으로 충분합니다.

---

## P1 — 즉시 수정 필요

### P1-1. Discord 권한(RBAC) 시스템이 실제로는 작동하지 않음

- **위치**: `src/discord_bot/permissions.py:189-231` (데코레이터 정의) vs. `src/discord_bot/commands/*.py` (실제 명령 핸들러 — 적용 0건)
- **검증 결과**: `grep -rn "@requires_permission" src/` 결과 — 데코레이터 정의(`def requires_permission`) 1건 + docstring 예시 1건뿐. **`@requires_permission(...)` 데코레이터를 실제로 사용한 명령 핸들러는 코드베이스 전체에 0건.** `tests/test_permissions.py`에서만 테스트로 호출됨.
- **영향**: 보안 — CLAUDE.md P1 분류 기준 "보안 취약점"에 정확히 해당.
  - 봇 시작·정지·긴급청산·일시정지·재개 등 모든 ADMIN 권한 명령이 권한 체크 없이 누구나 실행 가능.
  - `DISCORD_ADMIN_USER_IDS` / `DISCORD_ADMIN_ROLE_IDS` / `DISCORD_TRADER_ROLE_IDS` 환경변수 설정이 의미 없음.
  - 실제 자금 운영 봇에서 Discord 길드 멤버 누구든지 `/emergency_close`, `/stop_bot` 호출 가능 → **자금 손실로 직결**.
- **권장 조치**:
  1. `src/discord_bot/commands/control.py`(시작/정지/긴급청산/일시정지/재개)의 모든 핸들러에 `@requires_permission(PermissionLevel.ADMIN)` 또는 `TRADER` 적용.
  2. `src/discord_bot/commands/monitoring.py`(조회 명령)의 핸들러에는 `VIEWER` 또는 권한 체크 생략(공개) 정책 결정.
  3. 단위 테스트에 "각 명령이 데코레이터를 가지고 있는지" 메타 테스트 추가(예: `func.__wrapped__` 또는 데코레이터 등록부 검증).
- **작업량**: **M** (1일) — 명령 11개 분류 + 데코레이터 적용 + 메타 테스트 + 회귀 테스트.
- **원본**: `_workspace/code-audit/01_dead_code.md` § MEDIUM Confidence (line 69) + 본 리포트 검증 결과.

### P1-2. 봇 운영 감사 로그가 기록되지 않음 (Audit Trail 누락)

- **위치**: `src/storage/audit_log.py:211 (log_bot_pause)`, `:233 (log_bot_resume)`, `:310 (log_config_change)`
- **검증 결과**: `grep -rn "log_bot_pause\|log_bot_resume\|log_config_change" src/` 결과 — **정의 위치 외 호출 0건.** 운영 코드(`bot_instance.py`, `bot_manager.py`, Discord 명령 핸들러, API 엔드포인트) 어디에서도 호출되지 않음.
- **영향**: 컴플라이언스 / 사후 추적 불가능 — CLAUDE.md P1 분류 "리스크 관리 우회"에 인접.
  - 봇 일시정지/재개 시점, 누가 했는지, 왜 했는지 audit log 테이블에 기록되지 않음.
  - 설정 변경(`BotConfig` 갱신) 이력 추적 불가 → 사고 발생 시 원인 분석 불가.
  - DB 스키마(`audit_logs` 테이블)와 메서드 구현은 정상이나 호출 누락.
- **권장 조치**:
  1. `src/bot_instance.py`의 `pause()`/`resume()` 메서드에 `await self._audit_log.log_bot_pause(...)` 호출 추가.
  2. 설정 변경 경로(`BotManager.update_bot_config()` 또는 API `/bots/{name}/config` 핸들러)에 `log_config_change` 호출 추가.
  3. Discord `/pause`, `/resume` 명령 핸들러에서도 호출(중복이지만 사용자 ID 기록을 위해).
- **작업량**: **S** (1시간 이내) — 호출부만 3-4곳 추가. 메서드 시그니처 이미 갖춰짐.
- **원본**: `_workspace/code-audit/01_dead_code.md` § MEDIUM Confidence (line 59).

---

## P2 — 이번 스프린트 권장

### P2-1. 백테스트 CLI `--strategy` 기본값이 삭제된 모듈을 가리킴

- **위치**: `src/backtest/cli.py:28` — `default="rule_based"`
- **영향**: `src/ai/rule_based.py`는 2026-02-20에 삭제됨(MEMORY.md 기록). CLI를 인자 없이 실행하면 무효 전략명으로 백테스트 엔진에 전달되어 실패하거나 silently 무시될 가능성. 사용자 혼란 + 백테스트 신뢰도 저하.
- **권장 조치**: ① 유효 전략명(예: `"ensemble"` 또는 `"confluence"`)으로 default 변경, ② `BacktestEngine`이 `args.strategy`를 어떻게 사용하는지 확인 후 인자 자체 제거 검토.
- **작업량**: **S**
- **원본**: `_workspace/code-audit/04_legacy_residue.md` § 4 APEX-V 대체 잔재 의심.

### P2-2. `src/api/routes/bots.py` (358 LOC) 단위 테스트 부재

- **위치**: `src/api/routes/bots.py` — 봇 생성/시작/정지/조회 핵심 제어 흐름을 담당하는 FastAPI 라우터. `test_api_bots.py`가 존재하지만 **이 라우터 모듈을 직접 import하지 않음** (integration 레벨에서만 검증되거나 dead).
- **영향**: 봇 라이프사이클 제어 경로의 단위 테스트 갭 — Presentation 계층이지만 자금 영향 명령(`/start`, `/stop`)을 노출. CLAUDE.md "핵심 도메인 테스트 부재" 기준에 해당.
- **권장 조치**: `test_api_bots.py`가 실제로 어떤 모듈을 import하는지 확인 → 라우터 핸들러 단위 테스트 또는 TestClient 기반 통합 테스트 보강.
- **작업량**: **M**
- **원본**: `_workspace/code-audit/03_test_coverage.md` § 2.

### P2-3. 핵심 도메인 디렉토리 실제 라인 커버리지 미측정

- **위치**: `src/trading/`, `src/exchange/`, `src/ai/`, `src/data/`
- **영향**: CLAUDE.md 목표(95%/95%/90%/90%)에 도달했는지 모름. collect-only 단계 수치(7-23%)는 신뢰 불가. 실제 측정 없이는 P1/P2 회귀를 자동 감지 불가.
- **권장 조치**: `pytest tests/ --cov=src --cov-report=term-missing` 풀 실행(15분+ 예상) → 디렉토리별 실측 → CLAUDE.md 목표 미달 모듈 식별 → 보강 PR 분리.
- **작업량**: **M** (실측 자체는 자동, 갭 보강은 별도 작업).
- **원본**: `_workspace/code-audit/03_test_coverage.md` § 4.

### P2-4. `src/api/services/orchestration_service.py` — Wiring 누락 또는 폐기 결정 필요

- **위치**: `src/api/services/orchestration_service.py` (149 LOC) + `src/api/dependencies.py:341,351` (`set_/get_orchestration_service`)
- **영향**: 고아 모듈 + 데드코드 + 미사용 DI placeholder가 한 모듈에 동시 발견됨 → **확실 제거 후보 1순위**. tests에서만 참조됨. API 라우트 어디에서도 사용되지 않음.
- **권장 조치**: ① 향후 통합 계획이 있으면 wiring(라우트에서 `Depends(get_orchestration_service)` 등록), ② 없으면 모듈 + dependencies.py setter/getter + 관련 테스트 일괄 삭제.
- **작업량**: **S** (삭제 시) / **M** (wiring 시).
- **원본**: `01_dead_code.md` HIGH + `02_import_graph.md` § 3 고아 모듈 (교차 검증).

### P2-5. `src/data/bocpd.py` + `src/ai/lgb_booster.py` — 통합 미완료 모듈

- **위치**:
  - `src/data/bocpd.py` (232 LOC) + `BotConfig.use_bocpd_regime`, `bocpd_window_size`
  - `src/ai/lgb_booster.py` (LGBDeadZoneVerifier) + `BotConfig.use_lightgbm_dead_zone`, `lightgbm_model_path`
- **검증 결과**: 두 클래스 모두 인스턴스화 0건. `BotConfig` 플래그도 docstring 외 `src/` 어디에서도 읽히지 않음. `regime_detector.py`/`confluence_engine.py` 인자 시그니처에만 placeholder가 남아있음.
- **영향**: 데드코드 + 사용자 혼동(플래그를 켜도 아무 일도 안 일어남).
- **권장 조치**: ① 통합 계획 재개(commit `263243b` Phase 2의 후속 작업), ② 통합 계획 없으면 모듈 + 플래그 + placeholder 인자 일괄 제거.
- **작업량**: **M** (제거 시) / **L** (통합 시).
- **원본**: `01_dead_code.md` HIGH + `02_import_graph.md` § 3 고아 모듈 (교차 검증) + 본 리포트 검증.

### P2-6. `src/data/market_data_formatter.py` — 사용처 없는 모듈 (294 LOC)

- **위치**: `src/data/market_data_formatter.py` 전체
- **영향**: 어디서도 import되지 않음. AI 프롬프트 포매터로 추정되지만 `enhanced_gemini.py` 등에서 사용하지 않음. Legacy 잔재 가능성 매우 높음.
- **권장 조치**: git blame으로 도입 사유 확인 → 사용 계획 없으면 모듈 삭제.
- **작업량**: **S**
- **원본**: `01_dead_code.md` MEDIUM + `02_import_graph.md` § 3 고아 모듈 (교차 검증).

---

## P3 — 시간 여유 시

| 항목 | 위치 | 권장 조치 | 작업량 | 원본 |
| --- | --- | --- | --- | --- |
| Redis 키 상수 8개 미사용 (정의만 있고 실제 키는 클래스 내부 인라인) | `src/storage/redis_state.py:22-30` | 8개 상수 일괄 삭제 | S | `01_dead_code.md` HIGH |
| `EventBus.subscribe/unsubscribe/handler_count` 미사용 (publish-only 패턴) | `src/utils/event_bus.py:38,53,102` | publish-only 큐로 단순화 또는 메서드 삭제 | S | `01_dead_code.md` HIGH |
| `circuit_breaker.clear_registry / async_reset / decorate` 미사용 | `src/utils/circuit_breaker.py:285,318,396` | 메서드 삭제 | S | `01_dead_code.md` HIGH |
| `BotConfig` deprecated 4개 필드 (rule_based 잔재) | `src/bot_config.py:236-242` | 다음 BotConfig 스키마 v2 마이그레이션 시 일괄 제거 | S | `04_legacy_residue.md` § 2 |
| `bot_instance.py` 48개 import — god-module 신호 | `src/bot_instance.py` | Application Layer 분해 (pipeline/signal/risk gate 분리) | L | `02_import_graph.md` § 비고 |
| Discord 임베드/유틸 미사용 함수 (`format_pause_duration`, `truncate_id`, `create_status_embed`) | `src/discord_bot/utils.py:111,269`, `embeds.py:26` | 사용 계획 없으면 삭제 | S | `01_dead_code.md` MEDIUM |
| 동기 retry 데코레이터 미사용 (`sync_retry`) | `src/utils/retry.py:81` | 동기 호출 경로 도입 계획 없으면 삭제 | S | `01_dead_code.md` MEDIUM |
| 구조화 로깅 헬퍼 미사용 (`get_structured_logger`, `is_json_logging_enabled`) | `src/utils/logging.py:294,315` | 적용 또는 삭제 | S | `01_dead_code.md` MEDIUM |
| 다양한 운영 보조 메서드 (15개+) 테스트만 호출 | `bot_manager.py`, `redis_state.py`, `signal_tracker.py` 등 | API/Discord 노출 계획 명확화 후 결정 | M | `01_dead_code.md` MEDIUM |

---

## 통계 요약

| 항목 | 값 |
| --- | --- |
| 분석 대상 모듈 | 111 (.py 파일, src/ 기준) |
| 데드코드 (HIGH 확신) | 21개 / ~340 라인 |
| 데드코드 (MEDIUM 확신) | 18개 |
| 미사용 import | **0건** |
| 순환 import | **0건** |
| 고아 모듈 | 3건 (`orchestration_service`, `bocpd`, `market_data_formatter`) |
| 테스트 부재 핵심 모듈 | 1건 (`api/routes/bots.py`) + 1건 보조 (`api/schemas/common.py`) |
| 수집 실패 테스트 | **0건** (3022 테스트 정상 수집) |
| 6개월+ 묵힌 TODO | **0건** |
| 6개월+ 묵힌 모듈 | **0건** |
| Deprecated 마커 | 2건 (BotConfig 역호환용 의도적 잔재) |
| 주석 처리된 3줄+ 블록 | **0건** |
| `if False:` / dead branch | **0건** |
| 테스트 매핑률 | 97.8% (89/91 모듈) |

**확실 제거 후보 (3축 교차검증 통과)**: 모듈 단위 — `orchestration_service.py`, `bocpd.py` + `lgb_booster.py` (통합 결정 필요), `market_data_formatter.py`.

---

## 후속 작업 권장 순서

### 세션 1: P1 처리 (보안/감사 운영 갭)
**목표**: P1-1, P1-2 해결 → 검증 → 커밋.

1. **P1-1 RBAC 적용** (M, ~1일)
   - `src/discord_bot/commands/` 11개 명령 핸들러에 `@requires_permission` 적용
   - 데코레이터 적용 메타 테스트 추가
   - 검증: `python3.10 -m pytest tests/test_discord_bot.py tests/test_permissions.py -v`
2. **P1-2 audit log 호출 추가** (S, ~1시간)
   - `bot_instance.pause()`/`resume()`, `BotManager.update_bot_config()`에 호출 추가
   - 검증: `python3.10 -m pytest tests/test_bot_instance.py tests/test_audit_log.py -v`
3. **전체 검증**: `python3.10 -m pytest tests/ -v` → `ruff check src/ tests/` → `mypy src/`

### 세션 2: P2 처리 (테스트 갭 + 데드 모듈 정리)
**목표**: P2-1 ~ P2-6 결정 + 실행. 가능하면 묶어서 1-2개 PR로 분리.

- **묶음 A (테스트 보강)**: P2-2 (api/routes/bots.py 라우터 테스트) + P2-3 (전체 라인 커버리지 측정 + 갭 보강).
- **묶음 B (데드 모듈 정리 결정)**: P2-1 (CLI default), P2-4 (orchestration_service), P2-5 (bocpd + lgb_booster), P2-6 (market_data_formatter). 각 항목 git blame으로 도입 사유 확인 → 사용자 결정 → 일괄 삭제 또는 통합.
- 검증: 매 PR마다 `pytest` → `ruff` → `mypy` 통과 + `src/trading/`, `src/exchange/` 영향 시 전체 1860+ 테스트 회귀.

### 세션 3: P3 처리 (코드 위생 마이크로 정리)
**목표**: 남은 데드코드 일괄 PR (HIGH confidence 6항목 + Redis 키 상수 8개 등).

- 한 PR에 묶어 ~50라인 net-negative diff 가능.
- 검증: `pytest` → `ruff` → `mypy`.

### 세션 4 (선택, L 작업): bot_instance.py 분해
- `src/bot_instance.py`의 48-import god-module을 pipeline orchestrator / signal coordinator / risk gate / lifecycle manager로 분해.
- CLAUDE.md "계층 분리" 원칙 강화. 단, 자금 영향 영역이므로 전체 회귀 테스트 필수.

> **CLAUDE.md 50/50 규칙 적용**: 세션 1(P1)은 50% 시스템 개선(보안), 세션 2 묶음 A는 50% 시스템 개선(테스트), 세션 3은 100% 시스템 개선(위생). 다음 기능 개발 사이클에서 50% 비율 유지를 위해 P1/P2를 우선 소화 후 기능 작업으로 전환 권장.

---

## 검증 권장 사항

본 리포트의 한계:
- 4개 입력 보고서 모두 **STATUS: COMPLETE** — 전체 분석 데이터는 신뢰 가능.
- 단, `03_test_coverage.md`는 **collect-only 모드**로 실행됨. 실제 라인 커버리지(CLAUDE.md 95%/95%/90%/90% 목표 대비)는 **미측정**. 사용자 결정으로 P2-3 트리거 권장.
- P1-1 RBAC 검증은 본 리포트가 직접 수행함 — `grep -rn "@requires_permission" src/` 결과 0건으로 확정.
- P1-2 audit log 검증도 본 리포트가 직접 수행 — `grep -rn "log_bot_pause\|log_bot_resume\|log_config_change" src/` 결과 정의부 외 호출 0건 확정.
- BOCPD/LGB 미통합도 본 리포트가 검증 — `grep -rn "BOCPDDetector\|LGBDeadZoneVerifier" src/` 결과 정의·docstring 언급만, 인스턴스화 0건 확정.

추가 확인 권장:
- P2-2의 `test_api_bots.py`가 실제로 어떤 클라이언트를 통해 라우터를 호출하는지 코드 리뷰.
- P2-5 결정 시 `commit 263243b` (APEX-V Phase 2)의 통합 계획 문서가 `docs/plans/` 또는 `_workspace/`에 남아있는지 확인.

---

## 안전 가드

- 이 리포트는 **분석만** 수행. 실제 코드 변경 없음.
- 후속 작업은 항목별로 분리하여 진행 권장 (Conventional Commits + branch per item).
- `src/trading/`, `src/exchange/` 변경 시 **전체 3022 테스트 통과 필수**.
- 어떤 항목이든 제거 전 `git blame`으로 도입 사유 재확인.
- P1-1 RBAC 적용은 **봇 운영 중 머지 전 staging 환경에서 권한 체크 동작 확인 필수**.
- BOCPD/LGB 모듈 제거 시 `BotConfig` 플래그를 함께 제거하면 기존 Redis에 직렬화된 페이로드 역호환성 깨짐 — 마이그레이션 전략(필드는 유지하되 deprecated 마커 추가, 다음 메이저에서 제거) 또는 일괄 제거 결정 필요.

---

## 결론

사용자가 우려한 "오래된 코드, 제대로 동작 안 할 수도 있다"는 전제는 **데이터로 반증되었습니다.** 코드베이스 위생 지표(미사용 import, 순환 import, TODO, 6개월+ 묵힌 모듈, 주석 처리 코드, 테스트 수집 실패)가 모두 0이며, 매핑률 97.8%, 1860+ → 3022 테스트 정상 수집은 **매우 건강한 상태**입니다.

발견된 이슈는 "오래된 코드"가 아니라 **최근(2026-02-20) 추가된 기능의 통합 누락 + Discord 보안 데코레이터 적용 누락**입니다. P1 2건만 1-2일 내 해결하면 GREEN 상태로 즉시 복귀 가능합니다.
