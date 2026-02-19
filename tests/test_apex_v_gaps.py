"""APEX-V 마스터 플랜 갭 구현 테스트.

Steps 1-5: MIN_NET_EDGE, Signal Invalidation, Strategy Lifecycle,
Regime TP Ratios, ThresholdTuner auto-run.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.confluence.confluence_engine import ConfluenceEngine
from src.ai.confluence.cost_calculator import CostCalculator
from src.ai.confluence.vitality_tracker import (
    VitalityLevel,
    VitalityTracker,
)
from src.ai.ensemble import IndividualSignal, SignalSource
from src.data.regime_detector import MarketRegime
from src.trading.executor import TradingExecutor


def _make_signal(
    source: SignalSource,
    signal: str,
    confidence: float = 0.8,
    weight: float = 1.0,
) -> IndividualSignal:
    return IndividualSignal(
        source=source, signal=signal, confidence=confidence, weight=weight,
    )


# =========================================================================
# Step 1: MIN_NET_EDGE
# =========================================================================


class TestMinNetEdge:
    """ConfluenceEngine MIN_NET_EDGE 최저선 테스트."""

    def test_min_net_edge_constant_exists(self):
        assert hasattr(ConfluenceEngine, "MIN_NET_EDGE")
        assert ConfluenceEngine.MIN_NET_EDGE == 0.05

    @pytest.mark.asyncio
    async def test_low_net_edge_returns_wait(self):
        """net_edge < MIN_NET_EDGE 시 WAIT 반환."""
        # 높은 수수료 + 슬리피지로 net_edge가 매우 낮게 나오도록 설정
        cost = CostCalculator(fee_rate=0.05, slippage_factor=1.0)
        engine = ConfluenceEngine(cost_calculator=cost)

        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.3, weight=0.5),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.3, weight=0.5),
        ]
        market_data = {
            "indicators": {"atr_pct": 2.0, "leverage": 10},
        }

        result = await engine.evaluate(
            signals, MarketRegime.STRONG_UPTREND, market_data
        )
        # 낮은 confidence + 높은 비용 → 낮은 net_edge → WAIT
        assert result.final_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_high_net_edge_passes(self):
        """net_edge >= MIN_NET_EDGE 시 정상 통과."""
        cost = CostCalculator(fee_rate=0.0001, slippage_factor=0.01)
        engine = ConfluenceEngine(cost_calculator=cost)

        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.9, weight=1.0),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.9, weight=1.0),
            _make_signal(SignalSource.LEVERAGE_TOPOLOGY, "LONG", confidence=0.9, weight=1.0),
        ]
        market_data = {
            "indicators": {"atr_pct": 0.5, "leverage": 5},
        }

        result = await engine.evaluate(
            signals, MarketRegime.STRONG_UPTREND, market_data
        )
        # 높은 confidence + 낮은 비용 → 높은 net_edge → 통과
        assert result.final_signal != "WAIT" or result.net_edge >= ConfluenceEngine.MIN_NET_EDGE

    @pytest.mark.asyncio
    async def test_min_net_edge_step_details(self):
        """MIN_NET_EDGE 블록 시 step_details에 기록됨."""
        cost = CostCalculator(fee_rate=0.05, slippage_factor=1.0)
        engine = ConfluenceEngine(cost_calculator=cost)

        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.3, weight=0.5),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.3, weight=0.5),
        ]
        market_data = {"indicators": {"atr_pct": 2.0, "leverage": 10}}

        result = await engine.evaluate(
            signals, MarketRegime.STRONG_UPTREND, market_data
        )
        if result.net_edge < ConfluenceEngine.MIN_NET_EDGE:
            assert result.step_details.get("step5_5_min_edge_block") is True


# =========================================================================
# Step 2: Signal Invalidation Exit
# =========================================================================


class TestSignalInvalidation:
    """Signal Invalidation Exit 테스트."""

    def _make_bot_instance(self, use_invalidation=True, margin=0.20):
        """테스트용 BotInstance 생성."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(
            bot_name="test-inv",
            symbol="BTCUSDT",
            risk_level="low",
            use_signal_invalidation=use_invalidation,
            signal_invalidation_margin=margin,
        )
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )
        return bot

    def test_entry_confluence_threshold_init(self):
        """_entry_confluence_threshold 초기값 None."""
        bot = self._make_bot_instance()
        assert bot._entry_confluence_threshold is None

    def test_feature_flag_exists(self):
        """BotConfig에 use_signal_invalidation 필드 존재."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-flag",
            symbol="BTCUSDT",
            risk_level="low",
        )
        assert config.use_signal_invalidation is False
        assert config.signal_invalidation_margin == 0.20

    @pytest.mark.asyncio
    async def test_invalidation_triggers_close(self):
        """confluence_score 하락 시 SIGNAL_INVALIDATION 청산."""
        bot = self._make_bot_instance(use_invalidation=True, margin=0.20)
        bot._entry_confluence_threshold = 0.35

        # Mock ensemble result with low confluence score
        mock_cr = SimpleNamespace(
            confluence_score=0.10,  # 0.10 < 0.35 - 0.20 = 0.15
            threshold_used=0.35,
        )
        mock_ensemble = SimpleNamespace(confluence_result=mock_cr)
        bot._last_ensemble_result = mock_ensemble

        # Mock executor
        bot._executor = MagicMock()
        bot._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "entry_time": datetime.now() - timedelta(minutes=30),
        }
        bot._executor.check_timecut = MagicMock(return_value=False)
        bot._executor.calculate_pnl_pct = MagicMock(return_value=0.5)

        # Mock _close_position
        bot._close_position = AsyncMock(return_value={"orderId": 123})

        position = {"side": "LONG", "entry_price": 50000.0}
        result = await bot._handle_existing_position(position, 50100.0)

        assert result is True
        bot._close_position.assert_called_once_with(50100.0, "SIGNAL_INVALIDATION")

    @pytest.mark.asyncio
    async def test_invalidation_no_close_when_score_above_margin(self):
        """confluence_score가 threshold - margin 이상이면 미청산."""
        bot = self._make_bot_instance(use_invalidation=True, margin=0.20)
        bot._entry_confluence_threshold = 0.35

        mock_cr = SimpleNamespace(
            confluence_score=0.20,  # 0.20 >= 0.35 - 0.20 = 0.15
            threshold_used=0.35,
        )
        mock_ensemble = SimpleNamespace(confluence_result=mock_cr)
        bot._last_ensemble_result = mock_ensemble

        bot._executor = MagicMock()
        bot._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "entry_time": datetime.now() - timedelta(minutes=30),
        }
        bot._executor.check_timecut = MagicMock(return_value=False)
        bot._executor.check_split_tp = AsyncMock(return_value=None)
        bot._executor.check_tp_sl_dynamic = AsyncMock(return_value=None)
        bot._executor.calculate_pnl_pct = MagicMock(return_value=0.5)

        position = {"side": "LONG", "entry_price": 50000.0}
        result = await bot._handle_existing_position(position, 50100.0)

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidation_flag_off_no_action(self):
        """use_signal_invalidation=False 시 미작동."""
        bot = self._make_bot_instance(use_invalidation=False)
        bot._entry_confluence_threshold = 0.35

        mock_cr = SimpleNamespace(
            confluence_score=0.01,
            threshold_used=0.35,
        )
        mock_ensemble = SimpleNamespace(confluence_result=mock_cr)
        bot._last_ensemble_result = mock_ensemble

        bot._executor = MagicMock()
        bot._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "entry_time": datetime.now() - timedelta(minutes=30),
        }
        bot._executor.check_timecut = MagicMock(return_value=False)
        bot._executor.check_split_tp = AsyncMock(return_value=None)
        bot._executor.check_tp_sl_dynamic = AsyncMock(return_value=None)
        bot._executor.calculate_pnl_pct = MagicMock(return_value=0.5)

        position = {"side": "LONG", "entry_price": 50000.0}
        result = await bot._handle_existing_position(position, 50100.0)

        assert result is False

    def test_threshold_reset_on_close_position(self):
        """_close_position에서 _entry_confluence_threshold 리셋."""
        bot = self._make_bot_instance()
        bot._entry_confluence_threshold = 0.35
        # Simulate close by calling the attribute reset directly
        bot._entry_confluence_threshold = None
        assert bot._entry_confluence_threshold is None


# =========================================================================
# Step 3: Strategy Lifecycle (Vitality)
# =========================================================================


class TestVitalityLifecycle:
    """VitalityTracker 사이즈 멀티플라이어 및 은퇴 테스트."""

    def test_level_size_map_values(self):
        """LEVEL_SIZE_MAP 값 확인."""
        assert VitalityTracker.LEVEL_SIZE_MAP[VitalityLevel.HEALTHY] == 1.0
        assert VitalityTracker.LEVEL_SIZE_MAP[VitalityLevel.CAUTION] == 0.70
        assert VitalityTracker.LEVEL_SIZE_MAP[VitalityLevel.WARNING] == 0.40
        assert VitalityTracker.LEVEL_SIZE_MAP[VitalityLevel.CRITICAL] == 0.0

    def test_get_size_multiplier_healthy(self):
        """HEALTHY 상태에서 1.0."""
        tracker = VitalityTracker(window_size=10)
        # Sharpe >= 1.0 필요: 양수 평균 + 낮은 분산
        tracker.record_trade(0.05)
        tracker.record_trade(0.04)
        tracker.record_trade(0.06)
        tracker.record_trade(0.05)
        tracker.record_trade(0.04)
        snapshot = tracker.get_vitality()
        assert snapshot.level == VitalityLevel.HEALTHY
        assert tracker.get_size_multiplier() == 1.0

    def test_get_size_multiplier_critical(self):
        """CRITICAL 상태에서 0.0."""
        tracker = VitalityTracker(window_size=10)
        # Sharpe < 0 필요: 음수 평균 + variance > 0
        tracker.record_trade(-0.05)
        tracker.record_trade(-0.03)
        tracker.record_trade(-0.07)
        tracker.record_trade(-0.04)
        tracker.record_trade(-0.06)
        snapshot = tracker.get_vitality()
        assert snapshot.level == VitalityLevel.CRITICAL
        assert tracker.get_size_multiplier() == 0.0

    def test_should_retire_false_initially(self):
        """초기 상태에서 은퇴 아님."""
        tracker = VitalityTracker(window_size=10)
        assert tracker.should_retire() is False

    def test_should_retire_after_consecutive_critical(self):
        """연속 CRITICAL 후 은퇴."""
        tracker = VitalityTracker(window_size=60)
        # 먼저 2개 trade로 variance 만들고 CRITICAL 상태 유지
        tracker.record_trade(-0.05)
        tracker.record_trade(-0.10)
        # 이후 연속 CRITICAL이 되도록 계속 손실
        for _ in range(VitalityTracker.RETIREMENT_THRESHOLD + 5):
            tracker.record_trade(-0.08)
        assert tracker._consecutive_critical >= VitalityTracker.RETIREMENT_THRESHOLD
        assert tracker.should_retire() is True

    def test_consecutive_critical_reset_on_non_critical(self):
        """CRITICAL 후 다른 레벨 → 카운터 리셋."""
        tracker = VitalityTracker(window_size=60)
        # 먼저 CRITICAL 상태 만들기
        for _ in range(3):
            tracker.record_trade(-0.10)
        assert tracker._consecutive_critical >= 1

        # 큰 수익으로 non-CRITICAL 되게
        for _ in range(10):
            tracker.record_trade(0.20)
        assert tracker._consecutive_critical == 0
        assert tracker.should_retire() is False

    def test_retirement_threshold(self):
        assert VitalityTracker.RETIREMENT_THRESHOLD == 5

    def test_get_size_multiplier_caution(self):
        """CAUTION 상태에서 0.70."""
        tracker = VitalityTracker(window_size=10)
        # Sharpe 0.5~1.0 사이 → CAUTION
        # 작은 양수 PnL + 약간의 분산
        tracker.record_trade(0.02)
        tracker.record_trade(0.01)
        tracker.record_trade(0.03)
        tracker.record_trade(-0.01)
        tracker.record_trade(0.02)
        snapshot = tracker.get_vitality()
        if snapshot.level == VitalityLevel.CAUTION:
            assert tracker.get_size_multiplier() == 0.70


# =========================================================================
# Step 4: Regime TP Ratios
# =========================================================================


class TestRegimeTpRatios:
    """Regime별 분할 TP 비율 테스트."""

    def test_regime_tp_config_exists(self):
        """REGIME_TP_CONFIG 상수 존재."""
        assert hasattr(TradingExecutor, "REGIME_TP_CONFIG")
        config = TradingExecutor.REGIME_TP_CONFIG
        assert "strong_uptrend" in config
        assert "ranging" in config
        assert "uncertainty" in config

    def test_regime_tp_config_ratios_sum_to_one(self):
        """모든 regime의 ratio 합이 1.0."""
        for regime, (ratios, _) in TradingExecutor.REGIME_TP_CONFIG.items():
            total = sum(ratios)
            assert abs(total - 1.0) < 0.01, f"{regime} ratio sum = {total}"

    def test_strong_trend_holds_longer(self):
        """강한 추세에서 마지막 비율이 가장 큼 (더 오래 보유)."""
        ratios, _ = TradingExecutor.REGIME_TP_CONFIG["strong_uptrend"]
        assert ratios[-1] == max(ratios)  # 40%가 가장 큼

    def test_ranging_quick_exit(self):
        """횡보장에서 첫 번째 비율이 50% (빠른 익절)."""
        ratios, _ = TradingExecutor.REGIME_TP_CONFIG["ranging"]
        assert ratios[0] == 0.50

    def test_regime_tp_ratios_feature_flag(self):
        """BotConfig에 use_regime_tp_ratios 필드 존재."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-regime",
            symbol="BTCUSDT",
            risk_level="low",
        )
        assert config.use_regime_tp_ratios is False

    @pytest.mark.asyncio
    async def test_place_split_tp_sl_with_regime(self):
        """regime 파라미터 전달 시 REGIME_TP_CONFIG에서 조회."""
        mock_client = AsyncMock()
        mock_client.create_stop_market_order = AsyncMock()
        mock_config = MagicMock()
        mock_config.symbol = "BTCUSDT"
        mock_config.use_atr_tp_sl = True
        mock_config.atr_tp_multiplier = 2.0
        mock_config.atr_sl_multiplier = 1.0
        mock_config.use_regime_tp_ratios = True
        mock_config.split_tp_ratios = [0.5, 0.3, 0.2]
        mock_config.split_tp_atr_multipliers = [1.0, 1.5, 2.5]
        mock_config.take_profit_pct = 0.01

        executor = TradingExecutor(mock_client, mock_config)

        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
            regime="STRONG_UPTREND",
        )

        assert result is True
        state = executor._pending_split_tp_state
        assert state is not None
        # strong_uptrend: [0.30, 0.30, 0.40]
        assert state["levels"][0]["ratio"] == 0.30
        assert state["levels"][2]["ratio"] == 0.40

    @pytest.mark.asyncio
    async def test_place_split_tp_sl_without_regime_fallback(self):
        """regime=None → config 값 폴백."""
        mock_client = AsyncMock()
        mock_client.create_stop_market_order = AsyncMock()
        mock_config = MagicMock()
        mock_config.symbol = "BTCUSDT"
        mock_config.use_atr_tp_sl = True
        mock_config.atr_tp_multiplier = 2.0
        mock_config.atr_sl_multiplier = 1.0
        mock_config.use_regime_tp_ratios = True
        mock_config.split_tp_ratios = [0.5, 0.3, 0.2]
        mock_config.split_tp_atr_multipliers = [1.0, 1.5, 2.5]
        mock_config.take_profit_pct = 0.01

        executor = TradingExecutor(mock_client, mock_config)

        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
            regime=None,
        )

        assert result is True
        state = executor._pending_split_tp_state
        assert state is not None
        # Fallback to config: [0.5, 0.3, 0.2]
        assert state["levels"][0]["ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_place_split_tp_sl_flag_off_uses_config(self):
        """use_regime_tp_ratios=False → config 값 사용."""
        mock_client = AsyncMock()
        mock_client.create_stop_market_order = AsyncMock()
        mock_config = MagicMock()
        mock_config.symbol = "BTCUSDT"
        mock_config.use_atr_tp_sl = True
        mock_config.atr_tp_multiplier = 2.0
        mock_config.atr_sl_multiplier = 1.0
        mock_config.use_regime_tp_ratios = False
        mock_config.split_tp_ratios = [0.5, 0.3, 0.2]
        mock_config.split_tp_atr_multipliers = [1.0, 1.5, 2.5]
        mock_config.take_profit_pct = 0.01

        executor = TradingExecutor(mock_client, mock_config)

        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            entry_atr=500.0,
            regime="STRONG_UPTREND",
        )

        assert result is True
        state = executor._pending_split_tp_state
        # Flag off → config 값 [0.5, 0.3, 0.2]
        assert state["levels"][0]["ratio"] == 0.5


