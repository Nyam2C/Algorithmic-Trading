"""Half-Kelly Transition 테스트.

APEX-V Phase 2 Step 1: Quarter-Kelly → Half-Kelly 전환 로직.
"""
from __future__ import annotations

from src.trading.kelly_sizer import (
    HALF_KELLY_DEFAULT_MIN_TRADES,
    HALF_KELLY_FRACTION,
    HALF_KELLY_MAX_CONSECUTIVE_LOSSES,
    HALF_KELLY_MIN_PROFIT_FACTOR,
    HALF_KELLY_MIN_WIN_RATE,
    KellySizer,
)


def _build_winning_trades(count: int, win_rate: float = 0.60) -> list[float]:
    """승률에 맞는 거래 목록 생성 (교차 배치로 연속 손실 방지)."""
    wins = int(count * win_rate)
    losses = count - wins
    # 교차 배치: 연속 손실이 5개 이상 생기지 않도록
    trades: list[float] = []
    w, lo = 0, 0
    for i in range(count):
        if w < wins and (lo >= losses or i % 3 != 2):
            trades.append(0.02)
            w += 1
        else:
            trades.append(-0.01)
            lo += 1
    return trades


class TestHalfKellyTransition:
    """Half-Kelly 전환 조건 테스트."""

    def test_half_kelly_disabled_by_default(self):
        """기본값은 Quarter-Kelly."""
        sizer = KellySizer()
        assert sizer._use_half_kelly is False
        assert sizer._half_kelly_active is False

    def test_half_kelly_not_active_when_disabled(self):
        """use_half_kelly=False면 항상 Quarter-Kelly."""
        sizer = KellySizer(use_half_kelly=False)
        trades = _build_winning_trades(60, win_rate=0.65)
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        result = sizer.calculate_kelly_size("strong_uptrend")
        assert result is not None
        assert sizer.half_kelly_active is False

    def test_half_kelly_activates_on_trending_regime(self):
        """TRENDING 레짐 + 조건 충족 시 Half-Kelly 활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        # 높은 승률, 좋은 profit factor
        trades = _build_winning_trades(30, win_rate=0.65)
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        result_half = sizer.calculate_kelly_size("strong_uptrend")
        assert result_half is not None
        assert sizer.half_kelly_active is True

        # 같은 조건에서 Quarter-Kelly
        sizer2 = KellySizer(use_half_kelly=False)
        for t in trades:
            sizer2.record_trade("strong_uptrend", t)
        result_quarter = sizer2.calculate_kelly_size("strong_uptrend")
        assert result_quarter is not None

        # Half-Kelly 결과가 Quarter-Kelly보다 커야 함
        assert result_half > result_quarter

    def test_half_kelly_rejected_on_ranging_regime(self):
        """RANGING 레짐에서는 Half-Kelly 비활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        trades = _build_winning_trades(30, win_rate=0.65)
        for t in trades:
            sizer.record_trade("ranging", t)

        sizer.calculate_kelly_size("ranging")
        assert sizer.half_kelly_active is False

    def test_half_kelly_rejected_low_win_rate(self):
        """승률 55% 미만이면 Half-Kelly 비활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        # 승률 50% → HALF_KELLY_MIN_WIN_RATE(0.55) 미만
        trades = _build_winning_trades(30, win_rate=0.50)
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        sizer.calculate_kelly_size("strong_uptrend")
        assert sizer.half_kelly_active is False

    def test_half_kelly_rejected_low_profit_factor(self):
        """Profit factor 1.5 미만이면 Half-Kelly 비활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        # 승률은 높지만 profit factor 낮음 (작은 이익, 큰 손실)
        trades = [0.005] * 18 + [-0.01] * 12  # win=60%, pf=0.75
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        sizer.calculate_kelly_size("strong_uptrend")
        assert sizer.half_kelly_active is False

    def test_half_kelly_rejected_insufficient_trades(self):
        """거래 수 부족 시 Half-Kelly 비활성화."""
        sizer = KellySizer(
            use_half_kelly=True,
            half_kelly_min_trades=HALF_KELLY_DEFAULT_MIN_TRADES,
        )
        # 20건만 기록 (Kelly 최소 충족, Half-Kelly 최소 미충족)
        trades = _build_winning_trades(25, win_rate=0.65)
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        sizer.calculate_kelly_size("strong_uptrend")
        assert sizer.half_kelly_active is False

    def test_half_kelly_rejected_consecutive_losses(self):
        """최근 5거래 연속 손실 시 Half-Kelly 비활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        # 좋은 거래 후 최근 5개 연속 손실
        good_trades = _build_winning_trades(25, win_rate=0.75)
        for t in good_trades:
            sizer.record_trade("strong_uptrend", t)
        # 최근 5개 연속 손실 추가
        for _ in range(HALF_KELLY_MAX_CONSECUTIVE_LOSSES):
            sizer.record_trade("strong_uptrend", -0.01)

        sizer.calculate_kelly_size("strong_uptrend")
        assert sizer.half_kelly_active is False

    def test_half_kelly_rollback_on_negative_kelly(self):
        """Kelly raw가 음수면 Half-Kelly 비활성화."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=20)
        # 대부분 손실 → kelly_raw 음수
        trades = [0.01] * 5 + [-0.02] * 20
        for t in trades:
            sizer.record_trade("strong_uptrend", t)

        result = sizer.calculate_kelly_size("strong_uptrend")
        assert result == sizer.min_size_pct
        assert sizer.half_kelly_active is False


class TestHalfKellyRedis:
    """Half-Kelly Redis 영속화 테스트."""

    def test_to_dict_includes_half_kelly_state(self):
        """to_dict에 half_kelly 상태 포함."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=30)
        data = sizer.to_dict()
        assert "half_kelly_active" in data
        assert "use_half_kelly" in data
        assert "half_kelly_min_trades" in data
        assert data["use_half_kelly"] is True
        assert data["half_kelly_min_trades"] == 30

    def test_from_dict_restores_half_kelly_state(self):
        """from_dict에서 half_kelly 상태 복원."""
        sizer = KellySizer(use_half_kelly=True, half_kelly_min_trades=30)
        trades = _build_winning_trades(40, win_rate=0.65)
        for t in trades:
            sizer.record_trade("strong_uptrend", t)
        sizer.calculate_kelly_size("strong_uptrend")

        data = sizer.to_dict()

        sizer2 = KellySizer()
        sizer2.from_dict(data)
        assert sizer2._half_kelly_active == sizer._half_kelly_active
        assert sizer2._use_half_kelly is True
        assert sizer2._half_kelly_min_trades == 30

    def test_from_dict_backward_compatible(self):
        """이전 버전 to_dict 데이터로도 from_dict 동작."""
        sizer = KellySizer()
        old_data = {
            "kelly_fraction": 0.25,
            "min_size_pct": 0.003,
            "max_size_pct": 0.02,
            "regime_trades": {},
        }
        sizer.from_dict(old_data)
        assert sizer._half_kelly_active is False


class TestHalfKellyConstants:
    """Half-Kelly 상수 테스트."""

    def test_fraction_values(self):
        assert HALF_KELLY_FRACTION == 0.50
        assert HALF_KELLY_MIN_WIN_RATE == 0.55
        assert HALF_KELLY_MIN_PROFIT_FACTOR == 1.5
        assert HALF_KELLY_DEFAULT_MIN_TRADES == 50
        assert HALF_KELLY_MAX_CONSECUTIVE_LOSSES == 5
