"""
멀티봇 관리자 모듈

여러 BotInstance를 생성, 시작, 중지, 모니터링하는 MultiBotManager 클래스.

Phase 5.4: 멀티봇 총 노출도 제한
"""
import asyncio
from typing import Optional, Any, Union, Tuple
from loguru import logger

from src.bot_config import BotConfig
from src.bot_instance import BotInstance, OnSignalCallback, OnTradeCallback, OnErrorCallback
from src.storage.redis_state import RedisStateManager, DummyRedisStateManager


class MultiBotManager:
    """멀티봇 관리자

    여러 BotInstance를 관리하고 조율하는 클래스입니다.
    각 봇의 생명주기(시작, 중지, 일시정지)를 관리하고,
    전체 봇의 상태를 모니터링합니다.

    Attributes:
        bots: 등록된 봇 인스턴스 딕셔너리 (bot_name -> BotInstance)
        bot_count: 등록된 봇 수
        running_count: 실행 중인 봇 수

    Example:
        >>> manager = MultiBotManager(api_key, api_secret)
        >>> manager.add_bot(BotConfig(bot_name="btc-bot", symbol="BTCUSDT"))
        >>> await manager.start_all()
    """

    def __init__(
        self,
        binance_api_key: str,
        binance_secret_key: str,
        gemini_api_key: str = "",
        discord_webhook_url: str = "",
        database_url: Optional[str] = None,
        loop_interval_seconds: int = 300,
        configs: Optional[list[BotConfig]] = None,
        redis_state_manager: Optional[Union[RedisStateManager, DummyRedisStateManager]] = None,
        # Phase 5.4: 총 노출도 제한
        max_total_exposure: float = 0.0,  # 0 = 제한 없음
    ) -> None:
        """멀티봇 관리자 초기화

        Args:
            binance_api_key: Binance API 키
            binance_secret_key: Binance Secret 키
            gemini_api_key: Gemini API 키
            discord_webhook_url: Discord 웹훅 URL
            database_url: PostgreSQL 데이터베이스 URL
            loop_interval_seconds: 루프 간격 (초)
            configs: 초기 봇 설정 리스트
            redis_state_manager: Redis 상태 관리자
            max_total_exposure: 최대 총 노출도 (USDT). 0이면 제한 없음.
        """
        self._binance_api_key = binance_api_key
        self._binance_secret_key = binance_secret_key
        self._gemini_api_key = gemini_api_key
        self._discord_webhook_url = discord_webhook_url
        self._database_url = database_url
        self._loop_interval_seconds = loop_interval_seconds
        self._redis_state_manager = redis_state_manager

        # Phase 5.4: 총 노출도 제한
        self._max_total_exposure = max_total_exposure

        # 봇 인스턴스 저장
        self._bots: dict[str, BotInstance] = {}

        # 봇 태스크 저장
        self._tasks: dict[str, asyncio.Task] = {}

        # 글로벌 콜백
        self._on_signal_callback: Optional[OnSignalCallback] = None
        self._on_trade_callback: Optional[OnTradeCallback] = None
        self._on_error_callback: Optional[OnErrorCallback] = None

        # 초기 봇 설정 등록
        if configs:
            for config in configs:
                if config.is_active:
                    self.add_bot(config)

        logger.info(
            f"MultiBotManager 초기화 완료: {len(self._bots)}개 봇 등록, "
            f"max_exposure=${max_total_exposure:,.2f}" if max_total_exposure > 0 else
            f"MultiBotManager 초기화 완료: {len(self._bots)}개 봇 등록 (노출도 제한 없음)"
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def bots(self) -> dict[str, BotInstance]:
        """등록된 봇 인스턴스 딕셔너리"""
        return self._bots

    @property
    def bot_count(self) -> int:
        """등록된 봇 수"""
        return len(self._bots)

    @property
    def running_count(self) -> int:
        """실행 중인 봇 수"""
        return sum(1 for bot in self._bots.values() if bot.is_running)

    @property
    def paused_count(self) -> int:
        """일시정지된 봇 수"""
        return sum(1 for bot in self._bots.values() if bot.is_paused)

    @property
    def redis_state_manager(
        self,
    ) -> Optional[Union[RedisStateManager, DummyRedisStateManager]]:
        """Redis 상태 관리자"""
        return self._redis_state_manager

    @property
    def max_total_exposure(self) -> float:
        """최대 총 노출도 (Phase 5.4)"""
        return self._max_total_exposure

    def set_max_total_exposure(self, value: float) -> None:
        """최대 총 노출도 설정 (Phase 5.4)"""
        self._max_total_exposure = value
        logger.info(f"최대 총 노출도 설정: ${value:,.2f}")

    # =========================================================================
    # Phase 5.4: 총 노출도 관리
    # =========================================================================

    async def get_total_exposure(self) -> float:
        """모든 봇의 총 포지션 가치 계산

        Returns:
            총 노출도 (USDT)
        """
        total = 0.0

        for bot in self._bots.values():
            state = bot.get_state()
            position = state.get("position")

            if position:
                # 포지션 가치 계산: quantity * entry_price * leverage
                quantity = abs(position.get("position_amt", 0))
                entry_price = position.get("entry_price", 0)
                leverage = state.get("leverage", 1)

                position_value = quantity * entry_price * leverage
                total += position_value

                logger.debug(
                    f"[{bot.bot_name}] 포지션 노출도: "
                    f"{quantity} x ${entry_price:,.2f} x {leverage}x = ${position_value:,.2f}"
                )

        return total

    async def can_open_position(
        self, bot_name: str, position_value: float
    ) -> Tuple[bool, str]:
        """새 포지션 진입 가능 여부 확인 (Phase 5.4)

        Args:
            bot_name: 봇 이름
            position_value: 새 포지션 가치 (USDT)

        Returns:
            (가능 여부, 사유)
        """
        # 노출도 제한이 없으면 항상 허용
        if self._max_total_exposure <= 0:
            return True, ""

        current_exposure = await self.get_total_exposure()
        new_total = current_exposure + position_value

        if new_total > self._max_total_exposure:
            reason = (
                f"총 노출도 한도 초과: ${new_total:,.2f} > ${self._max_total_exposure:,.2f} "
                f"(현재=${current_exposure:,.2f}, 신규=${position_value:,.2f})"
            )
            logger.warning(f"[{bot_name}] {reason}")
            return False, reason

        logger.info(
            f"[{bot_name}] 포지션 진입 허용: "
            f"총 노출도 ${new_total:,.2f} / ${self._max_total_exposure:,.2f}"
        )
        return True, ""

    def get_exposure_summary(self) -> dict[str, Any]:
        """노출도 요약 정보 (Phase 5.4)

        Returns:
            노출도 요약 딕셔너리
        """
        import asyncio

        # 비동기 함수를 동기적으로 호출
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 이미 이벤트 루프가 실행 중이면 현재 캐시된 상태 사용
            total = 0.0
            for bot in self._bots.values():
                state = bot.get_state()
                position = state.get("position")
                if position:
                    quantity = abs(position.get("position_amt", 0))
                    entry_price = position.get("entry_price", 0)
                    leverage = state.get("leverage", 1)
                    total += quantity * entry_price * leverage
        else:
            # 이벤트 루프가 없으면 새로 실행
            total = asyncio.run(self.get_total_exposure())

        return {
            "current_exposure": total,
            "max_exposure": self._max_total_exposure,
            "available_exposure": max(0, self._max_total_exposure - total) if self._max_total_exposure > 0 else float("inf"),
            "utilization_pct": (total / self._max_total_exposure * 100) if self._max_total_exposure > 0 else 0,
            "limit_enabled": self._max_total_exposure > 0,
        }

    # =========================================================================
    # Redis 상태 관리
    # =========================================================================

    def set_redis_state_manager(
        self, manager: Union[RedisStateManager, DummyRedisStateManager]
    ) -> None:
        """Redis 상태 관리자 설정

        Args:
            manager: Redis 상태 관리자
        """
        self._redis_state_manager = manager
        # 기존 봇에도 적용
        for bot in self._bots.values():
            bot.set_redis_state_manager(manager)
        logger.info("Redis 상태 관리자 설정됨")

    async def restore_bots_from_redis(self) -> list[str]:
        """Redis에서 등록된 봇 목록 복구

        Returns:
            복구된 봇 이름 리스트
        """
        if self._redis_state_manager is None:
            logger.warning("Redis 상태 관리자 없음 - 복구 스킵")
            return []

        try:
            # 서버 시작 시 running 상태 초기화
            await self._redis_state_manager.clear_running_bots()

            # 등록된 봇 목록 조회
            registered_bots = await self._redis_state_manager.get_registered_bots()
            logger.info(f"Redis에서 {len(registered_bots)}개 봇 발견")

            return registered_bots

        except Exception as e:
            logger.error(f"Redis 봇 복구 실패: {e}")
            return []

    async def get_redis_bot_states(self) -> dict[str, dict[str, Any]]:
        """Redis에 저장된 모든 봇 상태 조회

        Returns:
            봇 이름 -> 상태 딕셔너리
        """
        if self._redis_state_manager is None:
            return {}

        result = {}
        try:
            registered_bots = await self._redis_state_manager.get_registered_bots()
            for bot_name in registered_bots:
                state = await self._redis_state_manager.load_bot_state(bot_name)
                if state:
                    result[bot_name] = state
            return result
        except Exception as e:
            logger.error(f"Redis 봇 상태 조회 실패: {e}")
            return {}

    # =========================================================================
    # 콜백 설정
    # =========================================================================

    def set_on_signal_callback(self, callback: OnSignalCallback) -> None:
        """전체 봇에 적용될 시그널 콜백 설정"""
        self._on_signal_callback = callback
        # 기존 봇에도 적용
        for bot in self._bots.values():
            bot._on_signal_callback = callback
        logger.debug("글로벌 시그널 콜백 설정됨")

    def set_on_trade_callback(self, callback: OnTradeCallback) -> None:
        """전체 봇에 적용될 거래 콜백 설정"""
        self._on_trade_callback = callback
        for bot in self._bots.values():
            bot._on_trade_callback = callback
        logger.debug("글로벌 거래 콜백 설정됨")

    def set_on_error_callback(self, callback: OnErrorCallback) -> None:
        """전체 봇에 적용될 에러 콜백 설정"""
        self._on_error_callback = callback
        for bot in self._bots.values():
            bot._on_error_callback = callback
        logger.debug("글로벌 에러 콜백 설정됨")

    # =========================================================================
    # 봇 등록/해제
    # =========================================================================

    def add_bot(self, config: BotConfig) -> BotInstance:
        """봇 추가

        Args:
            config: 봇 설정

        Returns:
            생성된 BotInstance

        Raises:
            ValueError: 동일한 이름의 봇이 이미 존재하는 경우
        """
        if config.bot_name in self._bots:
            raise ValueError(f"Bot '{config.bot_name}' already exists")

        instance = BotInstance(
            config=config,
            binance_api_key=self._binance_api_key,
            binance_secret_key=self._binance_secret_key,
            gemini_api_key=self._gemini_api_key,
            discord_webhook_url=self._discord_webhook_url,
            database_url=self._database_url,
            loop_interval_seconds=self._loop_interval_seconds,
            redis_state_manager=self._redis_state_manager,
            on_signal_callback=self._on_signal_callback,
            on_trade_callback=self._on_trade_callback,
            on_error_callback=self._on_error_callback,
        )

        self._bots[config.bot_name] = instance
        logger.info(f"봇 추가됨: {config.bot_name} ({config.symbol})")

        return instance

    def remove_bot(self, bot_name: str) -> None:
        """봇 제거

        Args:
            bot_name: 제거할 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        if bot_name not in self._bots:
            raise ValueError(f"Bot '{bot_name}' not found")

        # 실행 중인 태스크가 있으면 취소
        if bot_name in self._tasks:
            self._tasks[bot_name].cancel()
            del self._tasks[bot_name]

        del self._bots[bot_name]
        logger.info(f"봇 제거됨: {bot_name}")

    # =========================================================================
    # 봇 조회
    # =========================================================================

    def get_bot(self, bot_name: str) -> Optional[BotInstance]:
        """봇 인스턴스 조회

        Args:
            bot_name: 봇 이름

        Returns:
            BotInstance 또는 None
        """
        return self._bots.get(bot_name)

    def get_all_states(self) -> list[dict[str, Any]]:
        """전체 봇 상태 조회

        Returns:
            봇 상태 리스트
        """
        return [bot.get_state() for bot in self._bots.values()]

    def get_summary(self) -> dict[str, Any]:
        """관리자 요약 정보

        Returns:
            요약 정보 딕셔너리
        """
        return {
            "total_bots": self.bot_count,
            "running_bots": self.running_count,
            "paused_bots": self.paused_count,
            # Phase 5.4: 노출도 정보
            "exposure": self.get_exposure_summary(),
            "bots": [
                {
                    "name": bot.bot_name,
                    "symbol": bot.symbol,
                    "is_running": bot.is_running,
                    "is_paused": bot.is_paused,
                    "risk_level": bot.config.risk_level,
                }
                for bot in self._bots.values()
            ],
        }

    # =========================================================================
    # 봇 제어 (단일)
    # =========================================================================

    def pause_bot(self, bot_name: str) -> None:
        """특정 봇 일시정지

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self._bots.get(bot_name)
        if not bot:
            raise ValueError(f"Bot '{bot_name}' not found")

        bot.pause()
        logger.info(f"봇 일시정지: {bot_name}")

    def resume_bot(self, bot_name: str) -> None:
        """특정 봇 재개

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self._bots.get(bot_name)
        if not bot:
            raise ValueError(f"Bot '{bot_name}' not found")

        bot.resume()
        logger.info(f"봇 재개: {bot_name}")

    async def start_bot(self, bot_name: str) -> None:
        """특정 봇 시작

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self._bots.get(bot_name)
        if not bot:
            raise ValueError(f"Bot '{bot_name}' not found")

        # 이미 실행 중이면 무시
        if bot_name in self._tasks and not self._tasks[bot_name].done():
            logger.warning(f"봇 이미 실행 중: {bot_name}")
            return

        # 태스크 생성 및 시작
        task = asyncio.create_task(bot.start())
        self._tasks[bot_name] = task
        logger.info(f"봇 시작됨: {bot_name}")

    async def stop_bot(self, bot_name: str) -> None:
        """특정 봇 정지

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self._bots.get(bot_name)
        if not bot:
            raise ValueError(f"Bot '{bot_name}' not found")

        await bot.stop()

        # 태스크 정리
        if bot_name in self._tasks:
            task = self._tasks[bot_name]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self._tasks[bot_name]

        logger.info(f"봇 정지됨: {bot_name}")

    # =========================================================================
    # 봇 제어 (전체)
    # =========================================================================

    def pause_all(self) -> None:
        """전체 봇 일시정지"""
        for bot in self._bots.values():
            bot.pause()
        logger.info(f"전체 봇 일시정지: {self.bot_count}개")

    def resume_all(self) -> None:
        """전체 봇 재개"""
        for bot in self._bots.values():
            bot.resume()
        logger.info(f"전체 봇 재개: {self.bot_count}개")

    async def start_all(self) -> None:
        """전체 봇 시작"""
        tasks = []
        for bot_name, bot in self._bots.items():
            if bot_name not in self._tasks or self._tasks[bot_name].done():
                task = asyncio.create_task(bot.start())
                self._tasks[bot_name] = task
                tasks.append(task)

        logger.info(f"전체 봇 시작: {len(tasks)}개")

    async def stop_all(self) -> None:
        """전체 봇 정지"""
        # 모든 봇에 정지 요청
        for bot in self._bots.values():
            await bot.stop()

        # 모든 태스크 대기
        if self._tasks:
            for task in self._tasks.values():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        self._tasks.clear()
        logger.info(f"전체 봇 정지: {self.bot_count}개")

    # =========================================================================
    # 메인 실행
    # =========================================================================

    async def run(self) -> None:
        """모든 봇 시작 및 대기

        Ctrl+C로 종료될 때까지 실행합니다.
        """
        logger.info("MultiBotManager 실행 시작")

        try:
            await self.start_all()

            # 모든 봇 태스크가 완료될 때까지 대기
            if self._tasks:
                await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("종료 신호 수신")
        except Exception as e:
            logger.error(f"MultiBotManager 에러: {e}", exc_info=True)
        finally:
            await self.stop_all()
            logger.info("MultiBotManager 종료")
