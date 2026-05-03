---
title: "Architecture Analysis — 2026-05-03"
date: 2026-05-03
tags: [audit, architecture, refactoring, decision-card]
status: completed
---

# Architecture Analysis

> 본 리포트는 3개 분석 산출물(layer boundary / module cohesion / dataflow)을 종합하여
> "지금 아키텍처가 어떤 상태이고, 다음에 무엇을 할 것인가" 단일 의사결정 카드를 제공합니다.
> 위생(health_report.md)은 별도 리포트이며, 본 리포트는 **구조/설계** 관점입니다.

---

## TL;DR

**아키텍처 평가:** **SOLID (with one growing pressure point)**
근거: 진성 계층 위반 0, 순환 import 0, 미사용 import 0, 양방향 결합 1쌍(정상 패턴), APEX-V 22/25 컴포넌트 통합 완료. 단 `bot_instance.py`(3657 LOC, 60 메서드) 단일 god-module이 모든 변경의 병목으로 누적.

**한 문장 답변 ("다음 무엇을 해야 하는가?"):**
> **시나리오 A (안정 우선)** — Silent No-op 플래그 정리 + CLAUDE.md 데이터 흐름 동기화 + 직전 P1 수정의 후속 모니터링. 작업 1~2일, 회귀 위험 낮음, 이후 시나리오 B 분해 작업의 사전 준비물이 자연스럽게 갖춰짐.

**3가지 선택지:**

| 선택지 | 작업량 | 회귀 위험 | 컴파운드 효과 | 적합한 상황 |
| --- | --- | --- | --- | --- |
| **A) 안정 우선 — 위생 정리 + 문서 동기화** | S~M (1~2일) | 낮음 | 강 (B의 사전 준비) | 직전 P1 수정 후 안정화·관찰 단계, 이번 추천 |
| **B) 부분 분해 — `bot_instance.py` 5-way split** | L+ (1~2주) | **높음** (자금 영향) | 강 (이후 시그널/실행/상태 변경 격리) | 분해 전용 sprint를 떼낼 수 있을 때 |
| **C) 새 기능 (APEX-V Phase 3 등)** | 가변 | 누적 (god-module 추가 비대) | 단기 ROI만 | 비즈니스 가치 우선 + 부채 유예 가능 시 |

---

## 1. 강점 (지금 잘 되고 있는 것)

- **계층 분리 깨끗**: 진성 HARD 위반 0건. 4건의 `main.py → Presentation` import는 모두 composition root 부트스트랩이며, 일반적이고 정상적인 패턴(layer-boundary §1).
- **순환 의존 0**: 양방향 import는 `discord_bot.client ↔ discord_bot.views` 1쌍뿐(동일 패키지 내 Discord SDK 패턴, 정상)(cohesion §2).
- **APEX-V 통합 진척률 88%**: 25개 컴포넌트 중 22개가 코드에서 호출/wired. MTI / Confluence / 6채널 / Microprice / Kelly / Vitality / KSG / OI 직교화 / PCMCI / Graceful Degradation / Shadow / BTLive 등 모두 end-to-end 연결(dataflow §4).
- **테스트 커버 매핑 97.8%**: 89/91 모듈에 대응 테스트, 3022 테스트 정상 수집(health_report cross-check).
- **Forward 데이터 흐름 end-to-end OK**: `WS/REST → indicators/sentiment → MTI → regime → 6채널 → Confluence → Sizing → RiskManager → Executor → Binance` 단절 지점 없음(dataflow §5.1).
- **자가 튜닝 피드백 루프 5종 동작**: ThresholdTuner / PCMCI / Vitality / BTLive / WeeklyReport (dataflow §5.3).
- **분해 후보를 분리 못 해도 응집은 양호**: `confluence_engine`(fan-out 8), `bot_manager`(33 메서드) 등 god 후보 2~3선은 단일 책임 영역에 응집되어 있어 즉각 분해 압력 낮음.

> 한 줄: 사용자가 우려한 "오래되고 동작 안 할 것 같다"는 전제는 사실과 다릅니다. 구조는 건강하며, 이슈는 한 곳에 집중되어 있습니다.

---

## 2. 약점 (해결되면 좋을 구조적 이슈)

### 약점 1: `bot_instance.py` god-module — 단일 복잡도 핫스팟
- 위치: `src/bot_instance.py` (3657 LOC, 60 메서드, out-degree 48)
- 무엇: 5-Gate 파이프라인 + Kelly + Microprice + Degradation + Shadow + 상태 영속화 + 리스크 게이트 + 메인 루프가 단일 클래스에 통합. `_initialize`(357 LOC, 49 branches), `_close_position`(299/47), `_execute_single_loop`(191/21), `_run_five_gate_pipeline`(175/23) 등 장문 함수 8개가 이 파일에 집중(cohesion §1, §4).
- 왜 문제: 자금 영향 코드의 변경이 항상 같은 파일 한 곳을 거쳐 PR 충돌·회귀 위험을 증폭. 신규 채널/게이트 추가 시 god-module 비대화가 이미 가속(APEX-V 추가분이 그 증거).
- 영향 모듈: 자기 자신 + Domain x29 + Infra x9 + Application x9 (in-degree는 1 — `bot_manager`만).
- 권장: 5-way 분해(lifecycle / signal_pipeline / position_executor / state_persistence / facade). 단 자금 영향 — **분해 전용 sprint와 staging 24h 무인 운영 검증** 필수. 즉시 진행보다는 마이크로 리팩토링(아래 약점 2~3)으로 사전 비대 LOC를 줄인 후 본 분해 진입을 권장.

### 약점 2: `_initialize`(357 LOC/49 br), `_close_position`(299/47) 단일 메서드 비대
- 위치: `src/bot_instance.py:784`, `:1667`
- 무엇: 의존성 wiring과 청산 사유별 분기가 한 함수에 모두 모임.
- 왜 문제: god-module 분해의 사전 단계로 이 두 메서드만 단계별/사유별 헬퍼로 추출해도 가독성·테스트 격리 도움. 분해 작업 비용을 단계적으로 분할 가능.
- 권장: P2 마이크로 리팩토링. `_init_storage()/_init_ai()/_init_risk()` 등 단계별 추출, `_close_for_tp()/_close_for_sl()/_close_for_signal_invalidation()` 등 사유별 추출(cohesion §5).

### 약점 3: Silent No-op 플래그 — 운영 오인 위험 (P1 후보)
- 위치: `src/bot_config.py` (`use_bocpd_regime`, `use_lightgbm_dead_zone`)
- 무엇: 두 플래그는 BotConfig Pydantic 필드로 받지만 `BOCPDDetector` / `LGBDeadZoneVerifier` 인스턴스화·주입이 코드 어디에서도 일어나지 않음. 설정에서 `True`로 바꿔도 효과 0.
- 왜 문제: **운영자가 활성화된 것으로 오인할 수 있음**. dataflow와 health_report **두 리포트에서 독립적으로 동일 결론** — 신뢰도 매우 높음.
- 영향 모듈: `bot_config.py`, `data/regime_detector.py`(BOCPD 옵션), `ai/confluence_engine.py`(`lgb_verifier=` 인자만 존재), `ai/lgb_booster.py`(인스턴스화 0).
- 권장 (택일):
  - (a) 코드/플래그 제거 + Redis 페이로드 역호환을 위해 deprecated 마커 추가(권장 — 단기 비용 최저).
  - (b) BOCPD/LGB wiring 완성(Phase 3 수준 작업, L).
  - 어떤 결정을 내려도 **현 상태 유지는 부적절**.

### 약점 4: Pipeline / Legacy 두 경로 코드 중복
- 위치: `_run_five_gate_pipeline`(2369) vs `_apply_signal_filters`(2216)
- 무엇: MTI/Regime/MTF 처리가 두 경로에 거의 동일 로직으로 중복 존재. `use_confluence_engine` 토글에 따라 분기.
- 왜 문제: 한쪽만 수정될 위험. Shadow Mode가 ON이면 두 경로를 모두 실행 — 외부 호출(LLM, KSG) 비용 2배(dataflow C-1, C-2).
- 권장: Pipeline 정착 후 Legacy 경로 deprecate 일정 결정. 즉시 제거는 위험 — 단계적 deprecation 권장(P2/P3).

