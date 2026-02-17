"""UTC 기반 트레이딩 세션 분류.

APEX-V Phase C: 세션별 가중치 적용을 위한 시간대 분류.
"""
from datetime import datetime, timezone
from enum import Enum


class TradingSession(Enum):
    """트레이딩 세션."""
    ASIA = "asia"            # 00:00-08:00 UTC
    EU = "eu"                # 08:00-13:00 UTC
    US = "us"                # 13:00-21:00 UTC
    DEEP_NIGHT = "deep_night"  # 21:00-00:00 UTC


class SessionClassifier:
    """UTC 시간 기반 트레이딩 세션 분류기."""

    # 세션별 시간 범위 (UTC)
    _SESSION_RANGES: list[tuple[int, int, TradingSession]] = [
        (0, 8, TradingSession.ASIA),
        (8, 13, TradingSession.EU),
        (13, 21, TradingSession.US),
        (21, 24, TradingSession.DEEP_NIGHT),
    ]

    def classify(self, current_time: datetime | None = None) -> TradingSession:
        """현재 시간의 트레이딩 세션을 분류.

        Args:
            current_time: 분류할 시간 (None이면 현재 UTC 시간)

        Returns:
            TradingSession enum
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        hour = current_time.hour
        for start, end, session in self._SESSION_RANGES:
            if start <= hour < end:
                return session

        return TradingSession.DEEP_NIGHT  # fallback (shouldn't reach)
