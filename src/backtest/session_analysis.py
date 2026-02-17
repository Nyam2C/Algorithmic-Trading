"""세션별 거래 분석 — APEX-V Phase E.

SessionClassifier를 활용하여 거래를 ASIA/EU/US/DEEP_NIGHT로 분류하고,
세션별 성과 통계를 산출한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.ai.confluence.session_classifier import (
    SessionClassifier,
)
from src.backtest.engine import Trade

# 세션 분석 상수
MIN_TRADES_FOR_SHARPE = 2
WEAK_SESSION_WIN_RATE = 50.0
UNKNOWN_SESSION = "UNKNOWN"


@dataclass
class SessionStats:
    """세션별 거래 통계."""

    session: str
    total_trades: int
    winning_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    sharpe_ratio: float
    profit_factor: float
    recommendation: str


@dataclass
class SessionAnalysisResult:
    """세션 분석 결과."""

    sessions: dict[str, SessionStats] = field(default_factory=dict)
    weak_sessions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "sessions": {
                name: {
                    "session": s.session,
                    "total_trades": s.total_trades,
                    "winning_trades": s.winning_trades,
                    "win_rate": round(s.win_rate, 2),
                    "total_pnl": round(s.total_pnl, 2),
                    "avg_pnl": round(s.avg_pnl, 2),
                    "sharpe_ratio": round(s.sharpe_ratio, 2),
                    "profit_factor": round(s.profit_factor, 2),
                    "recommendation": s.recommendation,
                }
                for name, s in self.sessions.items()
            },
            "weak_sessions": self.weak_sessions,
        }


class SessionAnalyzer:
    """세션별 거래 분석기."""

    def __init__(self) -> None:
        self._classifier = SessionClassifier()

    def analyze(self, trades: list[Trade]) -> SessionAnalysisResult:
        """거래 목록을 세션별로 분석.

        Args:
            trades: 거래 목록.

        Returns:
            SessionAnalysisResult
        """
        if not trades:
            return SessionAnalysisResult()

        # 세션별 거래 분류
        buckets: dict[str, list[Trade]] = {}
        for trade in trades:
            session = self._classify_trade(trade)
            if session not in buckets:
                buckets[session] = []
            buckets[session].append(trade)

        # 세션별 통계 계산
        result = SessionAnalysisResult()
        for session_name, session_trades in buckets.items():
            stats = self._compute_stats(session_name, session_trades)
            result.sessions[session_name] = stats

        # 약한 세션 식별
        result.weak_sessions = [
            name
            for name, stats in result.sessions.items()
            if stats.win_rate < WEAK_SESSION_WIN_RATE
            and name != UNKNOWN_SESSION
        ]

        return result

    def _classify_trade(self, trade: Trade) -> str:
        """거래를 세션으로 분류.

        Trade.entry_time이 datetime이면 SessionClassifier 사용.
        그 외 타입은 UNKNOWN으로 분류.
        """
        entry_time = trade.entry_time
        if isinstance(entry_time, datetime):
            session = self._classifier.classify(entry_time)
            return session.value.upper()

        return UNKNOWN_SESSION

    def _compute_stats(
        self, session: str, trades: list[Trade],
    ) -> SessionStats:
        """세션별 통계 계산."""
        total = len(trades)
        pnls = [t.pnl or 0.0 for t in trades]
        winners = sum(1 for p in pnls if p > 0)
        win_rate = (winners / total * 100) if total > 0 else 0.0

        total_pnl = sum(pnls)
        avg_pnl = total_pnl / total if total > 0 else 0.0

        sharpe = self._calculate_sharpe(pnls)
        pf = self._calculate_profit_factor(pnls)

        if win_rate < WEAK_SESSION_WIN_RATE and session != UNKNOWN_SESSION:
            recommendation = "DISABLE"
        elif win_rate < 55.0:  # noqa: PLR2004
            recommendation = "REVIEW"
        else:
            recommendation = "ENABLE"

        return SessionStats(
            session=session,
            total_trades=total,
            winning_trades=winners,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            sharpe_ratio=sharpe,
            profit_factor=pf,
            recommendation=recommendation,
        )

    def _calculate_sharpe(self, pnls: list[float]) -> float:
        """Sharpe ratio 계산."""
        if len(pnls) < MIN_TRADES_FOR_SHARPE:
            return 0.0

        mean_r = sum(pnls) / len(pnls)
        variance = sum((r - mean_r) ** 2 for r in pnls) / (len(pnls) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return 0.0
        return (mean_r / std) * math.sqrt(252)

    def _calculate_profit_factor(self, pnls: list[float]) -> float:
        """Profit factor 계산 (총 수익 / 총 손실)."""
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss
