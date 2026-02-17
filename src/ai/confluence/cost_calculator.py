"""Net Edge 비용 계산.

APEX-V Phase C Step 5: 비용 차감 후 순 기대값 검증.
"""
from loguru import logger


class CostCalculator:
    """거래 비용 계산기.

    왕복 수수료 + 슬리피지를 기반으로 비용 패널티를 계산합니다.

    Attributes:
        fee_rate: 왕복 수수료율 (기본 0.08%)
        slippage_factor: 슬리피지 계수 (ATR% x factor)
    """

    def __init__(
        self,
        fee_rate: float = 0.0008,
        slippage_factor: float = 0.1,
    ) -> None:
        """비용 계산기 초기화.

        Args:
            fee_rate: 왕복 수수료율 (예: 0.0008 = 0.08%)
            slippage_factor: 슬리피지 계수 (ATR% x factor)
        """
        self.fee_rate = fee_rate
        self.slippage_factor = slippage_factor

    def calculate_cost_penalty(self, atr_pct: float, leverage: int) -> float:
        """비용 패널티 계산 (0~1 스케일).

        비용 = (왕복 수수료 + 슬리피지) x 레버리지
        패널티 = min(비용, 1.0) — 스케일 0~1

        Args:
            atr_pct: ATR 퍼센트 (예: 1.5 = 1.5%)
            leverage: 레버리지 배수

        Returns:
            비용 패널티 (0.0 ~ 1.0)
        """
        # 왕복 수수료 (진입 + 청산)
        fee_cost = self.fee_rate * 2

        # 슬리피지: ATR% x 계수 (퍼센트 → 비율 변환)
        slippage_cost = (atr_pct / 100.0) * self.slippage_factor

        # 총 비용 x 레버리지 (레버리지가 높을수록 비용 영향 큼)
        total_cost = (fee_cost + slippage_cost) * leverage

        penalty = min(total_cost, 1.0)

        logger.debug(
            f"비용 계산: fee={fee_cost:.4f}, slippage={slippage_cost:.4f}, "
            f"leverage={leverage}x, penalty={penalty:.4f}"
        )

        return penalty

    def calculate_net_edge(
        self,
        confluence_score: float,
        atr_pct: float,
        leverage: int,
    ) -> tuple[float, float]:
        """순 기대값 계산.

        net_edge = confluence_score - cost_penalty

        Args:
            confluence_score: 합류 점수 (0~1)
            atr_pct: ATR 퍼센트
            leverage: 레버리지 배수

        Returns:
            (net_edge, cost_penalty) 튜플
        """
        cost_penalty = self.calculate_cost_penalty(atr_pct, leverage)
        net_edge = confluence_score - cost_penalty

        logger.debug(
            f"Net Edge: {confluence_score:.3f} - {cost_penalty:.3f} = {net_edge:.3f}"
        )

        return net_edge, cost_penalty

    def update_slippage_factor(self, new_factor: float) -> None:
        """실행 피드백에서 슬리피지 계수 업데이트.

        Args:
            new_factor: 새 슬리피지 계수 (0.01 ~ 0.5 범위로 클램프)
        """
        self.slippage_factor = max(0.01, min(0.5, new_factor))
        logger.debug(f"슬리피지 계수 업데이트: {self.slippage_factor:.4f}")

