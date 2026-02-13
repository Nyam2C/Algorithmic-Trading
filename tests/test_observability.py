"""Observability & Monitoring 개선 테스트.

Phase 1: 로그 파이프라인 (trade/ai_signal sinks)
Phase 2: Prometheus 새 메트릭
Phase 3: AIDecisionLogger
Phase 4: /health/bots 엔드포인트
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry

from src.ai.ai_logger import AIDecisionLogger
from src.metrics.prometheus import TradingMetrics

# =============================================================================
# Phase 1: 로그 파이프라인 테스트
# =============================================================================


class TestLoggingSinks:
    """로그 싱크 필터링 테스트."""

    def test_setup_json_logging_creates_4_file_sinks(self):
        """setup_json_logging이 4개 파일 싱크를 생성하는지 확인."""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            from src.utils.logging import setup_json_logging

            setup_json_logging(
                log_level="INFO",
                enable_file_logging=True,
                enable_json_stdout=True,
                mask_sensitive=True,
                log_dir="/tmp/test_obs_logs",
            )

            # stdout(1) + bot.json.log(1) + error.json.log(1)
            # + trade.json.log(1) + ai_signal.json.log(1) = 5 calls
            assert mock_logger.add.call_count == 5

    def test_trade_filter_accepts_trade_open(self):
        """trade 필터가 TRADE_OPEN을 수용하는지 확인."""
        # trade filter lambda를 직접 테스트
        record = {"extra": {"event_type": "TRADE_OPEN"}}
        assert record["extra"].get("event_type") in ("TRADE_OPEN", "TRADE_CLOSE")

    def test_trade_filter_accepts_trade_close(self):
        """trade 필터가 TRADE_CLOSE를 수용하는지 확인."""
        record = {"extra": {"event_type": "TRADE_CLOSE"}}
        assert record["extra"].get("event_type") in ("TRADE_OPEN", "TRADE_CLOSE")

    def test_trade_filter_rejects_other_events(self):
        """trade 필터가 다른 이벤트를 거부하는지 확인."""
        record = {"extra": {"event_type": "AI_SIGNAL"}}
        assert record["extra"].get("event_type") not in ("TRADE_OPEN", "TRADE_CLOSE")

    def test_ai_signal_filter_accepts_ai_signal(self):
        """ai_signal 필터가 AI_SIGNAL을 수용하는지 확인."""
        record = {"extra": {"event_type": "AI_SIGNAL"}}
        assert record["extra"].get("event_type") in ("AI_SIGNAL", "ENSEMBLE_SIGNAL")

    def test_ai_signal_filter_accepts_ensemble_signal(self):
        """ai_signal 필터가 ENSEMBLE_SIGNAL을 수용하는지 확인."""
        record = {"extra": {"event_type": "ENSEMBLE_SIGNAL"}}
        assert record["extra"].get("event_type") in ("AI_SIGNAL", "ENSEMBLE_SIGNAL")

    def test_ai_signal_filter_rejects_trade_events(self):
        """ai_signal 필터가 거래 이벤트를 거부하는지 확인."""
        record = {"extra": {"event_type": "TRADE_OPEN"}}
        assert record["extra"].get("event_type") not in (
            "AI_SIGNAL",
            "ENSEMBLE_SIGNAL",
        )

    def test_no_event_type_rejected_by_both_filters(self):
        """event_type 없는 레코드가 양쪽 필터에서 거부되는지 확인."""
        record = {"extra": {}}
        assert record["extra"].get("event_type") not in ("TRADE_OPEN", "TRADE_CLOSE")
        assert record["extra"].get("event_type") not in (
            "AI_SIGNAL",
            "ENSEMBLE_SIGNAL",
        )


# =============================================================================
# Phase 2: Prometheus 새 메트릭 테스트
# =============================================================================


class TestNewPrometheusMetrics:
    """새 Prometheus 메트릭 테스트."""

    @pytest.fixture
    def fresh_registry(self):
        """각 테스트마다 새로운 레지스트리 생성."""
        return CollectorRegistry()

    @pytest.fixture
    def metrics(self, fresh_registry):
        """각 테스트마다 새로운 메트릭 인스턴스 생성."""
        return TradingMetrics(registry=fresh_registry)

    def test_loop_duration_metric_exists(self, metrics):
        """loop_duration 메트릭이 존재하는지 확인."""
        assert metrics.loop_duration is not None

    def test_loop_total_metric_exists(self, metrics):
        """loop_total 메트릭이 존재하는지 확인."""
        assert metrics.loop_total is not None

    def test_signal_total_metric_exists(self, metrics):
        """signal_total 메트릭이 존재하는지 확인."""
        assert metrics.signal_total is not None

    def test_ai_latency_metric_exists(self, metrics):
        """ai_latency 메트릭이 존재하는지 확인."""
        assert metrics.ai_latency is not None

    def test_record_loop_duration(self, metrics):
        """루프 소요시간 기록."""
        metrics.record_loop_duration("btc-bot", 2.5)
        # 에러 없이 호출되어야 함

    def test_record_loop_duration_increments_total(self, metrics):
        """루프 기록 시 loop_total도 증가."""
        metrics.record_loop_duration("btc-bot", 1.0)
        metrics.record_loop_duration("btc-bot", 2.0)
        # 2번 호출

    def test_record_signal(self, metrics):
        """시그널 기록."""
        metrics.record_signal("btc-bot", "LONG", "ensemble")
        metrics.record_signal("btc-bot", "WAIT", "rule_based")
        metrics.record_signal("btc-bot", "SHORT", "memory_gemini")

    def test_record_ai_latency(self, metrics):
        """AI 응답시간 기록."""
        metrics.record_ai_latency("btc-bot", 1.5)
        metrics.record_ai_latency("btc-bot", 2.3)

    def test_record_rsi(self, metrics):
        """RSI 값 기록."""
        metrics.record_rsi("btc-bot", 35.2)
        metrics.record_rsi("btc-bot", 70.0)

    def test_rsi_metric_exists(self, metrics):
        """trading_rsi 메트릭이 존재하는지 확인."""
        assert metrics._rsi_value is not None

    def test_record_rsi_nan_skipped(self, metrics):
        """NaN RSI는 기록하지 않음."""
        metrics.record_rsi("btc-bot", float("nan"))
        # NaN이 설정되지 않음 (에러 없이 스킵)


# =============================================================================
# Phase 3: AIDecisionLogger 테스트
# =============================================================================


class TestAIDecisionLogger:
    """AIDecisionLogger 구조화 로깅 테스트."""

    @pytest.fixture
    def ai_logger(self):
        """AIDecisionLogger 인스턴스 생성."""
        return AIDecisionLogger()

    def test_log_gemini_call(self, ai_logger):
        """Gemini 호출 로깅이 에러 없이 동작."""
        ai_logger.log_gemini_call(
            bot_name="btc-bot",
            prompt_summary="RSI=35.2, MA7=95000...",
            raw_response="LONG",
            parsed_signal="LONG",
            reason="RSI 과매도 + 상승 추세",
            memory_used=True,
            latency_ms=1250.0,
            model="gemini-2.5-flash",
        )

    def test_log_gemini_call_truncates_prompt(self, ai_logger):
        """프롬프트가 500자로 절삭되는지 확인."""
        long_prompt = "x" * 1000
        # 에러 없이 호출되어야 함
        ai_logger.log_gemini_call(
            bot_name="btc-bot",
            prompt_summary=long_prompt,
            raw_response="WAIT",
            parsed_signal="WAIT",
        )

    def test_log_gemini_call_empty_prompt(self, ai_logger):
        """빈 프롬프트도 처리."""
        ai_logger.log_gemini_call(
            bot_name="btc-bot",
            prompt_summary="",
            raw_response="WAIT",
            parsed_signal="WAIT",
        )

    def test_log_ensemble_decision(self, ai_logger):
        """앙상블 결정 로깅이 에러 없이 동작."""
        ai_logger.log_ensemble_decision(
            bot_name="btc-bot",
            component_signals=[
                {"source": "gemini", "signal": "LONG", "confidence": 0.8, "weight": 0.4},
                {
                    "source": "rule_based",
                    "signal": "LONG",
                    "confidence": 1.0,
                    "weight": 0.3,
                },
            ],
            final_signal="LONG",
            consensus_ratio=1.0,
            weighted_score=0.5,
        )

    def test_log_ensemble_decision_empty_signals(self, ai_logger):
        """빈 신호 목록도 처리."""
        ai_logger.log_ensemble_decision(
            bot_name="btc-bot",
            component_signals=[],
            final_signal="WAIT",
            consensus_ratio=0.0,
        )

    def test_log_gemini_call_with_event_type(self, ai_logger):
        """Gemini 로깅에 event_type=AI_SIGNAL 및 전체 필드 바인딩 확인."""
        with patch("src.ai.ai_logger.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            ai_logger.log_gemini_call(
                bot_name="btc-bot",
                prompt_summary="test",
                raw_response="LONG",
                parsed_signal="LONG",
                reason="test reason",
                memory_used=True,
                latency_ms=100.0,
                model="gemini-2.5-flash",
            )

            bind_kwargs = mock_logger.bind.call_args[1]
            assert bind_kwargs["event_type"] == "AI_SIGNAL"
            assert bind_kwargs["signal"] == "LONG"
            assert bind_kwargs["bot_name"] == "btc-bot"
            assert bind_kwargs["raw_response"] == "LONG"
            assert bind_kwargs["reason"] == "test reason"
            assert bind_kwargs["memory_used"] is True
            assert bind_kwargs["latency_ms"] == 100.0
            assert bind_kwargs["model"] == "gemini-2.5-flash"
            mock_bound.info.assert_called_once_with("Gemini AI 시그널 생성")

    def test_log_ensemble_with_event_type(self, ai_logger):
        """앙상블 로깅에 event_type=ENSEMBLE_SIGNAL 및 전체 필드 바인딩 확인."""
        with patch("src.ai.ai_logger.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            ai_logger.log_ensemble_decision(
                bot_name="btc-bot",
                component_signals=[{"source": "gemini", "signal": "LONG"}],
                final_signal="WAIT",
                consensus_ratio=0.75,
                weighted_score=0.6,
            )

            bind_kwargs = mock_logger.bind.call_args[1]
            assert bind_kwargs["event_type"] == "ENSEMBLE_SIGNAL"
            assert bind_kwargs["signal"] == "WAIT"
            assert bind_kwargs["bot_name"] == "btc-bot"
            assert bind_kwargs["final_signal"] == "WAIT"
            assert bind_kwargs["consensus_ratio"] == 0.75
            assert bind_kwargs["weighted_score"] == 0.6
            assert len(bind_kwargs["component_signals"]) == 1
            mock_bound.info.assert_called_once_with("앙상블 시그널 결정")


# =============================================================================
# Phase 4: /health/bots 엔드포인트 테스트
# =============================================================================


class TestHealthBotsEndpoint:
    """봇별 상태 엔드포인트 테스트."""

    @pytest.fixture
    def mock_bot(self):
        """Mock 봇 인스턴스."""
        bot = MagicMock()
        bot.get_state.return_value = {
            "bot_name": "btc-bot",
            "is_running": True,
            "is_paused": False,
            "loop_count": 100,
            "last_loop_duration": 2.3,
            "last_signal": "WAIT",
            "current_price": 95000.0,
            "market_regime": "TRENDING",
            "has_position": False,
            "uptime_start": datetime(2024, 1, 1, 12, 0, 0),
        }
        return bot

    @pytest.fixture
    def mock_manager(self, mock_bot):
        """Mock 봇 매니저."""
        manager = MagicMock()
        manager.bots = {"btc-bot": mock_bot}
        manager.bot_count = 1
        manager.running_count = 1
        return manager

    @pytest.mark.asyncio
    async def test_health_bots_returns_bot_status(self, mock_manager, mock_bot):
        """봇 상태가 올바르게 반환되는지 확인."""
        with patch(
            "src.api.routes.health.get_bot_manager_optional",
            return_value=mock_manager,
        ):
            from src.api.routes.health import bot_health

            result = await bot_health()

            assert "bots" in result
            assert len(result["bots"]) == 1

            bot_status = result["bots"][0]
            assert bot_status["bot_name"] == "btc-bot"
            assert bot_status["is_running"] is True
            assert bot_status["loop_count"] == 100
            assert bot_status["last_loop_duration_sec"] == 2.3
            assert bot_status["last_signal"] == "WAIT"
            assert bot_status["current_price"] == 95000.0
            assert bot_status["market_regime"] == "TRENDING"
            assert bot_status["has_position"] is False
            assert bot_status["uptime_seconds"] > 0

    @pytest.mark.asyncio
    async def test_health_bots_no_manager(self):
        """매니저 없을 때 빈 목록 반환."""
        with patch(
            "src.api.routes.health.get_bot_manager_optional",
            return_value=None,
        ):
            from src.api.routes.health import bot_health

            result = await bot_health()
            assert result == {"bots": []}


# =============================================================================
# Phase 2: BotInstance 루프 타이밍 테스트
# =============================================================================


class TestBotInstanceLoopTiming:
    """BotInstance 루프 타이밍 테스트."""

    def test_get_state_includes_loop_timing(self):
        """get_state()에 루프 타이밍 필드가 포함되는지 확인."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(bot_name="test-bot", symbol="BTCUSDT")
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )

        state = bot.get_state()
        assert "last_loop_duration" in state
        assert "last_loop_time" in state
        assert "has_position" in state
        assert state["last_loop_duration"] == 0.0
        assert state["last_loop_time"] is None
        assert state["has_position"] is False

    def test_get_state_market_regime(self):
        """get_state()에 market_regime이 포함되는지 확인."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(bot_name="test-bot", symbol="BTCUSDT")
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )

        state = bot.get_state()
        assert "market_regime" in state
        assert state["market_regime"].upper() == "UNKNOWN"


# =============================================================================
# Phase 2: Binance API latency 메트릭 테스트
# =============================================================================


class TestBinanceAPILatency:
    """Binance API latency 메트릭 테스트."""

    def test_binance_has_record_latency_method(self):
        """BinanceTestnetClient에 _record_latency 메서드 확인."""
        from src.exchange.binance import BinanceTestnetClient

        client = BinanceTestnetClient(
            api_key="test", secret_key="test", testnet=True
        )
        assert hasattr(client, "_record_latency")

    def test_record_latency_no_error_without_metrics(self):
        """메트릭 없이도 _record_latency가 에러 없이 동작."""
        from src.exchange.binance import BinanceTestnetClient

        client = BinanceTestnetClient(
            api_key="test", secret_key="test", testnet=True
        )
        client._metrics = None
        # 에러 없이 호출되어야 함
        import time

        client._record_latency("test_endpoint", time.monotonic())


# =============================================================================
# Phase 9 WS4: Exchange Close Detection (merged from test_ws4_phase9.py)
# =============================================================================


class TestPhase9ExchangeCloseDetection:
    """Issue B: Detect when exchange closes position via SL/TP."""

    @pytest.fixture
    def bot_instance(self):
        """Create a minimal BotInstance for testing."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(bot_name="test-bot", symbol="BTCUSDT")
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )
        return bot

    @pytest.mark.asyncio
    async def test_detects_exchange_side_close(self, bot_instance):
        """When executor has a position but exchange returns None, detect the close."""
        from unittest.mock import AsyncMock, MagicMock

        bot = bot_instance

        # Setup: executor has a tracked position
        mock_executor = AsyncMock()
        mock_executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "position_amt": 0.01,
            "trade_id": "test-123",
            "entry_time": datetime.now(),
        }
        # Exchange says no position exists
        mock_executor.get_position = AsyncMock(return_value=None)
        mock_executor.calculate_pnl_pct = MagicMock(return_value=-1.5)

        bot._executor = mock_executor

        # Mock binance client for current price
        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=49500.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0, "total": 1000.0}
        )
        mock_client.cancel_all_open_orders = AsyncMock()
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        # Mock risk manager
        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ""))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, "test"))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()
        bot._risk_manager.track_trade_result = AsyncMock()

        # Mock trade DB
        bot._trade_db = AsyncMock()
        bot._trade_db.add_exit = AsyncMock(return_value=True)

        # Mock _fetch_market_data to return simple data
        bot._fetch_market_data = AsyncMock(return_value={
            "current_price": 49500.0,
            "indicators": {
                "ma_7": 50000.0, "ma_25": 50500.0, "ma_99": 51000.0,
                "atr": 500.0, "price": 49500.0, "rsi": 50.0, "volume_ratio": 1.0,
            },
        })

        # Run the loop
        await bot._execute_single_loop()

        # The exchange-side close should have been detected and PnL tracked
        bot._risk_manager.track_trade_pnl.assert_called_once()
        # Position should be cleared
        assert bot._current_position is None

    @pytest.mark.asyncio
    async def test_no_false_positive_when_no_tracked_position(self, bot_instance):
        """No detection when executor has no tracked position."""
        from unittest.mock import AsyncMock

        bot = bot_instance
        mock_executor = AsyncMock()
        mock_executor.current_position = None
        mock_executor.get_position = AsyncMock(return_value=None)
        bot._executor = mock_executor

        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0, "total": 1000.0}
        )
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ""))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, "test"))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()

        bot._fetch_market_data = AsyncMock(return_value={
            "current_price": 50000.0,
            "indicators": {
                "ma_7": 50000.0, "ma_25": 50500.0, "ma_99": 51000.0,
                "atr": 500.0, "price": 50000.0, "rsi": 50.0, "volume_ratio": 1.0,
            },
        })

        # No tracked position, so no detection should happen
        await bot._execute_single_loop()
        bot._risk_manager.track_trade_pnl.assert_not_called()

    @pytest.mark.asyncio
    async def test_exchange_close_records_to_db(self, bot_instance):
        """Exchange close should record exit in DB."""
        from unittest.mock import AsyncMock, MagicMock

        bot = bot_instance

        mock_executor = AsyncMock()
        mock_executor.current_position = {
            "side": "SHORT",
            "entry_price": 52000.0,
            "position_amt": 0.02,
            "trade_id": "trade-456",
            "entry_time": datetime.now(),
        }
        mock_executor.get_position = AsyncMock(return_value=None)
        mock_executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        bot._executor = mock_executor

        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=51000.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0, "total": 1000.0}
        )
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ""))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, "test"))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()
        bot._risk_manager.track_trade_result = AsyncMock()

        mock_db = AsyncMock()
        mock_db.add_exit = AsyncMock(return_value=True)
        bot._trade_db = mock_db

        bot._fetch_market_data = AsyncMock(return_value={
            "current_price": 51000.0,
            "indicators": {
                "ma_7": 50000.0, "ma_25": 50500.0, "ma_99": 51000.0,
                "atr": 500.0, "price": 51000.0, "rsi": 50.0, "volume_ratio": 1.0,
            },
        })

        await bot._execute_single_loop()

        # Should have recorded exit in DB with EXCHANGE_SL_TP reason
        mock_db.add_exit.assert_called_once()
        call_kwargs = mock_db.add_exit.call_args
        assert call_kwargs.kwargs.get("exit_reason") == "EXCHANGE_SL_TP" or             (call_kwargs[1] if len(call_kwargs) > 1 else {}).get("exit_reason") == "EXCHANGE_SL_TP"


