"""Graceful Degradation Controller 테스트."""

import time

import pytest

from src.trading.degradation_controller import (
    L4_GRACE_PERIOD,
    DegradationLevel,
    DegradationState,
    GracefulDegradationController,
    HealthStatus,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def controller() -> GracefulDegradationController:
    """기본 컨트롤러."""
    return GracefulDegradationController()


@pytest.fixture()
def healthy() -> HealthStatus:
    """모든 것이 정상인 HealthStatus."""
    return HealthStatus(
        ws_connected=True,
        ws_stale=False,
        ws_reconnect_failures=0,
        market_data_circuit_ok=True,
        trading_circuit_ok=True,
        account_circuit_ok=True,
        consecutive_loop_errors=0,
        ws_enabled=True,
    )


# =========================================================================
# TestDegradationLevel
# =========================================================================


class TestDegradationLevel:
    """DegradationLevel enum 테스트."""

    def test_level_ordering(self) -> None:
        """레벨이 올바른 순서인지 확인."""
        assert DegradationLevel.NORMAL < DegradationLevel.PARTIAL_DELAY
        assert DegradationLevel.PARTIAL_DELAY < DegradationLevel.WS_DISCONNECTED
        assert DegradationLevel.WS_DISCONNECTED < DegradationLevel.REST_FAILED
        assert DegradationLevel.REST_FAILED < DegradationLevel.TOTAL_DISCONNECT

    def test_level_values(self) -> None:
        """레벨 값 확인."""
        assert DegradationLevel.NORMAL == 0
        assert DegradationLevel.PARTIAL_DELAY == 1
        assert DegradationLevel.WS_DISCONNECTED == 2
        assert DegradationLevel.REST_FAILED == 3
        assert DegradationLevel.TOTAL_DISCONNECT == 4


# =========================================================================
# TestHealthStatus
# =========================================================================


class TestHealthStatus:
    """HealthStatus dataclass 테스트."""

    def test_defaults(self) -> None:
        """기본값 확인."""
        h = HealthStatus()
        assert h.ws_connected is True
        assert h.ws_stale is False
        assert h.ws_reconnect_failures == 0
        assert h.market_data_circuit_ok is True
        assert h.trading_circuit_ok is True
        assert h.account_circuit_ok is True
        assert h.consecutive_loop_errors == 0
        assert h.ws_enabled is False

    def test_frozen(self) -> None:
        """frozen이라 수정 불가."""
        h = HealthStatus()
        with pytest.raises(AttributeError):
            h.ws_connected = False  # type: ignore[misc]


# =========================================================================
# TestDegradationState
# =========================================================================


class TestDegradationState:
    """DegradationState dataclass 테스트."""

    def test_frozen(self) -> None:
        """frozen 확인."""
        s = DegradationState(
            level=DegradationLevel.NORMAL,
            size_multiplier=1.0,
            can_open_position=True,
            should_close_all=False,
            reason="test",
        )
        with pytest.raises(AttributeError):
            s.level = DegradationLevel.REST_FAILED  # type: ignore[misc]


# =========================================================================
# TestLevelComputation
# =========================================================================


class TestLevelComputation:
    """레벨 계산 테스트."""

    def test_l0_all_healthy(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """모든 것이 정상이면 L0."""
        state = controller.evaluate(healthy)
        assert state.level == DegradationLevel.NORMAL
        assert state.size_multiplier == 1.0
        assert state.can_open_position is True
        assert state.should_close_all is False

    def test_l1_trading_circuit_open(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """trading circuit OPEN → L1."""
        h = HealthStatus(
            **{**healthy.__dict__, "trading_circuit_ok": False}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.PARTIAL_DELAY
        assert state.size_multiplier == 0.8
        assert state.can_open_position is True

    def test_l1_account_circuit_open(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """account circuit OPEN → L1."""
        h = HealthStatus(
            **{**healthy.__dict__, "account_circuit_ok": False}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.PARTIAL_DELAY

    def test_l1_ws_stale(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """WS stale → L1."""
        h = HealthStatus(**{**healthy.__dict__, "ws_stale": True})
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.PARTIAL_DELAY

    def test_l1_consecutive_errors_2(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """연속 에러 2회 → L1."""
        h = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 2}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.PARTIAL_DELAY

    def test_l2_ws_disconnected(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """WS 연결 끊김 → L2."""
        h = HealthStatus(
            **{**healthy.__dict__, "ws_connected": False, "ws_enabled": True}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.WS_DISCONNECTED
        assert state.size_multiplier == 0.5
        assert state.can_open_position is False

    def test_l2_ws_reconnect_failures(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """WS reconnect 5회 실패 → L2."""
        h = HealthStatus(
            **{**healthy.__dict__, "ws_reconnect_failures": 5, "ws_enabled": True}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.WS_DISCONNECTED

    def test_l2_not_triggered_when_ws_disabled(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """WS 미사용 시 WS 끊김이 L2를 유발하지 않음."""
        h = HealthStatus(
            **{**healthy.__dict__, "ws_connected": False, "ws_enabled": False}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.NORMAL

    def test_l3_market_data_circuit_open(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """market_data circuit OPEN → L3."""
        h = HealthStatus(
            **{**healthy.__dict__, "market_data_circuit_ok": False}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.REST_FAILED
        assert state.size_multiplier == 0.0
        assert state.can_open_position is False

    def test_l4_both_circuits_open(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """trading + account 둘 다 OPEN → L4."""
        h = HealthStatus(
            **{
                **healthy.__dict__,
                "trading_circuit_ok": False,
                "account_circuit_ok": False,
            }
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT
        assert state.size_multiplier == 0.0
        assert state.can_open_position is False

    def test_l4_consecutive_errors_5(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """연속 에러 5회 → L4."""
        h = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 5}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT

    def test_l4_priority_over_l3(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """L4 조건 + L3 조건 동시 → L4 우선."""
        h = HealthStatus(
            **{
                **healthy.__dict__,
                "trading_circuit_ok": False,
                "account_circuit_ok": False,
                "market_data_circuit_ok": False,
            }
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT


# =========================================================================
# TestHysteresis
# =========================================================================


class TestHysteresis:
    """Hysteresis (회복 지연) 테스트."""

    def test_degradation_is_immediate(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """악화는 즉시 반영."""
        # L0 → L4 한번에
        h = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 5}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT

    def test_recovery_is_gradual(
        self,
        controller: GracefulDegradationController,
        healthy: HealthStatus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """회복은 한 단계씩."""
        fake_time = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

        # L2로 악화
        h_bad = HealthStatus(
            **{**healthy.__dict__, "ws_connected": False, "ws_enabled": True}
        )
        state = controller.evaluate(h_bad)
        assert state.level == DegradationLevel.WS_DISCONNECTED

        # 즉시 회복 시도 → 아직 L2 유지
        state = controller.evaluate(healthy)
        assert state.level == DegradationLevel.WS_DISCONNECTED

        # 60초 후 → L1로 한 단계 회복
        fake_time[0] = 160.0
        state = controller.evaluate(healthy)
        assert state.level == DegradationLevel.PARTIAL_DELAY

        # 즉시 다시 → 아직 L1
        state = controller.evaluate(healthy)
        assert state.level == DegradationLevel.PARTIAL_DELAY

        # 30초 후 → L0 회복
        fake_time[0] = 190.0
        state = controller.evaluate(healthy)
        assert state.level == DegradationLevel.NORMAL

    def test_recovery_resets_on_new_degradation(
        self,
        controller: GracefulDegradationController,
        healthy: HealthStatus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """회복 중 다시 악화하면 즉시 반영."""
        fake_time = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

        # L1으로 악화
        h_l1 = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 2}
        )
        controller.evaluate(h_l1)

        # 회복 대기 중 L3로 악화
        fake_time[0] = 110.0
        h_l3 = HealthStatus(
            **{**healthy.__dict__, "market_data_circuit_ok": False}
        )
        state = controller.evaluate(h_l3)
        assert state.level == DegradationLevel.REST_FAILED


# =========================================================================
# TestL4ForceClose
# =========================================================================


class TestL4ForceClose:
    """L4 전체 청산 유예 테스트."""

    def test_l4_no_close_before_grace(
        self,
        controller: GracefulDegradationController,
        healthy: HealthStatus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """L4 진입 후 유예 시간 전에는 청산 안 함."""
        fake_time = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

        h_l4 = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 5}
        )
        state = controller.evaluate(h_l4)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT
        assert state.should_close_all is False

        # 유예 직전
        fake_time[0] = 100.0 + L4_GRACE_PERIOD - 1
        state = controller.evaluate(h_l4)
        assert state.should_close_all is False

    def test_l4_close_after_grace(
        self,
        controller: GracefulDegradationController,
        healthy: HealthStatus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """L4 유예 시간 경과 후 전체 청산."""
        fake_time = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

        h_l4 = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 5}
        )
        controller.evaluate(h_l4)

        # 유예 경과
        fake_time[0] = 100.0 + L4_GRACE_PERIOD
        state = controller.evaluate(h_l4)
        assert state.should_close_all is True

    def test_l4_timer_resets_on_recovery(
        self,
        controller: GracefulDegradationController,
        healthy: HealthStatus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """L4 해제 후 다시 L4 진입하면 타이머 리셋."""
        fake_time = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

        h_l4 = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 5}
        )
        controller.evaluate(h_l4)

        # L4 → L3로 회복 (60초 후)
        fake_time[0] = 160.0
        h_l3 = HealthStatus(
            **{**healthy.__dict__, "market_data_circuit_ok": False}
        )
        controller.evaluate(h_l3)
        assert controller.current_level == DegradationLevel.REST_FAILED

        # 다시 L4
        fake_time[0] = 161.0
        state = controller.evaluate(h_l4)
        assert state.level == DegradationLevel.TOTAL_DISCONNECT
        assert state.should_close_all is False  # 타이머 리셋됨

        # 30초 후 (원래라면 첫 L4에서 이미 유예 지남)
        fake_time[0] = 161.0 + L4_GRACE_PERIOD
        state = controller.evaluate(h_l4)
        assert state.should_close_all is True


# =========================================================================
# TestEdgeCases
# =========================================================================


class TestEdgeCases:
    """엣지 케이스 테스트."""

    def test_ws_disabled_no_l2(
        self, controller: GracefulDegradationController
    ) -> None:
        """WS 미사용 시 WS 문제가 있어도 L2가 아님."""
        h = HealthStatus(
            ws_connected=False,
            ws_stale=True,
            ws_reconnect_failures=10,
            ws_enabled=False,
        )
        state = controller.evaluate(h)
        # ws_stale → L1 (ws_enabled 무관하게 ws_stale은 L1 조건)
        assert state.level == DegradationLevel.PARTIAL_DELAY

    def test_idempotent_evaluation(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """같은 상태 반복 평가 → 같은 결과."""
        s1 = controller.evaluate(healthy)
        s2 = controller.evaluate(healthy)
        assert s1.level == s2.level
        assert s1.size_multiplier == s2.size_multiplier

    def test_all_defaults(
        self, controller: GracefulDegradationController
    ) -> None:
        """기본 HealthStatus (WS 미사용) → L0."""
        state = controller.evaluate(HealthStatus())
        assert state.level == DegradationLevel.NORMAL

    def test_consecutive_errors_3_is_l1(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """연속 에러 3회 → L1 (L4 아님)."""
        h = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 3}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.PARTIAL_DELAY

    def test_consecutive_errors_1_is_l0(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """연속 에러 1회 → L0."""
        h = HealthStatus(
            **{**healthy.__dict__, "consecutive_loop_errors": 1}
        )
        state = controller.evaluate(h)
        assert state.level == DegradationLevel.NORMAL

    def test_current_level_property(
        self, controller: GracefulDegradationController, healthy: HealthStatus
    ) -> None:
        """current_level 프로퍼티 동작 확인."""
        assert controller.current_level == DegradationLevel.NORMAL
        h = HealthStatus(
            **{**healthy.__dict__, "market_data_circuit_ok": False}
        )
        controller.evaluate(h)
        assert controller.current_level == DegradationLevel.REST_FAILED
