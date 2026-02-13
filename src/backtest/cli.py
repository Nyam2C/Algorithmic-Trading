"""백테스트 CLI.

커맨드라인에서 백테스트를 실행하는 도구입니다.

Usage:
    python -m src.backtest.cli --data data.csv --leverage 10
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

from src.backtest.engine import BacktestConfig, BacktestEngine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(
        description="High-Win Survival System 백테스트",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data", type=str, required=True, help="OHLCV CSV 파일 경로",
    )
    parser.add_argument(
        "--strategy", type=str, default="rule_based", help="전략 이름",
    )
    parser.add_argument(
        "--leverage", type=int, default=10, help="레버리지",
    )
    parser.add_argument(
        "--capital", type=float, default=10000.0, help="초기 자본 (USDT)",
    )
    parser.add_argument(
        "--tp", type=float, default=0.01, help="익절 비율",
    )
    parser.add_argument(
        "--sl", type=float, default=0.005, help="손절 비율",
    )
    parser.add_argument(
        "--commission", type=float, default=0.0004, help="수수료 비율",
    )
    parser.add_argument(
        "--position-size", type=float, default=0.05,
        help="포지션 크기 비율",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="결과 출력 파일 경로",
    )
    return parser.parse_args(argv)


def load_data(path: str) -> pd.DataFrame:
    """CSV에서 OHLCV 데이터 로드."""
    file_path = Path(path)
    if not file_path.exists():
        logger.error(f"데이터 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    df = pd.read_csv(file_path)
    required_cols = {"open", "high", "low", "close", "volume"}
    if not required_cols.issubset(set(df.columns)):
        logger.error(
            f"필수 컬럼 누락: {required_cols - set(df.columns)}",
        )
        sys.exit(1)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def default_strategy(
    _candle: dict,
    market_data: dict,
) -> str:
    """기본 rule-based 전략.

    RSI 기반 단순 전략:
    - RSI < 30: LONG
    - RSI > 70: SHORT
    - 그 외: WAIT
    """
    rsi = market_data.get("rsi")
    if rsi is None:
        return "WAIT"

    if rsi < 30:  # noqa: PLR2004
        return "LONG"
    if rsi > 70:  # noqa: PLR2004
        return "SHORT"
    return "WAIT"


def print_results(result) -> None:
    """백테스트 결과 출력."""
    print("\n" + "=" * 60)  # noqa: T201
    print("  백테스트 결과")  # noqa: T201
    print("=" * 60)  # noqa: T201
    print(f"  총 거래: {result.total_trades}")  # noqa: T201
    print(f"  승률: {result.win_rate:.1f}%")  # noqa: T201
    print(f"  총 PnL: ${result.total_pnl:,.2f}")  # noqa: T201
    print(f"  최대 드로다운: {result.max_drawdown:.2%}")  # noqa: T201
    print(f"  샤프 비율: {result.sharpe_ratio:.2f}")  # noqa: T201
    print(f"  최종 자본: ${result.final_capital:,.2f}")  # noqa: T201
    print("=" * 60)  # noqa: T201


def main(argv: list[str] | None = None) -> int:
    """메인 실행."""
    args = parse_args(argv)

    logger.info(f"백테스트 시작: {args.data}")

    df = load_data(args.data)

    # DataFrame을 list[dict]로 변환 (BacktestEngine API)
    if "timestamp" not in df.columns:
        df["timestamp"] = range(len(df))
    candles = df.to_dict("records")

    config = BacktestConfig(
        initial_capital=args.capital,
        leverage=args.leverage,
        position_size_pct=args.position_size,
        tp_pct=args.tp,
        sl_pct=args.sl,
        commission_pct=args.commission,
    )

    engine = BacktestEngine(config=config, data=candles)
    result = engine.run(strategy=default_strategy)

    print_results(result)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(str(result.to_dict()))
        logger.info(f"결과 저장: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
