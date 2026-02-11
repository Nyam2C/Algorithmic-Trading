"""
AI 모듈 커버리지 개선 테스트

gemini.py, scoring.py, ensemble.py의 미커버 라인을 대상으로 합니다.
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.ai.ensemble import (
    EnsembleSignalGenerator,
    IndividualSignal,
    SignalSource,
)
from src.ai.gemini import GeminiSignalGenerator
from src.ai.scoring import IndicatorScorer, ScoringResult

# =============================================================================
# Helper: Gemini generator fixture
# =============================================================================

def _make_generator(
    system_prompt="System",
    analysis_template="Analysis {{current_price}}",
    analysis_with_reason_template="AnalysisWithReason {{current_price}}",
):
    """Gemini generator 생성 헬퍼"""
    with patch("src.ai.gemini.genai.Client"):
        with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
            mock_load.side_effect = [
                system_prompt,
                analysis_template,
                analysis_with_reason_template,
            ]
            return GeminiSignalGenerator(api_key="test_key")


def _sample_market_data():
    """샘플 시장 데이터"""
    return {
        "current_price": 105000.0,
        "high_24h": 108000.0,
        "low_24h": 102000.0,
        "change_24h_pct": 2.5,
        "trend_2h_pct": 1.2,
        "trend_30min_pct": 0.5,
        "bullish_candles": 15,
        "bearish_candles": 9,
        "resistance": 108000.0,
        "support": 102000.0,
        "rsi": 55.0,
        "rsi_trend": "rising",
        "ma_7": 104500.0,
        "ma_25": 103000.0,
        "ma_99": 100000.0,
        "price_vs_ma7_pct": 0.48,
        "price_vs_ma7_pos": "above",
        "price_vs_ma25_pct": 1.94,
        "price_vs_ma25_pos": "above",
        "current_volume": 1500.0,
        "avg_volume": 1200.0,
        "volume_ratio": 1.25,
        "volume_trend": "increasing",
        "atr": 1500.0,
        "atr_pct": 1.43,
        "volatility_state": "normal",
        "dist_resistance_pct": 2.86,
        "dist_support_pct": -2.86,
    }


# =============================================================================
# Gemini: Lines 70-78 (_load_prompt FileNotFoundError and Exception)
# =============================================================================

class TestGeminiLoadPromptErrors:
    """_load_prompt 에러 처리 테스트 (lines 70-78)"""

    def test_load_prompt_file_not_found_analysis_with_reason(self, tmp_path):
        """analysis_with_reason.txt 없을 때 analysis.txt로 폴백 (lines 72-74)"""
        # 프롬프트 디렉토리 생성 (analysis_with_reason.txt 제외)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.txt").write_text("system prompt")
        (prompts_dir / "analysis.txt").write_text("analysis prompt")
        # analysis_with_reason.txt는 생성하지 않음

        with patch("src.ai.gemini.genai.Client"):
            with patch("src.ai.gemini.Path") as mock_path_cls:
                # Path(__file__).parent가 tmp_path를 가리키도록 설정
                mock_parent = MagicMock()
                mock_parent.__truediv__ = Mock(return_value=prompts_dir)
                mock_path_cls.return_value.parent = mock_parent

                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                # system.txt 로드
                generator.system_prompt = generator._load_prompt("system.txt")
                assert generator.system_prompt == "system prompt"

                # analysis.txt 로드
                generator.analysis_template = generator._load_prompt("analysis.txt")
                assert generator.analysis_template == "analysis prompt"

                # analysis_with_reason.txt → FileNotFoundError → analysis.txt 폴백
                generator.analysis_with_reason_template = generator._load_prompt("analysis_with_reason.txt")
                assert generator.analysis_with_reason_template == "analysis prompt"

    def test_load_prompt_file_not_found_other_file_raises(self, tmp_path):
        """system.txt 등 다른 파일이 없으면 예외 발생 (line 75: raise)"""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        # 파일 생성하지 않음

        with patch("src.ai.gemini.genai.Client"):
            with patch("src.ai.gemini.Path") as mock_path_cls:
                mock_parent = MagicMock()
                mock_parent.__truediv__ = Mock(return_value=prompts_dir)
                mock_path_cls.return_value.parent = mock_parent

                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                with pytest.raises(FileNotFoundError):
                    generator._load_prompt("system.txt")

    def test_load_prompt_generic_exception(self):
        """일반 예외 발생 시 re-raise (lines 76-78)"""
        with patch("src.ai.gemini.genai.Client"):

            def smart_open(path, *args, **kwargs):
                raise PermissionError("Permission denied")

            with patch("builtins.open", side_effect=smart_open):
                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                with pytest.raises(PermissionError):
                    generator._load_prompt("system.txt")


# =============================================================================
# Gemini: Lines 139-141 (_build_market_prompt exception)
# =============================================================================

class TestGeminiBuildMarketPromptError:
    """_build_market_prompt 에러 처리 (lines 139-141)"""

    def test_build_market_prompt_missing_key(self):
        """필수 데이터 누락 시 예외 (lines 139-141)"""
        generator = _make_generator()
        # 불완전한 데이터
        bad_data = {"current_price": 100000.0}  # 나머지 필드 없음

        with pytest.raises(KeyError):
            generator._build_market_prompt(bad_data)


# =============================================================================
# Gemini: Lines 227-228, 234-237 (get_signal_sync null/invalid response)
# =============================================================================

class TestGeminiGetSignalSyncEdgeCases:
    """get_signal_sync 엣지 케이스 (lines 227-228, 234-237)"""

    def test_get_signal_sync_null_response(self):
        """동기 호출 시 null 응답 → WAIT (lines 227-228)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = None
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal = generator.get_signal_sync(_sample_market_data())
        assert signal == "WAIT"

    def test_get_signal_sync_invalid_signal(self):
        """동기 호출 시 잘못된 신호 → WAIT (lines 234-237)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = "INVALID_RESPONSE"
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal = generator.get_signal_sync(_sample_market_data())
        assert signal == "WAIT"


# =============================================================================
# Gemini: Lines 310-312 (_build_market_prompt_with_reason exception)
# =============================================================================

class TestGeminiBuildMarketPromptWithReasonError:
    """_build_market_prompt_with_reason 에러 처리 (lines 310-312)"""

    def test_build_market_prompt_with_reason_error(self):
        """_build_market_prompt_with_reason 데이터 누락 시 예외"""
        generator = _make_generator()
        bad_data = {"current_price": 100000.0}  # 불완전

        with pytest.raises(KeyError):
            generator._build_market_prompt_with_reason(bad_data)


# =============================================================================
# Gemini: Lines 428-458 (get_signal_with_reason_sync)
# =============================================================================

class TestGeminiGetSignalWithReasonSync:
    """get_signal_with_reason_sync 테스트 (lines 428-458)"""

    def test_sync_with_reason_success(self):
        """동기 신호+이유 정상 반환 (lines 428-453)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = '{"signal": "LONG", "reason": "RSI 과매도"}'
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "LONG"
        assert "RSI" in reason or "과매도" in reason

    def test_sync_with_reason_null_response(self):
        """동기 null 응답 → WAIT + 응답 없음 (lines 446-448)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = None
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "WAIT"
        assert "응답 없음" in reason

    def test_sync_with_reason_api_error(self):
        """동기 API 에러 → WAIT + 오류 메시지 (lines 455-458)"""
        generator = _make_generator()
        generator.client.models.generate_content = Mock(
            side_effect=Exception("Connection error")
        )

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "WAIT"
        assert "API 오류" in reason


# =============================================================================
# Scoring: Lines 171, 197-198, 203-204, 209-210, 215-216
# =============================================================================

class TestScoringRSIEdgeCases:
    """RSI 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_rsi_extreme_oversold(self, scorer):
        """RSI < 20: 극단적 과매도 (lines 197-198)"""
        score = scorer._score_rsi(15.0)
        assert score.score == 1.0
        assert "극단적 과매도" in score.reason

    def test_rsi_low_zone(self, scorer):
        """RSI 30-40: 저점 근접 (lines 203-204)"""
        score = scorer._score_rsi(35.0)
        assert score.score > 0.3
        assert "저점 근접" in score.reason

    def test_rsi_high_zone(self, scorer):
        """RSI 60-70: 고점 근접 (lines 209-210)"""
        score = scorer._score_rsi(65.0)
        assert score.score < -0.3
        assert "고점 근접" in score.reason

    def test_rsi_extreme_overbought(self, scorer):
        """RSI > 80: 극단적 과매수 (lines 215-216)"""
        score = scorer._score_rsi(85.0)
        assert score.score == -1.0
        assert "극단적 과매수" in score.reason


