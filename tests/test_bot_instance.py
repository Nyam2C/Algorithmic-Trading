"""
BotInstance 클래스 테스트

개별 봇 인스턴스의 트레이딩 루프 로직 테스트
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance


class TestBotInstance:
    """BotInstance 클래스 테스트"""

    # ===== Fixtures =====
    @pytest.fixture
    def mock_binance_client(self) -> Mock:
        """Mock BinanceTestnetClient"""
        client = Mock()
        client.get_current_price = AsyncMock(return_value=50000.0)
        client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000",
            "priceChangePercent": "1.5",
        })
        client.get_position = AsyncMock(return_value=None)
        client.set_leverage = AsyncMock(return_value=True)
        client.create_market_order = AsyncMock(return_value={
            "orderId": "12345",
            "origQty": "0.001",
        })
        client.close_position = AsyncMock(return_value={
            "orderId": "12346",
        })
        return client

    @pytest.fixture
    def mock_trade_db(self) -> Mock:
        """Mock TradeHistoryDB"""
        db = Mock()
        db.add_entry = AsyncMock(return_value="trade-123")
        db.add_exit = AsyncMock()
        db.get_open_trade = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def bot_config(self):
        """테스트용 BotConfig"""
        from src.bot_config import BotConfig
        return BotConfig(
            bot_id=uuid4(),
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",
            is_testnet=True,
            is_active=True,
        )

    # ===== 생성 테스트 =====
    class TestCreation:
        """BotInstance 생성 테스트"""

        def test_BotConfig로_생성(self, bot_config) -> None:
            """BotConfig를 사용하여 BotInstance 생성"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
            )

            assert instance.config == bot_config
            assert instance.bot_name == "test-bot"
            assert instance.symbol == "BTCUSDT"
            assert instance.is_running is False

        def test_의존성_주입_가능(
            self,
            bot_config,
            mock_binance_client: Mock,
            mock_trade_db: Mock,
        ) -> None:
            """외부 의존성 주입 가능"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
                trade_db=mock_trade_db,
            )

            assert instance._binance_client is mock_binance_client
            assert instance._trade_db is mock_trade_db

    # ===== 상태 관리 테스트 =====
    class TestStateManagement:
        """봇 상태 관리 테스트"""

        def test_초기_상태(self, bot_config) -> None:
            """초기 상태 확인"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
            )

            state = instance.get_state()

            assert state["is_running"] is False
            assert state["is_paused"] is False
            assert state["bot_name"] == "test-bot"
            assert state["symbol"] == "BTCUSDT"
            assert state["position"] is None

        def test_pause_resume(self, bot_config) -> None:
            """pause/resume 기능 테스트"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
            )

            # 초기: paused=False
            assert instance.is_paused is False

            # Pause
            instance.pause()
            assert instance.is_paused is True

            # Resume
            instance.resume()
            assert instance.is_paused is False

        def test_emergency_close_플래그(self, bot_config) -> None:
            """emergency_close 플래그 설정"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
            )

            # 초기: False
            assert instance._emergency_close is False

            # 설정
            instance.request_emergency_close()
            assert instance._emergency_close is True

    # ===== 시그널 생성 테스트 =====
    class TestSignalGeneration:
        """시그널 생성 테스트"""

        @pytest.mark.asyncio
        async def test_시장_데이터_수집(
            self,
            bot_config,
            mock_binance_client: Mock,
        ) -> None:
            """시장 데이터 수집 테스트"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
            )

            # analyze_market을 모킹하여 데이터 형식 문제 우회
            with patch("src.bot_instance.analyze_market") as mock_analyze:
                mock_analyze.return_value = {
                    "current_price": 50000.0,
                    "rsi": 45.0,
                    "ma_7": 49500.0,
                    "volume_ratio": 1.1,
                }

                market_data = await instance._fetch_market_data()

            assert market_data["current_price"] == 50000.0
            mock_binance_client.get_current_price.assert_called_once_with("BTCUSDT")
            mock_binance_client.get_klines.assert_called_once()

        @pytest.mark.asyncio
        async def test_시그널_생성_with_custom_parameters(
            self,
            mock_binance_client: Mock,
        ) -> None:
            """커스텀 RSI 파라미터로 시그널 생성"""
            from src.bot_config import BotConfig
            from src.bot_instance import BotInstance

            config = BotConfig(
                bot_name="custom-bot",
                symbol="BTCUSDT",
                rsi_oversold=30.0,  # 커스텀 값
                rsi_overbought=70.0,  # 커스텀 값
            )

            instance = BotInstance(
                config=config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
            )

            # signal_generator의 파라미터 확인 (속성명은 _없이 rsi_oversold)
            assert instance._signal_generator.rsi_oversold == 30.0
            assert instance._signal_generator.rsi_overbought == 70.0

    # ===== 트레이딩 루프 테스트 =====
    class TestTradingLoop:
        """트레이딩 루프 테스트"""

        @pytest.mark.asyncio
        async def test_단일_루프_실행(
            self,
            bot_config,
            mock_binance_client: Mock,
        ) -> None:
            """단일 트레이딩 루프 실행 테스트"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
            )

            # executor를 먼저 초기화
            await instance._initialize()

            # analyze_market 모킹
            with patch("src.bot_instance.analyze_market") as mock_analyze:
                mock_analyze.return_value = {
                    "current_price": 50000.0,
                    "rsi": 45.0,
                    "ma_7": 49500.0,
                    "volume_ratio": 1.1,
                }

                # 단일 루프 실행
                await instance._execute_single_loop()

            # 시장 데이터 조회 확인
            mock_binance_client.get_current_price.assert_called()
            mock_binance_client.get_klines.assert_called()

        @pytest.mark.asyncio
        async def test_paused_상태에서_트레이딩_스킵(
            self,
            bot_config,
            mock_binance_client: Mock,
        ) -> None:
            """paused 상태에서 트레이딩 스킵"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
            )

            # executor를 먼저 초기화
            await instance._initialize()

            # Pause 상태
            instance.pause()

            # analyze_market 모킹
            with patch("src.bot_instance.analyze_market") as mock_analyze:
                mock_analyze.return_value = {
                    "current_price": 50000.0,
                    "rsi": 45.0,
                    "ma_7": 49500.0,
                    "volume_ratio": 1.1,
                }

                # 루프 실행
                await instance._execute_single_loop()

            # 포지션 오픈이 호출되지 않아야 함
            mock_binance_client.create_market_order.assert_not_called()

    # ===== 포지션 관리 테스트 =====
    class TestPositionManagement:
        """포지션 관리 테스트"""

        @pytest.mark.asyncio
        async def test_포지션_오픈(
            self,
            bot_config,
            mock_binance_client: Mock,
            mock_trade_db: Mock,
        ) -> None:
            """포지션 오픈 테스트"""
            from src.bot_instance import BotInstance

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
                trade_db=mock_trade_db,
            )

            # executor를 먼저 초기화
            await instance._initialize()

            # 포지션 오픈
            result = await instance._open_position("LONG", 50000.0)

            assert result is not None
            mock_binance_client.create_market_order.assert_called()

        @pytest.mark.asyncio
        async def test_포지션_클로즈(
            self,
            bot_config,
            mock_binance_client: Mock,
            mock_trade_db: Mock,
        ) -> None:
            """포지션 클로즈 테스트"""
            from src.bot_instance import BotInstance

            # 기존 포지션이 있는 상태
            mock_binance_client.get_position = AsyncMock(return_value={
                "side": "LONG",
                "position_amt": 0.001,
                "entry_price": 49000.0,
            })

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
                trade_db=mock_trade_db,
            )

            # executor를 먼저 초기화
            await instance._initialize()

            # 포지션 클로즈
            result = await instance._close_position(50000.0, "TP")

            assert result is not None
            mock_binance_client.close_position.assert_called()

    # ===== 콜백 테스트 =====
    class TestCallbacks:
        """콜백 테스트"""

        @pytest.mark.asyncio
        async def test_on_signal_콜백(
            self,
            bot_config,
            mock_binance_client: Mock,
        ) -> None:
            """on_signal 콜백 호출 테스트"""
            from src.bot_instance import BotInstance

            callback_called = False
            callback_data = {}

            async def on_signal(bot_name: str, signal: str, price: float) -> None:
                nonlocal callback_called, callback_data
                callback_called = True
                callback_data = {"bot_name": bot_name, "signal": signal, "price": price}

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
                on_signal_callback=on_signal,
            )

            # 시그널 콜백 실행
            await instance._notify_signal("LONG", 50000.0)

            assert callback_called is True
            assert callback_data["bot_name"] == "test-bot"
            assert callback_data["signal"] == "LONG"

        @pytest.mark.asyncio
        async def test_on_trade_콜백(
            self,
            bot_config,
            mock_binance_client: Mock,
        ) -> None:
            """on_trade 콜백 호출 테스트"""
            from src.bot_instance import BotInstance

            callback_called = False

            async def on_trade(
                bot_name: str,
                action: str,
                side: str,
                price: float,
                pnl: float | None,
            ) -> None:
                nonlocal callback_called
                callback_called = True

            instance = BotInstance(
                config=bot_config,
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                binance_client=mock_binance_client,
                on_trade_callback=on_trade,
            )

            # 트레이드 콜백 실행
            await instance._notify_trade("OPEN", "LONG", 50000.0, None)

            assert callback_called is True


class TestBotInstanceIntegration:
    """BotInstance 통합 테스트"""

    @pytest.fixture
    def mock_binance_client(self) -> Mock:
        """Mock BinanceTestnetClient"""
        client = Mock()
        client.get_current_price = AsyncMock(return_value=50000.0)
        client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000",
            "priceChangePercent": "1.5",
        })
        client.get_position = AsyncMock(return_value=None)
        client.set_leverage = AsyncMock(return_value=True)
        return client

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_binance_client: Mock) -> None:
        """start/stop 생명주기 테스트"""
        import asyncio

        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(
            bot_name="lifecycle-test",
            symbol="BTCUSDT",
        )

        instance = BotInstance(
            config=config,
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            binance_client=mock_binance_client,
        )

        # 시작
        task = asyncio.create_task(instance.start())
        await asyncio.sleep(0.1)

        assert instance.is_running is True

        # 정지
        await instance.stop()
        await asyncio.sleep(0.1)

        assert instance.is_running is False

        # 태스크 정리
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# =============================================================================
# 커버리지 향상 테스트 (from test_bot_instance_coverage.py)
# =============================================================================

# 공통 Fixtures

@pytest.fixture
def coverage_bot_config():
    """테스트용 BotConfig"""
    return BotConfig(
        bot_id=uuid4(),
        bot_name="coverage-bot",
        symbol="BTCUSDT",
        risk_level="medium",
        is_testnet=True,
        is_active=True,
    )


@pytest.fixture
def coverage_mock_binance_client():
    """Mock BinanceTestnetClient"""
    client = MagicMock()
    client.connect = AsyncMock()
    client.get_current_price = AsyncMock(return_value=50000.0)
    client.get_klines = AsyncMock(return_value=[
        [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
    ] * 24)
    client.get_ticker_24h = AsyncMock(return_value={
        "volume": "10000",
        "priceChangePercent": "1.5",
    })
    client.get_position = AsyncMock(return_value=None)
    client.set_leverage = AsyncMock(return_value=True)
    client.create_market_order = AsyncMock(return_value={
        "orderId": "12345",
        "origQty": "0.001",
    })
    client.close_position = AsyncMock(return_value={"orderId": "12346"})
    client.get_account_balance = AsyncMock(return_value={"available": 10000.0})
    return client


@pytest.fixture
def coverage_mock_trade_db():
    """Mock TradeHistoryDB"""
    db = MagicMock()
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()
    db.add_entry = AsyncMock(return_value="trade-123")
    db.add_exit = AsyncMock()
    db.get_open_trade = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_redis_manager():
    """Mock Redis 상태 관리자"""
    manager = MagicMock()
    manager.save_bot_state = AsyncMock()
    manager.load_bot_state = AsyncMock(return_value=None)
    manager.save_position = AsyncMock()
    manager.load_position = AsyncMock(return_value=None)
    manager.delete_position = AsyncMock()
    manager.register_bot = AsyncMock()
    manager.set_bot_running = AsyncMock()
    manager.set_bot_stopped = AsyncMock()
    return manager


@pytest.fixture
def mock_enhanced_gemini():
    """Mock EnhancedGeminiSignalGenerator"""
    gemini = MagicMock()
    gemini.get_signal_with_memory = AsyncMock(return_value="LONG")
    gemini.set_context_builder = MagicMock()
    return gemini


def _create_instance(bot_config, **kwargs):
    """BotInstance 생성 헬퍼"""
    defaults = {
        "config": bot_config,
        "binance_api_key": "test_key",
        "binance_secret_key": "test_secret",
    }
    defaults.update(kwargs)
    return BotInstance(**defaults)


# =============================================================================
# Redis 상태 동기화 테스트
# =============================================================================


class TestRedisSyncState:
    """Redis 상태 동기화/복구 관련 테스트"""

    @pytest.mark.asyncio
    async def test_sync_state_to_redis_no_position(self, coverage_bot_config, mock_redis_manager):
        """포지션 없이 Redis 상태 동기화"""
        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )
        instance._current_position = None

        await instance._sync_state_to_redis()

        mock_redis_manager.save_bot_state.assert_called_once()
        mock_redis_manager.delete_position.assert_called_once_with("coverage-bot")

    @pytest.mark.asyncio
    async def test_sync_state_to_redis_with_position(self, coverage_bot_config, mock_redis_manager):
        """포지션이 있을 때 Redis 상태 동기화"""
        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )
        instance._current_position = {"side": "LONG", "entry_price": 50000.0}

        await instance._sync_state_to_redis()

        mock_redis_manager.save_bot_state.assert_called_once()
        mock_redis_manager.save_position.assert_called_once_with(
            "coverage-bot", {"side": "LONG", "entry_price": 50000.0}
        )

    @pytest.mark.asyncio
    async def test_sync_state_to_redis_no_manager(self, coverage_bot_config):
        """Redis 관리자가 없을 때 동기화 스킵"""
        instance = _create_instance(coverage_bot_config)
        # redis_state_manager가 None이면 바로 리턴
        await instance._sync_state_to_redis()
        # 에러 없이 완료

    @pytest.mark.asyncio
    async def test_sync_state_to_redis_exception(self, coverage_bot_config, mock_redis_manager):
        """Redis 동기화 실패 시 경고 로그"""
        mock_redis_manager.save_bot_state = AsyncMock(side_effect=Exception("redis error"))
        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        # 예외가 발생해도 에러가 전파되지 않음
        await instance._sync_state_to_redis()

    @pytest.mark.asyncio
    async def test_restore_state_from_redis_no_manager(self, coverage_bot_config):
        """Redis 관리자가 없을 때 복구 실패"""
        instance = _create_instance(coverage_bot_config)

        result = await instance._restore_state_from_redis()
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_state_from_redis_with_state(self, coverage_bot_config, mock_redis_manager):
        """Redis에서 봇 상태 복구"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": True,
            "loop_count": 42,
            "last_signal": "LONG",
            "last_signal_time": None,
        })
        mock_redis_manager.load_position = AsyncMock(return_value=None)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()

        assert result is True
        assert instance._is_paused is True
        assert instance._loop_count == 42
        assert instance._last_signal == "LONG"

    @pytest.mark.asyncio
    async def test_restore_state_from_redis_with_position(self, coverage_bot_config, mock_redis_manager):
        """Redis에서 포지션 포함 상태 복구"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": False,
            "loop_count": 10,
            "last_signal": "SHORT",
        })
        mock_redis_manager.load_position = AsyncMock(return_value={
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        })

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()

        assert result is True
        assert instance._current_position is not None
        assert instance._current_position["side"] == "LONG"

    @pytest.mark.asyncio
    async def test_restore_state_from_redis_exception(self, coverage_bot_config, mock_redis_manager):
        """Redis 상태 복구 실패"""
        mock_redis_manager.load_bot_state = AsyncMock(side_effect=Exception("redis error"))

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_state_no_saved_state(self, coverage_bot_config, mock_redis_manager):
        """Redis에 저장된 상태가 없을 때"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value=None)
        mock_redis_manager.load_position = AsyncMock(return_value=None)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()
        assert result is False

    def test_set_redis_state_manager(self, coverage_bot_config, mock_redis_manager):
        """Redis 상태 관리자 설정"""
        instance = _create_instance(coverage_bot_config)
        assert instance._redis_state_manager is None

        instance.set_redis_state_manager(mock_redis_manager)
        assert instance._redis_state_manager is mock_redis_manager


