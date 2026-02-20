# High-Win Survival System - 프로젝트 개요

## 목차
1. [프로젝트 소개](#1-프로젝트-소개)
2. [기술 스택](#2-기술-스택)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [핵심 모듈 상세](#4-핵심-모듈-상세)
5. [데이터 흐름](#5-데이터-흐름)
6. [트레이딩 전략](#6-트레이딩-전략)
7. [개발 계획 (IMPLEMENTATION_PLANS)](#7-개발-계획-implementation_plans)
8. [실행 방법](#8-실행-방법)
9. [API 레퍼런스](#9-api-레퍼런스)

---

## 1. 프로젝트 소개

### 개요
**High-Win Survival System**은 비트코인 선물 자동매매 봇입니다. Binance Futures Testnet에서 동작하며, 기술적 지표와 AI(Google Gemini)를 활용하여 매매 신호를 생성합니다.

### 철학
- **생존 우선**: 높은 승률(Win Rate)보다 자본 보존 중심
- **자동화**: 24/7 무인 운영 가능
- **모니터링**: Discord를 통한 원격 제어 및 알림
- **테스트 우선**: TDD 기반 개발, 90%+ 커버리지 목표

### 구현된 기능
| 카테고리 | 기능 |
|----------|------|
| 자동매매 | 단일/멀티봇 트레이딩, Binance Futures API |
| AI | Gemini AI 시그널, 메모리 시스템 (과거 거래 학습) |
| 리스크 관리 | 일일 손실 한도, 연속 손실 쿨다운, 드로다운 모니터링 |
| 전략 | 마켓 레짐 감지, 다중 타임프레임 분석, ATR 기반 TP/SL |
| 모니터링 | Prometheus 메트릭, Grafana 대시보드, 감사 로그 |
| 제어 | Discord 봇, REST API, 수동 승인 모드 |
| 검증 | 백테스트 엔진, 2863+ 테스트 |

---

## 2. 기술 스택

| 영역 | 기술 | 버전/상세 |
|------|------|----------|
| 언어 | Python | 3.10+ |
| 거래소 API | Binance Futures | python-binance (Testnet) |
| AI | Google Gemini | gemini-2.0-flash-exp |
| 데이터베이스 | PostgreSQL | asyncpg |
| 캐시/상태 | Redis | redis>=5.0.0 |
| REST API | FastAPI | 0.109.0+ |
| 알림/제어 | Discord Bot | discord.py |
| 모니터링 | Grafana + Loki | Docker Compose |
| 테스트 | pytest | 2863+ 테스트 |
| 코드 품질 | ruff, mypy | 린트 + 타입 체크 ✅ 통과 |
| CI/CD | GitHub Actions | 자동 테스트 |

---

## 3. 프로젝트 구조

```
Algorithmic-Trading/
├── src/                          # 메인 소스 코드
│   ├── main.py                   # 진입점 & 메인 루프
│   ├── config.py                 # 환경 설정 관리
│   ├── bot_config.py             # 멀티봇 설정 모델
│   ├── bot_instance.py           # 개별 봇 인스턴스
│   ├── bot_manager.py            # 멀티봇 관리자
│   ├── api/                      # REST API
│   │   ├── main.py               # FastAPI 앱 팩토리
│   │   ├── config.py             # API 설정
│   │   ├── dependencies.py       # 의존성 주입
│   │   ├── routes/               # API 라우터
│   │   │   ├── health.py         # /health, /ready
│   │   │   ├── bots.py           # /api/bots CRUD
│   │   │   ├── n8n.py            # /api/n8n 웹훅
│   │   │   └── analytics.py      # /api/analytics
│   │   ├── schemas/              # 요청/응답 모델
│   │   └── services/             # 비즈니스 로직
│   ├── analytics/                # 거래 분석
│   │   ├── trade_analyzer.py     # 거래 이력 분석기
│   │   └── memory_context.py     # AI 메모리 컨텍스트
│   ├── ai/                       # AI 신호 생성
│   │   ├── gemini.py             # Gemini AI 클라이언트
│   │   ├── enhanced_gemini.py    # 메모리 주입 Gemini
│   │   ├── ensemble.py           # 앙상블 시그널 엔진
│   │   ├── signals.py            # 신호 파싱/검증
│   │   └── prompts/              # AI 프롬프트 템플릿
│   ├── backtest/                 # 백테스트 프레임워크
│   │   └── engine.py             # 백테스트 엔진
│   ├── data/                     # 데이터 처리
│   │   ├── indicators.py         # 기술적 지표 (RSI, MA, ATR)
│   │   ├── regime_detector.py    # 마켓 레짐 감지
│   │   ├── multi_timeframe.py    # 다중 타임프레임 분석
│   │   └── market_data_formatter.py # Gemini용 데이터 압축
│   ├── exchange/                 # 거래소 API
│   │   └── binance.py            # Binance Testnet 클라이언트
│   ├── metrics/                  # 모니터링 메트릭
│   │   └── prometheus.py         # Prometheus 메트릭
│   ├── trading/                  # 주문 실행
│   │   ├── executor.py           # 포지션 관리
│   │   ├── risk_manager.py       # 리스크 관리
│   │   └── trade_approval.py     # 수동 승인 시스템
│   ├── storage/                  # 데이터 저장
│   │   ├── trade_history.py      # PostgreSQL 거래 기록
│   │   ├── redis_state.py        # Redis 상태 관리
│   │   └── audit_log.py          # 감사 로그
│   ├── discord_bot/              # Discord 봇
│   │   ├── client.py             # 봇 클라이언트
│   ├── commands/             # 슬래시 명령어 (11개 한글)
│   ├── permissions.py        # 권한 시스템
│   ├── embeds.py             # UI 컴포넌트
│   └── views.py              # Discord Views
│   └── utils/                    # 유틸리티
│       ├── retry.py              # 재시도 데코레이터
│       └── logging.py            # JSON 구조화 로깅
├── tests/                        # 테스트 코드 (1860+)
├── workflows/                    # n8n 워크플로우 템플릿
├── scripts/                      # 운영 스크립트
├── deploy/                       # Docker Compose 파일
├── db/                           # DB 스키마
│   ├── init.sql                  # 초기 스키마
│   └── migrations/               # 마이그레이션
│       ├── 001_multi_bot.sql     # 멀티봇 지원 스키마
│       ├── 002_analytics_views.sql # 분석용 뷰/함수
│       └── 003_audit_logs.sql    # 감사 로그
└── monitoring/                   # Grafana + Loki 설정
```

---

## 7. 구현 체크리스트

### 핵심 기능
| 기능 | 파일 | 설명 |
|------|------|------|
| Binance API | `src/exchange/binance.py` | Testnet/Mainnet 클라이언트 |
| 기술적 지표 | `src/data/indicators.py` | RSI, MA, ATR, Volume |
| 앙상블 신호 | `src/ai/ensemble.py` | 6채널 + Confluence Engine |
| AI 신호 | `src/ai/gemini.py` | Gemini AI 클라이언트 |
| 주문 실행 | `src/trading/executor.py` | Market/Limit Order, TP/SL |
| 거래 기록 | `src/storage/trade_history.py` | PostgreSQL 저장 |
| Discord 봇 | `src/discord_bot/bot.py` | 원격 제어 UI |

### 멀티봇 시스템
| 기능 | 파일 | 설명 |
|------|------|------|
| 봇 설정 | `src/bot_config.py` | Pydantic 모델, risk_level |
| 봇 인스턴스 | `src/bot_instance.py` | 개별 봇 트레이딩 루프 |
| 봇 관리자 | `src/bot_manager.py` | 여러 봇 관리/조율 |
| REST API | `src/api/` | FastAPI 엔드포인트 |
| Redis 상태 | `src/storage/redis_state.py` | 봇 상태 영구 저장 |

### 리스크 관리
| 기능 | 파일 | 설명 |
|------|------|------|
| 리스크 관리자 | `src/trading/risk_manager.py` | 일일 손실 한도, 쿨다운, 드로다운 |
| 수동 승인 | `src/trading/trade_approval.py` | 첫 N거래 수동 확인 |

### 전략 고도화
| 기능 | 파일 | 설명 |
|------|------|------|
| 레짐 감지 | `src/data/regime_detector.py` | 횡보장 진입 회피 |
| 다중 타임프레임 | `src/data/multi_timeframe.py` | 상위 TF 추세 확인 |
| 백테스트 | `src/backtest/engine.py` | 전략 시뮬레이션 |

### AI 메모리 시스템
| 기능 | 파일 | 설명 |
|------|------|------|
| 거래 분석기 | `src/analytics/trade_analyzer.py` | RSI별/시간대별 통계 |
| 메모리 컨텍스트 | `src/analytics/memory_context.py` | AI 프롬프트 빌더 |
| 메모리 주입 AI | `src/ai/enhanced_gemini.py` | 과거 성과 학습 |

### 모니터링
| 기능 | 파일 | 설명 |
|------|------|------|
| Prometheus 메트릭 | `src/metrics/prometheus.py` | /metrics 엔드포인트 |
| 감사 로그 | `src/storage/audit_log.py` | 모든 이벤트 기록 |
| JSON 로깅 | `src/utils/logging.py` | CloudWatch/Loki 호환 |

### Phase 5: 통합 완료 (2026-02-12 구현)
| 기능 | 파일 | 설명 |
|------|------|------|
| SHORT PnL 수정 (P1) | `src/bot_instance.py` | abs() + side별 PnL 계산 |
| update_balance 연결 (P1) | `src/bot_instance.py` | 매 루프 드로다운 추적 |
| ATR 환경변수 매핑 | `src/config.py` | USE_ATR_TP_SL, ATR_*_MULTIPLIER |
| SignalTracker 통합 | `src/bot_instance.py` | 인메모리 신호 추적 |
| Prometheus 통합 | `src/bot_instance.py` | 거래/PnL 메트릭 기록 |
| MTF 통합 | `src/bot_instance.py`, `src/bot_config.py` | 15분봉 필터 (use_mtf_filter) |
| Ensemble 통합 | `src/bot_instance.py`, `src/bot_config.py` | 앙상블 시그널 (use_ensemble) |
| TradeApproval 통합 | `src/bot_instance.py`, `src/bot_config.py` | 비차단 수동 승인 |
| Exposure Check 연결 | `src/bot_manager.py`, `src/bot_instance.py` | 콜백 기반 노출도 제한 |

### Phase 6: 개선 시스템 (2026-02-04 구현)
| 기능 | 파일 | 설명 |
|------|------|------|
| 신호 추적 | `src/analytics/signal_tracker.py` | AI 신호 성과 추적 및 통계 |
| Rate Limiting | `src/api/middleware/rate_limit.py` | DoS 방지 미들웨어 |
| 신호 이유 로깅 | `src/ai/gemini.py` | 온도 0.3, 신호 생성 이유 포함 |
| Discord 통계 | `src/discord_bot/commands/monitoring.py` | /signal-stats 명령어 |

### Discord 권한 시스템 (2026-02-04 구현)
| 기능 | 파일 | 설명 |
|------|------|------|
| 권한 모듈 | `src/discord_bot/permissions.py` | 권한 레벨 정의 및 체크 |
| 제어 명령어 권한 | `src/discord_bot/commands/control.py` | TRADER/ADMIN 권한 적용 |
| UI 권한 체크 | `src/discord_bot/views.py` | 버튼 클릭 시 권한 검증 |

### Observability & Monitoring 개선 (2026-02-12 구현)
| 기능 | 파일 | 설명 |
|------|------|------|
| 로그 파이프라인 수리 | `monitoring/promtail/promtail-config.yml` | .json.log 경로 수정 |
| 거래 전용 로그 | `src/utils/logging.py` | trade.json.log 필터 싱크 |
| AI 시그널 전용 로그 | `src/utils/logging.py` | ai_signal.json.log 필터 싱크 |
| 거래 이벤트 로깅 | `src/bot_instance.py` | TRADE_OPEN/TRADE_CLOSE event_type |
| Prometheus 서버 추가 | `monitoring/docker-compose.yml` | prom/prometheus:v2.49.1 컨테이너 |
| Prometheus 설정 | `monitoring/prometheus/prometheus.yml` | 15초 스크래핑 |
| Prometheus 데이터소스 | `monitoring/grafana/provisioning/datasources/prometheus.yml` | Grafana 자동 연결 |
| 루프 메트릭 | `src/metrics/prometheus.py` | loop_duration, loop_total |
| 시그널 메트릭 | `src/metrics/prometheus.py` | signal_total (source별) |
| AI 응답시간 메트릭 | `src/metrics/prometheus.py` | ai_latency_seconds |
| API 지연시간 계측 | `src/exchange/binance.py` | get_current_price, get_klines 등 |
| 루프 타이밍 | `src/bot_instance.py` | _last_loop_duration, _last_loop_time |
| AI 의사결정 로거 | `src/ai/ai_logger.py` | AIDecisionLogger 클래스 |
| Gemini 계측 | `src/ai/gemini.py` | 프롬프트/응답/지연시간 로깅 |
| Enhanced Gemini 계측 | `src/ai/enhanced_gemini.py` | 메모리 컨텍스트 로깅 |
| Ensemble 계측 | `src/ai/ensemble.py` | 컴포넌트 신호 로깅 |
| 봇 상태 엔드포인트 | `src/api/routes/health.py` | GET /health/bots |
| Grafana 대시보드 개선 | `monitoring/grafana/dashboards/*.json` | Prometheus 패널 추가 |

### n8n 통합 재설계 (2026-02-15 구현)
| 기능 | 파일 | 설명 |
|------|------|------|
| /command 제거 | `src/api/routes/n8n.py` | /api/bots와 중복되는 명령 엔드포인트 삭제 |
| 콜백 서비스 연결 | `src/main.py` | N8NCallbackService를 MultiBotManager 콜백에 연결 |
| 시장 컨텍스트 수신 | `src/api/routes/n8n.py` | POST /api/n8n/market-context (Fear & Greed, 펀딩레이트) |
| Redis 시장 컨텍스트 | `src/storage/redis_state.py` | save/load_market_context (TTL 1시간) |
| 워크플로우 정리 | `workflows/` | 중복 삭제 + 6개 워크플로우 (시그널, 리포트, 에스컬레이션, 데이터, 저널, 헬스) |

---

## 구현 기능 상세

### 1. 리스크 관리 시스템 (RiskManager)
**파일**: `src/trading/risk_manager.py`

봇의 리스크를 실시간으로 관리하는 클래스입니다.

**기능:**
- 일일 손실 한도: -5% 도달 시 자동 거래 정지
- 연속 손실 카운터: 3연패 시 30분 쿨다운
- 드로다운 모니터링: 최대 10% 드로다운 추적

**설정 옵션:**
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| max_daily_loss_pct | 0.05 (5%) | 일일 최대 손실률 |
| max_drawdown_pct | 0.10 (10%) | 최대 드로다운 |
| max_consecutive_losses | 3 | 연속 손실 허용 횟수 |
| cooldown_minutes | 30 | 쿨다운 시간 (분) |

**사용 예시:**
```python
risk_manager = RiskManager(max_daily_loss_pct=0.05)
await risk_manager.reset_daily_stats(10000.0)
await risk_manager.track_trade_pnl(-100.0)
halt, reason = await risk_manager.should_halt_trading()
```

---

### 2. 마켓 레짐 감지 (RegimeDetector)
**파일**: `src/data/regime_detector.py`

MA 정렬과 ATR로 현재 시장 상태를 분류합니다.

**레짐 종류:**
| 레짐 | 조건 | 추천 액션 |
|------|------|----------|
| STRONG_UPTREND | MA7 > MA25 > MA99, ATR >= 1% | LONG 선호 |
| WEAK_UPTREND | MA7 > MA25 > MA99, ATR < 1% | 조심스러운 LONG |
| RANGING | MA 혼재 | 진입 회피 |
| WEAK_DOWNTREND | MA7 < MA25 < MA99, ATR < 1% | 조심스러운 SHORT |
| STRONG_DOWNTREND | MA7 < MA25 < MA99, ATR >= 1% | SHORT 선호 |

**핵심 로직:**
- 횡보장(RANGING)에서는 자동으로 WAIT 시그널 반환
- 강한 상승 추세에서 SHORT 시그널 필터링
- 강한 하락 추세에서 LONG 시그널 필터링

**사용 예시:**
```python
detector = RegimeDetector()
regime = detector.detect(market_data)
if regime == MarketRegime.RANGING:
    signal = "WAIT"
```

---

### 3. 다중 타임프레임 분석 (MultiTimeframeAnalyzer)
**파일**: `src/data/multi_timeframe.py`

상위 타임프레임(15분봉)의 추세를 확인하여 시그널을 필터링합니다.

**정렬 상태:**
| 상태 | 설명 |
|------|------|
| ALIGNED | 시그널과 상위 TF 추세 일치 |
| CONFLICTING | 시그널과 상위 TF 추세 충돌 -> WAIT |
| NEUTRAL | 판단 불가 |

**필터링 규칙:**
- LONG 시그널 + 15분봉 하락추세 -> WAIT
- SHORT 시그널 + 15분봉 상승추세 -> WAIT
- 추세 일치 시 -> 시그널 통과

**설정:**
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| tolerance_pct | 0.1% | MA25 근처 허용 범위 |
| strict_mode | False | True면 MA 정렬까지 확인 |

**사용 예시:**
```python
analyzer = MultiTimeframeAnalyzer()
filtered = analyzer.filter_signal("LONG", higher_tf_data)
if filtered == "WAIT":
    print("상위 TF와 충돌 - 진입 안함")
```

---

### 4. 백테스트 프레임워크 (BacktestEngine)
**파일**: `src/backtest/engine.py`

과거 데이터로 전략을 시뮬레이션합니다.

**주요 클래스:**
- `BacktestConfig`: 백테스트 설정
- `Trade`: 개별 거래 기록
- `BacktestResult`: 결과 (승률, 총손익, 최대 드로다운)

**설정 옵션:**
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| initial_capital | 10000.0 | 초기 자본 |
| leverage | 10 | 레버리지 |
| position_size_pct | 0.05 | 포지션 크기 (5%) |
| tp_pct | 0.01 | 익절 (1%) |
| sl_pct | 0.005 | 손절 (0.5%) |
| commission_pct | 0.0004 | 수수료 (0.04%) |
| timecut_bars | 100 | 시간 제한 (봉 개수) |

**결과 메트릭:**
- total_trades: 총 거래 수
- win_rate: 승률 (%)
- total_pnl: 총 손익
- max_drawdown: 최대 드로다운
- equity_curve: 자산 곡선

**사용 예시:**
```python
config = BacktestConfig(initial_capital=10000)
engine = BacktestEngine(config, candles)
result = engine.run(my_strategy)
print(f"Win rate: {result.win_rate}%")
```

---

### 5. Prometheus 메트릭 (TradingMetrics)
**파일**: `src/metrics/prometheus.py`

실시간 모니터링을 위한 Prometheus 메트릭을 제공합니다.

**메트릭 목록:**
| 메트릭 | 타입 | 레이블 | 설명 |
|--------|------|--------|------|
| trading_trades_total | Counter | bot_name, side, result | 총 거래 수 |
| trading_position_pnl_percent | Gauge | bot_name | 현재 포지션 PnL % |
| trading_trade_duration_seconds | Histogram | bot_name | 거래 지속시간 |
| trading_api_latency_seconds | Histogram | endpoint | API 지연시간 |
| trading_signal_confidence | Gauge | bot_name | 시그널 신뢰도 |

**엔드포인트:**
- `GET /metrics` - Prometheus 형식 메트릭 반환

**Grafana 연동:**
Prometheus를 데이터소스로 추가하여 대시보드 구성 가능

**사용 예시:**
```python
metrics = TradingMetrics.get_instance()
metrics.record_trade("btc-bot", "LONG", "win", 120.0)
metrics.record_position_pnl("btc-bot", 2.5)
```

---

### 6. 감사 로그 (AuditLogManager)
**파일**: `src/storage/audit_log.py`

모든 거래 및 봇 이벤트를 기록합니다.

**이벤트 타입:**
| 이벤트 | 설명 |
|--------|------|
| TRADE_OPEN | 포지션 진입 |
| TRADE_CLOSE | 포지션 청산 |
| BOT_PAUSE | 봇 일시정지 |
| BOT_RESUME | 봇 재시작 |
| EMERGENCY_CLOSE | 긴급 청산 |
| CONFIG_CHANGE | 설정 변경 |
| RISK_HALT | 리스크 한도 도달 |

**저장 방식:**
- PostgreSQL 영구 저장 (DB 연결 시)
- 인메모리 폴백 (DB 미연결 시)

**DB 스키마:** `db/migrations/003_audit_logs.sql`

**사용 예시:**
```python
manager = AuditLogManager()
await manager.log_trade_open("btc-bot", "LONG", 0.001, 50000.0)
logs = await manager.get_recent_logs(bot_name="btc-bot", limit=10)
```

---

### 7. 수동 승인 시스템 (TradeApprovalManager)
**파일**: `src/trading/trade_approval.py`

첫 N거래에 대해 수동 승인을 요구합니다.

**승인 상태:**
| 상태 | 설명 |
|------|------|
| PENDING | 승인 대기 중 |
| APPROVED | 승인됨 |
| REJECTED | 거부됨 |
| TIMEOUT | 시간 초과 |

**설정:**
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| manual_approval_enabled | True | 수동 승인 활성화 |
| manual_approval_trades | 5 | 수동 승인 필요 거래 수 |
| approval_timeout | 60 | 승인 대기 시간 (초) |

**Discord 연동:**
TradeApprovalRequest를 Discord Embed로 변환하여 승인 UI 제공 가능

**사용 예시:**
```python
manager = TradeApprovalManager(manual_approval_enabled=True)
if await manager.requires_approval("btc-bot"):
    request = await manager.create_request("btc-bot", "LONG", 50000, 0.001)
    # Discord에서 승인 대기
    await manager.approve(request.request_id, "user123")
```

---

## 멀티봇 아키텍처

### 위험도별 기본값
| Risk Level | 레버리지 | 포지션 크기 | TP/SL |
|------------|---------|------------|-------|
| low (보수적) | 10x | 3% | 0.3% |
| medium (중간) | 15x | 5% | 0.4% |
| high (공격적) | 20x | 8% | 0.6% |

### 통합 아키텍처
```
[trading-bot 컨테이너]
└─ src/main.py
   ├─ MultiBotManager (봇 생명주기 관리)
   ├─ FastAPI 서버 (uvicorn 내장, 포트 8000)
   ├─ Discord 봇 (원격 제어)
   └─ 기본 봇 (환경변수 기반 자동 생성)
```

---

### 8. Discord 권한 시스템 (PermissionLevel)
**파일**: `src/discord_bot/permissions.py`

Discord 봇 명령어에 권한 레벨을 적용하여 보안을 강화합니다.

**권한 레벨:**
| 레벨 | 값 | 명령어 |
|------|-----|--------|
| VIEWER | 1 | /대시보드, /상태, /포지션, /수익, /내역, /계정, /프롬프트, /핑 |
| TRADER | 2 | 위 + /제어 (일시정지/재개), /알림 |
| ADMIN | 3 | 위 + /제어 (시작/정지), /긴급청산 |

**환경변수:**
| 환경변수 | 설명 | 예시 |
|---------|------|------|
| DISCORD_ADMIN_USER_IDS | 관리자 사용자 ID (쉼표 구분) | 123456789,987654321 |
| DISCORD_ADMIN_ROLE_IDS | 관리자 역할 ID (쉼표 구분) | 111111111,222222222 |
| DISCORD_TRADER_ROLE_IDS | 트레이더 역할 ID (쉼표 구분) | 333333333,444444444 |

**권한 체크 순서:**
1. 사용자 ID가 `admin_user_ids`에 있으면 → ADMIN
2. 사용자 역할 중 `admin_role_ids`에 있으면 → ADMIN
3. 사용자 역할 중 `trader_role_ids`에 있으면 → TRADER
4. 그 외 모든 사용자 → VIEWER

**사용 예시:**
```python
from src.discord_bot.permissions import (
    PermissionLevel,
    check_permission,
    requires_permission,
)

# 직접 체크
if check_permission(interaction, PermissionLevel.ADMIN):
    await do_admin_action()

# 데코레이터 사용
@requires_permission(PermissionLevel.TRADER)
async def trader_command(interaction):
    ...
```

---

## 검증 상태
- **Ruff**: ✅ All checks passed!
- **MyPy**: ✅ Success: no issues found
- **테스트**: ✅ 2863 passed (APEX-V 전체 + 레거시 정리)

### 검증 방법
```bash
# 전체 스택 시작
./scripts/start.sh

# 상태 확인
./scripts/start.sh --status

# API 테스트
curl http://localhost:8000/health
curl http://localhost:8000/docs  # Swagger UI (개발 모드)
curl http://localhost:3000       # Grafana

# JSON 로깅 확인
docker logs trading-bot 2>&1 | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]"

# Redis 연결 확인
docker exec -it trading-redis redis-cli ping

# 봇 상태 확인
docker exec -it trading-redis redis-cli HGETALL "trading:bot:btc-bot:state"

# 컨테이너 재시작 후 상태 복구
docker-compose restart trading-bot
docker logs trading-bot 2>&1 | grep "상태 복구"

# API 헬스체크 (Redis 포함)
curl http://localhost:8000/health | jq .
# {"status": "healthy", "version": "1.0.0", "components": {"redis": true}}
```

---

*문서 작성일: 2026-02-14*
