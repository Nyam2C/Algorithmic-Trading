"""
MultiBotManager 클래스 테스트

여러 BotInstance를 관리하는 MultiBotManager 테스트
"""
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4


class TestMultiBotManager:
    """MultiBotManager 클래스 테스트"""

    # ===== Fixtures =====
    @pytest.fixture
    def bot_configs(self) -> list:
        """테스트용 BotConfig 리스트"""
        from src.bot_config import BotConfig

        return [
            BotConfig(
                bot_id=uuid4(),
                bot_name="btc-bot",
                symbol="BTCUSDT",
                risk_level="low",
                is_active=True,
            ),
            BotConfig(
                bot_id=uuid4(),
                bot_name="eth-bot",
                symbol="ETHUSDT",
                risk_level="medium",
                is_active=True,
            ),
            BotConfig(
                bot_id=uuid4(),
                bot_name="sol-bot",
                symbol="SOLUSDT",
                risk_level="high",
                is_active=False,  # 비활성화된 봇
            ),
        ]

    @pytest.fixture
    def manager(self, bot_configs: list):
        """테스트용 MultiBotManager"""
        from src.bot_manager import MultiBotManager

        return MultiBotManager(
            binance_api_key="test_key",
            binance_secret_key="test_secret",
        )

    # ===== 생성 테스트 =====
    class TestCreation:
        """MultiBotManager 생성 테스트"""

        def test_기본_생성(self) -> None:
            """기본 생성 테스트"""
            from src.bot_manager import MultiBotManager

            manager = MultiBotManager(
                binance_api_key="test_key",
                binance_secret_key="test_secret",
            )

            assert manager is not None
            assert len(manager.bots) == 0

        def test_설정과_함께_생성(self, bot_configs: list) -> None:
            """봇 설정과 함께 생성"""
            from src.bot_manager import MultiBotManager

            manager = MultiBotManager(
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                configs=bot_configs,
            )

            # 활성화된 봇만 등록됨
            assert len(manager.bots) == 2
            assert "btc-bot" in manager.bots
            assert "eth-bot" in manager.bots
            assert "sol-bot" not in manager.bots

    # ===== 봇 등록/해제 테스트 =====
    class TestBotRegistration:
        """봇 등록/해제 테스트"""

        def test_봇_추가(self, manager) -> None:
            """봇 추가 테스트"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="new-bot",
                symbol="BTCUSDT",
                is_active=True,
            )

            manager.add_bot(config)

            assert "new-bot" in manager.bots
            assert len(manager.bots) == 1

        def test_중복_봇_추가_에러(self, manager) -> None:
            """중복 봇 추가 시 에러"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="dup-bot",
                symbol="BTCUSDT",
                is_active=True,
            )

            manager.add_bot(config)

            with pytest.raises(ValueError, match="already exists"):
                manager.add_bot(config)

        def test_봇_제거(self, manager) -> None:
            """봇 제거 테스트"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="temp-bot",
                symbol="BTCUSDT",
                is_active=True,
            )

            manager.add_bot(config)
            assert "temp-bot" in manager.bots

            manager.remove_bot("temp-bot")
            assert "temp-bot" not in manager.bots

        def test_없는_봇_제거_에러(self, manager) -> None:
            """없는 봇 제거 시 에러"""
            with pytest.raises(ValueError, match="not found"):
                manager.remove_bot("non-existent-bot")

    # ===== 봇 조회 테스트 =====
    class TestBotQuery:
        """봇 조회 테스트"""

        def test_봇_이름으로_조회(self, manager, bot_configs: list) -> None:
            """봇 이름으로 조회"""
            # 봇 추가
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            instance = manager.get_bot("btc-bot")

            assert instance is not None
            assert instance.bot_name == "btc-bot"

        def test_없는_봇_조회시_None(self, manager) -> None:
            """없는 봇 조회 시 None 반환"""
            instance = manager.get_bot("non-existent")

            assert instance is None

        def test_전체_봇_상태_조회(self, manager, bot_configs: list) -> None:
            """전체 봇 상태 조회"""
            # 봇 추가
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            states = manager.get_all_states()

            assert len(states) == 2
            assert any(s["bot_name"] == "btc-bot" for s in states)
            assert any(s["bot_name"] == "eth-bot" for s in states)

    # ===== 봇 제어 테스트 =====
    class TestBotControl:
        """봇 제어 테스트"""

        def test_특정_봇_pause(self, manager) -> None:
            """특정 봇 일시정지"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="pause-test",
                symbol="BTCUSDT",
                is_active=True,
            )
            manager.add_bot(config)

            manager.pause_bot("pause-test")

            instance = manager.get_bot("pause-test")
            assert instance is not None
            assert instance.is_paused is True

        def test_특정_봇_resume(self, manager) -> None:
            """특정 봇 재개"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="resume-test",
                symbol="BTCUSDT",
                is_active=True,
            )
            manager.add_bot(config)

            manager.pause_bot("resume-test")
            manager.resume_bot("resume-test")

            instance = manager.get_bot("resume-test")
            assert instance is not None
            assert instance.is_paused is False

        def test_전체_봇_pause(self, manager, bot_configs: list) -> None:
            """전체 봇 일시정지"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            manager.pause_all()

            for name, instance in manager.bots.items():
                assert instance.is_paused is True

        def test_전체_봇_resume(self, manager, bot_configs: list) -> None:
            """전체 봇 재개"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            manager.pause_all()
            manager.resume_all()

            for name, instance in manager.bots.items():
                assert instance.is_paused is False

    # ===== 시작/정지 테스트 =====
    class TestStartStop:
        """시작/정지 테스트"""

        @pytest.mark.asyncio
        async def test_단일_봇_시작(self, manager) -> None:
            """단일 봇 시작"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="start-test",
                symbol="BTCUSDT",
                is_active=True,
            )
            manager.add_bot(config)

            # 봇 시작을 모킹
            instance = manager.get_bot("start-test")
            assert instance is not None
            instance.start = AsyncMock()

            await manager.start_bot("start-test")

            instance.start.assert_called_once()

        @pytest.mark.asyncio
        async def test_단일_봇_정지(self, manager) -> None:
            """단일 봇 정지"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="stop-test",
                symbol="BTCUSDT",
                is_active=True,
            )
            manager.add_bot(config)

            instance = manager.get_bot("stop-test")
            assert instance is not None
            instance.stop = AsyncMock()

            await manager.stop_bot("stop-test")

            instance.stop.assert_called_once()

        @pytest.mark.asyncio
        async def test_전체_봇_시작(self, manager, bot_configs: list) -> None:
            """전체 봇 시작"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            # 각 봇의 start 모킹
            for name, instance in manager.bots.items():
                instance.start = AsyncMock()

            await manager.start_all()

            for name, instance in manager.bots.items():
                instance.start.assert_called_once()

        @pytest.mark.asyncio
        async def test_전체_봇_정지(self, manager, bot_configs: list) -> None:
            """전체 봇 정지"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            # 각 봇의 stop 모킹
            for name, instance in manager.bots.items():
                instance.stop = AsyncMock()

            await manager.stop_all()

            for name, instance in manager.bots.items():
                instance.stop.assert_called_once()

    # ===== 통계 테스트 =====
    class TestStatistics:
        """통계 테스트"""

        def test_전체_봇_수(self, manager, bot_configs: list) -> None:
            """전체 봇 수 확인"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            assert manager.bot_count == 2

        def test_실행중인_봇_수(self, manager, bot_configs: list) -> None:
            """실행 중인 봇 수 확인"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            # 모든 봇이 정지 상태
            assert manager.running_count == 0

        def test_요약_정보(self, manager, bot_configs: list) -> None:
            """요약 정보 확인"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            summary = manager.get_summary()

            assert summary["total_bots"] == 2
            assert summary["running_bots"] == 0
            assert summary["paused_bots"] == 0
            assert len(summary["bots"]) == 2


class TestMultiBotManagerCallbacks:
    """MultiBotManager 콜백 테스트"""

    @pytest.fixture
    def manager(self):
        """테스트용 MultiBotManager"""
        from src.bot_manager import MultiBotManager

        return MultiBotManager(
            binance_api_key="test_key",
            binance_secret_key="test_secret",
        )

    def test_글로벌_콜백_설정(self, manager) -> None:
        """글로벌 콜백 설정"""
        from src.bot_config import BotConfig

        signal_received = []

        async def on_signal(bot_name: str, signal: str, price: float) -> None:
            signal_received.append((bot_name, signal, price))

        manager.set_on_signal_callback(on_signal)

        config = BotConfig(
            bot_name="callback-test",
            symbol="BTCUSDT",
            is_active=True,
        )
        manager.add_bot(config)

        # 콜백이 봇에 전달되었는지 확인
        instance = manager.get_bot("callback-test")
        assert instance is not None
        assert instance._on_signal_callback is not None
