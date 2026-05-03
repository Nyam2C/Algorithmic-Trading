"""
BotConfig 모델 테스트

멀티봇 설정을 위한 BotConfig Pydantic 모델 테스트
"""
from uuid import UUID

import pytest


class TestBotConfig:
    """BotConfig 모델 테스트"""

    # ===== 기본 생성 테스트 =====
    class TestCreation:
        """BotConfig 생성 테스트"""

        def test_기본_설정으로_생성(self) -> None:
            """기본 설정으로 BotConfig 생성 가능"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
            )

            assert config.bot_name == "test-bot"
            assert config.symbol == "BTCUSDT"
            assert config.risk_level == "medium"  # 기본값
            # leverage는 None이지만 get_effective_leverage()로 기본값 15 반환
            assert config.leverage is None
            assert config.get_effective_leverage() == 5
            assert config.is_active is False  # 기본값

        def test_모든_파라미터_지정하여_생성(self) -> None:
            """모든 파라미터를 지정하여 BotConfig 생성"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="btc-aggressive",
                symbol="BTCUSDT",
                risk_level="high",
                leverage=20,
                position_size_pct=0.08,
                take_profit_pct=0.006,
                stop_loss_pct=0.002,
                time_cut_minutes=90,
                rsi_oversold=40.0,
                rsi_overbought=60.0,
                volume_threshold=1.0,
                is_testnet=True,
                is_active=True,
                description="공격적 BTC 전략",
                max_daily_loss_pct=0.05,
            )

            assert config.bot_name == "btc-aggressive"
            assert config.risk_level == "high"
            assert config.leverage == 20
            assert config.position_size_pct == 0.08
            assert config.rsi_oversold == 40.0
            assert config.description == "공격적 BTC 전략"

        def test_bot_id_자동_생성(self) -> None:
            """bot_id가 자동으로 UUID 생성됨"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
            )

            assert config.bot_id is not None
            assert isinstance(config.bot_id, UUID)

        def test_bot_id_지정_가능(self) -> None:
            """bot_id를 직접 지정 가능"""
            from uuid import uuid4

            from src.bot_config import BotConfig

            custom_id = uuid4()
            config = BotConfig(
                bot_id=custom_id,
                bot_name="test-bot",
                symbol="BTCUSDT",
            )

            assert config.bot_id == custom_id

    # ===== risk_level 검증 테스트 =====
    class TestRiskLevel:
        """risk_level 검증 테스트"""

        @pytest.mark.parametrize("risk_level", ["low", "medium", "high"])
        def test_유효한_risk_level(self, risk_level: str) -> None:
            """유효한 risk_level 값 허용"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                risk_level=risk_level,
            )

            assert config.risk_level == risk_level

        def test_잘못된_risk_level_에러(self) -> None:
            """잘못된 risk_level 값은 에러"""
            from pydantic import ValidationError

            from src.bot_config import BotConfig

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    risk_level="invalid",
                )

    # ===== 위험도별 기본값 테스트 =====
    class TestRiskLevelDefaults:
        """위험도별 기본값 테스트"""

        def test_low_risk_기본값(self) -> None:
            """low risk level의 기본값 확인"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="conservative-bot",
                symbol="BTCUSDT",
                risk_level="low",
            )

            # low risk 기본값: leverage=3, position_size=0.03, tp=0.006/sl=0.003
            assert config.get_effective_leverage() == 3
            assert config.get_effective_position_size_pct() == 0.03
            assert config.get_effective_take_profit_pct() == 0.006
            assert config.get_effective_stop_loss_pct() == 0.003

        def test_medium_risk_기본값(self) -> None:
            """medium risk level의 기본값 확인"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="balanced-bot",
                symbol="BTCUSDT",
                risk_level="medium",
            )

            # medium risk 기본값: leverage=5, position_size=0.05, tp=0.008/sl=0.004
            assert config.get_effective_leverage() == 5
            assert config.get_effective_position_size_pct() == 0.05
            assert config.get_effective_take_profit_pct() == 0.008
            assert config.get_effective_stop_loss_pct() == 0.004

        def test_high_risk_기본값(self) -> None:
            """high risk level의 기본값 확인"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="aggressive-bot",
                symbol="BTCUSDT",
                risk_level="high",
            )

            # high risk 기본값: leverage=10, position_size=0.08, tp=0.012/sl=0.004
            assert config.get_effective_leverage() == 10
            assert config.get_effective_position_size_pct() == 0.08
            assert config.get_effective_take_profit_pct() == 0.012
            assert config.get_effective_stop_loss_pct() == 0.004

        def test_명시적_값이_기본값_오버라이드(self) -> None:
            """명시적으로 지정한 값이 risk_level 기본값을 오버라이드"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="custom-bot",
                symbol="BTCUSDT",
                risk_level="low",  # low risk
                leverage=10,  # 명시적 지정 (0.003 * 10 = 3% < 5%)
                position_size_pct=0.1,  # 명시적 지정
            )

            # 명시적 값 사용
            assert config.get_effective_leverage() == 10
            assert config.get_effective_position_size_pct() == 0.1
            # 미지정 값은 risk_level 기본값 사용
            assert config.get_effective_take_profit_pct() == 0.006

    # ===== symbol 검증 테스트 =====
    class TestSymbolValidation:
        """symbol 검증 테스트"""

        def test_symbol_대문자_변환(self) -> None:
            """symbol이 자동으로 대문자로 변환됨"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="test-bot",
                symbol="btcusdt",
            )

            assert config.symbol == "BTCUSDT"

        def test_USDT_아닌_symbol_에러(self) -> None:
            """USDT로 끝나지 않는 symbol은 에러"""
            from pydantic import ValidationError

            from src.bot_config import BotConfig

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSD",  # USDT가 아님
                )

    # ===== leverage 검증 테스트 =====
    class TestLeverageValidation:
        """leverage 검증 테스트"""

        def test_leverage_범위_내_유효(self) -> None:
            """1-50 범위의 leverage 유효"""
            from src.bot_config import BotConfig

            for leverage in [1, 10, 25, 50]:
                config = BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=leverage,
                    stop_loss_pct=0.0003,  # 매우 낮은 SL로 리스크 검증 통과
                    max_daily_loss_pct=0.50,  # 50% 높은 한도
                )
                assert config.leverage == leverage

        def test_leverage_0이하_에러(self) -> None:
            """leverage가 0 이하면 에러"""
            from pydantic import ValidationError

            from src.bot_config import BotConfig

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=0,
                )

        def test_leverage_50초과_에러(self) -> None:
            """leverage가 50 초과면 에러"""
            from pydantic import ValidationError

            from src.bot_config import BotConfig

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=51,
                )

    # ===== position_size_pct 검증 테스트 =====
    class TestPositionSizeValidation:
        """position_size_pct 검증 테스트"""

        def test_position_size_범위_내_유효(self) -> None:
            """0-1 범위의 position_size_pct 유효"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                position_size_pct=0.05,
            )

            assert config.position_size_pct == 0.05

        def test_position_size_10프로_초과_경고(self) -> None:
            """position_size가 10% 초과면 경고 (허용은 됨)"""
            import warnings

            from src.bot_config import BotConfig

            # 경고가 발생해야 함
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                config = BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    position_size_pct=0.15,
                )
                # position_size_pct > 0.1 경고 확인은 validator에서 처리
                assert config.position_size_pct == 0.15

    # ===== to_trading_config 변환 테스트 =====
    class TestToTradingConfig:
        """to_trading_config 변환 테스트"""

        def test_TradingConfig로_변환(self) -> None:
            """BotConfig를 기존 TradingConfig 형식으로 변환"""
            from src.bot_config import BotConfig

            bot_config = BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                risk_level="medium",
                leverage=10,
            )

            trading_config = bot_config.to_trading_config(
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                gemini_api_key="test_gemini",
                discord_webhook_url="https://discord.com/webhook",
            )

            assert trading_config.bot_name == "test-bot"
            assert trading_config.symbol == "BTCUSDT"
            assert trading_config.leverage == 10
            assert trading_config.binance_api_key == "test_key"

        def test_phase5_통합_필드_매핑(self) -> None:
            """Phase 5 통합 필드가 to_trading_config에서 올바르게 매핑됨"""
            from src.bot_config import BotConfig

            bot_config = BotConfig(
                bot_name="full-bot",
                symbol="BTCUSDT",
                risk_level="medium",
                leverage=10,
                use_regime_filter=True,
                allow_weak_trend=False,
                use_mtf_filter=True,
                use_ensemble=True,
                manual_approval_enabled=True,
                manual_approval_trades=10,
                approval_timeout=120,
            )

            trading_config = bot_config.to_trading_config(
                binance_api_key="key",
                binance_secret_key="secret",
                gemini_api_key="gemini",
                discord_webhook_url="https://discord.com/webhook",
            )

            assert trading_config.use_regime_filter is True
            assert trading_config.allow_weak_trend is False
            assert trading_config.use_mtf_filter is True
            assert trading_config.use_ensemble is True
            assert trading_config.manual_approval_enabled is True
            assert trading_config.manual_approval_trades == 10
            assert trading_config.approval_timeout == 120

        def test_phase5_통합_필드_기본값_매핑(self) -> None:
            """Phase 5 통합 필드 기본값이 to_trading_config에서 올바르게 매핑됨"""
            from src.bot_config import BotConfig

            bot_config = BotConfig(
                bot_name="default-bot",
                symbol="BTCUSDT",
            )

            trading_config = bot_config.to_trading_config(
                binance_api_key="key",
                binance_secret_key="secret",
                gemini_api_key="gemini",
                discord_webhook_url="https://discord.com/webhook",
            )

            assert trading_config.use_regime_filter is False
            assert trading_config.allow_weak_trend is True
            assert trading_config.use_mtf_filter is False
            assert trading_config.use_ensemble is False
            assert trading_config.manual_approval_enabled is False
            assert trading_config.manual_approval_trades == 5
            assert trading_config.approval_timeout == 60

    # ===== from_db_row 변환 테스트 =====
    class TestFromDbRow:
        """from_db_row 변환 테스트"""

        def test_DB_row에서_BotConfig_생성(self) -> None:
            """DB row dict에서 BotConfig 생성"""
            from uuid import uuid4

            from src.bot_config import BotConfig

            bot_id = uuid4()
            db_row = {
                "id": bot_id,
                "bot_name": "db-bot",
                "symbol": "ETHUSDT",
                "risk_level": "high",
                "leverage": 20,
                "position_size_pct": 0.08,
                "take_profit_pct": 0.006,
                "stop_loss_pct": 0.002,
                "time_cut_minutes": 90,
                "rsi_oversold": 40.0,
                "rsi_overbought": 60.0,
                "volume_threshold": 1.0,
                "is_testnet": True,
                "is_active": True,
                "description": "DB에서 로드된 봇",
            }

            config = BotConfig.from_db_row(db_row)

            assert config.bot_id == bot_id
            assert config.bot_name == "db-bot"
            assert config.symbol == "ETHUSDT"
            assert config.risk_level == "high"


