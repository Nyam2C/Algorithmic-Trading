"""
Utils 모듈 커버리지 개선 테스트

logging.py: lines 121-122, 167, 176-190, 251-262
retry.py: lines 42, 61-62, 119-120
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.utils.logging import (
    JSONFormatter,
    disable_json_logging,
    is_json_logging_enabled,
    setup_json_logging,
    setup_logging_from_env,
)
from src.utils.retry import async_retry, sync_retry

# =============================================================================
# Logging: Lines 121-122 (exception info in JSONFormatter)
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
        parsed = json.loads(result.strip())

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
        parsed = json.loads(result.strip())

        assert parsed["exception"]["type"] is None
        assert parsed["exception"]["value"] is None


# =============================================================================
# Logging: Line 167 (human-readable stdout)
# =============================================================================

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


# =============================================================================
# Logging: Lines 176-190 (file logging)
# =============================================================================

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
            # stdout + JSON file + error file = 3 add 호출
            assert mock_logger.add.call_count == 3


# =============================================================================
# Logging: Lines 251-262 (setup_logging_from_env)
# =============================================================================

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
        parsed = json.loads(result.strip())

        assert "file" not in parsed
        assert parsed["logger"] == "root"


# =============================================================================
# Retry: Line 42 (CancelledError re-raise)
# =============================================================================

class TestAsyncRetryCancelledError:
    """CancelledError 즉시 전파 (line 42)"""

    @pytest.mark.asyncio
    async def test_cancelled_error_not_retried(self):
        """CancelledError는 즉시 전파 (lines 40-42)"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def cancellable_func():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await cancellable_func()

        assert call_count == 1  # 재시도 없이 즉시 전파


# =============================================================================
# Retry: Lines 61-62 (unreachable last_exception raise)
# =============================================================================

class TestAsyncRetryEdgeCaseLastException:
    """마지막 예외 raise 엣지 케이스 (lines 61-62)

    이 코드는 일반적으로 도달하지 않지만, 방어 코드로 존재.
    max_attempts=0 같은 경우를 시뮬레이션해야 하나 실제로는
    range(1, 0+1)이 빈 범위이므로 for 루프에 진입하지 않음.
    """

    @pytest.mark.asyncio
    async def test_zero_max_attempts(self):
        """max_attempts=0이면 함수가 호출되지 않고 None 반환"""
        call_count = 0

        @async_retry(max_attempts=0, delay=0.01)
        async def never_called():
            nonlocal call_count
            call_count += 1
            return "result"

        # max_attempts=0이면 for 루프 진입 안 함 → None 반환
        result = await never_called()
        assert call_count == 0
        assert result is None


# =============================================================================
# Retry: Lines 119-120 (sync_retry unreachable last_exception raise)
# =============================================================================

class TestSyncRetryEdgeCaseLastException:
    """sync_retry 마지막 예외 raise 엣지 케이스 (lines 119-120)"""

    def test_zero_max_attempts_sync(self):
        """max_attempts=0이면 함수가 호출되지 않고 None 반환"""
        call_count = 0

        @sync_retry(max_attempts=0, delay=0.01)
        def never_called():
            nonlocal call_count
            call_count += 1
            return "result"

        result = never_called()
        assert call_count == 0
        assert result is None


class TestAsyncRetryPreservesArgs:
    """함수 인자 보존 테스트"""

    @pytest.mark.asyncio
    async def test_async_retry_with_kwargs(self):
        """키워드 인자 전달"""
        @async_retry(max_attempts=2, delay=0.01)
        async def func(a, b=10):
            return a + b

        result = await func(5, b=20)
        assert result == 25


class TestSyncRetrySpecificException:
    """sync_retry 특정 예외 필터"""

    def test_sync_non_matching_exception(self):
        """매칭되지 않는 예외는 재시도하지 않음"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong type")

        with pytest.raises(TypeError):
            raise_type_error()

        assert call_count == 1
