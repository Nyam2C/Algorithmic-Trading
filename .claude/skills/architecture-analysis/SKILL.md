---
name: architecture-analysis
description: 거대 Python 거래봇의 아키텍처를 읽기 전용으로 분석한다. 계층 분리(Presentation/Application/Domain/Infra) 위반, 모듈 응집도/결합도, god-module(특히 bot_instance.py out-degree 48), 데이터 흐름과 AI 파이프라인 통합 구조(APEX-V 5-Gate, Confluence Engine, 6채널 시그널)를 3개 전문 에이전트로 병렬 분석하여 의사결정 카드 형태의 단일 리포트를 생성. 사용자가 "아키텍처 분석", "구조 분석", "리팩토링 방향", "분해할까", "다음에 뭘 할지", "god-module", "계층 위반", "결합도", "데이터 흐름 검증", "APEX-V 통합 상태"를 언급하거나 코드 구조 차원의 의사결정을 위한 진단을 요청할 때 반드시 이 스킬을 사용. 코드 변경/커밋은 절대 하지 않는 읽기 전용 메타 작업이며, code-health-audit 스킬과는 다른 도메인(헬스=청소 vs 아키텍처=구조)이다.
---

# Architecture Analysis Orchestrator

거대 거래봇 프로젝트의 **구조와 설계** 차원을 진단하는 워크플로우.

## 핵심 보장

1. **읽기 전용** — 코드/설정/git 변경 없음.
2. **부분 실패 허용** — 3개 분석 중 하나가 실패해도 나머지로 리포트 생성.
3. **시간 상한** — 각 에이전트 5분, 전체 20분.
4. **재사용** — code-health-audit이 만든 import 그래프(`_workspace/code-audit/_import_graph_result.json`)와 health_report.md를 입력으로 활용해 중복 분석 방지.
5. **의사결정 카드 산출** — "분석 끝, 알아서 결정해라"가 아니라 "선택지 3개 + 추천 + 트레이드오프"를 명확히 제시.

## Phase 0: 컨텍스트 확인

1. `_workspace/architecture-analysis/` 존재 여부:
   - **존재 + 부분 재실행 요청** → 해당 에이전트만 재호출
   - **존재 + 새 분석 요청** → `_workspace/architecture-analysis-prev-<YYYYMMDD>/`로 이동 후 새로 생성
   - **미존재** → 신규 실행
2. `_workspace/code-audit/_import_graph_result.json` 존재 확인 — 있으면 재사용, 없으면 에이전트가 직접 빌드.
3. `docs/audits/health_report.md` 존재 확인 — 있으면 architecture-reporter가 cross-check 입력으로 사용.
4. `git status` 점검 — 변경 파일이 있어도 분석은 진행 (working tree 기준).

## Phase 1: 환경 준비 (1분 이내)

이전 헬스 감사 산출물 점검:
- `_workspace/code-audit/_import_graph_result.json` 형식 확인
- `_workspace/code-audit/01_dead_code.md` 의 미통합 컴포넌트(BOCPD/LGB) 목록 추출 — dataflow-tracer가 사용

이전 산출물이 없거나 7일 이상 묵었으면 사용자에게 "헬스 감사부터 다시 하시겠습니까?" 질문.

## Phase 2: 3개 분석 에이전트 병렬 실행 (각 5분 이내)

**실행 모드: 에이전트 팀 (팬아웃)**

`Agent` 도구로 3개 에이전트를 단일 메시지에서 병렬 호출 (`run_in_background: true`):

| 에이전트 | 산출물 |
|---|---|
| `layer-boundary-analyst` | `_workspace/architecture-analysis/01_layer_boundary.md` |
| `module-cohesion-analyst` | `_workspace/architecture-analysis/02_module_cohesion.md` |
| `dataflow-tracer` | `_workspace/architecture-analysis/03_dataflow.md` |

**각 호출에 반드시:**
- `subagent_type: "general-purpose"`
- `model: "opus"`
- `prompt`: 에이전트 정의 파일을 읽고 그 지침을 따르라는 명시 + 작업 루트 + 산출물 경로 + 시간 상한

