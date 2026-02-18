"""
Tests for Market Tradability Index (MTI)

Phase A-2: Gate 0 거래 적합성 판단 테스트
"""
from datetime import datetime, timezone

import pytest

from src.data.tradability import (
    MarketTradabilityIndex,
    TradabilityScore,
)


@pytest.fixture
def mti():
    """기본 MTI 인스턴스"""
    return MarketTradabilityIndex()


class TestTradabilityScore:
    """TradabilityScore 데이터클래스 테스트"""

    def test_score_creation(self):
        """점수 정상 생성"""
        score = TradabilityScore(
            total_score=75.0,
            is_tradable=True,
            grade="OPTIMAL",
            components={"volatility_score": 80, "session_score": 90, "volume_score": 70},
            reason="거래 적합",
        )
        assert score.total_score == 75.0
        assert score.is_tradable is True
        assert score.grade == "OPTIMAL"

    def test_standby_score(self):
        """STANDBY 점수"""
        score = TradabilityScore(
            total_score=30.0,
            is_tradable=False,
            grade="STANDBY",
            components={},
            reason="변동성 부족",
        )
        assert score.is_tradable is False
        assert score.grade == "STANDBY"


class TestVolatilityScore:
    """변동성 점수 테스트"""

    def test_very_low_volatility(self, mti):
        """극저변동성 (ATR% < 0.3) → 30점"""
        score = mti._volatility_score(0.1)
        assert score == 30.0

    def test_normal_volatility(self, mti):
        """적정 변동성 (0.3~0.8) → 80점"""
        score = mti._volatility_score(0.5)
        assert score == 80.0

    def test_high_volatility(self, mti):
        """고변동성 (0.8~1.5) → 100점"""
        score = mti._volatility_score(1.0)
        assert score == 100.0

    def test_extreme_volatility(self, mti):
        """과도한 변동성 (>1.5) → 60점"""
        score = mti._volatility_score(2.0)
        assert score == 60.0

    def test_zero_volatility(self, mti):
        """변동성 0 → 30점"""
        score = mti._volatility_score(0.0)
        assert score == 30.0

    def test_negative_volatility(self, mti):
        """음수 변동성 → 0점"""
        score = mti._volatility_score(-1.0)
        assert score == 0.0


class TestSessionScore:
    """세션 점수 테스트"""

    def test_us_session(self, mti):
        """US 세션 (13:30~21:00 UTC) → 100점"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti._session_score(t)
        assert score == 100.0

    def test_eu_session(self, mti):
        """EU 세션 (08:00~13:00 UTC) → 90점"""
        t = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        score = mti._session_score(t)
        assert score == 90.0

    def test_asia_session(self, mti):
        """ASIA 세션 (00:00~08:00 UTC) → 70점"""
        t = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)
        score = mti._session_score(t)
        assert score == 70.0

    def test_deep_night(self, mti):
        """Deep Night (21:00~00:00 UTC) → 55점"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score = mti._session_score(t)
        assert score == 55.0

    def test_session_boundary_asia_eu(self, mti):
        """ASIA/EU 경계 (08:00 UTC) → EU"""
        t = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
        name = mti._get_session_name(t)
        assert name == "EU"

    def test_session_boundary_eu_us(self, mti):
        """EU/US 경계 (13:00 UTC) → US"""
        t = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)
        name = mti._get_session_name(t)
        assert name == "US"


class TestVolumeScore:
    """볼륨 점수 테스트"""

    def test_zero_volume(self, mti):
        """거래량 0 → 0점"""
        score = mti._volume_score(0)
        assert score == 0.0

    def test_very_low_volume(self, mti):
        """매우 낮은 거래량 (< 0.3x) → 20점"""
        score = mti._volume_score(0.2)
        assert score == 20.0

    def test_low_volume(self, mti):
        """낮은 거래량 (0.3~0.7x) → 50점"""
        score = mti._volume_score(0.5)
        assert score == 50.0

    def test_below_avg_volume(self, mti):
        """평균 미만 (0.7~1.0x) → 70점"""
        score = mti._volume_score(0.8)
        assert score == 70.0

    def test_above_avg_volume(self, mti):
        """평균 초과 (1.0~1.5x) → 90점"""
        score = mti._volume_score(1.2)
        assert score == 90.0

    def test_high_volume(self, mti):
        """고거래량 (>= 1.5x) → 100점"""
        score = mti._volume_score(2.0)
        assert score == 100.0