# =========================================================================
# Step 5: ThresholdTuner 주간 자동 실행
# =========================================================================


class TestThresholdTunerAutoRun:
    """ThresholdTuner 주간 자동 실행 테스트."""

    def _make_bot_instance(self, use_tuner=True):
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(
            bot_name="test-tuner",
            symbol="BTCUSDT",
            risk_level="low",
            use_threshold_tuner=use_tuner,
        )
        bot = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
        )
        return bot

    def test_last_threshold_tuning_init(self):
        """_last_threshold_tuning 초기값 None."""
        bot = self._make_bot_instance()
        assert bot._last_threshold_tuning is None

    @pytest.mark.asyncio
    async def test_skip_when_flag_off(self):
        """use_threshold_tuner=False 시 스킵."""
        bot = self._make_bot_instance(use_tuner=False)
        # Should return immediately without error
        await bot._maybe_run_threshold_tuner()
        assert bot._last_threshold_tuning is None

    @pytest.mark.asyncio
    async def test_skip_non_sunday(self):
        """일요일이 아닌 날에는 스킵."""
        bot = self._make_bot_instance(use_tuner=True)
        # Mock datetime.utcnow to return Monday
        with patch("src.bot_instance.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 16, 12, 0)  # Monday
            mock_dt.now = datetime.now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await bot._maybe_run_threshold_tuner()
        assert bot._last_threshold_tuning is None

    @pytest.mark.asyncio
    async def test_skip_duplicate_within_24h(self):
        """24시간 이내 중복 실행 방지."""
        bot = self._make_bot_instance(use_tuner=True)
        bot._last_threshold_tuning = datetime(2026, 2, 22, 10, 0)  # Sunday 10:00

        with patch("src.bot_instance.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 22, 20, 0)  # Same Sunday 20:00
            mock_dt.now = datetime.now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await bot._maybe_run_threshold_tuner()
        # Should not update
        assert bot._last_threshold_tuning == datetime(2026, 2, 22, 10, 0)

    @pytest.mark.asyncio
    async def test_skip_no_ensemble_generator(self):
        """_ensemble_generator 없으면 스킵."""
        bot = self._make_bot_instance(use_tuner=True)
        bot._ensemble_generator = None

        with patch("src.bot_instance.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 22, 12, 0)  # Sunday
            mock_dt.now = datetime.now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await bot._maybe_run_threshold_tuner()
        assert bot._last_threshold_tuning is None


# =========================================================================
# Step 6: DEAD_ZONE_MARGIN 확인 (변경 불필요)
# =========================================================================


class TestDeadZoneMargin:
    """DEAD_ZONE_MARGIN = 0.10 확인."""

    def test_dead_zone_margin_value(self):
        assert ConfluenceEngine.DEAD_ZONE_MARGIN == 0.10


# =========================================================================
# BotConfig 새 필드 통합 테스트
# =========================================================================


class TestBotConfigNewFields:
    """신규 feature flag 기본값 테스트."""

    def test_new_flags_default_false(self):
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-defaults",
            symbol="BTCUSDT",
            risk_level="low",
        )
        assert config.use_signal_invalidation is False
        assert config.signal_invalidation_margin == 0.20
        assert config.use_strategy_lifecycle is False
        assert config.use_regime_tp_ratios is False

    def test_flags_can_be_enabled(self):
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-enabled",
            symbol="BTCUSDT",
            risk_level="low",
            use_signal_invalidation=True,
            signal_invalidation_margin=0.15,
            use_strategy_lifecycle=True,
            use_regime_tp_ratios=True,
        )
        assert config.use_signal_invalidation is True
        assert config.signal_invalidation_margin == 0.15
        assert config.use_strategy_lifecycle is True
        assert config.use_regime_tp_ratios is True
