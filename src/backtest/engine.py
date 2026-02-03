"""
백테스트 엔진

Phase 6.5: 백테스트 프레임워크
- 전략 시뮬레이션
- 성과 계산
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


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
    """
    initial_capital: float = 10000.0
    leverage: int = 10
    position_size_pct: float = 0.05  # 5%
    tp_pct: float = 0.01  # 1%
    sl_pct: float = 0.005  # 0.5%
    timecut_bars: int = 100
    commission_pct: float = 0.0004  # 0.04%


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
    ) -> None:
        """엔진 초기화

        Args:
            config: 백테스트 설정
            data: 캔들 데이터 리스트
        """
        self.config = config
        self.data = data
        self.capital = config.initial_capital
        self.position: Optional[Trade] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [config.initial_capital]

        logger.debug(f"BacktestEngine 초기화: {len(data)} 캔들, 초기자본 ${config.initial_capital}")

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
        """시장 데이터 준비"""
        if index < 25:
            return {}

        closes = [c["close"] for c in self.data[max(0, index-25):index+1]]
        return {
            "ma_7": sum(closes[-7:]) / 7 if len(closes) >= 7 else None,
            "ma_25": sum(closes[-25:]) / 25 if len(closes) >= 25 else None,
        }

    def _open_position(self, candle: Dict, side: str) -> None:
        """포지션 진입"""
        entry_price = candle["close"]
        position_value = self.capital * self.config.position_size_pct * self.config.leverage
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

        logger.debug(f"진입: {side} @ {entry_price}, qty={quantity:.4f}")

    def _close_position(self, candle: Dict, exit_reason: str) -> None:
        """포지션 청산"""
        if self.position is None:
            return

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
            f"청산: {self.position.side} @ {exit_price}, "
            f"reason={exit_reason}, pnl={pnl:.2f}"
        )

        self.trades.append(self.position)
        self.position = None

    def _check_exit(self, candle: Dict, bars: int) -> Optional[str]:
        """청산 조건 체크"""
        if self.position is None:
            return None

        current_price = candle["close"]
        entry_price = self.position.entry_price
        side = self.position.side

        # TP/SL 가격 계산
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
