"""개별 봇 인스턴스 모듈.

각 봇의 트레이딩 루프 로직을 캡슐화한 BotInstance 클래스.
기존 main.py의 trading_loop 로직을 분리하여 멀티봇 실행 지원.

Phase 4: AI 메모리 시스템 통합
- EnhancedGeminiSignalGenerator 지원
- 과거 거래 분석 기반 시그널 생성
"""
import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Union

from loguru import logger

from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator
from src.ai.rule_based import RuleBasedSignalGenerator
from src.ai.signals import should_enter_trade, validate_signal
from src.analytics.memory_context import AIMemoryContextBuilder

# Phase 5 통합 모듈
from src.analytics.signal_tracker import SignalTracker
from src.analytics.trade_analyzer import TradeHistoryAnalyzer
from src.bot_config import BotConfig
from src.data.indicators import analyze_market
from src.data.multi_timeframe import MultiTimeframeAnalyzer
from src.data.regime_detector import MarketRegime, RegimeDetector  # Phase 6.2
from src.exchange.binance import BinanceTestnetClient
from src.storage.redis_state import DummyRedisStateManager, RedisStateManager
from src.storage.trade_history import TradeHistoryDB
from src.trading.executor import TradingExecutor
from src.trading.risk_manager import RiskManager  # Phase 5.2

# 콜백 타입 정의
OnSignalCallback = Callable[[str, str, float], Awaitable[None]]
OnTradeCallback = Callable[[str, str, str, float, float | None], Awaitable[None]]
OnErrorCallback = Callable[[str, Exception], Awaitable[None]]
OnExposureCheckCallback = Callable[[str, float], Awaitable[tuple[bool, str]]]


