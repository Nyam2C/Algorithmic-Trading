"""
Tests for KellySizer — Kelly Criterion 동적 포지션 사이징

APEX-V Phase D: Kelly 공식 기반 포지션 크기 결정 테스트
"""

import pytest

from src.trading.kelly_sizer import KellySizer


@pytest.fixture
def sizer():
    """기본 KellySizer 인스턴스"""
    return KellySizer(kelly_fraction=0.25, min_size_pct=0.003, max_size_pct=0.02)


# ---------------------------------------------------------------------------
# TestKellySizer — Kelly 공식 계산 + record_trade 로직
# ---------------------------------------------------------------------------


class TestKellySizer:
    """Kelly 공식 및 거래 기록 테스트"""

    def test_kelly_formula_known_values(self, sizer):
        """60% 승률, avg_win=2%, avg_loss=1% → b=2, f*=0.4, quarter=0.1"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        # p=0.6, b=2.0, f*=(0.6*2-0.4)/2=0.4, quarter=0.1
        assert result == pytest.approx(0.1, abs=1e-9)

    def test_kelly_formula_50_win_rate(self, sizer):
        """50% 승률, avg_win=1.5%, avg_loss=1% → b=1.5, f*=1/6"""
        for _ in range(10):
            sizer.record_trade("TRENDING", 0.015)
        for _ in range(10):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        # f* = (0.5*1.5 - 0.5)/1.5 = 0.25/1.5
        # quarter = (0.25/1.5) * 0.25
        expected = (0.25 / 1.5) * 0.25
        assert result == pytest.approx(expected, abs=1e-9)

    def test_quarter_kelly_scaling(self, sizer):
        """Kelly fraction이 raw f*에 정확히 곱해지는지 확인"""
        for _ in range(15):
            sizer.record_trade("TRENDING", 0.03)
        for _ in range(5):
            sizer.record_trade("TRENDING", -0.01)

        # p=0.75, b=3.0, f*=(0.75*3-0.25)/3 = 2/3
        # quarter = 2/3 * 0.25
        result = sizer.calculate_kelly_size("TRENDING")
        expected = (2.0 / 3.0) * 0.25
        assert result == pytest.approx(expected, abs=1e-9)

    def test_half_kelly_scaling(self):
        """Half-Kelly(0.5)로 초기화 시 2배 적용"""
        sizer = KellySizer(kelly_fraction=0.5)
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        # f*=0.4, half-kelly=0.2
        assert result == pytest.approx(0.2, abs=1e-9)

    def test_insufficient_data_returns_none(self, sizer):
        """거래 수 < 20 → None 반환"""
        for _ in range(19):
            sizer.record_trade("TRENDING", 0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        assert result is None

    def test_exactly_20_trades_calculates(self, sizer):
        """정확히 20건이면 계산 수행"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        assert result is not None

    def test_unknown_regime_returns_none(self, sizer):
        """등록되지 않은 레짐 → None"""
        result = sizer.calculate_kelly_size("NONEXISTENT")
        assert result is None

    def test_empty_tracker_returns_none(self, sizer):
        """기록 없는 초기 상태 → None"""
        result = sizer.calculate_kelly_size("TRENDING")
        assert result is None

    def test_per_regime_independent_tracking(self, sizer):
        """TRENDING과 RANGING 거래가 독립적으로 추적"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        for _ in range(10):
            sizer.record_trade("RANGING", 0.005)

        assert sizer.calculate_kelly_size("TRENDING") is not None
        assert sizer.calculate_kelly_size("RANGING") is None

    def test_per_regime_different_results(self, sizer):
        """서로 다른 레짐은 서로 다른 Kelly 값을 산출"""
        for _ in range(16):
            sizer.record_trade("TRENDING", 0.03)
        for _ in range(4):
            sizer.record_trade("TRENDING", -0.01)

        for _ in range(11):
            sizer.record_trade("VOLATILE", 0.01)
        for _ in range(9):
            sizer.record_trade("VOLATILE", -0.01)

        trending_size = sizer.calculate_kelly_size("TRENDING")
        volatile_size = sizer.calculate_kelly_size("VOLATILE")
        assert trending_size != volatile_size

    def test_rolling_window_eviction_at_100(self, sizer):
        """100건 초과 시 가장 오래된 거래가 제거"""
        for _ in range(100):
            sizer.record_trade("TRENDING", -0.01)

        for _ in range(20):
            sizer.record_trade("TRENDING", 0.02)

        assert len(sizer._regime_trades["TRENDING"]) == 100
        trades = list(sizer._regime_trades["TRENDING"])
        wins = [t for t in trades if t > 0]
        assert len(wins) == 20

    def test_negative_kelly_returns_min_size(self, sizer):
        """손실 전략 (음의 Kelly) → min_size_pct 반환"""
        # 20% 승률, b=1 → f*=(0.2-0.8)/1=-0.6 → min_size_pct
        for _ in range(4):
            sizer.record_trade("TRENDING", 0.01)
        for _ in range(16):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        assert result == sizer.min_size_pct

    def test_all_losses_returns_min_size(self, sizer):
        """전패 (p=0) → b=0 방어 → min_size_pct 반환"""
        for _ in range(20):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_kelly_size("TRENDING")
        # avg_win=0, b=0 → b==0 체크에서 min_size_pct 반환
        assert result == sizer.min_size_pct

    def test_all_wins_returns_min_size(self, sizer):
        """전승 (q=0, avg_loss=0) → avg_loss==0 체크 → min_size_pct"""
        for _ in range(20):
            sizer.record_trade("TRENDING", 0.02)

        result = sizer.calculate_kelly_size("TRENDING")
        assert result == sizer.min_size_pct

    def test_zero_pnl_counted_as_loss(self, sizer):
        """pnl_pct=0.0 은 loss로 분류 (t <= 0)"""
        for _ in range(15):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(5):
            sizer.record_trade("TRENDING", 0.0)

        # avg_loss = abs(0.0) 평균 = 0.0 → avg_loss==0 → min_size_pct
        result = sizer.calculate_kelly_size("TRENDING")
        assert result == sizer.min_size_pct

    def test_deque_maxlen_is_100(self, sizer):
        """레짐별 deque의 maxlen이 100인지 확인"""
        for _ in range(150):
            sizer.record_trade("TRENDING", 0.01)

        assert len(sizer._regime_trades["TRENDING"]) == 100
        assert sizer._regime_trades["TRENDING"].maxlen == 100

    def test_mixed_small_pnl_values(self, sizer):
        """매우 작은 PnL 값도 정상 기록 및 계산"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.0001)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.00005)

        result = sizer.calculate_kelly_size("TRENDING")
        assert result is not None
        assert result > 0


