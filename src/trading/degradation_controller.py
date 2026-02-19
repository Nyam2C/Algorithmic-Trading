"""Graceful Degradation Controller.

4단계 장애 대응 시스템. WS 단절, REST 실패 등 부분 장애 시
자동으로 기능 수준을 조절하여 자본을 보호합니다.

레벨:
    L0 NORMAL          — 모든 기능 활성, size x1.0
    L1 PARTIAL_DELAY   — 일부 지연, size x0.8, 진입 허용
    L2 WS_DISCONNECTED — WS 단절, size x0.5, 진입 금지
    L3 REST_FAILED     — REST 실패, size x0.0, 포지션 관리만
    L4 TOTAL_DISCONNECT — 완전 단절, 30초 후 전체 청산
"""

import time
from dataclasses import dataclass
from enum import IntEnum

from loguru import logger


class DegradationLevel(IntEnum):
    """장애 대응 레벨."""

    NORMAL = 0
    PARTIAL_DELAY = 1
    WS_DISCONNECTED = 2
    REST_FAILED = 3
    TOTAL_DISCONNECT = 4


# 레벨별 설정 상수
_LEVEL_CONFIG: dict[int, dict] = {
    0: {"size_multiplier": 1.0, "can_open": True},
    1: {"size_multiplier": 0.8, "can_open": True},
    2: {"size_multiplier": 0.5, "can_open": False},
    3: {"size_multiplier": 0.0, "can_open": False},
    4: {"size_multiplier": 0.0, "can_open": False},
}

# Hysteresis 회복 대기 시간 (초)
_RECOVERY_HOLD: dict[int, float] = {
    1: 30.0,
    2: 60.0,
    3: 60.0,
    4: 60.0,
}

# L4 전체 청산 유예 시간 (초)
L4_GRACE_PERIOD: float = 30.0


@dataclass(frozen=True)
class HealthStatus:
    """봇 건강 상태. bot_instance가 매 루프 조립."""

    ws_connected: bool = True
    ws_stale: bool = False
    ws_reconnect_failures: int = 0
    market_data_circuit_ok: bool = True
    trading_circuit_ok: bool = True
    account_circuit_ok: bool = True
    consecutive_loop_errors: int = 0
    ws_enabled: bool = False


@dataclass(frozen=True)
class DegradationState:
    """evaluate() 결과."""

    level: DegradationLevel
    size_multiplier: float
    can_open_position: bool
    should_close_all: bool
    reason: str


class GracefulDegradationController:
    """Graceful Degradation Controller.

    악화는 즉시 반영, 회복은 hold time 후 한 단계씩.
    L4 진입 시 30초 유예 후 전체 청산 플래그.
    """

    def __init__(self) -> None:
        self._current_level = DegradationLevel.NORMAL
        self._level_change_time: float = time.monotonic()
        self._l4_enter_time: float | None = None
        self._log = logger.bind(component="degradation_controller")

    @property
    def current_level(self) -> DegradationLevel:
        """현재 레벨."""
        return self._current_level

    def evaluate(self, health: HealthStatus) -> DegradationState:
        """건강 상태 평가 → 장애 대응 상태 반환.

        Args:
            health: 현재 건강 상태

        Returns:
            DegradationState
        """
        now = time.monotonic()
        raw_level, reason = self._compute_raw_level(health)

        # 악화: 즉시 반영
        if raw_level > self._current_level:
            self._current_level = DegradationLevel(raw_level)
            self._level_change_time = now
            self._log.warning(
                f"Degradation 악화: L{raw_level} — {reason}"
            )
            # L4 진입 시 타이머 시작
            if (
                raw_level == DegradationLevel.TOTAL_DISCONNECT
                and self._l4_enter_time is None
            ):
                self._l4_enter_time = now

        # 회복: hold time 경과 후 한 단계씩
        elif raw_level < self._current_level:
            hold = _RECOVERY_HOLD.get(int(self._current_level), 30.0)
            elapsed = now - self._level_change_time
            if elapsed >= hold:
                new_level = DegradationLevel(int(self._current_level) - 1)
                self._current_level = new_level
                self._level_change_time = now
                self._log.info(
                    f"Degradation 회복: L{new_level} (hold {hold}s 경과)"
                )
                # L4 해제 시 타이머 리셋
                if new_level < DegradationLevel.TOTAL_DISCONNECT:
                    self._l4_enter_time = None

        # L4 유예 아닐 때 타이머 리셋
        if self._current_level < DegradationLevel.TOTAL_DISCONNECT:
            self._l4_enter_time = None

        # L4 전체 청산 판단
        should_close_all = (
            self._current_level == DegradationLevel.TOTAL_DISCONNECT
            and self._l4_enter_time is not None
            and now - self._l4_enter_time >= L4_GRACE_PERIOD
        )

        cfg = _LEVEL_CONFIG[int(self._current_level)]
        return DegradationState(
            level=self._current_level,
            size_multiplier=cfg["size_multiplier"],
            can_open_position=cfg["can_open"],
            should_close_all=should_close_all,
            reason=reason,
        )

    def _compute_raw_level(
        self, health: HealthStatus
    ) -> tuple[DegradationLevel, str]:
        """건강 상태에서 raw 레벨 계산 (hysteresis 미적용).

        Returns:
            (레벨, 사유) 튜플
        """
        # L4: trading + account 둘 다 OPEN, 또는 연속 에러 ≥ 5
        if (
            not health.trading_circuit_ok and not health.account_circuit_ok
        ) or health.consecutive_loop_errors >= 5:  # noqa: PLR2004
            reason = (
                "trading+account circuit OPEN"
                if not health.trading_circuit_ok and not health.account_circuit_ok
                else f"consecutive_errors={health.consecutive_loop_errors}"
            )
            return DegradationLevel.TOTAL_DISCONNECT, reason

        # L3: market_data circuit OPEN
        if not health.market_data_circuit_ok:
            return DegradationLevel.REST_FAILED, "market_data circuit OPEN"

        # L2: WS 활성인데 연결 끊김 또는 reconnect 실패 ≥ 5
        if health.ws_enabled and (
            not health.ws_connected
            or health.ws_reconnect_failures >= 5  # noqa: PLR2004
        ):
            reason = (
                f"ws_reconnect_failures={health.ws_reconnect_failures}"
                if health.ws_reconnect_failures >= 5  # noqa: PLR2004
                else "ws_disconnected"
            )
            return DegradationLevel.WS_DISCONNECTED, reason

        # L1: trading 또는 account 중 하나 OPEN, WS stale, 연속 에러 ≥ 2
        if (
            not health.trading_circuit_ok
            or not health.account_circuit_ok
            or health.ws_stale
            or health.consecutive_loop_errors >= 2  # noqa: PLR2004
        ):
            reasons = []
            if not health.trading_circuit_ok:
                reasons.append("trading circuit OPEN")
            if not health.account_circuit_ok:
                reasons.append("account circuit OPEN")
            if health.ws_stale:
                reasons.append("ws_stale")
            if health.consecutive_loop_errors >= 2:  # noqa: PLR2004
                reasons.append(
                    f"consecutive_errors={health.consecutive_loop_errors}"
                )
            return DegradationLevel.PARTIAL_DELAY, ", ".join(reasons)

        # L0: 모두 정상
        return DegradationLevel.NORMAL, "all_healthy"
