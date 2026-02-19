"""Regime Transition Protocol 테스트."""

from src.data.regime_detector import (
    MarketRegime,
    RegimeTransitionManager,
    RegimeTransitionResult,
    TransitionPhase,
)


class TestTransitionPhase:
    """TransitionPhase enum 테스트."""

    def test_phases_exist(self):
        assert TransitionPhase.STABLE.value == "stable"
        assert TransitionPhase.CONFIRMING.value == "confirming"
        assert TransitionPhase.HIGH_VOL_LOCKOUT.value == "high_vol_lockout"


class TestRegimeTransitionResult:
    """RegimeTransitionResult 테스트."""

    def test_default_values(self):
        r = RegimeTransitionResult(
            confirmed_regime=MarketRegime.STRONG_UPTREND,
            phase=TransitionPhase.STABLE,
        )
        assert r.confirmed_regime == MarketRegime.STRONG_UPTREND
        assert r.phase == TransitionPhase.STABLE
        assert r.should_reduce_position is False
        assert r.is_conservative is False
        assert r.raw_regime == MarketRegime.STRONG_UPTREND

    def test_custom_values(self):
        r = RegimeTransitionResult(
            confirmed_regime=MarketRegime.STRONG_UPTREND,
            phase=TransitionPhase.CONFIRMING,
            should_reduce_position=True,
            is_conservative=True,
            raw_regime=MarketRegime.RANGING,
        )
        assert r.should_reduce_position is True
        assert r.raw_regime == MarketRegime.RANGING


class TestRegimeTransitionManager:
    """RegimeTransitionManager 테스트."""

    def setup_method(self):
        self.mgr = RegimeTransitionManager()

    def test_initial_state(self):
        assert self.mgr.phase == TransitionPhase.STABLE
        assert self.mgr.confirmed_regime == MarketRegime.UNKNOWN

    def test_first_update_sets_regime(self):
        """첫 업데이트: UNKNOWN -> STRONG_UPTREND = 전환 감지."""
        r = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)
        assert r.phase == TransitionPhase.CONFIRMING
        assert r.confirmed_regime == MarketRegime.UNKNOWN  # 아직 미확정
        assert r.should_reduce_position is True  # 첫 전환 감지

    def test_same_regime_stays_stable(self):
        """같은 레짐 반복 → STABLE 유지."""
        # 초기 confirmed = UNKNOWN
        r1 = self.mgr.update(MarketRegime.UNKNOWN, 1000.0)
        assert r1.phase == TransitionPhase.STABLE

    def test_confirming_reverts_on_original(self):
        """CONFIRMING 중 원래 레짐으로 복귀 → 취소."""
        self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)
        assert self.mgr.phase == TransitionPhase.CONFIRMING

        # 원복
        r = self.mgr.update(MarketRegime.UNKNOWN, 2000.0)
        assert r.phase == TransitionPhase.STABLE
        assert r.confirmed_regime == MarketRegime.UNKNOWN

    def test_confirming_confirms_after_12h(self):
        """12시간 지속 → 전환 확정."""
        self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)
        assert self.mgr.phase == TransitionPhase.CONFIRMING

        # 12시간 + 1초 후
        h12 = 12 * 3600 + 1
        r = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0 + h12)
        assert r.phase == TransitionPhase.STABLE
        assert r.confirmed_regime == MarketRegime.STRONG_UPTREND

    def test_confirming_stays_before_12h(self):
        """12시간 미만 → 확인 대기 유지."""
        self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)

        r = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0 + 3600)
        assert r.phase == TransitionPhase.CONFIRMING
        assert r.is_conservative is True

    def test_reduce_emitted_only_once(self):
        """should_reduce_position은 1회만 발생."""
        r1 = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)
        assert r1.should_reduce_position is True

        # 같은 CONFIRMING 상태에서 다시 호출
        r2 = self.mgr.update(MarketRegime.STRONG_UPTREND, 2000.0)
        assert r2.should_reduce_position is False

    def test_rapid_flip_triggers_lockout(self):
        """12시간 내 3회 전환 → HIGH_VOL_LOCKOUT."""
        now = 1000.0
        # 전환 1: UNKNOWN -> UP
        self.mgr.update(MarketRegime.STRONG_UPTREND, now)
        # 원복 후 전환 2: UNKNOWN -> DOWN
        self.mgr.update(MarketRegime.UNKNOWN, now + 100)
        self.mgr.update(MarketRegime.STRONG_DOWNTREND, now + 200)
        # 원복 후 전환 3: UNKNOWN -> RANGING
        self.mgr.update(MarketRegime.UNKNOWN, now + 300)
        r = self.mgr.update(MarketRegime.RANGING, now + 400)

        # 전환 기록이 3회 이상 → LOCKOUT
        # (실제로는 CONFIRMING 중 다른 레짐으로 변경이 record_transition을 트리거)
        assert r.phase == TransitionPhase.HIGH_VOL_LOCKOUT or r.confirmed_regime == MarketRegime.UNCERTAINTY

    def test_lockout_forces_uncertainty(self):
        """LOCKOUT 중 UNCERTAINTY 강제."""
        # 강제 LOCKOUT 진입
        self.mgr._phase = TransitionPhase.HIGH_VOL_LOCKOUT
        self.mgr._lockout_since = 1000.0
        self.mgr._confirmed_regime = MarketRegime.UNCERTAINTY

        r = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0 + 3600)
        assert r.confirmed_regime == MarketRegime.UNCERTAINTY
        assert r.phase == TransitionPhase.HIGH_VOL_LOCKOUT
        assert r.is_conservative is True

    def test_lockout_expires_after_24h(self):
        """24시간 후 LOCKOUT 해제."""
        self.mgr._phase = TransitionPhase.HIGH_VOL_LOCKOUT
        self.mgr._lockout_since = 1000.0
        self.mgr._confirmed_regime = MarketRegime.UNCERTAINTY

        h24 = 24 * 3600 + 1
        r = self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0 + h24)
        assert r.phase == TransitionPhase.STABLE
        assert r.confirmed_regime == MarketRegime.STRONG_UPTREND

    def test_confirming_new_regime_during_confirm(self):
        """CONFIRMING 중 또 다른 레짐으로 변경."""
        self.mgr.update(MarketRegime.STRONG_UPTREND, 1000.0)
        assert self.mgr.phase == TransitionPhase.CONFIRMING

        r = self.mgr.update(MarketRegime.STRONG_DOWNTREND, 2000.0)
        assert r.phase == TransitionPhase.CONFIRMING
        assert r.confirmed_regime == MarketRegime.UNKNOWN  # 원래 confirmed 유지

    def test_constants(self):
        """상수 값 검증."""
        assert RegimeTransitionManager.CONFIRMATION_HOURS == 12.0
        assert RegimeTransitionManager.RAPID_FLIP_THRESHOLD == 3
        assert RegimeTransitionManager.LOCKOUT_HOURS == 24.0
        assert RegimeTransitionManager.POSITION_REDUCE_PCT == 0.50
