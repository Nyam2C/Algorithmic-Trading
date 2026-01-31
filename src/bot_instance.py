"""
개별 봇 인스턴스 모듈

각 봇의 트레이딩 루프 로직을 캡슐화한 BotInstance 클래스.
기존 main.py의 trading_loop 로직을 분리하여 멀티봇 실행 지원.

Phase 4: AI 메모리 시스템 통합
- EnhancedGeminiSignalGenerator 지원
- 과거 거래 분석 기반 시그널 생성
"""
import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable, Any, Union
from loguru import logger

from src.bot_config import BotConfig
from src.exchange.binance import BinanceTestnetClient
from src.data.indicators import analyze_market
from src.ai.rule_based import RuleBasedSignalGenerator
from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator
from src.ai.signals import validate_signal, should_enter_trade
from src.trading.executor import TradingExecutor
from src.storage.trade_history import TradeHistoryDB
from src.storage.redis_state import RedisStateManager, DummyRedisStateManager
from src.analytics.trade_analyzer import TradeHistoryAnalyzer
from src.analytics.memory_context import AIMemoryContextBuilder


# 콜백 타입 정의
OnSignalCallback = Callable[[str, str, float], Awaitable[None]]
OnTradeCallback = Callable[[str, str, str, float, Optional[float]], Awaitable[None]]
OnErrorCallback = Callable[[str, Exception], Awaitable[None]]


