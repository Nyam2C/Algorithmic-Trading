---
title: "코드 리뷰 관찰 포인트"
date: 2026-02-11
tags: [code-review, refactoring, tech-debt]
status: exploring
---

## 목적

전체 코드베이스 리뷰 중 발견한 관찰 포인트를 기록합니다.
P1(필수 수정) / P2(권장) / P3(개선 가능) 분류 기준 적용.

---

## src/main.py

- **[P3] `datetime.utcnow()` deprecated**: 109줄. Python 3.12+에서 deprecated. `datetime.now(timezone.utc)` 권장.
- **[P2] `bot_state` dict 동기화 문제**: 236~246줄. plain dict로 Discord 봇에 전달되지만 BotManager/BotInstance와 실시간 동기화 안 됨. 실제 상태와 괴리 가능.

## src/config.py

- **[P2] Pydantic v1 스타일 혼재**: `@validator` 사용 (6줄). `bot_config.py`는 `@field_validator` (v2). 프로젝트 내 일관성 부족.
- **[P2] ATR 환경변수 매핑 누락**: `use_atr_tp_sl`, `atr_tp_multiplier`, `atr_sl_multiplier`가 `TradingConfig`에 정의되어 있으나 `load_config()`에서 환경변수 매핑이 빠져 있어 항상 기본값만 사용됨.
- **[P3] 싱글톤 전역 변수 패턴**: 178~187줄. 테스트 시 `_config = None` 리셋 필요. `functools.lru_cache` 등 더 안전한 패턴 고려.

## src/bot_config.py

- **[P3] `class Config` v1 스타일**: 312줄. Pydantic v2에서는 `model_config = ConfigDict(validate_assignment=True)` 권장.

## src/config_loader.py

- **[P2] YAML 세부 파라미터 무시**: `BotYamlEntry.to_bot_config()` (65~83줄)에서 `leverage`, `position_size_pct` 등 세부 파라미터가 전달 안 됨. YAML에서 커스텀 값 지정 불가.
- **[P3] symbol validator 불일치**: `BotYamlEntry`는 대문자 변환만, `BotConfig`는 USDT 체크도 함. `BotConfig`에서 재검증되긴 하지만 불일치.

## src/bot_instance.py

- **[P2] PnL 계산 로직 분산**: 612~615줄. `executor.calculate_pnl_pct()`와 별도로 `pnl_usd`를 수동 계산. 계산 로직이 executor와 bot_instance에 분산되어 불일치 위험.
- **[P3] `_close_position`에서 position 이중 조회**: 600줄 `executor.get_position()` 호출 후 606줄 `executor.close_position()` 호출. 사이에 상태 변경 가능성 (race condition은 단일 스레드라 낮지만 논리적 중복).
- **[P3] 긴급 청산 시 포지션 없을 때 처리**: 744~749줄. `_emergency_close` 시 포지션 유무 확인 없이 `_close_position` 호출. 내부에서 처리하긴 하지만 명시적 가드 권장.
- **[P3] `_execute_single_loop` 메서드 길이**: 706~799줄 약 93줄. 분기가 많아 가독성 저하. 포지션 관리 로직 분리 고려.

## src/bot_manager.py

- **[P2] `get_exposure_summary()` sync/async 혼합**: 206~241줄. 이벤트 루프 상태에 따라 동기/비동기 분기 처리. `asyncio.run()`은 이미 루프가 있으면 실패. async로 통일 권장.
- **[P2] `can_open_position()`이 BotInstance에서 미호출**: 노출도 체크 메서드가 존재하지만 `bot_instance.py`의 `_open_position()`에서 호출하지 않아 실제로 노출도 제한이 작동 안 할 수 있음.
- **[P3] `remove_bot()`에서 `bot.stop()` 미호출**: 382~388줄. 태스크 cancel만 하고 cleanup(Redis, DB 해제)이 안 될 수 있음.
- **[P3] 콜백 설정 시 private 속성 직접 접근**: 315줄 `bot._on_signal_callback = callback`. setter 메서드 없이 private 속성 직접 수정.

## src/data/indicators.py

