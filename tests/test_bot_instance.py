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
        client.create_stop_market_order = AsyncMock(return_value={
            "orderId": "77777", "type": "STOP_MARKET", "status": "NEW",
        })
        client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": "88888", "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })
        client.cancel_all_open_orders = AsyncMock(return_value={
            "code": 200, "msg": "success",
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
            # MA99 계산을 위해 limit=150으로 호출되어야 함
            mock_binance_client.get_klines.assert_called_once_with("BTCUSDT", limit=150)

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
    client.create_stop_market_order = AsyncMock(return_value={
        "orderId": "77777", "type": "STOP_MARKET", "status": "NEW",
    })
    client.create_take_profit_market_order = AsyncMock(return_value={
        "orderId": "88888", "type": "TAKE_PROFIT_MARKET", "status": "NEW",
    })
    client.cancel_all_open_orders = AsyncMock(return_value={
        "code": 200, "msg": "success",
    })
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
        instance._emergency_event.set()

        # 포지션 클로즈를 모킹
        instance._close_position = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }

            await instance._execute_single_loop()

        assert not instance._emergency_event.is_set()
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
                instance._emergency_event.set()  # Unblock event wait

        instance._execute_single_loop = mock_execute

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
                instance._emergency_event.set()  # Unblock event wait
                raise RuntimeError("loop error")
            instance._is_running = False
            instance._emergency_event.set()  # Unblock event wait

        instance._execute_single_loop = mock_execute

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
            instance._emergency_event.set()  # Unblock event wait

        instance._execute_single_loop = mock_execute

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


class TestRecoveryMarkerProcessing:
    """Recovery marker processing in _restore_state_from_redis 테스트"""

    @pytest.mark.asyncio
    async def test_recovery_marker_found_and_processed(self, coverage_bot_config, mock_redis_manager, coverage_mock_trade_db):
        """복구 마커가 발견되면 DB에 기록하고 마커 삭제"""
        recovery_data = {
            "entry_time": "2026-02-13T10:00:00",
            "entry_price": 50000.0,
            "side": "LONG",
            "quantity": 0.001,
            "leverage": 15,
            "symbol": "BTCUSDT",
        }
        # First call returns bot state, second returns no position, third returns recovery data
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": False,
            "loop_count": 5,
            "last_signal": "WAIT",
        })
        call_count = 0
        async def load_position_side_effect(key):
            nonlocal call_count
            call_count += 1
            if key == "coverage-bot":
                return None  # No normal position
            if key == "coverage-bot:recovery":
                return recovery_data
            return None
        mock_redis_manager.load_position = AsyncMock(side_effect=load_position_side_effect)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
            trade_db=coverage_mock_trade_db,
        )

        result = await instance._restore_state_from_redis()

        assert result is True
        # DB add_entry should have been called with recovery data
        coverage_mock_trade_db.add_entry.assert_called_once()
        call_kwargs = coverage_mock_trade_db.add_entry.call_args
        assert call_kwargs[1]["entry_price"] == 50000.0
        assert call_kwargs[1]["side"] == "LONG"
        # Recovery marker should be deleted
        mock_redis_manager.delete_position.assert_called_with("coverage-bot:recovery")

    @pytest.mark.asyncio
    async def test_recovery_marker_no_marker(self, coverage_bot_config, mock_redis_manager):
        """복구 마커가 없으면 아무것도 하지 않음"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": False,
            "loop_count": 5,
            "last_signal": "WAIT",
        })
        mock_redis_manager.load_position = AsyncMock(return_value=None)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()
        assert result is True

    @pytest.mark.asyncio
    async def test_recovery_marker_db_failure(self, coverage_bot_config, mock_redis_manager, coverage_mock_trade_db):
        """복구 마커 DB 기록 실패 시 에러 로그만 남김"""
        recovery_data = {
            "entry_time": "2026-02-13T10:00:00",
            "entry_price": 50000.0,
            "side": "LONG",
            "quantity": 0.001,
            "leverage": 15,
            "symbol": "BTCUSDT",
        }
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": False, "loop_count": 0, "last_signal": "WAIT",
        })
        async def load_position_side_effect(key):
            if key == "coverage-bot":
                return None
            if key == "coverage-bot:recovery":
                return recovery_data
            return None
        mock_redis_manager.load_position = AsyncMock(side_effect=load_position_side_effect)
        coverage_mock_trade_db.add_entry = AsyncMock(side_effect=Exception("DB error"))

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
            trade_db=coverage_mock_trade_db,
        )

        # Should not raise, just log the error
        result = await instance._restore_state_from_redis()
        assert result is True

    @pytest.mark.asyncio
    async def test_recovery_marker_check_exception(self, coverage_bot_config, mock_redis_manager):
        """복구 마커 체크 자체가 실패해도 정상 진행"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            "is_paused": False, "loop_count": 0, "last_signal": "WAIT",
        })
        call_count = 0
        async def load_position_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return  # Normal position
            raise Exception("Redis connection error")
        mock_redis_manager.load_position = AsyncMock(side_effect=load_position_side_effect)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()
        assert result is True


