---
name: code-health-audit
description: 거대 Python 프로젝트(High-Win Survival Bot, 1860+ 테스트)의 코드 헬스를 읽기 전용으로 종합 감사한다. 데드코드, 미사용 import, 순환 import, 테스트 커버리지 갭, legacy 잔재를 4개 전문 에이전트로 병렬 분석하여 P1/P2/P3 리포트를 생성. 사용자가 "코드 감사", "데드코드", "리팩토링 분석", "헬스 체크", "전체 코드 분석", "오래된 코드 정리", "레거시 정리"를 언급하거나, 코드베이스 전반의 상태/품질을 점검하고 싶다고 할 때 반드시 이 스킬을 사용. 코드 변경/커밋은 절대 하지 않는 읽기 전용 메타 작업이며, 후속 리팩토링은 별도 세션에서 사용자가 우선순위를 지정한 항목만 수행한다.
---

# Code Health Audit Orchestrator

이 거대 거래봇 프로젝트(src/ 111 모듈, tests/ 114 모듈, 1860+ 테스트)의 헬스를 안전하게 감사하는 워크플로우.

## 핵심 보장

1. **읽기 전용** — 어떤 에이전트도 코드/설정을 변경하지 않는다. git 커밋/푸시/체크아웃 없음.
2. **부분 실패 허용** — 4개 분석 중 하나가 실패해도 나머지로 리포트 생성.
3. **실행 시간 상한** — 각 에이전트 5분 이내, 전체 20분 이내. 초과 시 부분 결과로 진행.
4. **재현 가능** — 모든 중간 산출물은 `_workspace/code-audit/`에 보존.

## Phase 0: 컨텍스트 확인

워크플로우 시작 직후 다음을 확인:

1. `_workspace/code-audit/` 존재 여부
   - **존재 + 사용자가 부분 재실행 요청** → 해당 에이전트만 재호출, 다른 산출물 유지
   - **존재 + 사용자가 새 분석 요청** → 기존 디렉토리를 `_workspace/code-audit-prev-<YYYYMMDD>/`로 이동 후 새로 생성
   - **미존재** → 신규 실행
2. `git status`로 워킹 트리 상태 점검 — 변경 파일이 있으면 사용자에게 경고만 (계속 진행 가능, 단 분석은 working tree 기준).
3. `python3.10 --version` 확인 — 3.10이 없으면 `python3 --version`으로 폴백.

## Phase 1: 환경 준비 (1분 이내)

다음을 빠르게 확인하고 결과를 _workspace/code-audit/_environment.md 에 기록:

- ruff, vulture, pytest 설치 여부 (없으면 폴백 경로 알림)
- 의존성 import 가능 여부 (`python3.10 -c "import src.main"` 시도)

이 단계의 실패는 곧 다음 단계의 입력이 된다 (예: pytest collect 실패는 test-coverage-auditor의 P1 발견).

## Phase 2: 4개 분석 에이전트 병렬 실행 (각 5분 이내)

**실행 모드: 에이전트 팀 (팬아웃)**

`Agent` 도구로 4개 에이전트를 **단일 메시지 안에서 병렬** 호출 (`run_in_background: true`):

| 순서 | 에이전트 | 산출물 |
|---|---|---|
| 동시 | `dead-code-hunter` | `_workspace/code-audit/01_dead_code.md` |
| 동시 | `import-graph-analyst` | `_workspace/code-audit/02_import_graph.md` |
| 동시 | `test-coverage-auditor` | `_workspace/code-audit/03_test_coverage.md` |
| 동시 | `legacy-detector` | `_workspace/code-audit/04_legacy_residue.md` |

**각 호출에 반드시:**
- `subagent_type: "general-purpose"`
- `model: "opus"`
- `description: "<1줄 설명>"`
- `prompt`: 에이전트 정의 파일을 읽고 그 지침을 따르라는 명시 + 작업 루트 + 산출물 경로

**Agent 도구 호출 예시 (한 메시지에 4개):**

```
Agent(
  description="Dead code analysis",
  subagent_type="general-purpose",
  model="opus",
  prompt="""
  Read .claude/agents/dead-code-hunter.md and follow its instructions exactly.
  Working directory: /mnt/c/Users/박/Desktop/hi/Algorithmic-Trading
  Output file: _workspace/code-audit/01_dead_code.md
  Time budget: 5 minutes. If you exceed, write PARTIAL status and stop.
  Do NOT modify any source files. Read-only analysis.
  """,
  run_in_background=true
)
```

(나머지 3개도 같은 패턴.)

## Phase 3: 결과 수집 및 검증

4개 에이전트 완료 후:

1. 각 산출물 파일이 존재하는지 확인 (`ls _workspace/code-audit/`)
2. 각 파일의 첫 줄 STATUS 헤더 확인
3. 누락 / FAILED 인 산출물은 audit-reporter에게 명시적으로 알림

## Phase 4: 종합 리포트 생성 (audit-reporter)

`Agent` 도구로 단일 호출:

```
Agent(
  description="Synthesize health report",
  subagent_type="general-purpose",
  model="opus",
  prompt="""
  Read .claude/agents/audit-reporter.md and follow its instructions exactly.
  Inputs: _workspace/code-audit/01_dead_code.md, 02_import_graph.md,
          03_test_coverage.md, 04_legacy_residue.md
  Reference: CLAUDE.md (P1/P2/P3 criteria)
  Output: docs/audits/health_report.md
  Do NOT modify source code. Read-only synthesis.
  """
)
```

(병렬 아님 — 다른 4개 산출물에 의존.)

## Phase 5: 최종 보고

사용자에게:
1. `docs/audits/health_report.md` 생성 완료 알림
2. 리포트 TL;DR 섹션을 직접 읽어서 인용 (사용자가 파일을 안 열어도 핵심 파악 가능)
3. **다음 행동 선택지 제시**:
   - "P1 N건만 다음 세션에서 처리하시겠습니까?"
   - "특정 영역(trading/exchange 등)을 더 깊게 보겠습니까?"
4. 현재 세션은 여기서 종료 — 코드 변경/커밋은 사용자 명시 승인 후 별도 세션.

## 데이터 전달 프로토콜

- **파일 기반** — 모든 중간 산출물은 `_workspace/code-audit/`에 저장.
- 파일명 규칙: `{순번}_{영역}.md` (예: `01_dead_code.md`)
- 최종 산출물: `docs/audits/health_report.md` (사용자 영구 참조)
- 임시 스크립트(`_dead_code_scan.py`, `_import_graph.py`, `_pytest_collect.log`)는 `_workspace/`에 남겨 재현성 확보.

## 에러 핸들링

| 시나리오 | 처리 |
|---|---|
| 에이전트 1개 실패 | 해당 산출물 누락, 다른 3개로 진행. audit-reporter가 누락 명시. |
| 에이전트 2+개 실패 | 사용자에게 보고, 재시도 또는 부분 리포트 생성 선택. |
| 도구(ruff/vulture) 미설치 | pip 설치 시도 → 실패 시 폴백 스크립트. |
| pytest collect 자체가 import 에러 | test-coverage-auditor가 이를 P1 발견으로 보고. |
| 시간 초과 | 부분 결과로 STATUS=PARTIAL 보고. |
| 파일 저장 실패 (Korean path 이슈) | `Write` 대신 Bash python heredoc으로 재시도 (CLAUDE.md Common Pitfalls 참조). |

## 보안/안전 가드

- **절대 금지**: `git commit`, `git push`, `git reset`, `rm`, source 파일 `Edit`/`Write`.
- **허용**: `_workspace/`, `docs/audits/` 하위 파일 생성. `python3.10 -m pytest --collect-only` (실행만, 변경 없음).
- 에이전트가 위 금지 명령을 실행하려 하면 즉시 중단하고 사용자에게 보고.

## 테스트 시나리오

**정상 흐름:**
1. 사용자: "코드 감사해줘"
2. Phase 0~5 순차 실행
3. `docs/audits/health_report.md` 생성, TL;DR 보고
4. 사용자가 P1 항목 우선순위 지정 → 새 세션에서 리팩토링

**에러 흐름 1 — pytest collect 실패:**
1. test-coverage-auditor가 conftest import 에러 발견
2. STATUS=PARTIAL 으로 보고, 에러 항목을 P1으로 분류
3. 다른 3개 분석은 정상 완료
4. audit-reporter가 통합 리포트의 P1 섹션 최상위에 conftest 에러 배치

**에러 흐름 2 — 거대 그래프로 import-graph-analyst 시간 초과:**
1. 5분 타임아웃, 부분 결과만 _workspace에 저장
2. STATUS=PARTIAL — 5개 디렉토리 중 3개만 분석
3. audit-reporter가 "import 분석 부분 완료, 추가 세션 필요" 명시

## 후속 작업 키워드 (description에 반영됨)

- "코드 감사 다시", "헬스 체크 다시", "분석 업데이트"
- "P1만 다시", "test-coverage 부분만 재실행"
- "<영역> 깊이 분석"

이 키워드들은 Phase 0의 컨텍스트 확인 단계에서 부분 재실행으로 라우팅된다.
