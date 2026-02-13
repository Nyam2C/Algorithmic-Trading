"""
MultiBotManager 클래스 테스트

여러 BotInstance를 관리하는 MultiBotManager 테스트
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.bot_config import BotConfig
from src.bot_manager import MultiBotManager


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

            for _name, instance in manager.bots.items():
                assert instance.is_paused is True

        def test_전체_봇_resume(self, manager, bot_configs: list) -> None:
            """전체 봇 재개"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            manager.pause_all()
            manager.resume_all()

            for _name, instance in manager.bots.items():
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
            for _name, instance in manager.bots.items():
                instance.start = AsyncMock()

            await manager.start_all()

            for _name, instance in manager.bots.items():
                instance.start.assert_called_once()

        @pytest.mark.asyncio
        async def test_전체_봇_정지(self, manager, bot_configs: list) -> None:
            """전체 봇 정지"""
            for config in bot_configs:
                if config.is_active:
                    manager.add_bot(config)

            # 각 봇의 stop 모킹
            for _name, instance in manager.bots.items():
                instance.stop = AsyncMock()

            await manager.stop_all()

            for _name, instance in manager.bots.items():
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


# =============================================================================
# 커버리지 향상 테스트 (from test_bot_manager_coverage.py)
# =============================================================================

# 공통 Fixtures

@pytest.fixture
def coverage_bot_configs():
    """테스트용 BotConfig 리스트"""
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
            is_active=False,
        ),
    ]


@pytest.fixture
def coverage_manager():
    """기본 MultiBotManager"""
    return MultiBotManager(
        binance_api_key="test_key",
        binance_secret_key="test_secret",
    )


@pytest.fixture
def mock_redis_manager():
    """Mock Redis 상태 관리자"""
    mgr = MagicMock()
    mgr.save_bot_state = AsyncMock()
    mgr.load_bot_state = AsyncMock(return_value=None)
    mgr.save_position = AsyncMock()
    mgr.load_position = AsyncMock(return_value=None)
    mgr.delete_position = AsyncMock()
    mgr.register_bot = AsyncMock()
    mgr.set_bot_running = AsyncMock()
    mgr.set_bot_stopped = AsyncMock()
    mgr.clear_running_bots = AsyncMock()
    mgr.get_registered_bots = AsyncMock(return_value=["btc-bot", "eth-bot"])
    return mgr


# =============================================================================
# 생성 테스트
# =============================================================================


class TestCoverageCreation:
    """MultiBotManager 생성 관련 테스트"""

    def test_creation_with_max_exposure(self):
        """max_total_exposure 설정과 함께 생성"""
        mgr = MultiBotManager(
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            max_total_exposure=100000.0,
        )
        assert mgr.max_total_exposure == 100000.0

    def test_creation_with_configs_filters_inactive(self, coverage_bot_configs):
        """비활성 봇은 필터링됨"""
        mgr = MultiBotManager(
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            configs=coverage_bot_configs,
        )
        assert mgr.bot_count == 2
        assert "sol-bot" not in mgr.bots

    def test_creation_with_all_options(self, coverage_bot_configs, mock_redis_manager):
        """모든 옵션을 포함하여 생성"""
        mgr = MultiBotManager(
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="gemini_key",
            discord_webhook_url="https://discord.webhook",
            database_url="postgresql://test@localhost/db",
            loop_interval_seconds=60,
            configs=coverage_bot_configs,
            redis_state_manager=mock_redis_manager,
            max_total_exposure=50000.0,
        )
        assert mgr.bot_count == 2
        assert mgr.max_total_exposure == 50000.0


# =============================================================================
# Properties 테스트
# =============================================================================


