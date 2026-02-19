"""BT↔Live Comparator 테스트."""
from datetime import datetime

from src.analytics.bt_live_comparator import (
    BTLiveComparator,
    ComparatorReport,
    TradeComparison,
)


class TestTradeComparison:
    """TradeComparison 테스트."""

    def test_slippage_pct(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=100.0, live_entry=101.0,
        )
        assert abs(c.slippage_pct - 0.01) < 1e-6

    def test_slippage_zero_bt_entry(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=0.0, live_entry=100.0,
        )
        assert c.slippage_pct == 0.0

    def test_fill_divergence(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=100.0, live_entry=100.0,
            bt_fill_rate=1.0, live_fill_rate=0.8,
        )
        assert abs(c.fill_divergence - 0.2) < 1e-6

    def test_funding_divergence(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=100.0, live_entry=100.0,
            bt_funding_cost=0.0, live_funding_cost=0.5,
        )
        assert abs(c.funding_divergence - 0.5) < 1e-6

    def test_total_divergence(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=100.0, live_entry=100.0,
        )
        # 모두 0이면 total도 0
        assert c.total_divergence_pct == 0.0

    def test_total_divergence_weighted(self):
        c = TradeComparison(
            trade_id="1", timestamp=datetime.now(), side="LONG",
            bt_entry=100.0, live_entry=110.0,  # 10% slippage
            bt_fill_rate=1.0, live_fill_rate=0.5,  # 50% fill divergence
        )
        expected = 0.10 * 0.5 + 0.50 * 0.3 + 0.0
        assert abs(c.total_divergence_pct - expected) < 1e-6


class TestComparatorReport:
    """ComparatorReport 테스트."""

    def test_empty_report(self):
        r = ComparatorReport()
        assert r.trade_count == 0
        assert r.is_warning is False
        assert r.is_critical is False


class TestBTLiveComparator:
    """BTLiveComparator 테스트."""

    def setup_method(self):
        self.comparator = BTLiveComparator(
            warning_threshold=0.20,
            critical_threshold=0.30,
        )

    def _make_comparison(
        self, bt_entry: float = 100.0, live_entry: float = 100.0,
    ) -> TradeComparison:
        return TradeComparison(
            trade_id="test", timestamp=datetime.now(), side="LONG",
            bt_entry=bt_entry, live_entry=live_entry,
        )

    def test_normal_trade(self):
        c = self._make_comparison(100.0, 100.1)  # 0.1% slippage
        report = self.comparator.record_comparison(c)
        assert report.is_warning is False
        assert report.is_critical is False

    def test_warning_threshold(self):
        # 각 비교에서 total_divergence > 0.20 되도록
        for _ in range(5):
            c = self._make_comparison(100.0, 160.0)  # 60% slippage
            report = self.comparator.record_comparison(c)
        assert report.is_warning is True

    def test_critical_threshold(self):
        for _ in range(5):
            c = self._make_comparison(100.0, 180.0)  # 80% slippage
            report = self.comparator.record_comparison(c)
        assert report.is_critical is True

    def test_max_history(self):
        comp = BTLiveComparator(max_history=5)
        for i in range(10):
            c = self._make_comparison(100.0, 100.0 + i)
            comp.record_comparison(c)
        assert comp.comparison_count == 5

    def test_get_report_without_record(self):
        report = self.comparator.get_report()
        assert report.trade_count == 0

    def test_report_averages(self):
        c1 = self._make_comparison(100.0, 102.0)  # 2% slippage
        c2 = self._make_comparison(100.0, 104.0)  # 4% slippage
        self.comparator.record_comparison(c1)
        report = self.comparator.record_comparison(c2)
        assert report.avg_slippage_pct > 0
        assert report.trade_count == 2


class TestBTLiveConfig:
    """Feature flag 테스트."""

    def test_default_disabled(self):
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", symbol="BTCUSDT", risk_level="low",
                          leverage=3, stop_loss_pct=0.003)
        assert config.use_bt_live_comparator is False
        assert config.bt_live_warning_threshold == 0.20
        assert config.bt_live_critical_threshold == 0.30

    def test_enable_comparator(self):
        from src.bot_config import BotConfig
        config = BotConfig(
            bot_name="test", symbol="BTCUSDT", risk_level="low",
            leverage=3, stop_loss_pct=0.003,
            use_bt_live_comparator=True,
            bt_live_warning_threshold=0.15,
            bt_live_critical_threshold=0.25,
        )
        assert config.use_bt_live_comparator is True
        assert config.bt_live_warning_threshold == 0.15


class TestBTLivePrometheusMetrics:
    """BT-Live Prometheus 메트릭 테스트."""

    def test_metrics_creation(self):
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics
        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)
        assert metrics._bt_live_divergence is not None
        assert metrics._bt_live_alert_total is not None

    def test_record_divergence(self):
        from prometheus_client import CollectorRegistry

        from src.metrics.prometheus import TradingMetrics
        registry = CollectorRegistry()
        metrics = TradingMetrics(registry=registry)
        metrics.record_bt_live_divergence("test-bot", 0.15, "warning")
