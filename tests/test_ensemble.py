"""
AI 앙상블 시스템 테스트

Phase 6.3: 가중 투표, 합의, 스코어링 테스트
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.ensemble import (
    EnsembleResult,
    EnsembleSignalGenerator,
    IndividualSignal,
    SignalSource,
)
from src.ai.scoring import (
    IndicatorScore,
    IndicatorScorer,
    ScoringResult,
)


class TestIndicatorScore:
    """IndicatorScore 테스트"""

    def test_weighted_score_long(self):
        """LONG 신호 가중 점수 테스트"""
        score = IndicatorScore(
            name="rsi",
            value=30.0,
            score=0.8,
            weight=0.5,
        )

        # 점수 * 가중치
        assert score.weighted_score() == 0.4

    def test_weighted_score_short(self):
        """SHORT 신호는 weighted_score가 음수가 아님 (점수 자체가 음수)"""
        score = IndicatorScore(
            name="rsi",
            value=75.0,
            score=-0.8,
            weight=0.5,
        )

        assert score.weighted_score() == -0.4


class TestIndicatorScorer:
    """IndicatorScorer 테스트"""

    @pytest.fixture
    def scorer(self):
        """테스트용 스코어러"""
        return IndicatorScorer()

    @pytest.fixture
    def bullish_market_data(self):
        """상승 시장 데이터"""
        return {
            "rsi": 28.0,  # 과매도
            "ma_7": 51000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,  # MA 상승 정렬
            "volume_ratio": 1.8,
            "atr_pct": 1.5,
            "macd": 100,
            "macd_signal": 50,
            "price_vs_ma25_pct": 2.0,
        }

    @pytest.fixture
    def bearish_market_data(self):
        """하락 시장 데이터"""
        return {
            "rsi": 75.0,  # 과매수
            "ma_7": 49000.0,
            "ma_25": 50000.0,
            "ma_99": 51000.0,  # MA 하락 정렬
            "volume_ratio": 1.5,
            "atr_pct": 1.5,
            "macd": -100,
            "macd_signal": -50,
            "price_vs_ma25_pct": -2.0,
        }

    @pytest.fixture
    def neutral_market_data(self):
        """중립 시장 데이터"""
        return {
            "rsi": 50.0,  # 중립
            "ma_7": 50000.0,
            "ma_25": 50000.0,
            "volume_ratio": 1.0,
            "atr_pct": 1.0,
            "macd": 0,
            "macd_signal": 0,
            "price_vs_ma25_pct": 0.0,
        }

    def test_score_rsi_oversold(self, scorer):
        """RSI 과매도 점수 테스트"""
        score = scorer._score_rsi(25.0)

        assert score.score > 0.5  # LONG 신호
        assert "과매도" in score.reason

    def test_score_rsi_overbought(self, scorer):
        """RSI 과매수 점수 테스트"""
        score = scorer._score_rsi(75.0)

        assert score.score < -0.5  # SHORT 신호
        assert "과매수" in score.reason

    def test_score_rsi_neutral(self, scorer):
        """RSI 중립 점수 테스트"""
        score = scorer._score_rsi(50.0)

        assert score.score == 0.0  # 중립
        assert "중립" in score.reason

    def test_score_ma_trend_bullish(self, scorer, bullish_market_data):
        """MA 상승 추세 점수 테스트"""
        score = scorer._score_ma_trend(bullish_market_data)

        assert score.score > 0  # LONG 방향
        assert "상승" in score.reason

    def test_score_ma_trend_bearish(self, scorer, bearish_market_data):
        """MA 하락 추세 점수 테스트"""
        score = scorer._score_ma_trend(bearish_market_data)

        assert score.score < 0  # SHORT 방향
        assert "하락" in score.reason

    def test_calculate_score_bullish(self, scorer, bullish_market_data):
        """상승 시장 종합 점수 테스트"""
        result = scorer.calculate_score(bullish_market_data)

        assert result.total_score > 0
        assert result.signal == "LONG"
        assert result.confidence > 0

    def test_calculate_score_bearish(self, scorer, bearish_market_data):
        """하락 시장 종합 점수 테스트"""
        result = scorer.calculate_score(bearish_market_data)

        assert result.total_score < 0
        assert result.signal == "SHORT"

    def test_calculate_score_neutral(self, scorer, neutral_market_data):
        """중립 시장 종합 점수 테스트"""
        result = scorer.calculate_score(neutral_market_data)

        assert abs(result.total_score) < 0.2
        assert result.signal == "WAIT"

    def test_get_signal(self, scorer, bullish_market_data):
        """간단한 신호 반환 테스트"""
        signal = scorer.get_signal(bullish_market_data)

        assert signal in ["LONG", "SHORT", "WAIT"]

    def test_get_signal_with_reason(self, scorer, bullish_market_data):
        """신호와 이유 반환 테스트"""
        signal, reason = scorer.get_signal_with_reason(bullish_market_data)

        assert signal in ["LONG", "SHORT", "WAIT"]
        assert len(reason) > 0


class TestScoringResult:
    """ScoringResult 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        result = ScoringResult(
            total_score=0.65,
            signal="LONG",
            confidence=0.65,
            indicator_scores=[
                IndicatorScore("rsi", 30.0, 0.8, 0.25, "RSI 과매도"),
            ],
            reasons=["RSI 과매도"],
        )

        data = result.to_dict()

        assert data["total_score"] == 0.65
        assert data["signal"] == "LONG"
        assert len(data["indicator_scores"]) == 1
        assert data["reasons"] == ["RSI 과매도"]