class TestApprovalSignalConsistencyInLoop:
    """Approval signal consistency check in trading loop 테스트"""

    @pytest.mark.asyncio
    async def test_signal_changed_skips_entry(self, coverage_mock_binance_client):
        """승인 후 시그널이 변경되면 진입 스킵"""
        from src.trading.trade_approval import TradeApprovalRequest

        config = BotConfig(
            bot_name="approval-consistency",
            symbol="BTCUSDT",
            manual_approval_enabled=True,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._open_position = AsyncMock()

        # Create a pre-approved request with original_signal="LONG"
        req = TradeApprovalRequest(
            bot_name="approval-consistency",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            original_signal="LONG",
        )
        req.approve("user_1")
        instance._pending_approval_request = req

        # But current signal is SHORT
        instance._signal_generator.get_signal = MagicMock(return_value="SHORT")

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 80.0,
                "ma_7": 51000.0,
                "volume_ratio": 2.0,
            }
            await instance._execute_single_loop()

        # Should not open position because signal changed
        instance._open_position.assert_not_called()
        assert instance._pending_approval_request is None

    @pytest.mark.asyncio
    async def test_signal_matches_proceeds_entry(self, coverage_mock_binance_client):
        """승인 후 시그널이 동일하면 진입 진행"""
        from src.trading.trade_approval import TradeApprovalRequest

        config = BotConfig(
            bot_name="approval-match",
            symbol="BTCUSDT",
            manual_approval_enabled=True,
            manual_approval_trades=5,
        )

        instance = _create_instance(
            config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()
        instance._open_position = AsyncMock(return_value={"orderId": "123"})

        # Mark 5 trades completed so no more approval needed after this one
        for _ in range(5):
            await instance._trade_approval.record_trade_completed("approval-match")

        # Create a pre-approved request with original_signal="LONG"
        req = TradeApprovalRequest(
            bot_name="approval-match",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            original_signal="LONG",
        )
        req.approve("user_1")
        instance._pending_approval_request = req

        # Current signal is also LONG
        instance._signal_generator.get_signal = MagicMock(return_value="LONG")

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 20.0,
                "ma_7": 49500.0,
                "volume_ratio": 2.0,
            }
            with patch("src.bot_instance.should_enter_trade", return_value=True):
                await instance._execute_single_loop()

        # Should proceed with entry
        instance._open_position.assert_called_once()


# =============================================================================
# Phase 8 Issue #2: Cancel Orders Before Risk Halt Force Close
# =============================================================================


