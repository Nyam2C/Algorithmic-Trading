"""개별 봇 인스턴스 모듈.

각 봇의 트레이딩 루프 로직을 캡슐화한 BotInstance 클래스.
기존 main.py의 trading_loop 로직을 분리하여 멀티봇 실행 지원.

Phase 4: AI 메모리 시스템 통합
- EnhancedGeminiSignalGenerator 지원
- 과거 거래 분석 기반 시그널 생성
"""
import asyncio
import contextlib
import math
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

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
from src.storage.audit_log import AuditLogManager
from src.storage.redis_state import DummyRedisStateManager, RedisStateManager
from src.storage.trade_history import TradeHistoryDB
from src.trading.executor import TradingExecutor
from src.trading.risk_manager import RiskManager  # Phase 5.2
from src.trading.signal_cooldown import SignalCooldownManager

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

    def __init__(  # noqa: PLR0915
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
        redis_state_manager: RedisStateManager | DummyRedisStateManager | None = None,
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
        self._emergency_event = asyncio.Event()
        self._uptime_start: datetime | None = None
        self._loop_count = 0
        self._consecutive_errors: int = 0
        self._max_consecutive_errors: int = 5

        # 현재 데이터
        self._current_price: float = 0.0
        self._last_signal: str = "WAIT"
        self._last_signal_time: datetime | None = None
        self._current_position: dict | None = None
        self._market_data: dict | None = None
        self._consecutive_wait_count: int = 0

        # 루프 타이밍
        self._last_loop_duration: float = 0.0
        self._last_loop_time: datetime | None = None

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
            strategy=getattr(config, "signal_strategy", "trend_pullback"),
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

        # APEX-V Phase D: Kelly sizer + Execution tracker
        self._kelly_sizer: Any | None = None
        self._execution_tracker: Any | None = None

        # APEX-V 5-Gate Pipeline
        self._pipeline_size_pct: float | None = None
        self._last_ensemble_result: Any | None = None  # EnsembleResult 캐시
        self._last_mti_grade: str = "OPTIMAL"

        # Phase 5 통합: SignalTracker (인메모리)
        self._signal_tracker = SignalTracker(db_pool=None)
        self._last_signal_id: str | None = None

        # Phase 5 통합: Prometheus 메트릭
        self._metrics: Any | None = None
        try:
            from src.metrics.prometheus import _get_metrics
            self._metrics = _get_metrics()
        except Exception:  # noqa: S110
            pass  # prometheus_client 미설치 시 스킵

        # Phase 5 통합: MultiTimeframeAnalyzer
        self._mtf_analyzer = MultiTimeframeAnalyzer()
        self._higher_tf_data: dict[str, Any] | None = None
        self._higher_tf_fetch_time: datetime | None = None

        # Phase 5 통합: EnsembleSignalGenerator
        self._ensemble_generator: Any | None = None

        # Phase 5 통합: TradeApprovalManager
        self._trade_approval: Any | None = None
        self._pending_approval_request: Any | None = None

        # Phase 5 통합: 노출도 체크 콜백
        self._on_exposure_check = on_exposure_check

        # Phase 5 통합: AuditLogManager
        self._audit_log: AuditLogManager | None = None

        # 시그널 쿨다운 매니저
        self._signal_cooldown: SignalCooldownManager | None = None

        # Phase 5 통합: 외부 시그널 주입
        self._injected_signal: dict[str, Any] | None = None

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
            # 루프 타이밍
            "last_loop_duration": self._last_loop_duration,
            "last_loop_time": self._last_loop_time,
            # 포지션 유무
            "has_position": self._current_position is not None,
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
        self._emergency_event.set()
        self._log.warning("긴급 청산 요청됨")

    def inject_signal(self, signal_data: dict[str, Any]) -> bool:
        """외부 시그널 주입.

        Args:
            signal_data: 시그널 데이터 (signal, source, confidence, metadata)

        Returns:
            주입 성공 여부
        """
        signal = signal_data.get("signal", "").upper()
        if signal not in ("LONG", "SHORT", "WAIT"):
            self._log.warning(f"유효하지 않은 주입 시그널: {signal}")
            return False

        self._injected_signal = signal_data
        self._log.info(
            f"외부 시그널 주입: {signal} "
            f"(source={signal_data.get('source', 'unknown')})"
        )
        return True

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

    def get_last_ai_call(self) -> dict[str, Any] | None:
        """마지막 AI 호출 정보 반환 (디버깅용).

        Returns:
            마지막 호출 정보 딕셔너리 또는 None
        """
        if self._enhanced_gemini:
            return self._enhanced_gemini.get_last_ai_call()
        return None

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

            # Phase 1: 리스크 매니저 상태 영속화
            await self._redis_state_manager.save_risk_state(
                self.bot_name, self._risk_manager.to_dict()
            )

            # Phase D: Kelly sizer + Execution tracker 영속화
            if self._kelly_sizer:
                try:
                    await self._redis_state_manager.save_bot_state(
                        f"{self.bot_name}:kelly",
                        self._kelly_sizer.to_dict(),
                    )
                except Exception as e:
                    self._log.debug(f"Kelly 상태 저장 실패: {e}")
            if self._execution_tracker:
                try:
                    await self._redis_state_manager.save_bot_state(
                        f"{self.bot_name}:exec_tracker",
                        self._execution_tracker.to_dict(),
                    )
                except Exception as e:
                    self._log.debug(f"ExecTracker 상태 저장 실패: {e}")

            # Phase 1: 하트비트 기록 (TTL = loop_interval x 2)
            heartbeat_ttl = self._loop_interval_seconds * 2
            heartbeat_data = {
                "timestamp": datetime.now().isoformat(),
                "loop_count": self._loop_count,
                "status": "paused" if self._is_paused else "running",
                "current_price": self._current_price,
                "has_position": self._current_position is not None,
            }
            await self._redis_state_manager.write_heartbeat(
                self.bot_name, heartbeat_data, heartbeat_ttl
            )

        except Exception as e:
            self._log.warning(f"Redis 상태 동기화 실패: {e}")

    async def _restore_state_from_redis(self) -> bool:  # noqa: PLR0915
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

            # Phase 1: 리스크 매니저 상태 복구
            risk_state = await self._redis_state_manager.load_risk_state(
                self.bot_name
            )
            if risk_state:
                self._risk_manager.from_dict(risk_state)
                self._log.info(
                    f"리스크 상태 복구: daily_pnl={risk_state.get('daily_pnl', 0):.2f}"
                )

            # Phase D: Kelly sizer + Execution tracker 복구
            if self._kelly_sizer:
                try:
                    kelly_data = await self._redis_state_manager.load_bot_state(
                        f"{self.bot_name}:kelly"
                    )
                    if kelly_data:
                        self._kelly_sizer.from_dict(kelly_data)
                        self._log.info("KellySizer 상태 복구 완료")
                except Exception as e:
                    self._log.debug(f"Kelly 상태 복구 실패: {e}")
            if self._execution_tracker:
                try:
                    exec_data = await self._redis_state_manager.load_bot_state(
                        f"{self.bot_name}:exec_tracker"
                    )
                    if exec_data:
                        self._execution_tracker.from_dict(exec_data)
                        self._log.info("ExecutionTracker 상태 복구 완료")
                except Exception as e:
                    self._log.debug(f"ExecTracker 상태 복구 실패: {e}")

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

            # Check for recovery markers (failed DB writes from previous session)
            try:
                recovery_data = await self._redis_state_manager.load_position(
                    f"{self.bot_name}:recovery"
                )
                if recovery_data:
                    self._log.warning(f"복구 마커 발견: {recovery_data}")
                    if self._trade_db:
                        try:
                            from datetime import datetime as dt
                            entry_time_str = recovery_data.get("entry_time", "")
                            entry_time = (
                                dt.fromisoformat(entry_time_str)
                                if entry_time_str else dt.now()
                            )
                            await self._trade_db.add_entry(
                                entry_time=entry_time,
                                entry_price=recovery_data.get("entry_price", 0),
                                side=recovery_data.get("side", "LONG"),
                                quantity=recovery_data.get("quantity", 0),
                                leverage=recovery_data.get("leverage", 1),
                                symbol=recovery_data.get("symbol", self.symbol),
                            )
                            # Clean up recovery marker
                            await self._redis_state_manager.delete_position(
                                f"{self.bot_name}:recovery"
                            )
                            self._log.info("복구 마커 DB 복구 완료 - 마커 삭제")
                        except Exception as db_err:
                            self._log.error(f"복구 마커 DB 복구 실패: {db_err}")
            except Exception as recovery_err:
                self._log.warning(f"복구 마커 체크 실패: {recovery_err}")

            # Check for exit recovery markers (failed exit DB writes)
            try:
                exit_recovery = await self._redis_state_manager.load_position(
                    f"{self.bot_name}:recovery:exit"
                )
                if exit_recovery:
                    self._log.warning(f"청산 복구 마커 발견: {exit_recovery}")
                    if self._trade_db:
                        try:
                            from datetime import datetime as dt
                            exit_time_str = exit_recovery.get("exit_time", "")
                            exit_time = (
                                dt.fromisoformat(exit_time_str)
                                if exit_time_str else dt.now()
                            )
                            await self._trade_db.add_exit(
                                trade_id=exit_recovery.get("trade_id", ""),
                                exit_time=exit_time,
                                exit_price=exit_recovery.get("exit_price", 0),
                                exit_reason=exit_recovery.get("exit_reason", "UNKNOWN"),
                                pnl=exit_recovery.get("pnl", 0),
                                pnl_pct=exit_recovery.get("pnl_pct", 0),
                            )
                            await self._redis_state_manager.delete_position(
                                f"{self.bot_name}:recovery:exit"
                            )
                            self._log.info("청산 복구 마커 DB 복구 완료 - 마커 삭제")
                        except Exception as db_err:
                            self._log.error(f"청산 복구 마커 DB 복구 실패: {db_err}")
            except Exception as exit_recovery_err:
                self._log.warning(f"청산 복구 마커 체크 실패: {exit_recovery_err}")

            return bool(saved_state)

        except Exception as e:
            self._log.warning(f"Redis 상태 복구 실패: {e}")
            return False

    async def _reconcile_position(self) -> None:
        """거래소 포지션과 Redis 상태를 비교하여 조정.

        - 거래소에만 포지션 있음 (orphan) -> Redis에 저장, 내부 상태 갱신
        - Redis에만 포지션 있음 (ghost) -> Redis에서 삭제, 내부 상태 초기화
        - 양쪽 모두 있음 -> 거래소 값으로 동기화
        - 양쪽 모두 없음 -> 아무 동작 없음
        """
        if self._binance_client is None:
            return

        exchange_pos = None
        for attempt in range(3):
            try:
                exchange_pos = await self._binance_client.get_position(self.symbol)
                break
            except Exception as e:
                _max_retries = 3
                if attempt < _max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s
                    self._log.warning(
                        f"거래소 포지션 조회 실패 (시도 {attempt + 1}/3, "
                        f"{delay}s 후 재시도): {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self._log.error(f"거래소 포지션 조회 3회 실패 (조정 스킵): {e}")
                    return

        redis_pos = None
        if self._redis_state_manager:
            try:
                redis_pos = await self._redis_state_manager.load_position(self.bot_name)
            except Exception as e:
                self._log.warning(f"Redis 포지션 조회 실패: {e}")

        if exchange_pos and not redis_pos:
            # Orphan: 거래소에만 포지션 존재 -> adopt
            self._current_position = exchange_pos
            side = exchange_pos['side']
            ep = exchange_pos['entry_price']
            self._log.warning(
                f"고아 포지션 발견 (거래소만): {side} @ ${ep:,.2f} - 채택"
            )
            if self._redis_state_manager:
                await self._redis_state_manager.save_position(
                    self.bot_name, exchange_pos
                )

        elif not exchange_pos and redis_pos:
            # Ghost: Redis에만 포지션 존재 -> remove
            self._current_position = None
            side = redis_pos.get('side')
            ep = redis_pos.get('entry_price', 0)
            self._log.warning(
                f"유령 포지션 발견 (Redis만): {side} @ ${ep:,.2f} - 삭제"
            )
            if self._redis_state_manager:
                await self._redis_state_manager.delete_position(self.bot_name)

        elif exchange_pos and redis_pos:
            # Both exist -> sync to exchange values
            self._current_position = exchange_pos
            side = exchange_pos['side']
            ep = exchange_pos['entry_price']
            self._log.info(
                f"포지션 동기화 (거래소 기준): {side} @ ${ep:,.2f}"
            )
            if self._redis_state_manager:
                await self._redis_state_manager.save_position(
                    self.bot_name, exchange_pos
                )

        # else: no position on either side -> nothing to do

    def set_redis_state_manager(
        self, manager: RedisStateManager | DummyRedisStateManager
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

        # Phase 5 통합: 감사 로그 초기화
        try:
            db_pool = getattr(self._trade_db, 'pool', None) if self._trade_db else None
            self._audit_log = AuditLogManager(db_pool=db_pool)
            self._log.info("AuditLogManager 초기화 완료")
        except Exception as e:
            self._log.warning(f"AuditLogManager 초기화 실패: {e}")

        # Phase 5 통합: SignalTracker DB 연결
        if self._trade_db:
            try:
                db_pool = getattr(self._trade_db, 'pool', None)
                if db_pool:
                    self._signal_tracker = SignalTracker(db_pool=db_pool)
                    self._log.info("SignalTracker DB 풀 연결 완료")
            except Exception as e:
                self._log.warning(f"SignalTracker DB 연결 실패: {e}")

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

        # 시그널 쿨다운 매니저 초기화
        if self._redis_state_manager:
            self._signal_cooldown = SignalCooldownManager(
                redis_manager=self._redis_state_manager,
                bot_name=self.bot_name,
                symbol=self.symbol,
                signal_cooldown_seconds=self.config.signal_cooldown_seconds,
                post_loss_cooldown_seconds=self.config.post_loss_cooldown_seconds,
                alert_dedup_seconds=self.config.alert_dedup_seconds,
            )
            self._log.info("SignalCooldownManager 초기화 완료")

        # Phase 5 통합: EnsembleSignalGenerator 초기화
        if getattr(self.config, "use_ensemble", False):
            try:
                from src.ai.ensemble import EnsembleSignalGenerator
                self._ensemble_generator = EnsembleSignalGenerator(
                    rule_based_generator=self._signal_generator,
                )
                # Gemini 생성기 연결
                if self._enhanced_gemini:
                    self._ensemble_generator.set_gemini_generator(self._enhanced_gemini)
                self._log.info("EnsembleSignalGenerator 초기화 완료")

                # Phase 5 통합: IndicatorScorer 연결
                try:
                    from src.ai.scoring import IndicatorScorer
                    scorer = IndicatorScorer()
                    self._ensemble_generator.set_scoring_generator(scorer)
                    self._log.info("IndicatorScorer 앙상블에 연결 완료")
                except Exception as e2:
                    self._log.warning(f"IndicatorScorer 연결 실패: {e2}")

                # APEX-V Phase B: 채널 연결
                if self.config.use_tsmom_channel:
                    from src.ai.channels.tsmom import TSMOMChannel
                    self._ensemble_generator.set_tsmom_channel(TSMOMChannel())
                    self._log.info("TSMOM 채널 연결")

                if self.config.use_funding_basis_channel:
                    from src.ai.channels.funding_basis import (
                        FundingBasisChannel,
                    )
                    self._ensemble_generator.set_funding_channel(FundingBasisChannel())
                    self._log.info("FundingBasis 채널 연결")

                if self.config.use_leverage_topology_channel:
                    from src.ai.channels.leverage_topology import (
                        LeverageTopologyChannel,
                    )
                    self._ensemble_generator.set_leverage_channel(LeverageTopologyChannel())
                    self._log.info("LeverageTopology 채널 연결")

                if self.config.use_smart_money_channel:
                    from src.ai.channels.smart_money_divergence import (
                        SmartMoneyDivergenceChannel,
                    )
                    self._ensemble_generator.set_smart_money_channel(SmartMoneyDivergenceChannel())
                    self._log.info("SmartMoney 채널 연결")

                # APEX-V Phase C: Confluence Engine 초기화
                if getattr(self.config, "use_confluence_engine", False):
                    from src.ai.confluence.confluence_engine import (
                        ConfluenceEngine,
                    )
                    from src.ai.confluence.cost_calculator import (
                        CostCalculator,
                    )
                    from src.ai.confluence.session_classifier import (
                        SessionClassifier,
                    )
                    from src.ai.confluence.signal_dedup import (
                        SignalDeduplicator,
                    )
                    from src.ai.confluence.vitality_tracker import (
                        VitalityTracker,
                    )
                    _confluence = ConfluenceEngine(
                        deduplicator=SignalDeduplicator(),
                        cost_calculator=CostCalculator(),
                        vitality_tracker=VitalityTracker(),
                        session_classifier=SessionClassifier(),
                        gemini_verifier=self._enhanced_gemini,
                    )
                    self._ensemble_generator.set_confluence_engine(_confluence)
                    self._log.info("Confluence Engine 초기화 완료")

            except Exception as e:
                self._log.warning(f"앙상블 생성기 초기화 실패: {e}")

        # APEX-V Phase D: Kelly Sizer 초기화
        if getattr(self.config, "use_kelly_sizing", False):
            try:
                from src.trading.kelly_sizer import KellySizer
                self._kelly_sizer = KellySizer(
                    kelly_fraction=getattr(self.config, "kelly_fraction", 0.25),
                    min_size_pct=getattr(self.config, "kelly_min_size_pct", 0.003),
                    max_size_pct=getattr(self.config, "kelly_max_size_pct", 0.02),
                )
                self._log.info("KellySizer 초기화 완료")
            except Exception as e:
                self._log.warning(f"KellySizer 초기화 실패: {e}")

        # APEX-V Phase D: Execution Tracker 초기화
        if getattr(self.config, "use_execution_feedback", False):
            try:
                from src.trading.execution_tracker import (
                    ExecutionTracker,
                )
                self._execution_tracker = ExecutionTracker()
                self._log.info("ExecutionTracker 초기화 완료")
            except Exception as e:
                self._log.warning(f"ExecutionTracker 초기화 실패: {e}")

        # Phase 5 통합: TradeApprovalManager 초기화
        if getattr(self.config, "manual_approval_enabled", False):
            try:
                from src.trading.trade_approval import (
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

        # Phase 5.2: Binance 연결 + 리스크 매니저 초기화
        # (1) Binance 연결 (별도 try-except — 실패 원인 정확히 로깅)
        connected = False
        if self._binance_client:
            try:
                await self._binance_client.connect()
                connected = True
            except Exception as e:
                self._log.error(f"Binance 클라이언트 연결 실패: {e}")

        # Position reconciliation: 거래소 vs Redis 포지션 동기화 (연결 성공 시에만)
        if connected:
            await self._reconcile_position()

        # (2) 메트릭 기본값 등록 (연결 무관 — Grafana template variable 활성화)
        if self._metrics:
            m = self._metrics
            bn = self.bot_name
            m.record_account_balance(bn, 0.0)
            m.record_available_balance(bn, 0.0)
            m.record_unrealized_pnl(bn, 0.0)
            stats = self._risk_manager.get_stats()
            m.record_daily_pnl(bn, stats["daily_pnl"])
            m.record_daily_pnl_pct(bn, stats["daily_pnl_pct"])
            m.record_drawdown_pct(bn, stats["current_drawdown"])
            m.record_win_rate(bn, stats["win_rate"])

        # (3) 잔고 조회 + 메트릭 실제값 갱신 (연결 성공 시)
        if connected:
            try:
                balance_info = await self._binance_client.get_account_balance()
                await self._risk_manager.reset_daily_stats(balance_info["available"])
                self._log.info(
                    f"리스크 매니저 초기화: 시작 잔고=${balance_info['available']:,.2f}"
                )
                if self._metrics:
                    m.record_account_balance(bn, balance_info["balance"])
                    m.record_available_balance(bn, balance_info["available"])
                    m.record_unrealized_pnl(
                        bn, balance_info.get("unrealized_pnl", 0.0)
                    )
            except Exception as e:
                self._log.warning(f"잔고 조회 실패 (기본값 사용): {e}")
                await self._risk_manager.reset_daily_stats(1000.0)
        else:
            await self._risk_manager.reset_daily_stats(1000.0)

        # 시그널 모드 로그
        if self._ensemble_generator:
            mode = "앙상블 (Gemini + Rule-based)"
        elif self._use_memory_signals and self._enhanced_gemini:
            mode = "AI 메모리 (Enhanced Gemini)"
        else:
            mode = "규칙 기반 (Rule-based only)"
        self._log.warning(f"시그널 모드: {mode}")

        self._log.info("봇 초기화 완료")

    async def _cleanup(self) -> None:
        """봇 정리 (연결 해제)."""
        # 열린 포지션 확인 및 경고
        try:
            if self._executor:
                position = await self._executor.get_position()
                if position:
                    self._log.warning(
                        f"종료 시 열린 포지션 발견: {position.get('side', 'UNKNOWN')} "
                        f"{abs(position.get('position_amt', 0))} {self.symbol} "
                        f"@ ${position.get('entry_price', 0):,.2f} "
                        f"(미실현PnL: ${position.get('unrealized_pnl', 0):,.2f})"
                    )
        except Exception as e:
            self._log.warning(f"종료 시 포지션 확인 실패: {e}")

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

        # 캔들스틱 데이터 조회 (MA99 계산에 최소 99개 필요, 여유분 포함 150개)
        klines = await self._binance_client.get_klines(self.symbol, limit=150)

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
                    self.symbol, interval="15m", limit=150
                )
                higher_tf_data = analyze_market(klines_15m, ticker_24h, current_price)
                self._higher_tf_data = higher_tf_data
                self._higher_tf_fetch_time = datetime.now()
            except Exception as e:
                self._log.warning(f"15분봉 데이터 수집 실패: {e}")

        return {
            "current_price": current_price,
            "klines": klines,
            "ticker_24h": ticker_24h,
            "indicators": indicators,
            "higher_tf_data": higher_tf_data,
        }

    async def _fetch_sentiment_data(self) -> dict[str, Any] | None:
        """시장 심리 데이터 수집 (Phase B 채널용)."""
        cfg = self.config
        if not any([
            cfg.use_funding_basis_channel,
            cfg.use_leverage_topology_channel,
            cfg.use_smart_money_channel,
        ]):
            return None

        if self._binance_client is None:
            return None

        try:
            sentiment = await self._binance_client.get_market_sentiment(self.symbol)

            # 단위 변환: Binance는 percentage(0.05=0.05%), 채널은 raw(0.0005=0.05%)
            raw_fr = sentiment["funding_rate"] / 100.0

            current_price = self._current_price

            # Redis에 OI/LS 스냅샷 저장
            if self._redis_state_manager:
                oi = sentiment.get("open_interest", 0.0)
                ls = sentiment.get("long_short_ratio", 1.0)
                if oi > 0:
                    await self._redis_state_manager.save_oi_snapshot(
                        self.symbol, oi, current_price
                    )
                if ls > 0:
                    await self._redis_state_manager.save_ls_snapshot(
                        self.symbol, ls, current_price
                    )

            # Redis에서 히스토리 로드
            oi_history: list[dict] = []
            ls_history: list[dict] = []
            if self._redis_state_manager:
                oi_history = await self._redis_state_manager.load_oi_history(
                    self.symbol
                )
                ls_history = await self._redis_state_manager.load_ls_history(
                    self.symbol
                )

            return {
                "funding_rate": raw_fr,
                "long_short_ratio": sentiment["long_short_ratio"],
                "open_interest": sentiment["open_interest"],
                "current_price": current_price,
                "oi_history": oi_history,
                "ls_history": ls_history,
            }
        except Exception as e:
            self._log.warning(f"심리 데이터 수집 실패: {e}")
            return None

    def _get_klines_df(self, market_data: dict[str, Any]) -> Any:
        """klines를 TSMOM용 DataFrame으로 변환."""
        if not self.config.use_tsmom_channel:
            return None
        klines = market_data.get("klines")
        if not klines:
            return None
        try:
            import pandas as pd
            df = pd.DataFrame(klines, columns=[
                "timestamp", "open", "high", "low", "close",
                "volume", "close_time", "quote_volume",
                "trades", "taker_buy_base", "taker_buy_quote", "ignore",
            ])
            df["close"] = df["close"].astype(float)
            return df
        except Exception:
            return None

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
            self._log.warning(f"AI 시그널 생성 실패, 규칙 기반으로 폴백: {e}")
            if self._metrics:
                try:
                    self._metrics.record_signal(
                        self.bot_name, "FALLBACK", "gemini_error"
                    )
                except Exception as e:
                    self._log.debug(f"폴백 시그널 메트릭 기록 실패: {e}")
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

        # Phase 7: 단일 거래 리스크 검증
        risk_ok, risk_reason = await self._risk_manager.validate_position_risk(
            stop_loss_pct=self.config.get_effective_stop_loss_pct(),
            leverage=self.config.get_effective_leverage(),
            max_loss_per_trade_pct=getattr(self.config, "max_loss_per_trade_pct", 0.02),
        )
        if not risk_ok:
            self._log.warning(f"리스크 검증 실패 - 진입 중단: {risk_reason}")
            return None

        # APEX-V: Pipeline이 사전 계산한 사이즈 우선 사용
        dynamic_size_pct: float | None
        if self._pipeline_size_pct is not None:
            dynamic_size_pct = self._pipeline_size_pct
            self._pipeline_size_pct = None  # 한번 사용 후 클리어
        else:
            dynamic_size_pct = self._compute_dynamic_size()

        order = await self._executor.open_position(
            signal, current_price, entry_atr, dynamic_size_pct=dynamic_size_pct
        )

        if order:
            self._current_position = self._executor.current_position

            # DB에 기록 (실패 시 Redis에 복구 마커 저장)
            if self._trade_db and self._executor.current_position:
                # Phase 8: 실제 체결가(fill price) 사용
                fill_price = self._executor.current_position.get(
                    "entry_price", current_price
                )
                try:
                    trade_id = await self._trade_db.add_entry(
                        entry_time=datetime.now(),
                        entry_price=fill_price,
                        side=signal,
                        quantity=float(order.get("origQty", 0)),
                        leverage=self.config.get_effective_leverage(),
                        symbol=self.symbol,
                    )
                    self._executor.current_position["trade_id"] = trade_id
                    self._log.info(f"거래 진입 기록: ID={trade_id}")
                except Exception as db_err:
                    self._log.error(f"거래 진입 DB 기록 실패: {db_err}")
                    # Redis에 복구 마커 저장
                    if self._redis_state_manager:
                        try:
                            recovery_data = {
                                "entry_time": datetime.now().isoformat(),
                                "entry_price": current_price,
                                "side": signal,
                                "quantity": float(order.get("origQty", 0)),
                                "leverage": self.config.get_effective_leverage(),
                                "symbol": self.symbol,
                                "order_id": order.get("orderId"),
                            }
                            await self._redis_state_manager.save_position(
                                f"{self.bot_name}:recovery", recovery_data
                            )
                            self._log.warning("Redis에 복구 마커 저장 완료")
                        except Exception as redis_err:
                            self._log.critical(
                                "DB와 Redis 모두 기록 실패"
                                f" - 수동 확인 필요: {redis_err}"
                            )

            # 시그널 쿨다운 설정
            if self._signal_cooldown:
                await self._signal_cooldown.set_signal_cooldown(signal)

            # Phase 5 통합: 감사 로그 기록
            if self._audit_log:
                try:
                    await self._audit_log.log_trade_open(
                        self.bot_name, signal,
                        float(order.get("origQty", 0)), current_price,
                    )
                except Exception as e:
                    self._log.debug(f"진입 감사 로그 기록 실패: {e}")

            # 콜백 호출
            await self._notify_trade("OPEN", signal, current_price, None)

            # 구조화 로깅: 거래 진입 이벤트
            self._log.bind(event_type="TRADE_OPEN").info(
                "포지션 진입",
                side=signal,
                price=current_price,
                quantity=float(order.get("origQty", 0)),
                leverage=self.config.get_effective_leverage(),
            )

        return order

    def _compute_dynamic_size(self) -> float | None:
        """APEX-V Phase D: 동적 포지션 사이징 계산.

        Kelly sizer → drawdown sizing → 기본값 순으로 적용.

        Returns:
            동적 포지션 크기 비율 또는 None (기본값 사용).
        """
        dynamic_size_pct: float | None = None

        if self._kelly_sizer:
            regime_str = (
                self._current_regime.value
                if self._current_regime
                else "UNKNOWN"
            )
            config_default = self.config.get_effective_position_size_pct()
            drawdown_pct = self._risk_manager.get_current_drawdown()

            dynamic_size_pct = self._kelly_sizer.calculate_final_size(
                regime=regime_str,
                config_default=config_default,
                drawdown_pct=drawdown_pct,
            )

            # Execution tracker modifier 적용
            if self._execution_tracker:
                exec_mod = self._execution_tracker.get_size_modifier()
                if exec_mod == 0.0:
                    self._log.warning("실행 품질 미달 — 진입 스킵")
                    return 0.0
                dynamic_size_pct *= exec_mod

        elif getattr(self.config, "use_drawdown_sizing", False):
            dd_mult = self._risk_manager.get_drawdown_size_multiplier()
            dynamic_size_pct = self.config.get_effective_position_size_pct() * dd_mult

        return dynamic_size_pct

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
        try:
            order = await self._executor.close_position()
        except RuntimeError as e:
            self._log.critical(
                f"포지션 청산 부분 체결 실패 - PnL 기록 스킵: {e}"
            )
            return None

        if order:
            entry_price = position["entry_price"]
            side = position["side"]

            # Phase 7: 실제 체결가 기반 PnL 계산
            exit_price = current_price  # default fallback
            avg_price_str = order.get("avgPrice")
            if avg_price_str:
                try:
                    exit_price = float(avg_price_str)
                    self._log.info(f"실제 체결가 사용: ${exit_price:,.2f}")
                except (ValueError, TypeError):
                    self._log.warning("체결가 파싱 실패, 현재가 사용")
            else:
                self._log.warning("체결가 없음(avgPrice), 현재가 사용")

            # Sanity check: exit_price vs current_price divergence
            _max_divergence = 0.05
            if (
                current_price > 0
                and abs(exit_price - current_price) / current_price
                > _max_divergence
            ):
                self._log.critical(
                    f"체결가/현재가 괴리 5% 초과: 체결=${exit_price:,.2f} vs "
                    f"현재=${current_price:,.2f}, 현재가로 PnL 계산"
                )
                exit_price = current_price

            # PnL 계산 (exit_price 사용)
            pnl_pct = self._executor.calculate_pnl_pct(entry_price, exit_price, side)
            if side == "LONG":
                pnl_usd = (exit_price - entry_price) * abs(position["position_amt"])
            else:
                pnl_usd = (entry_price - exit_price) * abs(position["position_amt"])

            # Phase 9: 추정 수수료 차감 (진입+청산 왕복)
            _fee_rate = getattr(self.config, "estimated_fee_rate", 0.0008)
            if _fee_rate > 0:
                _fee = abs(position["position_amt"]) * exit_price * _fee_rate * 2
                pnl_usd -= _fee

            # Phase 5 통합: 감사 로그 기록
            if self._audit_log:
                try:
                    await self._audit_log.log_trade_close(
                        self.bot_name, side, exit_reason, pnl_usd, pnl_pct,
                    )
                except Exception as e:
                    self._log.debug(f"청산 감사 로그 기록 실패: {e}")

            # DB에 기록
            exit_closed = True  # Default: track PnL unless DB says already closed
            if self._trade_db and self._executor.current_position:
                executor_position = self._executor.current_position
                if executor_position and executor_position.get("trade_id"):
                    entry_time = executor_position.get("entry_time", datetime.now())
                    duration = int((datetime.now() - entry_time).total_seconds() / 60)
                    try:
                        exit_closed = await self._trade_db.add_exit(
                            trade_id=executor_position["trade_id"],
                            exit_time=datetime.now(),
                            exit_price=exit_price,
                            exit_reason=exit_reason,
                            pnl=pnl_usd,
                            pnl_pct=pnl_pct,
                            duration_minutes=duration,
                        )
                        if not exit_closed:
                            self._log.warning(
                                "이미 청산된 거래 - PnL 이중 추적 방지"
                            )
                    except Exception as exit_db_err:
                        self._log.error(f"청산 기록 DB 저장 실패: {exit_db_err}")
                        if self._redis_state_manager:
                            try:
                                exit_recovery = {
                                    "trade_id": executor_position["trade_id"],
                                    "exit_time": datetime.now().isoformat(),
                                    "exit_price": exit_price,
                                    "exit_reason": exit_reason,
                                    "pnl": pnl_usd,
                                    "pnl_pct": pnl_pct,
                                }
                                await self._redis_state_manager.save_position(
                                    f"{self.bot_name}:recovery:exit", exit_recovery
                                )
                                self._log.warning("Redis에 청산 복구 마커 저장 완료")
                            except Exception as redis_err:
                                self._log.critical(
                                    "DB와 Redis 모두 청산 기록 실패"
                                    f" - 수동 확인 필요: {redis_err}"
                                )

            # Phase 5.2: 리스크 매니저에 PnL 추적 (이미 청산된 거래면 스킵)
            if exit_closed:
                await self._risk_manager.track_trade_pnl(pnl_usd)
                is_win = pnl_usd >= 0
                await self._risk_manager.track_trade_result(is_win)
                # 손실 시 쿨다운 설정
                if not is_win and self._signal_cooldown:
                    await self._signal_cooldown.set_post_loss_cooldown()
            else:
                self._log.info("PnL 추적 스킵 - 이미 청산된 거래")

            # 리스크 한도 체크
            halt, reason = await self._risk_manager.should_halt_trading()
            if halt and not self._risk_halt_notified:
                self._log.warning(f"리스크 한도 도달 - 자동 정지: {reason}")
                self._risk_halt_notified = True
                await self._notify_risk_halt(reason)
                self.pause()

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

            # Phase 9: Clear executor position state after all DB/PnL tracking
            self._executor.clear_position()

            # Phase 2: 분산 노출도 해제
            if self._redis_state_manager:
                await self._redis_state_manager.release_exposure(self.bot_name)

            # 콜백 호출
            await self._notify_trade("CLOSE", side, exit_price, pnl_pct)

            self._log.bind(event_type="TRADE_CLOSE").info(
                f"포지션 청산 완료: {exit_reason}, PnL={pnl_pct:+.2f}%",
                exit_reason=exit_reason,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
            )

            # Phase C: Vitality Tracker에 거래 결과 기록
            if (
                self._ensemble_generator
                and hasattr(self._ensemble_generator, "_confluence_engine")
                and self._ensemble_generator._confluence_engine
            ):
                engine = self._ensemble_generator._confluence_engine
                if hasattr(engine, "_vitality") and engine._vitality:
                    engine._vitality.record_trade(pnl_pct / 100.0)

            # Phase D: Kelly sizer에 거래 결과 기록
            if self._kelly_sizer and exit_closed:
                regime_str = (
                    self._current_regime.value
                    if self._current_regime
                    else "UNKNOWN"
                )
                self._kelly_sizer.record_trade(regime_str, pnl_pct / 100.0)

            # Phase D: Execution tracker에 실행 품질 기록
            if self._execution_tracker and exit_closed:
                slippage = (
                    abs(exit_price - current_price) / current_price
                    if current_price > 0
                    else 0.0
                )
                self._execution_tracker.record_execution(
                    entry_price=entry_price,
                    exit_price=exit_price,
                    side=side,
                    pnl_actual=pnl_usd,
                    pnl_theoretical=pnl_usd,  # 이론적 PnL (실제와 동일로 시작)
                    slippage_pct=slippage,
                )
                # CostCalculator에 보정된 슬리피지 피드백
                if (
                    self._ensemble_generator
                    and hasattr(self._ensemble_generator, "_confluence_engine")
                    and self._ensemble_generator._confluence_engine
                ):
                    eng = self._ensemble_generator._confluence_engine
                    if hasattr(eng, "_cost_calculator") and eng._cost_calculator:
                        cal_slip = (
                            self._execution_tracker
                            .get_calibrated_slippage_factor()
                        )
                        eng._cost_calculator.update_slippage_factor(cal_slip)

                # 전략 일시정지 체크
                if self._execution_tracker.should_pause_strategy():
                    self._log.warning("실행 품질 미달 — 자동 일시정지")
                    self.pause()

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
        # Phase 5 통합: 감사 로그 기록
        if self._audit_log:
            try:
                await self._audit_log.log_risk_halt(self.bot_name, reason)
            except Exception as e:
                self._log.debug(f"리스크 중지 감사 로그 기록 실패: {e}")
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

    async def _check_daily_risk_reset(self) -> None:
        """일일 리스크 리셋 체크 (UTC 자정 경과 시)."""
        # 미실현 PnL 조회 (리셋 시 이월용)
        _unrealized_pnl = 0.0
        if self._executor:
            try:
                _pos = await self._executor.get_position()
                if _pos:
                    _unrealized_pnl = _pos.get("unrealized_pnl", 0.0)
            except Exception as e:
                self._log.debug(f"미실현 PnL 조회 실패: {e}")
        if self._binance_client:
            try:
                balance_info = await self._binance_client.get_account_balance()
                await self._risk_manager.check_and_reset_if_new_day(
                    balance_info["available"], unrealized_pnl=_unrealized_pnl
                )
            except Exception as e:
                self._log.debug(f"일일 리스크 리셋 실패: {e}")

    async def _handle_risk_halt(self) -> bool:
        """리스크 한도 도달 시 기존 포지션 강제 청산.

        Returns:
            True이면 루프 조기 종료 (halt 상태)
        """
        # 미실현 PnL 조회
        _unrealized_pnl = 0.0
        if self._executor:
            try:
                _pos = await self._executor.get_position()
                if _pos:
                    _unrealized_pnl = _pos.get("unrealized_pnl", 0.0)
            except Exception as e:
                self._log.debug(f"미실현 PnL 조회 실패: {e}")
        halt, halt_reason = await self._risk_manager.should_halt_trading(
            _unrealized_pnl
        )
        if not halt:
            return False

        if not self._risk_halt_notified:
            self._log.warning(f"리스크 한도 도달: {halt_reason}")
            self._risk_halt_notified = True
            await self._notify_risk_halt(halt_reason)

        # 기존 포지션 청산 (close_on_risk_halt 설정 확인)
        close_on_halt = getattr(self.config, "close_on_risk_halt", True)
        if close_on_halt and self._executor:
            position = await self._executor.get_position()
            if position:
                self._log.warning("리스크 한도 - 기존 포지션 강제 청산")
                # 주문 먼저 취소 (SL/TP와의 경쟁 조건 방지)
                if self._binance_client:
                    try:
                        await self._binance_client.cancel_all_open_orders(
                            self.symbol
                        )
                        self._log.info("강제 청산 전 주문 취소 완료")
                    except Exception as cancel_err:
                        self._log.warning(
                            f"강제 청산 전 주문 취소 실패: {cancel_err}"
                        )

                    # 주문 취소 후 포지션 재확인 (SL 체결 시 청산 불필요)
                    position = await self._executor.get_position()
                    if not position:
                        self._log.info(
                            "주문 취소 후 포지션 없음 (SL/TP 이미 체결)"
                        )
                        self.pause()
                        return True

                # 현재가 조회를 위해 시장 데이터 필요
                try:
                    if self._binance_client is None:
                        raise RuntimeError('Binance client not initialized')
                    price = await self._binance_client.get_current_price(
                        self.symbol
                    )
                    await self._close_position(price, "RISK_HALT")
                except Exception as e:
                    self._log.error(f"리스크 강제 청산 실패: {e}")

        self.pause()
        return True

    async def _generate_combined_signal(
        self,
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """4-source 시그널 생성 (injected > ensemble > memory > rule_based).

        Returns:
            (signal, signal_source) 튜플
        """
        current_price = market_data["current_price"]

        if self._injected_signal:
            injected = self._injected_signal
            self._injected_signal = None
            signal = injected.get("signal", "WAIT").upper()
            signal_source = f"injected:{injected.get('source', 'external')}"
            self._last_signal = signal
            self._last_signal_time = datetime.now()
            self._log.info(
                f"주입 시그널 사용: {signal} (source={injected.get('source')})"
            )
            return signal, signal_source

        if getattr(self.config, "use_ensemble", False) and self._ensemble_generator:
            _ai_t0 = time.monotonic()
            try:
                result = await self._ensemble_generator.generate_ensemble_signal(
                    market_data.get("indicators", {}),
                    bot_id=str(self.config.bot_id),
                    sentiment_data=sentiment_data,
                    klines_df=self._get_klines_df(market_data),
                )
                signal = result.final_signal
                signal_source = "ensemble"
                self._last_signal = signal
                self._last_signal_time = datetime.now()
                self._log.info(
                    f"앙상블 시그널: {signal} @ ${current_price:,.2f} "
                    f"(합의율={result.consensus_ratio:.1%})"
                )
                # Prometheus: signal_confidence + ai_latency 기록
                if self._metrics:
                    try:
                        self._metrics.record_signal_confidence(
                            self.bot_name, result.consensus_ratio
                        )
                    except Exception as e:
                        self._log.debug(f"시그널 confidence 메트릭 기록 실패: {e}")
                    try:
                        self._metrics.record_ai_latency(
                            self.bot_name, time.monotonic() - _ai_t0
                        )
                    except Exception as e:
                        self._log.debug(f"AI latency 메트릭 기록 실패: {e}")
                return signal, signal_source
            except Exception as e:
                self._log.warning(f"앙상블 시그널 실패, 폴백: {e}")
                signal = self._generate_signal(market_data)
                return signal, "rule_based"

        if self._use_memory_signals and self._enhanced_gemini:
            _ai_t0 = time.monotonic()
            signal = await self._generate_signal_with_memory(market_data)
            signal_source = "memory_gemini"
            self._log.info(f"메모리 시그널: {signal} @ ${current_price:,.2f}")
            if self._metrics:
                try:
                    self._metrics.record_ai_latency(
                        self.bot_name, time.monotonic() - _ai_t0
                    )
                except Exception as e:
                    self._log.debug(f"AI latency 메트릭 기록 실패: {e}")
            return signal, signal_source

        signal = self._generate_signal(market_data)
        self._log.info(f"시그널: {signal} @ ${current_price:,.2f}")
        return signal, "rule_based"

    def _apply_signal_filters(  # noqa: PLR0915
        self, signal: str, indicators: dict[str, Any]
    ) -> str:
        """레짐/MTF/WAIT 필터 적용.

        Returns:
            필터링된 시그널
        """
        # Gate 0: MTI (Market Tradability Index)
        atr_pct = indicators.get("atr_pct", 0.0)
        volume_ratio = indicators.get("volume_ratio", 1.0)
        if atr_pct > 0 and volume_ratio > 0:
            from src.data.tradability import MarketTradabilityIndex
            mti = MarketTradabilityIndex()
            mti_score = mti.evaluate(atr_pct, volume_ratio)
            if not mti_score.is_tradable:
                self._log.info(
                    f"MTI 게이트 차단: {mti_score.total_score:.1f} "
                    f"({mti_score.grade}) — {mti_score.reason}"
                )
                return "WAIT"

        # 레짐 감지 및 필터링
        # Confluence 모드에서는 시그널 생성 전 조기 감지됨 → 스킵
        if not getattr(self.config, "use_confluence_engine", False):
            self._current_regime = self._regime_detector.detect(indicators)

        # Prometheus: RSI 기록 (NaN guard)
        _rsi = indicators.get("rsi")
        if self._metrics and _rsi is not None and not math.isnan(float(_rsi)):
            try:
                self._metrics.record_rsi(self.bot_name, float(_rsi))
            except Exception as e:
                self._log.debug(f"RSI 메트릭 기록 실패: {e}")

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

        # 다중 타임프레임 필터링
        if getattr(self.config, "use_mtf_filter", False) and self._higher_tf_data:
            _mtf_stale = False
            _mtf_max_age_seconds = 900  # 15분
            if self._higher_tf_fetch_time:
                _mtf_age = (datetime.now() - self._higher_tf_fetch_time).total_seconds()
                if _mtf_age > _mtf_max_age_seconds:
                    self._log.warning(
                        f"MTF 데이터 만료 (>{_mtf_age:.0f}초 >15분), 필터 건너뜀"
                    )
                    _mtf_stale = True
            if not _mtf_stale:
                original_signal = signal
                signal = self._mtf_analyzer.filter_signal(signal, self._higher_tf_data)
                if signal != original_signal:
                    self._log.info(
                        f"MTF 필터링: {original_signal} → {signal}"
                    )

        # WAIT streak tracking and diagnostics
        _wait_log_interval = 1  # Every loop (1 x 1hour)
        _wait_alert_threshold = 3  # 3 hours
        if signal == "WAIT":
            self._consecutive_wait_count += 1
            if (
                self._consecutive_wait_count % _wait_log_interval == 0
                and hasattr(self._signal_generator, 'get_signal_diagnostic')
            ):
                diag = self._signal_generator.get_signal_diagnostic(
                    indicators,
                )
                self._log.warning(
                    f"연속 WAIT #{self._consecutive_wait_count}: {diag}"
                )
            if self._consecutive_wait_count >= _wait_alert_threshold:
                cnt = self._consecutive_wait_count
                self._log.warning(
                    f"⚠ {cnt}회 연속 WAIT - 시그널 조건 점검 필요"
                )
            if self._metrics:
                try:
                    self._metrics.record_consecutive_wait(
                        self.bot_name, self._consecutive_wait_count
                    )
                except Exception as e:
                    self._log.debug(f"연속 WAIT 메트릭 기록 실패: {e}")
        else:
            self._consecutive_wait_count = 0
            if self._metrics:
                try:
                    self._metrics.record_consecutive_wait(self.bot_name, 0)
                except Exception as e:
                    self._log.debug(f"연속 WAIT 리셋 메트릭 기록 실패: {e}")

        return signal

    def _track_wait_streak(self, signal: str, indicators: dict[str, Any]) -> None:
        """WAIT streak 추적 및 진단 (5-Gate Pipeline + Legacy 공용)."""
        _wait_log_interval = 1
        _wait_alert_threshold = 3
        if signal == "WAIT":
            self._consecutive_wait_count += 1
            if (
                self._consecutive_wait_count % _wait_log_interval == 0
                and hasattr(self._signal_generator, 'get_signal_diagnostic')
            ):
                diag = self._signal_generator.get_signal_diagnostic(indicators)
                self._log.warning(
                    f"연속 WAIT #{self._consecutive_wait_count}: {diag}"
                )
            if self._consecutive_wait_count >= _wait_alert_threshold:
                self._log.warning(
                    f"\u26a0 {self._consecutive_wait_count}회 연속 WAIT"
                    " - 시그널 조건 점검 필요"
                )
            if self._metrics:
                try:
                    self._metrics.record_consecutive_wait(
                        self.bot_name, self._consecutive_wait_count
                    )
                except Exception as e:
                    self._log.debug(f"연속 WAIT 메트릭 기록 실패: {e}")
        else:
            self._consecutive_wait_count = 0
            if self._metrics:
                try:
                    self._metrics.record_consecutive_wait(self.bot_name, 0)
                except Exception as e:
                    self._log.debug(f"연속 WAIT 리셋 메트릭 기록 실패: {e}")

    async def _run_five_gate_pipeline(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any],
        sentiment_data: dict[str, Any] | None,
    ) -> tuple[str, str]:
        """5-Gate APEX-V Pipeline.

        Gate 0: MTI -> STANDBY = 전체 스킵
        Gate 1: Regime Detection -> 컨텍스트 설정
        Gate 2+3: Signal + Confluence -> ConfluenceResult
        (Gate 4: sizing은 _compute_dynamic_size_with_modifiers에서 처리)

        Returns:
            (signal, signal_source) 튜플
        """
        # Gate 0: MTI (Market Tradability Index)
        atr_pct = indicators.get("atr_pct", 0.0)
        volume_ratio = indicators.get("volume_ratio", 1.0)
        self._last_mti_grade = "OPTIMAL"

        if atr_pct > 0 and volume_ratio > 0:
            from src.data.tradability import MarketTradabilityIndex
            mti = MarketTradabilityIndex()
            mti_score = mti.evaluate(atr_pct, volume_ratio)
            self._last_mti_grade = mti_score.grade
            if self._metrics:
                with contextlib.suppress(Exception):
                    self._metrics.record_gate_outcome(
                        self.bot_name, "mti",
                        "pass" if mti_score.is_tradable else "block",
                    )
            if not mti_score.is_tradable:
                self._log.info(
                    f"[5G] Gate 0 MTI 차단: {mti_score.grade}"
                    f" ({mti_score.total_score:.1f})"
                )
                self._track_wait_streak("WAIT", indicators)
                return "WAIT", "pipeline:mti_block"

        # Gate 1: Regime Detection
        self._current_regime = self._regime_detector.detect(indicators)
        indicators["regime"] = self._current_regime
        indicators["leverage"] = self.config.get_effective_leverage()
        self._log.info(f"[5G] Gate 1 레짐: {self._current_regime.value}")

        # Prometheus: RSI 기록
        _rsi = indicators.get("rsi")
        if self._metrics and _rsi is not None and not math.isnan(float(_rsi)):
            with contextlib.suppress(Exception):
                self._metrics.record_rsi(self.bot_name, float(_rsi))

        # Gate 2+3: Signal + Confluence
        signal, signal_source = await self._generate_combined_signal(
            market_data, sentiment_data=sentiment_data
        )
        if not validate_signal(signal):
            signal = "WAIT"

        # ConfluenceResult 추출
        if (
            self._ensemble_generator
            and hasattr(self._ensemble_generator, "_last_ensemble_result")
            and self._ensemble_generator._last_ensemble_result
        ):
            self._last_ensemble_result = (
                self._ensemble_generator._last_ensemble_result
            )

        # Prometheus: confluence gate
        if self._metrics:
            with contextlib.suppress(Exception):
                self._metrics.record_gate_outcome(
                    self.bot_name, "confluence",
                    "pass" if signal in ("LONG", "SHORT") else "block",
                )

        # Regime direction filter (안전장치)
        if self.config.use_regime_filter and signal in ("LONG", "SHORT"):
            filtered = self._regime_detector.filter_signal(
                signal, self._current_regime, self.config.allow_weak_trend
            )
            if filtered != signal:
                self._log.info(
                    f"[5G] 레짐 방향 필터: {signal} -> {filtered}"
                )
                signal = filtered

        # MTF 필터링
        if getattr(self.config, "use_mtf_filter", False) and self._higher_tf_data:
            _mtf_stale = False
            _mtf_max_age_seconds = 900
            if self._higher_tf_fetch_time:
                _mtf_age = (
                    datetime.now() - self._higher_tf_fetch_time
                ).total_seconds()
                if _mtf_age > _mtf_max_age_seconds:
                    self._log.warning(
                        f"MTF 데이터 만료 (>{_mtf_age:.0f}초), 필터 건너뜀"
                    )
                    _mtf_stale = True
            if not _mtf_stale:
                original_signal = signal
                signal = self._mtf_analyzer.filter_signal(
                    signal, self._higher_tf_data
                )
                if signal != original_signal:
                    self._log.info(
                        f"[5G] MTF 필터링: {original_signal} -> {signal}"
                    )

        # WAIT streak
        self._track_wait_streak(signal, indicators)
        return signal, signal_source

    # 5-Gate sizing thresholds
    _MARGIN_HIGH = 0.15
    _MARGIN_LOW = 0.05

    def _compute_dynamic_size_with_modifiers(self) -> float | None:
        """5-Gate Pipeline 전용: 모든 수정자 적용 동적 사이징."""
        entry_tier = 1.0
        mti_mod = 1.0
        cost_adj = 1.0
        vitality_mod = 1.0

        # MTI grade -> mti_mod
        if getattr(self, "_last_mti_grade", "OPTIMAL") == "REDUCED":
            mti_mod = 0.7

        # ConfluenceResult -> entry_tier, cost_adj, vitality_mod
        cr = getattr(self._last_ensemble_result, "confluence_result", None)
        if cr:
            # entry_tier: threshold 대비 margin
            margin = cr.confluence_score - cr.threshold_used
            if margin > self._MARGIN_HIGH:
                entry_tier = 1.2
            elif margin > self._MARGIN_LOW:
                entry_tier = 1.0
            else:
                entry_tier = 0.8

            # cost_adj: net_edge/score 비율
            if cr.confluence_score > 0:
                cost_ratio = cr.net_edge / cr.confluence_score
                cost_adj = max(0.5, min(1.0, cost_ratio))

            # vitality_mod
            if cr.vitality:
                vmap = {
                    "healthy": 1.0,
                    "caution": 0.85,
                    "warning": 0.65,
                    "critical": 0.4,
                }
                level = cr.vitality.level
                level_str = (
                    level.value.lower()
                    if hasattr(level, "value")
                    else str(level).lower()
                )
                vitality_mod = vmap.get(level_str, 1.0)

        # Kelly 또는 기본값에 수정자 적용
        if self._kelly_sizer:
            regime_str = (
                self._current_regime.value
                if self._current_regime
                else "UNKNOWN"
            )
            dynamic = self._kelly_sizer.calculate_final_size(
                regime=regime_str,
                config_default=self.config.get_effective_position_size_pct(),
                entry_tier=entry_tier,
                mti_mod=mti_mod,
                cost_adj=cost_adj,
                vitality_mod=vitality_mod,
                drawdown_pct=self._risk_manager.get_current_drawdown(),
            )
        else:
            base = self.config.get_effective_position_size_pct()
            if getattr(self.config, "use_drawdown_sizing", False):
                base *= self._risk_manager.get_drawdown_size_multiplier()
            dynamic = base * entry_tier * mti_mod * cost_adj * vitality_mod

        # Execution tracker
        if self._execution_tracker:
            exec_mod = self._execution_tracker.get_size_modifier()
            if exec_mod == 0.0:
                self._log.warning("[5G] 실행 품질 미달 - 진입 스킵")
                return 0.0
            dynamic *= exec_mod

        # Prometheus
        if self._metrics:
            with contextlib.suppress(Exception):
                self._metrics.record_gate_outcome(
                    self.bot_name, "risk_kelly", "pass"
                )

        return dynamic

    async def _record_signal(
        self,
        signal: str,
        signal_source: str,
        current_price: float,
        indicators: dict[str, Any],
    ) -> None:
        """시그널 기록 (SignalTracker + Prometheus + 콜백)."""
        try:
            conditions: dict[str, Any] = {
                "price": current_price,
                "regime": self._current_regime.value,
                "signal_source": signal_source,
            }
            if indicators:
                for k in ("rsi", "atr", "volume_ratio", "ma_7", "ma_25", "ma_99"):
                    if k in indicators:
                        conditions[k] = indicators[k]
            self._last_signal_id = await self._signal_tracker.record_signal(
                bot_id=str(self.config.bot_id),
                signal=signal,
                source=signal_source,
                market_conditions=conditions,
            )
        except Exception as e:
            self._log.warning(f"시그널 기록 실패: {e}")

        # Prometheus: 시그널 메트릭 기록
        if self._metrics:
            try:
                self._metrics.record_signal(self.bot_name, signal, signal_source)
            except Exception as e:
                self._log.debug(f"시그널 메트릭 기록 실패: {e}")

        # 콜백 호출 (알림 중복 제거 적용)
        if self._signal_cooldown and signal in ("LONG", "SHORT"):
            if await self._signal_cooldown.should_send_alert(signal):
                await self._notify_signal(signal, current_price)
                await self._signal_cooldown.mark_alert_sent(signal)
        else:
            await self._notify_signal(signal, current_price)

    async def _handle_emergency_close(self, current_price: float) -> bool:
        """긴급 청산 처리.

        Returns:
            True이면 긴급 청산 수행됨 (루프 조기 종료)
        """
        if not self._emergency_event.is_set():
            return False

        self._log.warning("긴급 청산 실행")
        if self._audit_log:
            try:
                await self._audit_log.log_emergency_close(
                    self.bot_name, "수동 긴급 청산 요청"
                )
            except Exception as e:
                self._log.debug(f"긴급 청산 감사 로그 기록 실패: {e}")
        await self._close_position(current_price, "MANUAL")
        self._emergency_event.clear()
        self._is_paused = True
        return True

    async def _detect_exchange_position_close(  # noqa: PLR0915
        self, current_price: float
    ) -> bool:
        """거래소 측 포지션 종료 감지 (SL/TP 체결).

        Returns:
            True이면 거래소 측 종료 감지됨 (루프 조기 종료)
        """
        if not (self._executor and isinstance(self._executor.current_position, dict)):
            return False

        exchange_pos = await self._executor.get_position()
        if exchange_pos is not None:
            return False

        # 봇은 포지션을 추적 중이나 거래소에 없음 → SL/TP 체결
        tracked = self._executor.current_position
        side = tracked.get("side", "LONG")
        entry_price = tracked.get("entry_price", 0.0)
        position_amt = abs(tracked.get("position_amt", 0.0))

        self._log.warning(
            f"거래소 측 포지션 종료 감지: {side} @ "
        )

        # PnL 추정 (현재가 기준)
        pnl_pct = self._executor.calculate_pnl_pct(
            entry_price, current_price, side
        )
        if side == "LONG":
            pnl_usd = (current_price - entry_price) * position_amt
        else:
            pnl_usd = (entry_price - current_price) * position_amt
        # position_amt는 거래소에서 이미 레버리지 적용된 값 - 이중 곱셈 금지

        # 추정 수수료 차감 (진입+청산 왕복) - _close_position과 동일 로직
        _fee_rate = getattr(self.config, "estimated_fee_rate", 0.0008)
        if _fee_rate > 0:
            _fee = position_amt * current_price * _fee_rate * 2
            pnl_usd -= _fee

        # DB에 기록
        if self._trade_db and tracked.get("trade_id"):
            entry_time = tracked.get("entry_time", datetime.now())
            duration = int(
                (datetime.now() - entry_time).total_seconds() / 60
            )
            try:
                exit_closed = await self._trade_db.add_exit(
                    trade_id=tracked["trade_id"],
                    exit_time=datetime.now(),
                    exit_price=current_price,
                    exit_reason="EXCHANGE_SL_TP",
                    pnl=pnl_usd,
                    pnl_pct=pnl_pct,
                    duration_minutes=duration,
                )
                if not exit_closed:
                    self._log.warning(
                        "이미 청산된 거래 - PnL 이중 추적 방지"
                    )
            except Exception as db_err:
                self._log.error(
                    f"거래소 측 종료 DB 기록 실패: {db_err}"
                )
                exit_closed = True  # DB 실패해도 리스크 매니저에는 기록

            # 리스크 매니저에 PnL 추적
            if exit_closed:
                await self._risk_manager.track_trade_pnl(pnl_usd)
                is_win = pnl_usd >= 0
                await self._risk_manager.track_trade_result(is_win)
                if not is_win and self._signal_cooldown:
                    await self._signal_cooldown.set_post_loss_cooldown()
        else:
            # trade_id 없으면 리스크 매니저에만 기록
            await self._risk_manager.track_trade_pnl(pnl_usd)
            is_win = pnl_usd >= 0
            await self._risk_manager.track_trade_result(is_win)
            if not is_win and self._signal_cooldown:
                await self._signal_cooldown.set_post_loss_cooldown()

        self._log.bind(event_type="TRADE_CLOSE").info(
            f"거래소 측 포지션 종료: {side}, PnL={pnl_pct:+.2f}%",
            exit_reason="EXCHANGE_SL_TP",
            side=side,
            entry_price=entry_price,
            exit_price=current_price,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
        )

        # 포지션 정리
        self._executor.clear_position()
        self._current_position = None

        # Phase 2: 분산 노출도 해제
        if self._redis_state_manager:
            await self._redis_state_manager.release_exposure(self.bot_name)

        # Prometheus 메트릭
        if self._metrics:
            try:
                result_str = "win" if pnl_usd >= 0 else "loss"
                entry_time = tracked.get("entry_time")
                duration_s = (
                    (datetime.now() - entry_time).total_seconds()
                    if entry_time else 0.0
                )
                self._metrics.record_trade(
                    self.bot_name, side, result_str, duration_s
                )
                self._metrics.clear_position_metrics(self.bot_name)
            except Exception as e:
                self._log.debug(f"거래소 측 종료 메트릭 기록 실패: {e}")
        return True

    async def _handle_existing_position(
        self, position: dict[str, Any], current_price: float
    ) -> bool:
        """기존 포지션 관리 (PnL 추적, Timecut, TP/SL 체크).

        Returns:
            True이면 포지션 청산됨 (루프 조기 종료)
        """
        if self._executor is None:
            return False

        self._log.debug(
            f"현재 포지션: {position['side']} @ ${position['entry_price']:,.2f}"
        )

        # Prometheus 포지션 PnL 기록
        if self._metrics and self._executor:
            try:
                pos_pnl_pct = self._executor.calculate_pnl_pct(
                    position["entry_price"], current_price, position["side"]
                )
                self._metrics.record_position_pnl(self.bot_name, pos_pnl_pct)
            except Exception as e:
                self._log.debug(f"포지션 PnL 메트릭 기록 실패: {e}")

        # Timecut 체크
        if (
            self._executor.current_position
            and self._executor.check_timecut(self._executor.current_position)
        ):
                self._log.info("Timecut 조건 충족")
                await self._close_position(current_price, "TIME_CUT")
                return True

        # TP/SL 체크 (ATR 기반 동적 TP/SL 지원)
        exit_reason = await self._executor.check_tp_sl_dynamic(
            position, current_price
        )
        if exit_reason:
            self._log.info(f"종료 조건 충족: {exit_reason}")
            await self._close_position(current_price, exit_reason)
            return True

        return False

    async def _attempt_new_entry(  # noqa: PLR0911, PLR0915
        self,
        signal: str,
        current_price: float,
        has_position: bool,
    ) -> None:
        """신규 포지션 진입 시도."""
        if self._is_paused:
            self._log.debug("봇 일시정지 중 - 진입 스킵")
            return

        # 리스크 체크 (쿨다운, 일일 손실 한도)
        _unrealized_pnl = 0.0
        if self._current_position:
            _unrealized_pnl = self._current_position.get("unrealized_pnl", 0.0)

        should_skip, skip_reason = await self._risk_manager.should_skip_trade(
            _unrealized_pnl
        )
        if should_skip:
            self._log.info(f"리스크 제한으로 진입 스킵: {skip_reason}")
            return

        # 시그널 쿨다운 체크
        if self._signal_cooldown and signal in ("LONG", "SHORT"):
            if await self._signal_cooldown.is_signal_on_cooldown(signal):
                self._log.info(f"시그널 쿨다운 중 - 진입 스킵: {signal}")
                return
            if await self._signal_cooldown.is_post_loss_cooldown_active():
                self._log.info("손실 후 쿨다운 중 - 진입 스킵")
                return

        # 수동 승인 체크 (비차단)
        if self._trade_approval and signal in ("LONG", "SHORT"):
            # 대기 중인 승인 요청이 있는지 확인
            if self._pending_approval_request:
                from src.trading.trade_approval import ApprovalStatus
                req = self._pending_approval_request
                if req.status == ApprovalStatus.APPROVED:
                    # Validate signal consistency
                    if (
                        hasattr(req, 'validate_signal_consistency')
                        and not req.validate_signal_consistency(signal)
                    ):
                        self._log.warning(
                            f"시그널 변경 감지: 승인 시 "
                            f"{req.original_signal} → 현재 "
                            f"{signal}, 진입 스킵"
                        )
                        self._pending_approval_request = None
                        return
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

        # 노출도 체크
        if self._on_exposure_check and signal in ("LONG", "SHORT"):
            try:
                pct = self.config.get_effective_position_size_pct()
                leverage = self.config.get_effective_leverage()
                position_value = current_price * pct * leverage
                can_open, reason = await self._on_exposure_check(
                    self.bot_name, position_value
                )
                if not can_open:
                    self._log.info(f"노출도 한도 초과 - 진입 스킵: {reason}")
                    return
            except Exception as e:
                self._log.warning(f"노출도 체크 실패: {e}")

        if should_enter_trade(signal, has_position):
            entry_atr = None
            if self._market_data:
                entry_atr = self._market_data.get("atr")
            self._log.info(
                f"{signal} 포지션 진입..."
                + (f" (ATR={entry_atr:.2f})" if entry_atr else "")
            )
            await self._open_position(signal, current_price, entry_atr)

    async def _check_redis_commands(self) -> None:
        """Redis 명령 큐에서 명령 확인 및 실행."""
        if self._redis_state_manager is None:
            return

        while True:
            command = await self._redis_state_manager.pop_command(self.bot_name)
            if command is None:
                break

            action = command.get("action", "").upper()
            self._log.info(f"Redis 명령 수신: {action}")

            if action == "PAUSE":
                self.pause()
            elif action == "RESUME":
                self.resume()
                self._risk_halt_notified = False
            elif action == "EMERGENCY_CLOSE":
                self.request_emergency_close()
            elif action == "STOP":
                await self.stop()
            else:
                self._log.warning(f"알 수 없는 Redis 명령: {action}")

    async def _execute_single_loop(self) -> None:
        """단일 트레이딩 루프 실행."""
        # Phase 1: Redis 명령 큐 확인
        await self._check_redis_commands()

        self._loop_count += 1
        self._log.info(f"루프 #{self._loop_count} 시작")

        # 0. 일일 리스크 리셋 체크
        await self._check_daily_risk_reset()

        # 1. 리스크 한도 체크 및 강제 청산
        if await self._handle_risk_halt():
            return

        # 2. 시장 데이터 수집
        market_data = await self._fetch_market_data()
        current_price = market_data["current_price"]

        # 잔고 업데이트 (드로다운 추적)
        if self._binance_client:
            try:
                balance_info = await self._binance_client.get_account_balance()
                await self._risk_manager.update_balance(balance_info["available"])

                # 계좌 메트릭 기록
                if self._metrics:
                    self._metrics.record_account_balance(
                        self.bot_name, balance_info["balance"]
                    )
                    self._metrics.record_available_balance(
                        self.bot_name, balance_info["available"]
                    )
                    self._metrics.record_unrealized_pnl(
                        self.bot_name, balance_info.get("unrealized_pnl", 0.0)
                    )
                    stats = self._risk_manager.get_stats()
                    self._metrics.record_daily_pnl(
                        self.bot_name, stats["daily_pnl"]
                    )
                    self._metrics.record_daily_pnl_pct(
                        self.bot_name, stats["daily_pnl_pct"]
                    )
                    self._metrics.record_drawdown_pct(
                        self.bot_name, stats["current_drawdown"]
                    )
                    self._metrics.record_win_rate(
                        self.bot_name, stats["win_rate"]
                    )
            except Exception as e:
                self._log.debug(f"잔고 업데이트 실패: {e}")

        # Phase B: 심리 데이터 수집
        sentiment_data = await self._fetch_sentiment_data()

        indicators = market_data.get("indicators", {})

        if getattr(self.config, "use_confluence_engine", False):
            # === 5-Gate Pipeline ===
            signal, signal_source = await self._run_five_gate_pipeline(
                market_data, indicators, sentiment_data
            )
            # Pipeline 사이징 사전 계산
            if signal in ("LONG", "SHORT"):
                self._pipeline_size_pct = (
                    self._compute_dynamic_size_with_modifiers()
                )
            else:
                self._pipeline_size_pct = None
        else:
            # === Legacy Flow ===
            self._pipeline_size_pct = None
            # 시그널 생성
            signal, signal_source = await self._generate_combined_signal(
                market_data, sentiment_data=sentiment_data
            )
            # 시그널 유효성 검증
            if not validate_signal(signal):
                self._log.warning(
                    f"유효하지 않은 시그널 '{signal}', WAIT으로 변경"
                )
                signal = "WAIT"
                self._last_signal = signal
            # 필터 적용 (레짐/MTF/WAIT)
            signal = self._apply_signal_filters(signal, indicators)

        # 시그널 기록
        await self._record_signal(signal, signal_source, current_price, indicators)

        # 6. 긴급 청산 확인
        if await self._handle_emergency_close(current_price):
            return

        # 7. 거래소 측 포지션 종료 감지 (SL/TP 체결)
        if await self._detect_exchange_position_close(current_price):
            return

        # 8. 현재 포지션 확인 및 관리
        if self._executor is None:
            return

        position = await self._executor.get_position()
        has_position = position is not None
        self._current_position = position

        if (
            has_position
            and position is not None
            and await self._handle_existing_position(position, current_price)
        ):
            return

        # 9. 신규 포지션 진입
        await self._attempt_new_entry(signal, current_price, has_position)


    async def _run_loop(self) -> None:
        """메인 트레이딩 루프."""
        self._is_running = True
        self._uptime_start = datetime.now()
        self._consecutive_errors = 0
        self._log.info("트레이딩 루프 시작")

        while self._is_running:
            if self._is_paused:
                await asyncio.sleep(1)
                continue

            loop_start = time.monotonic()
            try:
                loop_timeout = max(self._loop_interval_seconds - 20, 60)
                timed_out = False
                try:
                    await asyncio.wait_for(
                        self._execute_single_loop(),
                        timeout=loop_timeout,
                    )
                except asyncio.TimeoutError:
                    timed_out = True
                    self._consecutive_errors += 1
                    self._log.critical(
                        f"트레이딩 루프 타임아웃 ({loop_timeout}초) - "
                        "API 응답 지연 또는 무한 대기 가능성 "
                        f"({self._consecutive_errors}/{self._max_consecutive_errors})"
                    )

                if not timed_out:
                    # 성공 시에만 연속 에러 카운터 리셋
                    self._consecutive_errors = 0
                    # Redis 상태 동기화
                    await self._sync_state_to_redis()

            except Exception as e:
                self._consecutive_errors += 1
                self._log.error(
                    f"루프 에러 "
                    f"({self._consecutive_errors}/{self._max_consecutive_errors}): {e}",
                    exc_info=True,
                )
                await self._notify_error(e)

                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._is_paused = True
                    self._log.critical(
                        f"연속 {self._consecutive_errors}회 "
                        "에러 발생 - 봇 자동 일시정지. "
                        "수동 확인 후 resume 명령으로 재개하세요."
                    )
            finally:
                # 루프 타이밍 기록
                self._last_loop_duration = time.monotonic() - loop_start
                self._last_loop_time = datetime.now()
                if self._metrics:
                    try:
                        self._metrics.record_loop_duration(
                            self.bot_name, self._last_loop_duration
                        )
                    except Exception as e:
                        self._log.debug(f"루프 지속시간 메트릭 기록 실패: {e}")

            # 다음 루프까지 대기 (긴급 이벤트 시 즉시 깨어남)
            if not self._emergency_event.is_set():
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        self._emergency_event.wait(),
                        timeout=self._loop_interval_seconds,
                    )
            self._emergency_event.clear()

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
