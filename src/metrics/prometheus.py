"""Prometheus 메트릭 모듈.

Phase 7.2: 실시간 모니터링 대시보드
- 거래 메트릭 (trades_total, position_pnl, trade_duration)
- 시스템 메트릭 (api_latency, signal_confidence)
"""
from typing import Optional

from loguru import logger
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# 기본 레지스트리 (싱글톤)
_metrics_instance: Optional["TradingMetrics"] = None
_initialized: bool = False


class TradingMetrics:
    """트레이딩 메트릭 관리 클래스.

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
    _default_trades_total: Counter | None = None
    _default_trade_duration: Histogram | None = None
    _default_position_pnl: Gauge | None = None
    _default_api_latency: Histogram | None = None
    _default_signal_confidence: Gauge | None = None
    _default_loop_duration: Histogram | None = None
    _default_loop_total: Counter | None = None
    _default_signal_total: Counter | None = None
    _default_ai_latency: Histogram | None = None

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        """메트릭 초기화.

        Args:
            registry: Prometheus 레지스트리 (None이면 기본 레지스트리 사용)
        """
        global _initialized  # noqa: PLW0603

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
            self._loop_duration = TradingMetrics._default_loop_duration
            self._loop_total = TradingMetrics._default_loop_total
            self._signal_total = TradingMetrics._default_signal_total
            self._ai_latency = TradingMetrics._default_ai_latency
            return

        # 새 레지스트리거나 처음 초기화
        self._create_metrics()

        if self._use_default:
            _initialized = True

        logger.debug("TradingMetrics 초기화 완료")

    def _create_metrics(self) -> None:
        """메트릭 생성."""
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

        # 루프 메트릭
        loop_duration = Histogram(
            "trading_loop_duration_seconds",
            "Trading loop iteration duration in seconds",
            ["bot_name"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf")],
            registry=self._registry,
        )

        loop_total = Counter(
            "trading_loop_total",
            "Total number of trading loop iterations",
            ["bot_name"],
            registry=self._registry,
        )

        # 시그널 메트릭
        signal_total = Counter(
            "trading_signal_total",
            "Total number of signals generated",
            ["bot_name", "signal", "source"],
            registry=self._registry,
        )

        # AI 응답시간 메트릭
        ai_latency = Histogram(
            "trading_ai_latency_seconds",
            "Gemini AI response latency in seconds",
            ["bot_name"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")],
            registry=self._registry,
        )

        # 인스턴스 변수에 저장
        self._trades_total = trades_total
        self._trade_duration = trade_duration
        self._position_pnl = position_pnl
        self._api_latency = api_latency
        self._signal_confidence = signal_confidence
        self._loop_duration = loop_duration
        self._loop_total = loop_total
        self._signal_total = signal_total
        self._ai_latency = ai_latency

        # 기본 레지스트리면 클래스 변수에도 저장
        if self._use_default:
            TradingMetrics._default_trades_total = trades_total
            TradingMetrics._default_trade_duration = trade_duration
            TradingMetrics._default_position_pnl = position_pnl
            TradingMetrics._default_api_latency = api_latency
            TradingMetrics._default_signal_confidence = signal_confidence
            TradingMetrics._default_loop_duration = loop_duration
            TradingMetrics._default_loop_total = loop_total
            TradingMetrics._default_signal_total = signal_total
            TradingMetrics._default_ai_latency = ai_latency

    @property
    def trades_total(self) -> Counter:
        """거래 카운터."""
        if self._trades_total is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._trades_total

    @property
    def trade_duration(self) -> Histogram:
        """거래 지속시간 히스토그램."""
        if self._trade_duration is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._trade_duration

    @property
    def position_pnl(self) -> Gauge:
        """포지션 PnL 게이지."""
        if self._position_pnl is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._position_pnl

    @property
    def api_latency(self) -> Histogram:
        """API 지연시간 히스토그램."""
        if self._api_latency is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._api_latency

    @property
    def signal_confidence(self) -> Gauge:
        """시그널 신뢰도 게이지."""
        if self._signal_confidence is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._signal_confidence

    @property
    def loop_duration(self) -> Histogram:
        """루프 소요시간 히스토그램."""
        if self._loop_duration is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._loop_duration

    @property
    def loop_total(self) -> Counter:
        """루프 실행 횟수 카운터."""
        if self._loop_total is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._loop_total

    @property
    def signal_total(self) -> Counter:
        """시그널 발생 카운터."""
        if self._signal_total is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._signal_total

    @property
    def ai_latency(self) -> Histogram:
        """AI 응답시간 히스토그램."""
        if self._ai_latency is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._ai_latency

    def record_loop_duration(
        self,
        bot_name: str,
        duration_seconds: float,
    ) -> None:
        """루프 소요시간 기록.

        Args:
            bot_name: 봇 이름
            duration_seconds: 루프 소요시간 (초)
        """
        self.loop_duration.labels(bot_name=bot_name).observe(duration_seconds)
        self.loop_total.labels(bot_name=bot_name).inc()

    def record_signal(
        self,
        bot_name: str,
        signal: str,
        source: str,
    ) -> None:
        """시그널 발생 기록.

        Args:
            bot_name: 봇 이름
            signal: 시그널 (LONG, SHORT, WAIT)
            source: 시그널 소스 (rule_based, ensemble, memory_gemini)
        """
        self.signal_total.labels(bot_name=bot_name, signal=signal, source=source).inc()

    def record_ai_latency(
        self,
        bot_name: str,
        latency_seconds: float,
    ) -> None:
        """AI 응답시간 기록.

        Args:
            bot_name: 봇 이름
            latency_seconds: AI 응답시간 (초)
        """
        self.ai_latency.labels(bot_name=bot_name).observe(latency_seconds)

    def record_trade(
        self,
        bot_name: str,
        side: str,
        result: str,
        duration_seconds: float,
    ) -> None:
        """거래 기록.

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
        """API 지연시간 기록.

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
        """포지션 PnL 기록.

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
        """시그널 신뢰도 기록.

        Args:
            bot_name: 봇 이름
            confidence: 신뢰도 (0-1)
        """
        self.signal_confidence.labels(bot_name=bot_name).set(confidence)

    def clear_position_metrics(self, bot_name: str) -> None:
        """포지션 청산 시 메트릭 클리어.

        Args:
            bot_name: 봇 이름
        """
        self.position_pnl.labels(bot_name=bot_name).set(0.0)
        logger.debug(f"포지션 메트릭 클리어: bot={bot_name}")