### 약점 5: CLAUDE.md 데이터 흐름 다이어그램이 APEX-V 이전
- 위치: `CLAUDE.md` "데이터 흐름" 섹션
- 무엇: 명세 ↔ 실제 차이 10건. Gemini 역할이 "메인 분석"에서 "Step 8 Dead Zone 검증(~5-10%)" 으로 강등되었으나 문서 미반영. MTI Gate0, Microprice, 4개 피드백 루프 등 신규 단계 누락(dataflow §3).
- 왜 문제: SOT(Single Source of Truth)가 실제 코드와 어긋나면 신규 작업의 위치 추정 오류·중복 구현 위험 누적. CLAUDE.md "모든 작업 단위가 다음 작업을 더 쉽게 만들어야 한다" 원칙에 직접 반함.
- 권장: dataflow §7의 갱신 다이어그램으로 교체(P2, S, 위험 0).

### 약점 6: `analytics.trade_analyzer → storage.trade_history` 직접 의존
- 위치: `src/analytics/trade_analyzer.py`
- 무엇: Domain → Infra 정방향이지만 영속화 모듈을 직접 import. Repository 인터페이스가 부재.
- 왜 문제: 단위 테스트 시 `trade_history` 모킹 비용이 누적. 추후 저장소 교체 또는 멀티 저장소 시 변경 비용.
- 권장: P3, 작업량 S. `TradeRepository` Protocol 도입 후 의존성 주입.

### 약점 7: `RedisStateManager` 40 메서드 + Dummy mirror 35
- 위치: `src/storage/redis_state.py`
- 무엇: Bot 상태/Risk/Kelly/Microprice/명령 큐가 한 클래스에 통합. `DummyRedisStateManager`가 mirror 패턴으로 자동 동기화 부담.
- 왜 문제: 도메인별 Repository로 분해하면 각 영역 변경이 격리됨. 자금 영향은 낮음(Redis 키 네임스페이스만 보존하면 안전).
- 권장: P2/P3 분해 (4 Repository: BotState / RiskState / LearningState / CommandQueue) + Facade 유지(cohesion §1 god-3).

---

## 3. 데이터 흐름 통합 평가

**APEX-V 22/25 통합 완료 (88%)**. 미통합/유령 컴포넌트 3개:

| # | 컴포넌트 | 상태 | 결정 필요성 |
|---|---|---|---|
| 1 | `BOCPDDetector` | DEAD | **P1 후보** — 플래그만 노출되어 silent no-op |
| 2 | `LGBDeadZoneVerifier` | DEAD | **P1 후보** — 플래그만 노출되어 silent no-op |
| 3 | `LiquidationCascadeTrigger Mode B` | DEAD | P2 — Mode A(Channel)는 정상 통합, Mode B만 미사용 |

**명세 ↔ 실제 차이 10건** (dataflow §3): Gemini 역할 강등, MTI Gate0 추가, Microprice 다중화, 자가 튜닝 5루프 추가 등. CLAUDE.md 다이어그램 갱신 필수(dataflow §7 제안 다이어그램 채택 권장).

**Forward 흐름**: end-to-end OK. **Backward 학습 루프**: TradeHistory → Analyzer → MemoryContext → EnhancedGemini wiring 정상. **자가 튜닝 5루프** 모두 동작.

> 데이터 흐름의 구조 자체는 정상이지만 **CLAUDE.md 명세가 코드를 따라가지 못함**. 명세 동기화는 향후 모든 작업의 사전 비용을 낮춤.

---

## 4. 의사결정 카드 (메인)

### 시나리오 A: 안정 우선 — 위생/문서 동기화
- **무엇**:
  1. BOCPD/LGB 플래그 결정 + 처리 (제거 또는 wiring 완성).
  2. CLAUDE.md 데이터 흐름 다이어그램을 dataflow §7 제안으로 교체.
  3. 직전 P1 수정(RBAC 인라인, 감사 로그 호출, 9162bb9·57dea17)의 staging 모니터링 1주.