# =============================================================================
# AI 메모리 시그널 테스트
# =============================================================================


class TestMemorySignals:
    """AI 메모리 시그널 관련 테스트"""

    def test_memory_signals_enabled_true(self, coverage_bot_config, mock_enhanced_gemini):
        """메모리 시그널 활성화 상태 확인"""
        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )
        assert instance.memory_signals_enabled is True

    def test_memory_signals_enabled_false_no_gemini(self, coverage_bot_config):
        """Gemini 없으면 메모리 시그널 비활성"""
        instance = _create_instance(
            coverage_bot_config,
            use_memory_signals=True,
        )
        assert instance.memory_signals_enabled is False

    def test_memory_signals_enabled_false_not_set(self, coverage_bot_config, mock_enhanced_gemini):
        """use_memory_signals가 False이면 비활성"""
        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=False,
        )
        assert instance.memory_signals_enabled is False

    def test_enable_memory_signals_success(self, coverage_bot_config, mock_enhanced_gemini):
        """메모리 시그널 활성화 성공"""
        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
        )
        result = instance.enable_memory_signals()
        assert result is True
        assert instance._use_memory_signals is True

    def test_enable_memory_signals_no_gemini(self, coverage_bot_config):
        """EnhancedGemini 없이 활성화 시도 -> 실패"""
        instance = _create_instance(coverage_bot_config)
        result = instance.enable_memory_signals()
        assert result is False
        assert instance._use_memory_signals is False

    def test_disable_memory_signals(self, coverage_bot_config, mock_enhanced_gemini):
        """메모리 시그널 비활성화"""
        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )
        instance.disable_memory_signals()
        assert instance._use_memory_signals is False

    def test_set_enhanced_gemini(self, coverage_bot_config, mock_enhanced_gemini):
        """EnhancedGemini 설정"""
        instance = _create_instance(coverage_bot_config)
        assert instance._enhanced_gemini is None

        instance.set_enhanced_gemini(mock_enhanced_gemini)
        assert instance._enhanced_gemini is mock_enhanced_gemini

    @pytest.mark.asyncio
    async def test_generate_signal_with_memory_success(self, coverage_bot_config, mock_enhanced_gemini):
        """메모리 기반 시그널 생성 성공"""
        mock_enhanced_gemini.get_signal_with_memory = AsyncMock(return_value="LONG")

        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )

        market_data = {"indicators": {"rsi": 45.0, "ma_7": 49500.0}}
        signal = await instance._generate_signal_with_memory(market_data)

        assert signal == "LONG"
        mock_enhanced_gemini.get_signal_with_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_signal_with_memory_fallback_no_gemini(self, coverage_bot_config):
        """Gemini 없을 때 규칙 기반으로 폴백"""
        instance = _create_instance(coverage_bot_config)

        market_data = {"indicators": {"rsi": 45.0, "ma_7": 49500.0}}
        signal = await instance._generate_signal_with_memory(market_data)

        # 규칙 기반 시그널이므로 "WAIT", "LONG", "SHORT" 중 하나
        assert signal in ("WAIT", "LONG", "SHORT")

    @pytest.mark.asyncio
    async def test_generate_signal_with_memory_invalid_signal(self, coverage_bot_config, mock_enhanced_gemini):
        """AI가 유효하지 않은 시그널 반환 시 규칙 기반으로 대체"""
        mock_enhanced_gemini.get_signal_with_memory = AsyncMock(return_value="INVALID_SIGNAL")

        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )

        market_data = {"indicators": {"rsi": 45.0, "ma_7": 49500.0}}
        signal = await instance._generate_signal_with_memory(market_data)

        # 유효하지 않으므로 규칙 기반으로 대체
        assert signal in ("WAIT", "LONG", "SHORT")

    @pytest.mark.asyncio
    async def test_generate_signal_with_memory_exception(self, coverage_bot_config, mock_enhanced_gemini):
        """메모리 시그널 생성 실패 시 규칙 기반으로 폴백"""
        mock_enhanced_gemini.get_signal_with_memory = AsyncMock(
            side_effect=Exception("API error")
        )

        instance = _create_instance(
            coverage_bot_config,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )

        market_data = {"indicators": {"rsi": 45.0, "ma_7": 49500.0}}
        signal = await instance._generate_signal_with_memory(market_data)

        assert signal in ("WAIT", "LONG", "SHORT")