# =========================================================================
# 싱글톤 인스턴스 및 편의 함수
# =========================================================================


def _get_metrics() -> TradingMetrics:
    """싱글톤 메트릭 인스턴스 반환."""
    global _metrics_instance  # noqa: PLW0603
    if _metrics_instance is None:
        _metrics_instance = TradingMetrics()
    return _metrics_instance


def get_metrics_registry() -> CollectorRegistry:
    """메트릭 레지스트리 반환.

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
    """거래 기록 (편의 함수).

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
    """API 지연시간 기록 (편의 함수).

    Args:
        endpoint: API 엔드포인트 이름
        latency_seconds: 지연시간 (초)
    """
    _get_metrics().record_api_latency(endpoint, latency_seconds)


def record_position_pnl(
    bot_name: str,
    pnl_percent: float,
) -> None:
    """포지션 PnL 기록 (편의 함수).

    Args:
        bot_name: 봇 이름
        pnl_percent: PnL 비율 (%)
    """
    _get_metrics().record_position_pnl(bot_name, pnl_percent)


def record_signal_confidence(
    bot_name: str,
    confidence: float,
) -> None:
    """시그널 신뢰도 기록 (편의 함수).

    Args:
        bot_name: 봇 이름
        confidence: 신뢰도 (0-1)
    """
    _get_metrics().record_signal_confidence(bot_name, confidence)


def record_loop_duration(
    bot_name: str,
    duration_seconds: float,
) -> None:
    """루프 소요시간 기록 (편의 함수)."""
    _get_metrics().record_loop_duration(bot_name, duration_seconds)


def record_signal(
    bot_name: str,
    signal: str,
    source: str,
) -> None:
    """시그널 발생 기록 (편의 함수)."""
    _get_metrics().record_signal(bot_name, signal, source)