class TestCoverageProperties:
    """프로퍼티 테스트"""

    def test_bots_property(self, coverage_manager):
        """bots 프로퍼티"""
        assert coverage_manager.bots == {}

    def test_bot_count(self, coverage_manager):
        """bot_count 프로퍼티"""
        assert coverage_manager.bot_count == 0

    def test_running_count(self, coverage_manager, coverage_bot_configs):
        """running_count 프로퍼티"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        assert coverage_manager.running_count == 0

    def test_paused_count(self, coverage_manager, coverage_bot_configs):
        """paused_count 프로퍼티"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        coverage_manager.pause_bot("btc-bot")
        assert coverage_manager.paused_count == 1

    def test_redis_state_manager_property(self, coverage_manager):
        """redis_state_manager 프로퍼티"""
        assert coverage_manager.redis_state_manager is None

    def test_max_total_exposure_property(self, coverage_manager):
        """max_total_exposure 프로퍼티"""
        assert coverage_manager.max_total_exposure == 0.0

    def test_set_max_total_exposure(self, coverage_manager):
        """set_max_total_exposure 메서드"""
        coverage_manager.set_max_total_exposure(75000.0)
        assert coverage_manager.max_total_exposure == 75000.0


# =============================================================================
# Phase 5.4: 총 노출도 관리 테스트
# =============================================================================


