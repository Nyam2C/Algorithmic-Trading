"""LightGBM Dead Zone Verifier 테스트.

APEX-V Phase 2 Step 4: LightGBM Dead Zone 검증기 + Confluence Engine 통합.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.lgb_booster import (
    FEATURE_NAMES,
    LGB_MIN_CONFIDENCE,
    REGIME_INDEX,
    SESSION_INDEX,
    LGBDeadZoneVerifier,
)


class TestLGBDeadZoneVerifier:
    """LGBDeadZoneVerifier 단위 테스트."""

    def test_no_model_path(self):
        """모델 경로 없음 → is_available=False."""
        v = LGBDeadZoneVerifier()
        assert v.is_available is False

    def test_nonexistent_model_path(self):
        """존재하지 않는 모델 → is_available=False."""
        v = LGBDeadZoneVerifier(model_path="/tmp/nonexistent.txt")
        assert v.is_available is False

    def test_predict_without_model_raises(self):
        """모델 미로드 시 predict → RuntimeError."""
        v = LGBDeadZoneVerifier()
        with pytest.raises(RuntimeError, match="모델이 로드되지 않았습니다"):
            v.predict({"net_edge": 0.3})

    def test_predict_with_mock_model(self):
        """Mock 모델로 predict 동작 확인."""
        v = LGBDeadZoneVerifier()
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8])
        mock_model.best_iteration = 100
        v._model = mock_model

        assert v.is_available is True
        direction, confidence = v.predict({"net_edge": 0.3, "atr_pct": 0.5})
        assert direction == "LONG"
        assert confidence == pytest.approx(0.8)

    def test_predict_short_direction(self):
        """P(LONG) < 0.5 → SHORT."""
        v = LGBDeadZoneVerifier()
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.2])
        mock_model.best_iteration = 50
        v._model = mock_model

        direction, confidence = v.predict({"net_edge": 0.3})
        assert direction == "SHORT"
        assert confidence == pytest.approx(0.8)

    def test_predict_wait_on_equal(self):
        """P(LONG) = 0.5 → WAIT."""
        v = LGBDeadZoneVerifier()
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5])
        mock_model.best_iteration = 50
        v._model = mock_model

        direction, confidence = v.predict({})
        assert direction == "WAIT"

    def test_predict_exception_handling(self):
        """예측 실패 → WAIT, 0.0."""
        v = LGBDeadZoneVerifier()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("boom")
        mock_model.best_iteration = 50
        v._model = mock_model

        direction, confidence = v.predict({})
        assert direction == "WAIT"
        assert confidence == 0.0

    def test_feature_vector_construction(self):
        """특성 벡터 생성."""
        v = LGBDeadZoneVerifier()
        features = {"net_edge": 0.3, "atr_pct": 0.5, "rsi": 65.0}
        vec = v._build_feature_vector(features)
        assert len(vec) == len(FEATURE_NAMES)
        assert vec[0] == 0.3   # net_edge
        assert vec[3] == 0.5   # atr_pct
        assert vec[8] == 65.0  # rsi

    def test_missing_features_default_zero(self):
        """누락된 특성은 0.0으로 대체."""
        v = LGBDeadZoneVerifier()
        vec = v._build_feature_vector({})
        assert all(x == 0.0 for x in vec)


class TestLGBConstants:
    """상수 테스트."""

    def test_feature_names_count(self):
        assert len(FEATURE_NAMES) == 10

    def test_regime_index_values(self):
        assert len(REGIME_INDEX) == 7
        assert REGIME_INDEX["strong_uptrend"] == 0

    def test_session_index_values(self):
        assert len(SESSION_INDEX) == 4

    def test_min_confidence(self):
        assert LGB_MIN_CONFIDENCE == 0.6


class TestConfluenceEngineLGB:
    """Confluence Engine + LGB 통합 테스트."""

    @pytest.mark.asyncio
    async def test_dead_zone_lgb_confident_pass(self):
        """LGB confidence >= 0.6 + 방향 일치 → PASS."""

        from src.ai.confluence.confluence_engine import ConfluenceEngine

        mock_lgb = MagicMock()
        mock_lgb.is_available = True
        mock_lgb.predict.return_value = ("LONG", 0.8)

        engine = ConfluenceEngine(lgb_verifier=mock_lgb)

        # Dead Zone 내 (threshold ± margin)
        result = await engine._step8_gemini_boundary(
            "LONG", 0.30, 0.30, {"indicators": {}}
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_dead_zone_lgb_confident_reject(self):
        """LGB confidence >= 0.6 + 방향 불일치 → WAIT."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        mock_lgb = MagicMock()
        mock_lgb.is_available = True
        mock_lgb.predict.return_value = ("SHORT", 0.8)

        engine = ConfluenceEngine(lgb_verifier=mock_lgb)

        result = await engine._step8_gemini_boundary(
            "LONG", 0.30, 0.30, {"indicators": {}}
        )
        assert result == "WAIT"

    @pytest.mark.asyncio
    async def test_dead_zone_lgb_low_confidence_gemini_fallback(self):
        """LGB confidence < 0.6 → Gemini 폴백."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        mock_lgb = MagicMock()
        mock_lgb.is_available = True
        mock_lgb.predict.return_value = ("LONG", 0.4)

        mock_gemini = AsyncMock()
        mock_gemini.get_signal = AsyncMock(return_value="LONG")

        engine = ConfluenceEngine(
            lgb_verifier=mock_lgb, gemini_verifier=mock_gemini,
        )

        result = await engine._step8_gemini_boundary(
            "LONG", 0.30, 0.30, {"indicators": {}}
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_dead_zone_lgb_unavailable_gemini_fallback(self):
        """LGB 미가용 → Gemini 폴백."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        mock_gemini = AsyncMock()
        mock_gemini.get_signal = AsyncMock(return_value="LONG")

        engine = ConfluenceEngine(gemini_verifier=mock_gemini)

        result = await engine._step8_gemini_boundary(
            "LONG", 0.30, 0.30, {"indicators": {}}
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_dead_zone_outside_upper_auto_pass(self):
        """Dead Zone 위 → 자동 PASS (LGB 호출 안 함)."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        mock_lgb = MagicMock()
        mock_lgb.is_available = True
        engine = ConfluenceEngine(lgb_verifier=mock_lgb)

        result = await engine._step8_gemini_boundary(
            "LONG", 0.50, 0.30, {"indicators": {}}
        )
        assert result == "LONG"
        mock_lgb.predict.assert_not_called()