- **[P3] mutable default argument**: 33줄 `periods: list = [7, 25, 99]`. `None` 기본값 + 내부 할당 권장.
- **[P3] `iterrows()` 비효율**: 152줄 `analyze_candle_pattern()`. 벡터 연산 `(df["close"] > df["open"]).sum()` 권장.
- **[P2] 하드코딩된 타임프레임 가정**: "2-hour trend", "30min trend" 주석이 있지만 실제로는 입력 DataFrame 크기에 의존. 5분봉 × 24 = 2시간 전제가 명시적이지 않음.

## src/data/regime_detector.py

- **[P3] `assert` 사용**: 94줄. `python -O`에서 무시됨. 위에서 None 체크 완료이므로 실질 위험 낮지만 패턴으로 비권장.
- **[P3] 약한 추세에서 역추세 필터링 없음**: `WEAK_UPTREND` + SHORT, `WEAK_DOWNTREND` + LONG 조합 미필터링. 강한 추세에서만 역추세 차단.

## src/data/multi_timeframe.py

- **[P2] `bot_instance.py`에서 미사용**: `MultiTimeframeAnalyzer`가 트레이딩 루프에 통합 안 됨. CLAUDE.md에서는 핵심 설계 결정으로 명시.
- **[P3] 상위 TF 데이터 수집 경로 없음**: `_fetch_market_data()`가 단일 타임프레임만 가져옴. 15분봉 데이터 별도 수집 로직 부재.

## src/data/market_data_formatter.py

- **[P3] 미실현 PnL에 레버리지 미반영**: 186~189줄. 순수 가격 변동률만 계산. AI가 보는 정보와 실제 PnL 괴리 가능.
- **[P3] `estimate_tokens()` 부정확**: 253~259줄. 한글/영어 혼합에서 추정 정확도 낮음. 참고용이므로 큰 문제 아님.

## src/trading/executor.py

- **[P2] `open_position`과 `open_position_maker` 코드 중복**: 149~211줄 vs 213~322줄. 포지션 체크, 레버리지 설정, 사이징, position 저장 로직이 거의 동일. 공통 로직 추출 권장. ✅ 해결
- **[P2] `calculate_pnl_pct`에 레버리지 미반영**: 413~429줄. 순수 가격 변동률 반환. config TP/SL %가 레버리지 없는 값 기준이어야 함 — 혼동 가능.
- **[P3] 포지션 정밀도 하드코딩**: 115줄 `round(quantity, 3)`. BTC 외 심볼에서 다른 정밀도 필요.
- **[P3] 매 주문마다 `setup_leverage` 호출**: 172줄. 이미 같은 레버리지면 불필요한 API 호출.

## src/trading/risk_manager.py

- **[P2] 일일 통계 자동 리셋 없음**: `reset_daily_stats`가 수동 호출 전제. 날짜 변경 시 자동 리셋 로직 부재.
- **[P3] `update_balance` 미호출**: 드로다운 추적용이지만 트레이딩 루프에서 호출 없어 `_current_drawdown`이 항상 0.
- **[P3] 불필요한 async**: `track_trade_pnl`, `should_halt_trading` 등이 `async`지만 실제 `await` 없음.

## src/trading/trade_approval.py

- **[P2] `bot_instance.py`에서 미사용**: `TradeApprovalManager`가 트레이딩 루프에 미통합. CLAUDE.md에서는 핵심 설계로 명시.
- **[P3] 요청 저장소 메모리 기반**: `_requests` dict가 재시작 시 소실.
- **[P3] 타임아웃 처리 미구현**: `approval_timeout` 설정은 있지만 실제 타임아웃 체크 로직 없음.

## src/ai/gemini.py

- **[P2] `_build_market_prompt`와 `_build_market_prompt_with_reason` 완전 중복**: 78~138줄 vs 246~306줄. `formatted_data` 구성 동일. 공통 메서드 추출 권장. ✅ 해결
- **[P3] `get_signal`/`get_signal_sync` 코드 중복**: 비동기/동기 버전이 거의 동일.
- **[P3] 심볼 하드코딩**: 90줄 `"symbol": "BTCUSDT"`. 멀티심볼 지원 시 문제.

## src/ai/enhanced_gemini.py