class TestExposureManagement:
    """총 노출도 관리 테스트"""

    @pytest.mark.asyncio
    async def test_get_total_exposure_no_position(self, coverage_manager, coverage_bot_configs):
        """포지션 없을 때 총 노출도 0"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        total = await coverage_manager.get_total_exposure()
        assert total == 0.0

    @pytest.mark.asyncio
    async def test_get_total_exposure_with_positions(self, coverage_manager):
        """포지션이 있는 봇들의 총 노출도 계산"""
        config = BotConfig(bot_name="test-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)

        # 봇에 포지션 설정
        bot._current_position = {
            "position_amt": 0.1,
            "entry_price": 50000.0,
        }

        total = await coverage_manager.get_total_exposure()
        # 0.1 * 50000.0 * 15 (medium leverage) = 75000.0
        expected = 0.1 * 50000.0 * bot.config.get_effective_leverage()
        assert total == expected

    @pytest.mark.asyncio
    async def test_can_open_position_no_limit(self, coverage_manager):
        """노출도 제한 없으면 항상 허용"""
        can_open, reason = await coverage_manager.can_open_position("test-bot", 50000.0)
        assert can_open is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_can_open_position_within_limit(self, coverage_manager):
        """노출도 한도 내 허용"""
        coverage_manager.set_max_total_exposure(100000.0)

        can_open, reason = await coverage_manager.can_open_position("test-bot", 50000.0)
        assert can_open is True

    @pytest.mark.asyncio
    async def test_can_open_position_exceeds_limit(self, coverage_manager):
        """노출도 한도 초과 시 거부"""
        coverage_manager.set_max_total_exposure(10000.0)

        # 기존 포지션을 가진 봇 추가
        config = BotConfig(bot_name="existing-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot._current_position = {
            "position_amt": 0.1,
            "entry_price": 50000.0,
        }

        can_open, reason = await coverage_manager.can_open_position("new-bot", 5000.0)
        assert can_open is False
        assert "총 노출도 한도 초과" in reason

    def test_get_exposure_summary_no_limit(self, coverage_manager):
        """노출도 제한 없는 요약"""
        summary = coverage_manager.get_exposure_summary()
        assert summary["limit_enabled"] is False
        assert summary["current_exposure"] == 0.0
        assert summary["available_exposure"] == float("inf")
        assert summary["utilization_pct"] == 0

    def test_get_exposure_summary_with_limit(self, coverage_manager):
        """노출도 제한이 있는 요약"""
        coverage_manager.set_max_total_exposure(100000.0)
        summary = coverage_manager.get_exposure_summary()
        assert summary["limit_enabled"] is True
        assert summary["max_exposure"] == 100000.0
        assert summary["available_exposure"] == 100000.0

    def test_get_exposure_summary_with_positions(self, coverage_manager):
        """포지션이 있는 상태에서 노출도 요약"""
        coverage_manager.set_max_total_exposure(200000.0)

        config = BotConfig(bot_name="test-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot._current_position = {
            "position_amt": 0.1,
            "entry_price": 50000.0,
        }

        summary = coverage_manager.get_exposure_summary()
        assert summary["current_exposure"] > 0
        assert summary["utilization_pct"] > 0


# =============================================================================
# Redis 상태 관리 테스트
# =============================================================================


class TestRedisStateManagement:
    """Redis 상태 관리 관련 테스트"""

    def test_set_redis_state_manager(self, coverage_manager, mock_redis_manager, coverage_bot_configs):
        """Redis 상태 관리자 설정 (기존 봇에도 적용)"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        coverage_manager.set_redis_state_manager(mock_redis_manager)

        assert coverage_manager.redis_state_manager is mock_redis_manager
        # 기존 봇에도 적용됨
        for bot in coverage_manager.bots.values():
            assert bot._redis_state_manager is mock_redis_manager

    @pytest.mark.asyncio
    async def test_restore_bots_from_redis(self, coverage_manager, mock_redis_manager):
        """Redis에서 봇 목록 복구"""
        coverage_manager._redis_state_manager = mock_redis_manager

        bots = await coverage_manager.restore_bots_from_redis()

        assert bots == ["btc-bot", "eth-bot"]
        mock_redis_manager.clear_running_bots.assert_called_once()
        mock_redis_manager.get_registered_bots.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_bots_from_redis_no_manager(self, coverage_manager):
        """Redis 관리자 없으면 빈 리스트"""
        bots = await coverage_manager.restore_bots_from_redis()
        assert bots == []

    @pytest.mark.asyncio
    async def test_restore_bots_from_redis_exception(self, coverage_manager, mock_redis_manager):
        """Redis 복구 실패 시 빈 리스트"""
        mock_redis_manager.clear_running_bots = AsyncMock(
            side_effect=Exception("redis error")
        )
        coverage_manager._redis_state_manager = mock_redis_manager

        bots = await coverage_manager.restore_bots_from_redis()
        assert bots == []

    @pytest.mark.asyncio
    async def test_get_redis_bot_states(self, coverage_manager, mock_redis_manager):
        """Redis 봇 상태 조회"""
        mock_redis_manager.load_bot_state = AsyncMock(side_effect=[
            {"is_running": True, "bot_name": "btc-bot"},
            {"is_running": False, "bot_name": "eth-bot"},
        ])
        coverage_manager._redis_state_manager = mock_redis_manager

        states = await coverage_manager.get_redis_bot_states()

        assert "btc-bot" in states
        assert "eth-bot" in states

    @pytest.mark.asyncio
    async def test_get_redis_bot_states_no_manager(self, coverage_manager):
        """Redis 관리자 없으면 빈 딕셔너리"""
        states = await coverage_manager.get_redis_bot_states()
        assert states == {}

    @pytest.mark.asyncio
    async def test_get_redis_bot_states_exception(self, coverage_manager, mock_redis_manager):
        """Redis 상태 조회 실패"""
        mock_redis_manager.get_registered_bots = AsyncMock(
            side_effect=Exception("redis error")
        )
        coverage_manager._redis_state_manager = mock_redis_manager

        states = await coverage_manager.get_redis_bot_states()
        assert states == {}

    @pytest.mark.asyncio
    async def test_get_redis_bot_states_with_none_state(self, coverage_manager, mock_redis_manager):
        """Redis에서 일부 봇 상태가 None인 경우"""
        mock_redis_manager.load_bot_state = AsyncMock(side_effect=[
            {"is_running": True, "bot_name": "btc-bot"},
            None,  # eth-bot의 상태가 없음
        ])
        coverage_manager._redis_state_manager = mock_redis_manager

        states = await coverage_manager.get_redis_bot_states()

        assert "btc-bot" in states
        assert "eth-bot" not in states


# =============================================================================
# 콜백 설정 테스트
# =============================================================================