# =============================================================================
# Scoring: Lines 239, 255-263, 266-267, 269-270
# =============================================================================

class TestScoringMATrendEdgeCases:
    """MA 추세 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_ma_trend_zero_values(self, scorer):
        """MA 값 0인 경우 (line 239)"""
        data = {"ma_7": 0, "ma_25": 0}
        score = scorer._score_ma_trend(data)
        assert score.score == 0
        assert "데이터 부족" in score.reason

    def test_ma_trend_ma7_above_ma25_with_ma99_but_not_all_aligned(self, scorer):
        """MA99가 있고 MA7>MA25이지만 완전 정렬이 아닌 경우 (lines 255-257)"""
        data = {
            "ma_7": 52000.0,
            "ma_25": 50000.0,
            "ma_99": 51000.0,  # MA25 < MA99 < MA7 → 완전 정렬 아님
        }
        score = scorer._score_ma_trend(data)
        assert score.score == 0.5
        assert "상승 추세" in score.reason

    def test_ma_trend_ma7_below_ma25_with_ma99_not_all_aligned(self, scorer):
        """MA99가 있고 MA7<MA25이지만 완전 하락 정렬이 아닌 경우 (lines 258-260)"""
        data = {
            "ma_7": 49000.0,
            "ma_25": 50000.0,
            "ma_99": 49500.0,  # MA7 < MA99 < MA25 → 완전 정렬 아님
        }
        score = scorer._score_ma_trend(data)
        assert score.score == -0.5
        assert "하락 추세" in score.reason

    def test_ma_trend_equal_with_ma99(self, scorer):
        """MA7 == MA25이고 MA99가 있는 경우 (lines 261-263)"""
        data = {
            "ma_7": 50000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,
        }
        score = scorer._score_ma_trend(data)
        assert score.score == 0.0
        assert "혼재" in score.reason

    def test_ma_trend_no_ma99_uptrend(self, scorer):
        """MA99 없이 MA7 > MA25 (lines 265-267)"""
        data = {"ma_7": 51000.0, "ma_25": 50000.0}
        score = scorer._score_ma_trend(data)
        assert score.score == 0.5
        assert "상승 추세" in score.reason

    def test_ma_trend_no_ma99_downtrend(self, scorer):
        """MA99 없이 MA7 < MA25 (lines 268-270)"""
        data = {"ma_7": 49000.0, "ma_25": 50000.0}
        score = scorer._score_ma_trend(data)
        assert score.score == -0.5
        assert "하락 추세" in score.reason


# =============================================================================
# Scoring: Lines 289-290, 298-299, 315-316, 318-319, 324-325
# =============================================================================

class TestScoringVolumeATREdgeCases:
    """볼륨, ATR 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_volume_high(self, scorer):
        """볼륨 > 2.0 (lines 289-290)"""
        score = scorer._score_volume(2.5)
        assert score.score == 0.5
        assert "높은 거래량" in score.reason

    def test_volume_low(self, scorer):
        """볼륨 < 0.8 (lines 298-299)"""
        score = scorer._score_volume(0.5)
        assert score.score == -0.2
        assert "낮은 거래량" in score.reason

    def test_atr_high_volatility(self, scorer):
        """ATR > 3.0: 높은 변동성 (lines 315-316)"""
        score = scorer._score_atr(3.5)
        assert score.score == -0.3
        assert "높은 변동성" in score.reason

    def test_atr_moderate_volatility(self, scorer):
        """ATR 1.5-3.0: 적정 변동성 (lines 318-319)"""
        score = scorer._score_atr(2.0)
        assert score.score == 0.2
        assert "적정 변동성" in score.reason

    def test_atr_very_low_volatility(self, scorer):
        """ATR < 0.5: 매우 낮은 변동성 (lines 324-325)"""
        score = scorer._score_atr(0.3)
        assert score.score == -0.2
        assert "매우 낮은 변동성" in score.reason


