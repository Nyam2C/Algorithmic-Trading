"""Market Tradability Index (MTI) — Gate 0.

APEX-V Phase A: 시장 거래 적합성 판단.
RSA 대비 단순화 — L2 데이터 불필요:
- volatility_score (33%): ATR% 히스토리컬 분포 기반
- session_score (33%): UTC 시간대 (US:100, EU:90, ASIA:70, DeepNight:55)
- volume_score (33%): 현재/평균 볼륨 비율

>=70 OPTIMAL | 40~69 REDUCED | <40 STANDBY(진입 차단)
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

# Tradability 등급 상수
OPTIMAL_THRESHOLD = 70
REDUCED_THRESHOLD = 40

# 이유 판단 기준 점수
_REASON_VOL_THRESHOLD = 50
_REASON_SESS_THRESHOLD = 70
_REASON_VOLRATIO_THRESHOLD = 50

# 세션 시간 경계 (UTC)
_ASIA_END = 8       # 00:00~08:00
_EU_END = 13        # 08:00~13:00
_US_END = 21        # 13:00~21:00

# 볼륨 비율 구간 경계
_VOL_VERY_LOW = 0.3
_VOL_LOW = 0.7
_VOL_HIGH = 1.5

# 스프레드 구간 경계
_SPREAD_LOW = 0.5   # < 0.5% → 100점
_SPREAD_HIGH = 2.0  # > 2.0% → 20점

# 세션별 점수 (UTC 시간 기준)
SESSION_SCORES = {
    "US": 100,        # 13:30~21:00 UTC (NYSE open)
    "EU": 90,         # 07:00~15:30 UTC (LSE open)
    "ASIA": 70,       # 00:00~08:00 UTC (Tokyo/HK)
    "DEEP_NIGHT": 55, # 21:00~00:00 UTC (low liquidity)
}

# ATR% 분포 기반 변동성 점수 매핑
# ATR% < 0.3: 저변동성 (30점), 0.3~0.8: 적정 (80점)
# 0.8~1.5: 고변동성 (100점), >1.5: 과변동 (60점)
VOLATILITY_BANDS = [
    (0.3, 30),    # 매우 낮은 변동성 -> 거래 기회 부족
    (0.8, 80),    # 적정 변동성
    (1.5, 100),   # 높은 변동성 -> 최적
    (float("inf"), 60),  # 과도한 변동성 -> 리스크 증가
]


@dataclass
class TradabilityScore:
    """거래 적합성 점수.

    Attributes:
        total_score: 종합 점수 (0-100)
        is_tradable: 거래 가능 여부 (>= 40)
        grade: 등급 (OPTIMAL/REDUCED/STANDBY)
        components: 세부 점수
        reason: 판단 근거
    """
    total_score: float
    is_tradable: bool
    grade: str
    components: dict
    reason: str


class MarketTradabilityIndex:
    """Gate 0: 시장 거래 적합성 판단.

    세 가지 요소를 동일 가중치(33%)로 결합하여
    현재 시장이 거래에 적합한지 판단합니다.

    Example:
        >>> mti = MarketTradabilityIndex()
        >>> score = mti.evaluate(atr_pct=0.8, volume_ratio=1.2)
        >>> if not score.is_tradable:
        ...     signal = "WAIT"
    """

    def __init__(
        self,
        optimal_threshold: float = OPTIMAL_THRESHOLD,
        reduced_threshold: float = REDUCED_THRESHOLD,
    ) -> None:
        """MTI 초기화.

        Args:
            optimal_threshold: OPTIMAL 등급 임계값 (기본 70)
            reduced_threshold: REDUCED/STANDBY 경계 (기본 40)
        """
        self.optimal_threshold = optimal_threshold
        self.reduced_threshold = reduced_threshold

    def evaluate(
        self,
        atr_pct: float,
        volume_ratio: float,
        current_time: datetime | None = None,
        bid_ask_spread_pct: float | None = None,
    ) -> TradabilityScore:
        """시장 거래 적합성 평가.

        Args:
            atr_pct: ATR 퍼센트 (ATR/price * 100)
            volume_ratio: 현재 볼륨 / 평균 볼륨
            current_time: 평가 시간 (기본: 현재 UTC)
            bid_ask_spread_pct: 호가 스프레드 % (제공 시 5요소 모드)

        Returns:
            TradabilityScore
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        vol_score = self._volatility_score(atr_pct)
        sess_score = self._session_score(current_time)
        vol_ratio_score = self._volume_score(volume_ratio)

        if bid_ask_spread_pct is not None:
            # 5요소: Spread/Volume/Volatility/Event/Session 각 20%
            spread_score = self._spread_score(bid_ask_spread_pct)
            event_score = 80.0  # 정적 기본값 (캘린더 미연동)
            total = (
                spread_score + vol_ratio_score + vol_score
                + event_score + sess_score
            ) / 5
            components = {
                "volatility_score": round(vol_score, 1),
                "session_score": round(sess_score, 1),
                "volume_score": round(vol_ratio_score, 1),
                "spread_score": round(spread_score, 1),
                "event_score": round(event_score, 1),
            }
        else:
            # 기존 3요소 모드 (하위호환)
            total = (vol_score + sess_score + vol_ratio_score) / 3
            components = {
                "volatility_score": round(vol_score, 1),
                "session_score": round(sess_score, 1),
                "volume_score": round(vol_ratio_score, 1),
            }

        grade = self._determine_grade(total)
        is_tradable = total >= self.reduced_threshold

        reasons = []
        if vol_score < _REASON_VOL_THRESHOLD:
            reasons.append(
                f"변동성 부족 (ATR%={atr_pct:.2f})"
            )
        if sess_score < _REASON_SESS_THRESHOLD:
            session = self._get_session_name(current_time)
            reasons.append(f"비활성 세션 ({session})")
        if vol_ratio_score < _REASON_VOLRATIO_THRESHOLD:
            reasons.append(
                f"거래량 부족 (ratio={volume_ratio:.2f})"
            )
        if bid_ask_spread_pct is not None:
            spread_sc = self._spread_score(bid_ask_spread_pct)
            if spread_sc < _REASON_VOLRATIO_THRESHOLD:
                reasons.append(
                    f"스프레드 과대 (spread={bid_ask_spread_pct:.2f}%)"
                )
        reason = ", ".join(reasons) if reasons else "거래 적합"

        log_extra = ""
        if bid_ask_spread_pct is not None:
            sp = components['spread_score']
            ev = components['event_score']
            log_extra = f", spread={sp:.0f}, event={ev:.0f}"
        logger.info(
            f"MTI 평가: {total:.1f} ({grade}) — "
            f"vol={vol_score:.0f}, sess={sess_score:.0f}, "
            f"vol_ratio={vol_ratio_score:.0f}{log_extra}"
        )

        return TradabilityScore(
            total_score=round(total, 1),
            is_tradable=is_tradable,
            grade=grade,
            components=components,
            reason=reason,
        )

    @staticmethod
    def _spread_score(bid_ask_spread_pct: float) -> float:
        """호가 스프레드 기반 점수.

        Args:
            bid_ask_spread_pct: 스프레드 퍼센트

        Returns:
            점수 (0-100). 낮은 스프레드 = 높은 점수.
        """
        if bid_ask_spread_pct <= 0:
            return 100.0
        if bid_ask_spread_pct < _SPREAD_LOW:
            return 100.0
        if bid_ask_spread_pct <= _SPREAD_HIGH:
            # 0.5~2.0% 구간 선형 보간: 100 → 20
            span = _SPREAD_HIGH - _SPREAD_LOW
            return 100.0 - (bid_ask_spread_pct - _SPREAD_LOW) / span * 80.0
        return 20.0

    def _volatility_score(self, atr_pct: float) -> float:
        """ATR% 기반 변동성 점수.

        Args:
            atr_pct: ATR percentage

        Returns:
            점수 (0-100)
        """
        if atr_pct < 0:
            return 0.0
        for threshold, score in VOLATILITY_BANDS:
            if atr_pct < threshold:
                return float(score)
        return 60.0  # fallback

    def _session_score(self, current_time: datetime) -> float:
        """UTC 시간대 기반 세션 점수.

        Args:
            current_time: UTC datetime

        Returns:
            점수 (0-100)
        """
        session = self._get_session_name(current_time)
        return float(SESSION_SCORES.get(session, 55))

    def _get_session_name(self, current_time: datetime) -> str:
        """UTC 시간 기반 세션 이름 반환."""
        hour = current_time.hour
        if 0 <= hour < _ASIA_END:
            return "ASIA"
        if _ASIA_END <= hour < _EU_END:
            return "EU"
        if _EU_END <= hour < _US_END:
            return "US"
        return "DEEP_NIGHT"  # 21~24

    def _volume_score(self, volume_ratio: float) -> float:
        """볼륨 비율 기반 점수.

        Args:
            volume_ratio: current_volume / avg_volume

        Returns:
            점수 (0-100)
        """
        if volume_ratio <= 0:
            return 0.0
        if volume_ratio < _VOL_VERY_LOW:
            return 20.0
        if volume_ratio < _VOL_LOW:
            return 50.0
        if volume_ratio < 1.0:
            return 70.0
        if volume_ratio < _VOL_HIGH:
            return 90.0
        return 100.0  # >= 1.5x average

    def _determine_grade(self, total_score: float) -> str:
        """등급 결정.

        Args:
            total_score: 종합 점수

        Returns:
            "OPTIMAL", "REDUCED", or "STANDBY"
        """
        if total_score >= self.optimal_threshold:
            return "OPTIMAL"
        if total_score >= self.reduced_threshold:
            return "REDUCED"
        return "STANDBY"
