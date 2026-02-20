"""LightGBM Dead Zone Verifier.

APEX-V Phase 2: Dead Zone (±10pt) 영역에서
Gemini AI 대신/보강으로 결정 정확도 향상.

모델은 오프라인 학습 (scripts/train_lgb_model.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

# Feature 인덱스 매핑
FEATURE_NAMES = [
    "net_edge",
    "regime_idx",
    "session_idx",
    "atr_pct",
    "spread_pct",
    "ofi_score",
    "whale_score",
    "funding_rate",
    "rsi",
    "volume_ratio",
]

# 레짐 인덱스 매핑
REGIME_INDEX: dict[str, int] = {
    "strong_uptrend": 0,
    "weak_uptrend": 1,
    "ranging": 2,
    "weak_downtrend": 3,
    "strong_downtrend": 4,
    "uncertainty": 5,
    "unknown": 6,
}

# 세션 인덱스 매핑
SESSION_INDEX: dict[str, int] = {
    "us": 0,
    "eu": 1,
    "asia": 2,
    "deep_night": 3,
}

# 신뢰도 임계값
LGB_MIN_CONFIDENCE = 0.6


class LGBDeadZoneVerifier:
    """LightGBM Dead Zone 검증기.

    Dead Zone 내 시그널을 LightGBM 모델로 검증.
    모델이 없으면 예측 불가 (Gemini 폴백).

    Attributes:
        model: LightGBM Booster 또는 None
        model_path: 모델 파일 경로
    """

    def __init__(self, model_path: str | None = None) -> None:
        """초기화.

        Args:
            model_path: 학습된 LightGBM 모델 경로 (.txt 또는 .pkl)
        """
        self._model: Any | None = None
        self._model_path = model_path

        if model_path:
            self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """모델 로드.

        Args:
            model_path: 모델 파일 경로
        """
        path = Path(model_path)
        if not path.exists():
            logger.warning(f"LGB 모델 파일 없음: {model_path}")
            return

        try:
            import lightgbm as lgb  # noqa: PLC0415

            self._model = lgb.Booster(model_file=str(path))
            logger.info(f"LGB 모델 로드 완료: {model_path}")
        except ImportError:
            logger.warning("lightgbm 미설치 — LGB 검증 비활성화")
        except Exception as e:
            logger.error(f"LGB 모델 로드 실패: {e}")

    @property
    def is_available(self) -> bool:
        """모델 사용 가능 여부."""
        return self._model is not None

    def predict(self, features: dict[str, float]) -> tuple[str, float]:
        """Dead Zone 시그널 예측.

        Args:
            features: 특성 벡터 딕셔너리
                - net_edge, regime_idx, session_idx, atr_pct, ...

        Returns:
            (direction, confidence)
            direction: "LONG", "SHORT", or "WAIT"
            confidence: 예측 신뢰도 (0~1)

        Raises:
            RuntimeError: 모델 미로드
        """
        if self._model is None:
            raise RuntimeError("LGB 모델이 로드되지 않았습니다")

        feature_vector = self._build_feature_vector(features)

        try:
            import numpy as np  # noqa: PLC0415

            pred = self._model.predict(
                np.array([feature_vector]),
                num_iteration=self._model.best_iteration,
            )
            # 이진 분류: pred[0] = P(LONG)
            prob_long = float(pred[0])
            prob_short = 1.0 - prob_long

            if prob_long > prob_short:
                return "LONG", prob_long
            if prob_short > prob_long:
                return "SHORT", prob_short
            return "WAIT", 0.5
        except Exception as e:
            logger.error(f"LGB 예측 실패: {e}")
            return "WAIT", 0.0

    def _build_feature_vector(
        self, features: dict[str, float]
    ) -> list[float]:
        """특성 딕셔너리 → 순서 벡터 변환.

        Args:
            features: 특성 딕셔너리

        Returns:
            특성 벡터 리스트
        """
        return [features.get(name, 0.0) for name in FEATURE_NAMES]