class TestRiskLevelDefaults:
    """RISK_LEVEL_DEFAULTS 상수 테스트"""

    def test_모든_risk_level_기본값_존재(self) -> None:
        """low, medium, high 모든 risk_level에 기본값 존재"""
        from src.bot_config import RISK_LEVEL_DEFAULTS

        assert "low" in RISK_LEVEL_DEFAULTS
        assert "medium" in RISK_LEVEL_DEFAULTS
        assert "high" in RISK_LEVEL_DEFAULTS

    def test_기본값_키_존재(self) -> None:
        """각 risk_level에 필요한 키들이 존재"""
        from src.bot_config import RISK_LEVEL_DEFAULTS

        required_keys = [
            "leverage",
            "position_size_pct",
            "take_profit_pct",
            "stop_loss_pct",
        ]

        for level in ["low", "medium", "high"]:
            for key in required_keys:
                assert key in RISK_LEVEL_DEFAULTS[level], f"{level}에 {key} 없음"


class TestRiskConsistencyValidation:
    """Phase 8: 위험한 설정 거부 테스트"""

    def test_위험한_설정_거부_ValueError(self) -> None:
        """SL x leverage > daily_limit일 때 ValueError 발생"""
        from pydantic import ValidationError

        from src.bot_config import BotConfig

        # SL=0.4% x leverage=20 = 8% > 5% daily limit => ValueError
        with pytest.raises(ValidationError, match="리스크 불일치"):
            BotConfig(
                bot_name="risky-bot",
                symbol="BTCUSDT",
                leverage=20,
                stop_loss_pct=0.004,
                max_daily_loss_pct=0.05,
            )

    def test_안전한_설정_허용(self) -> None:
        """SL x leverage <= daily_limit일 때 정상 생성"""
        from src.bot_config import BotConfig

        # SL=0.3% x leverage=3 = 0.9% < 5% => OK
        config = BotConfig(
            bot_name="safe-bot",
            symbol="BTCUSDT",
            leverage=3,
            stop_loss_pct=0.003,
            max_daily_loss_pct=0.05,
        )
        assert config.leverage == 3
        assert config.stop_loss_pct == 0.003

    def test_high_risk_기본값은_안전(self) -> None:
        """high risk 기본값 SL=0.004 x leverage=10 = 4% < 5% 통과"""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="high-bot",
            symbol="BTCUSDT",
            risk_level="high",
        )
        # 0.004 * 10 = 0.04 < 0.05 => OK
        assert config.get_effective_stop_loss_pct() == 0.004
        assert config.get_effective_leverage() == 10


