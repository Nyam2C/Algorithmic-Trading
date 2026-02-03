"""
지표 기반 스코어링 시스템

Phase 6.3: AI 앙상블 - 지표 스코어링
- RSI, MA, Volume, ATR 기반 점수 계산
- 종합 점수로 신호 생성
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class IndicatorScore:
    """개별 지표 점수

    Attributes:
        name: 지표 이름
        value: 지표 값
        score: 점수 (-1 ~ 1, 음수=SHORT, 양수=LONG)
        weight: 가중치
        reason: 점수 산정 이유
    """

    name: str
    value: float
    score: float  # -1 to 1
    weight: float = 1.0
    reason: str = ""

    def weighted_score(self) -> float:
        """가중 점수 반환"""
        return self.score * self.weight


@dataclass
class ScoringResult:
    """스코어링 결과

    Attributes:
        total_score: 총점 (-1 ~ 1)
        signal: 생성된 신호
        confidence: 신뢰도 (0 ~ 1)
        indicator_scores: 개별 지표 점수 목록
        reasons: 주요 이유 목록
    """

    total_score: float
    signal: str
    confidence: float
    indicator_scores: List[IndicatorScore] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_score": round(self.total_score, 3),
            "signal": self.signal,
            "confidence": round(self.confidence, 3),
            "indicator_scores": [
                {
                    "name": s.name,
                    "value": s.value,
                    "score": round(s.score, 3),
                    "weight": s.weight,
                    "reason": s.reason,
                }
                for s in self.indicator_scores
            ],
            "reasons": self.reasons,
        }


class IndicatorScorer:
    """지표 기반 스코어링

    기술적 지표를 분석하여 점수화합니다.

    Example:
        >>> scorer = IndicatorScorer()
        >>> result = scorer.calculate_score(market_data)
        >>> print(f"Signal: {result.signal}, Score: {result.total_score}")
    """

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        "rsi": 0.25,
        "ma_trend": 0.25,
        "volume": 0.15,
        "atr": 0.10,
        "macd": 0.15,
        "price_position": 0.10,
    }

    # 신호 임계값
    LONG_THRESHOLD = 0.2
    SHORT_THRESHOLD = -0.2

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        long_threshold: float = LONG_THRESHOLD,
        short_threshold: float = SHORT_THRESHOLD,
    ) -> None:
        """스코어러 초기화

        Args:
            weights: 지표별 가중치
            long_threshold: LONG 신호 임계값
            short_threshold: SHORT 신호 임계값
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self._log = logger.bind(module="indicator_scorer")

    def calculate_score(self, market_data: Dict[str, Any]) -> ScoringResult:
        """종합 점수 계산

        Args:
            market_data: 시장 데이터 (지표 포함)

        Returns:
            ScoringResult
        """
        scores: List[IndicatorScore] = []
        reasons: List[str] = []

        # RSI 점수
        if "rsi" in market_data:
            rsi_score = self._score_rsi(market_data["rsi"])
            scores.append(rsi_score)
            if abs(rsi_score.score) > 0.5:
                reasons.append(rsi_score.reason)

        # MA 추세 점수
        if "ma_7" in market_data and "ma_25" in market_data:
            ma_score = self._score_ma_trend(market_data)
            scores.append(ma_score)
            if abs(ma_score.score) > 0.5:
                reasons.append(ma_score.reason)

        # 볼륨 점수
        if "volume_ratio" in market_data:
            volume_score = self._score_volume(market_data["volume_ratio"])
            scores.append(volume_score)

        # ATR 점수
        if "atr_pct" in market_data:
            atr_score = self._score_atr(market_data["atr_pct"])
            scores.append(atr_score)

        # MACD 점수
        if "macd" in market_data and "macd_signal" in market_data:
            macd_score = self._score_macd(market_data)
            scores.append(macd_score)
            if abs(macd_score.score) > 0.5:
                reasons.append(macd_score.reason)

        # 가격 위치 점수
        if "price_vs_ma25_pct" in market_data:
            position_score = self._score_price_position(market_data)
            scores.append(position_score)

        # 총점 계산
        total_weight = sum(s.weight for s in scores)
        if total_weight > 0:
            total_score = sum(s.weighted_score() for s in scores) / total_weight
        else:
            total_score = 0.0

        # 신호 결정
        signal = self._determine_signal(total_score)

        # 신뢰도 계산 (점수의 절대값)
        confidence = min(abs(total_score), 1.0)

        return ScoringResult(
            total_score=total_score,
            signal=signal,
            confidence=confidence,
            indicator_scores=scores,
            reasons=reasons[:3],  # 상위 3개 이유만
        )

    def _score_rsi(self, rsi: float) -> IndicatorScore:
        """RSI 점수 계산

        - RSI < 30: 강한 LONG 신호 (+0.8 ~ +1.0)
        - RSI 30-40: 약한 LONG 신호 (+0.3 ~ +0.8)
        - RSI 40-60: 중립 (0)
        - RSI 60-70: 약한 SHORT 신호 (-0.3 ~ -0.8)
        - RSI > 70: 강한 SHORT 신호 (-0.8 ~ -1.0)
        """
        if rsi < 20:
            score = 1.0
            reason = f"RSI 극단적 과매도 ({rsi:.1f})"
        elif rsi < 30:
            score = 0.8 + (30 - rsi) / 50
            reason = f"RSI 과매도 ({rsi:.1f})"
        elif rsi < 40:
            score = 0.3 + (40 - rsi) / 25
            reason = f"RSI 저점 근접 ({rsi:.1f})"
        elif rsi <= 60:
            score = 0.0
            reason = f"RSI 중립 ({rsi:.1f})"
        elif rsi <= 70:
            score = -0.3 - (rsi - 60) / 25
            reason = f"RSI 고점 근접 ({rsi:.1f})"
        elif rsi <= 80:
            score = -0.8 - (rsi - 70) / 50
            reason = f"RSI 과매수 ({rsi:.1f})"
        else:
            score = -1.0
            reason = f"RSI 극단적 과매수 ({rsi:.1f})"

        return IndicatorScore(
            name="rsi",
            value=rsi,
            score=score,
            weight=self.weights.get("rsi", 0.25),
            reason=reason,
        )

    def _score_ma_trend(self, data: Dict[str, Any]) -> IndicatorScore:
        """MA 추세 점수 계산

        - MA7 > MA25 > MA99: 강한 상승 추세 (+0.8)
        - MA7 > MA25: 상승 추세 (+0.5)
        - MA7 < MA25 < MA99: 강한 하락 추세 (-0.8)
        - MA7 < MA25: 하락 추세 (-0.5)
        """
        ma7 = data.get("ma_7", 0)
        ma25 = data.get("ma_25", 0)
        ma99 = data.get("ma_99")

        if ma7 == 0 or ma25 == 0:
            return IndicatorScore(
                name="ma_trend",
                value=0,
                score=0,
                weight=self.weights.get("ma_trend", 0.25),
                reason="MA 데이터 부족",
            )

        # MA 정렬 확인
        if ma99:
            if ma7 > ma25 > ma99:
                score = 0.8
                reason = "MA 완전 상승 정렬 (MA7>MA25>MA99)"
            elif ma7 < ma25 < ma99:
                score = -0.8
                reason = "MA 완전 하락 정렬 (MA7<MA25<MA99)"
            elif ma7 > ma25:
                score = 0.5
                reason = "MA 상승 추세 (MA7>MA25)"
            elif ma7 < ma25:
                score = -0.5
                reason = "MA 하락 추세 (MA7<MA25)"
            else:
                score = 0.0
                reason = "MA 혼재"
        else:
            if ma7 > ma25:
                score = 0.5
                reason = "MA 상승 추세 (MA7>MA25)"
            elif ma7 < ma25:
                score = -0.5
                reason = "MA 하락 추세 (MA7<MA25)"
            else:
                score = 0.0
                reason = "MA 중립"

        return IndicatorScore(
            name="ma_trend",
            value=ma7 / ma25 if ma25 else 0,
            score=score,
            weight=self.weights.get("ma_trend", 0.25),
            reason=reason,
        )

    def _score_volume(self, volume_ratio: float) -> IndicatorScore:
        """볼륨 점수 계산

        볼륨 증가는 추세 확인 (점수 증폭 효과로 사용)
        """
        if volume_ratio > 2.0:
            score = 0.5  # 강한 볼륨 - 추세 확인
            reason = f"높은 거래량 ({volume_ratio:.1f}x)"
        elif volume_ratio > 1.5:
            score = 0.3
            reason = f"증가한 거래량 ({volume_ratio:.1f}x)"
        elif volume_ratio > 0.8:
            score = 0.0
            reason = f"보통 거래량 ({volume_ratio:.1f}x)"
        else:
            score = -0.2  # 낮은 볼륨 - 신뢰도 감소
            reason = f"낮은 거래량 ({volume_ratio:.1f}x)"

        return IndicatorScore(
            name="volume",
            value=volume_ratio,
            score=score,
            weight=self.weights.get("volume", 0.15),
            reason=reason,
        )

    def _score_atr(self, atr_pct: float) -> IndicatorScore:
        """ATR 점수 계산

        변동성이 너무 높거나 낮으면 진입 회피
        """
        if atr_pct > 3.0:
            score = -0.3  # 높은 변동성 - 위험
            reason = f"높은 변동성 (ATR {atr_pct:.1f}%)"
        elif atr_pct > 1.5:
            score = 0.2  # 적정 변동성
            reason = f"적정 변동성 (ATR {atr_pct:.1f}%)"
        elif atr_pct > 0.5:
            score = 0.0
            reason = f"낮은 변동성 (ATR {atr_pct:.1f}%)"
        else:
            score = -0.2  # 너무 낮은 변동성 - 기회 부족
            reason = f"매우 낮은 변동성 (ATR {atr_pct:.1f}%)"

        return IndicatorScore(
            name="atr",
            value=atr_pct,
            score=score,
            weight=self.weights.get("atr", 0.10),
            reason=reason,
        )

    def _score_macd(self, data: Dict[str, Any]) -> IndicatorScore:
        """MACD 점수 계산

        - MACD > Signal: 상승 모멘텀 (+)
        - MACD < Signal: 하락 모멘텀 (-)
        - Histogram 크기로 강도 결정
        """
        macd = data.get("macd", 0)
        signal = data.get("macd_signal", 0)
        histogram = data.get("macd_histogram", macd - signal)

        if histogram > 0:
            # 상승 모멘텀
            if histogram > 50:
                score = 0.8
                reason = "강한 상승 모멘텀 (MACD)"
            else:
                score = 0.3 + min(histogram / 100, 0.5)
                reason = "상승 모멘텀 (MACD)"
        elif histogram < 0:
            # 하락 모멘텀
            if histogram < -50:
                score = -0.8
                reason = "강한 하락 모멘텀 (MACD)"
            else:
                score = -0.3 + max(histogram / 100, -0.5)
                reason = "하락 모멘텀 (MACD)"
        else:
            score = 0.0
            reason = "MACD 중립"

        return IndicatorScore(
            name="macd",
            value=histogram,
            score=score,
            weight=self.weights.get("macd", 0.15),
            reason=reason,
        )

    def _score_price_position(self, data: Dict[str, Any]) -> IndicatorScore:
        """가격 위치 점수 계산

        가격이 MA25 대비 위치
        """
        pct = data.get("price_vs_ma25_pct", 0)

        # 너무 높거나 낮으면 회귀 가능성
        if pct > 3:
            score = -0.3  # 과열 - SHORT 신호
            reason = f"가격이 MA25 위 {pct:.1f}% (과열)"
        elif pct > 1:
            score = 0.2  # 상승 추세 확인
            reason = f"가격이 MA25 위 {pct:.1f}%"
        elif pct < -3:
            score = 0.3  # 과매도 - LONG 신호
            reason = f"가격이 MA25 아래 {abs(pct):.1f}% (과매도)"
        elif pct < -1:
            score = -0.2  # 하락 추세 확인
            reason = f"가격이 MA25 아래 {abs(pct):.1f}%"
        else:
            score = 0.0
            reason = "가격이 MA25 근처"

        return IndicatorScore(
            name="price_position",
            value=pct,
            score=score,
            weight=self.weights.get("price_position", 0.10),
            reason=reason,
        )

    def _determine_signal(self, total_score: float) -> str:
        """신호 결정

        Args:
            total_score: 총점

        Returns:
            "LONG", "SHORT", 또는 "WAIT"
        """
        if total_score >= self.long_threshold:
            return "LONG"
        elif total_score <= self.short_threshold:
            return "SHORT"
        else:
            return "WAIT"

    def get_signal(self, market_data: Dict[str, Any]) -> str:
        """신호만 반환 (간단한 인터페이스)

        Args:
            market_data: 시장 데이터

        Returns:
            "LONG", "SHORT", 또는 "WAIT"
        """
        result = self.calculate_score(market_data)
        return result.signal

    def get_signal_with_reason(
        self, market_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """신호와 이유 반환

        Args:
            market_data: 시장 데이터

        Returns:
            (signal, reason) 튜플
        """
        result = self.calculate_score(market_data)
        reason = ", ".join(result.reasons) if result.reasons else "점수 기반 분석"
        return result.signal, reason
