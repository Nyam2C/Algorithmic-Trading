"""백테스트 CLI 테스트."""
import csv
from pathlib import Path

import pytest

from src.backtest.cli import default_strategy, load_data, main, parse_args


class TestParseArgs:
    """CLI 인자 파싱 테스트."""

    def test_필수_인자만(self) -> None:
        """--data만 지정하면 나머지는 기본값"""
        args = parse_args(["--data", "test.csv"])
        assert args.data == "test.csv"
        assert args.strategy == "rule_based"
        assert args.leverage == 10
        assert args.capital == 10000.0
        assert args.tp == 0.01
        assert args.sl == 0.005
        assert args.commission == 0.0004
        assert args.position_size == 0.05
        assert args.output is None

    def test_모든_인자_지정(self) -> None:
        """모든 인자 명시적 지정"""
        args = parse_args([
            "--data", "data.csv",
            "--strategy", "custom",
            "--leverage", "20",
            "--capital", "5000",
            "--tp", "0.02",
            "--sl", "0.01",
            "--commission", "0.001",
            "--position-size", "0.1",
            "--output", "result.json",
        ])
        assert args.data == "data.csv"
        assert args.strategy == "custom"
        assert args.leverage == 20
        assert args.capital == 5000.0
        assert args.tp == 0.02
        assert args.sl == 0.01
        assert args.commission == 0.001
        assert args.position_size == 0.1
        assert args.output == "result.json"

    def test_data_인자_필수(self) -> None:
        """--data 없으면 에러"""
        with pytest.raises(SystemExit):
            parse_args([])


class TestLoadData:
    """CSV 데이터 로딩 테스트."""

    def test_유효한_CSV_로드(self, tmp_path: Path) -> None:
        """유효한 OHLCV CSV 로드"""
        csv_file = tmp_path / "test.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["open", "high", "low", "close", "volume"])
            writer.writerow([100.0, 105.0, 95.0, 102.0, 1000.0])
            writer.writerow([102.0, 108.0, 100.0, 106.0, 1200.0])

        df = load_data(str(csv_file))
        assert len(df) == 2
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df["close"].iloc[0] == 102.0

    def test_존재하지_않는_파일(self) -> None:
        """존재하지 않는 파일이면 sys.exit(1)"""
        with pytest.raises(SystemExit):
            load_data("/nonexistent/path.csv")

    def test_필수_컬럼_누락(self, tmp_path: Path) -> None:
        """필수 컬럼이 없으면 sys.exit(1)"""
        csv_file = tmp_path / "bad.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["open", "close"])  # high, low, volume 누락
            writer.writerow([100.0, 102.0])

        with pytest.raises(SystemExit):
            load_data(str(csv_file))


class TestDefaultStrategy:
    """기본 전략 테스트."""

    def test_rsi_없으면_wait(self) -> None:
        """RSI 데이터 없으면 WAIT"""
        assert default_strategy({}, {}) == "WAIT"

    def test_rsi_30미만_long(self) -> None:
        """RSI < 30이면 LONG"""
        assert default_strategy({}, {"rsi": 25.0}) == "LONG"

    def test_rsi_70초과_short(self) -> None:
        """RSI > 70이면 SHORT"""
        assert default_strategy({}, {"rsi": 75.0}) == "SHORT"

    def test_rsi_30_70_사이_wait(self) -> None:
        """30 <= RSI <= 70이면 WAIT"""
        assert default_strategy({}, {"rsi": 50.0}) == "WAIT"
        assert default_strategy({}, {"rsi": 30.0}) == "WAIT"
        assert default_strategy({}, {"rsi": 70.0}) == "WAIT"


class TestMain:
    """메인 실행 통합 테스트."""

    def _create_ohlcv_csv(self, path: Path, num_rows: int = 50) -> None:
        """테스트용 OHLCV CSV 생성."""
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            base_price = 50000.0
            for i in range(num_rows):
                o = base_price + i * 10
                h = o + 50
                low = o - 50
                c = o + 20
                v = 1000.0 + i
                writer.writerow([i, o, h, low, c, v])

    def test_정상_실행(self, tmp_path: Path) -> None:
        """정상적인 백테스트 실행"""
        csv_file = tmp_path / "data.csv"
        self._create_ohlcv_csv(csv_file, num_rows=50)

        result = main(["--data", str(csv_file)])
        assert result == 0

    def test_결과_파일_출력(self, tmp_path: Path) -> None:
        """--output 옵션으로 결과 파일 출력"""
        csv_file = tmp_path / "data.csv"
        output_file = tmp_path / "result.txt"
        self._create_ohlcv_csv(csv_file, num_rows=50)

        result = main(["--data", str(csv_file), "--output", str(output_file)])
        assert result == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "total_trades" in content

    def test_커스텀_파라미터(self, tmp_path: Path) -> None:
        """커스텀 파라미터로 실행"""
        csv_file = tmp_path / "data.csv"
        self._create_ohlcv_csv(csv_file, num_rows=50)

        result = main([
            "--data", str(csv_file),
            "--leverage", "20",
            "--capital", "5000",
            "--tp", "0.02",
            "--sl", "0.01",
        ])
        assert result == 0