class TestIndividualSignal:
    """IndividualSignal 테스트"""

    def test_weighted_vote_long(self):
        """LONG 가중 투표 테스트"""
        signal = IndividualSignal(
            source=SignalSource.GEMINI_AI,
            signal="LONG",
            confidence=0.8,
            weight=0.4,
        )

        # LONG = +weight * confidence
        assert signal.weighted_vote() == pytest.approx(0.32)

    def test_weighted_vote_short(self):
        """SHORT 가중 투표 테스트"""
        signal = IndividualSignal(
            source=SignalSource.SCORING,
            signal="SHORT",
            confidence=1.0,
            weight=0.3,
        )

        # SHORT = -weight * confidence
        assert signal.weighted_vote() == pytest.approx(-0.3)

    def test_weighted_vote_wait(self):
        """WAIT 가중 투표 테스트"""
        signal = IndividualSignal(
            source=SignalSource.SCORING,
            signal="WAIT",
            confidence=0.7,
            weight=0.3,
        )

        # WAIT = 0
        assert signal.weighted_vote() == 0.0


class TestEnsembleSignalGenerator:
    """EnsembleSignalGenerator 테스트"""

    @pytest.fixture
    def mock_gemini(self):
        """Mock Gemini 생성기"""
        mock = AsyncMock()
        mock.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "RSI 과매도")
        )
        return mock

    @pytest.fixture
    def mock_scoring(self):
        """Mock 스코어링 생성기"""
        mock = MagicMock()
        mock.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.5,
                signal="LONG",
                confidence=0.7,
                reasons=["점수 기반"],
            )
        )
        return mock

    @pytest.fixture
    def ensemble(self, mock_gemini, mock_scoring):
        """테스트용 앙상블 생성기"""
        return EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

    @pytest.fixture
    def market_data(self):
        """테스트용 시장 데이터"""
        return {
            "rsi": 30.0,
            "ma_7": 51000.0,
            "ma_25": 50000.0,
        }

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_all_long(
        self, ensemble, market_data
    ):
        """모두 LONG일 때 앙상블 테스트"""
        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        assert result.final_signal == "LONG"
        assert len(result.individual_signals) == 2
        assert result.consensus_ratio == 1.0  # 만장일치

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_mixed(
        self, mock_gemini, market_data
    ):
        """혼합 신호 앙상블 테스트"""
        # Gemini: LONG, Scoring: SHORT
        mock_scoring = MagicMock()
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.5,
                signal="SHORT",
                confidence=0.7,
                reasons=[],
            )
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # Gemini LONG vs Scoring SHORT -> weighted vote decides
        assert result.final_signal in ("LONG", "SHORT", "WAIT")
        assert len(result.individual_signals) == 2

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_all_wait(
        self, mock_gemini, mock_scoring, market_data
    ):
        """모두 WAIT일 때 앙상블 테스트"""
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("WAIT", "관망")
        )
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.0,
                signal="WAIT",
                confidence=0.5,
                reasons=[],
            )
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        assert result.final_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_no_consensus(
        self, mock_gemini, mock_scoring, market_data
    ):
        """합의 실패 시 WAIT 테스트"""
        # Gemini: LONG, Scoring: WAIT
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "상승")
        )
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.0,
                signal="WAIT",
                confidence=0.5,
                reasons=[],
            )
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # Single LONG source passes MIN_SOURCES=1
        assert result.final_signal in ("LONG", "WAIT")

    def test_get_signal_sync(self, mock_scoring, market_data):
        """동기 신호 반환 테스트 (Gemini 없이)"""
        ensemble = EnsembleSignalGenerator(
            scoring_generator=mock_scoring,
        )

        signal = ensemble.get_signal(market_data)

        assert signal in ["LONG", "SHORT", "WAIT"]

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_with_error(
        self, mock_scoring, market_data
    ):
        """일부 소스 오류 시 테스트"""
        # Gemini 오류
        mock_gemini_error = AsyncMock()
        mock_gemini_error.get_signal_with_reason = AsyncMock(
            side_effect=Exception("API Error")
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini_error,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # Gemini 제외, scoring만 사용
        assert len(result.individual_signals) == 1
        assert result.final_signal in ["LONG", "SHORT", "WAIT"]


class TestEnsembleResult:
    """EnsembleResult 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        result = EnsembleResult(
            final_signal="LONG",
            individual_signals=[
                IndividualSignal(
                    source=SignalSource.GEMINI_AI,
                    signal="LONG",
                    confidence=0.8,
                    reason="AI 분석",
                    weight=0.4,
                ),
                IndividualSignal(
                    source=SignalSource.SCORING,
                    signal="LONG",
                    confidence=1.0,
                    reason="점수 기반",
                    weight=0.3,
                ),
            ],
            consensus_ratio=1.0,
            weighted_score=0.55,
            metadata={"bot_id": "test"},
        )

        data = result.to_dict()

        assert data["final_signal"] == "LONG"
        assert len(data["individual_signals"]) == 2
        assert data["consensus_ratio"] == 1.0
        assert data["weighted_score"] == 0.55
        assert data["metadata"]["bot_id"] == "test"


class TestWeightedVoting:
    """가중 투표 테스트"""

    def test_weighted_vote_strong_long(self):
        """강한 LONG 가중 투표 테스트"""
        ensemble = EnsembleSignalGenerator()

        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "LONG", 1.0, "", 0.4),
            IndividualSignal(SignalSource.SCORING, "LONG", 1.0, "", 0.45),
            IndividualSignal(SignalSource.SCORING, "WAIT", 0.5, "", 0.3),
        ]

        final, score, ratio = ensemble._weighted_vote(signals)

        assert final == "LONG"
        assert score > 0.3

    def test_weighted_vote_strong_short(self):
        """강한 SHORT 가중 투표 테스트"""
        ensemble = EnsembleSignalGenerator()

        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "SHORT", 1.0, "", 0.4),
            IndividualSignal(SignalSource.SCORING, "SHORT", 1.0, "", 0.45),
            IndividualSignal(SignalSource.SCORING, "SHORT", 0.8, "", 0.3),
        ]

        final, score, ratio = ensemble._weighted_vote(signals)

        assert final == "SHORT"
        assert score < -0.3

    def test_weighted_vote_empty(self):
        """빈 신호 리스트 테스트"""
        ensemble = EnsembleSignalGenerator()

        final, score, ratio = ensemble._weighted_vote([])

        assert final == "WAIT"
        assert score == 0.0
        assert ratio == 0.0


# =============================================================================
# Coverage tests merged from test_ai_coverage.py
# =============================================================================


class TestEnsembleSetGenerators:
    """앙상블 생성기 설정 테스트 (lines 151, 155, 159)"""

    def test_set_gemini_generator(self):
        """set_gemini_generator (line 151)"""
        ensemble = EnsembleSignalGenerator()
        mock_gen = MagicMock()
        ensemble.set_gemini_generator(mock_gen)
        assert ensemble._gemini is mock_gen

    def test_set_scoring_generator(self):
        """set_scoring_generator (line 159)"""
        ensemble = EnsembleSignalGenerator()
        mock_gen = MagicMock()
        ensemble.set_scoring_generator(mock_gen)
        assert ensemble._scoring is mock_gen


class TestEnsembleSourceErrors:
    """앙상블 소스 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_scoring_error_caught(self):
        """스코어링 신호 에러 처리 (lines 199-200)"""
        mock_gemini = AsyncMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("SHORT", "하락 추세")
        )
        mock_scoring = MagicMock()
        mock_scoring.calculate_score = MagicMock(side_effect=Exception("Score error"))

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal({"rsi": 70}, "test")
        assert len(result.individual_signals) == 1

    @pytest.mark.asyncio
    async def test_no_signal_sources(self):
        """모든 소스 없음 → WAIT (lines 203-205)"""
        ensemble = EnsembleSignalGenerator()  # 아무 생성기도 없음

        result = await ensemble.generate_ensemble_signal({"rsi": 50}, "test")
        assert result.final_signal == "WAIT"
        assert result.metadata.get("error") == "신호 소스 없음"