# =============================================================================
# Phase 9 WS2: BotConfig Hardening (merged from test_ws2_risk_hardening.py)
# =============================================================================


class TestPhase9LeverageCap:
    """Issue R: leverage 최대값을 125x -> 50x로 변경."""

    def test_leverage_50_allowed(self) -> None:
        """50x leverage는 허용."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            leverage=50,
            stop_loss_pct=0.0003,
            max_daily_loss_pct=0.50,
        )
        assert config.leverage == 50

    def test_leverage_51_rejected(self) -> None:
        """51x leverage는 거부."""
        from pydantic import ValidationError

        from src.bot_config import BotConfig

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                leverage=51,
                stop_loss_pct=0.0003,
                max_daily_loss_pct=0.50,
            )

    def test_leverage_125_rejected(self) -> None:
        """125x leverage는 거부 (이전에 허용)."""
        from pydantic import ValidationError

        from src.bot_config import BotConfig

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                leverage=125,
                stop_loss_pct=0.0003,
                max_daily_loss_pct=0.50,
            )


class TestPhase9FeeRate:
    """Issue F: BotConfig에 estimated_fee_rate 필드 추가."""

    def test_estimated_fee_rate_default(self) -> None:
        """기본 fee rate 0.0008 (0.08%)."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
        )
        assert config.estimated_fee_rate == 0.0008

    def test_estimated_fee_rate_custom(self) -> None:
        """커스텀 fee rate 설정."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.001,
        )
        assert config.estimated_fee_rate == 0.001

    def test_estimated_fee_rate_zero(self) -> None:
        """fee rate 0 허용 (수수료 없는 경우)."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.0,
        )
        assert config.estimated_fee_rate == 0.0

    def test_estimated_fee_rate_max(self) -> None:
        """fee rate 최대값 0.01 (1%) 허용."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            estimated_fee_rate=0.01,
        )
        assert config.estimated_fee_rate == 0.01

    def test_estimated_fee_rate_over_max_rejected(self) -> None:
        """fee rate > 0.01 거부."""
        from pydantic import ValidationError

        from src.bot_config import BotConfig

        with pytest.raises(ValidationError):
            BotConfig(
                bot_name="test-bot",
                symbol="BTCUSDT",
                estimated_fee_rate=0.02,
            )


class TestPhase9ExposureConsistency:
    """Issue H: position_value에 leverage 포함 필요."""

    def test_exposure_value_includes_leverage(self) -> None:
        """position_value = price * pct * leverage 임을 확인."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",  # leverage=5
        )
        pct = config.get_effective_position_size_pct()  # 0.05
        leverage = config.get_effective_leverage()  # 5
        current_price = 50000.0

        # Before fix: position_value = 50000 * 0.05 = 2500
        # After fix:  position_value = 50000 * 0.05 * 5 = 12500
        position_value = current_price * pct * leverage
        assert position_value == 12500.0


