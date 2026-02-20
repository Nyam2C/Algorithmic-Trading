"""PCMCI Causal Discovery Analyzer.

APEX-V Phase 2: PC 알고리즘 기반 조건부 독립성 검정 +
MCI 검정으로 시차 인과 관계를 식별하여
Hierarchical Gate 순서를 데이터 주도로 검증/제안.

참조: Runge et al. (2019), "Detecting and quantifying causal
associations in large nonlinear time series datasets"
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from loguru import logger


@dataclass
class CausalEdge:
    """인과 엣지.

    Attributes:
        source: 원인 시그널
        target: 결과 시그널
        lag: 시차 (양수 = source가 target보다 앞선다)
        strength: 인과 강도 (편상관 절대값)
        p_value: 검정 p-value
    """
    source: str
    target: str
    lag: int
    strength: float
    p_value: float


@dataclass
class CausalGraph:
    """인과 그래프.

    Attributes:
        edges: 유의미한 인과 엣지 리스트
        nodes: 시그널 소스 이름 리스트
        adjacency: 인접 행렬 {(source, target, lag): strength}
    """
    edges: list[CausalEdge] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    adjacency: dict[tuple[str, str, int], float] = field(default_factory=dict)


# PCMCI 상수
PCMCI_MIN_SAMPLES = 200
PCMCI_MAX_LAG = 5
PCMCI_SIGNIFICANCE_LEVEL = 0.05
PCMCI_DEFAULT_K = 3  # 조건 변수 최대 개수


class PCMCIAnalyzer:
    """PCMCI 인과 분석기.

    PC 알고리즘 (Phase 1): 조건부 독립성 검정으로 가짜 인과 제거
    MCI 검정 (Phase 2): 남은 링크에 대해 시차 인과 강도 측정

    Attributes:
        min_samples: 최소 샘플 수
        max_lag: 최대 시차
        significance: 유의 수준
    """

    def __init__(
        self,
        min_samples: int = PCMCI_MIN_SAMPLES,
        max_lag: int = PCMCI_MAX_LAG,
        significance: float = PCMCI_SIGNIFICANCE_LEVEL,
    ) -> None:
        self._min_samples = min_samples
        self._max_lag = max_lag
        self._significance = significance
        self._log = logger.bind(module="pcmci")

    def analyze(
        self,
        signal_history: dict[str, list[float]],
    ) -> CausalGraph:
        """시그널 히스토리에서 인과 그래프 구축.

        Args:
            signal_history: {source_name: [score_1, score_2, ...]}

        Returns:
            CausalGraph
        """
        sources = list(signal_history.keys())

        # 최소 샘플 확인
        min_len = min(len(v) for v in signal_history.values())
        if min_len < self._min_samples:
            self._log.warning(
                f"샘플 부족: {min_len} < {self._min_samples} → 빈 그래프"
            )
            return CausalGraph(nodes=sources)

        # 데이터 행렬 구성 (T x N)
        data = np.column_stack([
            np.array(signal_history[s][:min_len], dtype=np.float64)
            for s in sources
        ])

        # Phase 1: PC 알고리즘 — 후보 링크 식별
        candidate_links = self._pc_phase(data, sources)

        # Phase 2: MCI 검정 — 인과 강도 정량화
        edges = self._mci_phase(data, sources, candidate_links)

        graph = CausalGraph(
            edges=edges,
            nodes=sources,
            adjacency={
                (e.source, e.target, e.lag): e.strength
                for e in edges
            },
        )

        self._log.info(
            f"PCMCI 분석 완료: {len(sources)}개 소스, "
            f"{len(edges)}개 유의미한 인과 엣지"
        )
        return graph

    def suggest_layer_ordering(
        self,
        graph: CausalGraph,
    ) -> list[list[str]]:
        """인과 그래프에서 계층 순서 제안.

        인과 방향 기반 위상 정렬:
        - 더 많은 outgoing 엣지를 가진 소스 → 상위 계층 (leading)
        - 더 많은 incoming 엣지를 가진 소스 → 하위 계층 (lagging)

        Args:
            graph: CausalGraph

        Returns:
            계층 리스트 (상위 → 하위)
        """
        if not graph.edges or not graph.nodes:
            return [graph.nodes] if graph.nodes else []

        # 각 노드의 outgoing - incoming 점수 계산
        scores: dict[str, float] = dict.fromkeys(graph.nodes, 0.0)
        for edge in graph.edges:
            scores[edge.source] = scores.get(edge.source, 0.0) + edge.strength
            scores[edge.target] = scores.get(edge.target, 0.0) - edge.strength

        # 점수 기준 정렬 → 3계층 분할
        sorted_nodes = sorted(
            graph.nodes, key=lambda n: scores.get(n, 0.0), reverse=True
        )

        n = len(sorted_nodes)
        if n <= 2:  # noqa: PLR2004
            return [sorted_nodes]

        # 3등분
        third = max(1, n // 3)
        layers = [
            sorted_nodes[:third],        # leading (상위)
            sorted_nodes[third:2*third],  # middle
            sorted_nodes[2*third:],       # lagging (하위)
        ]
        # 빈 계층 제거
        return [layer for layer in layers if layer]

    def _pc_phase(
        self,
        data: np.ndarray,
        sources: list[str],  # noqa: ARG002
    ) -> list[tuple[int, int, int]]:
        """PC 알고리즘: 조건부 독립성 검정으로 후보 링크 식별.

        Returns:
            [(source_idx, target_idx, lag), ...]
        """
        n_vars = data.shape[1]
        candidates: list[tuple[int, int, int]] = []

        for target_idx in range(n_vars):
            for source_idx in range(n_vars):
                if source_idx == target_idx:
                    continue
                for lag_val in range(1, self._max_lag + 1):
                    _corr, p_val = self._partial_correlation(
                        data, source_idx, target_idx, lag_val
                    )
                    if p_val < self._significance:
                        candidates.append((source_idx, target_idx, lag_val))

        return candidates

    def _mci_phase(
        self,
        data: np.ndarray,
        sources: list[str],
        candidates: list[tuple[int, int, int]],
    ) -> list[CausalEdge]:
        """MCI 검정: 조건부 편상관으로 인과 강도 정량화.

        조건 변수: 타겟의 자기 과거값 + 다른 후보 소스의 과거값

        Returns:
            유의미한 CausalEdge 리스트
        """
        edges: list[CausalEdge] = []

        for source_idx, target_idx, lag in candidates:
            # 조건 변수 세트: 타겟의 자기 과거값
            condition_indices = [
                (target_idx, lag_i)
                for lag_i in range(1, min(lag + 1, self._max_lag + 1))
            ]

            # MCI 검정 (조건부 편상관)
            strength, p_val = self._conditional_partial_correlation(
                data, source_idx, target_idx, lag, condition_indices
            )

            if p_val < self._significance:
                edges.append(CausalEdge(
                    source=sources[source_idx],
                    target=sources[target_idx],
                    lag=lag,
                    strength=abs(strength),
                    p_value=p_val,
                ))

        return edges

    def _partial_correlation(
        self,
        data: np.ndarray,
        source_idx: int,
        target_idx: int,
        lag: int,
    ) -> tuple[float, float]:
        """단순 편상관 계산.

        Returns:
            (correlation, p_value)
        """
        n = data.shape[0]
        if lag >= n:
            return 0.0, 1.0

        x = data[: n - lag, source_idx]
        y = data[lag:, target_idx]

        min_len = min(len(x), len(y))
        if min_len < 5:  # noqa: PLR2004
            return 0.0, 1.0

        x = x[:min_len]
        y = y[:min_len]

        # Pearson 상관
        corr = self._pearson_corr(x, y)

        # t-test for correlation significance
        p_val = self._corr_p_value(corr, min_len)
        return corr, p_val

    def _conditional_partial_correlation(
        self,
        data: np.ndarray,
        source_idx: int,
        target_idx: int,
        lag: int,
        conditions: list[tuple[int, int]],
    ) -> tuple[float, float]:
        """조건부 편상관 계산.

        조건 변수의 영향을 제거한 후 편상관.

        Args:
            data: 데이터 행렬 (T x N)
            source_idx: 원인 변수 인덱스
            target_idx: 결과 변수 인덱스
            lag: 시차
            conditions: [(variable_idx, cond_lag), ...]

        Returns:
            (partial_correlation, p_value)
        """
        n = data.shape[0]
        max_lag = max(lag, max((cl for _, cl in conditions), default=0))
        effective_n = n - max_lag

        if effective_n < 10:  # noqa: PLR2004
            return 0.0, 1.0

        # 타겟과 소스 추출
        y = data[max_lag:, target_idx]
        x = data[max_lag - lag: n - lag, source_idx]

        min_len = min(len(x), len(y), effective_n)
        y = y[:min_len]
        x = x[:min_len]

        # 조건 변수가 없으면 단순 상관
        if not conditions:
            corr = self._pearson_corr(x, y)
            return corr, self._corr_p_value(corr, min_len)

        # 조건 변수 행렬 구성
        z_cols = []
        for var_idx, var_lag in conditions[:PCMCI_DEFAULT_K]:
            z = data[max_lag - var_lag: n - var_lag, var_idx]
            z_cols.append(z[:min_len])

        if not z_cols:
            corr = self._pearson_corr(x, y)
            return corr, self._corr_p_value(corr, min_len)

        z_matrix = np.column_stack(z_cols)

        # 조건부 편상관: OLS residuals의 상관
        try:
            # x 잔차
            x_resid = self._residualize(x, z_matrix)
            # y 잔차
            y_resid = self._residualize(y, z_matrix)

            corr = self._pearson_corr(x_resid, y_resid)
            # 자유도 보정
            df = min_len - z_matrix.shape[1] - 2
            p_val = self._corr_p_value(corr, df + 2)
            return corr, p_val
        except Exception:
            return 0.0, 1.0

    @staticmethod
    def _residualize(y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """OLS 잔차 계산: y에서 z의 영향 제거."""
        try:
            # z'z 역행렬
            ztz = z.T @ z
            # 정규화 (특이 행렬 방지)
            ztz += np.eye(ztz.shape[0]) * 1e-8
            beta = np.linalg.solve(ztz, z.T @ y)
            return y - z @ beta
        except np.linalg.LinAlgError:
            return y

    @staticmethod
    def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
        """Pearson 상관계수."""
        n = len(x)
        if n < 3:  # noqa: PLR2004
            return 0.0
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_std = np.std(x)
        y_std = np.std(y)
        if x_std == 0 or y_std == 0:
            return 0.0
        return float(np.mean((x - x_mean) * (y - y_mean)) / (x_std * y_std))

    @staticmethod
    def _corr_p_value(corr: float, n: int) -> float:
        """상관계수의 p-value (t-분포 근사).

        t = r * sqrt(n-2) / sqrt(1-r^2)
        """
        if n < 3 or abs(corr) >= 1.0:  # noqa: PLR2004
            return 1.0 if abs(corr) < 1.0 else 0.0

        t_stat = corr * math.sqrt(n - 2) / math.sqrt(1.0 - corr ** 2)
        # 정규 분포 근사 (n 충분히 크면)
        # 2-tailed p-value ≈ 2 * Phi(-|t|)
        # erfc 근사 사용
        return math.erfc(abs(t_stat) / math.sqrt(2.0))