- **왜**: 아키텍처 자체는 건강. P1 후보 silent no-op은 작은 결정으로 닫힘. 문서 동기화는 다음 작업 비용을 영구 절감.
- 작업량: S~M (1~2일)
- 회귀 위험: 낮음 (코드 변경 최소; 플래그 제거 시 Redis 역호환 마커 필요)
- 컴파운드 효과: 강 — 시나리오 B 착수 시 책임 경계가 이미 문서에 정리되어 분해 계획 작성 시간 단축.
- 다음에 좋은 것: 분해 sprint를 떼내거나 새 기능을 시작할 때 둘 다 출발선이 명확해짐.

### 시나리오 B: 부분 분해 — `bot_instance.py` 5-way split
- **무엇**: cohesion §1 god-1의 5-way 분해 제안 그대로:
  1. `BotLifecycleManager` (~700 LOC)
  2. `SignalPipeline` (~700 LOC)
  3. `PositionLifecycleManager` (~900 LOC, **자금 영향 영역**)
  4. `BotStatePersistence` (~300 LOC)
  5. `BotInstance` slim facade (~1000 LOC)
- **왜**: 단일 god-module이 모든 변경의 병목. 분해 후 시그널/실행/상태가 격리되어 후속 작업의 회귀 영역이 좁아짐.
- 작업량: **L+** (1~2주, 분해 sprint 전용)
- 회귀 위험: **높음** (자금 영향, 3022 테스트 전체 회귀 + staging 24h 무인 검증 필수)
- 컴파운드 효과: 강 — 새 거래소·새 전략·새 채널 추가 시 변경 영향이 격리됨.
- 다음에 좋은 것: APEX-V Phase 3 등 신규 기능 개발 시 god-module 비대 가속을 멈춤.
- **주의**: 사전에 시나리오 A를 먼저 완료하여 책임 경계를 문서화한 뒤 진입할 것. 또한 `_initialize` / `_close_position` 마이크로 리팩토링(약점 2)을 선행하면 분해 비용이 약 600~700 LOC 감소.

### 시나리오 C: 새 기능 (APEX-V Phase 3 등)
- **무엇**: 분해를 미루고 신규 채널/전략/AI 모델 등 비즈니스 가치 우선.
- **왜**: 단기 ROI 우선. 아직 아키텍처가 무너지지 않았으므로 즉각 막힘은 없음.
- 작업량: 가변
- 회귀 위험: 누적 — `bot_instance.py`가 또 한 번 비대해짐. APEX-V Phase 1~2 통합으로 이미 60 메서드 도달.
- 컴파운드 효과: 약 — 부채 가중. 다음 기능 추가 시 변경 영향 추정 비용이 더 커짐.
- 다음에 좋은 것: 직접적인 비즈니스 가치만 있는 시점.

---

## 5. 추천

위 3가지 중 **시나리오 A (안정 우선)** 추천.

**근거 (CLAUDE.md 50/50 + Compound 원칙 인용):**

1. **"모든 작업 단위가 다음 작업을 더 쉽게 만들어야 한다"** — 시나리오 A의 CLAUDE.md 다이어그램 동기화는 시나리오 B의 분해 계획서 작성 비용을 직접 낮춥니다. A를 먼저 하면 B가 쉬워지지만, B를 먼저 해도 A는 같은 비용입니다. 순서가 중요.
2. **50/50 규칙** — 사용자는 직전 세션에서 P1 수정(RBAC, 감사 로그 — 50% 시스템 개선)을 완료했습니다. silent no-op 결정과 문서 동기화는 그 연속선상의 위생/문서화 작업(역시 50% 시스템 개선)으로 자연스럽게 이어집니다. 이후 시나리오 B 또는 C로 50% 기능 개발 균형 회복 가능.
3. **자금 영향 가드** — 시나리오 B는 자금 영향 코드의 분해이므로 회귀 위험이 매우 큽니다. 직전 P1 수정의 staging 모니터링이 끝나기 전에 추가로 큰 변경을 쌓는 것은 부적절. A는 회귀 위험이 거의 0이며 monitoring window를 자연스럽게 제공.
4. **합리성** — silent no-op 플래그는 health_report와 dataflow **두 리포트가 독립적으로 동일 결론**을 내린 항목입니다. 신뢰도가 매우 높고, 작업량도 작아 즉시 처리하는 것이 합리적.