class TestCallbackSettings:
    """콜백 설정 테스트"""

    def test_set_on_signal_callback(self, coverage_manager, coverage_bot_configs):
        """시그널 콜백 설정"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        async def on_signal(bot_name, signal, price):
            pass

        coverage_manager.set_on_signal_callback(on_signal)

        assert coverage_manager._on_signal_callback is on_signal
        for bot in coverage_manager.bots.values():
            assert bot._on_signal_callback is on_signal

    def test_set_on_trade_callback(self, coverage_manager, coverage_bot_configs):
        """거래 콜백 설정"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        async def on_trade(bot_name, action, side, price, pnl):
            pass

        coverage_manager.set_on_trade_callback(on_trade)

        assert coverage_manager._on_trade_callback is on_trade
        for bot in coverage_manager.bots.values():
            assert bot._on_trade_callback is on_trade

    def test_set_on_error_callback(self, coverage_manager, coverage_bot_configs):
        """에러 콜백 설정"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        async def on_error(bot_name, error):
            pass

        coverage_manager.set_on_error_callback(on_error)

        assert coverage_manager._on_error_callback is on_error
        for bot in coverage_manager.bots.values():
            assert bot._on_error_callback is on_error

    def test_callbacks_applied_to_new_bots(self, coverage_manager):
        """콜백 설정 후 추가된 봇에도 적용"""
        async def on_signal(bot_name, signal, price):
            pass

        coverage_manager.set_on_signal_callback(on_signal)

        config = BotConfig(bot_name="new-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)

        # add_bot에서 매니저의 콜백이 전달됨
        assert bot._on_signal_callback is on_signal


# =============================================================================
# 봇 등록/해제 테스트
# =============================================================================


class TestCoverageBotRegistration:
    """봇 등록/해제 추가 테스트"""

    def test_remove_bot_with_running_task(self, coverage_manager):
        """실행 중인 태스크가 있는 봇 제거"""
        config = BotConfig(bot_name="running-bot", symbol="BTCUSDT", is_active=True)
        coverage_manager.add_bot(config)

        # 태스크 추가
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        mock_task.done = MagicMock(return_value=False)
        coverage_manager._tasks["running-bot"] = mock_task

        coverage_manager.remove_bot("running-bot")

        mock_task.cancel.assert_called_once()
        assert "running-bot" not in coverage_manager._tasks
        assert "running-bot" not in coverage_manager.bots


# =============================================================================
# 봇 조회 테스트
# =============================================================================


class TestCoverageBotQuery:
    """봇 조회 관련 테스트"""

    def test_get_all_states(self, coverage_manager, coverage_bot_configs):
        """전체 봇 상태 조회"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        states = coverage_manager.get_all_states()
        assert len(states) == 2

    def test_get_summary_with_exposure(self, coverage_manager, coverage_bot_configs):
        """노출도 정보 포함한 요약"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        summary = coverage_manager.get_summary()

        assert "total_bots" in summary
        assert "running_bots" in summary
        assert "paused_bots" in summary
        assert "exposure" in summary
        assert "bots" in summary
        assert len(summary["bots"]) == 2

        # bots 리스트의 각 항목 필드 확인
        for bot_info in summary["bots"]:
            assert "name" in bot_info
            assert "symbol" in bot_info
            assert "is_running" in bot_info
            assert "is_paused" in bot_info
            assert "risk_level" in bot_info


# =============================================================================
# 봇 제어 테스트
# =============================================================================


class TestCoverageBotControl:
    """봇 제어 (단일) 테스트"""

    def test_pause_bot_not_found(self, coverage_manager):
        """없는 봇 일시정지 시 에러"""
        with pytest.raises(ValueError, match="not found"):
            coverage_manager.pause_bot("non-existent")

    def test_resume_bot_not_found(self, coverage_manager):
        """없는 봇 재개 시 에러"""
        with pytest.raises(ValueError, match="not found"):
            coverage_manager.resume_bot("non-existent")

    @pytest.mark.asyncio
    async def test_start_bot_not_found(self, coverage_manager):
        """없는 봇 시작 시 에러"""
        with pytest.raises(ValueError, match="not found"):
            await coverage_manager.start_bot("non-existent")

    @pytest.mark.asyncio
    async def test_stop_bot_not_found(self, coverage_manager):
        """없는 봇 정지 시 에러"""
        with pytest.raises(ValueError, match="not found"):
            await coverage_manager.stop_bot("non-existent")

    @pytest.mark.asyncio
    async def test_start_bot_already_running(self, coverage_manager):
        """이미 실행 중인 봇 시작 -> 무시"""
        config = BotConfig(bot_name="running-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot.start = AsyncMock()

        # 이미 실행 중인 태스크가 있는 것처럼 설정
        mock_task = MagicMock()
        mock_task.done = MagicMock(return_value=False)
        coverage_manager._tasks["running-bot"] = mock_task

        await coverage_manager.start_bot("running-bot")

        # start가 호출되지 않아야 함 (이미 실행 중)
        bot.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_bot_creates_task(self, coverage_manager):
        """봇 시작 시 태스크 생성"""
        config = BotConfig(bot_name="start-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot.start = AsyncMock()

        await coverage_manager.start_bot("start-bot")

        assert "start-bot" in coverage_manager._tasks

    @pytest.mark.asyncio
    async def test_stop_bot_with_task(self, coverage_manager):
        """태스크가 있는 봇 정지"""
        config = BotConfig(bot_name="stop-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot.stop = AsyncMock()

        # 완료된 태스크 설정
        mock_task = AsyncMock()
        mock_task.done = MagicMock(return_value=True)
        coverage_manager._tasks["stop-bot"] = mock_task

        await coverage_manager.stop_bot("stop-bot")

        bot.stop.assert_called_once()
        assert "stop-bot" not in coverage_manager._tasks

    @pytest.mark.asyncio
    async def test_stop_bot_with_running_task(self, coverage_manager):
        """실행 중인 태스크가 있는 봇 정지"""
        config = BotConfig(bot_name="stop-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot.stop = AsyncMock()

        # 아직 실행 중인 태스크
        async def dummy_task():
            await asyncio.sleep(100)

        task = asyncio.create_task(dummy_task())
        coverage_manager._tasks["stop-bot"] = task

        await coverage_manager.stop_bot("stop-bot")

        bot.stop.assert_called_once()
        assert "stop-bot" not in coverage_manager._tasks
        assert task.cancelled()


# =============================================================================
# 전체 봇 제어 테스트
# =============================================================================


class TestBotControlAll:
    """전체 봇 제어 테스트"""

    def test_pause_all(self, coverage_manager, coverage_bot_configs):
        """전체 봇 일시정지"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        coverage_manager.pause_all()

        for bot in coverage_manager.bots.values():
            assert bot.is_paused is True

    def test_resume_all(self, coverage_manager, coverage_bot_configs):
        """전체 봇 재개"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        coverage_manager.pause_all()
        coverage_manager.resume_all()

        for bot in coverage_manager.bots.values():
            assert bot.is_paused is False

    @pytest.mark.asyncio
    async def test_start_all(self, coverage_manager, coverage_bot_configs):
        """전체 봇 시작"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.start = AsyncMock()

        await coverage_manager.start_all()

        assert len(coverage_manager._tasks) == 2

    @pytest.mark.asyncio
    async def test_start_all_skips_running_bots(self, coverage_manager, coverage_bot_configs):
        """이미 실행 중인 봇은 스킵"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.start = AsyncMock()

        # btc-bot은 이미 실행 중
        mock_task = MagicMock()
        mock_task.done = MagicMock(return_value=False)
        coverage_manager._tasks["btc-bot"] = mock_task

        await coverage_manager.start_all()

        # eth-bot만 새로 시작됨
        assert "eth-bot" in coverage_manager._tasks

    @pytest.mark.asyncio
    async def test_stop_all(self, coverage_manager, coverage_bot_configs):
        """전체 봇 정지"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.stop = AsyncMock()

        # 태스크 추가
        async def dummy():
            await asyncio.sleep(100)

        for name in list(coverage_manager.bots.keys()):
            task = asyncio.create_task(dummy())
            coverage_manager._tasks[name] = task

        await coverage_manager.stop_all()

        assert len(coverage_manager._tasks) == 0
        for bot in coverage_manager.bots.values():
            bot.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_with_done_tasks(self, coverage_manager, coverage_bot_configs):
        """이미 완료된 태스크가 있는 전체 정지"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.stop = AsyncMock()

        # 완료된 태스크 추가
        mock_task = MagicMock()
        mock_task.done = MagicMock(return_value=True)
        mock_task.cancel = MagicMock()
        coverage_manager._tasks["btc-bot"] = mock_task

        await coverage_manager.stop_all()

        assert len(coverage_manager._tasks) == 0
        # 이미 완료된 태스크는 cancel이 호출되지 않음
        mock_task.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_all_no_tasks(self, coverage_manager, coverage_bot_configs):
        """태스크 없이 전체 정지"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.stop = AsyncMock()

        await coverage_manager.stop_all()

        for bot in coverage_manager.bots.values():
            bot.stop.assert_called_once()


