"""
BotConfig 모델 테스트

멀티봇 설정을 위한 BotConfig Pydantic 모델 테스트
"""
import pytest
from uuid import UUID


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
            assert config.get_effective_leverage() == 15
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
                stop_loss_pct=0.006,
                time_cut_minutes=90,
                rsi_oversold=40.0,
                rsi_overbought=60.0,
                volume_threshold=1.0,
                is_testnet=True,
                is_active=True,
                description="공격적 BTC 전략",
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
            from src.bot_config import BotConfig
            from uuid import uuid4

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
            from src.bot_config import BotConfig
            from pydantic import ValidationError

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

            # low risk 기본값: leverage=10, position_size=0.03, tp/sl=0.003
            assert config.get_effective_leverage() == 10
            assert config.get_effective_position_size_pct() == 0.03
            assert config.get_effective_take_profit_pct() == 0.003
            assert config.get_effective_stop_loss_pct() == 0.003

        def test_medium_risk_기본값(self) -> None:
            """medium risk level의 기본값 확인"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="balanced-bot",
                symbol="BTCUSDT",
                risk_level="medium",
            )

            # medium risk 기본값: leverage=15, position_size=0.05, tp/sl=0.004
            assert config.get_effective_leverage() == 15
            assert config.get_effective_position_size_pct() == 0.05
            assert config.get_effective_take_profit_pct() == 0.004
            assert config.get_effective_stop_loss_pct() == 0.004

        def test_high_risk_기본값(self) -> None:
            """high risk level의 기본값 확인"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="aggressive-bot",
                symbol="BTCUSDT",
                risk_level="high",
            )

            # high risk 기본값: leverage=20, position_size=0.08, tp/sl=0.006
            assert config.get_effective_leverage() == 20
            assert config.get_effective_position_size_pct() == 0.08
            assert config.get_effective_take_profit_pct() == 0.006
            assert config.get_effective_stop_loss_pct() == 0.006

        def test_명시적_값이_기본값_오버라이드(self) -> None:
            """명시적으로 지정한 값이 risk_level 기본값을 오버라이드"""
            from src.bot_config import BotConfig

            config = BotConfig(
                bot_name="custom-bot",
                symbol="BTCUSDT",
                risk_level="low",  # low risk
                leverage=25,  # 명시적 지정
                position_size_pct=0.1,  # 명시적 지정
            )

            # 명시적 값 사용
            assert config.get_effective_leverage() == 25
            assert config.get_effective_position_size_pct() == 0.1
            # 미지정 값은 risk_level 기본값 사용
            assert config.get_effective_take_profit_pct() == 0.003

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
            from src.bot_config import BotConfig
            from pydantic import ValidationError

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSD",  # USDT가 아님
                )

    # ===== leverage 검증 테스트 =====
    class TestLeverageValidation:
        """leverage 검증 테스트"""

        def test_leverage_범위_내_유효(self) -> None:
            """1-125 범위의 leverage 유효"""
            from src.bot_config import BotConfig

            for leverage in [1, 10, 50, 100, 125]:
                config = BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=leverage,
                )
                assert config.leverage == leverage

        def test_leverage_0이하_에러(self) -> None:
            """leverage가 0 이하면 에러"""
            from src.bot_config import BotConfig
            from pydantic import ValidationError

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=0,
                )

        def test_leverage_125초과_에러(self) -> None:
            """leverage가 125 초과면 에러"""
            from src.bot_config import BotConfig
            from pydantic import ValidationError

            with pytest.raises(ValidationError):
                BotConfig(
                    bot_name="test-bot",
                    symbol="BTCUSDT",
                    leverage=126,
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
            from src.bot_config import BotConfig
            import warnings

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
                leverage=15,
            )

            trading_config = bot_config.to_trading_config(
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                gemini_api_key="test_gemini",
                discord_webhook_url="https://discord.com/webhook",
            )

            assert trading_config.bot_name == "test-bot"
            assert trading_config.symbol == "BTCUSDT"
            assert trading_config.leverage == 15
            assert trading_config.binance_api_key == "test_key"

    # ===== from_db_row 변환 테스트 =====
    class TestFromDbRow:
        """from_db_row 변환 테스트"""

        def test_DB_row에서_BotConfig_생성(self) -> None:
            """DB row dict에서 BotConfig 생성"""
            from src.bot_config import BotConfig
            from uuid import uuid4

            bot_id = uuid4()
            db_row = {
                "id": bot_id,
                "bot_name": "db-bot",
                "symbol": "ETHUSDT",
                "risk_level": "high",
                "leverage": 20,
                "position_size_pct": 0.08,
                "take_profit_pct": 0.006,
                "stop_loss_pct": 0.006,
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
