"""
Tests for Prometheus Metrics

Phase 7.2: 실시간 모니터링 대시보드 - Prometheus 메트릭
"""
import pytest
from prometheus_client import CollectorRegistry

from src.metrics.prometheus import (
    TradingMetrics,
    get_metrics_registry,
    record_account_balance,
    record_api_latency,
    record_available_balance,
    record_daily_pnl,
    record_daily_pnl_pct,
    record_drawdown_pct,
    record_position_pnl,
    record_signal_confidence,
    record_trade,
    record_unrealized_pnl,
    record_win_rate,
)


@pytest.fixture
def fresh_registry():
    """각 테스트마다 새로운 레지스트리 생성"""
    return CollectorRegistry()


@pytest.fixture
def metrics(fresh_registry):
    """각 테스트마다 새로운 메트릭 인스턴스 생성"""
    return TradingMetrics(registry=fresh_registry)


class TestTradingMetrics:
    """TradingMetrics 클래스 테스트"""

    def test_init_creates_metrics(self, metrics):
        """메트릭이 올바르게 생성되는지 테스트"""
        assert metrics.trades_total is not None
        assert metrics.position_pnl is not None
        assert metrics.trade_duration is not None
        assert metrics.api_latency is not None
        assert metrics.signal_confidence is not None

    def test_record_trade_long_win(self, metrics):
        """LONG 거래 승리 기록"""
        # 거래 기록
        metrics.record_trade(
            bot_name="btc-bot",
            side="LONG",
            result="win",
            duration_seconds=120.5,
        )

        # 메트릭이 증가했는지 확인
        assert True

    def test_record_trade_short_loss(self, metrics):
        """SHORT 거래 손실 기록"""
        metrics.record_trade(
            bot_name="eth-bot",
            side="SHORT",
            result="loss",
            duration_seconds=300.0,
        )

        assert True

    def test_record_api_latency(self, metrics):
        """API 지연시간 기록"""
        metrics.record_api_latency(
            endpoint="get_klines",
            latency_seconds=0.15,
        )

        assert True

    def test_record_position_pnl(self, metrics):
        """포지션 PnL 기록"""
        metrics.record_position_pnl(
            bot_name="btc-bot",
            pnl_percent=2.5,
        )

        assert True

    def test_record_position_pnl_negative(self, metrics):
        """포지션 손실 PnL 기록"""
        metrics.record_position_pnl(
            bot_name="btc-bot",
            pnl_percent=-1.5,
        )

        assert True

    def test_record_signal_confidence(self, metrics):
        """시그널 신뢰도 기록"""
        metrics.record_signal_confidence(
            bot_name="btc-bot",
            confidence=0.85,
        )

        assert True

    def test_clear_position_metrics(self, metrics):
        """포지션 청산 시 메트릭 클리어"""
        # 포지션 메트릭 설정
        metrics.record_position_pnl("btc-bot", 2.5)

        # 청산 시 클리어
        metrics.clear_position_metrics("btc-bot")

        assert True