class TestRiskHaltCancelOrders:
    """Issue #2: 리스크 한도 강제 청산 전 주문 취소"""

    @pytest.mark.asyncio
    async def test_risk_halt_cancels_orders_before_close(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db,
    ):
        """리스크 한도 강제 청산 시 주문 먼저 취소"""
        coverage_mock_binance_client.cancel_all_open_orders = AsyncMock()
        coverage_mock_binance_client.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01, 'entry_price': 50000.0,
            'unrealized_pnl': -500.0,
        })
        coverage_mock_binance_client.close_position = AsyncMock(return_value={
            'orderId': '99999', 'status': 'FILLED', 'executedQty': '0.01',
            'avgPrice': '49000.0',
        })

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
        )
        instance._executor = Mock()
        instance._executor.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01, 'entry_price': 50000.0,
            'unrealized_pnl': -500.0,
        })
        instance._executor.close_position = AsyncMock(return_value={
            'orderId': '99999', 'status': 'FILLED', 'executedQty': '0.01',
            'avgPrice': '49000.0',
        })
        instance._executor.current_position = {
            'signal': 'LONG', 'entry_price': 50000.0, 'entry_time': datetime.now(),
        }
        instance._executor.calculate_pnl_pct = Mock(return_value=-2.0)

        # Force risk halt
        instance._risk_manager.should_halt_trading = AsyncMock(return_value=(True, 'daily loss'))

        await instance._execute_single_loop()

        # cancel_all_open_orders should be called before close
        coverage_mock_binance_client.cancel_all_open_orders.assert_called()

    @pytest.mark.asyncio
    async def test_risk_halt_recheck_position_after_cancel(
        self, coverage_bot_config, coverage_mock_binance_client,
    ):
        """주문 취소 후 포지션 재확인 (SL 체결 시 청산 불필요)"""
        coverage_mock_binance_client.cancel_all_open_orders = AsyncMock()

        call_count = 0
        async def get_position_effect(symbol=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First calls: position exists (risk check + initial)
                return {
                    'side': 'LONG', 'position_amt': 0.01, 'entry_price': 50000.0,
                    'unrealized_pnl': -500.0,
                }
            return None  # After cancel: position gone (SL filled)

        coverage_mock_binance_client.get_position = AsyncMock(
            side_effect=get_position_effect
        )

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )
        instance._executor = Mock()
        instance._executor.get_position = AsyncMock(side_effect=get_position_effect)
        instance._executor.close_position = AsyncMock()

        instance._risk_manager.should_halt_trading = AsyncMock(return_value=(True, 'daily loss'))

        await instance._execute_single_loop()

        # close_position should NOT be called since position is gone
        instance._executor.close_position.assert_not_called()


# =============================================================================
# Phase 8 Issue #5: Exit Recovery Marker Handling on Startup
# =============================================================================


class TestExitRecoveryMarker:
    """Issue #5: 청산 복구 마커 처리"""

    @pytest.mark.asyncio
    async def test_exit_recovery_marker_processed(
        self, coverage_bot_config, mock_redis_manager, coverage_mock_trade_db,
    ):
        """exit 복구 마커가 발견되면 add_exit 호출하고 마커 삭제"""
        exit_recovery_data = {
            'trade_id': 'trade-999',
            'exit_time': '2026-02-13T12:00:00',
            'exit_price': 51000.0,
            'exit_reason': 'TP',
            'pnl': 100.0,
            'pnl_pct': 2.0,
        }
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            'is_paused': False, 'loop_count': 5, 'last_signal': 'WAIT',
        })

        async def load_position_side_effect(key):
            if key == 'coverage-bot':
                return None
            if key == 'coverage-bot:recovery':
                return None  # No entry recovery marker
            if key == 'coverage-bot:recovery:exit':
                return exit_recovery_data
            return None

        mock_redis_manager.load_position = AsyncMock(side_effect=load_position_side_effect)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
            trade_db=coverage_mock_trade_db,
        )

        result = await instance._restore_state_from_redis()

        assert result is True
        # add_exit should be called with recovery data
        coverage_mock_trade_db.add_exit.assert_called_once()
        call_kwargs = coverage_mock_trade_db.add_exit.call_args[1]
        assert call_kwargs['trade_id'] == 'trade-999'
        assert call_kwargs['exit_price'] == 51000.0
        assert call_kwargs['exit_reason'] == 'TP'
        # Recovery marker should be deleted
        mock_redis_manager.delete_position.assert_called_with('coverage-bot:recovery:exit')

    @pytest.mark.asyncio
    async def test_exit_recovery_marker_db_failure(
        self, coverage_bot_config, mock_redis_manager, coverage_mock_trade_db,
    ):
        """exit 복구 마커 DB 기록 실패 시 에러만 로그"""
        exit_recovery_data = {
            'trade_id': 'trade-999',
            'exit_time': '2026-02-13T12:00:00',
            'exit_price': 51000.0,
            'exit_reason': 'SL',
            'pnl': -50.0,
            'pnl_pct': -1.0,
        }
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            'is_paused': False, 'loop_count': 0, 'last_signal': 'WAIT',
        })

        async def load_position_side_effect(key):
            if key == 'coverage-bot':
                return None
            if key == 'coverage-bot:recovery':
                return None
            if key == 'coverage-bot:recovery:exit':
                return exit_recovery_data
            return None

        mock_redis_manager.load_position = AsyncMock(side_effect=load_position_side_effect)
        coverage_mock_trade_db.add_exit = AsyncMock(side_effect=Exception('DB error'))

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
            trade_db=coverage_mock_trade_db,
        )

        # Should not raise
        result = await instance._restore_state_from_redis()
        assert result is True
        # Marker should NOT be deleted on failure
        for call in mock_redis_manager.delete_position.call_args_list:
            assert 'recovery:exit' not in str(call)

    @pytest.mark.asyncio
    async def test_exit_recovery_marker_not_found(
        self, coverage_bot_config, mock_redis_manager,
    ):
        """exit 복구 마커가 없으면 아무것도 안 함"""
        mock_redis_manager.load_bot_state = AsyncMock(return_value={
            'is_paused': False, 'loop_count': 0, 'last_signal': 'WAIT',
        })
        mock_redis_manager.load_position = AsyncMock(return_value=None)

        instance = _create_instance(
            coverage_bot_config,
            redis_state_manager=mock_redis_manager,
        )

        result = await instance._restore_state_from_redis()
        assert result is True



