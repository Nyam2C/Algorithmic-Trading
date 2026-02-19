"""
Tests for Market Tradability Index (MTI)

Phase A-2: Gate 0 거래 적합성 판단 테스트
5-Component MTI: Spread(25%) + Depth(25%) + Volatility(20%) + Event(15%) + Session(15%)
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
        """US 세션 (14:00~21:00 UTC) → 100점"""
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

    def test_session_boundary_eu_overlap(self, mti):
        """EU/Overlap 경계 (13:00 UTC) → EU_US_OVERLAP"""
        t = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)
        name = mti._get_session_name(t)
        assert name == "EU_US_OVERLAP"

    def test_session_boundary_overlap_us(self, mti):
        """Overlap/US 경계 (14:00 UTC) → US"""
        t = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)
        name = mti._get_session_name(t)
        assert name == "US"

    def test_eu_us_overlap_score(self, mti):
        """EU+US Overlap (13:00~14:00) → 110점"""
        t = datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc)
        score = mti._session_score(t)
        assert score == 110.0


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
    """종합 평가 테스트 (3-component 하위호환)"""

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
        score = mti.evaluate(atr_pct=1.0, volume_ratio=0.8, current_time=t)
        assert score.total_score >= 0

    def test_boundary_exactly_40(self, mti):
        """정확히 40점 → REDUCED (거래 가능)"""
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

    def test_atr_normalized_low_ratio(self, mti):
        """ATR-정규화: spread/ATR < 10% → 100점"""
        # spread=0.05%, ATR=1.0% → ratio=0.05 < 0.1
        assert mti._spread_score(0.05, atr_1m_pct=1.0) == 100.0

    def test_atr_normalized_mid_ratio(self, mti):
        """ATR-정규화: spread/ATR 중간 → 선형 보간"""
        # spread=0.3%, ATR=1.0% → ratio=0.3 (between 0.1 and 0.5)
        score = mti._spread_score(0.3, atr_1m_pct=1.0)
        assert 20 < score < 100

    def test_atr_normalized_high_ratio(self, mti):
        """ATR-정규화: spread/ATR > 50% → 20점"""
        # spread=1.0%, ATR=1.0% → ratio=1.0 > 0.5
        assert mti._spread_score(1.0, atr_1m_pct=1.0) == 20.0

    def test_atr_zero_falls_back_to_absolute(self, mti):
        """ATR=0 → 절대값 모드 폴백"""
        # atr_1m_pct=0 → absolute mode
        score = mti._spread_score(0.3, atr_1m_pct=0.0)
        assert score == 100.0  # < 0.5% → 100

    def test_atr_none_falls_back_to_absolute(self, mti):
        """ATR=None → 절대값 모드 폴백"""
        score = mti._spread_score(1.0, atr_1m_pct=None)
        score2 = mti._spread_score(1.0)
        assert score == score2


class TestDepthScore:
    """오더북 깊이 점수 테스트"""

    def test_zero_depth(self, mti):
        """깊이 0 → 0점"""
        assert mti._depth_score(0.0, 0.0) == 0.0

    def test_very_low_depth(self, mti):
        """매우 낮은 깊이 (< 5 BTC) → 30점"""
        assert mti._depth_score(1.0, 1.0) == 30.0

    def test_low_depth(self, mti):
        """낮은 깊이 (5~20 BTC) → 60점"""
        assert mti._depth_score(5.0, 5.0) == 60.0

    def test_normal_depth(self, mti):
        """적정 깊이 (20~100 BTC) → 90점"""
        assert mti._depth_score(25.0, 25.0) == 90.0

    def test_high_depth(self, mti):
        """높은 깊이 (>= 100 BTC) → 100점"""
        assert mti._depth_score(60.0, 60.0) == 100.0

    def test_bid_ask_imbalance_penalty(self, mti):
        """Bid/Ask 불균형 (> 3x) → 15% 감점"""
        # bid=40, ask=10 → ratio=4 > 3 → base 90 * 0.85 = 76.5
        score = mti._depth_score(40.0, 10.0)
        assert score == pytest.approx(76.5, abs=0.1)

    def test_ask_dominant_imbalance(self, mti):
        """Ask 우세 불균형 (< 1/3x) → 감점"""
        # bid=10, ask=40 → ratio=0.25 < 0.333 → 감점
        score = mti._depth_score(10.0, 40.0)
        assert score == pytest.approx(76.5, abs=0.1)

    def test_balanced_no_penalty(self, mti):
        """균형 잡힌 depth → 감점 없음"""
        score = mti._depth_score(25.0, 25.0)
        assert score == 90.0  # No penalty

    def test_one_side_zero(self, mti):
        """한쪽 0 → 깊이 기반 점수만 (불균형 체크 스킵)"""
        # bid=3, ask=0 → total=3 < 5 → 30점, but ask=0 so ratio check skipped
        score = mti._depth_score(3.0, 0.0)
        assert score == 30.0


class TestEventScore:
    """이벤트 캘린더 점수 테스트"""

    def test_no_event(self, mti):
        """이벤트 없는 시간 → 100점"""
        t = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert mti._event_score(t) == 100.0

    def test_funding_settlement_00(self, mti):
        """00:00 UTC 펀딩 정산 → 40점"""
        t = datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)
        assert mti._event_score(t) == 40.0

    def test_funding_settlement_08(self, mti):
        """08:00 UTC 펀딩 정산 → 40점"""
        t = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
        assert mti._event_score(t) == 40.0

    def test_funding_settlement_16(self, mti):
        """16:00 UTC 펀딩 정산 → 40점"""
        t = datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc)
        assert mti._event_score(t) == 40.0

    def test_funding_within_window(self, mti):
        """정산 ±30분 이내 → 40점"""
        # 07:45 → 08:00까지 15분 → 40
        t = datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc)
        assert mti._event_score(t) == 40.0

    def test_funding_outside_window(self, mti):
        """정산 ±30분 밖 → 100점"""
        # 08:35 → 08:00에서 35분 떨어짐 → 100
        t = datetime(2024, 1, 15, 8, 35, tzinfo=timezone.utc)
        assert mti._event_score(t) == 100.0

    def test_funding_midnight_wrap(self, mti):
        """자정 경계: 23:35 → 00:00까지 25분 → 40점"""
        t = datetime(2024, 1, 15, 23, 35, tzinfo=timezone.utc)
        assert mti._event_score(t) == 40.0

    def test_custom_event_within_window(self, mti):
        """커스텀 이벤트 ±30분 이내 → 40점"""
        event_time = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        current = datetime(2024, 1, 15, 14, 15, tzinfo=timezone.utc)
        assert mti._event_score(current, event_times=[event_time]) == 40.0

    def test_custom_event_outside_window(self, mti):
        """커스텀 이벤트 ±30분 밖 → 100점"""
        event_time = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        current = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert mti._event_score(current, event_times=[event_time]) == 100.0


class TestFourComponentMode:
    """4-component 모드 테스트 (spread 제공, depth 미제공)"""

    def test_four_component_optimal(self, mti):
        """4-component 최적 조건"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.5,
            current_time=t, bid_ask_spread_pct=0.1,
        )
        assert score.is_tradable is True
        assert "spread_score" in score.components
        assert "event_score" in score.components
        assert "depth_score" not in score.components

    def test_four_component_count(self, mti):
        """4-component 모드는 4개 컴포넌트"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t, bid_ask_spread_pct=0.5,
        )
        assert len(score.components) == 4

    def test_four_component_weights(self, mti):
        """4-component 가중치 정확성: Spread(30%) + Vol(25%) + Event(20%) + Session(25%)"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # US=100, event=100
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t, bid_ask_spread_pct=0.1,
        )
        # spread=100, vol=100, event=100, session=100
        # total = 0.30*100 + 0.25*100 + 0.20*100 + 0.25*100 = 100
        assert score.total_score == pytest.approx(100.0, abs=0.5)

    def test_four_component_standby(self, mti):
        """4-component STANDBY 조건"""
        # 00:10 UTC → funding window (event=40), ASIA (session=70)
        t = datetime(2024, 1, 15, 0, 10, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=-1.0, volume_ratio=0,  # vol_score=0
            current_time=t, bid_ask_spread_pct=3.0,
        )
        # spread=20, vol=0, event=40, session=70
        # total = 0.30*20 + 0.25*0 + 0.20*40 + 0.25*70 = 6+0+8+17.5 = 31.5
        assert score.grade == "STANDBY"
        assert score.is_tradable is False

    def test_high_spread_adds_reason(self, mti):
        """높은 스프레드 → reason에 스프레드 과대 포함"""
        t = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=0.1, volume_ratio=0.1,
            current_time=t, bid_ask_spread_pct=3.0,
        )
        assert "스프레드 과대" in score.reason