class BotInstance:
    """개별 봇 인스턴스.

    각 봇의 트레이딩 루프를 독립적으로 실행하는 클래스입니다.
    BotConfig를 기반으로 설정되며, 멀티봇 환경에서 여러 인스턴스가
    동시에 실행될 수 있습니다.

    Attributes:
        config: 봇 설정 (BotConfig)
        bot_name: 봇 이름
        symbol: 거래 심볼
        is_running: 실행 중 여부
        is_paused: 일시정지 여부

    Example:
        >>> config = BotConfig(bot_name="btc-bot", symbol="BTCUSDT")
        >>> instance = BotInstance(config, api_key, api_secret)
        >>> await instance.start()
    """

    def __init__(
        self,
        config: BotConfig,
        binance_api_key: str,
        binance_secret_key: str,
        gemini_api_key: str = "",
        discord_webhook_url: str = "",
        database_url: str | None = None,
        loop_interval_seconds: int = 300,
        # 의존성 주입 (테스트용)
        binance_client: BinanceTestnetClient | None = None,
        trade_db: TradeHistoryDB | None = None,
        redis_state_manager: (
            Union[RedisStateManager, DummyRedisStateManager] | None
        ) = None,
        # Phase 4: AI 메모리 시스템
        enhanced_gemini: EnhancedGeminiSignalGenerator | None = None,
        use_memory_signals: bool = False,
        # 콜백 함수
        on_signal_callback: OnSignalCallback | None = None,
        on_trade_callback: OnTradeCallback | None = None,
        on_error_callback: OnErrorCallback | None = None,
        # Phase 5: 노출도 체크 콜백
        on_exposure_check: OnExposureCheckCallback | None = None,
    ) -> None:
        """봇 인스턴스 초기화.

        Args:
            config: 봇 설정
            binance_api_key: Binance API 키
            binance_secret_key: Binance Secret 키
            gemini_api_key: Gemini API 키 (Phase 4: AI 메모리 시스템)
            discord_webhook_url: Discord 웹훅 URL
            database_url: PostgreSQL 데이터베이스 URL
            loop_interval_seconds: 루프 간격 (초)
            binance_client: Binance 클라이언트 (의존성 주입용)
            trade_db: 거래 기록 DB (의존성 주입용)
            redis_state_manager: Redis 상태 관리자 (의존성 주입용)
            enhanced_gemini: 메모리 기반 Gemini 시그널 생성기 (Phase 4)
            use_memory_signals: 메모리 기반 시그널 사용 여부 (Phase 4)
            on_signal_callback: 시그널 발생 시 콜백
            on_trade_callback: 거래 발생 시 콜백
            on_error_callback: 에러 발생 시 콜백
            on_exposure_check: 노출도 체크 콜백 (Phase 5)
        """
        self.config = config
        self._binance_api_key = binance_api_key
        self._binance_secret_key = binance_secret_key
        self._gemini_api_key = gemini_api_key
        self._discord_webhook_url = discord_webhook_url
        self._database_url = database_url
        self._loop_interval_seconds = loop_interval_seconds

        # 상태
        self._is_running = False
        self._is_paused = False
        self._emergency_close = False
        self._uptime_start: datetime | None = None
        self._loop_count = 0

        # 현재 데이터
        self._current_price: float = 0.0
        self._last_signal: str = "WAIT"
        self._last_signal_time: datetime | None = None
        self._current_position: dict | None = None
        self._market_data: dict | None = None

        # 의존성
        self._binance_client = binance_client
        self._trade_db = trade_db
        self._redis_state_manager = redis_state_manager
        self._executor: TradingExecutor | None = None

        # 시그널 생성기 (커스텀 RSI 파라미터 적용)
        self._signal_generator = RuleBasedSignalGenerator(
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            volume_threshold=config.volume_threshold,
        )

        # Phase 4: AI 메모리 시스템
        self._enhanced_gemini = enhanced_gemini
        self._use_memory_signals = use_memory_signals
        self._memory_context_builder: AIMemoryContextBuilder | None = None

        # Phase 5.2: 리스크 매니저
        self._risk_manager = RiskManager(
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            max_consecutive_losses=config.max_consecutive_losses,
            cooldown_minutes=config.cooldown_minutes,
        )
        self._risk_halt_notified = False  # 리스크 한도 도달 알림 플래그

        # Phase 6.2: 마켓 레짐 감지기
        self._regime_detector = RegimeDetector()
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN

        # Phase 5 통합: SignalTracker (인메모리)
        self._signal_tracker = SignalTracker(db_pool=None)
        self._last_signal_id: str | None = None

        # Phase 5 통합: Prometheus 메트릭
        self._metrics: Any | None = None
        try:
            from src.metrics.prometheus import _get_metrics  # noqa: PLC0415
            self._metrics = _get_metrics()
        except Exception:  # noqa: S110
            pass  # prometheus_client 미설치 시 스킵

        # Phase 5 통합: MultiTimeframeAnalyzer
        self._mtf_analyzer = MultiTimeframeAnalyzer()
        self._higher_tf_data: dict[str, Any] | None = None

        # Phase 5 통합: EnsembleSignalGenerator
        self._ensemble_generator: Any | None = None

        # Phase 5 통합: TradeApprovalManager
        self._trade_approval: Any | None = None
        self._pending_approval_request: Any | None = None

        # Phase 5 통합: 노출도 체크 콜백
        self._on_exposure_check = on_exposure_check

        # 콜백
        self._on_signal_callback = on_signal_callback
        self._on_trade_callback = on_trade_callback
        self._on_error_callback = on_error_callback

        # 로거 바인딩
        self._log = logger.bind(bot_name=config.bot_name, symbol=config.symbol)
        self._log.info(
            f"봇 인스턴스 초기화 완료 (memory_signals={use_memory_signals})"
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def bot_name(self) -> str:
        """봇 이름."""
        return self.config.bot_name

    @property
    def symbol(self) -> str:
        """거래 심볼."""
        return self.config.symbol

    @property
    def is_running(self) -> bool:
        """실행 중 여부."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """일시정지 여부."""
        return self._is_paused

    # =========================================================================
    # 상태 관리
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """현재 봇 상태 반환.

        Returns:
            봇 상태 딕셔너리
        """
        return {
            "bot_id": str(self.config.bot_id),
            "bot_name": self.bot_name,
            "symbol": self.symbol,
            "risk_level": self.config.risk_level,
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "uptime_start": self._uptime_start,
            "loop_count": self._loop_count,
            "current_price": self._current_price,
            "last_signal": self._last_signal,
            "last_signal_time": self._last_signal_time,
            "position": self._current_position,
            "leverage": self.config.get_effective_leverage(),
            # Phase 4: AI 메모리 시스템
            "memory_signals_enabled": self.memory_signals_enabled,
            # Phase 5.2: 리스크 상태
            "risk_stats": self._risk_manager.get_stats(),
            # Phase 6.2: 마켓 레짐
            "market_regime": self._current_regime.value,
            # Phase 5 통합: MTF 분석
            "use_mtf_filter": getattr(self.config, "use_mtf_filter", False),
            "higher_tf_trend": (
                self._mtf_analyzer.get_higher_tf_trend(self._higher_tf_data)
                if self._higher_tf_data else "NEUTRAL"
            ),
            # Phase 5 통합: 앙상블
            "use_ensemble": getattr(self.config, "use_ensemble", False),
            # Phase 5 통합: 승인 상태
            "trade_approval": (
                self._trade_approval.get_stats()
                if self._trade_approval else None
            ),
        }

    def pause(self) -> None:
        """봇 일시정지."""
        self._is_paused = True
        self._log.info("봇 일시정지됨")

    def resume(self) -> None:
        """봇 재개."""
        self._is_paused = False
        self._log.info("봇 재개됨")

    def request_emergency_close(self) -> None:
        """긴급 포지션 청산 요청."""
        self._emergency_close = True
        self._log.warning("긴급 청산 요청됨")

    # =========================================================================
    # Phase 4: AI 메모리 시스템
    # =========================================================================

    @property
    def memory_signals_enabled(self) -> bool:
        """메모리 기반 시그널 활성화 여부."""
        return self._use_memory_signals and self._enhanced_gemini is not None

    def enable_memory_signals(self) -> bool:
        """메모리 기반 시그널 활성화.

        Returns:
            활성화 성공 여부
        """
        if self._enhanced_gemini is None:
            self._log.warning("EnhancedGemini가 설정되지 않음")
            return False

        self._use_memory_signals = True
        self._log.info("메모리 기반 시그널 활성화됨")
        return True

    def disable_memory_signals(self) -> None:
        """메모리 기반 시그널 비활성화."""
        self._use_memory_signals = False
        self._log.info("메모리 기반 시그널 비활성화됨")

    def set_enhanced_gemini(
        self,
        gemini: EnhancedGeminiSignalGenerator,
    ) -> None:
        """EnhancedGeminiSignalGenerator 설정.

        Args:
            gemini: EnhancedGeminiSignalGenerator 인스턴스
        """
        self._enhanced_gemini = gemini
        self._log.info("EnhancedGemini 설정 완료")

    # =========================================================================
    # Redis 상태 관리
    # =========================================================================

    async def _sync_state_to_redis(self) -> None:
        """현재 상태를 Redis에 동기화."""
        if self._redis_state_manager is None:
            return

        try:
            state = self.get_state()
            await self._redis_state_manager.save_bot_state(self.bot_name, state)

            if self._current_position:
                await self._redis_state_manager.save_position(
                    self.bot_name, self._current_position
                )
            else:
                await self._redis_state_manager.delete_position(self.bot_name)

        except Exception as e:
            self._log.warning(f"Redis 상태 동기화 실패: {e}")

    async def _restore_state_from_redis(self) -> bool:
        """Redis에서 상태 복구.

        Returns:
            복구 성공 여부
        """
        if self._redis_state_manager is None:
            return False

        try:
            # 봇 상태 복구
            saved_state = await self._redis_state_manager.load_bot_state(self.bot_name)
            if saved_state:
                self._is_paused = saved_state.get("is_paused", False)
                self._loop_count = saved_state.get("loop_count", 0)
                self._last_signal = saved_state.get("last_signal", "WAIT")
                self._last_signal_time = saved_state.get("last_signal_time")
                self._log.info(
                    f"Redis에서 상태 복구: loop_count={self._loop_count}, "
                    f"is_paused={self._is_paused}"
                )

            # 포지션 복구
            saved_position = await self._redis_state_manager.load_position(
                self.bot_name
            )
            if saved_position:
                self._current_position = saved_position
                self._log.info(
                    f"Redis에서 포지션 복구: {saved_position.get('side')} @ "
                    f"${saved_position.get('entry_price', 0):,.2f}"
                )
                return True

            return bool(saved_state)

        except Exception as e:
            self._log.warning(f"Redis 상태 복구 실패: {e}")
            return False

    def set_redis_state_manager(
        self, manager: Union[RedisStateManager, DummyRedisStateManager]
    ) -> None:
        """Redis 상태 관리자 설정.

        Args:
            manager: Redis 상태 관리자
        """
        self._redis_state_manager = manager

    # =========================================================================
    # 초기화
    # =========================================================================

    async def _initialize(self) -> None:  # noqa: PLR0915
        """봇 초기화 (클라이언트 및 DB 연결)."""
        # Binance 클라이언트 초기화
        if self._binance_client is None:
            self._binance_client = BinanceTestnetClient(
                api_key=self._binance_api_key,
                secret_key=self._binance_secret_key,
                testnet=self.config.is_testnet,
            )

        # TradingConfig 생성
        trading_config = self.config.to_trading_config(
            binance_api_key=self._binance_api_key,
            binance_secret_key=self._binance_secret_key,
            gemini_api_key=self._gemini_api_key,
            discord_webhook_url=self._discord_webhook_url,
            database_url=self._database_url,
            loop_interval_seconds=self._loop_interval_seconds,
        )

        # Executor 초기화
        self._executor = TradingExecutor(
            binance_client=self._binance_client,
            config=trading_config,
        )

        # DB 연결
        if self._trade_db is None and self._database_url:
            try:
                self._trade_db = TradeHistoryDB(self._database_url)
                await self._trade_db.connect()
                self._log.info("거래 기록 DB 연결 완료")
            except Exception as e:
                self._log.error(f"거래 기록 DB 연결 실패: {e}")

        # Phase 4: AI 메모리 시스템 초기화
        if self._use_memory_signals and self._trade_db:
            try:
                analyzer = TradeHistoryAnalyzer(self._trade_db)
                self._memory_context_builder = AIMemoryContextBuilder(analyzer)

                # EnhancedGemini 생성 (주입되지 않은 경우)
                if self._enhanced_gemini is None and self._gemini_api_key:
                    self._enhanced_gemini = EnhancedGeminiSignalGenerator(
                        api_key=self._gemini_api_key,
                        context_builder=self._memory_context_builder,
                    )
                    self._log.info("AI 메모리 시스템 초기화 완료")
                elif self._enhanced_gemini and self._memory_context_builder:
                    self._enhanced_gemini.set_context_builder(
                        self._memory_context_builder
                    )
                    self._log.info("AI 메모리 컨텍스트 빌더 연결 완료")
            except Exception as e:
                self._log.error(f"AI 메모리 시스템 초기화 실패: {e}")
                self._use_memory_signals = False

        # Redis 상태 복구
        if self._redis_state_manager:
            restored = await self._restore_state_from_redis()
            if restored:
                self._log.info("이전 상태 복구 완료")
            # 봇 실행 상태 등록
            await self._redis_state_manager.register_bot(self.bot_name)
            await self._redis_state_manager.set_bot_running(self.bot_name)

        # Phase 5 통합: EnsembleSignalGenerator 초기화
        if getattr(self.config, "use_ensemble", False):
            try:
                from src.ai.ensemble import EnsembleSignalGenerator  # noqa: PLC0415
                self._ensemble_generator = EnsembleSignalGenerator(
                    rule_based_generator=self._signal_generator,
                )
                # Gemini 생성기 연결
                if self._enhanced_gemini:
                    self._ensemble_generator.set_gemini_generator(self._enhanced_gemini)
                self._log.info("EnsembleSignalGenerator 초기화 완료")
            except Exception as e:
                self._log.warning(f"앙상블 생성기 초기화 실패: {e}")

        # Phase 5 통합: TradeApprovalManager 초기화
        if getattr(self.config, "manual_approval_enabled", False):
            try:
                from src.trading.trade_approval import (  # noqa: PLC0415
                    TradeApprovalManager,
                )
                self._trade_approval = TradeApprovalManager(
                    manual_approval_enabled=True,
                    manual_approval_trades=getattr(
                        self.config, "manual_approval_trades", 5
                    ),
                    approval_timeout=getattr(
                        self.config, "approval_timeout", 60
                    ),
                )
                self._log.info("TradeApprovalManager 초기화 완료")
            except Exception as e:
                self._log.warning(f"승인 매니저 초기화 실패: {e}")

        # Phase 5.2: 리스크 매니저 일일 통계 초기화
        try:
            if self._binance_client:
                await self._binance_client.connect()
                balance_info = await self._binance_client.get_account_balance()
                await self._risk_manager.reset_daily_stats(balance_info["available"])
                self._log.info(
                    f"리스크 매니저 초기화: 시작 잔고=${balance_info['available']:,.2f}"
                )
        except Exception as e:
            self._log.warning(f"리스크 매니저 초기화 실패 (기본값 사용): {e}")
            await self._risk_manager.reset_daily_stats(1000.0)

        self._log.info("봇 초기화 완료")

    async def _cleanup(self) -> None:
        """봇 정리 (연결 해제)."""
        # Redis 상태 업데이트
        if self._redis_state_manager:
            await self._sync_state_to_redis()
            await self._redis_state_manager.set_bot_stopped(self.bot_name)
            self._log.info("Redis 상태 업데이트 완료")

        if self._trade_db:
            await self._trade_db.disconnect()
            self._log.info("거래 기록 DB 연결 해제")

    # =========================================================================
    # 시장 데이터
    # =========================================================================

    async def _fetch_market_data(self) -> dict[str, Any]:
        """시장 데이터 수집.

        Returns:
            시장 데이터 딕셔너리
        """
        if self._binance_client is None:
            raise RuntimeError("Binance client not initialized")

        # 현재 가격
        current_price = await self._binance_client.get_current_price(self.symbol)

        # 캔들스틱 데이터 조회
        klines = await self._binance_client.get_klines(self.symbol, limit=24)

        # 24시간 티커
        ticker_24h = await self._binance_client.get_ticker_24h(self.symbol)

        # 지표 계산
        indicators = analyze_market(klines, ticker_24h, current_price)

        self._current_price = current_price
        self._market_data = indicators

        # Phase 5 통합: MTF 15분봉 데이터 수집
        higher_tf_data = None
        if getattr(self.config, "use_mtf_filter", False):
            try:
                klines_15m = await self._binance_client.get_klines(
                    self.symbol, interval="15m", limit=24
                )
                higher_tf_data = analyze_market(klines_15m, ticker_24h, current_price)
                self._higher_tf_data = higher_tf_data
            except Exception as e:
                self._log.warning(f"15분봉 데이터 수집 실패: {e}")

        return {
            "current_price": current_price,
            "klines": klines,
            "ticker_24h": ticker_24h,
            "indicators": indicators,
            "higher_tf_data": higher_tf_data,
        }

    # =========================================================================
    # 시그널 생성
    # =========================================================================

    def _generate_signal(self, market_data: dict[str, Any]) -> str:
        """시그널 생성 (규칙 기반).

        Args:
            market_data: 시장 데이터

        Returns:
            시그널 ("LONG", "SHORT", "WAIT")
        """
        indicators = market_data.get("indicators", {})
        signal = self._signal_generator.get_signal(indicators)

        if not validate_signal(signal):
            self._log.warning(f"유효하지 않은 시그널 '{signal}', WAIT으로 변경")
            signal = "WAIT"

        self._last_signal = signal
        self._last_signal_time = datetime.now()

        return signal

    async def _generate_signal_with_memory(self, market_data: dict[str, Any]) -> str:
        """메모리 기반 시그널 생성 (Phase 4).

        과거 거래 분석 결과를 AI 프롬프트에 주입하여 시그널 생성

        Args:
            market_data: 시장 데이터

        Returns:
            시그널 ("LONG", "SHORT", "WAIT")
        """
        if not self._enhanced_gemini or not self._use_memory_signals:
            # Fallback to rule-based signal
            return self._generate_signal(market_data)

        try:
            indicators = market_data.get("indicators", {})
            signal = await self._enhanced_gemini.get_signal_with_memory(
                market_data=indicators,
                bot_id=str(self.config.bot_id),
            )

            if not validate_signal(signal):
                self._log.warning(
                    f"유효하지 않은 AI 시그널 '{signal}', 규칙 기반으로 대체"
                )
                return self._generate_signal(market_data)

            self._last_signal = signal
            self._last_signal_time = datetime.now()
            self._log.info(f"메모리 기반 AI 시그널: {signal}")

            return signal

        except Exception as e:
            self._log.error(f"메모리 시그널 생성 실패: {e}")
            # Fallback to rule-based signal
            return self._generate_signal(market_data)

    # =========================================================================
    # 포지션 관리
    # =========================================================================

    async def _open_position(
        self, signal: str, current_price: float, entry_atr: float | None = None
    ) -> dict | None:
        """포지션 오픈.

        Args:
            signal: 시그널 ("LONG" or "SHORT")
            current_price: 현재 가격
            entry_atr: 진입 시 ATR (Phase 6.1: 동적 TP/SL용)

        Returns:
            주문 결과 또는 None
        """
        if self._executor is None:
            raise RuntimeError("Executor not initialized")

        order = await self._executor.open_position(signal, current_price, entry_atr)

        if order:
            self._current_position = self._executor.current_position

            # DB에 기록
            if self._trade_db and self._executor.current_position:
                trade_id = await self._trade_db.add_entry(
                    entry_time=datetime.now(),
                    entry_price=current_price,
                    side=signal,
                    quantity=float(order.get("origQty", 0)),
                    leverage=self.config.get_effective_leverage(),
                    symbol=self.symbol,
                )
                self._executor.current_position["trade_id"] = trade_id
                self._log.info(f"거래 진입 기록: ID={trade_id}")

            # 콜백 호출
            await self._notify_trade("OPEN", signal, current_price, None)

        return order

    async def _close_position(  # noqa: PLR0915
        self,
        current_price: float,
        exit_reason: str,
    ) -> dict | None:
        """포지션 클로즈.

        Args:
            current_price: 현재 가격
            exit_reason: 청산 사유 ("TP", "SL", "TIME_CUT", "MANUAL")

        Returns:
            주문 결과 또는 None
        """
        if self._executor is None:
            raise RuntimeError("Executor not initialized")

        # 현재 포지션 정보
        position = await self._executor.get_position()
        if not position:
            self._log.info("청산할 포지션 없음")
            return None

        # 포지션 청산
        order = await self._executor.close_position()

        if order:
            entry_price = position["entry_price"]
            side = position["side"]

            # PnL 계산
            pnl_pct = self._executor.calculate_pnl_pct(entry_price, current_price, side)
            if side == "LONG":
                pnl_usd = (current_price - entry_price) * abs(position["position_amt"])
            else:
                pnl_usd = (entry_price - current_price) * abs(position["position_amt"])
            pnl_usd *= self.config.get_effective_leverage()

            # DB에 기록
            if self._trade_db and self._executor.current_position:
                executor_position = self._executor.current_position
                if executor_position and executor_position.get("trade_id"):
                    entry_time = executor_position.get("entry_time", datetime.now())
                    duration = int((datetime.now() - entry_time).total_seconds() / 60)
                    await self._trade_db.add_exit(
                        trade_id=executor_position["trade_id"],
                        exit_time=datetime.now(),
                        exit_price=current_price,
                        exit_reason=exit_reason,
                        pnl=pnl_usd,
                        pnl_pct=pnl_pct,
                        duration_minutes=duration,
                    )

            # Phase 5.2: 리스크 매니저에 PnL 추적
            await self._risk_manager.track_trade_pnl(pnl_usd)
            is_win = pnl_usd >= 0
            await self._risk_manager.track_trade_result(is_win)

            # 리스크 한도 체크
            halt, reason = await self._risk_manager.should_halt_trading()
            if halt and not self._risk_halt_notified:
                self._log.warning(f"리스크 한도 도달 - 자동 정지: {reason}")
                self.pause()
                self._risk_halt_notified = True
                await self._notify_risk_halt(reason)

            # Phase 5 통합: SignalTracker 결과 업데이트
            if self._last_signal_id:
                result_str = "win" if pnl_usd >= 0 else "loss"
                await self._signal_tracker.update_signal_result(
                    self._last_signal_id, result_str, pnl_usd
                )
                self._last_signal_id = None

            # Phase 5 통합: Prometheus 거래 메트릭
            if self._metrics:
                try:
                    result_str = "win" if pnl_usd >= 0 else "loss"
                    entry_time = None
                    if self._executor.current_position:
                        entry_time = self._executor.current_position.get("entry_time")
                    duration_s = (
                        (datetime.now() - entry_time).total_seconds()
                        if entry_time else 0.0
                    )
                    self._metrics.record_trade(
                        self.bot_name, side, result_str, duration_s
                    )
                    self._metrics.clear_position_metrics(self.bot_name)
                except Exception as e:
                    self._log.debug(f"메트릭 기록 실패: {e}")

            # Phase 5 통합: TradeApprovalManager 거래 완료 기록
            if self._trade_approval:
                await self._trade_approval.record_trade_completed(self.bot_name)

            self._current_position = None

            # 콜백 호출
            await self._notify_trade("CLOSE", side, current_price, pnl_pct)

            self._log.info(
                f"포지션 청산 완료: {exit_reason}, PnL={pnl_pct:+.2f}%"
            )

        return order

    # =========================================================================
    # 콜백
    # =========================================================================

    async def _notify_signal(self, signal: str, price: float) -> None:
        """시그널 콜백 호출."""
        if self._on_signal_callback:
            try:
                await self._on_signal_callback(self.bot_name, signal, price)
            except Exception as e:
                self._log.error(f"시그널 콜백 에러: {e}")

    async def _notify_trade(
        self,
        action: str,
        side: str,
        price: float,
        pnl: float | None,
    ) -> None:
        """거래 콜백 호출."""
        if self._on_trade_callback:
            try:
                await self._on_trade_callback(self.bot_name, action, side, price, pnl)
            except Exception as e:
                self._log.error(f"거래 콜백 에러: {e}")

    async def _notify_error(self, error: Exception) -> None:
        """에러 콜백 호출."""
        if self._on_error_callback:
            try:
                await self._on_error_callback(self.bot_name, error)
            except Exception as e:
                self._log.error(f"에러 콜백 에러: {e}")

    async def _notify_risk_halt(self, reason: str) -> None:
        """리스크 한도 도달 알림 (Phase 5.2)."""
        self._log.warning(f"[RISK HALT] {self.bot_name}: {reason}")
        # 에러 콜백을 통해 알림 (Discord 등에서 처리)
        if self._on_error_callback:
            try:
                error = RuntimeError(f"리스크 한도 도달: {reason}")
                await self._on_error_callback(self.bot_name, error)
            except Exception as e:
                self._log.error(f"리스크 알림 에러: {e}")

    # =========================================================================
    # 트레이딩 루프
    # =========================================================================

    async def _execute_single_loop(self) -> None:  # noqa: PLR0911, PLR0915
        """단일 트레이딩 루프 실행."""
        self._loop_count += 1
        self._log.info(f"루프 #{self._loop_count} 시작")

        # 1. 시장 데이터 수집
        market_data = await self._fetch_market_data()
        current_price = market_data["current_price"]

        # 잔고 업데이트 (드로다운 추적)
        if self._binance_client:
            try:
                balance_info = await self._binance_client.get_account_balance()
                await self._risk_manager.update_balance(balance_info["available"])
            except Exception:  # noqa: S110
                pass  # 잔고 조회 실패 시 스킵

        # 2. 시그널 생성 (우선순위: ensemble > memory_gemini > rule_based)
        signal_source = "rule_based"
        if getattr(self.config, "use_ensemble", False) and self._ensemble_generator:
            try:
                result = await self._ensemble_generator.generate_ensemble_signal(
                    market_data.get("indicators", {}),
                    bot_id=str(self.config.bot_id),
                )
                signal = result.final_signal
                signal_source = "ensemble"
                self._last_signal = signal
                self._last_signal_time = datetime.now()
                self._log.info(
                    f"앙상블 시그널: {signal} @ ${current_price:,.2f} "
                    f"(합의율={result.consensus_ratio:.1%})"
                )
            except Exception as e:
                self._log.warning(f"앙상블 시그널 실패, 폴백: {e}")
                signal = self._generate_signal(market_data)
        elif self._use_memory_signals and self._enhanced_gemini:
            signal = await self._generate_signal_with_memory(market_data)
            signal_source = "memory_gemini"
            self._log.info(f"메모리 시그널: {signal} @ ${current_price:,.2f}")
        else:
            signal = self._generate_signal(market_data)
            self._log.info(f"시그널: {signal} @ ${current_price:,.2f}")

        # Phase 6.2: 마켓 레짐 감지 및 필터링
        indicators = market_data.get("indicators", {})
        self._current_regime = self._regime_detector.detect(indicators)

        if self.config.use_regime_filter:
            original_signal = signal
            signal = self._regime_detector.filter_signal(
                signal,
                self._current_regime,
                allow_weak_trend=self.config.allow_weak_trend,
            )
            if signal != original_signal:
                self._log.info(
                    f"레짐 필터링: {original_signal} → {signal} "
                    f"(레짐={self._current_regime.value})"
                )

        # Phase 5 통합: 다중 타임프레임 필터링
        if getattr(self.config, "use_mtf_filter", False) and self._higher_tf_data:
            original_signal = signal
            signal = self._mtf_analyzer.filter_signal(signal, self._higher_tf_data)
            if signal != original_signal:
                self._log.info(
                    f"MTF 필터링: {original_signal} → {signal}"
                )

        # Phase 5 통합: 시그널 기록
        try:
            conditions = {
                "price": current_price,
                "regime": self._current_regime.value,
            }
            self._last_signal_id = await self._signal_tracker.record_signal(
                bot_id=str(self.config.bot_id),
                signal=signal,
                source=signal_source,
                market_conditions=conditions,
            )
        except Exception:  # noqa: S110
            pass

        # 콜백 호출
        await self._notify_signal(signal, current_price)

        # 3. 긴급 청산 확인
        if self._emergency_close:
            self._log.warning("긴급 청산 실행")
            await self._close_position(current_price, "MANUAL")
            self._emergency_close = False
            self._is_paused = True
            return

        # 4. 현재 포지션 확인
        if self._executor is None:
            return

        position = await self._executor.get_position()
        has_position = position is not None
        self._current_position = position

        if has_position and position is not None:
            self._log.debug(
                f"현재 포지션: {position['side']} @ ${position['entry_price']:,.2f}"
            )

            # Phase 5 통합: Prometheus 포지션 PnL 기록
            if self._metrics and self._executor:
                try:
                    pos_pnl_pct = self._executor.calculate_pnl_pct(
                        position["entry_price"], current_price, position["side"]
                    )
                    self._metrics.record_position_pnl(self.bot_name, pos_pnl_pct)
                except Exception:  # noqa: S110
                    pass

            # Timecut 체크
            if (
                self._executor.current_position
                and self._executor.check_timecut(self._executor.current_position)
            ):
                    self._log.info("Timecut 조건 충족")
                    await self._close_position(current_price, "TIME_CUT")
                    return

            # TP/SL 체크 (Phase 6.1: ATR 기반 동적 TP/SL 지원)
            exit_reason = await self._executor.check_tp_sl_dynamic(
                position, current_price
            )
            if exit_reason:
                self._log.info(f"종료 조건 충족: {exit_reason}")
                await self._close_position(current_price, exit_reason)
                return

        # 5. 신규 포지션 진입
        if self._is_paused:
            self._log.debug("봇 일시정지 중 - 진입 스킵")
            return

        # Phase 5.2/5.3: 리스크 체크 (쿨다운, 일일 손실 한도)
        should_skip, skip_reason = await self._risk_manager.should_skip_trade()
        if should_skip:
            self._log.info(f"리스크 제한으로 진입 스킵: {skip_reason}")
            return

        # Phase 5 통합: 수동 승인 체크 (비차단)
        if self._trade_approval and signal in ("LONG", "SHORT"):
            # 대기 중인 승인 요청이 있는지 확인
            if self._pending_approval_request:
                from src.trading.trade_approval import ApprovalStatus  # noqa: PLC0415
                req = self._pending_approval_request
                if req.status == ApprovalStatus.APPROVED:
                    self._log.info(f"승인 완료 - 진입 진행: {req.request_id}")
                    self._pending_approval_request = None
                elif req.status == ApprovalStatus.PENDING:
                    # 타임아웃 체크
                    elapsed = (
                        datetime.now(req.created_at.tzinfo) - req.created_at
                    ).total_seconds()
                    if elapsed > self._trade_approval.approval_timeout:
                        req.timeout()
                        self._pending_approval_request = None
                        self._log.info("승인 시간 초과 - 이번 루프 스킵")
                        return
                    self._log.debug("승인 대기 중 - 이번 루프 스킵")
                    return
                else:
                    # REJECTED or TIMEOUT
                    self._pending_approval_request = None
                    self._log.info(f"승인 거부/만료 - 스킵: {req.status.value}")
                    return

            # 새 승인 필요 여부 체크
            if await self._trade_approval.requires_approval(self.bot_name):
                indicators_data = self._market_data or {}
                request = await self._trade_approval.create_request(
                    bot_name=self.bot_name,
                    signal=signal,
                    price=current_price,
                    quantity=0.0,
                    rsi=indicators_data.get("rsi"),
                    atr=indicators_data.get("atr"),
                )
                self._pending_approval_request = request
                self._log.info(f"수동 승인 요청 생성: {request.request_id}")
                return

        # Phase 5 통합: 노출도 체크
        if self._on_exposure_check and signal in ("LONG", "SHORT"):
            try:
                pct = self.config.get_effective_position_size_pct()
                position_value = current_price * pct
                can_open, reason = await self._on_exposure_check(
                    self.bot_name, position_value
                )
                if not can_open:
                    self._log.info(f"노출도 한도 초과 - 진입 스킵: {reason}")
                    return
            except Exception as e:
                self._log.warning(f"노출도 체크 실패: {e}")

        if should_enter_trade(signal, has_position):
            # Phase 6.1: ATR 값 전달 (동적 TP/SL용)
            entry_atr = None
            if self._market_data:
                indicators = self._market_data
                entry_atr = indicators.get("atr")
            self._log.info(
                f"{signal} 포지션 진입..."
                + (f" (ATR={entry_atr:.2f})" if entry_atr else "")
            )
            await self._open_position(signal, current_price, entry_atr)

    async def _run_loop(self) -> None:
        """메인 트레이딩 루프."""
        self._is_running = True
        self._uptime_start = datetime.now()
        self._log.info("트레이딩 루프 시작")

        while self._is_running:
            try:
                await self._execute_single_loop()

                # Redis 상태 동기화
                await self._sync_state_to_redis()

            except Exception as e:
                self._log.error(f"루프 에러: {e}", exc_info=True)
                await self._notify_error(e)

            # 다음 루프까지 대기
            await asyncio.sleep(self._loop_interval_seconds)

        self._log.info("트레이딩 루프 종료")

    # =========================================================================
    # 생명주기 관리
    # =========================================================================

    async def start(self) -> None:
        """봇 시작."""
        self._log.info("봇 시작 중...")

        try:
            await self._initialize()
            await self._run_loop()
        except asyncio.CancelledError:
            self._log.info("봇 태스크 취소됨")
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """봇 정지."""
        self._log.info("봇 정지 요청")
        self._is_running = False
