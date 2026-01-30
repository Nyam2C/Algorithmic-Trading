"""
BotInstance 클래스 테스트

개별 봇 인스턴스의 트레이딩 루프 로직 테스트
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4


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
            from src.bot_instance import BotInstance
            from src.bot_config import BotConfig

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
        from src.bot_instance import BotInstance
        from src.bot_config import BotConfig

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
