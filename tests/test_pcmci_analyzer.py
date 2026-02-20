"""PCMCI Causal Discovery Analyzer 테스트.

APEX-V Phase 2 Step 5: 인과 그래프 구축 + 계층 추출 + 통합.
"""
from __future__ import annotations

import random

import numpy as np

from src.ai.causal.pcmci_analyzer import (
    PCMCI_MAX_LAG,
    PCMCI_MIN_SAMPLES,
    CausalGraph,
    PCMCIAnalyzer,
)


def _make_independent_history(
    n_sources: int = 3, n_samples: int = 250, seed: int = 42,
) -> dict[str, list[float]]:
    """독립적인 시그널 히스토리 생성."""
    rng = random.Random(seed)
    return {
        f"source_{i}": [rng.gauss(0, 1) for _ in range(n_samples)]
        for i in range(n_sources)
    }


def _make_causal_history(
    n_samples: int = 300, seed: int = 42,
) -> dict[str, list[float]]:
    """인과 관계가 있는 시그널 히스토리 생성.

    A → B (lag=1): B_t = 0.8 * A_{t-1} + noise
    A → C (lag=2): C_t = 0.6 * A_{t-2} + noise
    B, C 독립
    """
    rng = random.Random(seed)
    a = [rng.gauss(0, 1) for _ in range(n_samples)]
    b = [0.0] + [a[i] * 0.8 + rng.gauss(0, 0.3) for i in range(n_samples - 1)]
    c = [0.0, 0.0] + [
        a[i] * 0.6 + rng.gauss(0, 0.3)
        for i in range(n_samples - 2)
    ]
    return {"a": a, "b": b, "c": c}


class TestPCMCIAnalyzer:
    """PCMCIAnalyzer 단위 테스트."""

    def test_init_defaults(self):
        """기본 초기화."""
        analyzer = PCMCIAnalyzer()
        assert analyzer._min_samples == PCMCI_MIN_SAMPLES
        assert analyzer._max_lag == PCMCI_MAX_LAG

    def test_analyze_insufficient_samples(self):
        """샘플 부족 → 빈 그래프."""
        analyzer = PCMCIAnalyzer(min_samples=200)
        history = _make_independent_history(n_samples=50)
        graph = analyzer.analyze(history)
        assert isinstance(graph, CausalGraph)
        assert len(graph.edges) == 0
        assert len(graph.nodes) == 3

    def test_analyze_independent_signals(self):
        """독립 시그널 → 적은 엣지 (스퍼리어스 가능하지만 적음)."""
        analyzer = PCMCIAnalyzer(
            min_samples=100,
            significance=0.01,  # 더 엄격한 유의 수준
        )
        history = _make_independent_history(n_samples=250)
        graph = analyzer.analyze(history)
        assert isinstance(graph, CausalGraph)
        # 독립이므로 엣지가 적어야 함 (완전히 0은 아닐 수 있음)
        assert len(graph.edges) <= 10

    def test_analyze_causal_signals(self):
        """인과 관계 시그널 → 유의미한 엣지 존재."""
        analyzer = PCMCIAnalyzer(min_samples=100)
        history = _make_causal_history(n_samples=300)
        graph = analyzer.analyze(history)
        assert isinstance(graph, CausalGraph)
        assert len(graph.nodes) == 3
        # A→B 인과 관계가 탐지되어야 함 (강한 상관)
        a_to_b_edges = [
            e for e in graph.edges
            if e.source == "a" and e.target == "b"
        ]
        assert len(a_to_b_edges) > 0, "A→B 인과 관계 미탐지"

    def test_causal_edge_attributes(self):
        """CausalEdge 속성 확인."""
        analyzer = PCMCIAnalyzer(min_samples=100)
        history = _make_causal_history(n_samples=300)
        graph = analyzer.analyze(history)

        for edge in graph.edges:
            assert isinstance(edge.source, str)
            assert isinstance(edge.target, str)
            assert edge.lag >= 1
            assert edge.strength >= 0.0
            assert 0.0 <= edge.p_value <= 1.0

    def test_adjacency_dict(self):
        """adjacency 딕셔너리 구조."""
        analyzer = PCMCIAnalyzer(min_samples=100)
        history = _make_causal_history(n_samples=300)
        graph = analyzer.analyze(history)

        for (src, tgt, lag), strength in graph.adjacency.items():
            assert isinstance(src, str)
            assert isinstance(tgt, str)
            assert isinstance(lag, int)
            assert isinstance(strength, float)


