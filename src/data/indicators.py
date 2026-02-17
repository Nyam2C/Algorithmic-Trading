"""Technical indicators calculation using ta library."""

import pandas as pd
from loguru import logger
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

# 지표 분석 상수
RSI_TREND_THRESHOLD = 2
RSI_TREND_THRESHOLD_NEG = -2
HIGH_VOLATILITY_THRESHOLD = 1.5
LOW_VOLATILITY_THRESHOLD = 0.5
MIN_RSI_SAMPLES = 2


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index).

    Args:
        df: DataFrame with 'close' column
        period: RSI period (default: 14)

    Returns:
        Series with RSI values
    """
    try:
        rsi_indicator = RSIIndicator(close=df["close"], window=period)
        rsi = rsi_indicator.rsi()
        logger.debug(f"RSI({period}) calculated: {rsi.iloc[-1]:.2f}")
        return rsi
    except Exception as e:
        logger.error(f"Failed to calculate RSI: {e}")
        raise


def calculate_ma(
    df: pd.DataFrame, periods: list | None = None
) -> dict[str, pd.Series]:
    """Calculate Simple Moving Averages.

    Args:
        df: DataFrame with 'close' column
        periods: List of MA periods (default: [7, 25, 99])

    Returns:
        Dictionary of MA series
    """
    if periods is None:
        periods = [7, 25, 99]
    try:
        mas = {}
        for period in periods:
            ma_indicator = SMAIndicator(close=df["close"], window=period)
            mas[f"ma_{period}"] = ma_indicator.sma_indicator()
            logger.debug(
                f"MA({period}) calculated: "
                f"${mas[f'ma_{period}'].iloc[-1]:,.2f}"
            )
        return mas
    except Exception as e:
        logger.error(f"Failed to calculate MAs: {e}")
        raise


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ATR (Average True Range).

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default: 14)

    Returns:
        Series with ATR values
    """
    try:
        atr_indicator = AverageTrueRange(
            high=df["high"], low=df["low"], close=df["close"], window=period
        )
        atr = atr_indicator.average_true_range()
        logger.debug(f"ATR({period}) calculated: ${atr.iloc[-1]:.2f}")
        return atr
    except Exception as e:
        logger.error(f"Failed to calculate ATR: {e}")
        raise


def calculate_volume_ratio(df: pd.DataFrame) -> float:
    """Calculate current volume ratio vs average.

    마지막 캔들은 아직 진행 중(미완성)일 수 있어 거래량이 극단적으로 낮을 수 있음.
    따라서 마지막 캔들을 제외하고 완성된 캔들들만으로 비율을 계산합니다.

    Args:
        df: DataFrame with 'volume' column

    Returns:
        Volume ratio (current / average)
    """
    try:
        if len(df) > 1:
            # 마지막 미완성 캔들 제외, 완성된 캔들들로 계산
            completed = df.iloc[:-1]
            current_volume = completed["volume"].iloc[-1]
            avg_volume = completed["volume"].mean()
        else:
            current_volume = df["volume"].iloc[-1]
            avg_volume = df["volume"].mean()
        ratio = current_volume / avg_volume if avg_volume > 0 else 0
        logger.debug(f"Volume ratio: {ratio:.2f}x")
        return ratio
    except Exception as e:
        logger.error(f"Failed to calculate volume ratio: {e}")
        raise


def analyze_rsi_trend(rsi_series: pd.Series, window: int = 3) -> str:
    """Analyze RSI trend.

    Args:
        rsi_series: RSI values
        window: Number of candles to analyze

    Returns:
        "rising", "falling", or "flat"
    """
    recent_rsi = rsi_series.tail(window)
    if len(recent_rsi) < MIN_RSI_SAMPLES:
        return "flat"

    first = recent_rsi.iloc[0]
    last = recent_rsi.iloc[-1]
    diff = last - first

    if diff > RSI_TREND_THRESHOLD:
        return "rising"
    if diff < RSI_TREND_THRESHOLD_NEG:
        return "falling"
    return "flat"


def calculate_price_vs_ma(
    current_price: float, ma_value: float
) -> tuple[float, str]:
    """Calculate price position relative to MA.

    Args:
        current_price: Current price
        ma_value: MA value

    Returns:
        (percentage_diff, "above" or "below"). NaN일 경우 (NaN, "N/A") 반환.
    """
    import math  # noqa: PLC0415

    if math.isnan(ma_value) or ma_value == 0:
        return float("nan"), "N/A"
    pct_diff = ((current_price - ma_value) / ma_value) * 100
    position = "above" if pct_diff > 0 else "below"
    return pct_diff, position