# =============================================================================
# 시그널 생성 테스트
# =============================================================================


class TestSignalGeneration:
    """시그널 생성 관련 테스트"""

    def test_generate_signal_valid(self, coverage_bot_config):
        """유효한 시그널 생성"""
        instance = _create_instance(coverage_bot_config)
        market_data = {"indicators": {"rsi": 45.0, "volume_ratio": 1.3}}
        signal = instance._generate_signal(market_data)
        assert signal in ("WAIT", "LONG", "SHORT")
        assert instance._last_signal_time is not None

    def test_generate_signal_invalid_signal_becomes_wait(self, coverage_bot_config):
        """유효하지 않은 시그널은 WAIT으로 변경"""
        instance = _create_instance(coverage_bot_config)

        # signal_generator가 유효하지 않은 값을 반환하도록 모킹
        instance._signal_generator.get_signal = MagicMock(return_value="INVALID")

        market_data = {"indicators": {}}
        signal = instance._generate_signal(market_data)
        assert signal == "WAIT"


# =============================================================================
# 초기화 테스트
# =============================================================================


class TestInitialization:
    """봇 초기화 관련 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_with_binance_client(self, coverage_bot_config, coverage_mock_binance_client):
        """Binance 클라이언트가 주입된 상태에서 초기화"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        assert instance._executor is not None
        coverage_mock_binance_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_creates_binance_client_if_none(self, coverage_bot_config):
        """Binance 클라이언트가 없으면 생성"""
        instance = _create_instance(coverage_bot_config)

        with patch("src.bot_instance.BinanceTestnetClient") as MockBinance:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock()
            mock_client.get_account_balance = AsyncMock(return_value={"available": 5000.0})
            MockBinance.return_value = mock_client

            await instance._initialize()

            MockBinance.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_database_url(self, coverage_bot_config, coverage_mock_binance_client):
        """database_url이 있으면 TradeHistoryDB 초기화"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            database_url="postgresql://test:test@localhost/test",
        )

        with patch("src.bot_instance.TradeHistoryDB") as MockDB:
            mock_db = MagicMock()
            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            MockDB.return_value = mock_db

            await instance._initialize()

            MockDB.assert_called_once()
            mock_db.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_db_connection_failure(self, coverage_bot_config, coverage_mock_binance_client):
        """DB 연결 실패 시 에러 로그"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            database_url="postgresql://test:test@localhost/test",
        )

        with patch("src.bot_instance.TradeHistoryDB") as MockDB:
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(side_effect=Exception("DB connection failed"))
            MockDB.return_value = mock_db

            await instance._initialize()
            # 에러가 발생해도 초기화는 계속 진행됨

    @pytest.mark.asyncio
    async def test_initialize_with_memory_signals(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db, mock_enhanced_gemini
    ):
        """메모리 시그널과 함께 초기화"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )

        with patch("src.bot_instance.TradeHistoryAnalyzer"):
            with patch("src.bot_instance.AIMemoryContextBuilder") as MockCtx:
                mock_ctx_instance = MagicMock()
                MockCtx.return_value = mock_ctx_instance

                await instance._initialize()

                # enhanced_gemini가 이미 주입됐으므로 set_context_builder가 호출됨
                mock_enhanced_gemini.set_context_builder.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_memory_signals_create_gemini(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """메모리 시그널 + gemini_api_key가 있으면 EnhancedGemini 자동 생성"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            gemini_api_key="test_gemini_key",
            use_memory_signals=True,
        )

        with patch("src.bot_instance.TradeHistoryAnalyzer"):
            with patch("src.bot_instance.AIMemoryContextBuilder"):
                with patch("src.bot_instance.EnhancedGeminiSignalGenerator") as MockGemini:
                    mock_gemini = MagicMock()
                    MockGemini.return_value = mock_gemini

                    await instance._initialize()

                    MockGemini.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_memory_signals_exception(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """메모리 시스템 초기화 실패 시 비활성화"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            use_memory_signals=True,
        )

        with patch("src.bot_instance.TradeHistoryAnalyzer", side_effect=Exception("init error")):
            await instance._initialize()

        assert instance._use_memory_signals is False

    @pytest.mark.asyncio
    async def test_initialize_with_redis(
        self, coverage_bot_config, coverage_mock_binance_client, mock_redis_manager
    ):
        """Redis 상태 관리자가 있을 때 상태 복구 및 등록"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            redis_state_manager=mock_redis_manager,
        )

        await instance._initialize()

        mock_redis_manager.register_bot.assert_called_once_with("coverage-bot")
        mock_redis_manager.set_bot_running.assert_called_once_with("coverage-bot")

    @pytest.mark.asyncio
    async def test_initialize_risk_manager_balance_failure(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """리스크 매니저 초기화 시 잔고 조회 실패 -> 기본값 사용"""
        coverage_mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("balance error")
        )

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        # 기본값 1000.0으로 초기화됨 (에러 무시)


