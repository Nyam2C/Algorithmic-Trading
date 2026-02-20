"""5-Gate Pipeline 통합 테스트.

APEX-V 모든 모듈을 하나의 파이프라인으로 연결하는 통합 검증.
"""
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.ensemble import EnsembleResult
from src.bot_config import BotConfig
from src.bot_instance import BotInstance
from src.data.regime_detector import MarketRegime

# =========================================================================
# Fixtures
# =========================================================================


def _make_config(**overrides: Any) -> BotConfig:
    """테스트용 BotConfig 생성."""
    defaults = {
        "bot_name": "test-5g",
        "symbol": "BTCUSDT",
        "use_regime_filter": True,
        "use_confluence_engine": True,
        "allow_weak_trend": False,
    }
    defaults.update(overrides)
    return BotConfig(**defaults)


def _make_bot(config: BotConfig | None = None, **kw: Any) -> BotInstance:
    """테스트용 BotInstance 생성 (최소 의존성)."""
    cfg = config or _make_config()
    bot = BotInstance(
        config=cfg,
        binance_api_key="test",
        binance_secret_key="test",
        **kw,
    )
    # Mock executor
    bot._executor = MagicMock()
    bot._executor.current_position = None
    bot._executor.get_position = AsyncMock(return_value=None)
    return bot


@dataclass
class FakeVitality:
    """VitalitySnapshot 대용."""
    level: Any
    sharpe_ratio: float = 1.0
    trade_count: int = 10
    avg_pnl_pct: float = 0.5


@dataclass
class FakeConfluenceResult:
    """ConfluenceResult 대용."""
    final_signal: str = "LONG"
    confluence_score: float = 0.7
    net_edge: float = 0.6
    threshold_used: float = 0.5
    vitality: Any = None
    step_details: dict = None

    def __post_init__(self) -> None:
        if self.step_details is None:
            self.step_details = {}


@dataclass
class FakeMTIScore:
    """TradabilityScore 대용."""
    total_score: float
    is_tradable: bool
    grade: str
    components: dict = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.components is None:
            self.components = {}


# =========================================================================
# Gate 0: MTI Tests
# =========================================================================


class TestGate0MTI:
    """Gate 0 MTI 검증."""

    @pytest.mark.asyncio
    async def test_gate0_mti_standby_returns_wait(self) -> None:
        """MTI STANDBY -> WAIT, 시그널 생성 호출 안 됨."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.1, "volume_ratio": 0.3, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        standby_score = FakeMTIScore(
            total_score=25.0, is_tradable=False, grade="STANDBY"
        )

        with patch(
            "src.data.tradability.MarketTradabilityIndex"
        ) as MockMTI:
            mock_mti = MagicMock()
            mock_mti.evaluate.return_value = standby_score
            MockMTI.return_value = mock_mti

            # Mock _generate_combined_signal should NOT be called
            bot._generate_combined_signal = AsyncMock()

            signal, source = await bot._run_five_gate_pipeline(
                market_data, indicators, None
            )

        assert signal == "WAIT"
        assert source == "pipeline:mti_block"
        bot._generate_combined_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_gate0_mti_optimal_passes(self) -> None:
        """MTI OPTIMAL -> Gate 1로 진행."""
        bot = _make_bot()
        indicators = {"atr_pct": 1.5, "volume_ratio": 2.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        optimal_score = FakeMTIScore(
            total_score=80.0, is_tradable=True, grade="OPTIMAL"
        )

        with patch(
            "src.data.tradability.MarketTradabilityIndex"
        ) as MockMTI:
            mock_mti = MagicMock()
            mock_mti.evaluate.return_value = optimal_score
            MockMTI.return_value = mock_mti

            bot._generate_combined_signal = AsyncMock(
                return_value=("LONG", "ensemble")
            )

            signal, source = await bot._run_five_gate_pipeline(
                market_data, indicators, None
            )

        # Should proceed past MTI
        assert signal != "pipeline:mti_block"
        bot._generate_combined_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_gate0_mti_reduced_sets_grade(self) -> None:
        """REDUCED grade가 _last_mti_grade에 설정됨."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.8, "volume_ratio": 1.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        reduced_score = FakeMTIScore(
            total_score=55.0, is_tradable=True, grade="REDUCED"
        )

        with patch(
            "src.data.tradability.MarketTradabilityIndex"
        ) as MockMTI:
            mock_mti = MagicMock()
            mock_mti.evaluate.return_value = reduced_score
            MockMTI.return_value = mock_mti

            bot._generate_combined_signal = AsyncMock(
                return_value=("LONG", "ensemble")
            )

            await bot._run_five_gate_pipeline(
                market_data, indicators, None
            )

        assert bot._last_mti_grade == "REDUCED"


# =========================================================================
# Gate 1: Regime Tests
# =========================================================================