# ---------------------------------------------------------------------------
# TestDrawdownMultiplier — 드로다운 기반 포지션 축소
# ---------------------------------------------------------------------------


class TestDrawdownMultiplier:
    """드로다운 배수 테스트"""

    def test_zero_drawdown(self, sizer):
        """0% 드로다운 → 1.0 (축소 없음)"""
        assert sizer._drawdown_multiplier(0.0) == pytest.approx(1.0)

    def test_negative_drawdown(self, sizer):
        """음수 드로다운 → 1.0 (수익 상태)"""
        assert sizer._drawdown_multiplier(-0.05) == pytest.approx(1.0)

    def test_2_5_pct_drawdown(self, sizer):
        """2.5% 드로다운 → 0.85 (0~5% 구간 선형)"""
        # 1.0 - (0.025 / 0.05) * 0.3 = 0.85
        assert sizer._drawdown_multiplier(0.025) == pytest.approx(0.85)

    def test_5_pct_drawdown(self, sizer):
        """5% 드로다운 → 0.7"""
        assert sizer._drawdown_multiplier(0.05) == pytest.approx(0.7)

    def test_7_5_pct_drawdown(self, sizer):
        """7.5% 드로다운 → 0.5 (5~10% 구간 선형)"""
        # 0.7 - ((0.075 - 0.05) / 0.05) * 0.4 = 0.5
        assert sizer._drawdown_multiplier(0.075) == pytest.approx(0.5)

    def test_10_pct_drawdown(self, sizer):
        """10% 드로다운 → 0.3"""
        assert sizer._drawdown_multiplier(0.10) == pytest.approx(0.3)

    def test_15_pct_drawdown(self, sizer):
        """10% 초과 → 0.3 (클램핑)"""
        assert sizer._drawdown_multiplier(0.15) == pytest.approx(0.3)

    def test_1_pct_drawdown(self, sizer):
        """1% 드로다운 → 0.94 (0~5% 구간)"""
        # 1.0 - (0.01 / 0.05) * 0.3 = 0.94
        assert sizer._drawdown_multiplier(0.01) == pytest.approx(0.94)

    def test_boundary_just_over_5_pct(self, sizer):
        """5.01% → 5~10% 구간에 진입"""
        result = sizer._drawdown_multiplier(0.0501)
        expected = 0.7 - (0.0001 / 0.05) * 0.4
        assert result == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# TestKellyFinalSize — calculate_final_size 통합 테스트
