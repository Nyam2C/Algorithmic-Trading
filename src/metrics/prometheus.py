"""
Prometheus 메트릭 모듈

Phase 7.2: 실시간 모니터링 대시보드
- 거래 메트릭 (trades_total, position_pnl, trade_duration)
- 시스템 메트릭 (api_latency, signal_confidence)
"""
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY
from loguru import logger


# 기본 레지스트리 (싱글톤)
_metrics_instance: Optional["TradingMetrics"] = None
_initialized: bool = False


class TradingMetrics:
    """트레이딩 메트릭 관리 클래스

    Prometheus 메트릭을 생성하고 관리합니다.
    싱글톤 패턴을 사용하여 메트릭 중복 등록을 방지합니다.

    Attributes:
        trades_total: 총 거래 수 (Counter)
        position_pnl: 현재 포지션 PnL % (Gauge)
        trade_duration: 거래 지속시간 (Histogram)
        api_latency: API 지연시간 (Histogram)
        signal_confidence: 시그널 신뢰도 (Gauge)

    Example:
        >>> metrics = TradingMetrics.get_instance()
        >>> metrics.record_trade("btc-bot", "LONG", "win", 120.0)
        >>> metrics.record_position_pnl("btc-bot", 2.5)
    """

    # 클래스 레벨 메트릭 (기본 레지스트리용, 한번만 생성)
    _default_trades_total: Optional[Counter] = None
    _default_trade_duration: Optional[Histogram] = None
    _default_position_pnl: Optional[Gauge] = None
    _default_api_latency: Optional[Histogram] = None
    _default_signal_confidence: Optional[Gauge] = None

    def __init__(self, registry: Optional[CollectorRegistry] = None) -> None:
        """메트릭 초기화

        Args:
            registry: Prometheus 레지스트리 (None이면 기본 레지스트리 사용)
        """
        global _initialized

        self._registry = registry or REGISTRY
        self._use_default = registry is None

        # 기본 레지스트리 사용하고 이미 초기화된 경우
        if self._use_default and _initialized:
            # 인스턴스 변수에 클래스 변수 참조
            self._trades_total = TradingMetrics._default_trades_total
            self._trade_duration = TradingMetrics._default_trade_duration
            self._position_pnl = TradingMetrics._default_position_pnl
            self._api_latency = TradingMetrics._default_api_latency
            self._signal_confidence = TradingMetrics._default_signal_confidence
            return

        # 새 레지스트리거나 처음 초기화
        self._create_metrics()

        if self._use_default:
            _initialized = True

        logger.debug("TradingMetrics 초기화 완료")

    def _create_metrics(self) -> None:
        """메트릭 생성"""
        # 거래 메트릭
        trades_total = Counter(
            "trading_trades_total",
            "Total number of trades",
            ["bot_name", "side", "result"],
            registry=self._registry,
        )

        trade_duration = Histogram(
            "trading_trade_duration_seconds",
            "Trade duration in seconds",
            ["bot_name"],
            buckets=[10, 30, 60, 120, 300, 600, 1800, 3600, 7200, float("inf")],
            registry=self._registry,
        )

        # 포지션 메트릭
        position_pnl = Gauge(
            "trading_position_pnl_percent",
            "Current position PnL percentage",
            ["bot_name"],
            registry=self._registry,
        )

        # API 메트릭
        api_latency = Histogram(
            "trading_api_latency_seconds",
            "Binance API latency in seconds",
            ["endpoint"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf")],
            registry=self._registry,
        )

        # AI 시그널 메트릭
        signal_confidence = Gauge(
            "trading_signal_confidence",
            "AI signal confidence score (0-1)",
            ["bot_name"],
            registry=self._registry,
        )

        # 인스턴스 변수에 저장
        self._trades_total = trades_total
        self._trade_duration = trade_duration
        self._position_pnl = position_pnl
        self._api_latency = api_latency
        self._signal_confidence = signal_confidence

        # 기본 레지스트리면 클래스 변수에도 저장
        if self._use_default:
            TradingMetrics._default_trades_total = trades_total
            TradingMetrics._default_trade_duration = trade_duration
            TradingMetrics._default_position_pnl = position_pnl
            TradingMetrics._default_api_latency = api_latency
            TradingMetrics._default_signal_confidence = signal_confidence

    @property
    def trades_total(self) -> Counter:
        """거래 카운터"""
        assert self._trades_total is not None
        return self._trades_total

    @property
    def trade_duration(self) -> Histogram:
        """거래 지속시간 히스토그램"""
        assert self._trade_duration is not None
        return self._trade_duration

    @property
    def position_pnl(self) -> Gauge:
        """포지션 PnL 게이지"""
        assert self._position_pnl is not None
        return self._position_pnl

    @property
    def api_latency(self) -> Histogram:
        """API 지연시간 히스토그램"""
        assert self._api_latency is not None
        return self._api_latency

    @property
    def signal_confidence(self) -> Gauge:
        """시그널 신뢰도 게이지"""
        assert self._signal_confidence is not None
        return self._signal_confidence

    def record_trade(
        self,
        bot_name: str,
        side: str,
        result: str,
        duration_seconds: float,
    ) -> None:
        """거래 기록

        Args:
            bot_name: 봇 이름
            side: 거래 방향 ("LONG" or "SHORT")
            result: 거래 결과 ("win", "loss", "timeout", "manual")
            duration_seconds: 거래 지속시간 (초)
        """
        self.trades_total.labels(
            bot_name=bot_name,
            side=side,
            result=result,
        ).inc()

        self.trade_duration.labels(bot_name=bot_name).observe(duration_seconds)

        logger.debug(
            f"거래 메트릭 기록: bot={bot_name}, side={side}, "
            f"result={result}, duration={duration_seconds:.1f}s"
        )

    def record_api_latency(
        self,
        endpoint: str,
        latency_seconds: float,
    ) -> None:
        """API 지연시간 기록

        Args:
            endpoint: API 엔드포인트 이름
            latency_seconds: 지연시간 (초)
        """
        self.api_latency.labels(endpoint=endpoint).observe(latency_seconds)

    def record_position_pnl(
        self,
        bot_name: str,
        pnl_percent: float,
    ) -> None:
        """포지션 PnL 기록

        Args:
            bot_name: 봇 이름
            pnl_percent: PnL 비율 (%)
        """
        self.position_pnl.labels(bot_name=bot_name).set(pnl_percent)

    def record_signal_confidence(
        self,
        bot_name: str,
        confidence: float,
    ) -> None:
        """시그널 신뢰도 기록

        Args:
            bot_name: 봇 이름
            confidence: 신뢰도 (0-1)
        """
        self.signal_confidence.labels(bot_name=bot_name).set(confidence)

    def clear_position_metrics(self, bot_name: str) -> None:
        """포지션 청산 시 메트릭 클리어

        Args:
            bot_name: 봇 이름
        """
        self.position_pnl.labels(bot_name=bot_name).set(0.0)
        logger.debug(f"포지션 메트릭 클리어: bot={bot_name}")


# =========================================================================
# 싱글톤 인스턴스 및 편의 함수
# =========================================================================


def _get_metrics() -> TradingMetrics:
    """싱글톤 메트릭 인스턴스 반환"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = TradingMetrics()
    return _metrics_instance


def get_metrics_registry() -> CollectorRegistry:
    """메트릭 레지스트리 반환

    Returns:
        Prometheus CollectorRegistry
    """
    return REGISTRY


def record_trade(
    bot_name: str,
    side: str,
    result: str,
    duration_seconds: float,
) -> None:
    """거래 기록 (편의 함수)

    Args:
        bot_name: 봇 이름
        side: 거래 방향 ("LONG" or "SHORT")
        result: 거래 결과 ("win", "loss", "timeout", "manual")
        duration_seconds: 거래 지속시간 (초)
    """
    _get_metrics().record_trade(bot_name, side, result, duration_seconds)


def record_api_latency(
    endpoint: str,
    latency_seconds: float,
) -> None:
    """API 지연시간 기록 (편의 함수)

    Args:
        endpoint: API 엔드포인트 이름
        latency_seconds: 지연시간 (초)
    """
    _get_metrics().record_api_latency(endpoint, latency_seconds)


def record_position_pnl(
    bot_name: str,
    pnl_percent: float,
) -> None:
    """포지션 PnL 기록 (편의 함수)

    Args:
        bot_name: 봇 이름
        pnl_percent: PnL 비율 (%)
    """
    _get_metrics().record_position_pnl(bot_name, pnl_percent)


def record_signal_confidence(
    bot_name: str,
    confidence: float,
) -> None:
    """시그널 신뢰도 기록 (편의 함수)

    Args:
        bot_name: 봇 이름
        confidence: 신뢰도 (0-1)
    """
    _get_metrics().record_signal_confidence(bot_name, confidence)
