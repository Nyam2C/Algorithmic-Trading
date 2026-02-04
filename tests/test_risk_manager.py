"""
Tests for RiskManager

Phase 5.2: 일일 손실 한도
Phase 5.3: 연속 손실 카운터
"""
import pytest
from datetime import datetime, timedelta, timezone

from src.trading.risk_manager import RiskManager


@pytest.fixture
def risk_manager():
    """기본 RiskManager 인스턴스"""
    return RiskManager(
        max_daily_loss_pct=0.05,  # 5%
        max_drawdown_pct=0.10,     # 10%
        max_consecutive_losses=3,
        cooldown_minutes=30,
    )


class TestDailyLossLimit:
    """Phase 5.2: 일일 손실 한도 테스트"""

    @pytest.mark.asyncio
    async def test_reset_daily_stats(self, risk_manager):
        """일일 통계 리셋 테스트"""
        await risk_manager.reset_daily_stats(10000.0)

        assert risk_manager._daily_start_balance == 10000.0
        assert risk_manager._daily_pnl == 0.0
        assert risk_manager._daily_reset_time is not None

    @pytest.mark.asyncio
    async def test_track_trade_pnl_profit(self, risk_manager):
        """수익 거래 PnL 추적"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(100.0)

        assert risk_manager._daily_pnl == 100.0
        assert risk_manager._total_trades == 1
        assert risk_manager._winning_trades == 1
        assert risk_manager._losing_trades == 0

    @pytest.mark.asyncio
    async def test_track_trade_pnl_loss(self, risk_manager):
        """손실 거래 PnL 추적"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-50.0)

        assert risk_manager._daily_pnl == -50.0
        assert risk_manager._total_trades == 1
        assert risk_manager._winning_trades == 0
        assert risk_manager._losing_trades == 1

    @pytest.mark.asyncio
    async def test_track_multiple_trades(self, risk_manager):
        """여러 거래 PnL 누적"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(100.0)
        await risk_manager.track_trade_pnl(-50.0)
        await risk_manager.track_trade_pnl(75.0)

        assert risk_manager._daily_pnl == 125.0
        assert risk_manager._total_trades == 3
        assert risk_manager._winning_trades == 2
        assert risk_manager._losing_trades == 1

    @pytest.mark.asyncio
    async def test_should_halt_trading_no_halt(self, risk_manager):
        """일일 손실 한도 미달 - 중단 안 함"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-100.0)  # -1%

        halt, reason = await risk_manager.should_halt_trading()

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_should_halt_trading_halt(self, risk_manager):
        """일일 손실 한도 도달 - 중단"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-500.0)  # -5%

        halt, reason = await risk_manager.should_halt_trading()

        assert halt is True
        assert "일일 손실 한도" in reason
        assert "5.00%" in reason

    @pytest.mark.asyncio
    async def test_should_halt_trading_exceed(self, risk_manager):
        """일일 손실 한도 초과 - 중단"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-800.0)  # -8%

        halt, reason = await risk_manager.should_halt_trading()

        assert halt is True
        assert "일일 손실 한도" in reason

    @pytest.mark.asyncio
    async def test_should_halt_trading_profit_no_halt(self, risk_manager):
        """수익 상태에서는 중단 안 함"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(500.0)  # +5%

        halt, reason = await risk_manager.should_halt_trading()

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_get_daily_pnl_pct(self, risk_manager):
        """일일 PnL 비율 계산"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-250.0)

        pnl_pct = risk_manager.get_daily_pnl_pct()

        assert pnl_pct == pytest.approx(-0.025, rel=0.01)  # -2.5%


class TestConsecutiveLosses:
    """Phase 5.3: 연속 손실 카운터 테스트"""

    @pytest.mark.asyncio
    async def test_track_trade_result_win(self, risk_manager):
        """승리 시 연속 손실 카운터 리셋"""
        risk_manager._consecutive_losses = 2
        await risk_manager.track_trade_result(is_win=True)

        assert risk_manager._consecutive_losses == 0

    @pytest.mark.asyncio
    async def test_track_trade_result_loss(self, risk_manager):
        """손실 시 연속 손실 카운터 증가"""
        await risk_manager.track_trade_result(is_win=False)

        assert risk_manager._consecutive_losses == 1

    @pytest.mark.asyncio
    async def test_consecutive_losses_cooldown_trigger(self, risk_manager):
        """연속 손실 한도 도달 시 쿨다운 시작"""
        for _ in range(3):
            await risk_manager.track_trade_result(is_win=False)

        assert risk_manager._consecutive_losses == 3
        assert risk_manager._cooldown_until is not None

    @pytest.mark.asyncio
    async def test_is_in_cooldown_true(self, risk_manager):
        """쿨다운 중 확인"""
        # 쿨다운 설정 (30분 후)
        risk_manager._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        is_cooldown = await risk_manager.is_in_cooldown()

        assert is_cooldown is True

    @pytest.mark.asyncio
    async def test_is_in_cooldown_false_not_set(self, risk_manager):
        """쿨다운 미설정 시 False"""
        is_cooldown = await risk_manager.is_in_cooldown()

        assert is_cooldown is False

    @pytest.mark.asyncio
    async def test_is_in_cooldown_false_expired(self, risk_manager):
        """쿨다운 만료 시 False"""
        # 쿨다운 만료 (과거 시간)
        risk_manager._cooldown_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        risk_manager._consecutive_losses = 3

        is_cooldown = await risk_manager.is_in_cooldown()

        assert is_cooldown is False
        # 쿨다운 종료 시 리셋
        assert risk_manager._cooldown_until is None
        assert risk_manager._consecutive_losses == 0

    @pytest.mark.asyncio
    async def test_reset_consecutive_losses(self, risk_manager):
        """연속 손실 카운터 수동 리셋"""
        risk_manager._consecutive_losses = 5
        risk_manager._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=30)

        risk_manager.reset_consecutive_losses()

        assert risk_manager._consecutive_losses == 0
        assert risk_manager._cooldown_until is None


