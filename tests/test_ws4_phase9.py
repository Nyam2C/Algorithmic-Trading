"""Tests for WS4: Exchange Close Detection & Signal Quality.

Phase 9: Issues B, P, Q, T, U
"""
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.regime_detector import MarketRegime, RegimeDetector

# =========================================================================
# Issue B: Exchange SL/TP fills not detected at runtime
# =========================================================================


class TestExchangeCloseDetection:
    """Issue B: Detect when exchange closes position via SL/TP."""

    @pytest.fixture
    def bot_instance(self):
        """Create a minimal BotInstance for testing."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(bot_name='test-bot', symbol='BTCUSDT')
        bot = BotInstance(
            config=config,
            binance_api_key='test',
            binance_secret_key='test',
        )
        return bot

    @pytest.mark.asyncio
    async def test_detects_exchange_side_close(self, bot_instance):
        """When executor has a position but exchange returns None, detect the close."""
        bot = bot_instance

        # Setup: executor has a tracked position
        mock_executor = AsyncMock()
        mock_executor.current_position = {
            'side': 'LONG',
            'entry_price': 50000.0,
            'position_amt': 0.01,
            'trade_id': 'test-123',
            'entry_time': datetime.now(),
        }
        # Exchange says no position exists
        mock_executor.get_position = AsyncMock(return_value=None)
        mock_executor.calculate_pnl_pct = MagicMock(return_value=-1.5)

        bot._executor = mock_executor

        # Mock binance client for current price
        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=49500.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={'available': 1000.0, 'total': 1000.0}
        )
        mock_client.cancel_all_open_orders = AsyncMock()
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        # Mock risk manager
        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ''))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, 'test'))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()
        bot._risk_manager.track_trade_result = AsyncMock()

        # Mock trade DB
        bot._trade_db = AsyncMock()
        bot._trade_db.add_exit = AsyncMock(return_value=True)

        # Mock _fetch_market_data to return simple data
        bot._fetch_market_data = AsyncMock(return_value={
            'current_price': 49500.0,
            'indicators': {
                'ma_7': 50000.0, 'ma_25': 50500.0, 'ma_99': 51000.0,
                'atr': 500.0, 'price': 49500.0, 'rsi': 50.0, 'volume_ratio': 1.0,
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
        bot = bot_instance
        mock_executor = AsyncMock()
        mock_executor.current_position = None
        mock_executor.get_position = AsyncMock(return_value=None)
        bot._executor = mock_executor

        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={'available': 1000.0, 'total': 1000.0}
        )
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ''))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, 'test'))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()

        bot._fetch_market_data = AsyncMock(return_value={
            'current_price': 50000.0,
            'indicators': {
                'ma_7': 50000.0, 'ma_25': 50500.0, 'ma_99': 51000.0,
                'atr': 500.0, 'price': 50000.0, 'rsi': 50.0, 'volume_ratio': 1.0,
            },
        })

        # No tracked position, so no detection should happen
        await bot._execute_single_loop()
        bot._risk_manager.track_trade_pnl.assert_not_called()

    @pytest.mark.asyncio
    async def test_exchange_close_records_to_db(self, bot_instance):
        """Exchange close should record exit in DB."""
        bot = bot_instance

        mock_executor = AsyncMock()
        mock_executor.current_position = {
            'side': 'SHORT',
            'entry_price': 52000.0,
            'position_amt': 0.02,
            'trade_id': 'trade-456',
            'entry_time': datetime.now(),
        }
        mock_executor.get_position = AsyncMock(return_value=None)
        mock_executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        bot._executor = mock_executor

        mock_client = AsyncMock()
        mock_client.get_current_price = AsyncMock(return_value=51000.0)
        mock_client.get_account_balance = AsyncMock(
            return_value={'available': 1000.0, 'total': 1000.0}
        )
        mock_client.get_klines = AsyncMock(return_value=[])
        bot._binance_client = mock_client

        bot._risk_manager = AsyncMock()
        bot._risk_manager.should_halt_trading = AsyncMock(return_value=(False, ''))
        bot._risk_manager.should_skip_trade = AsyncMock(return_value=(True, 'test'))
        bot._risk_manager.check_and_reset_if_new_day = AsyncMock()
        bot._risk_manager.update_balance = AsyncMock()
        bot._risk_manager.track_trade_pnl = AsyncMock()
        bot._risk_manager.track_trade_result = AsyncMock()

        mock_db = AsyncMock()
        mock_db.add_exit = AsyncMock(return_value=True)
        bot._trade_db = mock_db

        bot._fetch_market_data = AsyncMock(return_value={
            'current_price': 51000.0,
            'indicators': {
                'ma_7': 50000.0, 'ma_25': 50500.0, 'ma_99': 51000.0,
                'atr': 500.0, 'price': 51000.0, 'rsi': 50.0, 'volume_ratio': 1.0,
            },
        })

        await bot._execute_single_loop()

        # Should have recorded exit in DB with EXCHANGE_SL_TP reason
        mock_db.add_exit.assert_called_once()
        call_kwargs = mock_db.add_exit.call_args
        assert call_kwargs.kwargs.get('exit_reason') == 'EXCHANGE_SL_TP' or                (call_kwargs[1] if len(call_kwargs) > 1 else {}).get('exit_reason') == 'EXCHANGE_SL_TP'


# =========================================================================
# Issue P: partial_trend_mode=True makes RANGING nearly impossible
# =========================================================================


class TestPartialTrendModeRanging:
    """Issue P: Low volatility + partial trend should be RANGING."""

    @pytest.fixture
    def partial_detector(self):
        """RegimeDetector with partial_trend_mode=True."""
        return RegimeDetector(
            atr_strong_threshold=1.0,
            atr_weak_threshold=0.5,
            partial_trend_mode=True,
        )

    def test_low_volatility_partial_bullish_is_ranging(self, partial_detector):
        """MA7 > MA25 but low ATR should be RANGING in partial mode."""
        market_data = {
            'ma_7': 100100.0,   # MA7 > MA25 (bullish partial)
            'ma_25': 100000.0,
            'ma_99': 100200.0,  # Not aligned (MA99 > MA7)
            'atr': 300.0,       # 0.3% < weak_threshold (0.5%)
            'price': 100100.0,
        }
        regime = partial_detector.detect(market_data)
        assert regime == MarketRegime.RANGING

    def test_low_volatility_partial_bearish_is_ranging(self, partial_detector):
        """MA7 < MA25 but low ATR should be RANGING in partial mode."""
        market_data = {
            'ma_7': 99900.0,    # MA7 < MA25 (bearish partial)
            'ma_25': 100000.0,
            'ma_99': 99800.0,   # Not aligned (MA99 < MA7)
            'atr': 300.0,       # 0.3% < weak_threshold (0.5%)
            'price': 99900.0,
        }
        regime = partial_detector.detect(market_data)
        assert regime == MarketRegime.RANGING

    def test_sufficient_volatility_partial_bullish_is_weak_uptrend(self, partial_detector):
        """MA7 > MA25 with sufficient ATR should still be WEAK_UPTREND."""
        market_data = {
            'ma_7': 100500.0,
            'ma_25': 100000.0,
            'ma_99': 100200.0,  # Not fully aligned
            'atr': 600.0,       # 0.6% > weak_threshold (0.5%)
            'price': 100500.0,
        }
        regime = partial_detector.detect(market_data)
        assert regime == MarketRegime.WEAK_UPTREND

    def test_sufficient_volatility_partial_bearish_is_weak_downtrend(self, partial_detector):
        """MA7 < MA25 with sufficient ATR should still be WEAK_DOWNTREND."""
        market_data = {
            'ma_7': 99500.0,
            'ma_25': 100000.0,
            'ma_99': 99800.0,  # Not fully aligned
            'atr': 600.0,      # 0.6% > weak_threshold (0.5%)
            'price': 99500.0,
        }
        regime = partial_detector.detect(market_data)
        assert regime == MarketRegime.WEAK_DOWNTREND

    def test_fully_aligned_bullish_unaffected(self, partial_detector):
        """Fully aligned bullish should still be detected correctly."""
        market_data = {
            'ma_7': 100500.0,
            'ma_25': 100000.0,
            'ma_99': 99000.0,
            'atr': 1500.0,  # 1.5%
            'price': 100500.0,
        }
        regime = partial_detector.detect(market_data)
        assert regime == MarketRegime.STRONG_UPTREND


# =========================================================================
# Issue Q: Gemini confidence hardcoded at 0.8
# =========================================================================


class TestGeminiConfidence:
    """Issue Q: Gemini confidence should default to 0.6."""

    @pytest.mark.asyncio
    async def test_gemini_default_confidence_is_0_6(self):
        """Default Gemini confidence should be 0.6, not 0.8."""
        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=('LONG', 'Test reason')
        )
        # Explicitly no last_confidence (or set to None)
        mock_gemini.last_confidence = None

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        assert signal.confidence == 0.6

    @pytest.mark.asyncio
    async def test_gemini_parsed_confidence_used(self):
        """When Gemini returns confidence in response, use it."""
        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=('LONG', 'Test reason')
        )
        mock_gemini.last_confidence = 0.9  # Parsed confidence (float)

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        # Should use the parsed confidence
        assert signal.confidence == 0.9

    @pytest.mark.asyncio
    async def test_gemini_no_parsed_confidence_uses_default(self):
        """When Gemini has no parsed confidence, use 0.6 default."""
        from src.ai.ensemble import EnsembleSignalGenerator

        mock_gemini = MagicMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=('SHORT', 'Bearish')
        )
        # No parsed confidence (None)
        mock_gemini.last_confidence = None

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)
        signal = await ensemble._get_gemini_signal({})

        assert signal.confidence == 0.6


# =========================================================================
# Issue T: /metrics endpoint has no auth
# =========================================================================


class TestMetricsAuth:
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
        with patch.dict(os.environ, {}, clear=False):
            # Make sure METRICS_AUTH_TOKEN is not set
            os.environ.pop('METRICS_AUTH_TOKEN', None)
            resp = client.get('/metrics')
            assert resp.status_code == 200

    def test_metrics_rejects_without_token(self, client):
        """When METRICS_AUTH_TOKEN is set, request without token gets 401."""
        with patch.dict(os.environ, {'METRICS_AUTH_TOKEN': 'secret123'}):
            resp = client.get('/metrics')
            assert resp.status_code == 401

    def test_metrics_rejects_wrong_token(self, client):
        """When METRICS_AUTH_TOKEN is set, wrong token gets 401."""
        with patch.dict(os.environ, {'METRICS_AUTH_TOKEN': 'secret123'}):
            resp = client.get('/metrics', headers={'Authorization': 'Bearer wrong'})
            assert resp.status_code == 401

    def test_metrics_accepts_correct_token(self, client):
        """When METRICS_AUTH_TOKEN is set, correct token gets 200."""
        with patch.dict(os.environ, {'METRICS_AUTH_TOKEN': 'secret123'}):
            resp = client.get('/metrics', headers={'Authorization': 'Bearer secret123'})
            assert resp.status_code == 200


# =========================================================================
# Issue U: Missing Prometheus operational metrics
# =========================================================================


class TestOperationalMetrics:
    """Issue U: New operational Prometheus metrics."""

    def test_exchange_connected_gauge_exists(self):
        """trading_exchange_connected gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        # Should be able to set the gauge without error
        metrics.record_exchange_connected('test-bot', True)
        metrics.record_exchange_connected('test-bot', False)

    def test_circuit_breaker_state_gauge_exists(self):
        """trading_circuit_breaker_state gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_circuit_breaker_state('api_breaker', 0)
        metrics.record_circuit_breaker_state('api_breaker', 1)

    def test_open_positions_gauge_exists(self):
        """trading_open_positions gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_open_positions('test-bot', 1)
        metrics.record_open_positions('test-bot', 0)

    def test_bot_uptime_gauge_exists(self):
        """trading_bot_uptime_seconds gauge should exist."""
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics

        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)

        metrics.record_bot_uptime('test-bot', 3600.0)
