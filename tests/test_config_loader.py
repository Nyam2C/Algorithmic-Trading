"""
YAML 설정 로더 테스트

멀티봇 YAML 설정 파일 로드 및 BotConfig 변환 테스트.
"""
import pytest

from src.config_loader import (
    GlobalConfig,
    BotYamlEntry,
    load_bots_from_yaml,
    load_bots_from_yaml_optional,
)


class TestGlobalConfig:
    """GlobalConfig 모델 테스트"""

    def test_default_values(self):
        """기본값 테스트"""
        config = GlobalConfig()
        assert config.is_testnet is True
        assert config.loop_interval_seconds == 300

    def test_custom_values(self):
        """커스텀 값 테스트"""
        config = GlobalConfig(is_testnet=False, loop_interval_seconds=600)
        assert config.is_testnet is False
        assert config.loop_interval_seconds == 600


class TestBotYamlEntry:
    """BotYamlEntry 모델 테스트"""

    def test_required_fields(self):
        """필수 필드 테스트"""
        entry = BotYamlEntry(name="test-bot", symbol="BTCUSDT", risk_level="medium")
        assert entry.name == "test-bot"
        assert entry.symbol == "BTCUSDT"
        assert entry.risk_level == "medium"
        assert entry.is_active is True  # 기본값

    def test_symbol_uppercase(self):
        """심볼 대문자 변환 테스트"""
        entry = BotYamlEntry(name="test-bot", symbol="btcusdt", risk_level="low")
        assert entry.symbol == "BTCUSDT"

    def test_invalid_risk_level(self):
        """잘못된 risk_level 검증"""
        with pytest.raises(ValueError):
            BotYamlEntry(name="test-bot", symbol="BTCUSDT", risk_level="invalid")

    def test_to_bot_config_with_global(self):
        """BotConfig 변환 (글로벌 설정 적용) 테스트"""
        entry = BotYamlEntry(name="btc-conservative", symbol="BTCUSDT", risk_level="low")
        global_config = GlobalConfig(is_testnet=False, loop_interval_seconds=600)

        bot_config = entry.to_bot_config(global_config)

        assert bot_config.bot_name == "btc-conservative"
        assert bot_config.symbol == "BTCUSDT"
        assert bot_config.risk_level == "low"
        assert bot_config.is_testnet is False  # 글로벌 설정 적용
        assert bot_config.is_active is True

    def test_to_bot_config_default_global(self):
        """BotConfig 변환 (기본 글로벌 설정) 테스트"""
        entry = BotYamlEntry(name="eth-balanced", symbol="ETHUSDT", risk_level="medium")

        bot_config = entry.to_bot_config()

        assert bot_config.bot_name == "eth-balanced"
        assert bot_config.symbol == "ETHUSDT"
        assert bot_config.risk_level == "medium"
        assert bot_config.is_testnet is True  # 기본값
        assert bot_config.is_active is True


class TestLoadBotsFromYaml:
    """YAML 로드 함수 테스트"""

    def test_load_valid_yaml(self, tmp_path):
        """유효한 YAML 파일 로드 테스트"""
        yaml_content = """
global:
  is_testnet: true
  loop_interval_seconds: 300

bots:
  - name: btc-conservative
    symbol: BTCUSDT
    risk_level: low
    is_active: true

  - name: eth-balanced
    symbol: ETHUSDT
    risk_level: medium
    is_active: true

  - name: sol-aggressive
    symbol: SOLUSDT
    risk_level: high
    is_active: false
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, global_config = load_bots_from_yaml(str(yaml_file))

        # 글로벌 설정 확인
        assert global_config.is_testnet is True
        assert global_config.loop_interval_seconds == 300

        # 봇 설정 확인
        assert len(bot_configs) == 3

        # BTC 봇
        btc_bot = bot_configs[0]
        assert btc_bot.bot_name == "btc-conservative"
        assert btc_bot.symbol == "BTCUSDT"
        assert btc_bot.risk_level == "low"
        assert btc_bot.is_active is True
        assert btc_bot.get_effective_leverage() == 10

        # ETH 봇
        eth_bot = bot_configs[1]
        assert eth_bot.bot_name == "eth-balanced"
        assert eth_bot.symbol == "ETHUSDT"
        assert eth_bot.risk_level == "medium"
        assert eth_bot.is_active is True
        assert eth_bot.get_effective_leverage() == 15

        # SOL 봇
        sol_bot = bot_configs[2]
        assert sol_bot.bot_name == "sol-aggressive"
        assert sol_bot.symbol == "SOLUSDT"
        assert sol_bot.risk_level == "high"
        assert sol_bot.is_active is False
        assert sol_bot.get_effective_leverage() == 20

    def test_load_yaml_without_global(self, tmp_path):
        """글로벌 설정 없는 YAML 로드 테스트"""
        yaml_content = """
