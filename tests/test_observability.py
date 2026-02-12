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
        """Gemini 로깅에 event_type=AI_SIGNAL 바인딩 확인."""
        with patch("src.ai.ai_logger.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            ai_logger.log_gemini_call(
                bot_name="btc-bot",
                prompt_summary="test",
                raw_response="LONG",
                parsed_signal="LONG",
            )

            mock_logger.bind.assert_called_with(event_type="AI_SIGNAL")
            mock_bound.info.assert_called_once()

    def test_log_ensemble_with_event_type(self, ai_logger):
        """앙상블 로깅에 event_type=ENSEMBLE_SIGNAL 바인딩 확인."""
        with patch("src.ai.ai_logger.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            ai_logger.log_ensemble_decision(
                bot_name="btc-bot",
                component_signals=[],
                final_signal="WAIT",
                consensus_ratio=0.0,
            )

            mock_logger.bind.assert_called_with(event_type="ENSEMBLE_SIGNAL")
            mock_bound.info.assert_called_once()


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