**시나리오 A 완료 후 자연스러운 다음 단계:**
- 안정 monitoring window가 종료되면 시나리오 B를 착수 가능 (선결조건: 분해 sprint 전용 일정 확보 + `_initialize` / `_close_position` 마이크로 리팩토링 선행).
- 시나리오 C는 god-module 비대를 더 키우므로, B 완료 후 진입하는 것이 장기 비용 최소.

---

## 6. 통계 요약

| 항목 | 값 | 출처 |
| --- | --- | --- |
| 4계층 위반 (HARD 진성) | **0** | layer §1 |
| 4계층 위반 (HARD, composition root) | 4 (정상 패턴, 문서 보강 권장) | layer §1 |
| 4계층 위반 (SOFT, god-module) | 1 (`bot_instance` fan-out 48) | layer §2 |
| 순환 import | 0 | layer/cohesion |
| 양방향 import 페어 | 1 (Discord SDK 정상 패턴) | cohesion §2 |
| 미사용 import | 0 | health_report cross-check |
| god-module 후보 (LOC>1500 또는 out>20) | 2 (`bot_instance` 3657, `executor` 1464) | cohesion §1 |
| Class god-objects (메서드 30+) | 5 (BotInstance 60, RedisStateManager 40, TradingMetrics 36, DummyRedis 35, MultiBotManager 33) | cohesion §3 |
| 장문 함수 (>100 LOC 또는 >15 br) | 29 (그중 8개가 `bot_instance.py`에 집중) | cohesion §4 |
| coupling pair 핫스팟 | 1 (`discord_bot.client`↔`views`, 정상) | cohesion §2 |
| APEX-V 컴포넌트 통합 | 22/25 (88%) | dataflow §4 |
| 미통합 APEX-V 컴포넌트 | 3 (BOCPD, LGB, LiqCascade Mode B) | dataflow §4 |
| 명세 ↔ 실제 흐름 차이 | 10 | dataflow §3 |
| Silent No-op 플래그 | 2 (`use_bocpd_regime`, `use_lightgbm_dead_zone`) | dataflow C-3 + health_report |

---

## 7. 안전 가드

- 본 리포트는 분석만 수행. 코드 변경 없음.
- 시나리오 B 분해 작업은 **항목별 분리 PR + 전체 회귀 테스트(3022) + staging 24h 무인 운영 검증** 필수.
- `src/trading/`, `src/exchange/` 분해는 race condition 신규 발생 위험으로 **본 리포트는 보류 권장** (cohesion §1 god-2, god-4).
- 어떤 분해도 시그널 → 실행 흐름의 정확성을 보존해야 함. 특히 `_close_position`은 자금 추적·감사 로그·DB 기록·메트릭이 한 함수에 응집되어 있어 사유별 추출 시 트랜잭션 순서 보존이 필수.
- silent no-op 플래그를 제거하기로 결정할 경우 Redis에 직렬화된 페이로드의 역호환 마커(deprecated alias)를 함께 남기지 않으면 운영 중 봇 재시작 시 로드 실패 가능.

---

## 8. 후속 작업 위임 (선택 시)

- **시나리오 A 진행 시**: dataflow-tracer가 제안한 §7 다이어그램으로 CLAUDE.md 갱신 + BOCPD/LGB 처리 결정 PR. 검증: `pytest` + `ruff check` + `mypy`.
- **시나리오 B 진행 시**: cohesion §1 god-1 5-way 분해 제안서를 plan 문서(`docs/plans/`)로 승격 후 단계별 실행. 분해 전 `_initialize` / `_close_position` 마이크로 리팩토링(약점 2)을 선행 권장.
- **시나리오 C 진행 시**: 신규 기능이 `bot_instance.py`에 메서드를 추가하기 전 분해 sprint 일정을 미리 확보하여 부채 누적을 차단.

---

_본 리포트는 layer-boundary-analyst / module-cohesion-analyst / dataflow-tracer 3개 분석을 종합하고 health_report.md와 cross-check하여 작성됨._