def analyze_candle_pattern(df: pd.DataFrame) -> dict:
    """Analyze recent candle patterns.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Dictionary with pattern analysis
    """
    bullish_count = sum(
        1 for _, row in df.iterrows() if row["close"] > row["open"]
    )
    bearish_count = len(df) - bullish_count

    # 2-hour trend
    first_close = df["close"].iloc[0]
    last_close = df["close"].iloc[-1]
    trend_pct = ((last_close - first_close) / first_close) * 100

    # Recent 30min trend (last 6 candles)
    recent_df = df.tail(6)
    recent_first = recent_df["close"].iloc[0]
    recent_last = recent_df["close"].iloc[-1]
    recent_trend_pct = ((recent_last - recent_first) / recent_first) * 100

    return {
        "bullish_candles": bullish_count,
        "bearish_candles": bearish_count,
        "trend_2h_pct": trend_pct,
        "trend_30min_pct": recent_trend_pct,
        "highest": df["high"].max(),
        "lowest": df["low"].min(),
    }



def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ADX (Average Directional Index).

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ADX period (default: 14)

    Returns:
        Series with ADX values
    """
    try:
        adx_indicator = ADXIndicator(
            high=df["high"], low=df["low"], close=df["close"], window=period
        )
        adx = adx_indicator.adx()
        logger.debug(f"ADX({period}) calculated: {adx.iloc[-1]:.2f}")
        return adx
    except Exception as e:
        logger.error(f"Failed to calculate ADX: {e}")
        raise


def calculate_adx_components(
    df: pd.DataFrame, period: int = 14
) -> dict[str, pd.Series]:
    """Calculate ADX with DI+ and DI- components.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ADX period (default: 14)

    Returns:
        Dictionary with 'adx', 'di_plus', 'di_minus' Series
    """
    try:
        adx_indicator = ADXIndicator(
            high=df["high"], low=df["low"], close=df["close"], window=period
        )
        return {
            "adx": adx_indicator.adx(),
            "di_plus": adx_indicator.adx_pos(),
            "di_minus": adx_indicator.adx_neg(),
        }
    except Exception as e:
        logger.error(f"Failed to calculate ADX components: {e}")
        raise


def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        df: DataFrame with 'close' column
        period: EMA period

    Returns:
        Series with EMA values
    """
    try:
        ema_indicator = EMAIndicator(close=df["close"], window=period)
        ema = ema_indicator.ema_indicator()
        logger.debug(f"EMA({period}) calculated: {ema.iloc[-1]:.2f}")
        return ema
    except Exception as e:
        logger.error(f"Failed to calculate EMA: {e}")
        raise


