"""Tests for SessionAnalyzer — APEX-V Phase E."""
from datetime import datetime, timezone

import pytest

from src.backtest.engine import Trade
from src.backtest.session_analysis import (
    UNKNOWN_SESSION,
    SessionAnalyzer,
)


def _make_trade(
    hour: int | None = None,
    pnl: float = 10.0,
    entry_time: object | None = None,
) -> Trade:
    """특정 시간대의 Trade 생성.

    hour가 주어지면 UTC datetime 생성.
    entry_time이 주어지면 그대로 사용.
    """
    if entry_time is not None:
        et = entry_time
    elif hour is not None:
        et = datetime(2025, 6, 15, hour, 30, 0, tzinfo=timezone.utc)
    else:
        et = 0
    return Trade(
        entry_time=et,
        entry_price=100.0,
        side="LONG",
        quantity=1.0,
        exit_price=100.0 + pnl,
        pnl=pnl,
    )


class TestSessionAnalyzer:
    """SessionAnalyzer 핵심 테스트."""

    def test_empty_trades(self) -> None:
        """빈 거래 목록 -> 빈 결과."""
        analyzer = SessionAnalyzer()
        result = analyzer.analyze([])
        assert result.sessions == {}
        assert result.weak_sessions == []

    def test_classify_asia(self) -> None:
        """00-08 UTC -> ASIA 세션."""
        trades = [_make_trade(hour=3, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "ASIA" in result.sessions

    def test_classify_eu(self) -> None:
        """08-13 UTC -> EU 세션."""
        trades = [_make_trade(hour=10, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "EU" in result.sessions

    def test_classify_us(self) -> None:
        """13-21 UTC -> US 세션."""
        trades = [_make_trade(hour=16, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "US" in result.sessions

    def test_classify_deep_night(self) -> None:
        """21-24 UTC -> DEEP_NIGHT 세션."""
        trades = [_make_trade(hour=22, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "DEEP_NIGHT" in result.sessions

    def test_multiple_sessions(self) -> None:
        """여러 세션에 걸친 거래 분류."""
        trades = [
            _make_trade(hour=2, pnl=10.0),   # ASIA
            _make_trade(hour=9, pnl=-5.0),   # EU
            _make_trade(hour=15, pnl=20.0),  # US
            _make_trade(hour=23, pnl=-3.0),  # DEEP_NIGHT
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert len(result.sessions) == 4

    def test_weak_session_detection(self) -> None:
        """WR < 50% -> weak session."""
        trades = [
            # ASIA: 1 win, 3 losses -> 25% WR
            _make_trade(hour=1, pnl=10.0),
            _make_trade(hour=2, pnl=-5.0),
            _make_trade(hour=3, pnl=-5.0),
            _make_trade(hour=4, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "ASIA" in result.weak_sessions

    def test_strong_session_not_weak(self) -> None:
        """WR >= 50% -> weak session 아님."""
        trades = [
            _make_trade(hour=14, pnl=10.0),
            _make_trade(hour=15, pnl=10.0),
            _make_trade(hour=16, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert "US" not in result.weak_sessions

    def test_disable_recommendation(self) -> None:
        """WR < 50% -> DISABLE 권고."""
        trades = [
            _make_trade(hour=1, pnl=-5.0),
            _make_trade(hour=2, pnl=-5.0),
            _make_trade(hour=3, pnl=10.0),
            _make_trade(hour=4, pnl=-5.0),
            _make_trade(hour=5, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert result.sessions["ASIA"].recommendation == "DISABLE"

    def test_enable_recommendation(self) -> None:
        """WR >= 55% -> ENABLE 권고."""
        trades = [
            _make_trade(hour=14, pnl=10.0),
            _make_trade(hour=15, pnl=10.0),
            _make_trade(hour=16, pnl=10.0),
            _make_trade(hour=17, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert result.sessions["US"].recommendation == "ENABLE"

    def test_profit_factor(self) -> None:
        """Profit factor = 총 수익 / 총 손실."""
        trades = [
            _make_trade(hour=14, pnl=30.0),
            _make_trade(hour=15, pnl=-10.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert result.sessions["US"].profit_factor == pytest.approx(3.0)

    def test_profit_factor_no_losses(self) -> None:
        """손실 없으면 profit_factor = inf."""
        trades = [
            _make_trade(hour=14, pnl=10.0),
            _make_trade(hour=15, pnl=20.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert result.sessions["US"].profit_factor == float("inf")

    def test_integer_timestamp_unknown(self) -> None:
        """정수 타임스탬프 -> UNKNOWN 세션."""
        trades = [_make_trade(entry_time=1234567890, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert UNKNOWN_SESSION in result.sessions

    def test_string_timestamp_unknown(self) -> None:
        """문자열 타임스탬프 -> UNKNOWN 세션."""
        trades = [_make_trade(entry_time="2025-01-01", pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert UNKNOWN_SESSION in result.sessions

    def test_unknown_not_in_weak_sessions(self) -> None:
        """UNKNOWN 세션은 weak_sessions에 포함되지 않음."""
        trades = [
            _make_trade(entry_time=123, pnl=-5.0),
            _make_trade(entry_time=456, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert UNKNOWN_SESSION not in result.weak_sessions

    def test_win_rate_calculation(self) -> None:
        """승률 정확성 검증."""
        trades = [
            _make_trade(hour=10, pnl=10.0),
            _make_trade(hour=11, pnl=10.0),
            _make_trade(hour=12, pnl=-5.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        stats = result.sessions["EU"]
        assert stats.win_rate == pytest.approx(66.67, abs=0.01)
        assert stats.winning_trades == 2
        assert stats.total_trades == 3

    def test_avg_pnl(self) -> None:
        """평균 PnL 계산."""
        trades = [
            _make_trade(hour=10, pnl=30.0),
            _make_trade(hour=11, pnl=-10.0),
        ]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        assert result.sessions["EU"].avg_pnl == pytest.approx(10.0)

    def test_to_dict(self) -> None:
        """to_dict 구조 검증."""
        trades = [_make_trade(hour=3, pnl=10.0)]
        analyzer = SessionAnalyzer()
        result = analyzer.analyze(trades)
        d = result.to_dict()
        assert "sessions" in d
        assert "weak_sessions" in d
        assert "ASIA" in d["sessions"]
        assert "win_rate" in d["sessions"]["ASIA"]
