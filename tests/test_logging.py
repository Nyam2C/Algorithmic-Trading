"""
JSON 로깅 모듈 테스트

JSON 포맷, 민감정보 마스킹 기능을 테스트합니다.
"""
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.utils.logging import (
    JSONFormatter,
    disable_json_logging,
    enable_json_logging,
    get_structured_logger,
    is_json_logging_enabled,
    mask_dict_sensitive_data,
    mask_sensitive_data,
    setup_json_logging,
    setup_logging_from_env,
)


class TestMaskSensitiveData:
    """민감정보 마스킹 텍스트 테스트"""

    def test_mask_api_key(self):
        """API 키 마스킹 테스트"""
        text = "api_key=abcd1234efgh5678ijkl"
        result = mask_sensitive_data(text)
        assert "abcd1234" not in result
        assert "***MASKED***" in result

    def test_mask_secret_key(self):
        """시크릿 키 마스킹 테스트"""
        text = "secret_key: 'xyz9876543210abc'"
        result = mask_sensitive_data(text)
        assert "xyz987" not in result
        assert "***MASKED***" in result

    def test_mask_password(self):
        """비밀번호 마스킹 테스트"""
        text = "password=mysecretpassword123"
        result = mask_sensitive_data(text)
        assert "mysecretpassword" not in result
        assert "***MASKED***" in result

    def test_mask_token(self):
        """토큰 마스킹 테스트"""
        text = "token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0'"
        result = mask_sensitive_data(text)
        assert "eyJhbGciOiJ" not in result
        assert "***MASKED***" in result

    def test_mask_webhook_url(self):
        """웹훅 URL 마스킹 테스트"""
        text = "webhook_url=https://discord.com/api/webhooks/123456789/abcdefghij"
        result = mask_sensitive_data(text)
        assert "discord.com" not in result
        assert "***MASKED***" in result

    def test_mask_binance_api_key(self):
        """Binance API 키 (64자) 마스킹 테스트"""
        # 64자 키 (Binance API 키 형식)
        key = "a" * 64
        result = mask_sensitive_data(f"key={key}")
        assert key not in result
        assert "***MASKED_KEY***" in result

    def test_no_mask_for_normal_text(self):
        """일반 텍스트는 마스킹하지 않음"""
        text = "This is a normal log message without sensitive data"
        result = mask_sensitive_data(text)
        assert result == text

    def test_multiple_sensitive_values(self):
        """여러 민감정보 동시 마스킹"""
        text = "api_key=key123456789 password=secret123 token=tokenvalue123456789012345"
        result = mask_sensitive_data(text)
        assert "key12345" not in result
        assert "secret123" not in result
        assert "tokenvalue" not in result


class TestMaskDictSensitiveData:
    """민감정보 마스킹 딕셔너리 테스트"""

    def test_mask_dict_api_key(self):
        """딕셔너리 API 키 마스킹"""
        data = {
            "api_key": "myapikey123456",
            "message": "Hello",
        }
        result = mask_dict_sensitive_data(data)
        assert result["api_key"] == "***MASKED***"
        assert result["message"] == "Hello"

    def test_mask_dict_binance_keys(self):
        """Binance API 키 마스킹"""
        data = {
            "binance_api_key": "testkey123",
            "binance_secret_key": "testsecret456",
            "symbol": "BTCUSDT",
        }
        result = mask_dict_sensitive_data(data)
        assert result["binance_api_key"] == "***MASKED***"
        assert result["binance_secret_key"] == "***MASKED***"
        assert result["symbol"] == "BTCUSDT"

    def test_mask_dict_nested(self):
        """중첩 딕셔너리 마스킹"""
        data = {
            "config": {
                "api_key": "nestedkey",
                "setting": "value",
            },
            "name": "test",
        }
        result = mask_dict_sensitive_data(data)
        assert result["config"]["api_key"] == "***MASKED***"
        assert result["config"]["setting"] == "value"
        assert result["name"] == "test"

    def test_mask_dict_string_values(self):
        """문자열 값 내 민감정보 마스킹"""
        data = {
            "log": "Connected with api_key=abc123456789def",
        }
        result = mask_dict_sensitive_data(data)
        assert "abc12345" not in result["log"]

    def test_mask_dict_preserves_non_sensitive(self):
        """비민감 데이터 보존"""
        data = {
            "count": 10,
            "enabled": True,
            "items": [1, 2, 3],
        }
        result = mask_dict_sensitive_data(data)
        assert result["count"] == 10
        assert result["enabled"] is True
        assert result["items"] == [1, 2, 3]


