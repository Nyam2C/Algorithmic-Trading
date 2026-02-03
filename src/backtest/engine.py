"""
백테스트 엔진

Phase 6.5: 백테스트 프레임워크
- 전략 시뮬레이션
- 성과 계산

Phase 6.2: 백테스트 현실화
- 슬리피지 모델 적용
- RSI, ATR, MACD, BB 지표 계산
- High/Low 기반 현실적 청산
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger

from src.backtest.slippage import (
    SlippageModel,
    calculate_realistic_entry_price,
    calculate_realistic_exit_price,
)


@dataclass
class BacktestConfig:
    """백테스트 설정

    Attributes:
        initial_capital: 초기 자본
        leverage: 레버리지
        position_size_pct: 포지션 크기 (자본의 %)
        tp_pct: 익절 비율
        sl_pct: 손절 비율
        timecut_bars: 시간 제한 (봉 개수)
        commission_pct: 수수료 비율
        use_slippage: 슬리피지 사용 여부 (Phase 6.2)
        use_realistic_exits: 현실적 청산 사용 여부 (Phase 6.2)
    """
    initial_capital: float = 10000.0
    leverage: int = 10
    position_size_pct: float = 0.05  # 5%
    tp_pct: float = 0.01  # 1%
    sl_pct: float = 0.005  # 0.5%
    timecut_bars: int = 100
    commission_pct: float = 0.0004  # 0.04%
    # Phase 6.2: 현실화 옵션
    use_slippage: bool = True
    use_realistic_exits: bool = True


@dataclass
class Trade:
    """거래 기록

    Attributes:
        entry_time: 진입 시간
        entry_price: 진입 가격
        side: 방향 (LONG/SHORT)
        quantity: 수량
        exit_time: 청산 시간
        exit_price: 청산 가격
        exit_reason: 청산 사유
        pnl: 손익
    """
    entry_time: Any
    entry_price: float
    side: str
    quantity: float
    exit_time: Optional[Any] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None

    def calculate_pnl(self) -> None:
        """PnL 계산"""
        if self.exit_price is None:
            return

        if self.side == "LONG":
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.pnl = (self.entry_price - self.exit_price) * self.quantity

    def is_winner(self) -> bool:
        """승리 여부"""
        if self.pnl is None:
            return False
        return self.pnl > 0


@dataclass
class BacktestResult:
    """백테스트 결과

    Attributes:
        trades: 거래 목록
        initial_capital: 초기 자본
        final_capital: 최종 자본
        total_trades: 총 거래 수
        winning_trades: 승리 거래 수
        losing_trades: 패배 거래 수
        win_rate: 승률 (%)
        total_pnl: 총 손익
        max_drawdown: 최대 드로다운
        sharpe_ratio: 샤프 비율
    """
    trades: List[Trade]
    initial_capital: float
    final_capital: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    equity_curve: List[float] = field(default_factory=list)

    def calculate_metrics(self) -> None:
        """메트릭 계산"""
        self.total_trades = len(self.trades)

        if self.total_trades == 0:
            return

        self.winning_trades = sum(1 for t in self.trades if t.is_winner())
        self.losing_trades = self.total_trades - self.winning_trades
        self.win_rate = (self.winning_trades / self.total_trades) * 100
        self.total_pnl = sum(t.pnl or 0 for t in self.trades)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl": round(self.total_pnl, 2),
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "return_pct": round((self.final_capital - self.initial_capital) / self.initial_capital * 100, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
        }


# 전략 함수 타입: (candle, market_data) -> signal
StrategyFunc = Callable[[Dict, Dict], str]


class BacktestEngine:
    """백테스트 엔진

    과거 데이터로 전략을 시뮬레이션합니다.

    Phase 6.2: 현실화 옵션 추가
    - 슬리피지 모델
    - RSI, ATR, MACD, BB 지표
    - High/Low 기반 현실적 청산

    Example:
        >>> config = BacktestConfig(initial_capital=10000)
        >>> engine = BacktestEngine(config, candles)
        >>> result = engine.run(my_strategy)
        >>> print(f"Win rate: {result.win_rate}%")
    """

    def __init__(
        self,
        config: BacktestConfig,
        data: List[Dict],
        slippage_model: Optional[SlippageModel] = None,
    ) -> None:
        """엔진 초기화

        Args:
            config: 백테스트 설정
            data: 캔들 데이터 리스트
            slippage_model: 슬리피지 모델 (선택)
        """
        self.config = config
        self.data = data
        self.capital = config.initial_capital
        self.position: Optional[Trade] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [config.initial_capital]

        # Phase 6.2: 슬리피지 모델
        self.slippage_model = slippage_model or (
            SlippageModel() if config.use_slippage else None
        )

        # 평균 거래량 (슬리피지 계산용)
        self._avg_volume = self._calculate_avg_volume()

        logger.debug(
            f"BacktestEngine 초기화: {len(data)} 캔들, "
            f"초기자본 ${config.initial_capital}, "
            f"슬리피지={'ON' if self.slippage_model else 'OFF'}"
        )

    def _calculate_avg_volume(self) -> float:
        """평균 거래량 계산"""
        volumes = [c.get("volume", 0) for c in self.data if c.get("volume", 0) > 0]
        if volumes:
            return sum(volumes) / len(volumes)
        return 10000.0  # 기본값

    def run(self, strategy: StrategyFunc) -> BacktestResult:
        """백테스트 실행

        Args:
            strategy: 전략 함수 (candle, market_data) -> "LONG" | "SHORT" | "WAIT"

        Returns:
            BacktestResult
        """
        logger.info("백테스트 시작...")
        bars_in_position = 0

        for i, candle in enumerate(self.data):
            # 시장 데이터 준비 (간단한 버전)
            market_data = self._prepare_market_data(i)

            # 포지션이 있으면 TP/SL/Timecut 체크
            if self.position is not None:
                bars_in_position += 1
                exit_reason = self._check_exit(candle, bars_in_position)

                if exit_reason:
                    self._close_position(candle, exit_reason)
                    bars_in_position = 0
                    continue

            # 포지션이 없으면 시그널 확인
            if self.position is None:
                signal = strategy(candle, market_data)

                if signal in ("LONG", "SHORT"):
                    self._open_position(candle, signal)
                    bars_in_position = 0

            # 자본 기록
            self.equity_curve.append(self.capital)

        # 남은 포지션 청산
        if self.position is not None:
            self._close_position(self.data[-1], "END")

        # 결과 계산
        result = BacktestResult(
            trades=self.trades,
            initial_capital=self.config.initial_capital,
            final_capital=self.capital,
            equity_curve=self.equity_curve,
        )
        result.calculate_metrics()
        result.max_drawdown = self._calculate_max_drawdown()

        logger.info(
            f"백테스트 완료: {result.total_trades}거래, "
            f"승률 {result.win_rate:.1f}%, 총손익 ${result.total_pnl:.2f}"
        )

        return result

    def _prepare_market_data(self, index: int) -> Dict:
        """시장 데이터 준비

        Phase 6.2: RSI, ATR, MACD, BB 지표 추가
        """
        if index < 25:
            return {}

        # 최근 데이터 슬라이스
        window = self.data[max(0, index - 99):index + 1]
        closes = [c["close"] for c in window]
        # highs/lows는 향후 ATR, BB 계산에 사용될 수 있음
        _ = [c["high"] for c in window]  # highs (reserved)
        _ = [c["low"] for c in window]  # lows (reserved)

        market_data: Dict[str, Any] = {}

        # Moving Averages
        if len(closes) >= 7:
            market_data["ma_7"] = sum(closes[-7:]) / 7
        if len(closes) >= 25:
            market_data["ma_25"] = sum(closes[-25:]) / 25
        if len(closes) >= 99:
            market_data["ma_99"] = sum(closes[-99:]) / 99

        # RSI (14 periods)
        if len(closes) >= 15:
            market_data["rsi"] = self._calculate_rsi(closes[-15:])

        # ATR (14 periods)
        if len(window) >= 15:
            market_data["atr"] = self._calculate_atr(window[-15:])
            if closes[-1] > 0:
                market_data["atr_pct"] = (market_data["atr"] / closes[-1]) * 100

        # MACD (12, 26, 9)
        if len(closes) >= 26:
            macd_data = self._calculate_macd(closes)
            market_data.update(macd_data)

        # Bollinger Bands (20, 2)
        if len(closes) >= 20:
            bb_data = self._calculate_bollinger_bands(closes[-20:])
            market_data.update(bb_data)

        # 현재 캔들 정보
        market_data["current_price"] = closes[-1]
        market_data["current_volume"] = window[-1].get("volume", 0)

        return market_data

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """RSI 계산"""
        if len(closes) < period + 1:
            return 50.0

        gains: List[float] = []
        losses: List[float] = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """ATR 계산"""
        if len(candles) < 2:
            return 0.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i - 1]["close"]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0

        return sum(true_ranges[-period:]) / min(len(true_ranges), period)

    def _calculate_macd(
        self,
        closes: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Dict[str, float]:
        """MACD 계산"""
        if len(closes) < slow:
            return {}

        # EMA 계산 함수
        def ema(data: List[float], period: int) -> List[float]:
            if len(data) < period:
                return []
            k = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]
            for price in data[period:]:
                ema_values.append(price * k + ema_values[-1] * (1 - k))
            return ema_values

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)

        if not ema_fast or not ema_slow:
            return {}

        # MACD 라인
        min_len = min(len(ema_fast), len(ema_slow))
        macd_line = [
            ema_fast[-(min_len - i)] - ema_slow[-(min_len - i)]
            for i in range(min_len)
        ]

        if len(macd_line) < signal:
            return {"macd": macd_line[-1] if macd_line else 0}

        # 시그널 라인
        signal_line = ema(macd_line, signal)

        if not signal_line:
            return {"macd": macd_line[-1]}

        return {
            "macd": macd_line[-1],
            "macd_signal": signal_line[-1],
            "macd_histogram": macd_line[-1] - signal_line[-1],
        }

    def _calculate_bollinger_bands(
        self,
        closes: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Dict[str, float]:
        """볼린저 밴드 계산"""
        if len(closes) < period:
            return {}

        sma = sum(closes[-period:]) / period

        # 표준편차
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = variance ** 0.5

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return {
            "bb_upper": upper,
            "bb_middle": sma,
            "bb_lower": lower,
            "bb_width": (upper - lower) / sma if sma > 0 else 0,
        }

    def _open_position(self, candle: Dict, side: str) -> None:
        """포지션 진입

        Phase 6.2: 슬리피지 적용
        """
        position_value = self.capital * self.config.position_size_pct * self.config.leverage

        # Phase 6.2: 슬리피지 적용
        if self.slippage_model and self.config.use_slippage:
            entry_price = calculate_realistic_entry_price(
                candle=candle,
                side=side,
                slippage_model=self.slippage_model,
                order_size=position_value,
                avg_volume=self._avg_volume,
            )
        else:
            entry_price = candle["close"]

        quantity = position_value / entry_price

        # 수수료 차감
        commission = position_value * self.config.commission_pct
        self.capital -= commission

        self.position = Trade(
            entry_time=candle["timestamp"],
            entry_price=entry_price,
            side=side,
            quantity=quantity,
        )

        logger.debug(f"진입: {side} @ {entry_price:.2f}, qty={quantity:.4f}")

    def _close_position(self, candle: Dict, exit_reason: str) -> None:
        """포지션 청산

        Phase 6.2: 현실적인 청산 가격 적용
        """
        if self.position is None:
            return

        # Phase 6.2: 현실적인 청산 가격
        if self.config.use_realistic_exits:
            exit_price = calculate_realistic_exit_price(
                candle=candle,
                position_side=self.position.side,
                exit_reason=exit_reason,
                entry_price=self.position.entry_price,
                tp_pct=self.config.tp_pct,
                sl_pct=self.config.sl_pct,
            )
        else:
            exit_price = candle["close"]

        self.position.exit_time = candle["timestamp"]
        self.position.exit_price = exit_price
        self.position.exit_reason = exit_reason
        self.position.calculate_pnl()

        # PnL 반영
        pnl = self.position.pnl or 0
        self.capital += pnl

        # 수수료 차감
        position_value = self.position.quantity * exit_price
        commission = position_value * self.config.commission_pct
        self.capital -= commission

        logger.debug(
            f"청산: {self.position.side} @ {exit_price:.2f}, "
            f"reason={exit_reason}, pnl={pnl:.2f}"
        )

        self.trades.append(self.position)
        self.position = None

    def _check_exit(self, candle: Dict, bars: int) -> Optional[str]:
        """청산 조건 체크

        Phase 6.2: High/Low 기반 현실적 TP/SL 체크
        """
        if self.position is None:
            return None

        entry_price = self.position.entry_price
        side = self.position.side

        # Phase 6.2: 현실적 체크는 high/low 사용
        if self.config.use_realistic_exits:
            high_price = candle["high"]
            low_price = candle["low"]

            if side == "LONG":
                tp_price = entry_price * (1 + self.config.tp_pct)
                sl_price = entry_price * (1 - self.config.sl_pct)

                # TP: 고가가 TP 가격 도달
                if high_price >= tp_price:
                    return "TP"
                # SL: 저가가 SL 가격 도달
                if low_price <= sl_price:
                    return "SL"
            else:  # SHORT
                tp_price = entry_price * (1 - self.config.tp_pct)
                sl_price = entry_price * (1 + self.config.sl_pct)

                # TP: 저가가 TP 가격 도달
                if low_price <= tp_price:
                    return "TP"
                # SL: 고가가 SL 가격 도달
                if high_price >= sl_price:
                    return "SL"
        else:
            # 기존 방식: 종가 기준
            current_price = candle["close"]

            if side == "LONG":
                tp_price = entry_price * (1 + self.config.tp_pct)
                sl_price = entry_price * (1 - self.config.sl_pct)

                if current_price >= tp_price:
                    return "TP"
                if current_price <= sl_price:
                    return "SL"
            else:  # SHORT
                tp_price = entry_price * (1 - self.config.tp_pct)
                sl_price = entry_price * (1 + self.config.sl_pct)

                if current_price <= tp_price:
                    return "TP"
                if current_price >= sl_price:
                    return "SL"

        # Timecut
        if bars >= self.config.timecut_bars:
            return "TIMECUT"

        return None

    def _calculate_max_drawdown(self) -> float:
        """최대 드로다운 계산"""
        if not self.equity_curve:
            return 0.0

        peak = self.equity_curve[0]
        max_dd = 0.0

        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd
