"""Microprice 순수 함수 단위 테스트."""
import pytest

from src.trading.microprice import (
    WAIT_CONFIG,
    calculate_limit_price,
    calculate_microprice,
    get_liquidity_tier,
)


class TestCalculateMicroprice:
    """calculate_microprice 테스트."""

    def test_equal_volumes(self):
        """매수/매도 볼륨 동일 → mid price."""
        result = calculate_microprice(99_990.0, 100_010.0, 10.0, 10.0)
        assert result == pytest.approx(100_000.0)

    def test_higher_bid_volume(self):
        """매수 볼륨 > 매도 볼륨 → ask 방향으로 치우침."""
        result = calculate_microprice(99_990.0, 100_010.0, 30.0, 10.0)
        assert result is not None
        # bid_vol 크면 microprice는 ask 쪽으로 이동
        mid = (99_990.0 + 100_010.0) / 2
        assert result > mid

    def test_higher_ask_volume(self):
        """매도 볼륨 > 매수 볼륨 → bid 방향으로 치우침."""
        result = calculate_microprice(99_990.0, 100_010.0, 10.0, 30.0)
        assert result is not None
        mid = (99_990.0 + 100_010.0) / 2
        assert result < mid

    def test_zero_bid_price(self):
        """bid가 0이면 None."""
        assert calculate_microprice(0, 100_000.0, 10.0, 10.0) is None

    def test_zero_ask_price(self):
        """ask가 0이면 None."""
        assert calculate_microprice(100_000.0, 0, 10.0, 10.0) is None

    def test_crossed_book(self):
        """bid >= ask (crossed book) → None."""
        assert calculate_microprice(100_010.0, 100_000.0, 10.0, 10.0) is None
        assert calculate_microprice(100_000.0, 100_000.0, 10.0, 10.0) is None

    def test_zero_volumes(self):
        """볼륨 합이 0이면 None."""
        assert calculate_microprice(99_990.0, 100_010.0, 0.0, 0.0) is None

    def test_negative_bid_price(self):
        """음수 bid → None."""
        assert calculate_microprice(-1.0, 100_000.0, 10.0, 10.0) is None


class TestCalculateLimitPrice:
    """calculate_limit_price 테스트."""

    def test_long_offset(self):
        """LONG: microprice - ATR * offset."""
        price = calculate_limit_price(100_000.0, "LONG", 50.0, 0.1)
        assert price == pytest.approx(99_995.0)

    def test_short_offset(self):
        """SHORT: microprice + ATR * offset."""
        price = calculate_limit_price(100_000.0, "SHORT", 50.0, 0.1)
        assert price == pytest.approx(100_005.0)

    def test_custom_offset_factor(self):
        """커스텀 offset_factor 적용."""
        price = calculate_limit_price(100_000.0, "LONG", 100.0, 0.2)
        assert price == pytest.approx(99_980.0)

    def test_rounding(self):
        """소수점 2자리 반올림."""
        price = calculate_limit_price(100_000.123, "LONG", 33.333, 0.1)
        assert price == round(100_000.123 - 33.333 * 0.1, 2)


class TestGetLiquidityTier:
    """get_liquidity_tier 테스트."""

    def test_high_tier(self):
        assert get_liquidity_tier(80.0) == "high"
        assert get_liquidity_tier(70.0) == "high"

    def test_medium_tier(self):
        assert get_liquidity_tier(50.0) == "medium"
        assert get_liquidity_tier(40.0) == "medium"

    def test_low_tier(self):
        assert get_liquidity_tier(30.0) == "low"
        assert get_liquidity_tier(0.0) == "low"

    def test_boundary_values(self):
        """경계값 테스트."""
        assert get_liquidity_tier(69.9) == "medium"
        assert get_liquidity_tier(39.9) == "low"


class TestWaitConfig:
    """WAIT_CONFIG 구조 테스트."""

    def test_all_tiers_present(self):
        assert set(WAIT_CONFIG.keys()) == {"high", "medium", "low"}

    def test_low_tier_no_market_fallback(self):
        """Low 유동성에서는 Market fallback 금지."""
        assert WAIT_CONFIG["low"]["allow_market_fallback"] is False

    def test_high_medium_allow_market(self):
        assert WAIT_CONFIG["high"]["allow_market_fallback"] is True
        assert WAIT_CONFIG["medium"]["allow_market_fallback"] is True

    def test_wait_seconds_ordering(self):
        """Low > High > Medium 대기시간."""
        assert WAIT_CONFIG["low"]["wait_seconds"] > WAIT_CONFIG["high"]["wait_seconds"]
        assert WAIT_CONFIG["high"]["wait_seconds"] > WAIT_CONFIG["medium"]["wait_seconds"]