bots:
  - name: btc-bot
    symbol: BTCUSDT
    risk_level: medium
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, global_config = load_bots_from_yaml(str(yaml_file))

        # 기본 글로벌 설정
        assert global_config.is_testnet is True
        assert global_config.loop_interval_seconds == 300

        # 봇 설정
        assert len(bot_configs) == 1
        assert bot_configs[0].bot_name == "btc-bot"

    def test_load_yaml_file_not_found(self):
        """존재하지 않는 파일 테스트"""
        with pytest.raises(FileNotFoundError):
            load_bots_from_yaml("/nonexistent/path/bots.yaml")

    def test_load_yaml_empty_bots(self, tmp_path):
        """빈 봇 리스트 테스트"""
        yaml_content = """
global:
  is_testnet: false

bots: []
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, global_config = load_bots_from_yaml(str(yaml_file))

        assert len(bot_configs) == 0
        assert global_config.is_testnet is False

    def test_load_yaml_completely_empty_file(self, tmp_path):
        """완전히 빈 YAML 파일 테스트"""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        bot_configs, global_config = load_bots_from_yaml(str(yaml_file))

        # 기본값 적용
        assert len(bot_configs) == 0
        assert global_config.is_testnet is True
        assert global_config.loop_interval_seconds == 300


class TestLoadBotsFromYamlOptional:
    """선택적 YAML 로드 함수 테스트 (하위 호환성)"""

    def test_optional_with_existing_file(self, tmp_path):
        """파일 존재 시 정상 로드"""
        yaml_content = """
bots:
  - name: test-bot
    symbol: BTCUSDT
    risk_level: low
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, global_config = load_bots_from_yaml_optional(str(yaml_file))

        assert len(bot_configs) == 1
        assert bot_configs[0].bot_name == "test-bot"

    def test_optional_file_not_found(self):
        """파일 없을 때 빈 리스트 반환"""
        bot_configs, global_config = load_bots_from_yaml_optional("/nonexistent/bots.yaml")

        assert bot_configs == []
        assert global_config is None

    def test_optional_default_path(self, tmp_path, monkeypatch):
        """기본 경로 사용 테스트"""
        yaml_content = """
bots:
  - name: default-bot
    symbol: ETHUSDT
    risk_level: medium
"""
        # configs 디렉토리 생성
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        yaml_file = configs_dir / "bots.yaml"
        yaml_file.write_text(yaml_content)

        # 현재 작업 디렉토리 변경
        monkeypatch.chdir(tmp_path)

        bot_configs, global_config = load_bots_from_yaml_optional()

        assert len(bot_configs) == 1
        assert bot_configs[0].bot_name == "default-bot"


class TestMultiBotIntegration:
    """멀티봇 통합 테스트"""

    def test_three_bots_different_risk_levels(self, tmp_path):
        """3개 봇, 다른 위험도 설정 테스트"""
        yaml_content = """
global:
  is_testnet: true
  loop_interval_seconds: 300

bots:
  - name: btc-conservative
    symbol: BTCUSDT
    risk_level: low
    is_active: true

  - name: eth-balanced
    symbol: ETHUSDT
    risk_level: medium
    is_active: true

  - name: sol-aggressive
    symbol: SOLUSDT
    risk_level: high
    is_active: true
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, _ = load_bots_from_yaml(str(yaml_file))

        # 각 봇의 효과적인 설정값 확인
        # low: leverage=10, position=3%, tp/sl=0.3%
        btc = bot_configs[0]
        assert btc.get_effective_leverage() == 10
        assert btc.get_effective_position_size_pct() == 0.03
        assert btc.get_effective_take_profit_pct() == 0.003
        assert btc.get_effective_stop_loss_pct() == 0.003

        # medium: leverage=15, position=5%, tp/sl=0.4%
        eth = bot_configs[1]
        assert eth.get_effective_leverage() == 15
        assert eth.get_effective_position_size_pct() == 0.05
        assert eth.get_effective_take_profit_pct() == 0.004
        assert eth.get_effective_stop_loss_pct() == 0.004

        # high: leverage=20, position=8%, tp/sl=0.6%
        sol = bot_configs[2]
        assert sol.get_effective_leverage() == 20
        assert sol.get_effective_position_size_pct() == 0.08
        assert sol.get_effective_take_profit_pct() == 0.006
        assert sol.get_effective_stop_loss_pct() == 0.006

    def test_filter_active_bots(self, tmp_path):
        """활성화된 봇만 필터링 테스트"""
        yaml_content = """
bots:
  - name: active-bot
    symbol: BTCUSDT
    risk_level: low
    is_active: true

  - name: inactive-bot
    symbol: ETHUSDT
    risk_level: medium
    is_active: false
"""
        yaml_file = tmp_path / "bots.yaml"
        yaml_file.write_text(yaml_content)

        bot_configs, _ = load_bots_from_yaml(str(yaml_file))

        active_bots = [b for b in bot_configs if b.is_active]
        assert len(active_bots) == 1
        assert active_bots[0].bot_name == "active-bot"