- **[P3] temperature 불일치**: 부모 `GeminiSignalGenerator` 기본값 0.3 vs `EnhancedGemini` 기본값 0.1. 의도적인지 확인 필요.

## src/ai/ensemble.py

- **[P2] `bot_instance.py`에서 미사용**: 앙상블이 트레이딩 루프에 통합 안 됨. rule_based만 사용 중.
- **[P3] Gemini 신뢰도 하드코딩**: 248줄 `confidence=0.8`. 실제 응답 품질과 무관.
- **[P3] `assert` 사용**: 237, 257, 272줄. 프로덕션에서 무시될 수 있음.

## src/ai/rule_based.py

- **[P2] LONG 조건 비직관적**: `RSI < oversold AND price > MA7` — 과매도 + 가격>MA7은 다이버전스. 일반 RSI 전략과 다름. 의도적이라면 주석 필요.
- **[P3] 기본값 혼동**: 자체 기본값 45/55 vs `BotConfig` 기본값 35/65. 실제로는 BotConfig 값 주입되지만 혼란 소지.

## src/ai/scoring.py

- **[P3] MACD 데이터 미계산**: `_score_macd` 존재하지만 `analyze_market()`이 MACD 미반환. 항상 스킵됨.
- **[P3] Volume 점수 방향성 없음**: 거래량 증가를 항상 양수 처리. 하락 추세에서 거래량 증가는 하락 확인이지만 LONG 보강으로 작용.

## src/analytics/trade_analyzer.py

- **[P2] `get_pattern_insights`와 `get_worst_patterns` 코드 중복**: 649~725줄 vs 727~800줄. RSI/시간대 분석 구조 동일, 필터만 다름. 공통 메서드 추출 가능. ✅ 해결
- **[P3] DB 함수 존재 전제**: `get_trading_summary` 등 PostgreSQL 함수가 미리 존재해야 함. 마이그레이션 의존성.

## src/analytics/memory_context.py

- **[P3] `_build_timing_insights`에서 `min_sample_size=3` 하드코딩**: 370~371줄. 다른 메서드는 30 사용. 일관성 부족.
- **[P3] best/worst 임계값 매직 넘버 분산**: RSI 70%/40%, 시간대 75%/35%. 상수로 정의 권장.

## src/analytics/signal_tracker.py

- **[P2] `bot_instance.py`에서 미사용**: 신호 추적이 트레이딩 루프에 미통합. 신호 생성되지만 기록 안 됨.
- **[P3] 인메모리 크기 제한 없음**: `_in_memory_signals` dict가 무한 증가 가능. 주기적 cleanup 로직 부재.

---

## src/exchange/binance.py

- **[P1] `get_all_positions`에서 에러 시 빈 리스트 반환**: 425줄. 네트워크 에러와 "포지션 없음" 구분 불가. 포지션이 있는데 조회 실패하면 봇이 중복 진입 가능. ✅ 해결
- **[P1] `get_all_positions`에 `@async_retry` 미적용**: 374줄. 다른 핵심 메서드에는 적용되어 있으나 이 메서드는 누락. ✅ 해결
- **[P1] `close_position` 내부에서 이중 retry**: 435줄. 메서드 자체에 `@async_retry` + 내부 `create_market_order`에도 `@async_retry`. 최대 9회 시도로 지연 체결 시 이중 청산 가능. ✅ 해결
- **[P2] `get_ticker_24h`에 `@async_retry` 미적용**: 167줄. ✅ 해결
- **[P2] `get_market_sentiment`에서 순차 API 호출**: 547~549줄. 3개 API 순차 호출. `asyncio.gather` 사용 시 3배 성능 개선 가능. ✅ 해결
- **[P2] `get_funding_rate`/`get_long_short_ratio`/`get_open_interest` 에러 시 기본값 반환**: 487, 518, 536줄. 에러와 실제 기본값 구분 불가. ✅ 해결
- **[P2] PnL 계산 로직 분산 (3번째 구현)**: 399~406줄. executor, bot_instance에 이어 세 번째 PnL 계산. 레버리지 반영 방식 불일치. ✅ 해결
- **[P3] `get_account_balance`에서 USDT 미발견 시 불완전한 반환**: 592줄. `unrealized_pnl` 필드 누락.
- **[P3] 타입 힌트 `Dict` 대신 소문자 `dict` 사용 가능**: 5줄. Python 3.10+ 환경.
- **[P3] `get_klines`의 `limit=24` 기본값**: 117줄. 5분봉 기준 2시간 전제가 다른 타임프레임에서 의미 달라짐.
- **[P3] "USDT" 등 문자열 리터럴 상수 미정의**: 576줄.