class TestEnsembleGeminiFallback:
    """Gemini get_signal 폴백 테스트 (lines 243-244)"""

    @pytest.mark.asyncio
    async def test_gemini_without_reason(self):
        """get_signal_with_reason 없으면 get_signal 사용"""
        mock_gemini = AsyncMock()
        # get_signal_with_reason 속성이 없음
        del mock_gemini.get_signal_with_reason
        mock_gemini.get_signal = AsyncMock(return_value="LONG")

        ensemble = EnsembleSignalGenerator(gemini_generator=mock_gemini)

        result = await ensemble.generate_ensemble_signal({"rsi": 30}, "test")
        assert len(result.individual_signals) == 1
        assert result.individual_signals[0].signal == "LONG"
        assert result.individual_signals[0].reason == "Gemini AI 분석"


class TestEnsembleScoringFallback:
    """스코어링 폴백 테스트 (lines 281-283)"""

    @pytest.mark.asyncio
    async def test_scoring_without_calculate_score(self):
        """calculate_score 없으면 get_signal 사용"""
        mock_scoring = MagicMock()
        del mock_scoring.calculate_score
        mock_scoring.get_signal = MagicMock(return_value="SHORT")

        ensemble = EnsembleSignalGenerator(scoring_generator=mock_scoring)

        result = await ensemble.generate_ensemble_signal({"rsi": 70}, "test")
        assert len(result.individual_signals) == 1
        sig = result.individual_signals[0]
        assert sig.signal == "SHORT"
        assert sig.confidence == 0.7
        assert sig.reason == "점수 기반 분석"


