"""
Tests for RiskManager

Phase 5.2: 일일 손실 한도
Phase 5.3: 연속 손실 카운터
"""
from datetime import datetime, timedelta, timezone

import pytest

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

class TestDailyRiskReset:
    """check_and_reset_if_new_day 테스트"""

    @pytest.mark.asyncio
    async def test_first_call_resets(self):
        """최초 호출 시 리셋 수행"""
        rm = RiskManager()
        assert rm._daily_reset_time is None

        result = await rm.check_and_reset_if_new_day(5000.0)

        assert result is True
        assert rm._daily_start_balance == 5000.0
        assert rm._daily_reset_time is not None

    @pytest.mark.asyncio
    async def test_same_day_no_reset(self):
        """같은 날 재호출 시 리셋 안 함"""
        rm = RiskManager()
        await rm.reset_daily_stats(5000.0)

        # PnL을 일부 기록
        await rm.track_trade_pnl(-50.0)
        assert rm._daily_pnl == -50.0

        result = await rm.check_and_reset_if_new_day(4950.0)

        assert result is False
        # PnL이 리셋되지 않아야 함
        assert rm._daily_pnl == -50.0

    @pytest.mark.asyncio
    async def test_midnight_crossing_resets(self):
        """UTC 자정 경과 시 리셋 수행"""
        rm = RiskManager()
        await rm.reset_daily_stats(5000.0)

        # 리셋 시간을 어제로 조작
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        rm._daily_reset_time = yesterday

        # PnL 기록
        await rm.track_trade_pnl(-100.0)
        assert rm._daily_pnl == -100.0

        result = await rm.check_and_reset_if_new_day(4900.0)

        assert result is True
        assert rm._daily_pnl == 0.0
        assert rm._daily_start_balance == 4900.0

class TestUnrealizedPnlIntegration:
    """미실현 PnL 통합 테스트"""

    @pytest.mark.asyncio
    async def test_halt_with_unrealized_loss_triggers(self, risk_manager):
        """실현 손실 + 미실현 손실 합산으로 한도 초과"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-200.0)  # -2% 실현 손실

        # 미실현 손실 -300 추가 → 합산 500 = 5% → 한도 도달
        halt, reason = await risk_manager.should_halt_trading(unrealized_pnl=-300.0)

        assert halt is True
        assert "일일 손실 한도" in reason

    @pytest.mark.asyncio
    async def test_halt_without_unrealized_backward_compatible(self, risk_manager):
        """unrealized_pnl=0 (기본값)일 때 기존 동작 유지"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-200.0)  # -2%

        halt, reason = await risk_manager.should_halt_trading()

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_halt_positive_unrealized_ignored(self, risk_manager):
        """미실현 이익은 손실 계산에 포함되지 않음"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-300.0)  # -3% 실현 손실

        # 미실현 이익 +500은 무시됨 → 실현 손실만 3%
        halt, reason = await risk_manager.should_halt_trading(unrealized_pnl=500.0)

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_skip_trade_forwards_unrealized_pnl(self, risk_manager):
        """should_skip_trade가 unrealized_pnl을 should_halt_trading에 전달"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-200.0)  # -2% 실현

        # 미실현 -300 → 합산 500 = 5% → 스킵
        should_skip, reason = await risk_manager.should_skip_trade(unrealized_pnl=-300.0)

        assert should_skip is True
        assert "일일 손실" in reason

    @pytest.mark.asyncio
    async def test_skip_trade_no_unrealized_backward_compatible(self, risk_manager):
        """should_skip_trade 기본값(0) 시 기존 동작 유지"""
        await risk_manager.reset_daily_stats(10000.0)
        await risk_manager.track_trade_pnl(-200.0)  # -2%

        should_skip, reason = await risk_manager.should_skip_trade()

        assert should_skip is False
        assert reason == ""


# =============================================================================
# Issue 8: Daily Loss Formula Bug Fix
# =============================================================================


