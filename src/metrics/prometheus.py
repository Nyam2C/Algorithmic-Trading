"""Prometheus 메트릭 모듈.

Phase 7.2: 실시간 모니터링 대시보드
- 거래 메트릭 (trades_total, position_pnl, trade_duration)
- 시스템 메트릭 (api_latency, signal_confidence)
"""

from loguru import logger
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# 기본 레지스트리 (싱글톤)
_metrics_instance: "TradingMetrics | None" = None
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
    _default_consecutive_wait: Gauge | None = None
    _default_exchange_connected: Gauge | None = None
    _default_circuit_breaker_state: Gauge | None = None
    _default_open_positions: Gauge | None = None
    _default_bot_uptime: Gauge | None = None
    _default_rsi_value: Gauge | None = None
    _default_account_balance: Gauge | None = None
    _default_available_balance: Gauge | None = None
    _default_unrealized_pnl: Gauge | None = None
    _default_daily_pnl: Gauge | None = None
    _default_daily_pnl_pct: Gauge | None = None
    _default_drawdown_pct: Gauge | None = None
    _default_win_rate: Gauge | None = None
    _default_gate_total: Counter | None = None
    _default_shadow_agreement: Gauge | None = None
    _default_bt_live_divergence: Gauge | None = None
    _default_bt_live_alert_total: Counter | None = None
    _default_shadow_comparison_total: Counter | None = None

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
            self._consecutive_wait = TradingMetrics._default_consecutive_wait
            self._exchange_connected = TradingMetrics._default_exchange_connected
            self._circuit_breaker_state = TradingMetrics._default_circuit_breaker_state
            self._open_positions = TradingMetrics._default_open_positions
            self._bot_uptime = TradingMetrics._default_bot_uptime
            self._rsi_value = TradingMetrics._default_rsi_value
            self._account_balance = TradingMetrics._default_account_balance
            self._available_balance = TradingMetrics._default_available_balance
            self._unrealized_pnl = TradingMetrics._default_unrealized_pnl
            self._daily_pnl = TradingMetrics._default_daily_pnl
            self._daily_pnl_pct = TradingMetrics._default_daily_pnl_pct
            self._drawdown_pct = TradingMetrics._default_drawdown_pct
            self._win_rate = TradingMetrics._default_win_rate
            self._gate_total = TradingMetrics._default_gate_total
            self._shadow_agreement = TradingMetrics._default_shadow_agreement
            self._shadow_comparison_total = (
                TradingMetrics._default_shadow_comparison_total
            )
            self._bt_live_divergence = TradingMetrics._default_bt_live_divergence
            self._bt_live_alert_total = TradingMetrics._default_bt_live_alert_total
            return

        # 새 레지스트리거나 처음 초기화
        self._create_metrics()

        if self._use_default:
            _initialized = True

        logger.debug("TradingMetrics 초기화 완료")

    def _create_metrics(self) -> None:  # noqa: PLR0915
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

        # 연속 WAIT 카운트 메트릭
        consecutive_wait = Gauge(
            "trading_consecutive_wait_count",
            "Number of consecutive WAIT signals",
            ["bot_name"],
            registry=self._registry,
        )

        # Phase 9: 운영 메트릭
        exchange_connected = Gauge(
            "trading_exchange_connected",
            "Exchange connection status (1=connected, 0=disconnected)",
            ["bot_name"],
            registry=self._registry,
        )

        circuit_breaker_state = Gauge(
            "trading_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open)",
            ["breaker_name"],
            registry=self._registry,
        )

        open_positions = Gauge(
            "trading_open_positions",
            "Number of open positions",
            ["bot_name"],
            registry=self._registry,
        )

        bot_uptime = Gauge(
            "trading_bot_uptime_seconds",
            "Bot uptime in seconds",
            ["bot_name"],
            registry=self._registry,
        )

        # RSI Gauge
        rsi_value = Gauge(
            "trading_rsi",
            "Current RSI value",
            ["bot_name"],
            registry=self._registry,
        )

        # 계좌 메트릭
        account_balance = Gauge(
            "trading_account_balance",
            "Total account balance (USDT)",
            ["bot_name"],
            registry=self._registry,
        )

        available_balance = Gauge(
            "trading_available_balance",
            "Available balance (USDT)",
            ["bot_name"],
            registry=self._registry,
        )

        unrealized_pnl = Gauge(
            "trading_unrealized_pnl",
            "Unrealized PnL (USDT)",
            ["bot_name"],
            registry=self._registry,
        )

        daily_pnl = Gauge(
            "trading_daily_pnl",
            "Daily realized PnL (USDT)",
            ["bot_name"],
            registry=self._registry,
        )

        daily_pnl_pct = Gauge(
            "trading_daily_pnl_pct",
            "Daily PnL percentage",
            ["bot_name"],
            registry=self._registry,
        )

        drawdown_pct = Gauge(
            "trading_drawdown_pct",
            "Current drawdown percentage",
            ["bot_name"],
            registry=self._registry,
        )

        win_rate = Gauge(
            "trading_win_rate",
            "Trading win rate (0-1)",
            ["bot_name"],
            registry=self._registry,
        )

        # Gate 메트릭 (5-Gate Pipeline)
        gate_total = Counter(
            "trading_gate_total",
            "Gate pass/block count in 5-Gate Pipeline",
            ["bot_name", "gate", "outcome"],
            registry=self._registry,
        )

        # Shadow Mode 메트릭
        shadow_agreement = Gauge(
            "trading_shadow_agreement_pct",
            "Shadow mode direction agreement percentage",
            ["bot_name"],
            registry=self._registry,
        )
        shadow_comparison_total = Counter(
            "trading_shadow_comparison_total",
            "Shadow mode comparison count",
            ["bot_name", "match"],
            registry=self._registry,
        )

        # BT↔Live Comparator 메트릭
        bt_live_divergence = Gauge(
            "trading_bt_live_divergence_pct",
            "BT vs Live total divergence percentage",
            ["bot_name"],
            registry=self._registry,
        )
        bt_live_alert_total = Counter(
            "trading_bt_live_alert_total",
            "BT vs Live alert count",
            ["bot_name", "level"],
            registry=self._registry,
        )

        # 인스턴스 변수에 저장
        self._bt_live_divergence = bt_live_divergence
        self._bt_live_alert_total = bt_live_alert_total
        self._shadow_agreement = shadow_agreement
        self._shadow_comparison_total = shadow_comparison_total
        self._gate_total = gate_total
        self._trades_total = trades_total
        self._trade_duration = trade_duration
        self._position_pnl = position_pnl
        self._api_latency = api_latency
        self._signal_confidence = signal_confidence
        self._loop_duration = loop_duration
        self._loop_total = loop_total
        self._signal_total = signal_total
        self._ai_latency = ai_latency
        self._consecutive_wait = consecutive_wait
        self._exchange_connected = exchange_connected
        self._circuit_breaker_state = circuit_breaker_state
        self._open_positions = open_positions
        self._bot_uptime = bot_uptime
        self._rsi_value = rsi_value
        self._account_balance = account_balance
        self._available_balance = available_balance
        self._unrealized_pnl = unrealized_pnl
        self._daily_pnl = daily_pnl
        self._daily_pnl_pct = daily_pnl_pct
        self._drawdown_pct = drawdown_pct
        self._win_rate = win_rate

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
            TradingMetrics._default_consecutive_wait = consecutive_wait
            TradingMetrics._default_exchange_connected = exchange_connected
            TradingMetrics._default_circuit_breaker_state = circuit_breaker_state
            TradingMetrics._default_open_positions = open_positions
            TradingMetrics._default_bot_uptime = bot_uptime
            TradingMetrics._default_rsi_value = rsi_value
            TradingMetrics._default_account_balance = account_balance
            TradingMetrics._default_available_balance = available_balance
            TradingMetrics._default_unrealized_pnl = unrealized_pnl
            TradingMetrics._default_daily_pnl = daily_pnl
            TradingMetrics._default_daily_pnl_pct = daily_pnl_pct
            TradingMetrics._default_drawdown_pct = drawdown_pct
            TradingMetrics._default_win_rate = win_rate
            TradingMetrics._default_gate_total = gate_total
            TradingMetrics._default_shadow_agreement = shadow_agreement
            TradingMetrics._default_shadow_comparison_total = shadow_comparison_total
            TradingMetrics._default_bt_live_divergence = bt_live_divergence
            TradingMetrics._default_bt_live_alert_total = bt_live_alert_total

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

    @property
    def consecutive_wait(self) -> Gauge:
        """연속 WAIT 카운트 게이지."""
        if self._consecutive_wait is None:
            raise RuntimeError("TradingMetrics not initialized")
        return self._consecutive_wait

    def record_exchange_connected(
        self,
        bot_name: str,
        connected: bool,
    ) -> None:
        """거래소 연결 상태 기록.

        Args:
            bot_name: 봇 이름
            connected: 연결 여부
        """
        if self._exchange_connected is not None:
            val = 1 if connected else 0
            self._exchange_connected.labels(bot_name=bot_name).set(val)

    def record_circuit_breaker_state(
        self,
        breaker_name: str,
        state: int,
    ) -> None:
        """서킷 브레이커 상태 기록.

        Args:
            breaker_name: 브레이커 이름
            state: 상태 (0=closed, 1=open)
        """
        if self._circuit_breaker_state is not None:
            self._circuit_breaker_state.labels(breaker_name=breaker_name).set(state)

    def record_open_positions(
        self,
        bot_name: str,
        count: int,
    ) -> None:
        """오픈 포지션 수 기록.

        Args:
            bot_name: 봇 이름
            count: 포지션 수
        """
        if self._open_positions is not None:
            self._open_positions.labels(bot_name=bot_name).set(count)

    def record_bot_uptime(
        self,
        bot_name: str,
        uptime_seconds: float,
    ) -> None:
        """봇 가동시간 기록.

        Args:
            bot_name: 봇 이름
            uptime_seconds: 가동시간 (초)
        """
        if self._bot_uptime is not None:
            self._bot_uptime.labels(bot_name=bot_name).set(uptime_seconds)

    def record_consecutive_wait(
        self,
        bot_name: str,
        count: int,
    ) -> None:
        """연속 WAIT 카운트 기록.

        Args:
            bot_name: 봇 이름
            count: 연속 WAIT 횟수
        """
        self.consecutive_wait.labels(bot_name=bot_name).set(count)

    def record_rsi(
        self,
        bot_name: str,
        rsi_value: float,
    ) -> None:
        """RSI 값 기록.

        Args:
            bot_name: 봇 이름
            rsi_value: RSI 값 (0-100)
        """
        import math  # noqa: PLC0415
        if self._rsi_value is not None and not math.isnan(rsi_value):
            self._rsi_value.labels(bot_name=bot_name).set(rsi_value)

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
            source: 시그널 소스 (fallback, ensemble, memory_gemini)
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

    def record_account_balance(self, bot_name: str, balance: float) -> None:
        """총 계좌 잔고 기록.

        Args:
            bot_name: 봇 이름
            balance: 총 잔고 (USDT)
        """
        if self._account_balance is not None:
            self._account_balance.labels(bot_name=bot_name).set(balance)

    def record_available_balance(self, bot_name: str, balance: float) -> None:
        """가용 잔고 기록.

        Args:
            bot_name: 봇 이름
            balance: 가용 잔고 (USDT)
        """
        if self._available_balance is not None:
            self._available_balance.labels(bot_name=bot_name).set(balance)

    def record_unrealized_pnl(self, bot_name: str, pnl: float) -> None:
        """미실현 손익 기록.

        Args:
            bot_name: 봇 이름
            pnl: 미실현 PnL (USDT)
        """
        if self._unrealized_pnl is not None:
            self._unrealized_pnl.labels(bot_name=bot_name).set(pnl)

    def record_daily_pnl(self, bot_name: str, pnl: float) -> None:
        """일일 실현 손익 기록.

        Args:
            bot_name: 봇 이름
            pnl: 일일 PnL (USDT)
        """
        if self._daily_pnl is not None:
            self._daily_pnl.labels(bot_name=bot_name).set(pnl)

    def record_daily_pnl_pct(self, bot_name: str, pnl_pct: float) -> None:
        """일일 수익률 기록.

        Args:
            bot_name: 봇 이름
            pnl_pct: 일일 PnL 비율 (%)
        """
        if self._daily_pnl_pct is not None:
            self._daily_pnl_pct.labels(bot_name=bot_name).set(pnl_pct)

    def record_drawdown_pct(self, bot_name: str, drawdown: float) -> None:
        """드로다운 기록.

        Args:
            bot_name: 봇 이름
            drawdown: 현재 드로다운 비율 (%)
        """
        if self._drawdown_pct is not None:
            self._drawdown_pct.labels(bot_name=bot_name).set(drawdown)

    def record_win_rate(self, bot_name: str, win_rate: float) -> None:
        """승률 기록.

        Args:
            bot_name: 봇 이름
            win_rate: 승률 (0-1)
        """
        if self._win_rate is not None:
            self._win_rate.labels(bot_name=bot_name).set(win_rate)

    def record_gate_outcome(
        self,
        bot_name: str,
        gate: str,
        outcome: str,
    ) -> None:
        """5-Gate Pipeline gate 결과 기록.

        Args:
            bot_name: 봇 이름
            gate: 게이트 이름 (mti, regime, confluence, risk_kelly)
            outcome: 결과 (pass, block)
        """
        if self._gate_total is not None:
            self._gate_total.labels(
                bot_name=bot_name, gate=gate, outcome=outcome
            ).inc()


    def record_shadow_comparison(
        self,
        bot_name: str,
        match: bool,
        agreement_pct: float,
    ) -> None:
        """Shadow Mode 비교 결과 기록."""
        if self._shadow_comparison_total is not None:
            self._shadow_comparison_total.labels(
                bot_name=bot_name, match=str(match).lower(),
            ).inc()
        if self._shadow_agreement is not None:
            self._shadow_agreement.labels(bot_name=bot_name).set(agreement_pct)

    def record_bt_live_divergence(
        self,
        bot_name: str,
        divergence_pct: float,
        level: str = "normal",
    ) -> None:
        """BT↔Live 괴리율 기록."""
        if self._bt_live_divergence is not None:
            self._bt_live_divergence.labels(bot_name=bot_name).set(divergence_pct)
        if level != "normal" and self._bt_live_alert_total is not None:
            self._bt_live_alert_total.labels(
                bot_name=bot_name, level=level,
            ).inc()

    def clear_position_metrics(self, bot_name: str) -> None:
        """포지션 청산 시 메트릭 클리어."""
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
    """메트릭 레지스트리 반환."""
    return REGISTRY


