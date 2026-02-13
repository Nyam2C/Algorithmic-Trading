"""
Phase 7: Risk Lifecycle P1 Tests

Tests for:
- Issue 1.2: SL x Leverage vs Daily Loss Limit Consistency
- Issue 2.2: Use Actual Fill Price for PnL
- Issue 2.1: Force Close Positions on Risk Halt
- Issue 2.4: DB Write Failure Recovery
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot_config import BotConfig
from src.trading.risk_manager import RiskManager

# =============================================================================
# Issue 1.2: SL x Leverage vs Daily Loss Limit Consistency
# =============================================================================


class TestRiskConsistency:
    """SL x leverage와 일일 손실 한도 일관성 테스트."""

    def test_risk_consistency_raises_error(self) -> None:
        """SL x leverage > daily_limit일 때 ValueError 발생."""
        from pydantic import ValidationError

        # SL=0.4%, leverage=20 => 8% > daily limit 5%
        with pytest.raises(ValidationError, match="리스크 불일치"):
            BotConfig(
                bot_name="risky-bot",
                symbol="BTCUSDT",
                risk_level="medium",
                leverage=20,
                stop_loss_pct=0.004,
                max_daily_loss_pct=0.05,
            )

    def test_risk_consistency_ok(self) -> None:
        """SL x leverage < daily_limit일 때 정상 생성."""
        config = BotConfig(
            bot_name="safe-bot",
            symbol="BTCUSDT",
            risk_level="low",
            leverage=3,
            stop_loss_pct=0.003,
            max_daily_loss_pct=0.05,
        )
        # SL=0.3% x leverage=3 = 0.9% < 5% => no error
        assert config.leverage == 3
        assert config.stop_loss_pct == 0.003

    def test_max_loss_per_trade_field(self) -> None:
        """BotConfig.max_loss_per_trade_pct 기본값 확인."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
        )
        assert config.max_loss_per_trade_pct == 0.02

    def test_close_on_risk_halt_field(self) -> None:
        """BotConfig.close_on_risk_halt 기본값 확인."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
        )
        assert config.close_on_risk_halt is True


# =============================================================================
# Issue 1.2: validate_position_risk
# =============================================================================


class TestValidatePositionRisk:
    """단일 거래 리스크 검증 테스트."""

    @pytest.mark.asyncio
    async def test_validate_position_risk_exceeds(self) -> None:
        """리스크 초과 시 False 반환."""
        rm = RiskManager()
        # SL=0.4% x leverage=20 = 8% > 2% limit
        ok, reason = await rm.validate_position_risk(
            stop_loss_pct=0.004,
            leverage=20,
            max_loss_per_trade_pct=0.02,
        )
        assert ok is False
        assert "단일 거래 리스크 초과" in reason

    @pytest.mark.asyncio
    async def test_validate_position_risk_ok(self) -> None:
        """리스크 범위 내일 때 True 반환."""
        rm = RiskManager()
        # SL=0.3% x leverage=3 = 0.9% < 2% limit
        ok, reason = await rm.validate_position_risk(
            stop_loss_pct=0.003,
            leverage=3,
            max_loss_per_trade_pct=0.02,
        )
        assert ok is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_validate_position_risk_boundary(self) -> None:
        """경계값 테스트: 정확히 같을 때는 통과."""
        rm = RiskManager()
        # SL=1% x leverage=2 = 2% == 2% limit (not exceeded)
        ok, reason = await rm.validate_position_risk(
            stop_loss_pct=0.01,
            leverage=2,
            max_loss_per_trade_pct=0.02,
        )
        assert ok is True
        assert reason == ""


# =============================================================================
# Helper: Create a BotInstance for testing
# =============================================================================


def _make_bot_instance(**overrides):
    """테스트용 BotInstance 생성 헬퍼."""
    from src.bot_instance import BotInstance

    config_kwargs = {
        "bot_name": "test-bot",
        "symbol": "BTCUSDT",
        "risk_level": "low",
        "leverage": 3,
        "stop_loss_pct": 0.003,
        "max_daily_loss_pct": 0.05,
        "max_loss_per_trade_pct": 0.02,
        "close_on_risk_halt": True,
    }
    config_kwargs.update(overrides.pop("config_overrides", {}))
    config = BotConfig(**config_kwargs)

    bot = BotInstance(
        config=config,
        binance_api_key="test",
        binance_secret_key="test",
        **overrides,
    )
    return bot


# =============================================================================
# Issue 2.2: Use Actual Fill Price for PnL
# =============================================================================


class TestPnlFillPrice:
    """실제 체결가 기반 PnL 계산 테스트."""

    @pytest.mark.asyncio
    async def test_pnl_uses_actual_fill_price(self) -> None:
        """_close_position이 order[avgPrice]를 사용하여 PnL 계산."""
        bot = _make_bot_instance()

        # Mock executor
        mock_executor = AsyncMock()
        mock_executor.get_position.return_value = {
            "entry_price": 100000.0,
            "side": "LONG",
            "position_amt": 0.001,
        }
        mock_executor.close_position.return_value = {
            "avgPrice": "100500.0",  # 실제 체결가
            "origQty": "0.001",
        }
        mock_executor.calculate_pnl_pct = MagicMock(return_value=0.5)
        mock_executor.current_position = {"trade_id": 1, "entry_time": datetime.now()}

        bot._executor = mock_executor
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._close_position(99000.0, "TP")

        # calculate_pnl_pct should be called with exit_price=100500.0, not 99000.0
        mock_executor.calculate_pnl_pct.assert_called_once_with(
            100000.0, 100500.0, "LONG"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_pnl_fallback_no_avg_price(self) -> None:
        """avgPrice 없을 때 current_price로 폴백."""
        bot = _make_bot_instance()

        mock_executor = AsyncMock()
        mock_executor.get_position.return_value = {
            "entry_price": 100000.0,
            "side": "LONG",
            "position_amt": 0.001,
        }
        mock_executor.close_position.return_value = {
            "origQty": "0.001",
            # no avgPrice field
        }
        mock_executor.calculate_pnl_pct = MagicMock(return_value=-0.5)
        mock_executor.current_position = {"trade_id": 1, "entry_time": datetime.now()}

        bot._executor = mock_executor
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._close_position(99500.0, "SL")

        # Should fall back to current_price=99500.0
        mock_executor.calculate_pnl_pct.assert_called_once_with(
            100000.0, 99500.0, "LONG"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_pnl_fallback_invalid_avg_price(self) -> None:
        """avgPrice 파싱 실패 시 current_price로 폴백."""
        bot = _make_bot_instance()

        mock_executor = AsyncMock()
        mock_executor.get_position.return_value = {
            "entry_price": 100000.0,
            "side": "SHORT",
            "position_amt": 0.001,
        }
        mock_executor.close_position.return_value = {
            "avgPrice": "invalid_price",
            "origQty": "0.001",
        }
        mock_executor.calculate_pnl_pct = MagicMock(return_value=1.0)
        mock_executor.current_position = {"trade_id": 1, "entry_time": datetime.now()}

        bot._executor = mock_executor
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._close_position(99000.0, "TP")

        # Should fall back to current_price=99000.0 due to parse failure
        mock_executor.calculate_pnl_pct.assert_called_once_with(
            100000.0, 99000.0, "SHORT"
        )


# =============================================================================
# Issue 2.1: Force Close Positions on Risk Halt
# =============================================================================


class TestRiskHaltClosePosition:
    """리스크 한도 시 포지션 강제 청산 테스트."""

    @pytest.mark.asyncio
    async def test_risk_halt_closes_position(self) -> None:
        """close_on_risk_halt=True일 때 리스크 한도에서 포지션 청산."""
        bot = _make_bot_instance(
            config_overrides={"close_on_risk_halt": True},
        )

        # Setup: risk manager should halt
        bot._risk_manager = RiskManager(max_daily_loss_pct=0.05)
        await bot._risk_manager.reset_daily_stats(10000.0)
        await bot._risk_manager.track_trade_pnl(-600.0)  # -6% > 5%

        # Mock executor with active position
        mock_executor = AsyncMock()
        mock_executor.get_position.return_value = {
            "entry_price": 100000.0,
            "side": "LONG",
            "position_amt": 0.001,
        }
        mock_executor.close_position.return_value = {
            "avgPrice": "99500.0",
            "origQty": "0.001",
        }
        mock_executor.calculate_pnl_pct = MagicMock(return_value=-0.5)
        mock_executor.current_position = {"trade_id": 1, "entry_time": datetime.now()}
        bot._executor = mock_executor

        # Mock binance client for price fetch
        mock_client = AsyncMock()
        mock_client.get_current_price.return_value = 99500.0
        mock_client.get_account_balance.return_value = {"available": 9400.0}
        bot._binance_client = mock_client

        # Execute loop
        await bot._execute_single_loop()

        # Should have tried to close the position
        mock_executor.close_position.assert_called_once()
        assert bot._is_paused is True

    @pytest.mark.asyncio
    async def test_risk_halt_no_close(self) -> None:
        """close_on_risk_halt=False일 때 포지션 유지, 일시정지만."""
        bot = _make_bot_instance(
            config_overrides={"close_on_risk_halt": False},
        )

        # Setup: risk manager should halt
        bot._risk_manager = RiskManager(max_daily_loss_pct=0.05)
        await bot._risk_manager.reset_daily_stats(10000.0)
        await bot._risk_manager.track_trade_pnl(-600.0)  # -6% > 5%

        # Mock executor with active position
        mock_executor = AsyncMock()
        mock_executor.get_position.return_value = {
            "entry_price": 100000.0,
            "side": "LONG",
            "position_amt": 0.001,
        }
        bot._executor = mock_executor

        # Mock binance client
        mock_client = AsyncMock()
        mock_client.get_account_balance.return_value = {"available": 9400.0}
        bot._binance_client = mock_client

        # Execute loop
        await bot._execute_single_loop()

        # close_position should NOT be called (only get_position for check)
        mock_executor.close_position.assert_not_called()
        assert bot._is_paused is True


# =============================================================================
# Issue 2.4: DB Write Failure Recovery
# =============================================================================


class TestDbFailureRecovery:
    """DB 기록 실패 시 Redis 복구 마커 테스트."""

    @pytest.mark.asyncio
    async def test_db_failure_redis_recovery(self) -> None:
        """DB 기록 실패 시 Redis에 복구 마커 저장."""
        bot = _make_bot_instance()

        # Mock executor
        mock_executor = AsyncMock()
        mock_executor.open_position.return_value = {
            "origQty": "0.001",
            "orderId": "12345",
        }
        mock_executor.current_position = {"side": "LONG", "entry_price": 100000.0}
        bot._executor = mock_executor

        # Mock trade_db that fails
        mock_db = AsyncMock()
        mock_db.add_entry.side_effect = Exception("DB connection error")
        bot._trade_db = mock_db

        # Mock redis state manager
        mock_redis = AsyncMock()
        bot._redis_state_manager = mock_redis

        # Mock risk manager to pass validation
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._open_position("LONG", 100000.0)

        # Order should still be placed
        assert result is not None
        # Redis recovery marker should be saved
        mock_redis.save_position.assert_called_once()
        call_args = mock_redis.save_position.call_args
        assert "test-bot:recovery" in call_args[0]
        recovery_data = call_args[0][1]
        assert recovery_data["side"] == "LONG"
        assert recovery_data["entry_price"] == 100000.0
        assert recovery_data["order_id"] == "12345"

    @pytest.mark.asyncio
    async def test_db_and_redis_failure(self) -> None:
        """DB와 Redis 모두 실패 시 critical 로그, 포지션은 메모리에 유지."""
        bot = _make_bot_instance()

        # Mock executor
        mock_executor = AsyncMock()
        mock_executor.open_position.return_value = {
            "origQty": "0.001",
            "orderId": "12345",
        }
        mock_executor.current_position = {"side": "LONG", "entry_price": 100000.0}
        bot._executor = mock_executor

        # Mock trade_db that fails
        mock_db = AsyncMock()
        mock_db.add_entry.side_effect = Exception("DB connection error")
        bot._trade_db = mock_db

        # Mock redis that also fails
        mock_redis = AsyncMock()
        mock_redis.save_position.side_effect = Exception("Redis connection error")
        bot._redis_state_manager = mock_redis

        # Mock risk manager to pass validation
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._open_position("LONG", 100000.0)

        # Order should still succeed (exchange order was placed)
        assert result is not None
        # Position should still be in memory
        assert bot._current_position is not None

    @pytest.mark.asyncio
    async def test_db_success_no_redis_fallback(self) -> None:
        """DB 성공 시 Redis 복구 마커 저장하지 않음."""
        bot = _make_bot_instance()

        # Mock executor
        mock_executor = AsyncMock()
        mock_executor.open_position.return_value = {
            "origQty": "0.001",
            "orderId": "12345",
        }
        mock_executor.current_position = {"side": "LONG", "entry_price": 100000.0}
        bot._executor = mock_executor

        # Mock trade_db that succeeds
        mock_db = AsyncMock()
        mock_db.add_entry.return_value = 42
        bot._trade_db = mock_db

        # Mock redis state manager
        mock_redis = AsyncMock()
        bot._redis_state_manager = mock_redis

        # Mock risk manager to pass validation
        bot._risk_manager = RiskManager()
        await bot._risk_manager.reset_daily_stats(10000.0)

        result = await bot._open_position("LONG", 100000.0)

        assert result is not None
        # Redis save_position should NOT be called for recovery
        mock_redis.save_position.assert_not_called()


# =============================================================================
# Issue 1.2: Risk validation blocks open_position
# =============================================================================


class TestOpenPositionRiskBlock:
    """_open_position 리스크 검증 블록 테스트."""

    @pytest.mark.asyncio
    async def test_risk_validation_blocks_entry(self) -> None:
        """리스크 검증 실패 시 포지션 진입 차단."""
        bot = _make_bot_instance(
            config_overrides={
                "leverage": 50,
                "stop_loss_pct": 0.004,
                "max_loss_per_trade_pct": 0.02,
                "max_daily_loss_pct": 0.25,  # 높은 일일 한도로 설정 검증 통과
            },
        )

        mock_executor = AsyncMock()
        bot._executor = mock_executor
        bot._risk_manager = RiskManager()

        # SL=0.4% x leverage=50 = 20% >> max_loss_per_trade_pct 2%
        result = await bot._open_position("LONG", 100000.0)

        assert result is None
        mock_executor.open_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_risk_validation_allows_entry(self) -> None:
        """리스크 검증 통과 시 포지션 진입 허용."""
        bot = _make_bot_instance(
            config_overrides={
                "leverage": 3,
                "stop_loss_pct": 0.003,
                "max_loss_per_trade_pct": 0.02,
            },
        )

        mock_executor = AsyncMock()
        mock_executor.open_position.return_value = {
            "origQty": "0.001",
            "orderId": "123",
        }
        mock_executor.current_position = None
        bot._executor = mock_executor
        bot._risk_manager = RiskManager()

        # SL=0.3% x leverage=3 = 0.9% < 2% limit
        result = await bot._open_position("LONG", 100000.0)

        mock_executor.open_position.assert_called_once()


# =============================================================================
# Scenario 4: BotConfig(sl=0.006, leverage=10) → ValueError
# (Relocated from test_phase8_audit_integration.py)
# =============================================================================


class TestScenario4DangerousConfigRejection:
    """이슈 4: 위험한 설정 조합 거부."""

    def test_sl_times_leverage_exceeds_daily_limit_raises(self):
        """sl(0.006) x leverage(10) = 6% > 5% → ValueError."""
        with pytest.raises(ValueError, match="리스크 불일치"):
            BotConfig(
                bot_name="dangerous-bot",
                symbol="BTCUSDT",
                risk_level="medium",
                stop_loss_pct=0.006,
                leverage=10,
            )

    def test_safe_config_accepted(self):
        """sl(0.004) x leverage(10) = 4% < 5% → 정상 생성."""
        config = BotConfig(
            bot_name="safe-bot",
            symbol="BTCUSDT",
            risk_level="high",
            # high 기본값: leverage=10, stop_loss_pct=0.004
        )
        assert config.get_effective_leverage() == 10
        assert config.get_effective_stop_loss_pct() == 0.004

    def test_high_risk_defaults_are_safe(self):
        """high 위험도 기본값이 안전한지 확인 (0.004 x 10 = 4% < 5%)."""
        config = BotConfig(
            bot_name="high-bot",
            symbol="BTCUSDT",
            risk_level="high",
        )
        sl = config.get_effective_stop_loss_pct()
        lev = config.get_effective_leverage()
        assert sl * lev <= 0.05  # 5% 일일 한도 이내
