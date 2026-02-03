"""
다중 타임프레임 분석 모듈

Phase 6.4: 다중 타임프레임 확인
- 상위 TF(15분봉)로 추세 확인
- 시그널과 상위 TF 추세 정렬 여부 판단
"""
from enum import Enum
from typing import Dict, Tuple
from loguru import logger


class TimeframeAlignment(Enum):
    """타임프레임 정렬 상태"""
    ALIGNED = "aligned"        # 시그널과 상위 TF 추세 일치
    CONFLICTING = "conflicting"  # 시그널과 상위 TF 추세 충돌
    NEUTRAL = "neutral"        # 판단 불가 또는 WAIT 시그널


class MultiTimeframeAnalyzer:
    """다중 타임프레임 분석기

    상위 타임프레임(15분봉 등)의 추세를 확인하여
    하위 타임프레임 시그널을 필터링합니다.

    Attributes:
        tolerance_pct: MA25 근처 허용 범위 (%)
        strict_mode: True면 MA 정렬까지 확인

    Example:
        >>> analyzer = MultiTimeframeAnalyzer()
        >>> filtered = analyzer.filter_signal("LONG", higher_tf_data)
        >>> if filtered == "WAIT":
        ...     print("상위 TF와 충돌 - 진입 안함")
    """

    def __init__(
        self,
        tolerance_pct: float = 0.1,
        strict_mode: bool = False,
    ) -> None:
        """분석기 초기화

        Args:
            tolerance_pct: MA25 근처 허용 범위 (%) - 이 범위 내면 중립 처리
            strict_mode: True면 MA7 > MA25 > MA99 정렬까지 확인
        """
        self.tolerance_pct = tolerance_pct
        self.strict_mode = strict_mode

        logger.debug(
            f"MultiTimeframeAnalyzer 초기화: tolerance={tolerance_pct}%, "
            f"strict_mode={strict_mode}"
        )

    def check_alignment(
        self,
        signal: str,
        higher_tf_data: Dict,
    ) -> TimeframeAlignment:
        """시그널과 상위 TF 추세 정렬 확인

        Args:
            signal: 하위 TF 시그널 ("LONG", "SHORT", "WAIT")
            higher_tf_data: 상위 TF 시장 데이터

        Returns:
            TimeframeAlignment
        """
        if signal == "WAIT":
            return TimeframeAlignment.NEUTRAL

        # 필수 데이터 확인
        ma_25 = higher_tf_data.get("ma_25")
        current_price = higher_tf_data.get("current_price") or higher_tf_data.get("price")

        if ma_25 is None or current_price is None:
            logger.warning("상위 TF 데이터 부족 - NEUTRAL 반환")
            return TimeframeAlignment.NEUTRAL

        # 가격과 MA25 비교
        price_vs_ma = (current_price - ma_25) / ma_25 * 100

        # 허용 범위 내면 중립
        if abs(price_vs_ma) <= self.tolerance_pct:
            return TimeframeAlignment.NEUTRAL

        is_higher_bullish = current_price > ma_25
        is_higher_bearish = current_price < ma_25

        # 엄격 모드: MA 정렬 확인
        if self.strict_mode:
            ma_bullish, ma_bearish = self.check_ma_alignment(higher_tf_data)
            if signal == "LONG" and not ma_bullish:
                return TimeframeAlignment.CONFLICTING
            if signal == "SHORT" and not ma_bearish:
                return TimeframeAlignment.CONFLICTING

        # 정렬 확인
        if signal == "LONG":
            if is_higher_bullish:
                return TimeframeAlignment.ALIGNED
            else:
                return TimeframeAlignment.CONFLICTING

        if signal == "SHORT":
            if is_higher_bearish:
                return TimeframeAlignment.ALIGNED
            else:
                return TimeframeAlignment.CONFLICTING

        return TimeframeAlignment.NEUTRAL

    def check_ma_alignment(
        self,
        higher_tf_data: Dict,
    ) -> Tuple[bool, bool]:
        """MA 정렬 확인

        Args:
            higher_tf_data: 상위 TF 시장 데이터

        Returns:
            (is_bullish_aligned, is_bearish_aligned)
        """
        ma_7 = higher_tf_data.get("ma_7")
        ma_25 = higher_tf_data.get("ma_25")
        ma_99 = higher_tf_data.get("ma_99")

        if ma_7 is None or ma_25 is None or ma_99 is None:
            return False, False

        is_bullish: bool = ma_7 > ma_25 > ma_99
        is_bearish: bool = ma_7 < ma_25 < ma_99

        return is_bullish, is_bearish

    def filter_signal(
        self,
        signal: str,
        higher_tf_data: Dict,
    ) -> str:
        """시그널 필터링

        상위 TF와 충돌하는 시그널을 WAIT로 변환합니다.

        Args:
            signal: 하위 TF 시그널
            higher_tf_data: 상위 TF 시장 데이터

        Returns:
            필터링된 시그널 ("LONG", "SHORT", "WAIT")
        """
        if signal == "WAIT":
            return signal

        alignment = self.check_alignment(signal, higher_tf_data)

        if alignment == TimeframeAlignment.CONFLICTING:
            logger.info(
                f"MTF 필터: {signal} 시그널이 상위 TF와 충돌 → WAIT"
            )
            return "WAIT"

        return signal

    def get_higher_tf_trend(
        self,
        higher_tf_data: Dict,
    ) -> str:
        """상위 TF 추세 반환

        Args:
            higher_tf_data: 상위 TF 시장 데이터

        Returns:
            "BULLISH", "BEARISH", "NEUTRAL"
        """
        ma_25 = higher_tf_data.get("ma_25")
        current_price = higher_tf_data.get("current_price") or higher_tf_data.get("price")

        if ma_25 is None or current_price is None:
            return "NEUTRAL"

        price_vs_ma = (current_price - ma_25) / ma_25 * 100

        if abs(price_vs_ma) <= self.tolerance_pct:
            return "NEUTRAL"

        if current_price > ma_25:
            return "BULLISH"
        else:
            return "BEARISH"

    def get_analysis_info(
        self,
        signal: str,
        higher_tf_data: Dict,
    ) -> Dict:
        """분석 정보 반환

        Args:
            signal: 하위 TF 시그널
            higher_tf_data: 상위 TF 시장 데이터

        Returns:
            분석 정보 딕셔너리
        """
        alignment = self.check_alignment(signal, higher_tf_data)
        trend = self.get_higher_tf_trend(higher_tf_data)
        ma_bullish, ma_bearish = self.check_ma_alignment(higher_tf_data)

        return {
            "signal": signal,
            "alignment": alignment.value,
            "higher_tf_trend": trend,
            "ma_bullish_aligned": ma_bullish,
            "ma_bearish_aligned": ma_bearish,
            "filtered_signal": self.filter_signal(signal, higher_tf_data),
        }
