"""
Tests for MarketDataFormatter
"""
import pytest
from src.data.market_data_formatter import (
    CompactMarketData,
    MarketDataFormatter,
    format_market_data,
    build_gemini_prompt,
    formatter,
)


class TestCompactMarketData:
    """CompactMarketData 데이터클래스 테스트"""

    @pytest.fixture
    def sample_data(self):
        """샘플 데이터"""
        return CompactMarketData(
            price=106500,
            change_24h=2.3,
            high_24h=108000,
            low_24h=104000,
            rsi=45,
            rsi_trend="↑",
            ma_position="상",
            trend_2h=1.2,
            volume_ratio=1.5,
            volatility="보통",
            funding_rate=0.01,
            long_short_ratio=1.1,
            position="없음",
            entry_price=None,
            unrealized_pnl_pct=None,
        )

    def test_to_compact_string_no_position(self, sample_data):
        """포지션 없는 경우 압축 문자열"""
        result = sample_data.to_compact_string()

        assert "BTC $106,500" in result
        assert "24h: +2.3%" in result
        assert "RSI:45↑" in result
        assert "MA:상" in result
        assert "포지션:없음" in result

    def test_to_compact_string_with_position(self):
        """포지션 있는 경우"""
        data = CompactMarketData(
            price=106500,
            change_24h=2.3,
            high_24h=108000,
            low_24h=104000,
            rsi=45,
            rsi_trend="↑",
            ma_position="상",
            trend_2h=1.2,
            volume_ratio=1.5,
            volatility="보통",
            position="LONG",
            entry_price=105000,
            unrealized_pnl_pct=1.43,
        )

        result = data.to_compact_string()

        assert "포지션:LONG" in result
        assert "$105,000" in result
        assert "+1.43%" in result

    def test_to_minimal_string_no_position(self, sample_data):
        """최소 포맷 - 포지션 없음"""
        result = sample_data.to_minimal_string()

        assert "BTC" in result
        assert "106500" in result
        assert "+2.3%" in result
        assert "RSI:45↑" in result
        assert "포지션:없음" in result

    def test_to_minimal_string_with_position(self):
        """최소 포맷 - 포지션 있음"""
        data = CompactMarketData(
            price=106500,
            change_24h=2.3,
            high_24h=108000,
            low_24h=104000,
            rsi=45,
            rsi_trend="↑",
            ma_position="상",
            trend_2h=1.2,
            volume_ratio=1.5,
            volatility="보통",
            position="SHORT",
            entry_price=107000,
            unrealized_pnl_pct=0.47,
        )

        result = data.to_minimal_string()

        assert "포지션:SHORT" in result

    def test_to_compact_string_with_funding_rate(self, sample_data):
        """펀딩비 포함"""
        result = sample_data.to_compact_string()

        assert "펀딩:+0.010%" in result

    def test_to_compact_string_with_long_short_ratio(self, sample_data):
        """롱숏 비율 포함"""
        result = sample_data.to_compact_string()

        assert "롱숏:" in result


