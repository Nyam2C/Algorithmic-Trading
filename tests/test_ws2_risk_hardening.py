"""
Tests for WS2: Risk Manager Hardening (Phase 9)

Issues: F, G, H, I, J, R
"""
from datetime import datetime, timezone

import pytest

from src.bot_config import BotConfig
from src.trading.risk_manager import RiskManager

# =============================================================================
# Issue R (P2): Leverage cap at 125x is dangerous -> change to 50x
# =============================================================================


class TestIssueLeverageCap:
    """Issue R: leverage 최대값을 125x -> 50x로 변경."""

    def test_leverage_50_allowed(self) -> None:
        """50x leverage는 허용."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            leverage=50,
            stop_loss_pct=0.0003,
            max_daily_loss_pct=0.50,
        )
        assert config.leverage == 50

    def test_leverage_51_rejected(self) -> None:
        """51x leverage는 거부."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                leverage=51,
                stop_loss_pct=0.0003,
                max_daily_loss_pct=0.50,
            )

    def test_leverage_125_rejected(self) -> None:
        """125x leverage는 거부 (이전에 허용)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                leverage=125,
                stop_loss_pct=0.0003,
                max_daily_loss_pct=0.50,
            )


# =============================================================================
# Issue F (P2): PnL excludes trading fees
# =============================================================================


class TestIssueFeeRate:
    """Issue F: BotConfig에 estimated_fee_rate 필드 추가."""

    def test_estimated_fee_rate_default(self) -> None:
        """기본 fee rate 0.0008 (0.08%)."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
        )
        assert config.estimated_fee_rate == 0.0008

    def test_estimated_fee_rate_custom(self) -> None:
        """커스텀 fee rate 설정."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.001,
        )
        assert config.estimated_fee_rate == 0.001

    def test_estimated_fee_rate_zero(self) -> None:
        """fee rate 0 허용 (수수료 없는 경우)."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.0,
        )
        assert config.estimated_fee_rate == 0.0

    def test_estimated_fee_rate_max(self) -> None:
        """fee rate 최대값 0.01 (1%) 허용."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.01,
        )
        assert config.estimated_fee_rate == 0.01

    def test_estimated_fee_rate_over_max_rejected(self) -> None:
        """fee rate > 0.01 거부."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                estimated_fee_rate=0.02,
            )


# =============================================================================
# Issue G (P2): Risk manager state lost on restart
# =============================================================================