## src/storage/trade_history.py

- **[P1] `cleanup_old_trades`에서 OPEN 거래 삭제 가능**: 366~368줄. `WHERE exit_time < $1` 조건에 `AND status = 'CLOSED'` 누락. exit_time이 설정된 OPEN 거래가 있다면 삭제됨. ✅ 해결
- **[P2] `_get_statistics_all`과 `_get_statistics_with_bot_id` 완전 중복**: 217~321줄. WHERE 조건 하나만 다름. 통합 가능. ✅ 해결
- **[P2] `datetime.now()` timezone-naive 사용**: 204, 364줄. DB의 `NOW()` (UTC)와 시간대 불일치 가능. ✅ 해결
- **[P2] `add_entry`에서 bot_id 유무에 따른 쿼리 분기 중복**: 93~107줄.
- **[P3] `get_recent_trades`도 bot_id 분기 중복**: 161~183줄.
- **[P3] 커넥션 풀 `max_size=10` 하드코딩**: 29줄.

## src/storage/redis_state.py

- **[P1] `_deserialize_state`에서 접두사 길이 하드코딩**: 499줄. `__list__`(8글자)와 `__dict__`(8글자) 모두 `value[8:]`로 파싱. `__list_`가 되면 파싱 오류. 접두사 문자열 변수화 권장. ✅ 해결
- **[P2] `is_connected`가 실제 연결 상태 미반영**: 70줄. `_client is not None`만 확인. Redis 연결 끊어져도 True. ✅ 해결
- **[P2] 직렬화에서 nested dict/list 내부 타입 보존 안 됨**: 471줄. `json.dumps`로 내부 datetime 등이 str로 변환되어 복구 불가. ✅ 해결
- **[P2] `save_bot_state`에서 `hset` 두 번 호출**: 154, 157줄. mapping과 last_updated가 원자적이지 않음. ✅ 해결
- **[P3] `DummyRedisStateManager`가 `RedisStateManager`를 상속하지 않음**: 507줄. 인터페이스 준수가 암묵적.
- **[P3] `clear_running_bots`에서 등록 봇과의 정합성 미확인**: 440줄.

## src/storage/audit_log.py

- **[P2] `get_recent_logs`가 항상 인메모리에서만 조회**: 352줄. DB에 저장되어도 조회는 인메모리만. 재시작 후 이전 로그 조회 불가. ✅ 해결
- **[P2] `_save_to_db`에서 `import json` 함수 내부 임포트**: 126줄. 비관례적. ✅ 해결
- **[P2] 인메모리 로그 트리밍이 비효율적**: 108줄. 리스트 슬라이싱 대신 `collections.deque(maxlen=N)` 권장. ✅ 해결
- **[P3] `get_logs_by_date_range`에서 timezone 비교 문제**: 388줄. `log.timestamp`(UTC)과 파라미터(timezone 미지정) 비교 시 오류 가능.
- **[P3] `get_stats`가 동기 메서드**: 397줄. 다른 메서드는 async인데 이것만 sync.

## src/api/main.py

- **[P3] 에러 응답 구조 불일치**: 75~109줄. ValueError와 일반 Exception 응답 형식 다름. ✅ 해결

## src/api/dependencies.py

- **[P3] API 키 검증 실패 로깅 없음**: 147~198줄. 보안 감사 추적 불가. ✅ 해결

## src/api/middleware/rate_limit.py

- **[P1] X-Forwarded-For 스푸핑으로 Rate Limit 우회 가능**: 143~173줄. 리버스 프록시 없이 직접 접근 시 헤더 조작으로 우회. ✅ 해결
- **[P2] cleanup TOCTOU**: 248줄. 체크-삭제 사이 레이스 가능. ✅ 해결