class TestEnsembleConsensusShort:
    """앙상블 합의 SHORT 테스트 (line 338)"""

    @pytest.mark.asyncio
    async def test_consensus_short_by_ratio(self):
        """2/3 이상이 SHORT이면 합의 SHORT (line 338)"""
        ensemble = EnsembleSignalGenerator(weighted_threshold=10.0)  # 높은 임계값으로 가중 무효화

        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "SHORT", 0.1, "", 0.55),
            IndividualSignal(SignalSource.SCORING, "SHORT", 0.1, "", 0.45),
        ]

        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "SHORT"


class TestEnsembleSyncNoSources:
    """동기 신호 소스 없음 테스트 (line 361)"""

    def test_get_signal_no_sources(self):
        """동기 호출 시 소스 없으면 WAIT (line 361)"""
        ensemble = EnsembleSignalGenerator()
        signal = ensemble.get_signal({"rsi": 50})
        assert signal == "WAIT"


class TestEnsembleGetSignalAsync:
    """get_signal_async 테스트 (lines 380-381)"""

    @pytest.mark.asyncio
    async def test_get_signal_async(self):
        """비동기 신호 반환 (lines 380-381)"""
        mock_gemini = AsyncMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "상승 추세")
        )
        mock_scoring = MagicMock()
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.5,
                signal="LONG",
                confidence=0.7,
                reasons=["점수"],
            )
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            scoring_generator=mock_scoring,
        )

        signal = await ensemble.get_signal_async({"rsi": 30}, "test-bot")
        assert signal == "LONG"



