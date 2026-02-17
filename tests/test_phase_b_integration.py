"""Phase B 통합 테스트.

bot_instance.py의 _fetch_sentiment_data(), _get_klines_df(), MTI 게이트 검증.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bot(
    use_funding: bool = False,
    use_leverage: bool = False,
    use_smart_money: bool = False,
    use_tsmom: bool = False,
    use_ensemble: bool = False,
) -> BotInstance:
    """최소 BotInstance 생성."""
    config = BotConfig(
        bot_name="test-bot",
        symbol="BTCUSDT",
        risk_level="low",
        use_funding_basis_channel=use_funding,
        use_leverage_topology_channel=use_leverage,
        use_smart_money_channel=use_smart_money,
        use_tsmom_channel=use_tsmom,
        use_ensemble=use_ensemble,
    )
    bot = BotInstance(
        config=config,
        binance_api_key="test",
        binance_secret_key="test",
    )
    return bot


def _make_binance_mock(
    funding_rate: float = 0.05,
    long_short_ratio: float = 1.5,
    open_interest: float = 50000.0,
) -> AsyncMock:
    """Binance 클라이언트 mock."""
    mock = AsyncMock()
    mock.get_market_sentiment = AsyncMock(return_value={
        "funding_rate": funding_rate,
        "long_short_ratio": long_short_ratio,
        "open_interest": open_interest,
    })
    return mock


def _make_redis_mock() -> AsyncMock:
    """Redis 상태 관리자 mock."""
    mock = AsyncMock()
    mock.save_oi_snapshot = AsyncMock()
    mock.save_ls_snapshot = AsyncMock()
    mock.load_oi_history = AsyncMock(return_value=[
        {"oi": 48000, "price": 49000},
        {"oi": 49000, "price": 49500},
        {"oi": 50000, "price": 50000},
    ])
    mock.load_ls_history = AsyncMock(return_value=[
        {"ratio": 1.4, "price": 49000},
        {"ratio": 1.5, "price": 50000},
    ])
    return mock


# ---------------------------------------------------------------------------
# 1. _fetch_sentiment_data() — 정상 데이터 반환
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_data_returns_correct_data() -> None:
    """Binance mock에서 심리 데이터를 올바르게 수집."""
    bot = _make_bot(use_funding=True)
    bot._binance_client = _make_binance_mock(funding_rate=0.05)
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is not None
    assert result["long_short_ratio"] == 1.5
    assert result["open_interest"] == 50000.0
    assert result["current_price"] == 50000.0


# ---------------------------------------------------------------------------
# 2. _fetch_sentiment_data() — 채널 미활성화 시 None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_data_none_when_channels_disabled() -> None:
    """모든 채널 비활성화 시 None 반환."""
    bot = _make_bot()  # 모든 채널 False
    bot._binance_client = _make_binance_mock()

    result = await bot._fetch_sentiment_data()

    assert result is None


# ---------------------------------------------------------------------------
# 3. _fetch_sentiment_data() — funding_rate 단위 변환 (/100)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_funding_rate_conversion() -> None:
    """Binance의 percentage FR을 raw decimal로 변환 (/100)."""
    bot = _make_bot(use_funding=True)
    # Binance returns 0.05 meaning 0.05%
    bot._binance_client = _make_binance_mock(funding_rate=0.05)
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is not None
    # 0.05 / 100 = 0.0005 (raw decimal)
    assert abs(result["funding_rate"] - 0.0005) < 1e-8


# ---------------------------------------------------------------------------
# 4. _fetch_sentiment_data() — API 실패 시 None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_data_api_failure_returns_none() -> None:
    """API 호출 실패 시 None 반환."""
    bot = _make_bot(use_funding=True)
    mock_client = AsyncMock()
    mock_client.get_market_sentiment = AsyncMock(
        side_effect=ConnectionError("API down")
    )
    bot._binance_client = mock_client
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is None


# ---------------------------------------------------------------------------
# 5. _fetch_sentiment_data() — Redis OI/LS 스냅샷 저장 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_saves_redis_snapshots() -> None:
    """Redis에 OI/LS 스냅샷 저장 호출 확인."""
    bot = _make_bot(use_funding=True)
    bot._binance_client = _make_binance_mock(
        funding_rate=0.05, open_interest=50000.0, long_short_ratio=1.5
    )
    redis_mock = _make_redis_mock()
    bot._redis_state_manager = redis_mock
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is not None
    redis_mock.save_oi_snapshot.assert_called_once_with(
        "BTCUSDT", 50000.0, 50000.0
    )
    redis_mock.save_ls_snapshot.assert_called_once_with(
        "BTCUSDT", 1.5, 50000.0
    )


# ---------------------------------------------------------------------------
# 6. _get_klines_df() — 변환 정상 동작
# ---------------------------------------------------------------------------


def test_get_klines_df_conversion() -> None:
    """klines 배열을 DataFrame으로 변환."""
    bot = _make_bot(use_tsmom=True)

    klines = [
        [1000, "100", "105", "95", "102", "1000",
         2000, "100000", "50", "500", "50000", "0"],
        [2000, "102", "107", "97", "104", "1100",
         3000, "110000", "55", "550", "55000", "0"],
    ]
    market_data = {"klines": klines}

    df = bot._get_klines_df(market_data)

    assert df is not None
    assert len(df) == 2
    assert float(df["close"].iloc[0]) == 102.0
    assert float(df["close"].iloc[1]) == 104.0


# ---------------------------------------------------------------------------
# 7. _get_klines_df() — TSMOM 비활성화 시 None
# ---------------------------------------------------------------------------


def test_get_klines_df_none_when_tsmom_disabled() -> None:
    """TSMOM 비활성화 시 None 반환."""
    bot = _make_bot(use_tsmom=False)

    result = bot._get_klines_df({"klines": [[1, 2, 3]]})

    assert result is None


# ---------------------------------------------------------------------------
# 8. MTI 게이트 — STANDBY(<40) → WAIT 강제
# ---------------------------------------------------------------------------


def test_mti_gate_blocks_standby() -> None:
    """MTI STANDBY (<40) 시 시그널을 WAIT으로 강제."""
    bot = _make_bot()

    # atr_pct=0.1 (매우 낮음 → 30점), volume_ratio=0.2 (매우 낮음 → 20점)
    # 세션 점수는 시간대에 따라 다르지만, vol+vol_ratio가 낮으면 STANDBY
    indicators = {"atr_pct": 0.1, "volume_ratio": 0.2}

    with patch(
        "src.data.tradability.MarketTradabilityIndex"
    ) as MockMTI:
        mock_instance = MagicMock()
        mock_score = MagicMock()
        mock_score.is_tradable = False
        mock_score.total_score = 25.0
        mock_score.grade = "STANDBY"
        mock_score.reason = "변동성 부족, 거래량 부족"
        mock_instance.evaluate.return_value = mock_score
        MockMTI.return_value = mock_instance

        result = bot._apply_signal_filters("LONG", indicators)

    assert result == "WAIT"


# ---------------------------------------------------------------------------
# 9. MTI 게이트 — OPTIMAL(≥70) → 시그널 통과
# ---------------------------------------------------------------------------


def test_mti_gate_passes_optimal() -> None:
    """MTI OPTIMAL (>=70) 시 시그널 그대로 통과."""
    bot = _make_bot()

    indicators = {"atr_pct": 0.8, "volume_ratio": 1.5}

    with patch(
        "src.data.tradability.MarketTradabilityIndex"
    ) as MockMTI:
        mock_instance = MagicMock()
        mock_score = MagicMock()
        mock_score.is_tradable = True
        mock_score.total_score = 80.0
        mock_score.grade = "OPTIMAL"
        mock_score.reason = "거래 적합"
        mock_instance.evaluate.return_value = mock_score
        MockMTI.return_value = mock_instance

        result = bot._apply_signal_filters("LONG", indicators)

    # LONG이 그대로 통과 (레짐 필터 등 비활성화)
    assert result == "LONG"


# ---------------------------------------------------------------------------
# 10. MTI 게이트 — atr_pct=0 → 스킵
# ---------------------------------------------------------------------------


def test_mti_gate_skipped_when_no_atr() -> None:
    """atr_pct=0이면 MTI 게이트 스킵."""
    bot = _make_bot()

    indicators = {"atr_pct": 0.0, "volume_ratio": 1.0}

    result = bot._apply_signal_filters("LONG", indicators)

    # MTI 스킵, 다른 필터도 비활성 → 시그널 유지
    assert result == "LONG"


# ---------------------------------------------------------------------------
# 11. _fetch_sentiment_data() — Binance 없으면 None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_no_binance_returns_none() -> None:
    """Binance 클라이언트 없으면 None 반환."""
    bot = _make_bot(use_funding=True)
    bot._binance_client = None

    result = await bot._fetch_sentiment_data()

    assert result is None


# ---------------------------------------------------------------------------
# 12. _fetch_sentiment_data() — Redis 히스토리 로드
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_loads_redis_history() -> None:
    """Redis에서 OI/LS 히스토리 로드."""
    bot = _make_bot(use_leverage=True)
    bot._binance_client = _make_binance_mock()
    redis_mock = _make_redis_mock()
    bot._redis_state_manager = redis_mock
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is not None
    assert len(result["oi_history"]) == 3
    assert len(result["ls_history"]) == 2
    redis_mock.load_oi_history.assert_called_once_with("BTCUSDT")
    redis_mock.load_ls_history.assert_called_once_with("BTCUSDT")


# ---------------------------------------------------------------------------
# 13. _fetch_sentiment_data() — Redis 없으면 빈 히스토리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sentiment_no_redis_empty_history() -> None:
    """Redis 없으면 OI/LS 히스토리 빈 리스트."""
    bot = _make_bot(use_smart_money=True)
    bot._binance_client = _make_binance_mock()
    bot._redis_state_manager = None
    bot._current_price = 50000.0

    result = await bot._fetch_sentiment_data()

    assert result is not None
    assert result["oi_history"] == []
    assert result["ls_history"] == []


# ---------------------------------------------------------------------------
# 14. _get_klines_df() — klines 없으면 None
# ---------------------------------------------------------------------------


def test_get_klines_df_no_klines_returns_none() -> None:
    """klines 없으면 None 반환."""
    bot = _make_bot(use_tsmom=True)

    result = bot._get_klines_df({"klines": None})

    assert result is None


def test_get_klines_df_empty_klines_returns_none() -> None:
    """빈 klines 리스트면 None 반환."""
    bot = _make_bot(use_tsmom=True)

    result = bot._get_klines_df({"klines": []})

    assert result is None