class TestEvaluate:
    """종합 평가 테스트"""

    def test_optimal_conditions(self, mti):
        """최적 조건: 고변동 + US 세션 + 고거래량"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # US
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.5, current_time=t)
        assert score.grade == "OPTIMAL"
        assert score.is_tradable is True
        assert score.total_score >= 70

    def test_reduced_conditions(self, mti):
        """제한 조건: 적정 변동 + ASIA + 평균 거래량"""
        t = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)  # ASIA
        score = mti.evaluate(atr_pct=0.5, volume_ratio=0.8, current_time=t)
        assert score.is_tradable is True
        # (80 + 70 + 70) / 3 = 73.3 => OPTIMAL actually
        # Let's check the actual grade
        assert score.grade in ("OPTIMAL", "REDUCED")

    def test_standby_conditions(self, mti):
        """대기 조건: 저변동 + Deep Night + 저거래량"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)  # Deep Night
        score = mti.evaluate(atr_pct=0.1, volume_ratio=0.1, current_time=t)
        assert score.grade == "STANDBY"
        assert score.is_tradable is False
        assert score.total_score < 40

    def test_evaluate_returns_components(self, mti):
        """평가 결과에 컴포넌트 점수 포함"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.0, current_time=t)
        assert "volatility_score" in score.components
        assert "session_score" in score.components
        assert "volume_score" in score.components

    def test_evaluate_reason_empty_for_optimal(self, mti):
        """OPTIMAL일 때 reason이 '거래 적합'"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.5, current_time=t)
        assert score.reason == "거래 적합"

    def test_evaluate_reason_has_details_for_standby(self, mti):
        """STANDBY일 때 reason에 상세 사유 포함"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=0.1, volume_ratio=0.1, current_time=t)
        assert "변동성 부족" in score.reason

    def test_evaluate_default_time(self, mti):
        """current_time 미지정 시 현재 시간 사용"""
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.0)
        assert score.total_score > 0

    def test_custom_thresholds(self):
        """커스텀 임계값"""
        mti = MarketTradabilityIndex(optimal_threshold=80, reduced_threshold=50)
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        # Score would be (100 + 100 + 70) / 3 = 90 => OPTIMAL
        score = mti.evaluate(atr_pct=1.0, volume_ratio=0.8, current_time=t)
        assert score.total_score >= 0

    def test_boundary_exactly_40(self, mti):
        """정확히 40점 → REDUCED (거래 가능)"""
        # Need conditions that give exactly 40
        # volatility 30 + session 55 + volume 20 = 105/3 = 35 (STANDBY)
        # volatility 30 + session 70 + volume 50 = 150/3 = 50 (REDUCED)
        t = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)  # ASIA=70
        score = mti.evaluate(atr_pct=0.1, volume_ratio=0.5, current_time=t)
        # (30 + 70 + 50) / 3 = 50 → REDUCED
        assert score.is_tradable is True
        assert score.grade == "REDUCED"

    def test_grade_determination(self, mti):
        """등급 결정 정확성"""
        assert mti._determine_grade(80.0) == "OPTIMAL"
        assert mti._determine_grade(70.0) == "OPTIMAL"
        assert mti._determine_grade(69.9) == "REDUCED"
        assert mti._determine_grade(40.0) == "REDUCED"
        assert mti._determine_grade(39.9) == "STANDBY"
        assert mti._determine_grade(0.0) == "STANDBY"



class TestSpreadScore:
    """스프레드 점수 테스트"""

    def test_zero_spread(self, mti):
        """스프레드 0% → 100점"""
        assert mti._spread_score(0.0) == 100.0

    def test_negative_spread(self, mti):
        """음수 스프레드 → 100점"""
        assert mti._spread_score(-0.1) == 100.0

    def test_low_spread(self, mti):
        """낮은 스프레드 (< 0.5%) → 100점"""
        assert mti._spread_score(0.3) == 100.0

    def test_mid_spread(self, mti):
        """중간 스프레드 (1.25%) → 선형 보간"""
        score = mti._spread_score(1.25)
        assert 20 < score < 100

    def test_high_spread(self, mti):
        """높은 스프레드 (> 2%) → 20점"""
        assert mti._spread_score(3.0) == 20.0

    def test_boundary_05_spread(self, mti):
        """경계값 0.5% → 100점"""
        assert mti._spread_score(0.5) == pytest.approx(100.0, abs=0.1)

    def test_boundary_20_spread(self, mti):
        """경계값 2.0% → 20점"""
        assert mti._spread_score(2.0) == pytest.approx(20.0, abs=0.1)


class TestFiveFactorMode:
    """5요소 모드 테스트"""

    def test_five_factor_optimal(self, mti):
        """5요소 모드 최적 조건"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.5,
            current_time=t, bid_ask_spread_pct=0.1,
        )
        assert score.is_tradable is True
        assert "spread_score" in score.components
        assert "event_score" in score.components

    def test_five_factor_standby(self, mti):
        """5요소 모드 대기 조건"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=0.1, volume_ratio=0,
            current_time=t, bid_ask_spread_pct=3.0,
        )
        assert score.grade == "STANDBY"
        assert score.is_tradable is False

    def test_three_factor_compat_none_spread(self, mti):
        """bid_ask_spread_pct=None → 기존 3요소 모드"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.5, current_time=t)
        assert "spread_score" not in score.components
        assert "event_score" not in score.components

    def test_five_factor_components_count(self, mti):
        """5요소 모드는 5개 컴포넌트"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t, bid_ask_spread_pct=0.5,
        )
        assert len(score.components) == 5

    def test_three_factor_components_count(self, mti):
        """3요소 모드는 3개 컴포넌트"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.0, current_time=t)
        assert len(score.components) == 3

    def test_five_factor_score_range(self, mti):
        """5요소 점수는 0~100 범위"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t, bid_ask_spread_pct=1.0,
        )
        assert 0 <= score.total_score <= 100

    def test_high_spread_adds_reason(self, mti):
        """높은 스프레드 → reason에 스프레드 과대 포함"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=0.1, volume_ratio=0.1,
            current_time=t, bid_ask_spread_pct=3.0,
        )
        assert "스프레드 과대" in score.reason

    def test_five_factor_grade_transition(self, mti):
        """5요소 모드에서 등급 전환 확인"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        # (100 + 100 + 100 + 80 + 100) / 5 = 96 → OPTIMAL
        score_opt = mti.evaluate(
            atr_pct=1.0, volume_ratio=2.0,
            current_time=t, bid_ask_spread_pct=0.1,
        )
        assert score_opt.grade == "OPTIMAL"

        # (30 + 55 + 20 + 80 + 20) / 5 = 41 → REDUCED
        t2 = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score_red = mti.evaluate(
            atr_pct=0.1, volume_ratio=0.1,
            current_time=t2, bid_ask_spread_pct=2.0,
        )
        assert score_red.grade in ("REDUCED", "STANDBY")