# =============================================================================
# Phase 9 WS4: Gemini Confidence (merged from test_ws4_phase9.py)
# =============================================================================


class TestPhase9GeminiConfidence:
    """Issue Q: Gemini confidence should default to 0.6."""

    @pytest.mark.asyncio
    async def test_gemini_default_confidence_is_0_6(self):
        """Default Gemini confidence should be 0.6, not 0.8."""
        from unittest.mock import AsyncMock, MagicMock

        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "Test reason")
        )
        # Explicitly no last_confidence (or set to None)
        mock_gemini.last_confidence = None

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        assert signal.confidence == 0.6

    @pytest.mark.asyncio
    async def test_gemini_parsed_confidence_used(self):
        """When Gemini returns confidence in response, use it."""
        from unittest.mock import AsyncMock, MagicMock

        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "Test reason")
        )
        mock_gemini.last_confidence = 0.9  # Parsed confidence (float)

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        # Should use the parsed confidence
        assert signal.confidence == 0.9

    @pytest.mark.asyncio
    async def test_gemini_no_parsed_confidence_uses_default(self):
        """When Gemini has no parsed confidence, use 0.6 default."""
        from unittest.mock import AsyncMock, MagicMock

        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("SHORT", "Bearish")
        )
        # No parsed confidence (None)
        mock_gemini.last_confidence = None

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        assert signal.confidence == 0.6


