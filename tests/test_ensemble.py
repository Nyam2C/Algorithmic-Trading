"""
AI 앙상블 시스템 테스트

Phase 6.3: 가중 투표, 합의, 스코어링 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ai.ensemble import (
    EnsembleSignalGenerator,
    EnsembleResult,
    IndividualSignal,
    SignalSource,
)
from src.ai.scoring import (
    IndicatorScorer,
    IndicatorScore,
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
            source=SignalSource.RULE_BASED,
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
    def mock_rule_based(self):
        """Mock 규칙 기반 생성기"""
        mock = MagicMock()
        mock.get_signal = MagicMock(return_value="LONG")
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
    def ensemble(self, mock_gemini, mock_rule_based, mock_scoring):
        """테스트용 앙상블 생성기"""
        return EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            rule_based_generator=mock_rule_based,
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
        assert len(result.individual_signals) == 3
        assert result.consensus_ratio == 1.0  # 만장일치

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_mixed(
        self, mock_gemini, mock_rule_based, market_data
    ):
        """혼합 신호 앙상블 테스트"""
        # Gemini: LONG, RuleBased: SHORT, Scoring: LONG
        mock_rule_based.get_signal = MagicMock(return_value="SHORT")
        mock_scoring = MagicMock()
        mock_scoring.calculate_score = MagicMock(
            return_value=ScoringResult(
                total_score=0.5,
                signal="LONG",
                confidence=0.7,
                reasons=[],
            )
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            rule_based_generator=mock_rule_based,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # 2/3 LONG (Gemini + Scoring) vs 1/3 SHORT (RuleBased)
        assert result.final_signal == "LONG"
        assert result.consensus_ratio == pytest.approx(2 / 3)

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_all_wait(
        self, mock_gemini, mock_rule_based, mock_scoring, market_data
    ):
        """모두 WAIT일 때 앙상블 테스트"""
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("WAIT", "관망")
        )
        mock_rule_based.get_signal = MagicMock(return_value="WAIT")
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
            rule_based_generator=mock_rule_based,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        assert result.final_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_no_consensus(
        self, mock_gemini, mock_rule_based, mock_scoring, market_data
    ):
        """합의 실패 시 WAIT 테스트"""
        # LONG, SHORT, WAIT 각각
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "상승")
        )
        mock_rule_based.get_signal = MagicMock(return_value="SHORT")
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
            rule_based_generator=mock_rule_based,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # 합의 실패 -> WAIT
        assert result.final_signal == "WAIT"

    def test_get_signal_sync(self, mock_rule_based, mock_scoring, market_data):
        """동기 신호 반환 테스트 (Gemini 없이)"""
        ensemble = EnsembleSignalGenerator(
            rule_based_generator=mock_rule_based,
            scoring_generator=mock_scoring,
        )

        signal = ensemble.get_signal(market_data)

        assert signal in ["LONG", "SHORT", "WAIT"]

    @pytest.mark.asyncio
    async def test_generate_ensemble_signal_with_error(
        self, mock_rule_based, mock_scoring, market_data
    ):
        """일부 소스 오류 시 테스트"""
        # Gemini 오류
        mock_gemini_error = AsyncMock()
        mock_gemini_error.get_signal_with_reason = AsyncMock(
            side_effect=Exception("API Error")
        )

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini_error,
            rule_based_generator=mock_rule_based,
            scoring_generator=mock_scoring,
        )

        result = await ensemble.generate_ensemble_signal(market_data, "test-bot")

        # Gemini 제외, 나머지로 결정
        assert len(result.individual_signals) == 2
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
                    source=SignalSource.RULE_BASED,
                    signal="LONG",
                    confidence=1.0,
                    reason="규칙 기반",
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
            IndividualSignal(SignalSource.RULE_BASED, "LONG", 1.0, "", 0.3),
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
            IndividualSignal(SignalSource.RULE_BASED, "SHORT", 1.0, "", 0.3),
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