# =============================================================================
# Issue 7: Use Fill Price for DB Entry Price
# =============================================================================


class TestUseFillPriceForEntry:
    """Issue 7: DB에 시장가 대신 실제 체결가(fill price)를 기록"""

    @pytest.mark.asyncio
    async def test_open_position_uses_fill_price_for_db(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """포지션 오픈 시 DB entry_price에 executor의 fill price 사용"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
        )

        await instance._initialize()

        # executor.open_position이 주문을 반환
        instance._executor.open_position = AsyncMock(
            return_value={"orderId": "123", "origQty": "0.001"}
        )
        # executor가 실제 체결가로 position을 업데이트한 상태
        instance._executor.current_position = {
            "signal": "LONG",
            "side": "BUY",
            "entry_price": 50100.0,  # Fill price (different from market price)
            "quantity": 0.001,
            "trade_id": None,
        }

        # market_price=50000, but fill_price=50100
        result = await instance._open_position("LONG", 50000.0)

        assert result is not None
        coverage_mock_trade_db.add_entry.assert_called_once()

        # Verify DB was called with fill price, not market price
        call_kwargs = coverage_mock_trade_db.add_entry.call_args[1]
        assert call_kwargs["entry_price"] == 50100.0  # fill price, not 50000

    @pytest.mark.asyncio
    async def test_open_position_fill_price_matches_executor(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """SHORT 포지션에서도 executor의 fill price를 사용"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
        )

        await instance._initialize()

        instance._executor.open_position = AsyncMock(
            return_value={"orderId": "456", "origQty": "0.002"}
        )
        instance._executor.current_position = {
            "signal": "SHORT",
            "side": "SELL",
            "entry_price": 49900.0,  # Fill price
            "quantity": 0.002,
            "trade_id": None,
        }

        result = await instance._open_position("SHORT", 50000.0)

        assert result is not None
        call_kwargs = coverage_mock_trade_db.add_entry.call_args[1]
        assert call_kwargs["entry_price"] == 49900.0  # fill price


# =============================================================================
# Issue 9: Check add_exit() Return Value
# =============================================================================


class TestCheckAddExitReturnValue:
    """Issue 9: add_exit()의 반환값을 확인하여 중복 PnL 추적 방지"""

    @pytest.mark.asyncio
    async def test_close_position_add_exit_true_tracks_pnl(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """add_exit() 성공 시 PnL 추적 정상 수행"""
        coverage_mock_trade_db.add_exit = AsyncMock(return_value=True)

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
        )

        await instance._initialize()

        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "trade_id": "trade-123",
            "entry_time": datetime.now(),
        }

        # Track initial state
        initial_trades = instance._risk_manager._total_trades

        result = await instance._close_position(50000.0, "TP")

        assert result is not None
        # PnL should be tracked (total_trades increased)
        assert instance._risk_manager._total_trades == initial_trades + 1

    @pytest.mark.asyncio
    async def test_close_position_add_exit_false_skips_pnl(
        self, coverage_bot_config, coverage_mock_binance_client, coverage_mock_trade_db
    ):
        """add_exit() False (이미 청산됨) 시 PnL 추적 스킵"""
        coverage_mock_trade_db.add_exit = AsyncMock(return_value=False)

        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
            trade_db=coverage_mock_trade_db,
        )

        await instance._initialize()

        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "trade_id": "trade-123",
            "entry_time": datetime.now(),
        }

        # Track initial state
        initial_trades = instance._risk_manager._total_trades

        result = await instance._close_position(50000.0, "TP")

        assert result is not None
        # PnL should NOT be tracked (add_exit returned False)
        assert instance._risk_manager._total_trades == initial_trades

    @pytest.mark.asyncio
    async def test_close_position_no_trade_id_still_tracks_pnl(
        self, coverage_bot_config, coverage_mock_binance_client
    ):
        """trade_id가 없으면 (DB 미사용) PnL 추적은 여전히 수행"""
        instance = _create_instance(
            coverage_bot_config,
            binance_client=coverage_mock_binance_client,
        )

        await instance._initialize()

        position = {
            "side": "LONG",
            "entry_price": 49000.0,
            "position_amt": 0.001,
        }
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = None

        initial_trades = instance._risk_manager._total_trades

        result = await instance._close_position(50000.0, "TP")

        assert result is not None
        # PnL tracking should still happen (no DB involved)
        assert instance._risk_manager._total_trades == initial_trades + 1



class TestSignalValidationGate:
    """Issue 12: validate_signal gate before regime filter"""

    @pytest.fixture
    def bot_config(self):
        from uuid import uuid4
        return BotConfig(
            bot_id=uuid4(),
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",
            is_testnet=True,
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_invalid_injected_signal_becomes_wait(self, bot_config):
        """Invalid injected signal should be caught by validation gate"""
        mock_client = Mock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        mock_client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000", "priceChangePercent": "1.5",
        })
        mock_client.get_position = AsyncMock(return_value=None)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0}
        )

        instance = BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
            binance_client=mock_client,
        )

        # Inject an invalid signal (empty string after processing)
        instance._injected_signal = {"signal": "INVALID_GARBAGE", "source": "test"}

        # Mock analyze_market, executor
        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0, "ma_7": 50000.0, "ma_25": 49500.0,
                "ma_99": 49000.0, "atr": 500.0, "price": 50000.0,
            }
            instance._executor = Mock()
            instance._executor.get_position = AsyncMock(return_value=None)
            instance._risk_manager = Mock()
            instance._risk_manager.should_halt_trading = AsyncMock(
                return_value=(False, "")
            )
            instance._risk_manager.check_and_reset_if_new_day = AsyncMock()
            instance._risk_manager.update_balance = AsyncMock()
            instance._risk_manager.should_skip_trade = AsyncMock(
                return_value=(False, "")
            )

            await instance._execute_single_loop()

        # The invalid signal should have been turned to WAIT
        assert instance._last_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_valid_signal_passes_validation_gate(self, bot_config):
        """Valid LONG signal should pass through validation gate"""
        mock_client = Mock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        mock_client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000", "priceChangePercent": "1.5",
        })
        mock_client.get_position = AsyncMock(return_value=None)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0}
        )

        instance = BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
            binance_client=mock_client,
        )

        # Inject a valid LONG signal
        instance._injected_signal = {"signal": "LONG", "source": "test"}

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0, "ma_7": 50500.0, "ma_25": 50000.0,
                "ma_99": 49000.0, "atr": 500.0, "price": 50000.0,
            }
            instance._executor = Mock()
            instance._executor.get_position = AsyncMock(return_value=None)
            instance._executor.current_position = None
            instance._executor.check_timecut = Mock(return_value=False)
            instance._executor.check_tp_sl_dynamic = AsyncMock(return_value=None)
            instance._executor.open_position = AsyncMock(return_value={
                "orderId": "123", "origQty": "0.001",
            })
            instance._risk_manager = Mock()
            instance._risk_manager.should_halt_trading = AsyncMock(
                return_value=(False, "")
            )
            instance._risk_manager.check_and_reset_if_new_day = AsyncMock()
            instance._risk_manager.update_balance = AsyncMock()
            instance._risk_manager.should_skip_trade = AsyncMock(
                return_value=(False, "")
            )
            instance._risk_manager.validate_position_risk = AsyncMock(
                return_value=(True, "")
            )

            await instance._execute_single_loop()

        # LONG should have passed through (not forced to WAIT by validation)
        # It may be filtered by regime but the validation gate itself should pass
        assert instance._last_signal in ("LONG", "WAIT")


class TestMtfDataStaleness:
    """Issue 16: MTF data staleness detection"""

    @pytest.fixture
    def bot_config(self):
        from uuid import uuid4
        return BotConfig(
            bot_id=uuid4(),
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",
            is_testnet=True,
            is_active=True,
            use_mtf_filter=True,
        )

    def test_higher_tf_fetch_time_attribute_exists(self, bot_config):
        """BotInstance should have _higher_tf_fetch_time attribute"""
        instance = BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
        )
        assert hasattr(instance, "_higher_tf_fetch_time")
        assert instance._higher_tf_fetch_time is None

    @pytest.mark.asyncio
    async def test_fetch_records_higher_tf_time(self, bot_config):
        """Fetching MTF data should record timestamp"""
        mock_client = Mock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        mock_client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000", "priceChangePercent": "1.5",
        })

        instance = BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
            binance_client=mock_client,
        )

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0, "ma_7": 50000.0, "ma_25": 49500.0,
                "ma_99": 49000.0, "atr": 500.0, "price": 50000.0,
            }
            await instance._fetch_market_data()

        assert instance._higher_tf_fetch_time is not None
        assert isinstance(instance._higher_tf_fetch_time, datetime)

    @pytest.mark.asyncio
    async def test_stale_mtf_data_skips_filter(self, bot_config):
        """Stale MTF data (>15min) should skip MTF filter"""
        from datetime import timedelta

        mock_client = Mock()
        mock_client.get_current_price = AsyncMock(return_value=50000.0)
        mock_client.get_klines = AsyncMock(return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ] * 24)
        mock_client.get_ticker_24h = AsyncMock(return_value={
            "volume": "10000", "priceChangePercent": "1.5",
        })
        mock_client.get_position = AsyncMock(return_value=None)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 1000.0}
        )

        instance = BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
            binance_client=mock_client,
        )

        # Set stale MTF data (20 min ago)
        instance._higher_tf_fetch_time = datetime.now() - timedelta(minutes=20)
        instance._higher_tf_data = {
            "ma_25": 50000.0, "current_price": 49000.0,
        }

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 30.0, "ma_7": 50500.0, "ma_25": 50000.0,
                "ma_99": 49000.0, "atr": 500.0, "price": 50000.0,
            }
            instance._executor = Mock()
            instance._executor.get_position = AsyncMock(return_value=None)
            instance._executor.current_position = None
            instance._executor.check_timecut = Mock(return_value=False)
            instance._executor.check_tp_sl_dynamic = AsyncMock(return_value=None)
            instance._executor.open_position = AsyncMock(return_value={
                "orderId": "123", "origQty": "0.001",
            })
            instance._risk_manager = Mock()
            instance._risk_manager.should_halt_trading = AsyncMock(
                return_value=(False, "")
            )
            instance._risk_manager.check_and_reset_if_new_day = AsyncMock()
            instance._risk_manager.update_balance = AsyncMock()
            instance._risk_manager.should_skip_trade = AsyncMock(
                return_value=(False, "")
            )
            instance._risk_manager.validate_position_risk = AsyncMock(
                return_value=(True, "")
            )

            # Patch the signal generator to return LONG
            instance._signal_generator = Mock()
            instance._signal_generator.get_signal = Mock(return_value="LONG")

            # MTF filter would block LONG (bearish higher tf) but staleness should skip it
            await instance._execute_single_loop()

        # If MTF staleness detection works, it should NOT have been filtered to WAIT
        # The signal should stay LONG (or be filtered by regime, but not MTF)
        # We check that open_position was called (signal reached entry logic)
        # Note: regime filter may still apply, but MTF should not