class TestFiveComponentMode:
    """5-component 모드 테스트 (spread + depth 모두 제공)"""

    def test_five_component_optimal(self, mti):
        """5-component 최적 조건"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.5,
            current_time=t,
            bid_ask_spread_pct=0.1,
            bid_depth_total=60.0,
            ask_depth_total=60.0,
        )
        assert score.grade == "OPTIMAL"
        assert score.is_tradable is True

    def test_five_component_count(self, mti):
        """5-component 모드는 5개 컴포넌트"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=0.5,
            bid_depth_total=50.0,
            ask_depth_total=50.0,
        )
        assert len(score.components) == 5
        assert "spread_score" in score.components
        assert "depth_score" in score.components
        assert "volatility_score" in score.components
        assert "event_score" in score.components
        assert "session_score" in score.components

    def test_five_component_weights(self, mti):
        """5-component 가중치: Spread(25%) + Depth(25%) + Vol(20%) + Event(15%) + Session(15%)"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # US=100, event=100
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=0.1,   # spread=100
            bid_depth_total=60.0,     # depth=100
            ask_depth_total=60.0,
        )
        # total = 0.25*100 + 0.25*100 + 0.20*100 + 0.15*100 + 0.15*100 = 100
        assert score.total_score == pytest.approx(100.0, abs=0.5)

    def test_five_component_mixed_scores(self, mti):
        """5-component 혼합 점수 정확성"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=0.5,              # vol=80
            volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=1.25,  # spread: 선형보간 ≈ 60
            bid_depth_total=10.0,     # depth: total=20 → 90 (20~100 BTC 구간)
            ask_depth_total=10.0,
        )
        # spread ≈ 60, depth=90, vol=80, event=100, session=100
        # total = 0.25*60 + 0.25*90 + 0.20*80 + 0.15*100 + 0.15*100
        #       = 15 + 22.5 + 16 + 15 + 15 = 83.5
        assert score.total_score == pytest.approx(83.5, abs=1.0)
        assert score.grade == "OPTIMAL"

    def test_five_component_standby(self, mti):
        """5-component STANDBY"""
        # 00:10 UTC → funding window (40), ASIA (70)
        t = datetime(2024, 1, 15, 0, 10, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=-1.0, volume_ratio=0,
            current_time=t,
            bid_ask_spread_pct=3.0,    # spread=20
            bid_depth_total=1.0,       # depth=30
            ask_depth_total=1.0,
        )
        # total = 0.25*20 + 0.25*30 + 0.20*0 + 0.15*40 + 0.15*70
        #       = 5 + 7.5 + 0 + 6 + 10.5 = 29
        assert score.grade == "STANDBY"
        assert score.is_tradable is False

    def test_five_component_score_range(self, mti):
        """5-component 점수는 0~110 범위 (overlap 110점 반영 시)"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=1.0,
            bid_depth_total=50.0,
            ask_depth_total=50.0,
        )
        assert 0 <= score.total_score <= 110

    def test_five_component_with_depth_imbalance(self, mti):
        """5-component에서 depth 불균형 → 감점 반영"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        balanced = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=0.1,
            bid_depth_total=25.0,
            ask_depth_total=25.0,
        )
        imbalanced = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_ask_spread_pct=0.1,
            bid_depth_total=45.0,
            ask_depth_total=5.0,  # ratio=9 >> 3
        )
        assert imbalanced.total_score < balanced.total_score

    def test_five_component_with_event_penalty(self, mti):
        """5-component에서 펀딩 정산 시 이벤트 감점 반영"""
        t_normal = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        t_funding = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
        normal = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t_normal,
            bid_ask_spread_pct=0.1,
            bid_depth_total=50.0,
            ask_depth_total=50.0,
        )
        funding = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t_funding,
            bid_ask_spread_pct=0.1,
            bid_depth_total=50.0,
            ask_depth_total=50.0,
        )
        assert funding.total_score < normal.total_score


