"""Shadow Mode 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance, ShadowComparison
from src.data.regime_detector import MarketRegime


class TestShadowComparison:
    """ShadowComparison 데이터클래스 테스트."""

    def test_direction_match(self):
        c = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="LONG",
            direction_match=True,
            primary_source="pipeline",
            shadow_source="shadow:legacy",
        )
        assert c.direction_match is True
        assert c.agreement_pct == 100.0

    def test_direction_mismatch(self):
        c = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="SHORT",
            direction_match=False,
            primary_source="pipeline",
            shadow_source="shadow:legacy",
        )
        assert c.direction_match is False
        assert c.agreement_pct == 0.0

    def test_wait_vs_signal(self):
        c = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="WAIT",
            direction_match=False,
            primary_source="rule_based",
            shadow_source="shadow:pipeline",
        )
        assert c.direction_match is False


class TestShadowModeIntegration:
    """Shadow Mode 통합 테스트."""

    def _make_bot(self, **kwargs) -> BotInstance:
        """테스트용 BotInstance 생성."""
        defaults = {
            "bot_name": "test-shadow",
            "symbol": "BTCUSDT",
            "risk_level": "low",
            "use_shadow_mode": True,
            "use_ensemble": False,
        }
        defaults.update(kwargs)
        config = BotConfig(**defaults)
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )
        return bot

    def test_shadow_mode_flag_off_by_default(self):
        """기본값은 shadow_mode OFF."""
        config = BotConfig(bot_name="test", symbol="BTCUSDT", risk_level="low")
        assert config.use_shadow_mode is False

    def test_shadow_mode_flag_on(self):
        config = BotConfig(
            bot_name="test", symbol="BTCUSDT", risk_level="low",
            use_shadow_mode=True,
        )
        assert config.use_shadow_mode is True

    @pytest.mark.asyncio
    async def test_shadow_preserves_state(self):
        """Shadow 실행 후 상태 복원 확인."""
        bot = self._make_bot()
        bot._current_regime = MarketRegime.STRONG_UPTREND
        bot._consecutive_wait_count = 5
        bot._last_mti_grade = "OPTIMAL"
        bot._last_mti_score = 80.0

        market_data = {
            "current_price": 50000.0,
            "indicators": {"rsi": 50, "atr_pct": 0.5, "volume_ratio": 1.0},
        }

        # Mock _generate_combined_signal to return a signal
        with patch.object(
            bot, "_generate_combined_signal",
            new_callable=AsyncMock,
            return_value=("LONG", "rule_based"),
        ):
            await bot._run_shadow_path(
                market_data,
                market_data["indicators"],
                None,
                "SHORT",
                "pipeline",
            )

        # State should be restored
        assert bot._current_regime == MarketRegime.STRONG_UPTREND
        assert bot._consecutive_wait_count == 5
        assert bot._last_mti_grade == "OPTIMAL"
        assert bot._last_mti_score == 80.0

    @pytest.mark.asyncio
    async def test_shadow_exception_doesnt_crash(self):
        """Shadow 예외 시 무시."""
        bot = self._make_bot()
        bot._current_regime = MarketRegime.UNKNOWN

        with patch.object(
            bot, "_generate_combined_signal",
            new_callable=AsyncMock,
            side_effect=RuntimeError("shadow error"),
        ):
            # Should not raise
            await bot._run_shadow_path(
                {"current_price": 50000},
                {},
                None,
                "LONG",
                "pipeline",
            )

        # State preserved
        assert bot._current_regime == MarketRegime.UNKNOWN

    def test_record_shadow_comparison_match(self):
        """일치 시 메트릭 기록."""
        bot = self._make_bot()
        bot._metrics = MagicMock()

        comparison = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="LONG",
            direction_match=True,
            primary_source="pipeline",
            shadow_source="shadow:legacy",
        )
        bot._record_shadow_comparison(comparison)
        bot._metrics.record_shadow_comparison.assert_called_once_with(
            "test-shadow", True, 100.0,
        )

    def test_record_shadow_comparison_mismatch(self):
        """불일치 시 메트릭 기록."""
        bot = self._make_bot()
        bot._metrics = MagicMock()

        comparison = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="SHORT",
            direction_match=False,
            primary_source="rule_based",
            shadow_source="shadow:pipeline",
        )
        bot._record_shadow_comparison(comparison)
        bot._metrics.record_shadow_comparison.assert_called_once_with(
            "test-shadow", False, 0.0,
        )

    def test_record_shadow_no_metrics(self):
        """메트릭 없어도 에러 안남."""
        bot = self._make_bot()
        bot._metrics = None

        comparison = ShadowComparison(
            primary_signal="LONG",
            shadow_signal="LONG",
            direction_match=True,
            primary_source="p",
            shadow_source="s",
        )
        # Should not raise
        bot._record_shadow_comparison(comparison)

    @pytest.mark.asyncio
    async def test_shadow_legacy_path(self):
        """confluence ON → shadow runs legacy."""
        bot = self._make_bot(use_confluence_engine=True)
        bot._current_regime = MarketRegime.STRONG_UPTREND

        with patch.object(
            bot, "_generate_combined_signal",
            new_callable=AsyncMock,
            return_value=("LONG", "ensemble"),
        ) as mock_gen:
            bot._metrics = MagicMock()
            await bot._run_shadow_path(
                {"current_price": 50000},
                {"rsi": 50},
                None,
                "LONG",
                "pipeline:confluence",
            )
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_shadow_pipeline_path(self):
        """confluence OFF → shadow runs pipeline."""
        bot = self._make_bot(use_confluence_engine=False)
        bot._current_regime = MarketRegime.STRONG_UPTREND

        with patch.object(
            bot, "_run_five_gate_pipeline",
            new_callable=AsyncMock,
            return_value=("SHORT", "pipeline:mti_block"),
        ) as mock_pipe:
            bot._metrics = MagicMock()
            await bot._run_shadow_path(
                {"current_price": 50000},
                {"rsi": 50},
                None,
                "LONG",
                "rule_based",
            )
            mock_pipe.assert_called_once()
