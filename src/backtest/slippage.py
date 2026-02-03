"""
슬리피지 모델

Phase 6.2: 백테스트 현실화
- 볼륨 기반 슬리피지 계산
- 변동성 영향 반영
"""
from dataclasses import dataclass
from typing import Dict, Optional



@dataclass
class SlippageModel:
    """슬리피지 모델

    실제 거래에서 발생하는 슬리피지를 시뮬레이션합니다.

    Attributes:
        base_slippage_pct: 기본 슬리피지 (%)
        volume_impact_factor: 볼륨 영향 계수
        volatility_impact_factor: 변동성 영향 계수
        max_slippage_pct: 최대 슬리피지 (%)

    Example:
        >>> model = SlippageModel()
        >>> slippage = model.calculate_slippage(
        ...     order_size=1000.0,
        ...     avg_volume=10000.0,
        ...     volatility=0.02
        ... )
        >>> print(f"슬리피지: {slippage:.4f}%")
    """

    base_slippage_pct: float = 0.01  # 0.01% 기본 슬리피지
    volume_impact_factor: float = 0.001  # 볼륨 영향 계수
    volatility_impact_factor: float = 0.5  # 변동성 영향 계수
    max_slippage_pct: float = 0.1  # 최대 0.1% 슬리피지

    def calculate_slippage(
        self,
        order_size: float,
        avg_volume: float,
        volatility: float = 0.0,
    ) -> float:
        """슬리피지 계산

        Args:
            order_size: 주문 크기 (USD 또는 BTC)
            avg_volume: 평균 거래량
            volatility: 현재 변동성 (ATR% 등)

        Returns:
            슬리피지 비율 (0.01 = 1%)
        """
        # 기본 슬리피지
        slippage = self.base_slippage_pct / 100

        # 볼륨 영향 (주문 크기 / 평균 거래량)
        if avg_volume > 0:
            volume_ratio = order_size / avg_volume
            volume_impact = volume_ratio * self.volume_impact_factor
            slippage += volume_impact

        # 변동성 영향
        if volatility > 0:
            volatility_impact = volatility * self.volatility_impact_factor / 100
            slippage += volatility_impact

        # 최대값 제한
        max_slip = self.max_slippage_pct / 100
        slippage = min(slippage, max_slip)

        return slippage

    def apply_to_price(
        self,
        price: float,
        side: str,
        order_size: float,
        avg_volume: float,
        volatility: float = 0.0,
    ) -> float:
        """가격에 슬리피지 적용

        Args:
            price: 원래 가격
            side: "LONG" (매수) 또는 "SHORT" (매도)
            order_size: 주문 크기
            avg_volume: 평균 거래량
            volatility: 변동성

        Returns:
            슬리피지가 적용된 가격
        """
        slippage_pct = self.calculate_slippage(order_size, avg_volume, volatility)

        # LONG (매수): 가격 상승 (불리)
        # SHORT (매도): 가격 하락 (불리)
        if side == "LONG":
            return price * (1 + slippage_pct)
        else:  # SHORT
            return price * (1 - slippage_pct)


@dataclass
class MarketImpactModel:
    """시장 영향 모델

    대량 주문이 시장에 미치는 영향을 모델링합니다.

    Attributes:
        impact_coefficient: 영향 계수
        decay_factor: 영향 감소 계수
    """

    impact_coefficient: float = 0.1
    decay_factor: float = 0.5

    def calculate_impact(
        self,
        order_size: float,
        market_depth: float,
    ) -> float:
        """시장 영향 계산

        Args:
            order_size: 주문 크기
            market_depth: 시장 깊이 (호가창 깊이)

        Returns:
            가격 영향 비율
        """
        if market_depth <= 0:
            return 0.0

        # 선형 영향 모델
        impact = self.impact_coefficient * (order_size / market_depth)

        return min(impact, 0.05)  # 최대 5% 영향


def calculate_realistic_entry_price(
    candle: Dict,
    side: str,
    slippage_model: Optional[SlippageModel] = None,
    order_size: float = 1000.0,
    avg_volume: float = 10000.0,
) -> float:
    """현실적인 진입 가격 계산

    종가 대신 high/low를 고려한 진입 가격

    Args:
        candle: 캔들 데이터 (open, high, low, close, volume)
        side: "LONG" 또는 "SHORT"
        slippage_model: 슬리피지 모델
        order_size: 주문 크기
        avg_volume: 평균 거래량

    Returns:
        현실적인 진입 가격
    """
    close_price = candle["close"]
    high_price = candle["high"]
    low_price = candle["low"]

    # LONG: 종가와 고가의 중간 (약간 불리하게)
    # SHORT: 종가와 저가의 중간 (약간 불리하게)
    if side == "LONG":
        # 종가보다 약간 높은 가격으로 진입
        base_price = close_price + (high_price - close_price) * 0.3
    else:  # SHORT
        # 종가보다 약간 낮은 가격으로 진입
        base_price = close_price - (close_price - low_price) * 0.3

    # 슬리피지 적용
    if slippage_model:
        volatility = (high_price - low_price) / close_price * 100  # ATR%
        return slippage_model.apply_to_price(
            base_price, side, order_size, avg_volume, volatility
        )

    return base_price


def calculate_realistic_exit_price(
    candle: Dict,
    position_side: str,
    exit_reason: str,
    entry_price: float,
    tp_pct: float = 0.01,
    sl_pct: float = 0.005,
) -> float:
    """현실적인 청산 가격 계산

    TP/SL은 정확한 가격이 아닌 high/low 기준으로 체결

    Args:
        candle: 캔들 데이터
        position_side: 포지션 방향 ("LONG" 또는 "SHORT")
        exit_reason: 청산 사유 ("TP", "SL", "TIMECUT", etc.)
        entry_price: 진입 가격
        tp_pct: 익절 비율
        sl_pct: 손절 비율

    Returns:
        현실적인 청산 가격
    """
    high_price = candle["high"]
    low_price = candle["low"]
    close_price = candle["close"]

    if position_side == "LONG":
        tp_target = entry_price * (1 + tp_pct)
        sl_target = entry_price * (1 - sl_pct)

        if exit_reason == "TP":
            # TP는 고가에 도달해야 체결
            if high_price >= tp_target:
                return tp_target
            return close_price
        elif exit_reason == "SL":
            # SL은 저가에 도달해야 체결
            if low_price <= sl_target:
                return sl_target
            return close_price
        else:
            return close_price

    else:  # SHORT
        tp_target = entry_price * (1 - tp_pct)
        sl_target = entry_price * (1 + sl_pct)

        if exit_reason == "TP":
            # TP는 저가에 도달해야 체결
            if low_price <= tp_target:
                return tp_target
            return close_price
        elif exit_reason == "SL":
            # SL은 고가에 도달해야 체결
            if high_price >= sl_target:
                return sl_target
            return close_price
        else:
            return close_price