class TestWeightedThresholdAndMinSources:
    """Issue 15: Raised weighted threshold (0.5) and min 2 sources"""

    def test_weighted_threshold_is_0_3(self):
        """WEIGHTED_THRESHOLD class var should be 0.3 (aggressive)"""
        assert EnsembleSignalGenerator.WEIGHTED_THRESHOLD == 0.3

    def test_min_sources_is_1(self):
        """MIN_SOURCES class var should be 1 (single source allowed)"""
        assert EnsembleSignalGenerator.MIN_SOURCES == 1

    def test_single_source_long_passes(self):
        """Single source LONG should pass with MIN_SOURCES=1"""
        ensemble = EnsembleSignalGenerator()
        signals = [
            IndividualSignal(SignalSource.SCORING, "LONG", 1.0, "", 0.45),
        ]
        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "LONG"

    def test_single_source_short_passes(self):
        """Single source SHORT should pass with MIN_SOURCES=1"""
        ensemble = EnsembleSignalGenerator()
        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "SHORT", 1.0, "", 0.4),
        ]
        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "SHORT"

    def test_two_sources_long_passes(self):
        """Two sources LONG should pass weighted threshold"""
        ensemble = EnsembleSignalGenerator()
        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "LONG", 1.0, "", 0.4),
            IndividualSignal(SignalSource.SCORING, "LONG", 1.0, "", 0.45),
        ]
        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "LONG"

    def test_two_sources_short_passes(self):
        """Two sources SHORT should pass weighted threshold"""
        ensemble = EnsembleSignalGenerator()
        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "SHORT", 1.0, "", 0.4),
            IndividualSignal(SignalSource.SCORING, "SHORT", 1.0, "", 0.45),
        ]
        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "SHORT"

    def test_low_confidence_still_passes_with_0_3_threshold(self):
        """Low confidence score=0.4 passes 0.3 threshold"""
        ensemble = EnsembleSignalGenerator()
        # Two sources but low confidence -> weighted score around 0.4
        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "LONG", 0.4, "", 0.4),
            IndividualSignal(SignalSource.SCORING, "LONG", 0.4, "", 0.45),
        ]
        final, score, ratio = ensemble._weighted_vote(signals)
        # Score is 0.4*0.4/0.7 + 0.4*0.3/0.7 = 0.28/0.7 = 0.4 >= 0.3 threshold
        assert final == "LONG"

    @pytest.mark.asyncio
    async def test_single_source_ensemble_returns_signal(self):
        """Full ensemble with single source should return signal (MIN_SOURCES=1)"""
        mock_scoring = MagicMock()
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.5,
                signal="LONG",
                confidence=0.7,
                reasons=["test"],
            )
        )

        ensemble = EnsembleSignalGenerator(
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal({"rsi": 30}, "test")
        # Single source now passes with MIN_SOURCES=1
        assert result.final_signal == "LONG"