# =============================================================================
# run() 메서드 테스트
# =============================================================================


class TestRun:
    """run() 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_run_starts_and_gathers(self, coverage_manager, coverage_bot_configs):
        """run이 start_all 호출 후 gather"""
        for config in coverage_bot_configs:
            if config.is_active:
                coverage_manager.add_bot(config)

        for bot in coverage_manager.bots.values():
            bot.start = AsyncMock()
            bot.stop = AsyncMock()

        # start_all/stop_all 모킹
        coverage_manager.start_all = AsyncMock()
        coverage_manager.stop_all = AsyncMock()

        await coverage_manager.run()

        coverage_manager.start_all.assert_called_once()
        coverage_manager.stop_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_handles_exception(self, coverage_manager):
        """run 중 예외 발생 시 stop_all 호출"""
        coverage_manager.start_all = AsyncMock(side_effect=RuntimeError("start error"))
        coverage_manager.stop_all = AsyncMock()

        await coverage_manager.run()

        coverage_manager.stop_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_tasks_completes(self, coverage_manager):
        """태스크가 있을 때 run이 정상 완료"""
        config = BotConfig(bot_name="run-test", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)

        # 즉시 완료되는 start 모킹
        bot.start = AsyncMock()
        coverage_manager.stop_all = AsyncMock()

        await coverage_manager.run()

        coverage_manager.stop_all.assert_called_once()


# =============================================================================
# 봇 추가 시 콜백 전달 테스트
# =============================================================================


class TestAddBotWithCallbacks:
    """봇 추가 시 콜백이 올바르게 전달되는지 테스트"""

    def test_add_bot_inherits_global_callbacks(self, coverage_manager):
        """새 봇 추가 시 글로벌 콜백을 상속"""
        async def signal_cb(bot_name, signal, price):
            pass

        async def trade_cb(bot_name, action, side, price, pnl):
            pass

        async def error_cb(bot_name, error):
            pass

        coverage_manager.set_on_signal_callback(signal_cb)
        coverage_manager.set_on_trade_callback(trade_cb)
        coverage_manager.set_on_error_callback(error_cb)

        config = BotConfig(bot_name="inherited-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)

        assert bot._on_signal_callback is signal_cb
        assert bot._on_trade_callback is trade_cb
        assert bot._on_error_callback is error_cb

    def test_add_bot_with_redis(self, coverage_manager, mock_redis_manager):
        """Redis 관리자 설정 후 봇 추가 시 Redis 전달"""
        coverage_manager._redis_state_manager = mock_redis_manager

        config = BotConfig(bot_name="redis-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)

        assert bot._redis_state_manager is mock_redis_manager


# =============================================================================
# 엣지 케이스 테스트
# =============================================================================


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_get_bot_returns_none_for_nonexistent(self, coverage_manager):
        """존재하지 않는 봇 조회 시 None"""
        assert coverage_manager.get_bot("nonexistent") is None

    def test_get_all_states_empty(self, coverage_manager):
        """봇이 없을 때 빈 리스트"""
        assert coverage_manager.get_all_states() == []

    def test_get_summary_empty(self, coverage_manager):
        """봇이 없을 때 요약"""
        summary = coverage_manager.get_summary()
        assert summary["total_bots"] == 0
        assert summary["running_bots"] == 0
        assert summary["paused_bots"] == 0
        assert len(summary["bots"]) == 0

    @pytest.mark.asyncio
    async def test_get_total_exposure_empty(self, coverage_manager):
        """봇이 없을 때 총 노출도"""
        total = await coverage_manager.get_total_exposure()
        assert total == 0.0

    @pytest.mark.asyncio
    async def test_start_bot_done_task_restarts(self, coverage_manager):
        """완료된 태스크가 있는 봇 재시작"""
        config = BotConfig(bot_name="restart-bot", symbol="BTCUSDT", is_active=True)
        bot = coverage_manager.add_bot(config)
        bot.start = AsyncMock()

        # 완료된 태스크
        mock_task = MagicMock()
        mock_task.done = MagicMock(return_value=True)
        coverage_manager._tasks["restart-bot"] = mock_task

        await coverage_manager.start_bot("restart-bot")

        # 새 태스크로 교체됨
        assert "restart-bot" in coverage_manager._tasks


# =============================================================================
# Phase 8: Exposure Reservation Tests (Issue 10)
# =============================================================================


class TestExposureReservation:
    """Phase 8: 노출도 예약 패턴 테스트 (TOCTOU 방지)."""

    @pytest.mark.asyncio
    async def test_reserve_exposure_success(self) -> None:
        """한도 내 예약 성공."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        result = await manager.reserve_exposure("btc-bot", 50000.0)
        assert result is True
        assert "btc-bot" in manager._pending_reservations
        assert manager._pending_reservations["btc-bot"] == 50000.0

    @pytest.mark.asyncio
    async def test_reserve_exposure_exceeds_limit(self) -> None:
        """한도 초과 시 예약 거부."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        # First reservation OK
        result1 = await manager.reserve_exposure("btc-bot", 60000.0)
        assert result1 is True

        # Second reservation exceeds limit
        result2 = await manager.reserve_exposure("eth-bot", 50000.0)
        assert result2 is False
        assert "eth-bot" not in manager._pending_reservations

    @pytest.mark.asyncio
    async def test_reserve_exposure_no_limit(self) -> None:
        """한도 없으면 항상 성공."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=0.0,  # 제한 없음
        )

        result = await manager.reserve_exposure("btc-bot", 999999.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_release_reservation(self) -> None:
        """예약 해제."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        await manager.reserve_exposure("btc-bot", 50000.0)
        assert "btc-bot" in manager._pending_reservations

        await manager.release_reservation("btc-bot")
        assert "btc-bot" not in manager._pending_reservations

    @pytest.mark.asyncio
    async def test_release_nonexistent_reservation(self) -> None:
        """존재하지 않는 예약 해제 시 에러 없음."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        # Should not raise
        await manager.release_reservation("nonexistent-bot")

    @pytest.mark.asyncio
    async def test_get_total_exposure_includes_reservations(self) -> None:
        """get_total_exposure가 예약을 포함."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        # No bots, no positions, but a reservation
        await manager.reserve_exposure("btc-bot", 30000.0)
        total = await manager.get_total_exposure()
        assert total == 30000.0

    @pytest.mark.asyncio
    async def test_reserve_then_release_frees_capacity(self) -> None:
        """예약 해제 후 새 예약 가능."""
        manager = MultiBotManager(
            binance_api_key="test",
            binance_secret_key="test",
            max_total_exposure=100000.0,
        )

        # Reserve nearly full
        await manager.reserve_exposure("btc-bot", 90000.0)

        # New reservation exceeds
        result = await manager.reserve_exposure("eth-bot", 20000.0)
        assert result is False

        # Release first reservation
        await manager.release_reservation("btc-bot")

        # Now new reservation fits
        result = await manager.reserve_exposure("eth-bot", 20000.0)
        assert result is True