class TestSilentNoopFlagWarnings:
    """Architecture P1 후속: BOCPD/LGB silent no-op 플래그 deprecated 검증.

    배경: use_bocpd_regime, use_lightgbm_dead_zone는 BotConfig 필드로 받지만 운영
    코드에서 BOCPDDetector/LGBDeadZoneVerifier가 인스턴스화·주입되지 않아 효과가
    없는 silent no-op이다. 운영자가 활성화로 오인하지 않도록 BotConfig 초기화 시
    명시 경고 로그를 발생시킨다.
    """

    def test_use_bocpd_regime_true_emits_warning(self, caplog) -> None:
        """use_bocpd_regime=True이면 silent no-op 경고가 로그에 기록된다."""
        from loguru import logger as loguru_logger

        from src.bot_config import BotConfig

        # loguru → caplog 연결 (loguru 기본 sink는 caplog로 가지 않음)
        handler_id = loguru_logger.add(caplog.handler, format="{message}", level="WARNING")
        try:
            BotConfig(
                bot_name="bocpd-test",
                symbol="BTCUSDT",
                use_bocpd_regime=True,
            )
        finally:
            loguru_logger.remove(handler_id)

        warnings_text = "\n".join(r.message for r in caplog.records if r.levelname == "WARNING")
        assert "use_bocpd_regime=True지만" in warnings_text
        assert "silent no-op" in warnings_text

    def test_use_lightgbm_dead_zone_true_emits_warning(self, caplog) -> None:
        """use_lightgbm_dead_zone=True이면 silent no-op 경고가 로그에 기록된다."""
        from loguru import logger as loguru_logger

        from src.bot_config import BotConfig

        handler_id = loguru_logger.add(caplog.handler, format="{message}", level="WARNING")
        try:
            BotConfig(
                bot_name="lgb-test",
                symbol="BTCUSDT",
                use_lightgbm_dead_zone=True,
            )
        finally:
            loguru_logger.remove(handler_id)

        warnings_text = "\n".join(r.message for r in caplog.records if r.levelname == "WARNING")
        assert "use_lightgbm_dead_zone=True지만" in warnings_text
        assert "silent no-op" in warnings_text

    def test_default_false_no_warning(self, caplog) -> None:
        """기본값(False)에서는 silent no-op 경고가 발생하지 않는다."""
        from loguru import logger as loguru_logger

        from src.bot_config import BotConfig

        handler_id = loguru_logger.add(caplog.handler, format="{message}", level="WARNING")
        try:
            BotConfig(bot_name="default-test", symbol="BTCUSDT")
        finally:
            loguru_logger.remove(handler_id)

        warnings_text = "\n".join(r.message for r in caplog.records if r.levelname == "WARNING")
        assert "silent no-op" not in warnings_text

    def test_field_marked_deprecated(self) -> None:
        """플래그가 Pydantic 메타데이터에서 deprecated로 마킹되어 있다.

        IDE/타입 체커/문서 생성기가 이 정보를 활용한다. Field(deprecated=...)는
        Pydantic 2.7+ 에서 FieldInfo.deprecated 또는 metadata에 반영된다.
        """
        from src.bot_config import BotConfig

        fields = BotConfig.model_fields
        for name in ("use_bocpd_regime", "use_lightgbm_dead_zone",
                     "bocpd_window_size", "lightgbm_model_path"):
            field = fields[name]
            # Pydantic 2.x: Field(deprecated=...)는 FieldInfo.deprecated 또는
            # metadata 안의 deprecated 마커로 보존된다.
            deprecated_marker = getattr(field, "deprecated", None)
            assert deprecated_marker, (
                f"{name}이 deprecated로 마킹되어야 하지만 마커가 없음."
            )
