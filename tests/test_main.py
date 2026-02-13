"""
main.py 커버리지 향상 테스트

src/main.py의 함수들을 개별적으로 테스트합니다:
- setup_logging(): JSON 및 텍스트 로깅 설정
- send_discord_embed(): Discord 웹훅 전송
- run_embedded_api(): FastAPI 내장 서버 실행
- main(): 통합 메인 진입점
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# setup_logging 테스트
# =============================================================================


class TestSetupLogging:
    """setup_logging 함수 테스트"""

    def test_setup_logging_json_enabled(self):
        """JSON 로깅이 활성화된 경우"""
        with patch.dict(os.environ, {"ENABLE_JSON_LOGGING": "true"}):
            with patch("src.main.setup_logging_from_env") as mock_setup:
                from src.main import setup_logging
                setup_logging()
                mock_setup.assert_called_once()

    def test_setup_logging_json_disabled(self):
        """JSON 로깅이 비활성화된 경우 (텍스트 로깅 fallback)"""
        with patch.dict(os.environ, {"ENABLE_JSON_LOGGING": "false"}):
            with patch("src.main.logger") as mock_logger:
                with patch("src.main.Path") as mock_path:
                    mock_path_instance = MagicMock()
                    mock_path.return_value = mock_path_instance

                    from src.main import setup_logging
                    setup_logging()

                    mock_logger.remove.assert_called_once()
                    # logger.add가 3번 호출됨 (stdout, bot.log, error.log)
                    assert mock_logger.add.call_count == 3


# =============================================================================
# send_discord_embed 테스트
# =============================================================================


class TestSendDiscordEmbed:
    """send_discord_embed 함수 테스트"""

    @pytest.mark.asyncio
    async def test_send_embed_no_webhook(self):
        """webhook URL이 없을 때"""
        from src.main import send_discord_embed

        result = await send_discord_embed(
            webhook_url="",
            title="Test",
            description="Test desc",
            color=0x00FF00,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_success(self):
        """Discord embed 전송 성공"""
        from src.main import send_discord_embed

        mock_response = AsyncMock()
        mock_response.status = 204

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.main.aiohttp.ClientSession") as MockSession:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)

            # post 메서드가 context manager를 반환
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_instance.post = MagicMock(return_value=mock_post_cm)

            MockSession.return_value = mock_session_instance

            result = await send_discord_embed(
                webhook_url="https://discord.webhook/test",
                title="Test",
                description="Test desc",
                color=0x00FF00,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_embed_with_fields(self):
        """fields가 있는 Discord embed 전송"""
        from src.main import send_discord_embed

        mock_response = AsyncMock()
        mock_response.status = 204

        with patch("src.main.aiohttp.ClientSession") as MockSession:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)

            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_instance.post = MagicMock(return_value=mock_post_cm)

            MockSession.return_value = mock_session_instance

            result = await send_discord_embed(
                webhook_url="https://discord.webhook/test",
                title="Test",
                description="Test desc",
                color=0x00FF00,
                fields=[{"name": "Field1", "value": "Value1", "inline": True}],
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_embed_failure_status(self):
        """Discord embed 전송 실패 (HTTP 에러)"""
        from src.main import send_discord_embed

        mock_response = AsyncMock()
        mock_response.status = 400

        with patch("src.main.aiohttp.ClientSession") as MockSession:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)

            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_instance.post = MagicMock(return_value=mock_post_cm)

            MockSession.return_value = mock_session_instance

            result = await send_discord_embed(
                webhook_url="https://discord.webhook/test",
                title="Test",
                description="Test desc",
                color=0x00FF00,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_exception(self):
        """Discord embed 전송 중 예외"""
        from src.main import send_discord_embed

        with patch("src.main.aiohttp.ClientSession") as MockSession:
            MockSession.side_effect = Exception("connection error")

            result = await send_discord_embed(
                webhook_url="https://discord.webhook/test",
                title="Test",
                description="Test desc",
                color=0x00FF00,
            )
            assert result is False


# =============================================================================
# run_embedded_api 테스트
# =============================================================================


class TestRunEmbeddedApi:
    """run_embedded_api 함수 테스트"""

    @pytest.mark.asyncio
    async def test_run_embedded_api(self):
        """FastAPI 내장 서버 실행"""
        from src.main import run_embedded_api

        mock_app = MagicMock()

        # uvicorn is imported inside the function, so we patch it at the module level
        import uvicorn as real_uvicorn
        with patch.dict("sys.modules", {"uvicorn": MagicMock()}) as _:
            import sys
            mock_uvicorn = sys.modules["uvicorn"]

            mock_config_obj = MagicMock()
            mock_uvicorn.Config.return_value = mock_config_obj

            mock_server = MagicMock()
            mock_server.serve = AsyncMock()
            mock_uvicorn.Server.return_value = mock_server

            await run_embedded_api(mock_app, host="0.0.0.0", port=8080)

            mock_uvicorn.Config.assert_called_once_with(
                mock_app, host="0.0.0.0", port=8080, log_level="info"
            )
            mock_server.serve.assert_called_once()

        # Restore real uvicorn
        sys.modules["uvicorn"] = real_uvicorn


# =============================================================================
# main() 함수 테스트
# =============================================================================


class TestMain:
    """main() 함수 테스트"""

    @pytest.fixture
    def mock_config(self):
        """Mock TradingConfig"""
        config = MagicMock()
        config.binance_api_key = "test_key"
        config.binance_secret_key = "test_secret"
        config.gemini_api_key = "test_gemini"
        config.discord_webhook_url = "https://discord.webhook/test"
        config.database_url = None
        config.loop_interval_seconds = 300
        config.enable_redis_state = False
        config.redis_url = None
        config.redis_password = None
        config.redis_db = 0
        config.discord_bot_token = None
        config.bot_name = "test-bot"
        config.symbol = "BTCUSDT"
        config.leverage = 10
        config.position_size_pct = 0.05
        config.take_profit_pct = 0.004
        config.stop_loss_pct = 0.004
        config.time_cut_minutes = 120
        config.binance_testnet = True
        return config

    @pytest.mark.asyncio
    async def test_main_no_redis_no_db_no_discord(self, mock_config):
        """Redis, DB, Discord 없는 기본 main"""
        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.create_app") as mock_create_app:
                    mock_create_app.return_value = MagicMock()
                    with patch("src.main.send_discord_embed", new_callable=AsyncMock) as mock_embed:
                        mock_embed.return_value = True
                        with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                            with patch("src.main.MultiBotManager") as MockManager:
                                mock_manager = MagicMock()
                                mock_manager.run = AsyncMock()
                                mock_manager.stop_all = AsyncMock()
                                mock_manager.add_bot = MagicMock()
                                MockManager.return_value = mock_manager

                                # shutdown_event를 즉시 설정하기 위해 시그널 핸들러 모킹
                                with patch("src.main.signal") as mock_signal_module:
                                    with patch("src.main.asyncio.Event") as MockEvent:
                                        mock_event = MagicMock()
                                        mock_event.wait = AsyncMock(
                                            side_effect=asyncio.CancelledError()
                                        )
                                        MockEvent.return_value = mock_event

                                        await asyncio.wait_for(
                                            self._run_main(),
                                            timeout=5.0,
                                        )

    async def _run_main(self):
        """main 실행 헬퍼"""
        from src.main import main
        try:
            await main()
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_main_with_redis_enabled(self, mock_config):
        """Redis가 활성화된 main"""
        mock_config.enable_redis_state = True
        mock_config.redis_url = "redis://localhost:6379"

        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.disconnect = AsyncMock()

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.create_redis_manager", new_callable=AsyncMock, return_value=mock_redis):
                with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_redis_connection_failure(self, mock_config):
        """Redis 연결 실패"""
        mock_config.enable_redis_state = True
        mock_config.redis_url = "redis://localhost:6379"

        with patch("src.main.get_config", return_value=mock_config):
            with patch(
                "src.main.create_redis_manager",
                new_callable=AsyncMock,
                side_effect=Exception("Redis connection failed"),
            ):
                with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_with_database_url(self, mock_config):
        """database_url이 있는 main"""
        mock_config.database_url = "postgresql://test@localhost/test"

        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.TradeHistoryDB", return_value=mock_db):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

                                    mock_db.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_database_connection_failure(self, mock_config):
        """DB 연결 실패"""
        mock_config.database_url = "postgresql://test@localhost/test"

        mock_db = MagicMock()
        mock_db.connect = AsyncMock(side_effect=Exception("DB error"))
        mock_db.disconnect = AsyncMock()

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.TradeHistoryDB", return_value=mock_db):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_with_yaml_configs(self, mock_config):
        """YAML 봇 설정이 있는 main"""
        from src.bot_config import BotConfig

        yaml_configs = [
            BotConfig(bot_name="yaml-bot-1", symbol="BTCUSDT", is_active=True),
            BotConfig(bot_name="yaml-bot-2", symbol="ETHUSDT", is_active=True),
            BotConfig(bot_name="yaml-bot-3", symbol="SOLUSDT", is_active=False),
        ]

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=(yaml_configs, MagicMock())):
                with patch("src.main.create_app") as mock_create_app:
                    mock_create_app.return_value = MagicMock()
                    with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                        with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                            with patch("src.main.MultiBotManager") as MockManager:
                                mock_manager = MagicMock()
                                mock_manager.run = AsyncMock()
                                mock_manager.stop_all = AsyncMock()
                                mock_manager.add_bot = MagicMock()
                                MockManager.return_value = mock_manager

                                with patch("src.main.signal"):
                                    with patch("src.main.asyncio.Event") as MockEvent:
                                        mock_event = MagicMock()
                                        mock_event.wait = AsyncMock(
                                            side_effect=asyncio.CancelledError()
                                        )
                                        MockEvent.return_value = mock_event

                                        try:
                                            await asyncio.wait_for(
                                                self._run_main(),
                                                timeout=5.0,
                                            )
                                        except asyncio.TimeoutError:
                                            pass

                                # 활성 봇만 추가됨 (2개)
                                assert mock_manager.add_bot.call_count == 2

    @pytest.mark.asyncio
    async def test_main_with_discord_bot(self, mock_config):
        """Discord 봇 토큰이 있는 main"""
        mock_config.discord_bot_token = "valid_discord_token"

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.create_app") as mock_create_app:
                    mock_create_app.return_value = MagicMock()
                    with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                        with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                            with patch("src.main.start_discord_bot", new_callable=AsyncMock) as mock_discord:
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_discord_bot_disabled(self, mock_config):
        """Discord 봇 토큰이 placeholder인 경우"""
        mock_config.discord_bot_token = "your_bot_token_here"

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.create_app") as mock_create_app:
                    mock_create_app.return_value = MagicMock()
                    with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                        with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                            with patch("src.main.start_discord_bot", new_callable=AsyncMock) as mock_discord:
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

                                # Discord start가 호출되지 않아야 함
                                mock_discord.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_redis_not_connected(self, mock_config):
        """Redis가 생성됐지만 연결 안됨"""
        mock_config.enable_redis_state = True
        mock_config.redis_url = "redis://localhost:6379"

        mock_redis = MagicMock()
        mock_redis.is_connected = False

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.create_redis_manager", new_callable=AsyncMock, return_value=mock_redis):
                with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_discord_start_exception(self, mock_config):
        """Discord 봇 시작 중 예외"""
        mock_config.discord_bot_token = "valid_token"

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.create_app") as mock_create_app:
                    mock_create_app.return_value = MagicMock()
                    with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                        with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                            with patch(
                                "src.main.start_discord_bot",
                                side_effect=Exception("Discord init error"),
                            ):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

    @pytest.mark.asyncio
    async def test_main_shutdown_with_redis_cleanup(self, mock_config):
        """종료 시 Redis 연결 해제"""
        mock_config.enable_redis_state = True
        mock_config.redis_url = "redis://localhost:6379"

        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.disconnect = AsyncMock()

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.create_redis_manager", new_callable=AsyncMock, return_value=mock_redis):
                with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

                                    mock_redis.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_shutdown_with_db_cleanup(self, mock_config):
        """종료 시 DB 연결 해제"""
        mock_config.database_url = "postgresql://test@localhost/test"

        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        with patch("src.main.get_config", return_value=mock_config):
            with patch("src.main.load_bots_from_yaml_optional", return_value=([], None)):
                with patch("src.main.TradeHistoryDB", return_value=mock_db):
                    with patch("src.main.create_app") as mock_create_app:
                        mock_create_app.return_value = MagicMock()
                        with patch("src.main.send_discord_embed", new_callable=AsyncMock, return_value=True):
                            with patch("src.main.run_embedded_api", new_callable=AsyncMock):
                                with patch("src.main.MultiBotManager") as MockManager:
                                    mock_manager = MagicMock()
                                    mock_manager.run = AsyncMock()
                                    mock_manager.stop_all = AsyncMock()
                                    mock_manager.add_bot = MagicMock()
                                    MockManager.return_value = mock_manager

                                    with patch("src.main.signal"):
                                        with patch("src.main.asyncio.Event") as MockEvent:
                                            mock_event = MagicMock()
                                            mock_event.wait = AsyncMock(
                                                side_effect=asyncio.CancelledError()
                                            )
                                            MockEvent.return_value = mock_event

                                            try:
                                                await asyncio.wait_for(
                                                    self._run_main(),
                                                    timeout=5.0,
                                                )
                                            except asyncio.TimeoutError:
                                                pass

                                    mock_db.disconnect.assert_called_once()