## Phase 3: 결과 수집 및 검증

3개 에이전트 완료 후:
1. 각 산출물 파일 존재 확인
2. 각 파일의 첫 줄 STATUS 헤더 확인
3. PARTIAL/누락 보고서는 architecture-reporter에 명시적으로 알림

## Phase 4: 종합 리포트 생성 (architecture-reporter)

`Agent` 도구로 단일 호출 (병렬 아님 — 의존성 있음):
- `subagent_type: "general-purpose"`, `model: "opus"`
- 입력: 3개 분석 산출물 + `docs/audits/health_report.md`(cross-check) + `CLAUDE.md`(원칙) + `.claude/PROJECT_OVERVIEW.md`(맥락)
- 출력: `docs/audits/architecture_report.md`

## Phase 5: 최종 보고

사용자에게:
1. `docs/audits/architecture_report.md` 생성 완료 알림
2. **TL;DR + 의사결정 카드 직접 인용** (사용자가 파일 안 열어도 핵심 파악 가능)
3. 3개 시나리오(안정/부분 분해/새 기능) 중 하나를 추천 — 근거 제시
4. 사용자 결정 대기 → 별도 세션에서 실행

## 데이터 전달 프로토콜

- **파일 기반** — 모든 중간 산출물은 `_workspace/architecture-analysis/`.
- 파일명 규칙: `{순번}_{도메인}.md` (예: `01_layer_boundary.md`)
- 최종 산출물: `docs/audits/architecture_report.md` (영구 보존, git 추적)
- code-health-audit 산출물과의 cross-link: 같은 god-module이 두 리포트에 등장하면 architecture-reporter가 강조.

## 에러 핸들링

| 시나리오 | 처리 |
|---|---|
| 에이전트 1개 실패 | 해당 산출물 누락, 다른 2개로 진행. architecture-reporter가 누락 명시. |
| 에이전트 2+개 실패 | 사용자에게 보고, 재시도 또는 부분 리포트 생성 선택. |
| import_graph_result.json 누락 | 각 에이전트가 자체 ripgrep + AST로 빠르게 그래프 빌드 (예산 2분). |
| 시간 초과 | 부분 결과로 STATUS=PARTIAL. |

## 보안/안전 가드

- **절대 금지**: `git commit/push/reset`, `rm`, source 파일 `Edit`/`Write`.
- **허용**: `_workspace/architecture-analysis/` 및 `docs/audits/architecture_report.md` 생성, 정적 분석 (ripgrep, python AST).
- 어떤 에이전트도 실행 가능한 코드를 변경하지 않음 — 데이터 흐름 추적도 호출은 하지 않고 정적 추적만.

## 테스트 시나리오

**정상 흐름:**
1. 사용자: "아키텍처 분석해줘"
2. Phase 0~5 순차 실행
3. `docs/audits/architecture_report.md` 생성, TL;DR + 3 시나리오 인용
4. 사용자가 선택지 결정 → 별도 세션에서 분해/새 기능/안정 작업

**에러 흐름 1 — import 그래프 결과 부재:**
1. layer-boundary-analyst가 _workspace/code-audit/_import_graph_result.json 없음 감지
2. 자체적으로 빠른 그래프 빌드 (2분 예산)
3. STATUS=COMPLETE 또는 PARTIAL로 진행
4. architecture-reporter가 누락 사실 표기

**에러 흐름 2 — bot_instance.py가 너무 거대해서 dataflow 추적 5분 초과:**
1. dataflow-tracer가 핵심 단계만 대표 추적, STATUS=PARTIAL
2. architecture-reporter가 "데이터 흐름 분석 부분 완료, 추가 세션 필요" 명시

## 후속 작업 키워드 (description에 반영됨)

- "아키텍처 분석 다시", "구조 분석 업데이트"
- "<영역> 깊이 분석"
- "분해할까", "리팩토링 방향"
- "다음에 뭘 할지"

이 키워드들은 Phase 0의 컨텍스트 확인에서 부분 재실행으로 라우팅.