class TestJSONFormatter:
    """JSON 포매터 테스트"""

    @pytest.fixture
    def formatter(self):
        """JSON 포매터 생성"""
        return JSONFormatter(mask_sensitive=True)

    @pytest.fixture
    def sample_record(self):
        """샘플 로그 레코드"""
        return {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": "test.module",
            "message": "Test message",
            "file": MagicMock(name="test.py"),
            "line": 42,
            "function": "test_function",
            "extra": {"bot_name": "btc-bot", "price": 50000.0},
            "exception": None,
        }

    def test_format_basic_record(self, formatter, sample_record):
        """기본 레코드 포맷 테스트"""
        sample_record["level"].name = "INFO"
        sample_record["file"].name = "test.py"

        result = formatter(sample_record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test.module"
        assert "timestamp" in parsed

    def test_format_with_extra_context(self, formatter, sample_record):
        """추가 컨텍스트 포함 테스트"""
        sample_record["level"].name = "INFO"
        sample_record["file"].name = "test.py"

        result = formatter(sample_record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert parsed["bot_name"] == "btc-bot"
        assert parsed["price"] == 50000.0

    def test_format_masks_sensitive_data(self, formatter, sample_record):
        """민감정보 마스킹 테스트"""
        sample_record["level"].name = "INFO"
        sample_record["file"].name = "test.py"
        sample_record["message"] = "Connecting with api_key=secret123456789"

        result = formatter(sample_record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert "secret12345" not in parsed["message"]
        assert "***MASKED***" in parsed["message"]

    def test_format_without_masking(self, sample_record):
        """마스킹 비활성화 테스트"""
        formatter = JSONFormatter(mask_sensitive=False)
        sample_record["level"].name = "INFO"
        sample_record["file"].name = "test.py"
        sample_record["message"] = "Connecting with api_key=secret123456789"

        result = formatter(sample_record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        # 마스킹 비활성화 시 원본 유지
        assert "secret123456789" in parsed["message"]

    def test_format_timestamp_iso8601(self, formatter, sample_record):
        """타임스탬프 ISO8601 형식 테스트"""
        sample_record["level"].name = "INFO"
        sample_record["file"].name = "test.py"

        result = formatter(sample_record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        # ISO8601 형식: 2024-01-01T12:00:00.000Z
        assert "T" in parsed["timestamp"]
        assert parsed["timestamp"].endswith("Z")


class TestSetupJsonLogging:
    """setup_json_logging 함수 테스트"""

    def test_setup_enables_json_logging(self):
        """JSON 로깅 설정 테스트"""
        # 이 테스트는 실제 로거 설정을 변경하므로 주의
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()

            setup_json_logging(
                log_level="DEBUG",
                enable_file_logging=False,
                enable_json_stdout=True,
                mask_sensitive=True,
            )

            mock_logger.remove.assert_called()
            mock_logger.add.assert_called()


class TestGetStructuredLogger:
    """get_structured_logger 함수 테스트"""

    def test_returns_bound_logger(self):
        """바인딩된 로거 반환 테스트"""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind = MagicMock(return_value=mock_bound)

            result = get_structured_logger(
                "trading",
                bot_name="btc-bot",
                symbol="BTCUSDT"
            )

            mock_logger.bind.assert_called_once_with(
                logger_name="trading",
                bot_name="btc-bot",
                symbol="BTCUSDT"
            )
            assert result == mock_bound


class TestFeatureFlags:
    """Feature flag 테스트"""

    def test_enable_disable_json_logging(self):
        """JSON 로깅 활성화/비활성화 토글 테스트"""
        # 초기 상태 확인 (side effect only)
        _ = is_json_logging_enabled()

        # 활성화
        enable_json_logging()
        assert is_json_logging_enabled() is True

        # 비활성화
        disable_json_logging()
        assert is_json_logging_enabled() is False

        # 다시 활성화
        enable_json_logging()
        assert is_json_logging_enabled() is True


class TestLoggingIntegration:
    """로깅 통합 테스트"""

    def test_json_output_is_valid(self):
        """JSON 출력이 유효한지 확인"""
        formatter = JSONFormatter(mask_sensitive=True)

        record = {
            "time": datetime.now(timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": "integration.test",
            "message": "Integration test message",
            "file": MagicMock(name="test.py"),
            "line": 100,
            "function": "test_integration",
            "extra": {
                "event": "TEST",
                "value": 42,
                "nested": {"key": "value"},
            },
            "exception": None,
        }
        record["level"].name = "INFO"
        record["file"].name = "test.py"

        result = formatter(record)

        # JSON 파싱 가능해야 함
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        # 필수 필드 존재
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
        assert "logger" in parsed

        # 추가 컨텍스트 존재
        assert parsed["event"] == "TEST"
        assert parsed["value"] == 42

    def test_log_message_with_special_characters(self):
        """특수 문자 포함 메시지 테스트"""
        formatter = JSONFormatter(mask_sensitive=True)

        record = {
            "time": datetime.now(timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "message": '한글 메시지 with "quotes" and \\backslash',
            "file": MagicMock(name="test.py"),
            "line": 1,
            "function": "test",
            "extra": {},
            "exception": None,
        }
        record["level"].name = "INFO"
        record["file"].name = "test.py"

        result = formatter(record)

        # JSON 파싱 가능해야 함
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))
        assert "한글" in parsed["message"]
        assert "quotes" in parsed["message"]


# =============================================================================
# From test_utils_coverage.py: Logging tests
# =============================================================================


class TestJSONFormatterException:
    """JSONFormatter 예외 정보 포맷 테스트 (lines 120-126)"""

    def test_format_with_exception(self):
        """예외 정보 포함 레코드 포맷 (lines 121-126)"""
        formatter = JSONFormatter(mask_sensitive=False)

        exc_info = MagicMock()
        exc_info.type = ValueError
        exc_info.value = ValueError("test error")
        exc_info.traceback = "traceback info"

        record = {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "level": MagicMock(name="ERROR"),
            "name": "test",
            "message": "Error occurred",
            "file": MagicMock(name="test.py"),
            "line": 42,
            "function": "test_func",
            "extra": {},
            "exception": exc_info,
        }
        record["level"].name = "ERROR"
        record["file"].name = "test.py"

        result = formatter(record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test error" in str(parsed["exception"]["value"])
        assert parsed["exception"]["traceback"] == "traceback info"

    def test_format_with_exception_none_type(self):
        """예외 type이 None인 경우 (line 123)"""
        formatter = JSONFormatter(mask_sensitive=False)

        exc_info = MagicMock()
        exc_info.type = None
        exc_info.value = None
        exc_info.traceback = None

        record = {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "level": MagicMock(name="ERROR"),
            "name": "test",
            "message": "Error",
            "file": MagicMock(name="test.py"),
            "line": 1,
            "function": "test",
            "extra": {},
            "exception": exc_info,
        }
        record["level"].name = "ERROR"
        record["file"].name = "test.py"

        result = formatter(record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert parsed["exception"]["type"] is None
        assert parsed["exception"]["value"] is None


class TestSetupJsonLoggingHumanReadable:
    """Human-readable stdout 로깅 (lines 166-172)"""

    def test_setup_human_readable_stdout(self):
        """enable_json_stdout=False 시 human-readable 포맷 (line 167)"""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            setup_json_logging(
                log_level="INFO",
                enable_file_logging=False,
                enable_json_stdout=False,
                mask_sensitive=True,
            )

            mock_logger.remove.assert_called_once()
            # add가 호출되어야 함
            assert mock_logger.add.called


class TestSetupJsonLoggingFileLogging:
    """파일 로깅 설정 (lines 174-198)"""

    def test_setup_with_file_logging(self, tmp_path):
        """파일 로깅 활성화 (lines 176-198)"""
        log_dir = str(tmp_path / "test_logs")

        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            setup_json_logging(
                log_level="DEBUG",
                enable_file_logging=True,
                enable_json_stdout=True,
                mask_sensitive=True,
                log_dir=log_dir,
            )

            mock_logger.remove.assert_called_once()
            # stdout + bot.json.log + error.json.log + trade.json.log + ai_signal.json.log = 5
            assert mock_logger.add.call_count == 5


class TestSetupLoggingFromEnv:
    """환경변수 기반 로깅 설정 (lines 251-268)"""

    def test_setup_from_env_defaults(self):
        """기본 환경변수로 설정 (lines 251-268)"""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            with patch.dict(os.environ, {}, clear=True):
                setup_logging_from_env()

            # 기본값: enable_json=True, enable_file=True
            assert mock_logger.add.called

    def test_setup_from_env_custom_values(self):
        """커스텀 환경변수로 설정"""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            env = {
                "LOG_LEVEL": "DEBUG",
                "ENABLE_JSON_LOGGING": "false",
                "ENABLE_FILE_LOGGING": "false",
                "MASK_SENSITIVE": "false",
                "LOG_DIR": "/tmp/test_logs",
            }
            with patch.dict(os.environ, env, clear=True):
                setup_logging_from_env()

            assert mock_logger.add.called

    def test_setup_from_env_json_enabled(self):
        """JSON 로깅 활성화 환경변수"""
        with patch("src.utils.logging.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            env = {
                "ENABLE_JSON_LOGGING": "true",
                "ENABLE_FILE_LOGGING": "false",
            }
            with patch.dict(os.environ, env, clear=True):
                setup_logging_from_env()

            # enable_json_logging() 호출 확인
            assert is_json_logging_enabled() is True

        # 정리
        disable_json_logging()


class TestJSONFormatterNoFileInfo:
    """파일 정보 없는 레코드 (line 107 분기)"""

    def test_format_without_file_info(self):
        """file이 None인 레코드"""
        formatter = JSONFormatter(mask_sensitive=False)

        record = {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": None,
            "message": "No file info",
            "file": None,
            "line": None,
            "function": None,
            "extra": {},
            "exception": None,
        }
        record["level"].name = "INFO"

        result = formatter(record)
        parsed = json.loads(result.strip().replace("{{", "{").replace("}}", "}"))

        assert "file" not in parsed
        assert parsed["logger"] == "root"