def record_trade(
    bot_name: str, side: str, result: str, duration_seconds: float,
) -> None:
    """거래 기록 (편의 함수)."""
    _get_metrics().record_trade(bot_name, side, result, duration_seconds)


def record_api_latency(endpoint: str, latency_seconds: float) -> None:
    """API 지연시간 기록 (편의 함수)."""
    _get_metrics().record_api_latency(endpoint, latency_seconds)


def record_position_pnl(bot_name: str, pnl_percent: float) -> None:
    """포지션 PnL 기록 (편의 함수)."""
    _get_metrics().record_position_pnl(bot_name, pnl_percent)


def record_signal_confidence(bot_name: str, confidence: float) -> None:
    """시그널 신뢰도 기록 (편의 함수)."""
    _get_metrics().record_signal_confidence(bot_name, confidence)


def record_loop_duration(bot_name: str, duration_seconds: float) -> None:
    """루프 소요시간 기록 (편의 함수)."""
    _get_metrics().record_loop_duration(bot_name, duration_seconds)


def record_signal(bot_name: str, signal: str, source: str) -> None:
    """시그널 발생 기록 (편의 함수)."""
    _get_metrics().record_signal(bot_name, signal, source)


def record_consecutive_wait(bot_name: str, count: int) -> None:
    """연속 WAIT 카운트 기록 (편의 함수)."""
    _get_metrics().record_consecutive_wait(bot_name, count)