class BotInstance:
    """개별 봇 인스턴스

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
        database_url: Optional[str] = None,
        loop_interval_seconds: int = 300,
        # 의존성 주입 (테스트용)
        binance_client: Optional[BinanceTestnetClient] = None,
        trade_db: Optional[TradeHistoryDB] = None,
        redis_state_manager: Optional[Union[RedisStateManager, DummyRedisStateManager]] = None,
        # Phase 4: AI 메모리 시스템
        enhanced_gemini: Optional[EnhancedGeminiSignalGenerator] = None,
        use_memory_signals: bool = False,
        # 콜백 함수
        on_signal_callback: Optional[OnSignalCallback] = None,
        on_trade_callback: Optional[OnTradeCallback] = None,
        on_error_callback: Optional[OnErrorCallback] = None,
    ) -> None:
        """봇 인스턴스 초기화

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
        self._uptime_start: Optional[datetime] = None
        self._loop_count = 0

        # 현재 데이터
        self._current_price: float = 0.0
        self._last_signal: str = "WAIT"
        self._last_signal_time: Optional[datetime] = None
        self._current_position: Optional[dict] = None
        self._market_data: Optional[dict] = None

        # 의존성
        self._binance_client = binance_client
        self._trade_db = trade_db
        self._redis_state_manager = redis_state_manager
        self._executor: Optional[TradingExecutor] = None

        # 시그널 생성기 (커스텀 RSI 파라미터 적용)
        self._signal_generator = RuleBasedSignalGenerator(
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            volume_threshold=config.volume_threshold,
        )

        # Phase 4: AI 메모리 시스템
        self._enhanced_gemini = enhanced_gemini
        self._use_memory_signals = use_memory_signals
        self._memory_context_builder: Optional[AIMemoryContextBuilder] = None

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
        """봇 이름"""
        return self.config.bot_name

    @property
    def symbol(self) -> str:
        """거래 심볼"""
        return self.config.symbol

    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """일시정지 여부"""
        return self._is_paused

    # =========================================================================
    # 상태 관리
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """현재 봇 상태 반환

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
        }

    def pause(self) -> None:
        """봇 일시정지"""
        self._is_paused = True
        self._log.info("봇 일시정지됨")

    def resume(self) -> None:
        """봇 재개"""
        self._is_paused = False
        self._log.info("봇 재개됨")

    def request_emergency_close(self) -> None:
        """긴급 포지션 청산 요청"""
        self._emergency_close = True
        self._log.warning("긴급 청산 요청됨")

    # =========================================================================
    # Phase 4: AI 메모리 시스템
    # =========================================================================

    @property
    def memory_signals_enabled(self) -> bool:
        """메모리 기반 시그널 활성화 여부"""
        return self._use_memory_signals and self._enhanced_gemini is not None

    def enable_memory_signals(self) -> bool:
        """메모리 기반 시그널 활성화

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
        """메모리 기반 시그널 비활성화"""
        self._use_memory_signals = False
        self._log.info("메모리 기반 시그널 비활성화됨")

    def set_enhanced_gemini(
        self,
        gemini: EnhancedGeminiSignalGenerator,
    ) -> None:
        """EnhancedGeminiSignalGenerator 설정

        Args:
            gemini: EnhancedGeminiSignalGenerator 인스턴스
        """
        self._enhanced_gemini = gemini
        self._log.info("EnhancedGemini 설정 완료")

    # =========================================================================
    # Redis 상태 관리
    # =========================================================================

    async def _sync_state_to_redis(self) -> None:
        """현재 상태를 Redis에 동기화"""
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
        """Redis에서 상태 복구

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
            saved_position = await self._redis_state_manager.load_position(self.bot_name)
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
        """Redis 상태 관리자 설정

        Args:
            manager: Redis 상태 관리자
        """
        self._redis_state_manager = manager

    # =========================================================================
    # 초기화
    # =========================================================================

    async def _initialize(self) -> None:
        """봇 초기화 (클라이언트 및 DB 연결)"""
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

        self._log.info("봇 초기화 완료")

    async def _cleanup(self) -> None:
        """봇 정리 (연결 해제)"""
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
        """시장 데이터 수집

        Returns:
            시장 데이터 딕셔너리
        """
        if self._binance_client is None:
            raise RuntimeError("Binance client not initialized")

        # 현재 가격
        current_price = await self._binance_client.get_current_price(self.symbol)

        # Klines (캔들스틱)
        klines = await self._binance_client.get_klines(self.symbol, limit=24)

        # 24시간 티커
        ticker_24h = await self._binance_client.get_ticker_24h(self.symbol)

        # 지표 계산
        indicators = analyze_market(klines, ticker_24h, current_price)

        self._current_price = current_price
        self._market_data = indicators

        return {
            "current_price": current_price,
            "klines": klines,
            "ticker_24h": ticker_24h,
            "indicators": indicators,
        }

    # =========================================================================
    # 시그널 생성
    # =========================================================================

    def _generate_signal(self, market_data: dict[str, Any]) -> str:
        """시그널 생성 (규칙 기반)

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
        """메모리 기반 시그널 생성 (Phase 4)

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

    async def _open_position(self, signal: str, current_price: float) -> Optional[dict]:
        """포지션 오픈

        Args:
            signal: 시그널 ("LONG" or "SHORT")
            current_price: 현재 가격

        Returns:
            주문 결과 또는 None
        """
        if self._executor is None:
            raise RuntimeError("Executor not initialized")

        order = await self._executor.open_position(signal, current_price)

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

    async def _close_position(
        self,
        current_price: float,
        exit_reason: str,
    ) -> Optional[dict]:
        """포지션 클로즈

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
            pnl_usd = (current_price - entry_price) * position["position_amt"]
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
        """시그널 콜백 호출"""
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
        pnl: Optional[float],
    ) -> None:
        """거래 콜백 호출"""
        if self._on_trade_callback:
            try:
                await self._on_trade_callback(self.bot_name, action, side, price, pnl)
            except Exception as e:
                self._log.error(f"거래 콜백 에러: {e}")

    async def _notify_error(self, error: Exception) -> None:
        """에러 콜백 호출"""
        if self._on_error_callback:
            try:
                await self._on_error_callback(self.bot_name, error)
            except Exception as e:
                self._log.error(f"에러 콜백 에러: {e}")

    # =========================================================================
    # 트레이딩 루프
    # =========================================================================

    async def _execute_single_loop(self) -> None:
        """단일 트레이딩 루프 실행"""
        self._loop_count += 1
        self._log.info(f"루프 #{self._loop_count} 시작")

        # 1. 시장 데이터 수집
        market_data = await self._fetch_market_data()
        current_price = market_data["current_price"]

        # 2. 시그널 생성 (Phase 4: 메모리 기반 또는 규칙 기반)
        if self._use_memory_signals and self._enhanced_gemini:
            signal = await self._generate_signal_with_memory(market_data)
            self._log.info(f"메모리 시그널: {signal} @ ${current_price:,.2f}")
        else:
            signal = self._generate_signal(market_data)
            self._log.info(f"시그널: {signal} @ ${current_price:,.2f}")

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

            # Timecut 체크
            if self._executor.current_position:
                if self._executor.check_timecut(self._executor.current_position):
                    self._log.info("Timecut 조건 충족")
                    await self._close_position(current_price, "TIME_CUT")
                    return

            # TP/SL 체크
            exit_reason = await self._executor.check_tp_sl(position, current_price)
            if exit_reason:
                self._log.info(f"종료 조건 충족: {exit_reason}")
                await self._close_position(current_price, exit_reason)
                return

        # 5. 신규 포지션 진입
        if self._is_paused:
            self._log.debug("봇 일시정지 중 - 진입 스킵")
            return

        if should_enter_trade(signal, has_position):
            self._log.info(f"{signal} 포지션 진입...")
            await self._open_position(signal, current_price)

    async def _run_loop(self) -> None:
        """메인 트레이딩 루프"""
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
        """봇 시작"""
        self._log.info("봇 시작 중...")

        try:
            await self._initialize()
            await self._run_loop()
        except asyncio.CancelledError:
            self._log.info("봇 태스크 취소됨")
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """봇 정지"""
        self._log.info("봇 정지 요청")
        self._is_running = False