def calculate_bollinger_bandwidth(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Bollinger Bandwidth (BB width normalized by middle band).

    Used for regime transition detection - narrow bands indicate consolidation.

    Args:
        df: DataFrame with 'close' column
        period: Bollinger period (default: 20)

    Returns:
        Series with bandwidth values (0-1 typical range)
    """
    try:
        bb = BollingerBands(close=df["close"], window=period)
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        middle = bb.bollinger_mavg()
        bandwidth = (upper - lower) / middle
        bandwidth = bandwidth.fillna(0.0)
        logger.debug(f"BB Bandwidth({period}) calculated: {bandwidth.iloc[-1]:.4f}")
        return bandwidth
    except Exception as e:
        logger.error(f"Failed to calculate Bollinger Bandwidth: {e}")
        raise


def calculate_returns(
    df: pd.DataFrame, periods: list[int] | None = None
) -> dict[str, pd.Series]:
    """Calculate volatility-adjusted returns for multiple lookback windows.

    Used by TSMOM channel for momentum scoring.

    Args:
        df: DataFrame with 'close' column
        periods: List of lookback periods (default: [5, 10, 20])

    Returns:
        Dictionary of returns Series keyed by period (e.g., 'returns_5')
    """
    if periods is None:
        periods = [5, 10, 20]
    try:
        results = {}
        for period in periods:
            pct_change = df["close"].pct_change(period)
            # Volatility-adjusted: returns / rolling std
            rolling_std = df["close"].pct_change().rolling(window=period).std()
            vol_adjusted = pct_change / rolling_std.replace(0, float("nan"))
            results[f"returns_{period}"] = vol_adjusted
        logger.debug(f"Returns calculated for periods {periods}")
        return results
    except Exception as e:
        logger.error(f"Failed to calculate returns: {e}")
        raise


def analyze_market(
    df: pd.DataFrame, ticker_24h: dict, current_price: float
) -> dict:
    """Comprehensive market analysis.

    Args:
        df: Candlestick DataFrame
        ticker_24h: 24-hour ticker stats
        current_price: Current price

    Returns:
        Dictionary with all indicators and analysis
    """
    try:
        logger.info("Starting market analysis...")

        # Technical indicators
        rsi_series = calculate_rsi(df)
        mas = calculate_ma(df, periods=[7, 25, 99])
        atr_series = calculate_atr(df)

        # Current values
        rsi = rsi_series.iloc[-1]
        ma_7 = mas["ma_7"].iloc[-1]
        ma_25 = mas["ma_25"].iloc[-1]
        ma_99 = mas["ma_99"].iloc[-1]
        atr = atr_series.iloc[-1]

        # RSI trend
        rsi_trend = analyze_rsi_trend(rsi_series)

        # Price vs MAs
        price_vs_ma7_pct, price_vs_ma7_pos = calculate_price_vs_ma(
            current_price, ma_7
        )
        price_vs_ma25_pct, price_vs_ma25_pos = calculate_price_vs_ma(
            current_price, ma_25
        )

        # Volume analysis
        volume_ratio = calculate_volume_ratio(df)
        volume_trend = (
            "increasing"
            if df["volume"].iloc[-1] > df["volume"].iloc[-6]
            else "decreasing"
        )

        # ATR percentage
        atr_pct = (atr / current_price) * 100
        volatility_state = (
            "high"
            if atr_pct > HIGH_VOLATILITY_THRESHOLD
            else "low"
            if atr_pct < LOW_VOLATILITY_THRESHOLD
            else "normal"
        )

        # ADX (Trend strength)
        adx_series = calculate_adx(df)
        adx = adx_series.iloc[-1] if not adx_series.empty else 0.0

        # EMA 20
        ema_20_series = calculate_ema(df, period=20)
        ema_20 = ema_20_series.iloc[-1] if not ema_20_series.empty else 0.0

        # Bollinger Bandwidth
        bb_width_series = calculate_bollinger_bandwidth(df)
        bb_width = bb_width_series.iloc[-1] if not bb_width_series.empty else 0.0

        # Candle pattern
        candle_analysis = analyze_candle_pattern(df)

        # Support/Resistance (simple calculation)
        recent_high = candle_analysis["highest"]
        recent_low = candle_analysis["lowest"]

        dist_resistance_pct = ((recent_high - current_price) / current_price) * 100
        dist_support_pct = ((current_price - recent_low) / current_price) * 100

        analysis = {
            # Price data
            "current_price": current_price,
            "prev_close": (
                float(df["close"].iloc[-2])
                if len(df) >= 2  # noqa: PLR2004
                else current_price
            ),
            "high_24h": ticker_24h["high_24h"],
            "low_24h": ticker_24h["low_24h"],
            "change_24h_pct": ticker_24h["change_24h"],
            # Technical indicators
            "rsi": rsi,
            "rsi_trend": rsi_trend,
            "ma_7": ma_7,
            "ma_25": ma_25,
            "ma_99": ma_99,
            "price_vs_ma7_pct": price_vs_ma7_pct,
            "price_vs_ma7_pos": price_vs_ma7_pos,
            "price_vs_ma25_pct": price_vs_ma25_pct,
            "price_vs_ma25_pos": price_vs_ma25_pos,
            # Volume
            "current_volume": df["volume"].iloc[-1],
            "avg_volume": df["volume"].mean(),
            "volume_ratio": volume_ratio,
            "volume_trend": volume_trend,
            # Volatility
            "atr": atr,
            "atr_pct": atr_pct,
            "volatility_state": volatility_state,
            # New indicators (APEX-V)
            "adx": adx,
            "ema_20": ema_20,
            "bb_width": bb_width,
            # Candle patterns
            "trend_2h_pct": candle_analysis["trend_2h_pct"],
            "trend_30min_pct": candle_analysis["trend_30min_pct"],
            "bullish_candles": candle_analysis["bullish_candles"],
            "bearish_candles": candle_analysis["bearish_candles"],
            # Support/Resistance
            "resistance": recent_high,
            "support": recent_low,
            "dist_resistance_pct": dist_resistance_pct,
            "dist_support_pct": dist_support_pct,
        }

        logger.info("Market analysis completed")
        logger.info(f"RSI: {rsi:.2f} ({rsi_trend})")
        logger.info(f"Price vs MA7: {price_vs_ma7_pct:+.2f}% ({price_vs_ma7_pos})")
        logger.info(f"Volume: {volume_ratio:.2f}x ({volume_trend})")
        logger.info(f"Volatility: {volatility_state} (ATR: {atr_pct:.2f}%)")

        return analysis

    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise
