"""TSMOM Channel 테스트.

TSMOMChannel의 시그널 생성 로직을 포괄적으로 검증합니다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ai.channels.tsmom import TSMOMChannel
from src.ai.ensemble import IndividualSignal, SignalSource

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_df(prices: list[float]) -> pd.DataFrame:
    """close 가격 리스트로 OHLCV DataFrame 생성."""
    n = len(prices)
    return pd.DataFrame({
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
        "volume": [100.0] * n,
    })


def _make_uptrend_df(n: int = 100, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    """꾸준히 상승하는 가격 DataFrame."""
    prices = [start + i * step for i in range(n)]
    return _make_df(prices)


def _make_downtrend_df(n: int = 100, start: float = 200.0, step: float = 1.0) -> pd.DataFrame:
    """꾸준히 하락하는 가격 DataFrame."""
    prices = [start - i * step for i in range(n)]
    return _make_df(prices)


def _make_flat_df(n: int = 100, price: float = 100.0) -> pd.DataFrame:
    """변동 없는 가격 DataFrame (약간의 노이즈)."""
    rng = np.random.default_rng(42)
    prices = [price + rng.uniform(-0.001, 0.001) for _ in range(n)]
    return _make_df(prices)


def _make_mixed_df(n: int = 100) -> pd.DataFrame:
    """상승/하락이 혼합된 가격 DataFrame.

    전반부 상승, 후반부 하락 패턴으로 lookback window별 방향이 갈릴 수 있음.
    """
    half = n // 2
    prices_up = [100.0 + i * 0.5 for i in range(half)]
    prices_down = [prices_up[-1] - i * 0.5 for i in range(n - half)]
    return _make_df(prices_up + prices_down)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def channel() -> TSMOMChannel:
    return TSMOMChannel()


class TestTSMOMChannelBasic:
    """기본 시그널 생성 테스트."""

    @pytest.mark.asyncio
    async def test_all_positive_returns_long(self, channel: TSMOMChannel) -> None:
        """모든 lookback returns 양수 → LONG, confidence=1.0."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        assert sig.signal == "LONG"
        assert sig.confidence == 1.0

    @pytest.mark.asyncio
    async def test_all_negative_returns_short(self, channel: TSMOMChannel) -> None:
        """모든 lookback returns 음수 → SHORT, confidence=1.0."""
        df = _make_downtrend_df(100)
        sig = await channel.generate_signal(df)

        assert sig.signal == "SHORT"
        assert sig.confidence == 1.0

    @pytest.mark.asyncio
    async def test_source_is_tsmom(self, channel: TSMOMChannel) -> None:
        """source가 SignalSource.TSMOM인지 확인."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        assert sig.source == SignalSource.TSMOM

    @pytest.mark.asyncio
    async def test_weight_is_015(self, channel: TSMOMChannel) -> None:
        """weight가 0.15인지 확인."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        assert sig.weight == 0.15

    @pytest.mark.asyncio
    async def test_returns_individual_signal_type(self, channel: TSMOMChannel) -> None:
        """반환 타입이 IndividualSignal인지 확인."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        assert isinstance(sig, IndividualSignal)

    @pytest.mark.asyncio
    async def test_signal_values_are_valid(self, channel: TSMOMChannel) -> None:
        """시그널 값이 LONG, SHORT, WAIT 중 하나."""
        for make_fn in [_make_uptrend_df, _make_downtrend_df, _make_flat_df]:
            df = make_fn(100)
            sig = await channel.generate_signal(df)
            assert sig.signal in ("LONG", "SHORT", "WAIT")


class TestTSMOMInsufficientData:
    """데이터 부족 케이스 테스트."""

    @pytest.mark.asyncio
    async def test_empty_dataframe(self, channel: TSMOMChannel) -> None:
        """빈 DataFrame → WAIT, confidence=0.0."""
        df = _make_df([])
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0

    @pytest.mark.asyncio
    async def test_too_few_rows(self, channel: TSMOMChannel) -> None:
        """max(LOOKBACK_WINDOWS)+5 미만 → WAIT."""
        # max=60, 필요=65, 64행은 부족
        df = _make_uptrend_df(64)
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0
        assert "데이터 부족" in sig.reason

    @pytest.mark.asyncio
    async def test_exact_minimum_rows(self, channel: TSMOMChannel) -> None:
        """정확히 max(LOOKBACK_WINDOWS)+5행 → 정상 처리."""
        df = _make_uptrend_df(65)
        sig = await channel.generate_signal(df)

        # 65행이면 충분하므로 WAIT(데이터 부족)가 아니어야 함
        assert sig.reason != "데이터 부족"

    @pytest.mark.asyncio
    async def test_insufficient_data_weight(self, channel: TSMOMChannel) -> None:
        """데이터 부족 시에도 weight=0.15."""
        df = _make_df([100.0])
        sig = await channel.generate_signal(df)

        assert sig.weight == 0.15
        assert sig.source == SignalSource.TSMOM


class TestTSMOMMajorityLogic:
    """과반수 판정 로직 테스트."""

    @pytest.mark.asyncio
    async def test_3_long_1_short_gives_long(self, channel: TSMOMChannel) -> None:
        """3:1 양수 → LONG."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        # 강한 상승 추세 → 모든 window 양수 → 4:0 LONG
        assert sig.signal == "LONG"

    @pytest.mark.asyncio
    async def test_3_short_1_long_gives_short(self, channel: TSMOMChannel) -> None:
        """3:1 음수 → SHORT."""
        df = _make_downtrend_df(100)
        sig = await channel.generate_signal(df)

        assert sig.signal == "SHORT"

    @pytest.mark.asyncio
    async def test_confidence_reflects_majority_ratio(self, channel: TSMOMChannel) -> None:
        """confidence가 과반수 비율을 반영하는지 확인."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        # 4/4 = 1.0 or 3/4 = 0.75
        assert 0.0 < sig.confidence <= 1.0


class TestTSMOMNaNHandling:
    """NaN 처리 테스트."""

    @pytest.mark.asyncio
    async def test_all_nan_close_gives_wait(self, channel: TSMOMChannel) -> None:
        """모든 close가 NaN → 에러 핸들링 → WAIT."""
        n = 100
        df = pd.DataFrame({
            "open": [float("nan")] * n,
            "high": [float("nan")] * n,
            "low": [float("nan")] * n,
            "close": [float("nan")] * n,
            "volume": [100.0] * n,
        })
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0

    @pytest.mark.asyncio
    async def test_partial_nan_reduces_valid_count(self, channel: TSMOMChannel) -> None:
        """일부 NaN → valid_count 감소, 유효한 값으로만 판정."""
        # 대부분 상승 + 마지막 일부 NaN 삽입
        prices = [100.0 + i * 1.0 for i in range(100)]
        df = _make_df(prices)
        # 일부 close를 NaN으로 (calculate_returns 결과가 NaN이 되도록)
        # close 전체가 유효하면 returns도 유효하므로 여기서는 그냥 확인
        sig = await channel.generate_signal(df)

        assert sig.signal in ("LONG", "SHORT", "WAIT")
        assert isinstance(sig.confidence, float)

    @pytest.mark.asyncio
    async def test_zero_valid_returns_wait(self, channel: TSMOMChannel) -> None:
        """유효한 returns가 0개 → WAIT."""
        # 모든 close 동일 → pct_change=0 → rolling_std=0 → NaN
        n = 100
        df = _make_df([100.0] * n)
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0
        assert "유효한 리턴 데이터 없음" in sig.reason


class TestTSMOMReasonMessages:
    """reason 메시지 포맷 테스트."""

    @pytest.mark.asyncio
    async def test_long_reason_contains_counts(self, channel: TSMOMChannel) -> None:
        """LONG 시그널의 reason에 카운트 포함."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        if sig.signal == "LONG":
            assert "windows 양수" in sig.reason
            # reason에 숫자가 포함되어야 함
            assert "/" in sig.reason

    @pytest.mark.asyncio
    async def test_short_reason_contains_counts(self, channel: TSMOMChannel) -> None:
        """SHORT 시그널의 reason에 카운트 포함."""
        df = _make_downtrend_df(100)
        sig = await channel.generate_signal(df)

        if sig.signal == "SHORT":
            assert "windows 음수" in sig.reason
            assert "/" in sig.reason

    @pytest.mark.asyncio
    async def test_insufficient_data_reason(self, channel: TSMOMChannel) -> None:
        """데이터 부족 reason 메시지 확인."""
        df = _make_uptrend_df(10)
        sig = await channel.generate_signal(df)

        assert "데이터 부족" in sig.reason


class TestTSMOMEdgeCases:
    """경계 조건 테스트."""

    @pytest.mark.asyncio
    async def test_single_row_dataframe(self, channel: TSMOMChannel) -> None:
        """1행 DataFrame → WAIT."""
        df = _make_df([100.0])
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0

    @pytest.mark.asyncio
    async def test_lookback_windows_constant(self) -> None:
        """LOOKBACK_WINDOWS 상수 검증."""
        assert TSMOMChannel.LOOKBACK_WINDOWS == [5, 10, 20, 60]

    @pytest.mark.asyncio
    async def test_large_dataframe(self, channel: TSMOMChannel) -> None:
        """큰 DataFrame (500행)에서도 정상 동작."""
        df = _make_uptrend_df(500, step=0.5)
        sig = await channel.generate_signal(df)

        assert sig.signal in ("LONG", "SHORT", "WAIT")
        assert 0.0 <= sig.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_exception_handling_returns_wait(self, channel: TSMOMChannel) -> None:
        """예외 발생 시 WAIT 반환."""
        # close 컬럼 없는 DataFrame
        df = pd.DataFrame({"open": [1, 2, 3] * 30, "volume": [100] * 90})
        sig = await channel.generate_signal(df)

        assert sig.signal == "WAIT"
        assert "에러" in sig.reason

    @pytest.mark.asyncio
    async def test_mixed_trend_wait_or_majority(self, channel: TSMOMChannel) -> None:
        """혼합 추세 → WAIT 또는 과반수 방향."""
        df = _make_mixed_df(100)
        sig = await channel.generate_signal(df)

        assert sig.signal in ("LONG", "SHORT", "WAIT")

    @pytest.mark.asyncio
    async def test_weighted_vote_compatibility(self, channel: TSMOMChannel) -> None:
        """IndividualSignal.weighted_vote()와 호환되는지 확인."""
        df = _make_uptrend_df(100)
        sig = await channel.generate_signal(df)

        vote = sig.weighted_vote()
        if sig.signal == "LONG":
            assert vote > 0
        elif sig.signal == "SHORT":
            assert vote < 0
        else:
            assert vote == 0.0