class TestDrawdownManagement:
    """드로다운 관리 테스트"""

    @pytest.mark.asyncio
    async def test_update_balance_peak(self, risk_manager):
        """Peak balance 업데이트"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.update_balance(11000.0)

        assert risk_manager._peak_balance == 11000.0

    @pytest.mark.asyncio
    async def test_update_balance_drawdown(self, risk_manager):
        """드로다운 계산"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.update_balance(11000.0)  # Peak 설정
        await risk_manager.update_balance(9900.0)   # 10% 드로다운

        assert risk_manager._peak_balance == 11000.0
        assert risk_manager._current_drawdown == pytest.approx(0.10, rel=0.01)

    @pytest.mark.asyncio
    async def test_check_max_drawdown_no_breach(self, risk_manager):
        """드로다운 한도 미달"""
        await risk_manager.reset_daily_stats(10000.0)
        risk_manager._peak_balance = 10000.0
        risk_manager._current_drawdown = 0.05  # 5%

        breach, reason = await risk_manager.check_max_drawdown()

        assert breach is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_check_max_drawdown_breach(self, risk_manager):
        """드로다운 한도 도달"""
        risk_manager._current_drawdown = 0.12  # 12%

        breach, reason = await risk_manager.check_max_drawdown()

        assert breach is True
        assert "드로다운" in reason


class TestShouldSkipTrade:
    """통합 거래 스킵 체크 테스트"""

    @pytest.mark.asyncio
    async def test_should_skip_trade_no_skip(self, risk_manager):
        """정상 상태 - 스킵 안 함"""
        await risk_manager.reset_daily_stats(10000.0)

        should_skip, reason = await risk_manager.should_skip_trade()

        assert should_skip is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_should_skip_trade_cooldown(self, risk_manager):
        """쿨다운 중 스킵"""
        await risk_manager.reset_daily_stats(10000.0)
        risk_manager._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        should_skip, reason = await risk_manager.should_skip_trade()

        assert should_skip is True
        assert "쿨다운" in reason

    @pytest.mark.asyncio
    async def test_should_skip_trade_daily_loss(self, risk_manager):
        """일일 손실 한도 도달 시 스킵"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-600.0)  # -6%

        should_skip, reason = await risk_manager.should_skip_trade()

        assert should_skip is True
        assert "일일 손실" in reason

    @pytest.mark.asyncio
    async def test_should_skip_trade_max_drawdown(self, risk_manager):
        """드로다운 한도 도달 시 스킵"""
        await risk_manager.reset_daily_stats(10000.0)
        risk_manager._current_drawdown = 0.15  # 15%

        should_skip, reason = await risk_manager.should_skip_trade()

        assert should_skip is True
        assert "드로다운" in reason


class TestGetStats:
    """통계 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats(self, risk_manager):
        """전체 통계 조회"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(100.0)
        await risk_manager.track_trade_result(is_win=True)
        await risk_manager.track_trade_pnl(-50.0)
        await risk_manager.track_trade_result(is_win=False)

        stats = risk_manager.get_stats()

        assert stats["daily_pnl"] == 50.0
        assert stats["daily_start_balance"] == 10000.0
        assert stats["consecutive_losses"] == 1
        assert stats["total_trades"] == 2
        assert stats["winning_trades"] == 1
        assert stats["losing_trades"] == 1
        assert stats["win_rate"] == 0.5
        assert stats["max_daily_loss_pct"] == 0.05
        assert stats["max_consecutive_losses"] == 3

    def test_get_consecutive_losses(self, risk_manager):
        """연속 손실 횟수 조회"""
        risk_manager._consecutive_losses = 2

        assert risk_manager.get_consecutive_losses() == 2

    def test_get_current_drawdown(self, risk_manager):
        """현재 드로다운 조회"""
        risk_manager._current_drawdown = 0.08

        assert risk_manager.get_current_drawdown() == 0.08