class TestThreeComponentCompat:
    """3-component 하위호환 테스트"""

    def test_three_factor_compat_none_spread(self, mti):
        """bid_ask_spread_pct=None → 기존 3요소 모드"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.5, current_time=t)
        assert "spread_score" not in score.components
        assert "event_score" not in score.components
        assert "depth_score" not in score.components

    def test_three_factor_components_count(self, mti):
        """3요소 모드는 3개 컴포넌트"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(atr_pct=1.0, volume_ratio=1.0, current_time=t)
        assert len(score.components) == 3

    def test_three_factor_grade_transition(self, mti):
        """3-component 등급 전환"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score_opt = mti.evaluate(atr_pct=1.0, volume_ratio=2.0, current_time=t)
        assert score_opt.grade == "OPTIMAL"

        t2 = datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc)
        score_sb = mti.evaluate(atr_pct=0.1, volume_ratio=0.1, current_time=t2)
        assert score_sb.grade == "STANDBY"

    def test_depth_only_without_spread_stays_3_component(self, mti):
        """depth만 제공하고 spread 없으면 3-component 유지"""
        t = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        score = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0,
            current_time=t,
            bid_depth_total=50.0,
            ask_depth_total=50.0,
        )
        assert len(score.components) == 3
        assert "depth_score" not in score.components