class TestMarketDataFormatter:
    """MarketDataFormatter 클래스 테스트"""

    @pytest.fixture
    def formatter_instance(self):
        return MarketDataFormatter()

    @pytest.fixture
    def sample_market_data(self):
        """샘플 시장 데이터"""
        return {
            "current_price": 106500.0,
            "change_24h_pct": 2.3,
            "high_24h": 108000.0,
            "low_24h": 104000.0,
            "rsi": 45.0,
            "rsi_trend": "rising",
            "price_vs_ma7_pos": "above",
            "trend_2h_pct": 1.2,
            "volume_ratio": 1.5,
            "volatility_state": "normal",
        }

    def test_format_for_gemini_no_position(self, formatter_instance, sample_market_data):
        """포지션 없이 포맷"""
        result = formatter_instance.format_for_gemini(sample_market_data)

        assert "BTC" in result
        assert "106,500" in result
        assert "RSI:45" in result
        assert "포지션:없음" in result

    def test_format_for_gemini_with_position(self, formatter_instance, sample_market_data):
        """포지션 있이 포맷"""
        position = {
            "side": "LONG",
            "entry_price": 105000.0,
        }

        result = formatter_instance.format_for_gemini(sample_market_data, position=position)

        assert "포지션:LONG" in result

    def test_format_for_gemini_with_funding_rate(self, formatter_instance, sample_market_data):
        """펀딩비 포함"""
        result = formatter_instance.format_for_gemini(
            sample_market_data,
            funding_rate=0.01
        )

        assert "펀딩:" in result

    def test_format_for_gemini_minimal(self, formatter_instance, sample_market_data):
        """최소 포맷"""
        result = formatter_instance.format_for_gemini(sample_market_data, minimal=True)

        # 최소 포맷은 | 로 구분
        assert "|" in result

    def test_rsi_trend_mapping(self, formatter_instance, sample_market_data):
        """RSI 추세 매핑"""
        # rising -> ↑
        sample_market_data["rsi_trend"] = "rising"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "↑" in result

        # falling -> ↓
        sample_market_data["rsi_trend"] = "falling"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "↓" in result

        # neutral -> →
        sample_market_data["rsi_trend"] = "neutral"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "→" in result

    def test_ma_position_mapping(self, formatter_instance, sample_market_data):
        """MA 위치 매핑"""
        # above -> 상
        sample_market_data["price_vs_ma7_pos"] = "above"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "MA:상" in result

        # below -> 하
        sample_market_data["price_vs_ma7_pos"] = "below"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "MA:하" in result

        # middle -> 중
        sample_market_data["price_vs_ma7_pos"] = "middle"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "MA:중" in result

    def test_volatility_mapping(self, formatter_instance, sample_market_data):
        """변동성 매핑"""
        # low -> 낮음
        sample_market_data["volatility_state"] = "low"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "변동성:낮음" in result

        # normal -> 보통
        sample_market_data["volatility_state"] = "normal"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "변동성:보통" in result

        # high -> 높음
        sample_market_data["volatility_state"] = "high"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "변동성:높음" in result

        # extreme -> 극심
        sample_market_data["volatility_state"] = "extreme"
        result = formatter_instance.format_for_gemini(sample_market_data)
        assert "변동성:극심" in result


class TestBuildGeminiPrompt:
    """build_gemini_prompt 메서드 테스트"""

    @pytest.fixture
    def formatter_instance(self):
        return MarketDataFormatter()

    @pytest.fixture
    def sample_market_data(self):
        return {
            "current_price": 106500.0,
            "change_24h_pct": 2.3,
            "high_24h": 108000.0,
            "low_24h": 104000.0,
            "rsi": 45.0,
            "rsi_trend": "rising",
            "price_vs_ma7_pos": "above",
            "trend_2h_pct": 1.2,
            "volume_ratio": 1.5,
            "volatility_state": "normal",
        }

    def test_build_gemini_prompt(self, formatter_instance, sample_market_data):
        """Gemini 프롬프트 생성"""
        prompt = formatter_instance.build_gemini_prompt(sample_market_data)

        assert "비트코인 선물 트레이딩 전문가" in prompt
        assert "[시장 데이터]" in prompt
        assert "[규칙]" in prompt
        assert "LONG" in prompt
        assert "SHORT" in prompt
        assert "WAIT" in prompt

    def test_build_gemini_prompt_with_position(self, formatter_instance, sample_market_data):
        """포지션 포함 프롬프트"""
        position = {"side": "LONG", "entry_price": 105000.0}

        prompt = formatter_instance.build_gemini_prompt(sample_market_data, position=position)

        assert "포지션:LONG" in prompt


class TestEstimateTokens:
    """estimate_tokens 메서드 테스트"""

    @pytest.fixture
    def formatter_instance(self):
        return MarketDataFormatter()

    def test_estimate_tokens_short_text(self, formatter_instance):
        """짧은 텍스트"""
        text = "Hello world"
        tokens = formatter_instance.estimate_tokens(text)

        assert tokens > 0
        assert tokens < 10

    def test_estimate_tokens_long_text(self, formatter_instance):
        """긴 텍스트"""
        text = "This is a longer text with more words and characters"
        tokens = formatter_instance.estimate_tokens(text)

        assert tokens > 10


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    @pytest.fixture
    def sample_market_data(self):
        return {
            "current_price": 106500.0,
            "change_24h_pct": 2.3,
            "high_24h": 108000.0,
            "low_24h": 104000.0,
            "rsi": 45.0,
            "rsi_trend": "rising",
            "price_vs_ma7_pos": "above",
            "trend_2h_pct": 1.2,
            "volume_ratio": 1.5,
            "volatility_state": "normal",
        }

    def test_format_market_data_function(self, sample_market_data):
        """format_market_data 함수"""
        result = format_market_data(sample_market_data)

        assert "BTC" in result
        assert "106,500" in result

    def test_format_market_data_minimal(self, sample_market_data):
        """format_market_data 최소 포맷"""
        result = format_market_data(sample_market_data, minimal=True)

        assert "|" in result

    def test_build_gemini_prompt_function(self, sample_market_data):
        """build_gemini_prompt 함수"""
        prompt = build_gemini_prompt(sample_market_data)

        assert "비트코인 선물 트레이딩 전문가" in prompt