class TestLayerOrdering:
    """인과 순서 → 계층 추출 테스트."""

    def test_suggest_ordering_causal(self):
        """인과 관계 있는 그래프 → 유의미한 순서."""
        analyzer = PCMCIAnalyzer(min_samples=100)
        history = _make_causal_history(n_samples=300)
        graph = analyzer.analyze(history)
        ordering = analyzer.suggest_layer_ordering(graph)

        assert isinstance(ordering, list)
        assert len(ordering) >= 1
        # 모든 노드가 포함되어야 함
        all_nodes = [n for layer in ordering for n in layer]
        assert set(all_nodes) == set(graph.nodes)

    def test_suggest_ordering_empty_graph(self):
        """빈 그래프 → 단일 계층 폴백."""
        analyzer = PCMCIAnalyzer()
        graph = CausalGraph(nodes=["a", "b", "c"])
        ordering = analyzer.suggest_layer_ordering(graph)
        assert len(ordering) == 1
        assert set(ordering[0]) == {"a", "b", "c"}

    def test_suggest_ordering_no_nodes(self):
        """노드 없음 → 빈 리스트."""
        analyzer = PCMCIAnalyzer()
        graph = CausalGraph()
        ordering = analyzer.suggest_layer_ordering(graph)
        assert ordering == []

    def test_suggest_ordering_two_nodes(self):
        """2노드 → 단일 계층."""
        analyzer = PCMCIAnalyzer()
        graph = CausalGraph(nodes=["a", "b"])
        ordering = analyzer.suggest_layer_ordering(graph)
        assert len(ordering) == 1


class TestPCMCIInternals:
    """내부 통계 함수 테스트."""

    def test_pearson_corr(self):
        """Pearson 상관계수."""
        analyzer = PCMCIAnalyzer()
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        corr = analyzer._pearson_corr(x, y)
        assert abs(corr - 1.0) < 0.01

    def test_pearson_corr_negative(self):
        """음의 상관."""
        analyzer = PCMCIAnalyzer()
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([10.0, 8.0, 6.0, 4.0, 2.0])
        corr = analyzer._pearson_corr(x, y)
        assert abs(corr - (-1.0)) < 0.01

    def test_pearson_corr_zero_std(self):
        """상수 → 상관 0."""
        analyzer = PCMCIAnalyzer()
        x = np.array([1.0, 1.0, 1.0])
        y = np.array([1.0, 2.0, 3.0])
        assert analyzer._pearson_corr(x, y) == 0.0

    def test_corr_p_value(self):
        """p-value 유효 범위."""
        analyzer = PCMCIAnalyzer()
        p = analyzer._corr_p_value(0.5, 100)
        assert 0.0 <= p <= 1.0

    def test_residualize(self):
        """OLS 잔차."""
        analyzer = PCMCIAnalyzer()
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        z = np.array([[1.0], [1.0], [1.0], [1.0], [1.0]])  # 상수
        resid = analyzer._residualize(y, z)
        # 상수 제거 → 잔차 평균 ≈ 0
        assert abs(np.mean(resid)) < 0.1


class TestConfluenceEngineIntegration:
    """Confluence Engine + PCMCI 통합 테스트."""

    def test_update_causal_ordering(self):
        """update_causal_ordering 호출."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine()
        ordering = [["a", "b"], ["c", "d"], ["e"]]
        engine.update_causal_ordering(ordering)
        assert engine._causal_ordering == ordering

    def test_causal_ordering_none_by_default(self):
        """기본값은 None."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine()
        assert engine._causal_ordering is None