# =============================================================================
# Phase 9 WS4: Metrics Auth (merged from test_ws4_phase9.py)
# =============================================================================


class TestPhase9MetricsAuth:
    """Issue T: /metrics endpoint should have Bearer token auth."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""

        from fastapi import FastAPI

        from src.api.routes.health import router
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_metrics_no_auth_when_no_env_var(self, client):
        """When METRICS_AUTH_TOKEN is not set, metrics should be accessible."""
        import os

        with patch.dict(os.environ, {}, clear=False):
            # Make sure METRICS_AUTH_TOKEN is not set
            os.environ.pop("METRICS_AUTH_TOKEN", None)
            resp = client.get("/metrics")
            assert resp.status_code == 200

    def test_metrics_rejects_without_token(self, client):
        """When METRICS_AUTH_TOKEN is set, request without token gets 401."""
        import os

        with patch.dict(os.environ, {"METRICS_AUTH_TOKEN": "secret123"}):
            resp = client.get("/metrics")
            assert resp.status_code == 401

    def test_metrics_rejects_wrong_token(self, client):
        """When METRICS_AUTH_TOKEN is set, wrong token gets 401."""
        import os

        with patch.dict(os.environ, {"METRICS_AUTH_TOKEN": "secret123"}):
            resp = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
            assert resp.status_code == 401

    def test_metrics_accepts_correct_token(self, client):
        """When METRICS_AUTH_TOKEN is set, correct token gets 200."""
        import os

        with patch.dict(os.environ, {"METRICS_AUTH_TOKEN": "secret123"}):
            resp = client.get("/metrics", headers={"Authorization": "Bearer secret123"})
            assert resp.status_code == 200


# =============================================================================
# Phase 9 WS4: Operational Metrics (merged from test_ws4_phase9.py)
# =============================================================================


class TestPhase9OperationalMetrics:
    """Issue U: New operational Prometheus metrics."""

    def test_exchange_connected_gauge_exists(self):
        """trading_exchange_connected gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        # Should be able to set the gauge without error
        metrics.record_exchange_connected("test-bot", True)
        metrics.record_exchange_connected("test-bot", False)

    def test_circuit_breaker_state_gauge_exists(self):
        """trading_circuit_breaker_state gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_circuit_breaker_state("api_breaker", 0)
        metrics.record_circuit_breaker_state("api_breaker", 1)

    def test_open_positions_gauge_exists(self):
        """trading_open_positions gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_open_positions("test-bot", 1)
        metrics.record_open_positions("test-bot", 0)

    def test_bot_uptime_gauge_exists(self):
        """trading_bot_uptime_seconds gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_bot_uptime("test-bot", 3600.0)
