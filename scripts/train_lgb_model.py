"""LightGBM Dead Zone 검증 모델 학습 스크립트.

오프라인 백테스트 결과 기반으로 학습.

사용법:
    python scripts/train_lgb_model.py --input backtest_results.csv --output models/lgb_dead_zone.txt

입력 CSV 형식:
    net_edge, regime_idx, session_idx, atr_pct, spread_pct,
    ofi_score, whale_score, funding_rate, rsi, volume_ratio,
    label (1=올바른 진입, 0=잘못된 진입)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="LightGBM Dead Zone 모델 학습")
    parser.add_argument("--input", required=True, help="백테스트 결과 CSV")
    parser.add_argument(
        "--output", default="models/lgb_dead_zone.txt",
        help="모델 저장 경로",
    )
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-depth", type=int, default=5)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"입력 파일 없음: {input_path}")
        sys.exit(1)

    try:
        import lightgbm as lgb  # noqa: PLC0415
    except ImportError:
        print("lightgbm 미설치: pip install lightgbm>=4.0.0")
        sys.exit(1)

    # CSV 로드
    data = np.loadtxt(str(input_path), delimiter=",", skiprows=1)
    if data.shape[1] < 11:
        print(f"CSV 열 수 부족: {data.shape[1]} (최소 11)")
        sys.exit(1)

    X = data[:, :10]  # features
    y = data[:, 10]   # label

    # 학습/검증 분할 (80/20)
    n_train = int(len(X) * 0.8)
    X_train, X_val = X[:n_train], X[n_train:]
    y_train, y_val = y[:n_train], y[n_train:]

    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": args.learning_rate,
        "max_depth": args.max_depth,
        "num_leaves": 31,
        "verbose": -1,
        "seed": 42,
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=args.n_estimators,
        valid_sets=[val_data],
    )

    # 저장
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(output_path))
    print(f"모델 저장 완료: {output_path}")

    # Feature importance
    importance = model.feature_importance(importance_type="gain")
    from src.ai.lgb_booster import FEATURE_NAMES
    print("\nFeature Importance:")
    for name, imp in sorted(
        zip(FEATURE_NAMES, importance), key=lambda x: -x[1]
    ):
        print(f"  {name}: {imp:.2f}")


if __name__ == "__main__":
    main()
