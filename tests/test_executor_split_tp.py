"""Tests for split TP functionality in TradingExecutor.

APEX-V Phase A-4: 분할 익절 테스트
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.trading.executor import TradingExecutor


@pytest.fixture
def mock_config():
    """Split TP 활성화된 설정"""
    config = MagicMock()
    config.symbol = "BTCUSDT"
    config.leverage = 10
    config.position_size_pct = 0.05
    config.take_profit_pct = 0.008
    config.stop_loss_pct = 0.004
    config.use_atr_tp_sl = True
    config.atr_tp_multiplier = 2.0
    config.atr_sl_multiplier = 1.0
    config.use_split_tp = True
    config.split_tp_ratios = [0.5, 0.3, 0.2]
    config.split_tp_atr_multipliers = [1.0, 1.5, 2.5]
    config.max_slippage_pct = 0.005
    config.close_on_excessive_slippage = False
    return config


@pytest.fixture
def mock_client():
    """Mock Binance client"""
    client = AsyncMock()
    client.create_stop_market_order = AsyncMock(return_value={"orderId": 1})
    client.create_take_profit_market_order = AsyncMock(return_value={"orderId": 2})
    return client


@pytest.fixture
def executor(mock_client, mock_config):
    """TradingExecutor with split TP config"""
    return TradingExecutor(mock_client, mock_config)


class TestSplitTPPlacement:
    """분할 TP 주문 배치 테스트"""

    @pytest.mark.asyncio
    async def test_split_tp_delegates_when_enabled(self, executor, mock_client):
        """use_split_tp=True + ATR 존재 시 분할 TP로 위임"""
        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )
        assert result is True
        # SL 1회 + TP 3회 = 4회 주문
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 3

    @pytest.mark.asyncio
    async def test_split_tp_without_atr_falls_back(self, executor, mock_client):
        """ATR 없으면 기존 단일 TP로 fallback"""
        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=None,
        )
        assert result is True
        # SL + TP 각 1회 (기존 로직)
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 1

    @pytest.mark.asyncio
    async def test_split_tp_disabled_uses_single(self, mock_client):
        """use_split_tp=False면 단일 TP"""
        config = MagicMock()
        config.symbol = "BTCUSDT"
        config.use_split_tp = False
        config.use_atr_tp_sl = True
        config.atr_tp_multiplier = 2.0
        config.atr_sl_multiplier = 1.0
        config.take_profit_pct = 0.008
        config.stop_loss_pct = 0.004
        executor = TradingExecutor(mock_client, config)

        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )
        assert result is True
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 1


class TestSplitTPPrices:
    """분할 TP 가격 계산 테스트"""

    @pytest.mark.asyncio
    async def test_long_split_tp_prices(self, executor, mock_client):
        """LONG 분할 TP 가격이 올바른지"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )

        tp_calls = mock_client.create_take_profit_market_order.call_args_list
        assert len(tp_calls) == 3

        # TP1: 50000 + 500*1.0 = 50500
        assert tp_calls[0].kwargs["stop_price"] == 50500.0
        # TP2: 50000 + 500*1.5 = 50750
        assert tp_calls[1].kwargs["stop_price"] == 50750.0
        # TP3: 50000 + 500*2.5 = 51250
        assert tp_calls[2].kwargs["stop_price"] == 51250.0

    @pytest.mark.asyncio
    async def test_short_split_tp_prices(self, executor, mock_client):
        """SHORT 분할 TP 가격이 올바른지"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="SHORT",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )

        tp_calls = mock_client.create_take_profit_market_order.call_args_list
        assert len(tp_calls) == 3

        # TP1: 50000 - 500*1.0 = 49500
        assert tp_calls[0].kwargs["stop_price"] == 49500.0
        # TP2: 50000 - 500*1.5 = 49250
        assert tp_calls[1].kwargs["stop_price"] == 49250.0
        # TP3: 50000 - 500*2.5 = 48750
        assert tp_calls[2].kwargs["stop_price"] == 48750.0


class TestSplitTPQuantities:
    """분할 TP 수량 테스트"""

    @pytest.mark.asyncio
    async def test_split_tp_quantities(self, executor, mock_client):
        """분할 비율대로 수량 분배"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.1,
            entry_price=50000.0,
            entry_atr=500.0,
        )

        tp_calls = mock_client.create_take_profit_market_order.call_args_list
        # TP1: 50% = 0.05
        assert tp_calls[0].kwargs["quantity"] == 0.05
        # TP2: 30% = 0.03
        assert tp_calls[1].kwargs["quantity"] == 0.03
        # TP3: 20% = 0.02
        assert tp_calls[2].kwargs["quantity"] == 0.02

    @pytest.mark.asyncio
    async def test_split_tp_skips_tiny_quantity(self, executor, mock_client):
        """최소 주문 수량 미만이면 스킵"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.002,  # 20% = 0.0004 < 0.001
            entry_price=50000.0,
            entry_atr=500.0,
        )

        # TP3 (20% = 0.0004) 스킵되어야 함
        tp_calls = mock_client.create_take_profit_market_order.call_args_list
        assert len(tp_calls) == 2  # TP1 + TP2 only


class TestSplitTPSLFailure:
    """분할 TP SL 실패 테스트"""

    @pytest.mark.asyncio
    async def test_sl_failure_returns_false(self, executor, mock_client):
        """SL 주문 실패 시 False 반환"""
        mock_client.create_stop_market_order.side_effect = Exception("SL failed")

        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_tp_failure_still_returns_true(self, executor, mock_client):
        """TP 주문 실패해도 SL 성공이면 True"""
        mock_client.create_take_profit_market_order.side_effect = Exception("TP failed")

        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
        )
        assert result is True


class TestBotConfigSplitTP:
    """BotConfig split TP 설정 테스트"""

    def test_default_split_tp_disabled(self):
        """기본값: split TP 비활성화"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.use_split_tp is False

    def test_split_tp_ratios_default(self):
        """기본 분할 비율"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.split_tp_ratios == [0.5, 0.3, 0.2]

    def test_split_tp_ratios_must_sum_to_one(self):
        """분할 비율 합이 1.0이 아니면 에러"""
        from src.bot_config import BotConfig
        with pytest.raises(ValueError, match=r"sum must be 1\.0"):
            BotConfig(
                bot_name="test",
                stop_loss_pct=0.003,
                leverage=3,
                split_tp_ratios=[0.5, 0.3, 0.3],  # sum = 1.1
            )

    def test_split_tp_custom_ratios(self):
        """커스텀 분할 비율"""
        from src.bot_config import BotConfig
        config = BotConfig(
            bot_name="test",
            stop_loss_pct=0.003,
            leverage=3,
            split_tp_ratios=[0.6, 0.25, 0.15],
        )
        assert config.split_tp_ratios == [0.6, 0.25, 0.15]

    def test_use_adx_regime_default(self):
        """기본값: ADX regime 비활성화"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.use_adx_regime is False