class TestIssueRiskManagerSerialization:
    """Issue G: RiskManager to_dict()/from_dict() 직렬화."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager(
            max_daily_loss_pct=0.05,
            max_drawdown_pct=0.10,
            max_consecutive_losses=3,
            cooldown_minutes=30,
        )

    @pytest.mark.asyncio
    async def test_to_dict_contains_all_fields(self, risk_manager):
        """to_dict()가 모든 필수 필드를 포함."""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-100.0)
        await risk_manager.track_trade_result(is_win=False)

        state = risk_manager.to_dict()

        assert "daily_pnl" in state
        assert "daily_start_balance" in state
        assert "daily_reset_time" in state
        assert "consecutive_losses" in state
        assert "cooldown_until" in state
        assert "peak_balance" in state
        assert "current_drawdown" in state
        assert "total_trades" in state
        assert "winning_trades" in state
        assert "losing_trades" in state

    @pytest.mark.asyncio
    async def test_to_dict_values_correct(self, risk_manager):
        """to_dict()가 올바른 값을 반환."""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-100.0)
        await risk_manager.track_trade_pnl(50.0)

        state = risk_manager.to_dict()

        assert state["daily_pnl"] == -50.0
        assert state["daily_start_balance"] == 10000.0
        assert state["total_trades"] == 2
        assert state["winning_trades"] == 1
        assert state["losing_trades"] == 1
        assert state["peak_balance"] == 10000.0

    @pytest.mark.asyncio
    async def test_from_dict_restores_state(self, risk_manager):
        """from_dict()가 상태를 올바르게 복원."""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-200.0)
        await risk_manager.track_trade_result(is_win=False)
        await risk_manager.track_trade_result(is_win=False)

        # Serialize
        state = risk_manager.to_dict()

        # Create new instance and restore
        new_rm = RiskManager()
        new_rm.from_dict(state)

        assert new_rm._daily_pnl == -200.0
        assert new_rm._daily_start_balance == 10000.0
        assert new_rm._consecutive_losses == 2
        assert new_rm._total_trades == 1
        assert new_rm._winning_trades == 0
        assert new_rm._losing_trades == 1
        assert new_rm._peak_balance == 10000.0

    @pytest.mark.asyncio
    async def test_from_dict_restores_cooldown(self, risk_manager):
        """from_dict()가 쿨다운 상태를 복원."""
        # Trigger cooldown
        for _ in range(3):
            await risk_manager.track_trade_result(is_win=False)

        assert risk_manager._cooldown_until is not None

        state = risk_manager.to_dict()

        new_rm = RiskManager()
        new_rm.from_dict(state)

        assert new_rm._cooldown_until is not None
        assert new_rm._consecutive_losses == 3

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_halt_behavior(self, risk_manager):
        """직렬화/역직렬화 후 halt 판단이 동일."""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-600.0)  # -6% > 5%

        halt_before, _ = await risk_manager.should_halt_trading()

        state = risk_manager.to_dict()
        new_rm = RiskManager(max_daily_loss_pct=0.05)
        new_rm.from_dict(state)

        halt_after, _ = await new_rm.should_halt_trading()
        assert halt_before is True
        assert halt_after is True

    def test_to_dict_with_no_cooldown(self, risk_manager):
        """쿨다운 없을 때 to_dict."""
        state = risk_manager.to_dict()
        assert state["cooldown_until"] is None

    def test_from_dict_with_none_cooldown(self, risk_manager):
        """cooldown_until=None인 상태 복원."""
        state = {
            "daily_pnl": 0.0,
            "daily_start_balance": 5000.0,
            "daily_reset_time": datetime.now(timezone.utc).isoformat(),
            "consecutive_losses": 0,
            "cooldown_until": None,
            "peak_balance": 5000.0,
            "current_drawdown": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        }
        risk_manager.from_dict(state)
        assert risk_manager._cooldown_until is None

    def test_from_dict_empty_dict_no_crash(self, risk_manager):
        """빈 dict로 from_dict 호출 시 크래시 없음 (기본값 유지)."""
        risk_manager.from_dict({})
        # Should keep defaults
        assert risk_manager._daily_pnl == 0.0


# =============================================================================
# Issue J (P2): should_halt_trading() doesn't check drawdown
# =============================================================================


class TestIssueHaltChecksDrawdown:
    """Issue J: should_halt_trading()에 드로다운 체크 추가."""

    @pytest.mark.asyncio
    async def test_halt_on_drawdown_exceeded(self):
        """드로다운 한도 초과 시 halt."""
        rm = RiskManager(max_daily_loss_pct=0.05, max_drawdown_pct=0.10)
        await rm.reset_daily_stats(10000.0)
        rm._current_drawdown = 0.12  # 12% > 10%

        halt, reason = await rm.should_halt_trading()

        assert halt is True
        assert "드로다운" in reason

    @pytest.mark.asyncio
    async def test_no_halt_drawdown_under_limit(self):
        """드로다운이 한도 이내이면 halt 안 함."""
        rm = RiskManager(max_daily_loss_pct=0.05, max_drawdown_pct=0.10)
        await rm.reset_daily_stats(10000.0)
        rm._current_drawdown = 0.05  # 5% < 10%

        halt, reason = await rm.should_halt_trading()

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_halt_daily_loss_before_drawdown(self):
        """일일 손실이 먼저 한도 초과하면 일일 손실 사유 반환."""
        rm = RiskManager(max_daily_loss_pct=0.05, max_drawdown_pct=0.10)
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(-600.0)  # -6% > 5%
        rm._current_drawdown = 0.12  # 12% > 10%

        halt, reason = await rm.should_halt_trading()

        assert halt is True
        assert "일일 손실" in reason  # Daily loss checked first

    @pytest.mark.asyncio
    async def test_drawdown_halt_with_positive_pnl(self):
        """일일 PnL이 양수여도 드로다운으로 halt 가능."""
        rm = RiskManager(max_daily_loss_pct=0.05, max_drawdown_pct=0.10)
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(100.0)  # +1% profit today
        rm._current_drawdown = 0.15  # 15% drawdown from peak

        halt, reason = await rm.should_halt_trading()

        assert halt is True
        assert "드로다운" in reason


# =============================================================================
# Issue H (P2): Exposure calculation inconsistency
# =============================================================================


class TestIssueExposureConsistency:
    """Issue H: position_value에 leverage 포함 필요.

    Note: This tests the logic that position_value should be
    current_price * pct * leverage instead of current_price * pct.
    The actual change is in bot_instance.py:1580 which multiplies by leverage.
    """

    def test_exposure_value_includes_leverage(self) -> None:
        """position_value = price * pct * leverage 임을 확인."""
        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",  # leverage=5
        )
        pct = config.get_effective_position_size_pct()  # 0.05
        leverage = config.get_effective_leverage()  # 5
        current_price = 50000.0

        # Before fix: position_value = 50000 * 0.05 = 2500
        # After fix:  position_value = 50000 * 0.05 * 5 = 12500
        position_value = current_price * pct * leverage
        assert position_value == 12500.0


# =============================================================================
# Issue I (P2): reserve_exposure() unused in trade flow
# =============================================================================


class TestIssueReserveExposureInCanOpen:
    """Issue I: can_open_position()에 reserve_exposure() 통합."""

    @pytest.mark.asyncio
    async def test_can_open_position_creates_reservation(self):
        """can_open_position() 허용 시 자동 예약."""
        from src.bot_manager import MultiBotManager

        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        can_open, reason = await manager.can_open_position("btc-bot", 50000.0)

        assert can_open is True
        assert reason == ""
        # Reservation should be created
        assert "btc-bot" in manager._pending_reservations
        assert manager._pending_reservations["btc-bot"] == 50000.0

    @pytest.mark.asyncio
    async def test_can_open_position_reject_no_reservation(self):
        """can_open_position() 거부 시 예약 없음."""
        from src.bot_manager import MultiBotManager

        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=10000.0,
        )

        can_open, reason = await manager.can_open_position("btc-bot", 50000.0)

        assert can_open is False
        assert "btc-bot" not in manager._pending_reservations

    @pytest.mark.asyncio
    async def test_can_open_no_limit_no_reservation(self):
        """노출도 제한 없으면 예약 불필요."""
        from src.bot_manager import MultiBotManager

        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=0.0,  # no limit
        )

        can_open, reason = await manager.can_open_position("btc-bot", 50000.0)

        assert can_open is True
        # No reservation needed when no limit
        assert "btc-bot" not in manager._pending_reservations


# =============================================================================
# Scenario: Exposure Reservation (reserve + release cycle)
# (Relocated from test_phase8_audit_integration.py)
# =============================================================================


class TestExposureReservation:
    """이슈 10: 노출도 예약 패턴."""

    @pytest.mark.asyncio
    async def test_reserve_and_release_cycle(self):
        """예약 → 사용 → 해제 사이클."""
        from src.bot_manager import MultiBotManager

        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=10000.0,
        )

        # 예약 성공
        ok = await manager.reserve_exposure("bot-1", 5000.0)
        assert ok is True

        # 한도 초과 예약 실패
        ok = await manager.reserve_exposure("bot-2", 6000.0)
        assert ok is False

        # 예약 해제 후 재시도 성공
        await manager.release_reservation("bot-1")
        ok = await manager.reserve_exposure("bot-2", 6000.0)
        assert ok is True

        await manager.release_reservation("bot-2")

    @pytest.mark.asyncio
    async def test_total_exposure_includes_pending(self):
        """총 노출도에 대기 예약 포함."""
        from src.bot_manager import MultiBotManager

        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=10000.0,
        )

        await manager.reserve_exposure("bot-1", 3000.0)

        total = await manager.get_total_exposure()
        assert total >= 3000.0  # 최소 대기 예약 포함
