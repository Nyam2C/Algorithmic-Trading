"""실행 품질 추적기 — APEX-V Phase D.

거래 실행 품질을 추적하고, 슬리피지 피드백을 제공합니다.
Rolling window 기반으로 최근 N건의 실행 데이터를 유지합니다.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from loguru import logger

# 실행 품질 임계값
QUALITY_PAUSE_THRESHOLD = 0.60
QUALITY_DEGRADED_THRESHOLD = 0.80
QUALITY_EXCELLENT_THRESHOLD = 0.95


class ExecutionTracker:
    """실행 품질 추적기.

    최근 거래의 실행 품질(actual vs theoretical PnL)을 추적하여
    포지션 사이즈 조절 및 전략 일시정지 판단에 활용합니다.
    """

    def __init__(self, window_size: int = 50) -> None:
        """초기화.

        Args:
            window_size: 추적할 최근 거래 수 (기본 50건).
        """
        self._executions: deque[dict[str, Any]] = deque(maxlen=window_size)
        self._window_size = window_size
        logger.info(f"ExecutionTracker 초기화 완료 (window_size={window_size})")

    def record_execution(
        self,
        entry_price: float,
        exit_price: float,
        side: str,
        pnl_actual: float,
        pnl_theoretical: float,
        slippage_pct: float,
    ) -> None:
        """실행 기록 추가.

        Args:
            entry_price: 진입 가격.
            exit_price: 청산 가격.
            side: 포지션 방향 (LONG/SHORT).
            pnl_actual: 실제 실현 PnL.
            pnl_theoretical: 이론적 PnL (신호 기준).
            slippage_pct: 슬리피지 비율 (0.0~1.0).
        """
        record: dict[str, Any] = {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "side": side,
            "pnl_actual": pnl_actual,
            "pnl_theoretical": pnl_theoretical,
            "slippage_pct": slippage_pct,
        }
        self._executions.append(record)
        logger.debug(
            f"실행 기록 추가: side={side}, "
            f"actual={pnl_actual:.4f}, theoretical={pnl_theoretical:.4f}, "
            f"slippage={slippage_pct:.4f}"
        )

    def get_exec_quality(self) -> float:
        """실행 품질 계산.

        actual/theoretical 비율의 평균을 반환합니다.
        theoretical이 0인 거래는 제외합니다.

        Returns:
            실행 품질 (1.0 = 완벽, <1.0 = 손실 발생). 기록 없으면 1.0.
        """
        if not self._executions:
            return 1.0

        ratios: list[float] = []
        for ex in self._executions:
            if ex["pnl_theoretical"] != 0:
                ratios.append(ex["pnl_actual"] / ex["pnl_theoretical"])

        if not ratios:
            return 1.0

        return sum(ratios) / len(ratios)

    def get_size_modifier(self) -> float:
        """실행 품질 기반 포지션 사이즈 조절 계수.

        Returns:
            사이즈 계수:
            - <0.60 -> 0.0 (일시정지)
            - <0.80 -> 0.9
            - 0.80~0.95 -> 1.0
            - >0.95 -> 1.05
        """
        quality = self.get_exec_quality()

        if quality < QUALITY_PAUSE_THRESHOLD:
            logger.warning(f"실행 품질 심각 ({quality:.2f}) — 사이즈 0.0 (일시정지)")
            return 0.0
        if quality < QUALITY_DEGRADED_THRESHOLD:
            logger.info(f"실행 품질 저하 ({quality:.2f}) — 사이즈 0.9")
            return 0.9
        if quality <= QUALITY_EXCELLENT_THRESHOLD:
            return 1.0

        return 1.05

    def get_calibrated_slippage_factor(self) -> float:
        """보정된 슬리피지 팩터.

        기록된 실행들의 슬리피지 평균을 반환합니다.

        Returns:
            평균 슬리피지 비율. 기록 없으면 0.1 (기본값).
        """
        if not self._executions:
            return 0.1

        total = sum(ex["slippage_pct"] for ex in self._executions)
        return total / len(self._executions)

    def should_pause_strategy(self) -> bool:
        """전략 일시정지 여부 판단.

        실행 품질이 0.60 미만이면 True.

        Returns:
            일시정지 필요 여부.
        """
        quality = self.get_exec_quality()
        if quality < QUALITY_PAUSE_THRESHOLD:
            logger.warning(
                f"실행 품질 임계치 미달 ({quality:.2f} < {QUALITY_PAUSE_THRESHOLD}) "
                "— 전략 일시정지 권고"
            )
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Redis 저장용 직렬화.

        Returns:
            deque를 list로 변환한 dict.
        """
        return {
            "window_size": self._window_size,
            "executions": list(self._executions),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """dict에서 복원.

        Args:
            data: to_dict()로 생성된 dict.
        """
        window_size = data.get("window_size", self._window_size)
        self._window_size = window_size
        self._executions = deque(
            data.get("executions", []),
            maxlen=window_size,
        )
        logger.info(
            f"ExecutionTracker 복원 완료: {len(self._executions)}건 로드"
        )
