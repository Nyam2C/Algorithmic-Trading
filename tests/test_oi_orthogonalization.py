"""OI Orthogonalization 테스트."""
import pytest

from src.ai.channels.funding_basis import FundingBasisChannel
from src.ai.channels.oi_orthogonalization import OIOrthogonalizer


class TestOIOrthogonalizer:
    def test_beta_zero_initial(self):
        ort = OIOrthogonalizer()
        assert ort.beta == 0.0

    def test_update_stores_data(self):
        ort = OIOrthogonalizer()
        ort.update(0.001, 0.05)
        ort.update(0.002, 0.03)
        assert len(ort._fr_history) == 2
        assert len(ort._oi_signal_history) == 2

    def test_recompute_insufficient_samples(self):
        """MIN_SAMPLES 미만이면 beta 변경 없음."""
        ort = OIOrthogonalizer()
        for i in range(5):
            ort.update(0.001 * i, 0.01 * i)
        beta = ort.recompute_beta()
        assert beta == 0.0  # unchanged

    def test_recompute_correlated(self):
        """FR과 OI가 상관 → beta != 0."""
        ort = OIOrthogonalizer()
        for i in range(20):
            fr = 0.0001 * i + 0.0002 * i  # FR partially driven by OI-like pattern
            oi = 0.01 * i
            ort.update(fr, oi)
        beta = ort.recompute_beta()
        assert beta != 0.0

    def test_recompute_uncorrelated(self):
        """FR과 OI가 독립 → beta ≈ 0."""
        import random
        random.seed(42)
        ort = OIOrthogonalizer()
        for _i in range(20):
            fr = random.gauss(0, 0.001)
            oi = random.gauss(0, 0.01)
            ort.update(fr, oi)
        beta = ort.recompute_beta()
        # 독립 변수면 beta 작음
        assert abs(beta) < 0.5

    def test_orthogonalize_removes_oi(self):
        """beta=0.5일 때 OI 기여분 50% 제거."""
        ort = OIOrthogonalizer()
        ort._beta = 0.5
        result = ort.orthogonalize(0.001, 0.001)
        # 0.001 - 0.5 * 0.001 = 0.0005
        assert abs(result - 0.0005) < 1e-10

    def test_orthogonalize_zero_beta(self):
        """beta=0이면 원본 그대로."""
        ort = OIOrthogonalizer()
        result = ort.orthogonalize(0.001, 0.05)
        assert result == 0.001

    def test_smoothing(self):
        """첫 번째 계산 → beta=calc, 두 번째 → smoothed."""
        ort = OIOrthogonalizer()
        # First: establish beta
        for i in range(20):
            ort.update(0.0003 * i, 0.01 * i)
        first_beta = ort.recompute_beta()
        assert first_beta != 0.0

        # Second: add different data, beta should be smoothed
        for _i in range(5):
            ort.update(-0.001, 0.005)
        second_beta = ort.recompute_beta()
        # Smoothing: 70% old + 30% new → should be different from first
        assert second_beta != first_beta

    def test_rolling_trim(self):
        """ROLLING_WINDOW 초과 시 오래된 데이터 제거."""
        ort = OIOrthogonalizer()
        for _i in range(50):
            ort.update(0.001, 0.01)
        assert len(ort._fr_history) == OIOrthogonalizer.ROLLING_WINDOW

    def test_zero_variance_oi(self):
        """OI 변화가 0이면 beta 변경 없음."""
        ort = OIOrthogonalizer()
        for i in range(20):
            ort.update(0.001 * i, 0.0)  # zero OI change
        beta = ort.recompute_beta()
        assert beta == 0.0


class TestFundingBasisWithOrthogonalizer:
    @pytest.mark.asyncio
    async def test_funding_with_orthogonalizer(self):
        """Orthogonalizer가 있으면 FR 직교화."""
        ort = OIOrthogonalizer()
        ort._beta = 1.0  # 100% OI 제거

        channel = FundingBasisChannel(orthogonalizer=ort)
        # FR=0.001, OI_change=0.001 → orthogonalized FR = 0.001 - 1.0*0.001 = 0.0
        sig = await channel.generate_signal(
            funding_rate=0.001,
            long_short_ratio=2.0,  # 66% long
            oi_change_pct=0.001,
        )
        # FR=0 → WAIT (below threshold)
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_funding_without_orthogonalizer(self):
        """Orthogonalizer 없으면 기존 동작."""
        channel = FundingBasisChannel()
        sig = await channel.generate_signal(
            funding_rate=0.001,  # extreme long
            long_short_ratio=2.0,  # 66% long
        )
        # FR=0.001 > 0.0005, Long=66% > 65% → SHORT
        assert sig.signal == "SHORT"

    @pytest.mark.asyncio
    async def test_funding_no_oi_change(self):
        """oi_change_pct=None이면 직교화 스킵."""
        ort = OIOrthogonalizer()
        ort._beta = 1.0
        channel = FundingBasisChannel(orthogonalizer=ort)
        sig = await channel.generate_signal(
            funding_rate=0.001,
            long_short_ratio=2.0,
            oi_change_pct=None,
        )
        # No orthogonalization → normal FR=0.001 → SHORT
        assert sig.signal == "SHORT"
