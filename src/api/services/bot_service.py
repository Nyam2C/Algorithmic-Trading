"""
봇 서비스 모듈

봇 CRUD 및 제어 로직을 처리합니다.
"""
from typing import Any

from loguru import logger

from src.bot_manager import MultiBotManager
from src.bot_config import BotConfig
from src.api.schemas.bot import BotCreateRequest, BotUpdateRequest


class BotService:
    """봇 서비스

    봇 CRUD 및 제어 로직을 제공합니다.

    Attributes:
        manager: MultiBotManager 인스턴스
    """

    def __init__(self, manager: MultiBotManager) -> None:
        """봇 서비스 초기화

        Args:
            manager: MultiBotManager 인스턴스
        """
        self.manager = manager

    # =========================================================================
    # 조회
    # =========================================================================

    def list_bots(self) -> dict[str, Any]:
        """봇 목록 조회

        Returns:
            봇 목록 정보
        """
        bots = []
        for bot_name, bot in self.manager.bots.items():
            config = bot.config
            bots.append({
                "bot_id": config.bot_id,
                "bot_name": bot_name,
                "symbol": config.symbol,
                "risk_level": config.risk_level,
                "leverage": config.get_effective_leverage(),
                "position_size_pct": config.get_effective_position_size_pct(),
                "take_profit_pct": config.get_effective_take_profit_pct(),
                "stop_loss_pct": config.get_effective_stop_loss_pct(),
                "time_cut_minutes": config.time_cut_minutes,
                "is_testnet": config.is_testnet,
                "is_active": config.is_active,
                "is_running": bot.is_running,
                "is_paused": bot.is_paused,
                "description": config.description,
            })

        return {
            "total_bots": self.manager.bot_count,
            "running_bots": self.manager.running_count,
            "paused_bots": self.manager.paused_count,
            "bots": bots,
        }

    def get_bot_state(self, bot_name: str) -> dict[str, Any]:
        """봇 상태 조회

        Args:
            bot_name: 봇 이름

        Returns:
            봇 상태 정보

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        return bot.get_state()

    # =========================================================================
    # 생성
    # =========================================================================

    def create_bot(self, request: BotCreateRequest) -> dict[str, Any]:
        """봇 생성

        Args:
            request: 봇 생성 요청

        Returns:
            생성된 봇 정보

        Raises:
            ValueError: 동일한 이름의 봇이 이미 존재하는 경우
        """
        # BotConfig 생성
        config = BotConfig(
            bot_name=request.bot_name,
            symbol=request.symbol,
            risk_level=request.risk_level,
            leverage=request.leverage,
            position_size_pct=request.position_size_pct,
            take_profit_pct=request.take_profit_pct,
            stop_loss_pct=request.stop_loss_pct,
            time_cut_minutes=request.time_cut_minutes or 120,
            rsi_oversold=request.rsi_oversold or 35.0,
            rsi_overbought=request.rsi_overbought or 65.0,
            volume_threshold=request.volume_threshold or 1.2,
            is_testnet=request.is_testnet,
            is_active=False,  # 생성 시 비활성
            description=request.description,
        )

        # 봇 추가
        bot = self.manager.add_bot(config)
        logger.info(f"봇 생성됨: {request.bot_name}")

        return {
            "bot_id": config.bot_id,
            "bot_name": bot.bot_name,
            "symbol": config.symbol,
            "risk_level": config.risk_level,
            "leverage": config.get_effective_leverage(),
            "position_size_pct": config.get_effective_position_size_pct(),
            "take_profit_pct": config.get_effective_take_profit_pct(),
            "stop_loss_pct": config.get_effective_stop_loss_pct(),
            "time_cut_minutes": config.time_cut_minutes,
            "is_testnet": config.is_testnet,
            "is_active": config.is_active,
            "is_running": bot.is_running,
            "is_paused": bot.is_paused,
            "description": config.description,
        }

    # =========================================================================
    # 수정
    # =========================================================================

    def update_bot(
        self, bot_name: str, request: BotUpdateRequest
    ) -> dict[str, Any]:
        """봇 설정 수정

        Args:
            bot_name: 봇 이름
            request: 수정 요청

        Returns:
            수정된 봇 정보

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        config = bot.config

        # 설정 업데이트 (지정된 필드만)
        if request.risk_level is not None:
            config.risk_level = request.risk_level
        if request.leverage is not None:
            config.leverage = request.leverage
        if request.position_size_pct is not None:
            config.position_size_pct = request.position_size_pct
        if request.take_profit_pct is not None:
            config.take_profit_pct = request.take_profit_pct
        if request.stop_loss_pct is not None:
            config.stop_loss_pct = request.stop_loss_pct
        if request.time_cut_minutes is not None:
            config.time_cut_minutes = request.time_cut_minutes
        if request.rsi_oversold is not None:
            config.rsi_oversold = request.rsi_oversold
        if request.rsi_overbought is not None:
            config.rsi_overbought = request.rsi_overbought
        if request.volume_threshold is not None:
            config.volume_threshold = request.volume_threshold
        if request.is_testnet is not None:
            config.is_testnet = request.is_testnet
        if request.is_active is not None:
            config.is_active = request.is_active
        if request.description is not None:
            config.description = request.description

        logger.info(f"봇 설정 수정됨: {bot_name}")

        return {
            "bot_id": config.bot_id,
            "bot_name": bot.bot_name,
            "symbol": config.symbol,
            "risk_level": config.risk_level,
            "leverage": config.get_effective_leverage(),
            "position_size_pct": config.get_effective_position_size_pct(),
            "take_profit_pct": config.get_effective_take_profit_pct(),
            "stop_loss_pct": config.get_effective_stop_loss_pct(),
            "time_cut_minutes": config.time_cut_minutes,
            "is_testnet": config.is_testnet,
            "is_active": config.is_active,
            "is_running": bot.is_running,
            "is_paused": bot.is_paused,
            "description": config.description,
        }

    # =========================================================================
    # 삭제
    # =========================================================================

    def delete_bot(self, bot_name: str) -> None:
        """봇 삭제

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않거나 실행 중인 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        if bot.is_running:
            raise ValueError(
                f"Bot '{bot_name}' is currently running. Stop it first."
            )

        self.manager.remove_bot(bot_name)
        logger.info(f"봇 삭제됨: {bot_name}")

    # =========================================================================
    # 제어
    # =========================================================================

    async def start_bot(self, bot_name: str) -> None:
        """봇 시작

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        await self.manager.start_bot(bot_name)
        logger.info(f"봇 시작됨: {bot_name}")

    async def stop_bot(self, bot_name: str) -> None:
        """봇 정지

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        await self.manager.stop_bot(bot_name)
        logger.info(f"봇 정지됨: {bot_name}")

    def pause_bot(self, bot_name: str) -> None:
        """봇 일시정지

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        self.manager.pause_bot(bot_name)
        logger.info(f"봇 일시정지됨: {bot_name}")

    def resume_bot(self, bot_name: str) -> None:
        """봇 재개

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        self.manager.resume_bot(bot_name)
        logger.info(f"봇 재개됨: {bot_name}")

    def emergency_close(self, bot_name: str) -> None:
        """긴급 청산

        Args:
            bot_name: 봇 이름

        Raises:
            ValueError: 봇이 존재하지 않는 경우
        """
        bot = self.manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"Bot '{bot_name}' not found")

        bot.request_emergency_close()
        logger.warning(f"긴급 청산 요청됨: {bot_name}")

    # =========================================================================
    # 전체 제어
    # =========================================================================

    async def start_all(self) -> int:
        """전체 봇 시작

        Returns:
            시작된 봇 수
        """
        await self.manager.start_all()
        started = self.manager.running_count
        logger.info(f"전체 봇 시작됨: {started}개")
        return started

    async def stop_all(self) -> int:
        """전체 봇 정지

        Returns:
            정지된 봇 수
        """
        count = self.manager.running_count
        await self.manager.stop_all()
        logger.info(f"전체 봇 정지됨: {count}개")
        return count