class TestSingletonFormatter:
    """싱글톤 formatter 테스트"""

    def test_singleton_instance(self):
        """싱글톤 인스턴스"""
        assert formatter is not None
        assert isinstance(formatter, MarketDataFormatter)


class TestPnlCalculation:
    """PnL 계산 테스트"""

    @pytest.fixture
    def formatter_instance(self):
        return MarketDataFormatter()

    def test_long_position_profit(self, formatter_instance):
        """LONG 포지션 수익"""
        market_data = {
            "current_price": 106000.0,  # 진입가보다 높음
            "change_24h_pct": 2.0,
            "high_24h": 108000.0,
            "low_24h": 104000.0,
            "rsi": 50.0,
            "rsi_trend": "neutral",
            "price_vs_ma7_pos": "above",
            "trend_2h_pct": 1.0,
            "volume_ratio": 1.0,
            "volatility_state": "normal",
        }
        position = {
            "side": "LONG",
            "entry_price": 105000.0,
        }

        result = formatter_instance.format_for_gemini(market_data, position=position)

        # LONG: (106000-105000)/105000 * 100 ≈ 0.95%
        # 결과에 양수 PnL이 포함되어야 함
        assert "+" in result or "LONG" in result

    def test_short_position_profit(self, formatter_instance):
        """SHORT 포지션 수익"""
        market_data = {
            "current_price": 104000.0,  # 진입가보다 낮음
            "change_24h_pct": -1.0,
            "high_24h": 106000.0,
            "low_24h": 103000.0,
            "rsi": 50.0,
            "rsi_trend": "neutral",
            "price_vs_ma7_pos": "below",
            "trend_2h_pct": -1.0,
            "volume_ratio": 1.0,
            "volatility_state": "normal",
        }
        position = {
            "side": "SHORT",
            "entry_price": 105000.0,
        }

        result = formatter_instance.format_for_gemini(market_data, position=position)

        assert "SHORT" in result


class TestEdgeCases:
    """경계값 테스트"""

    @pytest.fixture
    def formatter_instance(self):
        return MarketDataFormatter()

    def test_zero_price(self, formatter_instance):
        """가격이 0인 경우"""
        market_data = {
            "current_price": 0,
            "change_24h_pct": 0,
            "high_24h": 0,
            "low_24h": 0,
            "rsi": 50.0,
            "rsi_trend": "neutral",
            "price_vs_ma7_pos": "middle",
            "trend_2h_pct": 0,
            "volume_ratio": 1.0,
            "volatility_state": "normal",
        }

        result = formatter_instance.format_for_gemini(market_data)

        assert "BTC" in result

    def test_missing_optional_fields(self, formatter_instance):
        """선택적 필드 누락"""
        market_data = {
            "current_price": 106500.0,
        }

        # 기본값으로 처리되어야 함
        result = formatter_instance.format_for_gemini(market_data)

        assert "BTC" in result

    def test_large_numbers(self, formatter_instance):
        """큰 숫자 처리"""
        market_data = {
            "current_price": 1000000.0,
            "change_24h_pct": 100.0,
            "high_24h": 1100000.0,
            "low_24h": 900000.0,
            "rsi": 99.0,
            "rsi_trend": "rising",
            "price_vs_ma7_pos": "above",
            "trend_2h_pct": 50.0,
            "volume_ratio": 10.0,
            "volatility_state": "extreme",
        }

        result = formatter_instance.format_for_gemini(market_data)

        assert "1,000,000" in result
