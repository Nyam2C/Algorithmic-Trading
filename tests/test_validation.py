"""Tests for src.utils.validation module."""

import numpy as np
import pandas as pd
import pytest

from src.utils.validation import sanitize_nan_values, validate_ohlcv_dataframe


class TestValidateOhlcvDataframe:
    """validate_ohlcv_dataframe 테스트"""

    def _make_df(self, n: int = 15) -> pd.DataFrame:
        """헬퍼: 유효한 OHLCV DataFrame 생성"""
        return pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
            "open": [100.0] * n,
            "high": [105.0] * n,
            "low": [95.0] * n,
            "close": [102.0] * n,
            "volume": [1000.0] * n,
        })

    def test_happy_path(self):
        """정상 데이터 통과"""
        df = self._make_df(15)
        result = validate_ohlcv_dataframe(df, min_rows=10)
        assert len(result) == 15
        assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    def test_nan_forward_fill(self):
        """NaN forward-fill 적용"""
        df = self._make_df(15)
        df.loc[2, "close"] = np.nan
        df.loc[5, "open"] = np.nan

        result = validate_ohlcv_dataframe(df, min_rows=10)
        assert len(result) == 15
        # NaN이 forward-fill 되어 이전 값으로 채워짐
        assert not result["close"].isna().any()
        assert not result["open"].isna().any()

    def test_min_rows_raises(self):
        """행 수 부족 시 ValueError"""
        df = self._make_df(3)
        with pytest.raises(ValueError, match="행 수 부족"):
            validate_ohlcv_dataframe(df, min_rows=5)

    def test_timestamp_not_monotonic(self):
        """비순차 타임스탬프 정렬"""
        df = self._make_df(10)
        # 역순으로 섞기
        df = df.iloc[::-1].reset_index(drop=True)
        result = validate_ohlcv_dataframe(df, min_rows=5)
        assert result["timestamp"].is_monotonic_increasing

    def test_missing_column_raises(self):
        """필수 열 누락 시 ValueError"""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="5min"),
            "open": [100.0] * 10,
            "high": [105.0] * 10,
        })
        with pytest.raises(ValueError, match="필수 열 누락"):
            validate_ohlcv_dataframe(df)

    def test_all_nan_rows_dropped(self):
        """전체 NaN 행 제거"""
        df = self._make_df(12)
        # 마지막 행을 전체 NaN으로
        for col in ["open", "high", "low", "close", "volume"]:
            df.loc[11, col] = np.nan
        result = validate_ohlcv_dataframe(df, min_rows=10)
        assert len(result) >= 10


class TestSanitizeNanValues:
    """sanitize_nan_values 테스트"""

    def test_no_nan(self):
        """NaN 없는 딕셔너리"""
        data = {"a": 1.0, "b": 2.0, "c": "text"}
        result = sanitize_nan_values(data)
        assert result == data

    def test_nan_replaced(self):
        """NaN 값 교체"""
        data = {"a": float("nan"), "b": 2.0}
        result = sanitize_nan_values(data)
        assert result["a"] == 0.0
        assert result["b"] == 2.0

    def test_none_replaced(self):
        """None 값 교체"""
        data = {"a": None, "b": 2.0}
        result = sanitize_nan_values(data)
        assert result["a"] == 0.0
        assert result["b"] == 2.0

    def test_custom_default(self):
        """커스텀 기본값"""
        data = {"a": float("nan"), "b": None}
        result = sanitize_nan_values(data, default=-1.0)
        assert result["a"] == -1.0
        assert result["b"] == -1.0

    def test_mixed_types_preserved(self):
        """비숫자 타입 보존"""
        data = {"a": float("nan"), "b": "text", "c": [1, 2], "d": True}
        result = sanitize_nan_values(data)
        assert result["a"] == 0.0
        assert result["b"] == "text"
        assert result["c"] == [1, 2]
        assert result["d"] is True