# ---------------------------------------------------------------------------


class TestKellyFinalSize:
    """최종 포지션 크기 결정 테스트"""

    def test_uses_config_default_when_kelly_none(self, sizer):
        """Kelly 데이터 부족 시 config_default 사용"""
        result = sizer.calculate_final_size("TRENDING", config_default=0.01)
        assert result == pytest.approx(0.01)

    def test_uses_kelly_when_available(self, sizer):
        """Kelly 데이터 충분 시 Kelly 값 사용 (max 클램핑)"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        # kelly=0.1, max_size_pct=0.02이므로 클램핑
        result = sizer.calculate_final_size("TRENDING", config_default=0.005)
        assert result == sizer.max_size_pct

    def test_min_clamping(self, sizer):
        """결과가 min_size_pct 이하면 min으로 클램핑"""
        result = sizer.calculate_final_size(
            "TRENDING",
            config_default=0.001,
            drawdown_pct=0.10,
        )
        # 0.001 * 0.3 = 0.0003 → min_size_pct(0.003)
        assert result == sizer.min_size_pct

    def test_max_clamping(self, sizer):
        """결과가 max_size_pct 이상이면 max로 클램핑"""
        result = sizer.calculate_final_size(
            "TRENDING",
            config_default=0.03,
            entry_tier=1.5,
            mti_mod=1.2,
        )
        # 0.03 * 1.5 * 1.2 = 0.054 → max_size_pct(0.02)
        assert result == sizer.max_size_pct

    def test_all_modifiers_combined(self, sizer):
        """모든 수정자가 곱해지는지 확인"""
        result = sizer.calculate_final_size(
            "TRENDING",
            config_default=0.01,
            entry_tier=0.8,
            mti_mod=0.9,
            cost_adj=0.95,
            vitality_mod=1.1,
            drawdown_pct=0.025,
        )
        expected_raw = 0.01 * 0.8 * 0.9 * 0.95 * 1.1 * 0.85
        expected = max(sizer.min_size_pct, min(expected_raw, sizer.max_size_pct))
        assert result == pytest.approx(expected)

    def test_drawdown_reduces_final_size(self, sizer):
        """드로다운 증가 → 포지션 크기 감소"""
        size_no_dd = sizer.calculate_final_size(
            "TRENDING", config_default=0.01, drawdown_pct=0.0,
        )
        size_with_dd = sizer.calculate_final_size(
            "TRENDING", config_default=0.01, drawdown_pct=0.05,
        )
        assert size_with_dd < size_no_dd

    def test_default_modifiers_are_neutral(self, sizer):
        """기본 수정자(모두 1.0, dd=0.0)는 base를 변경하지 않음"""
        result = sizer.calculate_final_size("TRENDING", config_default=0.01)
        assert result == pytest.approx(0.01)

    def test_entry_tier_scaling(self, sizer):
        """entry_tier만 적용"""
        result = sizer.calculate_final_size(
            "TRENDING", config_default=0.01, entry_tier=0.5,
        )
        assert result == pytest.approx(0.005)

    def test_mti_mod_scaling(self, sizer):
        """mti_mod만 적용"""
        result = sizer.calculate_final_size(
            "TRENDING", config_default=0.01, mti_mod=0.8,
        )
        assert result == pytest.approx(0.008)

    def test_negative_kelly_still_returns_min(self, sizer):
        """손실 전략 Kelly → min_size_pct가 base로 사용"""
        for _ in range(4):
            sizer.record_trade("TRENDING", 0.01)
        for _ in range(16):
            sizer.record_trade("TRENDING", -0.01)

        result = sizer.calculate_final_size("TRENDING", config_default=0.01)
        assert result == sizer.min_size_pct

    def test_custom_min_max(self):
        """커스텀 min/max 설정이 클램핑에 반영"""
        sizer = KellySizer(min_size_pct=0.005, max_size_pct=0.015)
        result_low = sizer.calculate_final_size(
            "TRENDING", config_default=0.001,
        )
        result_high = sizer.calculate_final_size(
            "TRENDING", config_default=0.05,
        )
        assert result_low == 0.005
        assert result_high == 0.015

    def test_cost_adj_and_vitality_mod(self, sizer):
        """cost_adj, vitality_mod 개별 적용 확인"""
        result = sizer.calculate_final_size(
            "TRENDING",
            config_default=0.01,
            cost_adj=0.9,
            vitality_mod=0.8,
        )
        assert result == pytest.approx(0.0072)


# ---------------------------------------------------------------------------
# TestKellySerialization — to_dict / from_dict 라운드트립
# ---------------------------------------------------------------------------


class TestKellySerialization:
    """직렬화/역직렬화 테스트"""

    def test_to_dict_empty(self, sizer):
        """빈 상태 직렬화"""
        data = sizer.to_dict()
        assert data["kelly_fraction"] == 0.25
        assert data["min_size_pct"] == 0.003
        assert data["max_size_pct"] == 0.02
        assert data["regime_trades"] == {}

    def test_to_dict_with_trades(self, sizer):
        """거래 기록 포함 직렬화"""
        sizer.record_trade("TRENDING", 0.01)
        sizer.record_trade("TRENDING", -0.005)
        sizer.record_trade("RANGING", 0.002)

        data = sizer.to_dict()
        assert len(data["regime_trades"]) == 2
        assert data["regime_trades"]["TRENDING"] == [0.01, -0.005]
        assert data["regime_trades"]["RANGING"] == [0.002]

    def test_round_trip_preserves_state(self, sizer):
        """to_dict → from_dict 라운드트립 후 상태 보존"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)
        for _ in range(5):
            sizer.record_trade("RANGING", 0.003)

        data = sizer.to_dict()

        new_sizer = KellySizer()
        new_sizer.from_dict(data)

        assert new_sizer.kelly_fraction == sizer.kelly_fraction
        assert new_sizer.min_size_pct == sizer.min_size_pct
        assert new_sizer.max_size_pct == sizer.max_size_pct
        assert list(new_sizer._regime_trades["TRENDING"]) == list(
            sizer._regime_trades["TRENDING"]
        )
        assert list(new_sizer._regime_trades["RANGING"]) == list(
            sizer._regime_trades["RANGING"]
        )

    def test_round_trip_kelly_calculation_matches(self, sizer):
        """복원 후 Kelly 계산 결과가 동일"""
        for _ in range(12):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(8):
            sizer.record_trade("TRENDING", -0.01)

        original_kelly = sizer.calculate_kelly_size("TRENDING")

        data = sizer.to_dict()
        new_sizer = KellySizer()
        new_sizer.from_dict(data)

        restored_kelly = new_sizer.calculate_kelly_size("TRENDING")
        assert restored_kelly == pytest.approx(original_kelly)

    def test_from_dict_restores_maxlen(self, sizer):
        """from_dict으로 복원 시 deque maxlen=100 유지"""
        for _ in range(50):
            sizer.record_trade("TRENDING", 0.01)

        data = sizer.to_dict()
        new_sizer = KellySizer()
        new_sizer.from_dict(data)

        assert new_sizer._regime_trades["TRENDING"].maxlen == 100

    def test_from_dict_partial_data(self, sizer):
        """일부 필드만 있는 딕셔너리에서도 복원"""
        sizer.from_dict({"kelly_fraction": 0.5})
        assert sizer.kelly_fraction == 0.5
        assert sizer.min_size_pct == 0.003
        assert sizer.max_size_pct == 0.02

    def test_from_dict_empty_dict(self, sizer):
        """빈 딕셔너리에서도 에러 없이 복원"""
        sizer.from_dict({})
        assert sizer.kelly_fraction == 0.25
        assert sizer._regime_trades == {}

    def test_round_trip_with_100_trades(self, sizer):
        """100건 가득 찬 deque 라운드트립"""
        for i in range(100):
            pnl = 0.02 if i % 3 != 0 else -0.01
            sizer.record_trade("TRENDING", pnl)

        data = sizer.to_dict()
        assert len(data["regime_trades"]["TRENDING"]) == 100

        new_sizer = KellySizer()
        new_sizer.from_dict(data)
        assert len(new_sizer._regime_trades["TRENDING"]) == 100

    def test_round_trip_multiple_regimes(self, sizer):
        """다중 레짐 라운드트립"""
        for _ in range(25):
            sizer.record_trade("TRENDING", 0.02)
        for _ in range(10):
            sizer.record_trade("RANGING", -0.005)
        for _ in range(5):
            sizer.record_trade("VOLATILE", 0.03)

        data = sizer.to_dict()
        new_sizer = KellySizer()
        new_sizer.from_dict(data)

        assert set(new_sizer._regime_trades.keys()) == {"TRENDING", "RANGING", "VOLATILE"}
        assert len(new_sizer._regime_trades["TRENDING"]) == 25
        assert len(new_sizer._regime_trades["RANGING"]) == 10
        assert len(new_sizer._regime_trades["VOLATILE"]) == 5
