"""Kelly Criterion 동적 포지션 사이징 모듈.

APEX-V Phase D: 레짐별 과거 거래 성과를 기반으로
Kelly 공식을 적용하여 최적 포지션 크기를 산출한다.

공식: f* = (p*b - q) / b
  - p = 승률 (win_rate)
  - b = 평균 수익 / 평균 손실 (payoff ratio)
  - q = 1 - p (패배율)

적용: f* x kelly_fraction (기본 0.25 = Quarter-Kelly)
클램핑: [min_size_pct, max_size_pct]
"""

from __future__ import annotations

from collections import deque

from loguru import logger

# Kelly 계산 상수
MIN_TRADES_FOR_KELLY = 20
DD_TIER1_THRESHOLD = 0.05
DD_MAX_THRESHOLD = 0.10


class KellySizer:
    """Kelly Criterion 동적 포지션 사이징.

    레짐(regime)별로 과거 거래 결과를 추적하고,
    Kelly 공식을 통해 최적 포지션 비율을 계산한다.
    Quarter-Kelly(0.25)를 기본으로 사용하여 변동성을 억제한다.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        min_size_pct: float = 0.003,
        max_size_pct: float = 0.02,
    ) -> None:
        """KellySizer 초기화.

        Args:
            kelly_fraction: Kelly 비율 승수 (기본 0.25 = Quarter-Kelly).
            min_size_pct: 최소 포지션 크기 비율.
            max_size_pct: 최대 포지션 크기 비율.
        """
        self.kelly_fraction = kelly_fraction
        self.min_size_pct = min_size_pct
        self.max_size_pct = max_size_pct
        self._regime_trades: dict[str, deque] = {}

        logger.info(
            "KellySizer 초기화 완료 — "
            f"fraction={kelly_fraction}, "
            f"min={min_size_pct}, max={max_size_pct}"
        )

    def record_trade(self, regime: str, pnl_pct: float) -> None:
        """레짐별 거래 결과를 기록한다.

        Args:
            regime: 시장 레짐 문자열 (예: "TRENDING", "RANGING").
            pnl_pct: 거래 손익률 (예: 0.015 = 1.5% 수익).
        """
        if regime not in self._regime_trades:
            self._regime_trades[regime] = deque(maxlen=100)

        self._regime_trades[regime].append(pnl_pct)
        logger.debug(
            f"거래 기록 — regime={regime}, pnl_pct={pnl_pct:.4f}, "
            f"총 {len(self._regime_trades[regime])}건"
        )

    def calculate_kelly_size(self, regime: str) -> float | None:
        """원시 Kelly 비율을 계산한다.

        최소 20건의 거래 데이터가 필요하다.

        Args:
            regime: 시장 레짐 문자열.

        Returns:
            Kelly 기반 포지션 크기 비율. 데이터 부족 시 None.
        """
        trades = self._regime_trades.get(regime)
        if trades is None or len(trades) < MIN_TRADES_FOR_KELLY:
            logger.debug(
                f"Kelly 계산 불가 — regime={regime}, "
                f"거래 수={len(trades) if trades else 0} "
                f"(최소 {MIN_TRADES_FOR_KELLY}건 필요)"
            )
            return None

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        total = len(trades)
        p = len(wins) / total  # 승률
        q = 1.0 - p  # 패배율

        avg_win = sum(abs(w) for w in wins) / len(wins) if wins else 0.0
        avg_loss = sum(abs(lo) for lo in losses) / len(losses) if losses else 0.0

        # b = payoff ratio (평균 수익 / 평균 손실)
        if avg_loss == 0:
            logger.debug(
                f"Kelly 계산 — regime={regime}, avg_loss=0 → min_size_pct 반환"
            )
            return self.min_size_pct

        b = avg_win / avg_loss

        if b == 0:
            logger.debug(
                f"Kelly 계산 — regime={regime}, b=0 (승리 없음) → min_size_pct 반환"
            )
            return self.min_size_pct

        # f* = (p*b - q) / b
        kelly_raw = (p * b - q) / b

        if kelly_raw <= 0:
            logger.debug(
                f"Kelly 음수 — regime={regime}, "
                f"p={p:.3f}, b={b:.3f}, f*={kelly_raw:.4f} → min_size_pct 반환"
            )
            return self.min_size_pct

        kelly_applied = kelly_raw * self.kelly_fraction

        logger.debug(
            f"Kelly 계산 완료 — regime={regime}, "
            f"p={p:.3f}, b={b:.3f}, f*={kelly_raw:.4f}, "
            f"적용={kelly_applied:.4f}"
        )
        return kelly_applied

    def calculate_final_size(
        self,
        regime: str,
        config_default: float,
        entry_tier: float = 1.0,
        mti_mod: float = 1.0,
        cost_adj: float = 1.0,
        vitality_mod: float = 1.0,
        drawdown_pct: float = 0.0,
    ) -> float:
        """모든 수정자를 적용한 최종 포지션 크기를 계산한다.

        최종 크기 = base x entry_tier x mti_mod x cost_adj
        x vitality_mod x drawdown_mult
        Kelly 데이터가 부족하면 config_default를 base로 사용한다.

        Args:
            regime: 시장 레짐 문자열.
            config_default: Kelly 미적용 시 기본 포지션 크기.
            entry_tier: 진입 단계 배수 (기본 1.0).
            mti_mod: MTI 기반 수정자 (기본 1.0).
            cost_adj: 비용 조정 배수 (기본 1.0).
            vitality_mod: 활력도 수정자 (기본 1.0).
            drawdown_pct: 현재 드로다운 비율 (0.0~1.0, 기본 0.0).

        Returns:
            클램핑된 최종 포지션 크기 비율.
        """
        kelly_size = self.calculate_kelly_size(regime)
        base = kelly_size if kelly_size is not None else config_default

        drawdown_mult = self._drawdown_multiplier(drawdown_pct)

        raw = base * entry_tier * mti_mod * cost_adj * vitality_mod * drawdown_mult
        final = max(self.min_size_pct, min(raw, self.max_size_pct))

        logger.debug(
            f"최종 포지션 크기 — regime={regime}, "
            f"base={base:.4f}, entry_tier={entry_tier:.2f}, "
            f"mti_mod={mti_mod:.2f}, cost_adj={cost_adj:.2f}, "
            f"vitality_mod={vitality_mod:.2f}, dd_mult={drawdown_mult:.2f}, "
            f"raw={raw:.4f}, final={final:.4f}"
        )
        return final

    def _drawdown_multiplier(self, drawdown_pct: float) -> float:
        """드로다운 비율에 따른 포지션 축소 배수를 계산한다.

        선형 보간: 0% → 1.0, 5% → 0.7, 10% → 0.3.
        0% 미만은 1.0, 10% 초과는 0.3으로 클램핑.

        Args:
            drawdown_pct: 드로다운 비율 (0.0~1.0 범위, 예: 0.05 = 5%).

        Returns:
            포지션 축소 배수 (0.3~1.0).
        """
        if drawdown_pct <= 0.0:
            return 1.0
        if drawdown_pct >= DD_MAX_THRESHOLD:
            return 0.3

        # 0%~5% 구간: 1.0 → 0.7 (기울기 = -6.0)
        if drawdown_pct <= DD_TIER1_THRESHOLD:
            return 1.0 - (drawdown_pct / DD_TIER1_THRESHOLD) * 0.3

        # 5%~10% 구간: 0.7 → 0.3 (기울기 = -8.0)
        return 0.7 - ((drawdown_pct - DD_TIER1_THRESHOLD) / DD_TIER1_THRESHOLD) * 0.4

    def to_dict(self) -> dict:
        """Redis 저장을 위해 상태를 직렬화한다.

        Returns:
            직렬화된 상태 딕셔너리.
        """
        return {
            "kelly_fraction": self.kelly_fraction,
            "min_size_pct": self.min_size_pct,
            "max_size_pct": self.max_size_pct,
            "regime_trades": {
                regime: list(trades)
                for regime, trades in self._regime_trades.items()
            },
        }

    def from_dict(self, data: dict) -> None:
        """딕셔너리에서 상태를 복원한다.

        Args:
            data: to_dict()로 생성된 딕셔너리.
        """
        self.kelly_fraction = data.get("kelly_fraction", self.kelly_fraction)
        self.min_size_pct = data.get("min_size_pct", self.min_size_pct)
        self.max_size_pct = data.get("max_size_pct", self.max_size_pct)

        regime_trades_raw = data.get("regime_trades", {})
        self._regime_trades = {
            regime: deque(trades, maxlen=100)
            for regime, trades in regime_trades_raw.items()
        }

        logger.info(
            f"KellySizer 상태 복원 — "
            f"{len(self._regime_trades)}개 레짐, "
            f"총 {sum(len(d) for d in self._regime_trades.values())}건 거래"
        )
