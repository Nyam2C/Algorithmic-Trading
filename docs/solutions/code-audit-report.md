---
title: "전체 코드 감사 보고서 (Code Audit Report)"
date: 2026-02-13
tags: [audit, security, trading-logic, infrastructure, P1-critical]
severity: P1
status: resolved
---

# High-Win Survival System — 전체 코드 감사 보고서

## Context

투자 결정 핵심 로직, 프로그램 흐름, 인프라 안전성을 기업/클라이언트 관점에서 전수 감사.
3개 병렬 감사팀 (트레이딩 흐름 / 시그널 로직 / 인프라 안전) 결과 종합.

---

## 1. 프로그램 흐름 (Trading Loop)

```
[5분 간격 루프]
1. Binance → 시세/캔들/24h 수집
2. 시그널 생성 (injected > ensemble > AI > rule_based)
3. 레짐 필터 (optional) → MTF 필터 (optional)
4. WAIT streak 진단
5. 긴급 청산 체크
6. 기존 포지션 관리 (Timecut / TP/SL 체크)
7. 리스크 체크 (쿨다운, 일일 손실)
8. 수동 승인 체크 (optional)
9. 노출도 체크 (optional)
10. 신규 진입 실행 → Binance 마켓 주문
```

---

## 2. P1 CRITICAL — 실돈 투입 전 반드시 수정

### P1-1. 거래소측 스탑로스 없음 — 봇 다운 시 무방비
- **파일**: `src/trading/executor.py`
- TP/SL이 **전부 봇 내부 폴링** (5분 간격). STOP_MARKET, TAKE_PROFIT_MARKET, OCO 주문 **제로**.
- 봇 크래시/네트워크 단절 시 열린 포지션에 **스탑이 없음**. 15~20x에서 5% 역행 = 마진 전액 손실.

### P1-2. 재시작 시 거래소 포지션 대조(Reconciliation) 없음
- **파일**: `src/bot_instance.py` `_initialize()`
- 시작 시 Redis에서 상태 복원만 함. **실제 거래소 포지션과 비교하지 않음**.
- 크래시 후 재시작 → 고아 포지션 방치 or 이중 포지션.

### P1-3. 일일 리스크 리셋이 실행되지 않음
- **파일**: `src/trading/risk_manager.py`
- `reset_daily_stats()`가 **봇 시작 시에만** 호출됨. 스케줄된 일일 리셋 **없음**.
- 여러 날 운영 시 "일일" 손실 한도가 "시작 이후 누적" 한도로 변질.

### P1-4. 기본 포지션 사이징이 하드코딩 $1,000
- **파일**: `src/trading/executor.py:109-110`
- `use_real_balance=False` (기본값) → `capital = 1000.0` 고정. 실잔고와 무관.

### P1-5. 기본 TP/SL이 1:1 — 수수료 차감 시 음의 기대값
- **파일**: `src/bot_config.py:16-35`
- 모든 리스크 레벨 TP% = SL%. Binance 수수료 적용 시 실제 R:R = 약 0.67:1.
- 승률 60%+ 필요 → 현 시그널로 불가능.

### P1-6. 시그널 전략 근본 결함 — 풀백 확인 없이 진입
- **파일**: `src/ai/rule_based.py`
- RSI < 45 + MA7 > MA25 시 즉시 LONG. **풀백 종료 확인(반전 신호) 없음** → 떨어지는 칼날.

### P1-7. 기본 레버리지 과도함
- **파일**: `src/bot_config.py:16-35`
- low=10x, medium=15x, high=20x. 20x에서 5% 역행 = 마진 100% 소진.

### P1-8. 빈 API 키로 봇 시작 가능
- **파일**: `src/config.py:143-174`
- API 키 기본값 `""`. 봇 시작 후 API 호출 시점에서 실패 → 포지션 오픈 후 클로즈 실패 가능.

---

## 3. P2 IMPORTANT — 빠른 시일 내 수정

| # | 영역 | 이슈 | 파일 |
|---|------|------|------|
| P2-1 | 실행 | 진입 가격이 체결가가 아닌 요청가로 저장 → PnL 오차 | `executor.py:219` |
| P2-2 | 실행 | 봇 종료 시 열린 포지션 청산 안 함 | `bot_instance.py:_cleanup()` |
| P2-3 | 리스크 | PnL 계산 불일치 (레버리지 적용 일관성 없음) | `pnl.py` vs `bot_instance.py` |
| P2-4 | 서킷브레이커 | 데이터 API 실패가 주문 API까지 차단 (같은 CB 인스턴스) | `binance.py` |
| P2-5 | 시그널 | partial_trend_mode 기본 켜짐 → 레짐 필터 사실상 무력화 | `regime_detector.py` |
| P2-6 | 시그널 | 앙상블 가중치 임의 + 단일 소스가 전체 오버라이드 가능 | `ensemble.py` |
| P2-7 | 시그널 | Gemini 신뢰도 하드코딩 0.8 (실제 확신도 무관) | `ensemble.py:269` |
| P2-8 | 시그널 | MACD 미계산 → 스코어링 15% 사각지대 | `scoring.py` vs `indicators.py` |
| P2-9 | 시그널 | 볼륨 스코어가 항상 LONG 편향 | `scoring.py:300-324` |
| P2-10 | MTF | 15분봉 MA25 단일 비교 → 노이즈 | `multi_timeframe.py` |
| P2-11 | 상태 | DummyRedis가 상태 무음 폐기 → 재시작 시 상태 손실 | `redis_state.py` |
| P2-12 | 인프라 | Redis 인증 없음 + 포트 노출 | `docker-compose.yml` |
| P2-13 | 인프라 | PostgreSQL 기본 비밀번호 `devpassword` | `docker-compose.yml` |
| P2-14 | API | API 인증이 완전 선택사항 | `dependencies.py` |
| P2-15 | API | n8n 시그널 주입이 RiskManager 우회 | `n8n.py` |
| P2-16 | API | /metrics 인증 없이 공개 | `health.py` |
| P2-17 | Discord | 긴급 청산이 최대 5분 지연 | Discord client |
| P2-18 | 배포 | Docker 리소스 제한/재시작 정책 없음 | `docker-compose.yml` |
| P2-19 | 배포 | 로그 로테이션/DB 백업 없음 | 전체 |
| P2-20 | CI | pip-audit/mypy/pytest non-blocking | `ci.yml` |
| P2-21 | 전략 | 2시간 타임컷이 수익 포지션도 무차별 청산 | `executor.py` |
| P2-22 | 전략 | 파라미터에 백테스트 근거 없음 | 전체 |
| P2-23 | DB | trade entry와 position state 비원자적 | `trade_history.py` |
| P2-24 | 설정 | BotConfig에 mainnet 안전장치 누락 | `bot_config.py` |

---

## 4. 잘 만든 부분

- SQL 인젝션 방어 (모든 쿼리 parameterized)
- 서킷 브레이커 + 리트라이 (API 복원력)
- 타이밍 세이프 비교 (`hmac.compare_digest`)
- 다중 시그널 필터링 레이어
- 수동 승인 시스템 (첫 N거래)
- 메인넷 안전 스위치 (`I_UNDERSTAND_THIS_IS_REAL_MONEY`)
- Pydantic 검증, DI 패턴, 1600+ 테스트, 구조화 로깅 + Prometheus

---

## 5. 종합 평가

| 환경 | 점수 | 판정 |
|------|------|------|
| 테스트넷 | **6/10** | 실험용으로 적합 |
| **라이브 트레이딩** | **2/10** | **현 상태로 실돈 투입 불가** |

### 핵심 3가지 이유:
1. **거래소측 스탑로스 부재**: 봇 다운 = 무방비 → 15x 플래시 크래시 = 계좌 청산
2. **음의 기대값 구조**: 1:1 TP/SL + 수수료 + 반전 확인 없는 시그널 = 장기 손실 확정
3. **크래시 복구 없음**: 재시작 시 거래소 대조 안 함 → 이중/고아 포지션

---

## 6. 최소 수정 로드맵

### Phase 1: 자금 보호 (필수)
1. 거래소측 STOP_MARKET / TAKE_PROFIT_MARKET 배치
2. 시작 시 거래소 포지션 Reconciliation
3. `use_atr_tp_sl=True` 기본 활성화 (최소 2:1 R:R)
4. 기본 레버리지 3~5x로 하향
5. 일일 리스크 리셋 스케줄링

### Phase 2: 시그널 품질 개선
6. 풀백 반전 확인 로직 추가
7. RSI 기본값 30/70으로 변경
8. MACD 계산 + 스코어링 연결
9. 볼륨 스코어 방향성 보정

### Phase 3: 프로덕션 준비
10. API 인증 필수화
11. Redis/PostgreSQL 인증 강화
12. Docker restart 정책 + 리소스 제한
13. 긴급 청산 즉시 실행 (5분 대기 제거)
14. 빈 API 키 시작 차단