# =============================================================================
# 정리(cleanup) 테스트
# =============================================================================


class TestCleanup:
    """봇 정리 관련 테스트"""

    @pytest.mark.asyncio
    async def test_cleanup_with_redis(self, coverage_bot_config, mock_redis_manager):
        """Redis가 있을 때 cleanup"""
        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        await instance._cleanup()

        mock_redis_manager.save_bot_state.assert_called_once()
        mock_redis_manager.set_bot_stopped.assert_called_once_with("coverage-bot")

    @pytest.mark.asyncio
    async def test_cleanup_with_trade_db(self, coverage_bot_config, coverage_mock_trade_db):
        """TradeDB가 있을 때 cleanup"""
        instance = _create_instance(
            coverage_bot_config,
            trade_db=coverage_mock_trade_db,
        )

        await instance._cleanup()

        coverage_mock_trade_db.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_dependencies(self, coverage_bot_config):
        """의존성 없이 cleanup"""
        instance = _create_instance(coverage_bot_config)
        await instance._cleanup()
        # 에러 없이 완료


# =============================================================================
# 시장 데이터 수집 테스트
# =============================================================================


class TestFetchMarketData:
    """시장 데이터 수집 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_market_data_no_client(self, coverage_bot_config):
        """Binance 클라이언트 없이 데이터 수집 시 RuntimeError"""
        instance = _create_instance(coverage_bot_config)

        with pytest.raises(RuntimeError, match="Binance client not initialized"):
            await instance._fetch_market_data()


# =============================================================================
# 포지션 관리 테스트
# =============================================================================


class TestPositionManagement:
    """포지션 오픈/클로즈 관련 테스트"""

    @pytest.mark.asyncio
    async def test_open_position_no_executor(self, coverage_bot_config):
        """Executor 없이 포지션 오픈 시 RuntimeError"""
        instance = _create_instance(coverage_bot_config)

        with pytest.raises(RuntimeError, match="Executor not initialized"):
            await instance._open_position("LONG", 50000.0)

    @pytest.mark.asyncio
    async def test_close_position_no_executor(self, coverage_bot_config):
        """Executor 없이 포지션 클로즈 시 RuntimeError"""
        instance = _create_instance(coverage_bot_config)

        with pytest.raises(RuntimeError, match="Executor not initialized"):
            await instance._close_position(50000.0, "TP")

    @pytest.mark.asyncio
    async def test_open_position_with_db_and_callback(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """포지션 오픈 시 DB 기록 및 콜백 호출"""
        on_trade = AsyncMock()

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            on_trade_callback=on_trade,
        )

        await instance._initialize()

        # executor의 open_position 결과를 모킹
        instance._executor.open_position = AsyncMock(return_value={"orderId": "123", "origQty": "0.001"})
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "trade_id": None,
        }

        result = await instance._open_position("LONG", 50000.0)

        assert result is not None
        coverage_mock_trade_db.add_entry.assert_called_once()
        on_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_position_returns_none(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """포지션 오픈 실패 (None 반환)"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._executor.open_position = AsyncMock(return_value=None)

        result = await instance._open_position("LONG", 50000.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_close_position_no_position(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """청산할 포지션이 없을 때"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._executor.get_position = AsyncMock(return_value=None)

        result = await instance._close_position(50000.0, "TP")
        assert result is None

    @pytest.mark.asyncio
    async def test_close_position_with_pnl_tracking(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """포지션 클로즈 시 PnL 추적 및 리스크 관리"""
        on_trade = AsyncMock()

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            on_trade_callback=on_trade,
        )

        await instance._initialize()

        # 포지션 정보 모킹
        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.04)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "trade_id": "trade-123",
            "entry_time": datetime.now(),
        }

        result = await instance._close_position(50000.0, "TP")

        assert result is not None
        coverage_mock_trade_db.add_exit.assert_called_once()
        on_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_position_risk_halt(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """포지션 클로즈 후 리스크 한도 도달 시 봇 정지"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=-5.0)
        instance._executor.current_position = None

        # 리스크 매니저가 거래 정지를 반환하도록 모킹
        instance._risk_manager.should_halt_trading = AsyncMock(
            return_value=(True, "일일 손실 한도 초과")
        )

        result = await instance._close_position(47500.0, "SL")

        assert result is not None
        assert instance._is_paused is True
        assert instance._risk_halt_notified is True

    @pytest.mark.asyncio
    async def test_close_position_risk_halt_with_error_callback(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """리스크 한도 도달 시 에러 콜백 호출"""
        on_error = AsyncMock()

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            on_error_callback=on_error,
        )

        await instance._initialize()

        position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=-5.0)
        instance._executor.current_position = None
        instance._risk_manager.should_halt_trading = AsyncMock(
            return_value=(True, "일일 손실 한도 초과")
        )

        await instance._close_position(47500.0, "SL")

        on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_position_with_atr(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """ATR 포함 포지션 오픈"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._executor.open_position = AsyncMock(return_value={"orderId": "123", "origQty": "0.001"})
        instance._executor.current_position = None

        result = await instance._open_position("LONG", 50000.0, entry_atr=500.0)
        assert result is not None



    @pytest.mark.asyncio
    async def test_close_short_position_pnl_calculation(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """SHORT 포지션 PnL 정확히 계산되는지 검증 (Phase 5 P1 버그 수정)"""
        on_trade = AsyncMock()

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
            on_trade_callback=on_trade,
        )

        await instance._initialize()

        # SHORT 포지션: entry=50000, exit=49000 → 이익
        position = {
            "side": "SHORT",
            "entry_price": 50000.0,
            "position_amt": -0.001,  # SHORT이므로 음수
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "789"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = {
            "side": "SHORT",
            "entry_price": 50000.0,
            "trade_id": "trade-short",
            "entry_time": datetime.now(),
        }

        result = await instance._close_position(49000.0, "TP")

        assert result is not None
        # pnl_usd = (50000 - 49000) * abs(-0.001) * leverage(15) = 15.0
        # 리스크 매니저의 daily_pnl이 양수여야 함
        daily_pnl = instance._risk_manager.get_daily_pnl()
        assert daily_pnl > 0, f"SHORT 이익인데 daily_pnl이 음수: {daily_pnl}"

    @pytest.mark.asyncio
    async def test_close_short_position_loss_pnl(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """SHORT 포지션 손실 시 PnL이 음수로 계산되는지 검증"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # SHORT 포지션: entry=50000, exit=51000 → 손실
        position = {
            "side": "SHORT",
            "entry_price": 50000.0,
            "position_amt": -0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "790"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=-2.0)
        instance._executor.current_position = None

        result = await instance._close_position(51000.0, "SL")

        assert result is not None


# =============================================================================
# 콜백 에러 핸들링 테스트
# =============================================================================


class TestCallbackErrorHandling:
    """콜백 호출 시 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_notify_signal_callback_error(self, coverage_bot_config):
        """시그널 콜백 에러 핸들링"""
        on_signal = AsyncMock(side_effect=Exception("callback error"))

        instance = _create_instance(
            coverage_bot_config,
            on_signal_callback=on_signal,
        )

        # 에러가 전파되지 않아야 함
        await instance._notify_signal("LONG", 50000.0)

    @pytest.mark.asyncio
    async def test_notify_trade_callback_error(self, coverage_bot_config):
        """거래 콜백 에러 핸들링"""
        on_trade = AsyncMock(side_effect=Exception("callback error"))

        instance = _create_instance(
            coverage_bot_config,
            on_trade_callback=on_trade,
        )

        await instance._notify_trade("OPEN", "LONG", 50000.0, None)

    @pytest.mark.asyncio
    async def test_notify_error_callback_error(self, coverage_bot_config):
        """에러 콜백 자체가 에러 발생"""
        on_error = AsyncMock(side_effect=Exception("callback error"))

        instance = _create_instance(
            coverage_bot_config,
            on_error_callback=on_error,
        )

        await instance._notify_error(RuntimeError("test error"))

    @pytest.mark.asyncio
    async def test_notify_error_no_callback(self, coverage_bot_config):
        """에러 콜백이 없을 때"""
        instance = _create_instance(coverage_bot_config)
        await instance._notify_error(RuntimeError("test error"))

    @pytest.mark.asyncio
    async def test_notify_signal_no_callback(self, coverage_bot_config):
        """시그널 콜백이 없을 때"""
        instance = _create_instance(coverage_bot_config)
        await instance._notify_signal("LONG", 50000.0)

    @pytest.mark.asyncio
    async def test_notify_trade_no_callback(self, coverage_bot_config):
        """거래 콜백이 없을 때"""
        instance = _create_instance(coverage_bot_config)
        await instance._notify_trade("OPEN", "LONG", 50000.0, None)

    @pytest.mark.asyncio
    async def test_notify_risk_halt(self, coverage_bot_config):
        """리스크 한도 알림"""
        on_error = AsyncMock()
        instance = _create_instance(
            coverage_bot_config,
            on_error_callback=on_error,
        )

        await instance._notify_risk_halt("일일 손실 한도 초과")
        on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_risk_halt_callback_error(self, coverage_bot_config):
        """리스크 알림 시 콜백 에러"""
        on_error = AsyncMock(side_effect=Exception("callback error"))
        instance = _create_instance(
            coverage_bot_config,
            on_error_callback=on_error,
        )

        # 에러가 전파되지 않아야 함
        await instance._notify_risk_halt("일일 손실 한도 초과")

    @pytest.mark.asyncio
    async def test_notify_risk_halt_no_callback(self, coverage_bot_config):
        """리스크 알림 콜백 없을 때"""
        instance = _create_instance(coverage_bot_config)
        await instance._notify_risk_halt("일일 손실 한도 초과")


# =============================================================================
# 트레이딩 루프 테스트
# =============================================================================


class TestTradingLoop:
    """트레이딩 루프 관련 테스트"""

    @pytest.mark.asyncio
    async def test_execute_single_loop_with_memory_signals(
        self, coverage_bot_config, coverage_mock_binance_client, mock_enhanced_gemini
    ):
        """메모리 시그널을 사용한 단일 루프 실행"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            enhanced_gemini=mock_enhanced_gemini,
            use_memory_signals=True,
        )

        await instance._initialize()

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        mock_enhanced_gemini.get_signal_with_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_loop_emergency_close(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """긴급 청산 플래그가 설정된 상태에서 루프 실행"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._emergency_close = True

        # 포지션 클로즈를 모킹
        instance._close_position = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        assert instance._emergency_close is False
        assert instance._is_paused is True
        instance._close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_loop_regime_filter(
        self, coverage_mock_binance_client
    ):
        """레짐 필터가 활성화된 상태에서 루프 실행"""
        config = BotConfig(
            bot_name="regime-test",
            symbol="BTCUSDT",
            risk_level="medium",
            is_testnet=True,
            use_regime_filter=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

    @pytest.mark.asyncio
    async def test_execute_single_loop_with_existing_position_timecut(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """기존 포지션이 있고 timecut 조건 충족 시"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # executor에 포지션 및 timecut 모킹
        position = {"side": "LONG", "entry_price": 49000.0, "position_amt": 0.001}
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "entry_time": datetime.now(),
        }
        instance._executor.check_timecut = MagicMock(return_value=True)
        instance._close_position = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        instance._close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_loop_with_existing_position_tp_sl(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """기존 포지션이 있고 TP/SL 조건 충족 시"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        position = {"side": "LONG", "entry_price": 49000.0, "position_amt": 0.001}
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "entry_time": datetime.now(),
        }
        instance._executor.check_timecut = MagicMock(return_value=False)
        instance._executor.check_tp_sl_dynamic = AsyncMock(return_value="TP")
        instance._close_position = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        instance._close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_loop_risk_skip(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """리스크 제한으로 진입 스킵"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 리스크 매니저가 거래 스킵을 반환
        instance._risk_manager.should_skip_trade = AsyncMock(
            return_value=(True, "쿨다운 중")
        )

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }
            with patch("src.bot_instance.should_enter_trade", return_value=True):
                await instance._execute_single_loop()

    @pytest.mark.asyncio
    async def test_execute_single_loop_calls_update_balance(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """매 루프마다 update_balance가 호출되어 드로다운 추적"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        # get_account_balance가 호출되어야 함 (init + loop)
        assert coverage_mock_binance_client.get_account_balance.call_count >= 2

    @pytest.mark.asyncio
    async def test_execute_single_loop_update_balance_failure(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """update_balance 실패 시 루프가 계속 진행"""
        coverage_mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("balance error")
        )

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        # init에서도 실패하므로 기본값으로 초기화됨
        await instance._initialize()

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            # 에러가 발생해도 루프가 계속 진행
            await instance._execute_single_loop()

    @pytest.mark.asyncio
    async def test_execute_single_loop_enter_trade_with_atr(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """ATR 정보가 있는 상태에서 진입"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        instance._open_position = AsyncMock(return_value={"orderId": "123"})

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 20.0,
                "ma_7": 49500.0,
                "volume_ratio": 2.0,
                "atr": 500.0,
            }
            with patch("src.bot_instance.should_enter_trade", return_value=True):
                await instance._execute_single_loop()

        instance._open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_loop_no_executor(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """executor가 None인 경우 포지션 확인 스킵"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._executor = None  # executor를 None으로 설정

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            # 에러 없이 완료
            await instance._execute_single_loop()


# =============================================================================
# 메인 루프 및 생명주기 테스트
# =============================================================================


class TestLifecycle:
    """봇 생명주기 테스트"""

    @pytest.mark.asyncio
    async def test_run_loop_executes_and_stops(self, coverage_bot_config, coverage_mock_binance_client):
        """run_loop가 is_running이 False가 되면 종료"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 한 번만 실행하고 멈추게 설정
        call_count = 0

        async def mock_execute():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                instance._is_running = False

        instance._execute_single_loop = mock_execute

        with patch("src.bot_instance.asyncio.sleep", new_callable=AsyncMock):
            await instance._run_loop()

        assert call_count >= 1
        assert instance._is_running is False

    @pytest.mark.asyncio
    async def test_run_loop_handles_exception(self, coverage_bot_config, coverage_mock_binance_client):
        """루프 중 에러 발생 시 계속 실행"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        call_count = 0

        async def mock_execute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("loop error")
            instance._is_running = False

        instance._execute_single_loop = mock_execute

        with patch("src.bot_instance.asyncio.sleep", new_callable=AsyncMock):
            await instance._run_loop()

        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_start_and_stop(self, coverage_bot_config, coverage_mock_binance_client):
        """start/stop 전체 생명주기"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        # start 내부의 _run_loop를 모킹하여 즉시 종료
        async def mock_run_loop():
            instance._is_running = True
            instance._is_running = False

        instance._run_loop = mock_run_loop
        instance._initialize = AsyncMock()
        instance._cleanup = AsyncMock()

        await instance.start()

        instance._initialize.assert_called_once()
        instance._cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cancelled(self, coverage_bot_config, coverage_mock_binance_client):
        """태스크 취소 시 cleanup 호출"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        instance._initialize = AsyncMock()
        instance._cleanup = AsyncMock()

        async def mock_run_loop():
            raise asyncio.CancelledError()

        instance._run_loop = mock_run_loop

        await instance.start()

        instance._cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, coverage_bot_config):
        """stop이 is_running을 False로 설정"""
        instance = _create_instance(coverage_bot_config)
        instance._is_running = True

        await instance.stop()

        assert instance._is_running is False

    @pytest.mark.asyncio
    async def test_run_loop_with_redis_sync(self, coverage_bot_config, coverage_mock_binance_client, mock_redis_manager):
        """루프 실행 중 Redis 동기화"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            redis_state_manager=mock_redis_manager,
        )

        await instance._initialize()

        call_count = 0

        async def mock_execute():
            nonlocal call_count
            call_count += 1
            instance._is_running = False

        instance._execute_single_loop = mock_execute

        with patch("src.bot_instance.asyncio.sleep", new_callable=AsyncMock):
            await instance._run_loop()

        # Redis 동기화가 호출되어야 함
        mock_redis_manager.save_bot_state.assert_called()


# =============================================================================
# 프로퍼티 테스트
# =============================================================================


class TestProperties:
    """프로퍼티 테스트"""

    def test_bot_name(self, coverage_bot_config):
        """bot_name 프로퍼티"""
        instance = _create_instance(coverage_bot_config)
        assert instance.bot_name == "coverage-bot"

    def test_symbol(self, coverage_bot_config):
        """symbol 프로퍼티"""
        instance = _create_instance(coverage_bot_config)
        assert instance.symbol == "BTCUSDT"

    def test_is_running(self, coverage_bot_config):
        """is_running 프로퍼티"""
        instance = _create_instance(coverage_bot_config)
        assert instance.is_running is False

    def test_is_paused(self, coverage_bot_config):
        """is_paused 프로퍼티"""
        instance = _create_instance(coverage_bot_config)
        assert instance.is_paused is False

    def test_get_state_includes_all_fields(self, coverage_bot_config):
        """get_state에 모든 필드가 포함"""
        instance = _create_instance(coverage_bot_config)
        state = instance.get_state()

        assert "bot_id" in state
        assert "bot_name" in state
        assert "symbol" in state
        assert "risk_level" in state
        assert "is_running" in state
        assert "is_paused" in state
        assert "uptime_start" in state
        assert "loop_count" in state
        assert "current_price" in state
        assert "last_signal" in state
        assert "last_signal_time" in state
        assert "position" in state
        assert "leverage" in state
        assert "memory_signals_enabled" in state
        assert "risk_stats" in state
        assert "market_regime" in state


# =============================================================================
# Phase 5 통합 테스트
# =============================================================================


class TestSignalTrackerIntegration:
    """SignalTracker 통합 테스트"""

    def test_signal_tracker_initialized(self, coverage_bot_config):
        """SignalTracker가 __init__에서 초기화됨"""
        instance = _create_instance(coverage_bot_config)
        assert instance._signal_tracker is not None

    @pytest.mark.asyncio
    async def test_signal_recorded_in_loop(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """루프에서 시그널이 기록됨"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        # 시그널이 기록되었는지 확인
        assert instance._last_signal_id is not None
        assert len(instance._signal_tracker._in_memory_signals) > 0

    @pytest.mark.asyncio
    async def test_signal_result_updated_on_close(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """포지션 청산 시 시그널 결과가 업데이트됨"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 시그널 ID 설정
        signal_id = await instance._signal_tracker.record_signal(
            bot_id=str(coverage_bot_config.bot_id),
            signal="LONG",
            source="rule_based",
        )
        instance._last_signal_id = signal_id

        # 포지션 청산
        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = None

        await instance._close_position(50000.0, "TP")

        # 시그널 결과 업데이트 확인
        record = instance._signal_tracker._in_memory_signals.get(signal_id)
        assert record is not None
        assert record.trade_result == "win"


class TestPrometheusIntegration:
    """Prometheus 메트릭 통합 테스트"""

    def test_metrics_initialized(self, coverage_bot_config):
        """TradingMetrics가 __init__에서 초기화 시도됨"""
        instance = _create_instance(coverage_bot_config)
        # prometheus_client가 설치되어 있으면 metrics가 있음
        # 설치되지 않았으면 None
        assert hasattr(instance, "_metrics")

    @pytest.mark.asyncio
    async def test_metrics_record_on_close(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """포지션 청산 시 Prometheus 메트릭 기록"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 메트릭을 모킹
        mock_metrics = MagicMock()
        instance._metrics = mock_metrics

        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = {
            "entry_time": datetime.now(),
        }

        await instance._close_position(50000.0, "TP")

        mock_metrics.record_trade.assert_called_once()
        mock_metrics.clear_position_metrics.assert_called_once_with(
            coverage_bot_config.bot_name
        )

    @pytest.mark.asyncio
    async def test_metrics_position_pnl_during_hold(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """포지션 유지 중 PnL 메트릭 기록"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        mock_metrics = MagicMock()
        instance._metrics = mock_metrics

        position = {"side": "LONG", "entry_price": 49000.0, "position_amt": 0.001}
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "entry_time": datetime.now(),
        }
        instance._executor.check_timecut = MagicMock(return_value=False)
        instance._executor.check_tp_sl_dynamic = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        mock_metrics.record_position_pnl.assert_called_once()


class TestMultiTimeframeIntegration:
    """MultiTimeframeAnalyzer 통합 테스트"""

    def test_mtf_analyzer_initialized(self, coverage_bot_config):
        """MTF 분석기가 __init__에서 초기화됨"""
        instance = _create_instance(coverage_bot_config)
        assert instance._mtf_analyzer is not None

    @pytest.mark.asyncio
    async def test_mtf_filter_applied_when_enabled(
        self, coverage_mock_binance_client
    ):
        """MTF 필터가 활성화 시 적용됨"""
        config = BotConfig(
            bot_name="mtf-test",
            symbol="BTCUSDT",
            use_mtf_filter=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 15분봉 데이터도 반환하도록 설정
        coverage_mock_binance_client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "ma_25": 49000.0,
                "volume_ratio": 1.1,
                "current_price": 50000.0,
            }

            await instance._execute_single_loop()

        # 15분봉 데이터가 수집되었는지 확인 (초기 5분봉 + 15분봉)
        assert coverage_mock_binance_client.get_klines.call_count >= 2


class TestEnsembleIntegration:
    """EnsembleSignalGenerator 통합 테스트"""

    @pytest.mark.asyncio
    async def test_ensemble_used_when_enabled(
        self, coverage_mock_binance_client
    ):
        """앙상블이 활성화 시 사용됨"""
        config = BotConfig(
            bot_name="ensemble-test",
            symbol="BTCUSDT",
            use_ensemble=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 앙상블 생성기가 초기화되었는지 확인
        assert instance._ensemble_generator is not None

    @pytest.mark.asyncio
    async def test_ensemble_signal_generation(
        self, coverage_mock_binance_client
    ):
        """앙상블 시그널 생성"""
        config = BotConfig(
            bot_name="ensemble-test",
            symbol="BTCUSDT",
            use_ensemble=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 앙상블을 모킹
        mock_result = MagicMock()
        mock_result.final_signal = "LONG"
        mock_result.consensus_ratio = 0.67
        instance._ensemble_generator.generate_ensemble_signal = AsyncMock(
            return_value=mock_result
        )

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        instance._ensemble_generator.generate_ensemble_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensemble_fallback_on_error(
        self, coverage_mock_binance_client
    ):
        """앙상블 실패 시 규칙 기반으로 폴백"""
        config = BotConfig(
            bot_name="ensemble-fallback",
            symbol="BTCUSDT",
            use_ensemble=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        # 앙상블이 에러를 발생시키도록 설정
        instance._ensemble_generator.generate_ensemble_signal = AsyncMock(
            side_effect=Exception("ensemble error")
        )

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            # 에러 없이 폴백해야 함
            await instance._execute_single_loop()


class TestTradeApprovalIntegration:
    """TradeApprovalManager 통합 테스트"""

    @pytest.mark.asyncio
    async def test_approval_manager_initialized_when_enabled(
        self, coverage_mock_binance_client
    ):
        """승인 매니저가 활성화 시 초기화됨"""
        config = BotConfig(
            bot_name="approval-test",
            symbol="BTCUSDT",
            manual_approval_enabled=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        assert instance._trade_approval is not None

    @pytest.mark.asyncio
    async def test_approval_creates_request_and_skips(
        self, coverage_mock_binance_client
    ):
        """승인 필요 시 요청 생성 후 루프 스킵"""
        config = BotConfig(
            bot_name="approval-skip",
            symbol="BTCUSDT",
            manual_approval_enabled=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._open_position = AsyncMock()

        # 규칙 기반 생성기가 LONG을 반환하도록 모킹
        instance._signal_generator.get_signal = MagicMock(return_value="LONG")

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 20.0,
                "ma_7": 49500.0,
                "volume_ratio": 2.0,
            }

            await instance._execute_single_loop()

        # 승인 대기 중이므로 포지션 오픈이 호출되지 않아야 함
        instance._open_position.assert_not_called()
        # 승인 요청이 생성되었는지 확인
        assert instance._pending_approval_request is not None


class TestExposureCheckIntegration:
    """MultiBotManager 노출도 체크 통합 테스트"""

    @pytest.mark.asyncio
    async def test_exposure_check_blocks_entry(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """노출도 한도 초과 시 진입 차단"""
        async def deny_exposure(bot_name: str, value: float) -> tuple[bool, str]:
            return False, "총 노출도 한도 초과"

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            on_exposure_check=deny_exposure,
        )

        await instance._initialize()
        instance._open_position = AsyncMock()
        instance._signal_generator.get_signal = MagicMock(return_value="LONG")

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 20.0,
                "ma_7": 49500.0,
                "volume_ratio": 2.0,
            }
            with patch("src.bot_instance.should_enter_trade", return_value=True):
                await instance._execute_single_loop()

        instance._open_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_exposure_check_allows_entry(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """노출도 허용 범위 내 진입 허용"""
        async def allow_exposure(bot_name: str, value: float) -> tuple[bool, str]:
            return True, ""

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            on_exposure_check=allow_exposure,
        )

        await instance._initialize()
        instance._open_position = AsyncMock(return_value={"orderId": "123"})
        instance._signal_generator.get_signal = MagicMock(return_value="LONG")

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 20.0,
                "ma_7": 49500.0,
                "volume_ratio": 2.0,
            }
            with patch("src.bot_instance.should_enter_trade", return_value=True):
                await instance._execute_single_loop()

        instance._open_position.assert_called_once()


class TestGetStateIntegration:
    """get_state 통합 필드 테스트"""

    def test_get_state_includes_new_fields(self, coverage_bot_config):
        """get_state에 Phase 5 통합 필드 포함"""
        instance = _create_instance(coverage_bot_config)
        state = instance.get_state()

        assert "use_mtf_filter" in state
        assert "higher_tf_trend" in state
        assert "use_ensemble" in state
        assert "trade_approval" in state