def record_rsi(bot_name: str, rsi_value: float) -> None:
    """RSI 값 기록 (편의 함수)."""
    _get_metrics().record_rsi(bot_name, rsi_value)


def record_account_balance(bot_name: str, balance: float) -> None:
    """총 계좌 잔고 기록 (편의 함수)."""
    _get_metrics().record_account_balance(bot_name, balance)


def record_available_balance(bot_name: str, balance: float) -> None:
    """가용 잔고 기록 (편의 함수)."""
    _get_metrics().record_available_balance(bot_name, balance)


def record_unrealized_pnl(bot_name: str, pnl: float) -> None:
    """미실현 손익 기록 (편의 함수)."""
    _get_metrics().record_unrealized_pnl(bot_name, pnl)


def record_daily_pnl(bot_name: str, pnl: float) -> None:
    """일일 실현 손익 기록 (편의 함수)."""
    _get_metrics().record_daily_pnl(bot_name, pnl)


def record_daily_pnl_pct(bot_name: str, pnl_pct: float) -> None:
    """일일 수익률 기록 (편의 함수)."""
    _get_metrics().record_daily_pnl_pct(bot_name, pnl_pct)


def record_drawdown_pct(bot_name: str, drawdown: float) -> None:
    """드로다운 기록 (편의 함수)."""
    _get_metrics().record_drawdown_pct(bot_name, drawdown)


def record_win_rate(bot_name: str, win_rate: float) -> None:
    """승률 기록 (편의 함수)."""
    _get_metrics().record_win_rate(bot_name, win_rate)


def record_gate_outcome(bot_name: str, gate: str, outcome: str) -> None:
    """5-Gate Pipeline gate 결과 기록 (편의 함수)."""
    _get_metrics().record_gate_outcome(bot_name, gate, outcome)


def record_shadow_comparison(
    bot_name: str, match: bool, agreement_pct: float,
) -> None:
    """Shadow Mode 비교 결과 기록 (편의 함수)."""
    _get_metrics().record_shadow_comparison(bot_name, match, agreement_pct)


def record_bt_live_divergence(
    bot_name: str, divergence_pct: float, level: str = "normal",
) -> None:
    """BT↔Live 괴리율 기록 (편의 함수)."""
    _get_metrics().record_bt_live_divergence(bot_name, divergence_pct, level)