class TestGate1Regime:
    """Gate 1 Regime 검증."""

    @pytest.mark.asyncio
    async def test_gate1_regime_sets_context(self) -> None:
        """indicators['regime'] 설정됨."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.0, "volume_ratio": 0.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        bot._generate_combined_signal = AsyncMock(
            return_value=("WAIT", "fallback")
        )

        await bot._run_five_gate_pipeline(
            market_data, indicators, None
        )

        assert "regime" in indicators
        assert isinstance(indicators["regime"], MarketRegime)
        assert "leverage" in indicators


# =========================================================================
# Gate 2+3: Signal + Confluence Tests
# =========================================================================


class TestGateSignalConfluence:
    """Gate 2+3 Signal + Confluence 검증."""

    @pytest.mark.asyncio
    async def test_gate2_signal_via_ensemble(self) -> None:
        """ensemble 호출 확인."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        bot._generate_combined_signal = AsyncMock(
            return_value=("SHORT", "ensemble")
        )

        signal, source = await bot._run_five_gate_pipeline(
            market_data, indicators, None
        )

        bot._generate_combined_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_gate3_confluence_result_extracted(self) -> None:
        """ConfluenceResult가 _last_ensemble_result를 통해 접근 가능."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        cr = FakeConfluenceResult(
            final_signal="LONG", confluence_score=0.8, net_edge=0.7
        )
        fake_er = EnsembleResult(
            final_signal="LONG",
            individual_signals=[],
            confluence_result=cr,
        )

        mock_ensemble = MagicMock()
        mock_ensemble._last_ensemble_result = fake_er
        bot._ensemble_generator = mock_ensemble

        bot._generate_combined_signal = AsyncMock(
            return_value=("LONG", "ensemble")
        )

        await bot._run_five_gate_pipeline(
            market_data, indicators, None
        )

        assert bot._last_ensemble_result is fake_er
        assert bot._last_ensemble_result.confluence_result is cr

    @pytest.mark.asyncio
    async def test_regime_direction_filter_as_safety(self) -> None:
        """RANGING에서 LONG -> WAIT."""
        bot = _make_bot()
        indicators = {"atr_pct": 0.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        bot._generate_combined_signal = AsyncMock(
            return_value=("LONG", "ensemble")
        )
        # Force RANGING regime
        bot._regime_detector = MagicMock()
        bot._regime_detector.detect.return_value = MarketRegime.RANGING
        bot._regime_detector.filter_signal.return_value = "WAIT"

        signal, _ = await bot._run_five_gate_pipeline(
            market_data, indicators, None
        )

        assert signal == "WAIT"


# =========================================================================
# Sizing Modifier Tests
# =========================================================================


class TestSizingModifiers:
    """사이징 수정자 검증."""

    def test_entry_tier_high_margin_1_2(self) -> None:
        """margin > 0.15 -> entry_tier=1.2."""
        bot = _make_bot()
        cr = FakeConfluenceResult(
            confluence_score=0.8, threshold_used=0.5, net_edge=0.75
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er
        bot._last_mti_grade = "OPTIMAL"

        size = bot._compute_dynamic_size_with_modifiers()
        assert size is not None
        # With entry_tier=1.2 (margin=0.3>0.15), base default is 0.1
        base = bot.config.get_effective_position_size_pct()
        # cost_adj = net_edge/score = 0.75/0.8 = 0.9375
        expected = base * 1.2 * 1.0 * 0.9375 * 1.0
        assert abs(size - expected) < 0.001

    def test_entry_tier_near_threshold_0_8(self) -> None:
        """margin < 0.05 -> entry_tier=0.8."""
        bot = _make_bot()
        cr = FakeConfluenceResult(
            confluence_score=0.53, threshold_used=0.5, net_edge=0.5
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er

        size = bot._compute_dynamic_size_with_modifiers()
        assert size is not None
        base = bot.config.get_effective_position_size_pct()
        # entry_tier=0.8 (margin=0.03<0.05), cost_adj=0.5/0.53~0.943
        cost_adj = max(0.5, min(1.0, 0.5 / 0.53))
        expected = base * 0.8 * 1.0 * cost_adj * 1.0
        assert abs(size - expected) < 0.001

    def test_cost_adj_from_net_edge(self) -> None:
        """net_edge/score 비율 반영."""
        bot = _make_bot()
        # net_edge = 0.3, score = 0.8 -> ratio = 0.375 -> clamped to 0.5
        cr = FakeConfluenceResult(
            confluence_score=0.8, threshold_used=0.3, net_edge=0.3
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er

        size = bot._compute_dynamic_size_with_modifiers()
        base = bot.config.get_effective_position_size_pct()
        # entry_tier=1.2 (margin=0.5>0.15), cost_adj=0.5 (0.375 clamped)
        expected = base * 1.2 * 1.0 * 0.5 * 1.0
        assert abs(size - expected) < 0.001

    def test_vitality_healthy_1_0(self) -> None:
        """HEALTHY -> vitality_mod=1.0."""
        bot = _make_bot()
        from src.ai.confluence.vitality_tracker import VitalityLevel
        vit = FakeVitality(level=VitalityLevel.HEALTHY)
        cr = FakeConfluenceResult(
            confluence_score=0.8, threshold_used=0.5,
            net_edge=0.75, vitality=vit,
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er

        size = bot._compute_dynamic_size_with_modifiers()
        base = bot.config.get_effective_position_size_pct()
        expected = base * 1.2 * 1.0 * (0.75 / 0.8) * 1.0
        assert abs(size - expected) < 0.001

    def test_vitality_critical_0_4(self) -> None:
        """CRITICAL -> vitality_mod=0.4."""
        bot = _make_bot()
        from src.ai.confluence.vitality_tracker import VitalityLevel
        vit = FakeVitality(level=VitalityLevel.CRITICAL)
        cr = FakeConfluenceResult(
            confluence_score=0.8, threshold_used=0.5,
            net_edge=0.75, vitality=vit,
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er

        size = bot._compute_dynamic_size_with_modifiers()
        base = bot.config.get_effective_position_size_pct()
        expected = base * 1.2 * 1.0 * (0.75 / 0.8) * 0.4
        assert abs(size - expected) < 0.001

    def test_kelly_receives_all_modifiers(self) -> None:
        """calculate_final_size() 호출 시 모든 파라미터 확인."""
        bot = _make_bot()
        from src.ai.confluence.vitality_tracker import VitalityLevel
        vit = FakeVitality(level=VitalityLevel.CAUTION)
        cr = FakeConfluenceResult(
            confluence_score=0.8, threshold_used=0.5,
            net_edge=0.75, vitality=vit,
        )
        fake_er = MagicMock()
        fake_er.confluence_result = cr
        bot._last_ensemble_result = fake_er
        bot._last_mti_grade = "REDUCED"
        bot._current_regime = MarketRegime.STRONG_UPTREND

        mock_kelly = MagicMock()
        mock_kelly.calculate_final_size.return_value = 0.05
        bot._kelly_sizer = mock_kelly

        result = bot._compute_dynamic_size_with_modifiers()

        mock_kelly.calculate_final_size.assert_called_once()
        call_kwargs = mock_kelly.calculate_final_size.call_args
        assert call_kwargs.kwargs["entry_tier"] == 1.2
        assert call_kwargs.kwargs["mti_mod"] == 0.7
        assert abs(call_kwargs.kwargs["cost_adj"] - 0.9375) < 0.001
        assert call_kwargs.kwargs["vitality_mod"] == 0.85
        assert call_kwargs.kwargs["regime"] == "strong_uptrend"
        assert result == 0.05

    def test_execution_tracker_zero_blocks(self) -> None:
        """exec_mod=0.0 -> 0.0 반환."""
        bot = _make_bot()
        bot._last_ensemble_result = None
        mock_tracker = MagicMock()
        mock_tracker.get_size_modifier.return_value = 0.0
        bot._execution_tracker = mock_tracker

        result = bot._compute_dynamic_size_with_modifiers()
        assert result == 0.0

    def test_mti_reduced_mod_0_7(self) -> None:
        """REDUCED -> mti_mod=0.7 적용."""
        bot = _make_bot()
        bot._last_ensemble_result = None
        bot._last_mti_grade = "REDUCED"

        size = bot._compute_dynamic_size_with_modifiers()
        base = bot.config.get_effective_position_size_pct()
        expected = base * 1.0 * 0.7 * 1.0 * 1.0  # no CR -> all 1.0 except mti
        assert abs(size - expected) < 0.001


# =========================================================================
# Integration Tests
# =========================================================================


class TestPipelineIntegration:
    """통합 검증."""

    @pytest.mark.asyncio
    async def test_pipeline_size_flows_to_open_position(self) -> None:
        """_pipeline_size_pct -> _open_position."""
        bot = _make_bot()
        bot._pipeline_size_pct = 0.05

        # Mock executor
        bot._executor = AsyncMock()
        bot._executor.open_position = AsyncMock(return_value={"origQty": "0.1"})
        bot._executor.current_position = {
            "entry_price": 50000.0, "side": "LONG"
        }

        await bot._open_position("LONG", 50000.0)

        # Verify dynamic_size_pct was passed
        call_args = bot._executor.open_position.call_args
        assert call_args.kwargs.get("dynamic_size_pct") == 0.05 or             (len(call_args.args) > 2 and call_args.args[2] is not None)

    @pytest.mark.asyncio
    async def test_pipeline_size_cleared_after_use(self) -> None:
        """사용 후 None."""
        bot = _make_bot()
        bot._pipeline_size_pct = 0.05

        bot._executor = AsyncMock()
        bot._executor.open_position = AsyncMock(return_value=None)
        bot._executor.current_position = None

        await bot._open_position("LONG", 50000.0)

        assert bot._pipeline_size_pct is None

    @pytest.mark.asyncio
    async def test_legacy_flow_unchanged(self) -> None:
        """confluence 비활성 -> 기존 경로."""
        config = _make_config(use_confluence_engine=False)
        bot = _make_bot(config=config)

        # _run_five_gate_pipeline should NOT be called
        bot._run_five_gate_pipeline = AsyncMock()
        bot._generate_combined_signal = AsyncMock(
            return_value=("WAIT", "fallback")
        )
        bot._apply_signal_filters = MagicMock(return_value="WAIT")
        bot._record_signal = AsyncMock()
        bot._handle_emergency_close = AsyncMock(return_value=False)
        bot._detect_exchange_position_close = AsyncMock(return_value=False)
        bot._fetch_market_data = AsyncMock(return_value={
            "current_price": 50000.0,
            "indicators": {"rsi": 50.0},
        })
        bot._check_redis_commands = AsyncMock()
        bot._check_daily_risk_reset = AsyncMock()
        bot._handle_risk_halt = AsyncMock(return_value=False)
        bot._fetch_sentiment_data = AsyncMock(return_value=None)
        bot._attempt_new_entry = AsyncMock()

        await bot._execute_single_loop()

        bot._run_five_gate_pipeline.assert_not_called()
        bot._generate_combined_signal.assert_called_once()
        assert bot._pipeline_size_pct is None

    def test_wait_streak_tracked(self) -> None:
        """WAIT 연속 카운터."""
        bot = _make_bot()
        bot._consecutive_wait_count = 0

        bot._track_wait_streak("WAIT", {})
        assert bot._consecutive_wait_count == 1

        bot._track_wait_streak("WAIT", {})
        assert bot._consecutive_wait_count == 2

        bot._track_wait_streak("LONG", {})
        assert bot._consecutive_wait_count == 0


# =========================================================================
# Metrics Tests
# =========================================================================


class TestGateMetrics:
    """메트릭 검증."""

    @pytest.mark.asyncio
    async def test_gate_metrics_recorded(self) -> None:
        """각 gate pass/block Prometheus 기록."""
        bot = _make_bot()
        mock_metrics = MagicMock()
        bot._metrics = mock_metrics

        indicators = {"atr_pct": 1.5, "volume_ratio": 2.0, "rsi": 50.0}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        optimal = FakeMTIScore(
            total_score=80.0, is_tradable=True, grade="OPTIMAL"
        )
        with patch(
            "src.data.tradability.MarketTradabilityIndex"
        ) as MockMTI:
            mock_mti_inst = MagicMock()
            mock_mti_inst.evaluate.return_value = optimal
            MockMTI.return_value = mock_mti_inst

            bot._generate_combined_signal = AsyncMock(
                return_value=("LONG", "ensemble")
            )

            await bot._run_five_gate_pipeline(
                market_data, indicators, None
            )

        # MTI gate should be recorded
        calls = mock_metrics.record_gate_outcome.call_args_list
        gate_names = [c.args[1] for c in calls]
        assert "mti" in gate_names
        assert "confluence" in gate_names

    @pytest.mark.asyncio
    async def test_rsi_recorded_in_pipeline(self) -> None:
        """RSI 메트릭 기록."""
        bot = _make_bot()
        mock_metrics = MagicMock()
        bot._metrics = mock_metrics

        indicators = {"atr_pct": 0.0, "rsi": 65.3}
        market_data = {"current_price": 50000.0, "indicators": indicators}

        bot._generate_combined_signal = AsyncMock(
            return_value=("WAIT", "fallback")
        )

        await bot._run_five_gate_pipeline(
            market_data, indicators, None
        )

        mock_metrics.record_rsi.assert_called_once_with("test-5g", 65.3)


# =========================================================================
# EnsembleResult confluence_result field test
# =========================================================================


class TestEnsembleResultField:
    """EnsembleResult.confluence_result 필드 검증."""

    def test_ensemble_result_has_confluence_result_field(self) -> None:
        """EnsembleResult에 confluence_result 필드 존재."""
        result = EnsembleResult(
            final_signal="LONG",
            individual_signals=[],
            confluence_result="test_cr",
        )
        assert result.confluence_result == "test_cr"

    def test_ensemble_result_confluence_result_default_none(self) -> None:
        """기본값 None."""
        result = EnsembleResult(
            final_signal="WAIT",
            individual_signals=[],
        )
        assert result.confluence_result is None
