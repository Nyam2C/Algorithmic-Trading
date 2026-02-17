"""전략 생존력(Vitality) 추적.

APEX-V Phase C Step 7: Rolling Sharpe 기반 전략 건강 상태 모니터링.
Phase 1 = 데이터 수집만. 시그널 차단 안 함.
"""
from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import sqrt

from loguru import logger


class VitalityLevel(Enum):
    """전략 생존력 레벨."""
    HEALTHY = "healthy"       # Sharpe >= 1.0
    CAUTION = "caution"       # Sharpe 0.5 ~ 1.0
    WARNING = "warning"       # Sharpe 0.0 ~ 0.5
    CRITICAL = "critical"     # Sharpe < 0.0


@dataclass
class VitalitySnapshot:
    """생존력 스냅샷.

    Attributes:
        level: 생존력 레벨
        sharpe_ratio: Rolling Sharpe Ratio
        trade_count: 기록된 거래 수
        avg_pnl_pct: 평균 PnL %
    """
    level: VitalityLevel
    sharpe_ratio: float
    trade_count: int
    avg_pnl_pct: float


class VitalityTracker:
    """전략 생존력 추적기.

    Rolling Sharpe Ratio를 기반으로 전략 건강 상태를 모니터링합니다.
    Phase 1에서는 데이터 수집과 로깅만 수행하며, 시그널 차단은 하지 않습니다.

    Attributes:
        window_size: Rolling window 크기 (거래 수)
    """

    MIN_TRADES_FOR_SHARPE = 2
    SHARPE_HEALTHY = 1.0
    SHARPE_CAUTION = 0.5


    def __init__(self, window_size: int = 60) -> None:
        """초기화.

        Args:
            window_size: Rolling window 크기 (기본 60 거래)
        """
        self.window_size = window_size
        self._trades: deque[float] = deque(maxlen=window_size)
        self._log = logger.bind(module="vitality")

    def record_trade(self, pnl_pct: float) -> None:
        """거래 결과 기록.

        Args:
            pnl_pct: 거래 PnL 퍼센트 (예: 0.02 = 2%)
        """
        self._trades.append(pnl_pct)
        snapshot = self.get_vitality()
        self._log.info(
            f"Vitality 기록: pnl={pnl_pct:.4f}, "
            f"level={snapshot.level.value}, sharpe={snapshot.sharpe_ratio:.2f}, "
            f"trades={snapshot.trade_count}/{self.window_size}"
        )

    def get_vitality(self) -> VitalitySnapshot:
        """현재 생존력 스냅샷 반환.

        Returns:
            VitalitySnapshot
        """
        trade_count = len(self._trades)
        if trade_count < self.MIN_TRADES_FOR_SHARPE:
            return VitalitySnapshot(
                level=VitalityLevel.HEALTHY,
                sharpe_ratio=0.0,
                trade_count=trade_count,
                avg_pnl_pct=self._trades[0] if trade_count == 1 else 0.0,
            )

        # Rolling Sharpe Ratio 계산
        avg = sum(self._trades) / trade_count
        variance = sum((x - avg) ** 2 for x in self._trades) / (trade_count - 1)
        std = sqrt(variance) if variance > 0 else 0.0

        sharpe = avg / std if std > 0 else 0.0

        # 레벨 결정
        level = self._classify_level(sharpe)

        return VitalitySnapshot(
            level=level,
            sharpe_ratio=round(sharpe, 4),
            trade_count=trade_count,
            avg_pnl_pct=round(avg, 6),
        )

    @staticmethod
    def _classify_level(sharpe: float) -> VitalityLevel:
        """Sharpe Ratio 기반 레벨 분류."""
        if sharpe >= VitalityTracker.SHARPE_HEALTHY:
            return VitalityLevel.HEALTHY
        if sharpe >= VitalityTracker.SHARPE_CAUTION:
            return VitalityLevel.CAUTION
        if sharpe >= 0.0:
            return VitalityLevel.WARNING
        return VitalityLevel.CRITICAL