class TestDailyLossFormulaBugFix:
    """Issue 8: daily_pnl이 양수(이익)일 때 손실로 잘못 처리되는 버그 수정"""

    @pytest.mark.asyncio
    async def test_positive_pnl_not_treated_as_loss(self):
        """양수 PnL은 손실로 계산되지 않아야 함"""
        rm = RiskManager(max_daily_loss_pct=0.05)
        await rm.reset_daily_stats(10000.0)

        # +300 이익 기록
        await rm.track_trade_pnl(300.0)

        # 미실현 손실 -100
        halt, reason = await rm.should_halt_trading(unrealized_pnl=-100.0)

        # net_pnl = 300 + (-100) = 200 > 0 -> 손실 아님 -> halt=False
        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_net_pnl_negative_triggers_halt(self):
        """실현+미실현 합산이 음수이고 한도 초과 시 halt"""
        rm = RiskManager(max_daily_loss_pct=0.05)
        await rm.reset_daily_stats(10000.0)

        # -300 손실 기록
        await rm.track_trade_pnl(-300.0)

        # 미실현 손실 -300 -> net_pnl = -300 + (-300) = -600 = 6%
        halt, reason = await rm.should_halt_trading(unrealized_pnl=-300.0)

        assert halt is True
        assert "일일 손실 한도" in reason

    @pytest.mark.asyncio
    async def test_net_pnl_positive_no_halt(self):
        """합산이 양수면 halt 안 함 (이전 버그: abs로 이익도 손실 처리)"""
        rm = RiskManager(max_daily_loss_pct=0.05)
        await rm.reset_daily_stats(10000.0)

        # +1000 큰 이익 기록
        await rm.track_trade_pnl(1000.0)

        # 미실현 손실 -200 -> net_pnl = 1000 + (-200) = 800 > 0
        halt, reason = await rm.should_halt_trading(unrealized_pnl=-200.0)

        # BUG 수정 전: abs(1000) + abs(-200) = 1200 = 12% -> halt!
        # BUG 수정 후: net_pnl = 800 > 0 -> no halt
        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_only_unrealized_loss_under_limit(self):
        """실현 PnL=0, 미실현 손실만 한도 미만"""
        rm = RiskManager(max_daily_loss_pct=0.05)
        await rm.reset_daily_stats(10000.0)

        # 미실현 손실 -300 -> net_pnl = -300 = 3% < 5%
        halt, reason = await rm.should_halt_trading(unrealized_pnl=-300.0)

        assert halt is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_only_unrealized_loss_at_limit(self):
        """실현 PnL=0, 미실현 손실만 한도 도달"""
        rm = RiskManager(max_daily_loss_pct=0.05)
        await rm.reset_daily_stats(10000.0)

        # 미실현 손실 -500 -> net_pnl = -500 = 5% >= 5%
        halt, reason = await rm.should_halt_trading(unrealized_pnl=-500.0)

        assert halt is True
        assert "일일 손실 한도" in reason


# =============================================================================
# Issue 11: Carry Over Unrealized Losses on Daily Reset
# =============================================================================


class TestCarryOverUnrealizedLossesOnReset:
    """Issue 11: 일일 리셋 시 미실현 손실 이월"""

    @pytest.mark.asyncio
    async def test_reset_with_unrealized_loss_carries_over(self):
        """미실현 손실 있는 상태에서 리셋 -> daily_pnl에 이월"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(-100.0)

        # Reset with unrealized loss
        await rm.reset_daily_stats(9500.0, unrealized_pnl=-200.0)

        # daily_pnl should carry over the unrealized loss
        assert rm._daily_pnl == -200.0
        assert rm._daily_start_balance == 9500.0

    @pytest.mark.asyncio
    async def test_reset_with_unrealized_profit_no_carry(self):
        """미실현 이익 있는 상태에서 리셋 -> daily_pnl=0"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)

        # Reset with unrealized profit
        await rm.reset_daily_stats(10500.0, unrealized_pnl=300.0)

        # Should not carry over profits
        assert rm._daily_pnl == 0.0

    @pytest.mark.asyncio
    async def test_reset_with_zero_unrealized(self):
        """미실현 PnL=0 -> 기존 동작(daily_pnl=0)"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(-50.0)

        # Reset without unrealized PnL
        await rm.reset_daily_stats(9950.0, unrealized_pnl=0.0)

        assert rm._daily_pnl == 0.0

    @pytest.mark.asyncio
    async def test_check_and_reset_if_new_day_carries_loss(self):
        """check_and_reset_if_new_day에서도 미실현 손실 이월"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)

        # Set reset time to yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        rm._daily_reset_time = yesterday

        result = await rm.check_and_reset_if_new_day(
            9800.0, unrealized_pnl=-150.0
        )

        assert result is True
        assert rm._daily_pnl == -150.0
        assert rm._daily_start_balance == 9800.0

    @pytest.mark.asyncio
    async def test_check_and_reset_same_day_no_carry(self):
        """같은 날 재호출 시 이월 없음"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(-50.0)

        result = await rm.check_and_reset_if_new_day(
            9950.0, unrealized_pnl=-100.0
        )

        assert result is False
        # PnL should remain as-is (no reset happened)
        assert rm._daily_pnl == -50.0

    @pytest.mark.asyncio
    async def test_backward_compatible_without_unrealized_pnl(self):
        """unrealized_pnl 인자 없이 호출 시 기존 동작 유지"""
        rm = RiskManager()
        await rm.reset_daily_stats(10000.0)
        await rm.track_trade_pnl(-100.0)

        # Reset without unrealized_pnl parameter (default=0.0)
        await rm.reset_daily_stats(9900.0)

        assert rm._daily_pnl == 0.0