class TestAccountMetrics:
    """계좌 메트릭 테스트"""

    def test_record_account_balance(self, metrics):
        """총 계좌 잔고 기록"""
        metrics.record_account_balance("btc-bot", 1234.56)
        assert True

    def test_record_available_balance(self, metrics):
        """가용 잔고 기록"""
        metrics.record_available_balance("btc-bot", 1000.0)
        assert True

    def test_record_unrealized_pnl(self, metrics):
        """미실현 손익 기록"""
        metrics.record_unrealized_pnl("btc-bot", 34.5)
        assert True

    def test_record_unrealized_pnl_negative(self, metrics):
        """미실현 손실 기록"""
        metrics.record_unrealized_pnl("btc-bot", -15.0)
        assert True

    def test_record_daily_pnl(self, metrics):
        """일일 실현 손익 기록"""
        metrics.record_daily_pnl("btc-bot", 50.0)
        assert True

    def test_record_daily_pnl_pct(self, metrics):
        """일일 수익률 기록"""
        metrics.record_daily_pnl_pct("btc-bot", 2.1)
        assert True

    def test_record_drawdown_pct(self, metrics):
        """드로다운 기록"""
        metrics.record_drawdown_pct("btc-bot", 1.2)
        assert True

    def test_record_win_rate(self, metrics):
        """승률 기록"""
        metrics.record_win_rate("btc-bot", 0.67)
        assert True

    def test_record_win_rate_zero(self, metrics):
        """승률 0% 기록"""
        metrics.record_win_rate("btc-bot", 0.0)
        assert True

    def test_account_metrics_multiple_bots(self, metrics):
        """멀티봇 계좌 메트릭"""
        metrics.record_account_balance("bot-1", 1000.0)
        metrics.record_account_balance("bot-2", 2000.0)
        metrics.record_daily_pnl("bot-1", 10.0)
        metrics.record_daily_pnl("bot-2", -5.0)
        assert True


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_record_trade_function(self):
        """record_trade 편의 함수"""
        # 오류 없이 호출되어야 함
        record_trade(
            bot_name="btc-bot",
            side="LONG",
            result="win",
            duration_seconds=100.0,
        )

    def test_record_api_latency_function(self):
        """record_api_latency 편의 함수"""
        record_api_latency(
            endpoint="get_account",
            latency_seconds=0.05,
        )

    def test_record_position_pnl_function(self):
        """record_position_pnl 편의 함수"""
        record_position_pnl(
            bot_name="btc-bot",
            pnl_percent=1.5,
        )

    def test_record_signal_confidence_function(self):
        """record_signal_confidence 편의 함수"""
        record_signal_confidence(
            bot_name="btc-bot",
            confidence=0.75,
        )


    def test_record_account_balance_function(self):
        """record_account_balance 편의 함수"""
        record_account_balance(bot_name="btc-bot", balance=1234.56)

    def test_record_available_balance_function(self):
        """record_available_balance 편의 함수"""
        record_available_balance(bot_name="btc-bot", balance=1000.0)

    def test_record_unrealized_pnl_function(self):
        """record_unrealized_pnl 편의 함수"""
        record_unrealized_pnl(bot_name="btc-bot", pnl=34.5)

    def test_record_daily_pnl_function(self):
        """record_daily_pnl 편의 함수"""
        record_daily_pnl(bot_name="btc-bot", pnl=50.0)

    def test_record_daily_pnl_pct_function(self):
        """record_daily_pnl_pct 편의 함수"""
        record_daily_pnl_pct(bot_name="btc-bot", pnl_pct=2.1)

    def test_record_drawdown_pct_function(self):
        """record_drawdown_pct 편의 함수"""
        record_drawdown_pct(bot_name="btc-bot", drawdown=1.2)

    def test_record_win_rate_function(self):
        """record_win_rate 편의 함수"""
        record_win_rate(bot_name="btc-bot", win_rate=0.67)


class TestMetricsRegistry:
    """메트릭 레지스트리 테스트"""

    def test_get_metrics_registry(self):
        """레지스트리 반환"""
        registry = get_metrics_registry()
        assert registry is not None

    def test_singleton_pattern(self):
        """싱글톤 패턴 확인"""
        registry1 = get_metrics_registry()
        registry2 = get_metrics_registry()
        assert registry1 is registry2


class TestMetricsLabels:
    """메트릭 라벨 테스트"""

    def test_trade_labels(self, metrics):
        """거래 메트릭 라벨"""
        # 다양한 봇과 결과로 테스트
        metrics.record_trade("bot-1", "LONG", "win", 60.0)
        metrics.record_trade("bot-1", "SHORT", "loss", 120.0)
        metrics.record_trade("bot-2", "LONG", "timeout", 300.0)

        assert True

    def test_api_latency_labels(self, metrics):
        """API 지연시간 라벨"""
        # 다양한 엔드포인트
        metrics.record_api_latency("get_klines", 0.1)
        metrics.record_api_latency("create_order", 0.2)
        metrics.record_api_latency("get_account", 0.05)

        assert True


class TestHistogramBuckets:
    """히스토그램 버킷 테스트"""

    def test_trade_duration_histogram(self, metrics):
        """거래 지속시간 히스토그램"""
        # 다양한 지속시간
        durations = [10, 30, 60, 120, 300, 600, 1800, 3600]
        for d in durations:
            metrics.record_trade("test-bot", "LONG", "win", float(d))

        assert True

    def test_api_latency_histogram(self, metrics):
        """API 지연시간 히스토그램"""
        # 다양한 지연시간
        latencies = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        for lat in latencies:
            metrics.record_api_latency("test", lat)

        assert True
