"""
마켓 레짐 감지 모듈

Phase 6.2: 마켓 레짐 감지 (횡보 vs 추세)
- MA 정렬과 ATR로 시장 상태 분류
- 횡보장에서는 진입 회피
"""
from enum import Enum
from typing import Dict
from loguru import logger


class MarketRegime(Enum):
    """마켓 레짐 (시장 상태)"""
    STRONG_UPTREND = "strong_uptrend"      # 강한 상승 추세
    WEAK_UPTREND = "weak_uptrend"          # 약한 상승 추세
    RANGING = "ranging"                     # 횡보장 (레인지)
    WEAK_DOWNTREND = "weak_downtrend"      # 약한 하락 추세
    STRONG_DOWNTREND = "strong_downtrend"  # 강한 하락 추세
    UNKNOWN = "unknown"                     # 알 수 없음


class RegimeDetector:
    """마켓 레짐 감지기

    이동평균(MA)과 ATR을 사용하여 현재 시장 상태를 분류합니다.

    분류 기준:
    - MA 정렬: MA7 > MA25 > MA99 → 상승, 역순 → 하락
    - ATR 비율: ATR/가격 비율로 변동성 측정
    - 변동성 낮고 MA 혼재 → 횡보장

    Attributes:
        atr_strong_threshold: 강한 추세 ATR 비율 임계값 (기본 1.0%)
        atr_weak_threshold: 약한 추세 ATR 비율 임계값 (기본 0.5%)

    Example:
        >>> detector = RegimeDetector()
        >>> regime = detector.detect(market_data)
        >>> if regime == MarketRegime.RANGING:
        ...     signal = "WAIT"
    """

    def __init__(
        self,
        atr_strong_threshold: float = 1.0,  # 1%
        atr_weak_threshold: float = 0.5,    # 0.5%
    ) -> None:
        """레짐 감지기 초기화

        Args:
            atr_strong_threshold: 강한 추세 ATR 비율 임계값 (%)
            atr_weak_threshold: 약한 추세 ATR 비율 임계값 (%)
        """
        self.atr_strong_threshold = atr_strong_threshold
        self.atr_weak_threshold = atr_weak_threshold

        logger.debug(
            f"RegimeDetector 초기화: strong_threshold={atr_strong_threshold}%, "
            f"weak_threshold={atr_weak_threshold}%"
        )

    def detect(self, market_data: Dict) -> MarketRegime:
        """마켓 레짐 감지

        Args:
            market_data: 시장 데이터 (ma_7, ma_25, ma_99, atr, price 등)

        Returns:
            MarketRegime enum
        """
        try:
            # 필수 데이터 추출
            ma_7 = market_data.get("ma_7")
            ma_25 = market_data.get("ma_25")
            ma_99 = market_data.get("ma_99")
            atr = market_data.get("atr")
            price = market_data.get("price") or market_data.get("current_price")

            # 데이터 검증
            if not all([ma_7, ma_25, ma_99]):
                logger.warning("MA 데이터 부족, UNKNOWN 반환")
                return MarketRegime.UNKNOWN

            # ATR 비율 계산 (%)
            atr_pct = 0.0
            if atr and price and price > 0:
                atr_pct = (atr / price) * 100
            else:
                # ATR 데이터가 없으면 atr_pct로 시도
                atr_pct = market_data.get("atr_pct", 0.0)

            # MA 정렬 확인 (mypy: None 체크는 위에서 완료)
            assert ma_7 is not None and ma_25 is not None and ma_99 is not None
            is_bullish_aligned = ma_7 > ma_25 > ma_99  # 상승 정렬
            is_bearish_aligned = ma_7 < ma_25 < ma_99  # 하락 정렬

            # 레짐 결정
            regime = self._determine_regime(
                is_bullish_aligned, is_bearish_aligned, atr_pct
            )

            logger.info(
                f"마켓 레짐: {regime.value} "
                f"(MA7={ma_7:.2f}, MA25={ma_25:.2f}, MA99={ma_99:.2f}, ATR%={atr_pct:.2f}%)"
            )

            return regime

        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return MarketRegime.UNKNOWN

    def _determine_regime(
        self,
        is_bullish_aligned: bool,
        is_bearish_aligned: bool,
        atr_pct: float,
    ) -> MarketRegime:
        """레짐 결정 로직

        Args:
            is_bullish_aligned: MA 상승 정렬 여부
            is_bearish_aligned: MA 하락 정렬 여부
            atr_pct: ATR 비율 (%)

        Returns:
            MarketRegime
        """
        is_strong = atr_pct >= self.atr_strong_threshold

        if is_bullish_aligned:
            if is_strong:
                return MarketRegime.STRONG_UPTREND
            return MarketRegime.WEAK_UPTREND

        if is_bearish_aligned:
            if is_strong:
                return MarketRegime.STRONG_DOWNTREND
            return MarketRegime.WEAK_DOWNTREND

        # MA가 혼재된 상태 (정렬 안 됨)
        return MarketRegime.RANGING

    def filter_signal(
        self,
        signal: str,
        regime: MarketRegime,
        allow_weak_trend: bool = True,
    ) -> str:
        """레짐에 따라 시그널 필터링

        Args:
            signal: 원본 시그널 ("LONG", "SHORT", "WAIT")
            regime: 현재 마켓 레짐
            allow_weak_trend: 약한 추세에서 거래 허용 여부

        Returns:
            필터링된 시그널
        """
        if signal == "WAIT":
            return signal

        # 횡보장에서는 진입 안 함
        if regime == MarketRegime.RANGING:
            logger.info(f"횡보장 - {signal} 시그널 무시 → WAIT")
            return "WAIT"

        # 알 수 없는 상태에서도 보수적으로
        if regime == MarketRegime.UNKNOWN:
            logger.info(f"레짐 불명 - {signal} 시그널 무시 → WAIT")
            return "WAIT"

        # 약한 추세 허용 여부
        if not allow_weak_trend:
            if regime in (MarketRegime.WEAK_UPTREND, MarketRegime.WEAK_DOWNTREND):
                logger.info(f"약한 추세 - {signal} 시그널 무시 → WAIT")
                return "WAIT"

        # 강한 상승 추세에서 SHORT는 위험
        if regime == MarketRegime.STRONG_UPTREND and signal == "SHORT":
            logger.info("강한 상승 추세 - SHORT 시그널 무시 → WAIT")
            return "WAIT"

        # 강한 하락 추세에서 LONG는 위험
        if regime == MarketRegime.STRONG_DOWNTREND and signal == "LONG":
            logger.info("강한 하락 추세 - LONG 시그널 무시 → WAIT")
            return "WAIT"

        # 추세 방향과 일치하는 시그널은 허용
        return signal

    def get_regime_info(self, regime: MarketRegime) -> Dict:
        """레짐 정보 반환

        Args:
            regime: 마켓 레짐

        Returns:
            레짐 정보 딕셔너리
        """
        info = {
            MarketRegime.STRONG_UPTREND: {
                "name": "강한 상승 추세",
                "description": "MA 상승 정렬 + 높은 변동성",
                "recommended_action": "LONG 선호, SHORT 회피",
                "risk_level": "medium",
            },
            MarketRegime.WEAK_UPTREND: {
                "name": "약한 상승 추세",
                "description": "MA 상승 정렬 + 낮은 변동성",
                "recommended_action": "조심스러운 LONG 가능",
                "risk_level": "low",
            },
            MarketRegime.RANGING: {
                "name": "횡보장",
                "description": "MA 혼재, 방향성 불명확",
                "recommended_action": "진입 회피, 관망",
                "risk_level": "high",
            },
            MarketRegime.WEAK_DOWNTREND: {
                "name": "약한 하락 추세",
                "description": "MA 하락 정렬 + 낮은 변동성",
                "recommended_action": "조심스러운 SHORT 가능",
                "risk_level": "low",
            },
            MarketRegime.STRONG_DOWNTREND: {
                "name": "강한 하락 추세",
                "description": "MA 하락 정렬 + 높은 변동성",
                "recommended_action": "SHORT 선호, LONG 회피",
                "risk_level": "medium",
            },
            MarketRegime.UNKNOWN: {
                "name": "알 수 없음",
                "description": "데이터 부족",
                "recommended_action": "진입 회피, 데이터 확인",
                "risk_level": "high",
            },
        }

        return info.get(regime, info[MarketRegime.UNKNOWN])
