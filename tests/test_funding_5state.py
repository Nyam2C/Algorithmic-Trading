"""Funding 5-State 상태 머신 테스트."""
import pytest

from src.ai.channels.funding_basis import (
    FUNDING_STATE_CONFIG,
    FundingBasisChannel,
    FundingState,
)
from src.ai.ensemble import SignalSource


class TestFundingStateClassification:
    """_classify_funding_state 테스트."""

    def test_euphoria_state(self):
        state, score = FundingBasisChannel._classify_funding_state(0.0005)
        assert state == FundingState.EUPHORIA
        assert score == -90

    def test_euphoria_high_fr(self):
        state, score = FundingBasisChannel._classify_funding_state(0.001)
        assert state == FundingState.EUPHORIA
        assert score == -90

    def test_greed_state(self):
        state, score = FundingBasisChannel._classify_funding_state(0.0004)
        assert state == FundingState.GREED
        assert score == -60

    def test_greed_boundary(self):
        state, score = FundingBasisChannel._classify_funding_state(0.0003)
        assert state == FundingState.GREED
        assert score == -60

    def test_neutral_state(self):
        state, score = FundingBasisChannel._classify_funding_state(0.0001)
        assert state == FundingState.NEUTRAL
        assert score == 0

    def test_neutral_zero(self):
        state, score = FundingBasisChannel._classify_funding_state(0.0)
        assert state == FundingState.NEUTRAL
        assert score == 0

    def test_neutral_negative(self):
        state, score = FundingBasisChannel._classify_funding_state(-0.0001)
        assert state == FundingState.NEUTRAL
        assert score == 0

    def test_fear_state(self):
        state, score = FundingBasisChannel._classify_funding_state(-0.0003)
        assert state == FundingState.FEAR
        assert score == 60

    def test_fear_boundary(self):
        state, score = FundingBasisChannel._classify_funding_state(-0.0002)
        assert state == FundingState.FEAR
        assert score == 60

    def test_capitulation_state(self):
        state, score = FundingBasisChannel._classify_funding_state(-0.0006)
        assert state == FundingState.CAPITULATION
        assert score == 90


class TestFundingStateConfig:
    """FUNDING_STATE_CONFIG 테스트."""

    def test_all_states_have_config(self):
        for state in FundingState:
            assert state.value in FUNDING_STATE_CONFIG

    def test_config_has_required_keys(self):
        for cfg in FUNDING_STATE_CONFIG.values():
            assert "fr_min" in cfg
            assert "fr_max" in cfg
            assert "score" in cfg


class TestModulateWith5State:
    """_modulate_with_5state 테스트."""

    def setup_method(self):
        self.channel = FundingBasisChannel(use_5state=True)

    def test_neutral_returns_wait(self):
        sig, conf, suffix = self.channel._modulate_with_5state(
            "SHORT", 0.8, 0.0001,
        )
        assert sig == "WAIT"
        assert conf == 0.0
        assert "neutral" in suffix

    def test_euphoria_boosts_short(self):
        sig, conf, suffix = self.channel._modulate_with_5state(
            "SHORT", 0.8, 0.0006,
        )
        assert sig == "SHORT"
        assert conf > 0
        assert "euphoria" in suffix

    def test_capitulation_boosts_long(self):
        sig, conf, suffix = self.channel._modulate_with_5state(
            "LONG", 0.7, -0.0006,
        )
        assert sig == "LONG"
        assert conf > 0
        assert "capitulation" in suffix

    def test_wait_gets_direction_from_state(self):
        """WAIT 시그널에 극단 상태가 방향 제공."""
        sig, conf, suffix = self.channel._modulate_with_5state(
            "WAIT", 0.0, -0.0006,
        )
        assert sig == "LONG"
        assert conf > 0

    def test_conflicting_direction_reduces_confidence(self):
        """시그널과 5-State 방향 불일치 시 confidence 감쇠."""
        sig, conf, suffix = self.channel._modulate_with_5state(
            "LONG", 0.8, 0.0006,  # EUPHORIA → SHORT 유리인데 LONG 시그널
        )
        assert sig == "LONG"
        assert conf < 0.5  # 감쇠됨


class TestGenerateSignal5State:
    """generate_signal with use_5state=True 통합 테스트."""

    @pytest.fixture
    def channel(self):
        return FundingBasisChannel(use_5state=True)

    @pytest.fixture
    def legacy_channel(self):
        return FundingBasisChannel(use_5state=False)

    @pytest.mark.asyncio
    async def test_5state_euphoria_generates_short(self, channel):
        """EUPHORIA 상태에서 SHORT 시그널."""
        sig = await channel.generate_signal(
            funding_rate=0.0006, long_short_ratio=2.0,  # long 66%
        )
        assert sig.signal == "SHORT"
        assert sig.source == SignalSource.FUNDING_BASIS
        assert "5S:euphoria" in sig.reason

    @pytest.mark.asyncio
    async def test_5state_capitulation_generates_long(self, channel):
        """CAPITULATION 상태에서 LONG 시그널."""
        sig = await channel.generate_signal(
            funding_rate=-0.0006, long_short_ratio=0.5,  # short 66%
        )
        assert sig.signal == "LONG"
        assert "5S:capitulation" in sig.reason

    @pytest.mark.asyncio
    async def test_5state_neutral_returns_wait(self, channel):
        sig = await channel.generate_signal(
            funding_rate=0.0001, long_short_ratio=1.0,
        )
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_legacy_unchanged(self, legacy_channel):
        """use_5state=False면 기존 로직 그대로."""
        sig = await legacy_channel.generate_signal(
            funding_rate=0.0001, long_short_ratio=1.0,
        )
        assert sig.signal == "WAIT"
        assert "5S:" not in sig.reason

    @pytest.mark.asyncio
    async def test_5state_with_basis_cross_validation(self, channel):
        """5-State + basis 교차검증 통합."""
        sig = await channel.generate_signal(
            funding_rate=0.0006, long_short_ratio=2.0,
            basis=0.001,  # FR과 같은 방향 → 부스트
        )
        assert sig.signal == "SHORT"
        assert sig.confidence > 0

    @pytest.mark.asyncio
    async def test_5state_none_data(self, channel):
        """데이터 없으면 WAIT."""
        sig = await channel.generate_signal(
            funding_rate=None, long_short_ratio=None,
        )
        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0
