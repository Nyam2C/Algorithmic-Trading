"""Market Tradability Index (MTI) — Gate 0.

APEX-V 5-Component MTI:
- Spread Quality (25%): 실시간 bid-ask 스프레드 / ATR 정규화
- Depth Liquidity (25%): 오더북 깊이 (bid+ask 합계), bid/ask 불균형 감점
- Volatility Regime (20%): ATR% 히스토리컬 분포 기반
- Event Calendar (15%): 펀딩 정산(8시간 주기) ±30분 감점
- Session Quality (15%): UTC 세션별 점수 + EU+US Overlap

Fallback modes:
- 3-component (하위호환): Volatility(33%) + Session(33%) + Volume(33%)
- 4-component: Spread(30%) + Volatility(25%) + Event(20%) + Session(25%)
- 5-component: Spread(25%) + Depth(25%) + Volatility(20%) + Event(15%) + Session(15%)

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
_EU_US_OVERLAP_END = 14  # 13:00~14:00 EU+US Overlap
_US_END = 21        # 13:00~21:00

# 볼륨 비율 구간 경계
_VOL_VERY_LOW = 0.3
_VOL_LOW = 0.7
_VOL_HIGH = 1.5

# 스프레드 구간 경계 (절대값 모드)
_SPREAD_LOW = 0.5   # < 0.5% → 100점
_SPREAD_HIGH = 2.0  # > 2.0% → 20점

# 스프레드/ATR 비율 구간 (ATR-정규화 모드)
_SPREAD_ATR_LOW = 0.1    # spread/ATR < 10% → 100점
_SPREAD_ATR_HIGH = 0.5   # spread/ATR > 50% → 20점

# Depth 구간 경계 (BTC 수량 기준)
_DEPTH_VERY_LOW = 5.0     # < 5 BTC → 30점
_DEPTH_LOW = 20.0         # < 20 BTC → 60점
_DEPTH_HIGH = 100.0       # < 100 BTC → 90점
# >= 100 BTC → 100점

# Bid/Ask 불균형 감점 임계값
_IMBALANCE_THRESHOLD = 3.0  # bid/ask > 3x or < 1/3x → 감점

# 펀딩 정산 시간 (UTC hours)
_FUNDING_HOURS = (0, 8, 16)
_FUNDING_WINDOW_MINUTES = 30  # ±30분
_ECONOMIC_EVENT_SCORE = 20  # 경제 이벤트 시 점수

# 세션별 점수 (UTC 시간 기준)
SESSION_SCORES = {
    "US": 100,            # 14:00~21:00 UTC (NYSE open)
    "EU_US_OVERLAP": 110, # 13:00~14:00 UTC (최고 유동성)
    "EU": 90,             # 08:00~13:00 UTC (LSE open)
    "ASIA": 70,           # 00:00~08:00 UTC (Tokyo/HK)
    "DEEP_NIGHT": 55,     # 21:00~00:00 UTC (low liquidity)
}

# ATR% 분포 기반 변동성 점수 매핑
VOLATILITY_BANDS = [
    (0.3, 30),    # 매우 낮은 변동성 -> 거래 기회 부족
    (0.8, 80),    # 적정 변동성
    (1.5, 100),   # 높은 변동성 -> 최적
    (float("inf"), 60),  # 과도한 변동성 -> 리스크 증가
]

# 가중치 프리셋
_WEIGHTS_5 = {
    "spread": 0.25, "depth": 0.25, "volatility": 0.20,
    "event": 0.15, "session": 0.15,
}
_WEIGHTS_4 = {
    "spread": 0.30, "volatility": 0.25,
    "event": 0.20, "session": 0.25,
}


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

    5-Component 모드 (WS 데이터 제공 시):
        Spread(25%) + Depth(25%) + Volatility(20%) + Event(15%) + Session(15%)

    3-Component 폴백 (하위호환):
        Volatility(33%) + Session(33%) + Volume(33%)

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
        bid_depth_total: float | None = None,
        ask_depth_total: float | None = None,
        atr_1m_pct: float | None = None,
        event_times: list[datetime] | None = None,
        economic_events: list[tuple[datetime, int]] | None = None,
    ) -> TradabilityScore:
        """시장 거래 적합성 평가.

        Args:
            atr_pct: ATR 퍼센트 (ATR/price * 100)
            volume_ratio: 현재 볼륨 / 평균 볼륨
            current_time: 평가 시간 (기본: 현재 UTC)
            bid_ask_spread_pct: 호가 스프레드 % (제공 시 4/5요소 모드)
            bid_depth_total: 총 bid 수량 (제공 시 5요소 모드)
            ask_depth_total: 총 ask 수량 (제공 시 5요소 모드)
            atr_1m_pct: 1분봉 ATR% (제공 시 spread ATR-정규화)
            event_times: 커스텀 이벤트 시간 리스트 (FOMC 등)
            economic_events: 경제 이벤트 [(event_time, window_min)] 리스트 (선택)

        Returns:
            TradabilityScore
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        vol_score = self._volatility_score(atr_pct)
        sess_score = self._session_score(current_time)
        vol_ratio_score = self._volume_score(volume_ratio)

        if (
            bid_ask_spread_pct is not None
            and bid_depth_total is not None
            and ask_depth_total is not None
        ):
            # 5-component 가중치 적용
            spread_sc = self._spread_score(bid_ask_spread_pct, atr_1m_pct)
            depth_sc = self._depth_score(bid_depth_total, ask_depth_total)
            event_sc = self._event_score(current_time, event_times, economic_events)
            w = _WEIGHTS_5
            total = (
                w["spread"] * spread_sc
                + w["depth"] * depth_sc
                + w["volatility"] * vol_score
                + w["event"] * event_sc
                + w["session"] * sess_score
            )
            components = {
                "spread_score": round(spread_sc, 1),
                "depth_score": round(depth_sc, 1),
                "volatility_score": round(vol_score, 1),
                "event_score": round(event_sc, 1),
                "session_score": round(sess_score, 1),
            }
        elif bid_ask_spread_pct is not None:
            # 4-component: Spread(30%) + Volatility(25%) + Event(20%) + Session(25%)
            spread_sc = self._spread_score(bid_ask_spread_pct, atr_1m_pct)
            event_sc = self._event_score(current_time, event_times, economic_events)
            w = _WEIGHTS_4
            total = (
                w["spread"] * spread_sc
                + w["volatility"] * vol_score
                + w["event"] * event_sc
                + w["session"] * sess_score
            )
            components = {
                "spread_score": round(spread_sc, 1),
                "volatility_score": round(vol_score, 1),
                "event_score": round(event_sc, 1),
                "session_score": round(sess_score, 1),
            }
        else:
            # 3-component 폴백 (하위호환)
            total = (vol_score + sess_score + vol_ratio_score) / 3
            components = {
                "volatility_score": round(vol_score, 1),
                "session_score": round(sess_score, 1),
                "volume_score": round(vol_ratio_score, 1),
            }

        grade = self._determine_grade(total)
        is_tradable = total >= self.reduced_threshold

        reasons = self._build_reasons(
            atr_pct, vol_score, sess_score, vol_ratio_score,
            current_time, bid_ask_spread_pct, atr_1m_pct,
        )
        reason = ", ".join(reasons) if reasons else "거래 적합"

        log_extra = ""
        if "depth_score" in components:
            log_extra = (
                f", spread={components['spread_score']:.0f}"
                f", depth={components['depth_score']:.0f}"
                f", event={components['event_score']:.0f}"
            )
        elif "spread_score" in components:
            log_extra = (
                f", spread={components['spread_score']:.0f}"
                f", event={components['event_score']:.0f}"
            )
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

    def _build_reasons(
        self,
        atr_pct: float,
        vol_score: float,
        sess_score: float,
        vol_ratio_score: float,
        current_time: datetime,
        bid_ask_spread_pct: float | None,
        atr_1m_pct: float | None,
    ) -> list[str]:
        """판단 사유 리스트 생성."""
        reasons: list[str] = []
        if vol_score < _REASON_VOL_THRESHOLD:
            reasons.append(f"변동성 부족 (ATR%={atr_pct:.2f})")
        if sess_score < _REASON_SESS_THRESHOLD:
            session = self._get_session_name(current_time)
            reasons.append(f"비활성 세션 ({session})")
        if vol_ratio_score < _REASON_VOLRATIO_THRESHOLD:
            # volume_ratio는 외부에서 접근 불가하므로 점수로 판단
            reasons.append("거래량 부족")
        if bid_ask_spread_pct is not None:
            spread_sc = self._spread_score(bid_ask_spread_pct, atr_1m_pct)
            if spread_sc < _REASON_VOLRATIO_THRESHOLD:
                reasons.append(
                    f"스프레드 과대 (spread={bid_ask_spread_pct:.2f}%)"
                )
        return reasons

    @staticmethod
    def _spread_score(
        bid_ask_spread_pct: float,
        atr_1m_pct: float | None = None,
    ) -> float:
        """호가 스프레드 기반 점수.

        ATR-정규화: atr_1m_pct 제공 시 spread/ATR 비율로 채점.
        절대값 모드: 미제공 시 기존 구간 매핑.

        Args:
            bid_ask_spread_pct: 스프레드 퍼센트
            atr_1m_pct: 1분봉 ATR% (선택)

        Returns:
            점수 (0-100). 낮은 스프레드 = 높은 점수.
        """
        if bid_ask_spread_pct <= 0:
            return 100.0

        # ATR-정규화 모드: spread/ATR 비율 사용
        if atr_1m_pct is not None and atr_1m_pct > 0:
            value = bid_ask_spread_pct / atr_1m_pct
            low, high = _SPREAD_ATR_LOW, _SPREAD_ATR_HIGH
        else:
            # 절대값 모드 (하위호환)
            value = bid_ask_spread_pct
            low, high = _SPREAD_LOW, _SPREAD_HIGH

        if value < low:
            return 100.0
        if value <= high:
            return 100.0 - (value - low) / (high - low) * 80.0
        return 20.0

    @staticmethod
    def _depth_score(
        bid_depth_total: float,
        ask_depth_total: float,
    ) -> float:
        """오더북 깊이 기반 점수.

        Args:
            bid_depth_total: 총 bid 수량
            ask_depth_total: 총 ask 수량

        Returns:
            점수 (0-100). 깊은 유동성 = 높은 점수.
        """
        total = bid_depth_total + ask_depth_total
        if total <= 0:
            return 0.0

        # 기본 깊이 점수
        if total < _DEPTH_VERY_LOW:
            base = 30.0
        elif total < _DEPTH_LOW:
            base = 60.0
        elif total < _DEPTH_HIGH:
            base = 90.0
        else:
            base = 100.0

        # Bid/Ask 불균형 감점
        if ask_depth_total > 0 and bid_depth_total > 0:
            ratio = bid_depth_total / ask_depth_total
            if ratio > _IMBALANCE_THRESHOLD or ratio < 1.0 / _IMBALANCE_THRESHOLD:
                base *= 0.85  # 15% 감점

        return min(base, 100.0)

    @staticmethod
    def _event_score(
        current_time: datetime,
        event_times: list[datetime] | None = None,
        economic_events: list[tuple[datetime, int]] | None = None,
    ) -> float:
        """이벤트 캘린더 기반 점수.

        경제 이벤트 (FOMC/CPI 등) ±window 이내 → 20점.
        펀딩 정산 (00:00/08:00/16:00 UTC) ±30분 → 40점.
        커스텀 이벤트 시간 ±30분 → 40점.
        그 외 → 100점.

        Args:
            current_time: 현재 UTC 시간
            event_times: 커스텀 이벤트 시간 리스트 (선택)
            economic_events: 경제 이벤트 [(event_time, window_min), ...] (선택)

        Returns:
            점수 (20, 40, or 100). 최소 점수 우선.
        """
        min_score = 100.0

        # WS-4: 경제 이벤트 체크 (FOMC, CPI 등)
        if economic_events:
            for evt_time, window_min in economic_events:
                diff_sec = abs((current_time - evt_time).total_seconds())
                if diff_sec <= window_min * 60:
                    min_score = min(min_score, 20.0)

        minute_of_day = current_time.hour * 60 + current_time.minute

        # 펀딩 정산 체크
        for funding_hour in _FUNDING_HOURS:
            funding_minute = funding_hour * 60
            dist = abs(minute_of_day - funding_minute)
            # 자정 경계 처리 (23:30 ~ 00:30)
            dist = min(dist, 1440 - dist)
            if dist <= _FUNDING_WINDOW_MINUTES:
                min_score = min(min_score, 40.0)

        # 커스텀 이벤트 체크
        if event_times:
            for evt in event_times:
                diff_sec = abs((current_time - evt).total_seconds())
                if diff_sec <= _FUNDING_WINDOW_MINUTES * 60:
                    min_score = min(min_score, 40.0)

        return min_score

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
            점수 (55-110)
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
        if _EU_END <= hour < _EU_US_OVERLAP_END:
            return "EU_US_OVERLAP"
        if _EU_US_OVERLAP_END <= hour < _US_END:
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