## src/api/routes/analytics.py

- **[P2] bot_id 미검증**: 121줄. 임의 bot_id 전달 가능. ✅ 해결

## src/api/routes/bots.py

- **[P2] 에러 핸들링이 문자열 매칭에 의존**: 167줄. `"not found" in error_msg.lower()` — 언어 변경 시 깨짐. ✅ 해결

## src/api/routes/dashboard.py

- **[P1] WebSocket 인증 없음**: 275줄. REST 엔드포인트는 `verify_api_key` 적용, WebSocket은 미적용. 인증 없이 실시간 봇 데이터 접근 가능. ✅ 해결

## src/api/routes/n8n.py

- **[P1] 시그널 주입 미구현**: 41~60줄. 로깅만 하고 실제 BotInstance에 시그널 전달 안 됨. 엔드포인트가 존재하지만 기능 미동작. ✅ 해결

## src/api/routes/health.py

- **[P3] API 버전 하드코딩**: 17줄. `API_VERSION = "1.0.0"`.

## src/api/schemas/bot.py

- **[P3] datetime 필드에 timezone 미강제**: datetime 필드에 UTC 명시 없음.

## src/api/services/bot_service.py

- **[P2] 봇 심볼 변경 방지 없음**: 145~209줄. 실행 중 심볼 변경 가능. 잘못된 심볼로 거래 위험. ✅ 해결

## src/api/services/n8n_callback.py

- **[P2] 콜백 비활성화와 네트워크 실패 구분 불가**: 78~80줄. 둘 다 `False` 반환. ✅ 해결

## src/discord_bot/bot.py

- **[P1] 전체 1824줄이 데드 코드**: client.py + commands/ + embeds.py + views.py로 리팩토링 완료 후 원본 미삭제. 두 구현 공존으로 혼란 유발. 즉시 삭제 필요. ✅ 해결

## src/discord_bot/client.py

- **[P1] `bot_name` 파라미터 검증 없음 (경로 조작)**: 445줄. 사용자 입력이 URL 경로에 직접 삽입. `../../admin` 등 경로 조작 가능. ✅ 해결
- **[P2] API 에러 처리 너무 일반적**: 164줄. 4xx/5xx 구분 없이 일반 Exception. ✅ 해결

## src/discord_bot/commands/multibot.py

- **[P1] `bot_name` 입력 검증 없음**: 52줄. Discord 사용자 입력이 API URL에 직접 삽입. ✅ 해결

## src/discord_bot/views.py

- **[P1] `original_user_id` 미사용 (권한 우회)**: 50줄. 매개변수로 받지만 실제 권한 체크에서 현재 interaction.user 사용. User A가 시작한 확인 버튼을 User B가 눌러도 User B 권한으로 실행. ✅ 해결
- **[P2] API 호출 Rate Limiting 없음**: 여러 뷰에서 빠른 버튼 클릭으로 REST API 과부하 가능. ✅ 해결

## src/discord_bot/embeds.py

- **[P2] TP/SL 퍼센트 하드코딩**: 129, 134줄. `"+0.4%"` / `"-0.4%"` — 실제 설정과 무관한 고정값. ✅ 해결
- **[P2] trade history null 처리 불완전**: 248줄. `trade["exit_price"]` 대신 `trade.get("exit_price")` 필요. ✅ 해결
- **[P3] 에러 메시지 ephemeral 불일치**: 일부 에러만 `ephemeral=True`.

## src/discord_bot/constants.py

- **[P3] 매직 넘버 설명 부족**: DASHBOARD_VIEW=180 (왜 3분인지 설명 없음).

## src/utils/circuit_breaker.py

- **[P1] 전역 레지스트리 `_circuit_breakers`가 모듈 레벨 dict**: 324줄. 테스트 간 격리 문제 + 설정 덮어쓰기 불가. ✅ 해결
- **[P1] `config.exceptions` 타입 힌트가 `tuple`**: 49줄. `tuple[type[Exception], ...]`로 제한 필요. ✅ 해결
- **[P2] `reset()`이 lock 없이 상태 변경**: 298~305줄. 테스트용이지만 프로덕션 호출 시 레이스 가능. ✅ 해결
- **[P2] 데코레이터 팩토리에서 config 불변**: 386줄. 같은 이름으로 두 번째 호출 시 첫 번째 config 유지. ✅ 해결
- **[P2] HALF_OPEN 호출 카운트 관리**: 192줄. lock 안에서만 수정되지만 가독성 개선 필요. ✅ 해결

## src/utils/retry.py

- **[P1] `sync_retry`에서 `time.sleep` 사용**: 113줄. 이벤트 루프 내에서 호출되면 전체 루프 블로킹. ✅ 해결
- **[P2] 타입 힌트 미완성**: 30줄. `func`에 타입 힌트 없음. ✅ 해결
- **[P2] jitter 미지원**: 동시 다수 요청 시 "thundering herd" 문제. ✅ 해결

## src/utils/logging.py

- **[P1] 64자 영숫자 패턴이 너무 광범위**: 23줄. `[A-Za-z0-9]{64}` — UUID, 해시 등 정상 데이터도 마스킹. 로그 디버깅 시 필요 정보 손실. ✅ 해결
- **[P2] `mask_dict_sensitive_data`에서 리스트 값 미처리**: 60~70줄. dict 내 list의 민감정보 마스킹 안 됨. ✅ 해결
- **[P2] `setup_json_logging`이 기존 핸들러 전체 제거**: 151줄. `logger.remove()`로 다른 모듈 핸들러도 삭제. ✅ 해결
- **[P2] feature flag `_json_logging_enabled`가 실제 설정과 연동 안 됨**: 219줄. ✅ 해결

## src/backtest/engine.py

- **[P1] PnL 계산에 레버리지 미반영**: 81~83줄. `Trade.calculate_pnl()`이 순수 가격차 × 수량. 실제 PnL과 불일치. ✅ 해결
- **[P1] TP/SL 동시 충족 시 항상 TP 우선**: 537~556줄. 실제로는 SL이 먼저 도달할 수 있음. 과대 성과 추정. ✅ 해결
- **[P1] `_prepare_market_data`에서 미사용 변수**: 279~280줄. `highs`, `lows` 계산 후 `_ =`에 할당. 불필요한 연산. ✅ 해결
- **[P2] RSI 계산이 indicators.py와 다른 구현**: 318줄. SMA 기반 vs pandas 기반. 결과 불일치 가능. ✅ 해결
- **[P2] Sharpe ratio 미구현**: 117줄. 필드만 있고 계산 없음. ✅ 해결
- **[P2] 수수료 계산 정확성**: 466줄. 레버리지 포함 포지션 가치 기반인지 확인 필요.

## src/backtest/slippage.py

- **[P1] `MarketImpactModel`이 완전 미사용**: 104줄. 정의만 있고 engine.py에서 미사용. ✅ 해결
- **[P2] 슬리피지 계산에 랜덤성 없음**: 38줄. 같은 입력이면 항상 같은 슬리피지.
- **[P2] SHORT 진입 시 유리한 가격**: 173줄. 종가보다 낮은 가격으로 진입 — SHORT에 유리.
- **[P3] 슬리피지 단위 혼동**: `base_slippage_pct`(0.01%)가 내부에서 `/100` 처리. 반환값은 비율. 혼동 소지.

## src/metrics/prometheus.py

- **[P2] 프로퍼티에서 `assert` 사용**: 133, 139, 145, 151, 157줄. `python -O`에서 무시됨. ✅ 해결
- **[P2] `_metrics_instance`와 `_initialized` 이중 플래그**: 13~14줄. 통합 가능.
- **[P2] `bot_instance.py`에서 메트릭 기록 미호출**: 메트릭 모듈 존재하지만 트레이딩 루프에서 미사용.
- **[P2] 핵심 리스크 메트릭(balance, drawdown) 부재**: 거래 수/PnL만 추적.
- **[P3] `get_metrics_registry`가 항상 기본 REGISTRY 반환**: 250줄. 커스텀 레지스트리 무시.
- **[P3] Histogram 버킷 하드코딩**: 86, 103줄.
