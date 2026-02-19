"""BT↔Live Comparator — 백테스트 vs 실거래 괴리 감지.

Paper Trading 시 BT와 실시간 결과 간 괴리를 분해:
1. Slippage = |live_entry - bt_entry| / bt_entry
2. Fill Rate = 실제 체결 vs BT 가정 체결 비율
3. Funding = live_funding_cost - bt_funding_cost

괴리 > WARNING_PCT → 경고, > CRITICAL_PCT → 거래 정지.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger


@dataclass
class TradeComparison:
    """개별 거래 비교 결과."""
    trade_id: str
    timestamp: datetime
    side: str              # LONG / SHORT

    # 진입 가격
    bt_entry: float
    live_entry: float

    # 체결 비율 (1.0 = 100%)
    bt_fill_rate: float = 1.0
    live_fill_rate: float = 1.0

    # 펀딩 비용
    bt_funding_cost: float = 0.0
    live_funding_cost: float = 0.0

    @property
    def slippage_pct(self) -> float:
        """슬리피지 비율 (0~1)."""
        if self.bt_entry == 0:
            return 0.0
        return abs(self.live_entry - self.bt_entry) / self.bt_entry

    @property
    def fill_divergence(self) -> float:
        """체결 비율 괴리 (0~1)."""
        return abs(self.live_fill_rate - self.bt_fill_rate)

    @property
    def funding_divergence(self) -> float:
        """펀딩 비용 괴리 (절대값)."""
        return abs(self.live_funding_cost - self.bt_funding_cost)

    @property
    def total_divergence_pct(self) -> float:
        """총 괴리율 (0~1). 세 요소의 가중 합산."""
        # 슬리피지가 가장 중요 (50%), 체결률 (30%), 펀딩 (20%)
        return (
            self.slippage_pct * 0.5
            + self.fill_divergence * 0.3
            + min(self.funding_divergence * 10, 1.0) * 0.2  # 펀딩은 절대값 정규화
        )


@dataclass
class ComparatorReport:
    """BT↔Live 비교 리포트."""
    comparisons: list[TradeComparison] = field(default_factory=list)
    avg_slippage_pct: float = 0.0
    avg_fill_divergence: float = 0.0
    avg_funding_divergence: float = 0.0
    avg_total_divergence_pct: float = 0.0
    is_warning: bool = False
    is_critical: bool = False

    @property
    def trade_count(self) -> int:
        return len(self.comparisons)


class BTLiveComparator:
    """BT↔Live 괴리 감지기.

    Args:
        warning_threshold: 경고 임계값 (기본 0.20 = 20%)
        critical_threshold: 재검증 임계값 (기본 0.30 = 30%)
        max_history: 최대 비교 기록 수
    """

    def __init__(
        self,
        warning_threshold: float = 0.20,
        critical_threshold: float = 0.30,
        max_history: int = 100,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._max_history = max_history
        self._comparisons: list[TradeComparison] = []

    def record_comparison(self, comparison: TradeComparison) -> ComparatorReport:
        """거래 비교 기록 + 리포트 생성.

        Args:
            comparison: 개별 거래 비교

        Returns:
            ComparatorReport
        """
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_history:
            self._comparisons = self._comparisons[-self._max_history:]

        report = self._generate_report()

        if report.is_critical:
            logger.critical(
                f"BT↔Live 괴리 CRITICAL: {report.avg_total_divergence_pct:.1%} "
                f"(임계값: {self._critical_threshold:.0%})"
            )
        elif report.is_warning:
            logger.warning(
                f"BT↔Live 괴리 WARNING: {report.avg_total_divergence_pct:.1%} "
                f"(임계값: {self._warning_threshold:.0%})"
            )

        return report

    def _generate_report(self) -> ComparatorReport:
        """최근 비교 기록으로 리포트 생성."""
        if not self._comparisons:
            return ComparatorReport()

        # 최근 10개 기준 (충분한 샘플)
        recent = self._comparisons[-10:]
        n = len(recent)

        avg_slip = sum(c.slippage_pct for c in recent) / n
        avg_fill = sum(c.fill_divergence for c in recent) / n
        avg_fund = sum(c.funding_divergence for c in recent) / n
        avg_total = sum(c.total_divergence_pct for c in recent) / n

        return ComparatorReport(
            comparisons=list(recent),
            avg_slippage_pct=avg_slip,
            avg_fill_divergence=avg_fill,
            avg_funding_divergence=avg_fund,
            avg_total_divergence_pct=avg_total,
            is_warning=avg_total >= self._warning_threshold,
            is_critical=avg_total >= self._critical_threshold,
        )

    def get_report(self) -> ComparatorReport:
        """현재 리포트 조회 (기록 없이)."""
        return self._generate_report()

    @property
    def comparison_count(self) -> int:
        return len(self._comparisons)
