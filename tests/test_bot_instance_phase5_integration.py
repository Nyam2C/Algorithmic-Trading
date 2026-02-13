"""
Phase 5 통합 테스트: bot_instance.py 추가 기능
- Task #4: IndicatorScorer 연결
- Task #5: AuditLogManager 통합
- Task #6: SignalTracker DB 풀 연결
- Task #7: inject_signal 및 n8n 연동
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance

# =============================================================================
# 공통 Fixtures
# =============================================================================


@pytest.fixture
def bot_config():
    return BotConfig(
        bot_id=uuid4(),
        bot_name="phase5-test",
        symbol="BTCUSDT",
        risk_level="medium",
        is_testnet=True,
        is_active=True,
    )


@pytest.fixture
def mock_binance():
    client = MagicMock()
    client.connect = AsyncMock()
    client.get_current_price = AsyncMock(return_value=50000.0)
    client.get_klines = AsyncMock(
        return_value=[
            [1234567890000, "49000", "51000", "48500", "50000", "100", 0, 0, 0, 0, 0, 0],
        ]
        * 24
    )
    client.get_ticker_24h = AsyncMock(
        return_value={"volume": "10000", "priceChangePercent": "1.5"}
    )
    client.get_position = AsyncMock(return_value=None)
    client.set_leverage = AsyncMock(return_value=True)
    client.create_market_order = AsyncMock(
        return_value={"orderId": "12345", "origQty": "0.001"}
    )
    client.close_position = AsyncMock(return_value={"orderId": "12346"})
    client.get_account_balance = AsyncMock(return_value={"available": 10000.0})
    return client


@pytest.fixture
def mock_trade_db():
    db = MagicMock()
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()
    db.add_entry = AsyncMock(return_value="trade-123")
    db.add_exit = AsyncMock()
    db.pool = MagicMock()  # DB pool attribute
    return db


def _make_bot(bot_config, **kwargs):
    defaults = {
        "config": bot_config,
        "binance_api_key": "test_key",
        "binance_secret_key": "test_secret",
    }
    defaults.update(kwargs)
    return BotInstance(**defaults)


# =============================================================================
# Task #4: IndicatorScorer → EnsembleSignalGenerator 연결 테스트
# =============================================================================


class TestIndicatorScorerConnection:
    """Task #4: IndicatorScorer 연결 테스트"""

    @pytest.mark.asyncio
    async def test_scorer_connected_when_ensemble_enabled(self, mock_binance):
        """앙상블 활성화 시 IndicatorScorer가 연결됨"""
        config = BotConfig(
            bot_name="scorer-test",
            symbol="BTCUSDT",
            use_ensemble=True,
        )
        instance = _make_bot(config, binance_client=mock_binance)

        await instance._initialize()

        assert instance._ensemble_generator is not None
        # scorer가 연결되었는지 확인
        assert instance._ensemble_generator._scoring is not None

    @pytest.mark.asyncio
    async def test_scorer_not_connected_when_ensemble_disabled(
        self, bot_config, mock_binance
    ):
        """앙상블 비활성화 시 IndicatorScorer 연결 안 됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()
        assert instance._ensemble_generator is None

    @pytest.mark.asyncio
    async def test_ensemble_with_scorer_generates_signal(self, mock_binance):
        """IndicatorScorer 연결 후 앙상블 시그널 생성"""
        config = BotConfig(
            bot_name="ensemble-scorer-test",
            symbol="BTCUSDT",
            use_ensemble=True,
        )
        instance = _make_bot(config, binance_client=mock_binance)
        await instance._initialize()

        # 앙상블 generate_ensemble_signal을 모킹
        mock_result = MagicMock()
        mock_result.final_signal = "LONG"
        mock_result.consensus_ratio = 0.75
        instance._ensemble_generator.generate_ensemble_signal = AsyncMock(
            return_value=mock_result
        )

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 25.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.5,
            }
            await instance._execute_single_loop()

        instance._ensemble_generator.generate_ensemble_signal.assert_called_once()
        assert instance._last_signal == "LONG"


# =============================================================================
# Task #5: AuditLogManager 통합 테스트
# =============================================================================


class TestAuditLogIntegration:
    """Task #5: AuditLogManager 통합 테스트"""

    def test_audit_log_initialized_as_none(self, bot_config):
        """__init__에서 audit_log가 None으로 초기화됨"""
        instance = _make_bot(bot_config)
        assert instance._audit_log is None

    @pytest.mark.asyncio
    async def test_audit_log_initialized_on_init(self, bot_config, mock_binance):
        """_initialize에서 AuditLogManager가 초기화됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()
        assert instance._audit_log is not None

    @pytest.mark.asyncio
    async def test_audit_log_initialized_with_db_pool(
        self, bot_config, mock_binance, mock_trade_db
    ):
        """DB가 있으면 pool이 전달됨"""
        instance = _make_bot(
            bot_config, binance_client=mock_binance, trade_db=mock_trade_db
        )
        await instance._initialize()
        assert instance._audit_log is not None
        assert instance._audit_log._db_pool is mock_trade_db.pool

    @pytest.mark.asyncio
    async def test_audit_log_on_trade_open(
        self, bot_config, mock_binance, mock_trade_db
    ):
        """포지션 오픈 시 감사 로그 기록"""
        instance = _make_bot(
            bot_config, binance_client=mock_binance, trade_db=mock_trade_db
        )
        await instance._initialize()

        # audit_log 모킹
        instance._audit_log = MagicMock()
        instance._audit_log.log_trade_open = AsyncMock()

        instance._executor.open_position = AsyncMock(
            return_value={"orderId": "123", "origQty": "0.001"}
        )
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "trade_id": None,
        }

        await instance._open_position("LONG", 50000.0)
        instance._audit_log.log_trade_open.assert_called_once_with(
            "phase5-test", "LONG", 0.001, 50000.0
        )

    @pytest.mark.asyncio
    async def test_audit_log_on_trade_close(self, bot_config, mock_binance):
        """포지션 클로즈 시 감사 로그 기록"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        instance._audit_log = MagicMock()
        instance._audit_log.log_trade_close = AsyncMock()

        position = {"side": "LONG", "entry_price": 49000.0, "position_amt": 0.001}
        instance._executor.get_position = AsyncMock(return_value=position)
        instance._executor.close_position = AsyncMock(return_value={"orderId": "456"})
        instance._executor.calculate_pnl_pct = MagicMock(return_value=2.0)
        instance._executor.current_position = None

        await instance._close_position(50000.0, "TP")
        instance._audit_log.log_trade_close.assert_called_once()
        call_args = instance._audit_log.log_trade_close.call_args
        assert call_args[0][0] == "phase5-test"
        assert call_args[0][1] == "LONG"
        assert call_args[0][2] == "TP"

    @pytest.mark.asyncio
    async def test_audit_log_on_risk_halt(self, bot_config):
        """리스크 한도 도달 시 감사 로그 기록"""
        instance = _make_bot(bot_config)
        instance._audit_log = MagicMock()
        instance._audit_log.log_risk_halt = AsyncMock()

        await instance._notify_risk_halt("일일 손실 한도 초과")
        instance._audit_log.log_risk_halt.assert_called_once_with(
            "phase5-test", "일일 손실 한도 초과"
        )

    @pytest.mark.asyncio
    async def test_audit_log_on_emergency_close(self, bot_config, mock_binance):
        """긴급 청산 시 감사 로그 기록"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        instance._audit_log = MagicMock()
        instance._audit_log.log_emergency_close = AsyncMock()
        instance._emergency_close = True
        instance._close_position = AsyncMock(return_value=None)

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 45.0,
                "ma_7": 49500.0,
                "volume_ratio": 1.1,
            }
            await instance._execute_single_loop()

        instance._audit_log.log_emergency_close.assert_called_once_with(
            "phase5-test", "수동 긴급 청산 요청"
        )

    @pytest.mark.asyncio
    async def test_audit_log_error_suppressed(self, bot_config, mock_binance):
        """감사 로그 에러가 억제됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        instance._audit_log = MagicMock()
        instance._audit_log.log_trade_open = AsyncMock(
            side_effect=Exception("audit error")
        )

        instance._executor.open_position = AsyncMock(
            return_value={"orderId": "123", "origQty": "0.001"}
        )
        instance._executor.current_position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "trade_id": None,
        }

        # 에러 없이 완료되어야 함
        result = await instance._open_position("LONG", 50000.0)
        assert result is not None

    @pytest.mark.asyncio
    async def test_audit_log_not_called_when_none(self, bot_config, mock_binance):
        """audit_log가 None이면 호출 안 됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()
        instance._audit_log = None

        instance._executor.open_position = AsyncMock(
            return_value={"orderId": "123", "origQty": "0.001"}
        )
        instance._executor.current_position = None

        # 에러 없이 완료
        result = await instance._open_position("LONG", 50000.0)
        assert result is not None


# =============================================================================
# Task #6: SignalTracker DB 풀 연결 테스트
# =============================================================================


class TestSignalTrackerDBPool:
    """Task #6: SignalTracker DB 연결 테스트"""

    @pytest.mark.asyncio
    async def test_signal_tracker_connected_to_db_pool(
        self, bot_config, mock_binance, mock_trade_db
    ):
        """DB가 있으면 SignalTracker에 pool이 연결됨"""
        instance = _make_bot(
            bot_config, binance_client=mock_binance, trade_db=mock_trade_db
        )
        await instance._initialize()

        assert instance._signal_tracker.db_pool is mock_trade_db.pool

    @pytest.mark.asyncio
    async def test_signal_tracker_stays_in_memory_without_db(
        self, bot_config, mock_binance
    ):
        """DB가 없으면 SignalTracker는 인메모리로 유지"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        assert instance._signal_tracker.db_pool is None

    @pytest.mark.asyncio
    async def test_signal_tracker_stays_in_memory_without_pool(
        self, bot_config, mock_binance
    ):
        """DB는 있지만 pool이 None이면 인메모리로 유지"""
        mock_db = MagicMock()
        mock_db.pool = None
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        instance = _make_bot(
            bot_config, binance_client=mock_binance, trade_db=mock_db
        )
        await instance._initialize()

        assert instance._signal_tracker.db_pool is None


# =============================================================================
# Task #7: inject_signal 테스트
# =============================================================================


class TestInjectSignal:
    """Task #7: inject_signal 테스트"""

    def test_inject_signal_long(self, bot_config):
        """LONG 시그널 주입"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({
            "signal": "LONG",
            "source": "n8n",
            "confidence": 0.9,
        })
        assert result is True
        assert instance._injected_signal is not None
        assert instance._injected_signal["signal"] == "LONG"

    def test_inject_signal_short(self, bot_config):
        """SHORT 시그널 주입"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({
            "signal": "SHORT",
            "source": "external",
        })
        assert result is True

    def test_inject_signal_wait(self, bot_config):
        """WAIT 시그널 주입"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({"signal": "WAIT"})
        assert result is True

    def test_inject_signal_invalid(self, bot_config):
        """유효하지 않은 시그널 주입 거부"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({"signal": "INVALID"})
        assert result is False
        assert instance._injected_signal is None

    def test_inject_signal_empty(self, bot_config):
        """빈 시그널 주입 거부"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({})
        assert result is False

    def test_inject_signal_case_insensitive(self, bot_config):
        """대소문자 무관하게 처리"""
        instance = _make_bot(bot_config)
        result = instance.inject_signal({"signal": "long"})
        assert result is True

    @pytest.mark.asyncio
    async def test_injected_signal_used_in_loop(self, bot_config, mock_binance):
        """주입된 시그널이 루프에서 우선 사용됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        # 시그널 주입
        instance.inject_signal({
            "signal": "SHORT",
            "source": "n8n_webhook",
            "confidence": 0.95,
        })

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 50.0,
                "ma_7": 50000.0,
                "volume_ratio": 1.0,
            }
            await instance._execute_single_loop()

        assert instance._last_signal == "SHORT"
        # 주입 후 _injected_signal이 None으로 클리어됨
        assert instance._injected_signal is None

    @pytest.mark.asyncio
    async def test_injected_signal_cleared_after_use(self, bot_config, mock_binance):
        """주입 시그널은 한 번 사용 후 제거됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        instance.inject_signal({"signal": "LONG", "source": "test"})

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 50.0,
                "ma_7": 50000.0,
                "volume_ratio": 1.0,
            }
            # 첫 루프: 주입 시그널 사용
            await instance._execute_single_loop()
            assert instance._last_signal == "LONG"

            # 두 번째 루프: 일반 시그널 생성
            await instance._execute_single_loop()
            # 규칙 기반 시그널로 전환됨 (값은 달라질 수 있음)
            assert instance._injected_signal is None

    @pytest.mark.asyncio
    async def test_injected_signal_source_recorded(self, bot_config, mock_binance):
        """주입 시그널의 source가 기록됨"""
        instance = _make_bot(bot_config, binance_client=mock_binance)
        await instance._initialize()

        instance.inject_signal({"signal": "LONG", "source": "n8n"})

        with patch("src.bot_instance.analyze_market") as mock_analyze:
            mock_analyze.return_value = {
                "rsi": 50.0,
                "ma_7": 50000.0,
                "volume_ratio": 1.0,
            }
            await instance._execute_single_loop()

        # 시그널 트래커에 기록 확인
        signals = instance._signal_tracker._in_memory_signals
        # 마지막 기록된 시그널의 source 확인
        if signals:
            last_record = list(signals.values())[-1]
            assert "injected" in last_record.source

    def test_injected_signal_attr_exists(self, bot_config):
        """_injected_signal 속성이 __init__에서 초기화됨"""
        instance = _make_bot(bot_config)
        assert hasattr(instance, "_injected_signal")
        assert instance._injected_signal is None


# =============================================================================
# n8n 라우트 inject_signal 통합 테스트
# =============================================================================


class TestN8NSignalInjection:
    """n8n.py inject_signal 연동 테스트"""

    @pytest.mark.asyncio
    async def test_n8n_signal_route_calls_inject(self):
        """n8n 시그널 라우트가 bot.inject_signal을 호출"""
        from src.api.routes.n8n import receive_signal
        from src.api.schemas.n8n import N8NSignalPayload

        mock_bot = MagicMock()
        mock_bot.inject_signal = MagicMock(return_value=True)

        mock_manager = MagicMock()
        mock_manager.get_bot = MagicMock(return_value=mock_bot)

        payload = N8NSignalPayload(
            signal="LONG",
            source="n8n_test",
            bot_name="test-bot",
        )

        result = await receive_signal(payload, mock_manager, "valid")

        mock_bot.inject_signal.assert_called_once()
        call_data = mock_bot.inject_signal.call_args[0][0]
        assert call_data["signal"] == "LONG"
        assert call_data["source"] == "n8n_test"
        assert "injected to 1 bot(s)" in result.message

    @pytest.mark.asyncio
    async def test_n8n_signal_route_all_bots(self):
        """전체 봇에 시그널 주입"""
        from src.api.routes.n8n import receive_signal
        from src.api.schemas.n8n import N8NSignalPayload

        mock_bot1 = MagicMock()
        mock_bot1.inject_signal = MagicMock(return_value=True)
        mock_bot2 = MagicMock()
        mock_bot2.inject_signal = MagicMock(return_value=True)

        mock_manager = MagicMock()
        mock_manager.bots = {"bot1": mock_bot1, "bot2": mock_bot2}

        payload = N8NSignalPayload(
            signal="SHORT",
            source="external",
        )

        result = await receive_signal(payload, mock_manager, "valid")

        mock_bot1.inject_signal.assert_called_once()
        mock_bot2.inject_signal.assert_called_once()
        assert "injected to 2 bot(s)" in result.message