# =============================================================================
# Scoring: Lines 349-350, 357-358 (MACD)
# =============================================================================

class TestScoringMACDEdgeCases:
    """MACD 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_macd_strong_bullish(self, scorer):
        """MACD histogram > 50: 강한 상승 (lines 349-350)"""
        data = {"macd": 100, "macd_signal": 30, "macd_histogram": 70}
        score = scorer._score_macd(data)
        assert score.score == 0.8
        assert "강한 상승" in score.reason

    def test_macd_strong_bearish(self, scorer):
        """MACD histogram < -50: 강한 하락 (lines 357-358)"""
        data = {"macd": -100, "macd_signal": -30, "macd_histogram": -70}
        score = scorer._score_macd(data)
        assert score.score == -0.8
        assert "강한 하락" in score.reason


# =============================================================================
# Scoring: Lines 383-384, 389-390 (Price Position)
# =============================================================================

class TestScoringPricePositionEdgeCases:
    """가격 위치 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_price_overheated(self, scorer):
        """가격 MA25 위 3% 이상: 과열 (lines 383-384)"""
        data = {"price_vs_ma25_pct": 4.0}
        score = scorer._score_price_position(data)
        assert score.score == -0.3
        assert "과열" in score.reason

    def test_price_oversold(self, scorer):
        """가격 MA25 아래 3% 이상: 과매도 (lines 389-390)"""
        data = {"price_vs_ma25_pct": -4.0}
        score = scorer._score_price_position(data)
        assert score.score == 0.3
        assert "과매도" in score.reason


# =============================================================================
# Scoring: Line 171 (total_weight == 0)
# =============================================================================

class TestScoringEmptyData:
    """빈 데이터 스코어링 테스트"""

    def test_calculate_score_no_indicators(self):
        """지표가 없는 경우 total_score == 0 (line 171)"""
        scorer = IndicatorScorer()
        result = scorer.calculate_score({})
        assert result.total_score == 0.0
        assert result.signal == "WAIT"


# =============================================================================
# Ensemble: Lines 151, 155, 159 (set_XXX_generator)
# =============================================================================

class TestEnsembleSetGenerators:
    """앙상블 생성기 설정 테스트 (lines 151, 155, 159)"""

    def test_set_gemini_generator(self):
        """set_gemini_generator (line 151)"""
        ensemble = EnsembleSignalGenerator()
        mock_gen = MagicMock()
        ensemble.set_gemini_generator(mock_gen)
        assert ensemble._gemini is mock_gen

    def test_set_rule_based_generator(self):
        """set_rule_based_generator (line 155)"""
        ensemble = EnsembleSignalGenerator()
        mock_gen = MagicMock()
        ensemble.set_rule_based_generator(mock_gen)
        assert ensemble._rule_based is mock_gen

    def test_set_scoring_generator(self):
        """set_scoring_generator (line 159)"""
        ensemble = EnsembleSignalGenerator()
        mock_gen = MagicMock()
        ensemble.set_scoring_generator(mock_gen)
        assert ensemble._scoring is mock_gen


# =============================================================================
# Ensemble: Lines 191-192, 199-200, 204-205 (error handling in sources)
# =============================================================================

class TestEnsembleSourceErrors:
    """앙상블 소스 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_rule_based_error_caught(self):
        """규칙 기반 신호 에러 처리 (lines 191-192)"""
        mock_gemini = AsyncMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "AI 분석")
        )
        mock_rule = MagicMock()
        mock_rule.get_signal = MagicMock(side_effect=Exception("Rule error"))

        ensemble = EnsembleSignalGenerator(
            gemini_generator=mock_gemini,
            rule_based_generator=mock_rule,
        )

        result = await ensemble.generate_ensemble_signal({"rsi": 30}, "test")
        # 규칙 에러로 Gemini만 사용
        assert len(result.individual_signals) == 1
        assert result.individual_signals[0].source == SignalSource.GEMINI_AI

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


# =============================================================================
# Ensemble: Lines 243-244 (Gemini without get_signal_with_reason)
# =============================================================================

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


# =============================================================================
# Ensemble: Lines 281-283 (Scoring without calculate_score)
# =============================================================================

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


# =============================================================================
# Ensemble: Line 338 (consensus SHORT threshold)
# =============================================================================

class TestEnsembleConsensusShort:
    """앙상블 합의 SHORT 테스트 (line 338)"""

    @pytest.mark.asyncio
    async def test_consensus_short_by_ratio(self):
        """2/3 이상이 SHORT이면 합의 SHORT (line 338)"""
        ensemble = EnsembleSignalGenerator(weighted_threshold=10.0)  # 높은 임계값으로 가중 무효화

        signals = [
            IndividualSignal(SignalSource.GEMINI_AI, "SHORT", 0.1, "", 0.4),
            IndividualSignal(SignalSource.RULE_BASED, "SHORT", 0.1, "", 0.3),
            IndividualSignal(SignalSource.SCORING, "WAIT", 0.5, "", 0.3),
        ]

        final, score, ratio = ensemble._weighted_vote(signals)
        assert final == "SHORT"


# =============================================================================
# Ensemble: Line 361 (get_signal sync with no sources)
# =============================================================================

class TestEnsembleSyncNoSources:
    """동기 신호 소스 없음 테스트 (line 361)"""

    def test_get_signal_no_sources(self):
        """동기 호출 시 소스 없으면 WAIT (line 361)"""
        ensemble = EnsembleSignalGenerator()
        signal = ensemble.get_signal({"rsi": 50})
        assert signal == "WAIT"


# =============================================================================
# Ensemble: Lines 380-381 (get_signal_async)
# =============================================================================

class TestEnsembleGetSignalAsync:
    """get_signal_async 테스트 (lines 380-381)"""

    @pytest.mark.asyncio
    async def test_get_signal_async(self):
        """비동기 신호 반환 (lines 380-381)"""
        mock_gemini = AsyncMock()
        mock_gemini.get_signal_with_reason = AsyncMock(
            return_value=("LONG", "상승 추세")
        )
        mock_rule = MagicMock()
        mock_rule.get_signal = MagicMock(return_value="LONG")
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
            rule_based_generator=mock_rule,
            scoring_generator=mock_scoring,
        )

        signal = await ensemble.get_signal_async({"rsi": 30}, "test-bot")
        assert signal == "LONG"
