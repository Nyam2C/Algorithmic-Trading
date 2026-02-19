"""AI 앙상블 시스템.

Phase 6.3: 다중 신호 소스 앙상블
- Gemini AI, 규칙 기반, 스코어링 신호 결합
- 가중 투표로 최종 신호 결정
- 2/3 합의 시 신호 발생
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

from src.ai.ai_logger import AIDecisionLogger


class SignalSource(Enum):
    """신호 소스 종류."""

    GEMINI_AI = "gemini"
    RULE_BASED = "rule_based"
    SCORING = "scoring"
    MEMORY_GEMINI = "memory_gemini"
    FUNDING_BASIS = "funding_basis"
    LEVERAGE_TOPOLOGY = "leverage_topology"
    SMART_MONEY = "smart_money"
    TSMOM = "tsmom"
    OFI = "ofi"
    WHALE_FLOW = "whale_flow"
    LIQUIDATION_CASCADE = "liquidation_cascade"


@dataclass
class IndividualSignal:
    """개별 신호.

    Attributes:
        source: 신호 소스
        signal: 신호 ("LONG", "SHORT", "WAIT")
        confidence: 신뢰도 (0 ~ 1)
        reason: 신호 생성 이유
        weight: 가중치
    """

    source: SignalSource
    signal: str
    confidence: float = 1.0
    reason: str = ""
    weight: float = 1.0

    def weighted_vote(self) -> float:
        """가중 투표 값 반환.

        Returns:
            LONG: +weight, SHORT: -weight, WAIT: 0
        """
        if self.signal == "LONG":
            return self.weight * self.confidence
        if self.signal == "SHORT":
            return -self.weight * self.confidence
        return 0.0


@dataclass
class EnsembleResult:
    """앙상블 결과.

    Attributes:
        final_signal: 최종 신호
        individual_signals: 개별 신호 목록
        consensus_ratio: 합의 비율
        weighted_score: 가중 점수
        metadata: 추가 메타데이터
    """

    final_signal: str
    individual_signals: list[IndividualSignal]
    consensus_ratio: float = 0.0
    weighted_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    confluence_result: Any = None  # ConfluenceResult | None (순환 import 방지)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "final_signal": self.final_signal,
            "individual_signals": [
                {
                    "source": s.source.value,
                    "signal": s.signal,
                    "confidence": round(s.confidence, 3),
                    "reason": s.reason,
                    "weight": s.weight,
                }
                for s in self.individual_signals
            ],
            "consensus_ratio": round(self.consensus_ratio, 3),
            "weighted_score": round(self.weighted_score, 3),
            "metadata": self.metadata,
        }


class EnsembleSignalGenerator:
    """앙상블 신호 생성기.

    여러 신호 소스를 결합하여 최종 신호를 생성합니다.

    Example:
        >>> ensemble = EnsembleSignalGenerator()
        >>> result = await ensemble.generate_ensemble_signal(market_data, "btc-bot")
        >>> print(f"Signal: {result.final_signal}")
    """

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        SignalSource.GEMINI_AI: 0.4,
        SignalSource.RULE_BASED: 0.3,
        SignalSource.SCORING: 0.3,
    }

    # 합의 임계값
    CONSENSUS_THRESHOLD = 2 / 3  # 2/3 합의 필요
    WEIGHTED_THRESHOLD = 0.3  # 가중 점수 임계값 (공격적 시그널)
    MIN_SOURCES = 1  # 최소 소스 수 (단일 소스 허용)

    def __init__(
        self,
        weights: dict[SignalSource, float] | None = None,
        consensus_threshold: float = CONSENSUS_THRESHOLD,
        weighted_threshold: float = WEIGHTED_THRESHOLD,
        # 의존성 주입
        gemini_generator: Any | None = None,
        rule_based_generator: Any | None = None,
        scoring_generator: Any | None = None,
    ) -> None:
        """앙상블 생성기 초기화.

        Args:
            weights: 소스별 가중치
            consensus_threshold: 합의 임계값
            weighted_threshold: 가중 점수 임계값
            gemini_generator: Gemini AI 생성기
            rule_based_generator: 규칙 기반 생성기
            scoring_generator: 스코어링 생성기
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.consensus_threshold = consensus_threshold
        self.weighted_threshold = weighted_threshold

        self._gemini = gemini_generator
        self._rule_based = rule_based_generator
        self._scoring = scoring_generator

        # APEX-V Phase B: 4채널 슬롯
        self._funding_channel: Any | None = None
        self._leverage_channel: Any | None = None
        self._smart_money_channel: Any | None = None
        self._tsmom_channel: Any | None = None

        # APEX-V Fast Layer 채널
        self._ofi_channel: Any | None = None
        self._whale_flow_channel: Any | None = None

        # APEX-V: Liquidation Cascade Hunter
        self._liquidation_cascade_channel: Any | None = None

        # APEX-V Phase C: Confluence Engine
        self._confluence_engine: Any | None = None

        self._ai_logger = AIDecisionLogger()
        self._last_ensemble_result: EnsembleResult | None = None
        self._log = logger.bind(module="ensemble")
        self._log.info(
            f"EnsembleSignalGenerator 초기화: weights={self.weights}"
        )

    def set_gemini_generator(self, generator: Any) -> None:
        """Gemini 생성기 설정."""
        self._gemini = generator

    def set_rule_based_generator(self, generator: Any) -> None:
        """규칙 기반 생성기 설정."""
        self._rule_based = generator

    def set_scoring_generator(self, generator: Any) -> None:
        """스코어링 생성기 설정."""
        self._scoring = generator

    def set_funding_channel(self, channel: Any) -> None:
        """FundingBasis 채널 설정."""
        self._funding_channel = channel

    def set_leverage_channel(self, channel: Any) -> None:
        """LeverageTopology 채널 설정."""
        self._leverage_channel = channel

    def set_smart_money_channel(self, channel: Any) -> None:
        """SmartMoneyDivergence 채널 설정."""
        self._smart_money_channel = channel

    def set_tsmom_channel(self, channel: Any) -> None:
        """TSMOM 채널 설정."""
        self._tsmom_channel = channel

    def set_ofi_channel(self, channel: Any) -> None:
        """OFI 채널 설정."""
        self._ofi_channel = channel

    def set_whale_flow_channel(self, channel: Any) -> None:
        """WhaleFlow 채널 설정."""
        self._whale_flow_channel = channel

    def set_liquidation_cascade_channel(self, channel: Any) -> None:
        """LiquidationCascadeHunter 채널 설정."""
        self._liquidation_cascade_channel = channel

    def set_confluence_engine(self, engine: Any) -> None:
        """Confluence Engine 설정 (Phase C)."""
        self._confluence_engine = engine

    async def generate_ensemble_signal(
        self,
        market_data: dict[str, Any],
        bot_id: str = "",
        sentiment_data: dict[str, Any] | None = None,
        klines_df: Any | None = None,
    ) -> EnsembleResult:
        """앙상블 신호 생성.

        Args:
            market_data: 시장 데이터
            bot_id: 봇 ID
            sentiment_data: 심리 데이터 (Phase B 채널용)
            klines_df: OHLCV DataFrame (TSMOM 채널용)

        Returns:
            EnsembleResult
        """
        individual_signals: list[IndividualSignal] = []

        # 1. 각 소스에서 신호 수집
        # Gemini AI (Phase D: confluence 활성 시 Gemini는 Step 8 검증 전용)
        if self._gemini and not self._confluence_engine:
            try:
                gemini_signal = await self._get_gemini_signal(market_data)
                individual_signals.append(gemini_signal)
            except Exception as e:
                self._log.warning(f"Gemini 신호 생성 실패: {e}")

        # Rule-based
        if self._rule_based:
            try:
                rule_signal = self._get_rule_based_signal(market_data)
                individual_signals.append(rule_signal)
            except Exception as e:
                self._log.warning(f"규칙 기반 신호 생성 실패: {e}")

        # Scoring
        if self._scoring:
            try:
                scoring_signal = self._get_scoring_signal(market_data)
                individual_signals.append(scoring_signal)
            except Exception as e:
                self._log.warning(f"스코어링 신호 생성 실패: {e}")

        # APEX-V Phase B: 4채널 시그널 수집
        channel_signals = await self._collect_channel_signals(
            sentiment_data, klines_df
        )
        individual_signals.extend(channel_signals)

        # 신호가 없으면 WAIT
        if not individual_signals:
            self._log.warning("신호 소스 없음 - WAIT 반환")
            return EnsembleResult(
                final_signal="WAIT",
                individual_signals=[],
                metadata={"error": "신호 소스 없음"},
            )

        # Phase C: Confluence Engine 라우팅
        if self._confluence_engine is not None:
            from src.data.regime_detector import MarketRegime  # noqa: PLC0415
            indicators = market_data.get("indicators", {})
            regime = indicators.get("regime", MarketRegime.UNKNOWN)
            confluence_result = await self._confluence_engine.evaluate(
                individual_signals, regime, market_data
            )
            result = EnsembleResult(
                final_signal=confluence_result.final_signal,
                individual_signals=individual_signals,
                consensus_ratio=0.0,
                weighted_score=confluence_result.confluence_score,
                metadata={
                    "bot_id": bot_id,
                    "sources_used": len(individual_signals),
                    "confluence": confluence_result.step_details,
                },
                confluence_result=confluence_result,
            )
            self._last_ensemble_result = result
            return result

        # 2. 가중 투표
        final_signal, weighted_score, consensus_ratio = self._weighted_vote(
            individual_signals
        )

        result = EnsembleResult(
            final_signal=final_signal,
            individual_signals=individual_signals,
            consensus_ratio=consensus_ratio,
            weighted_score=weighted_score,
            metadata={
                "bot_id": bot_id,
                "sources_used": len(individual_signals),
            },
        )
        self._last_ensemble_result = result

        self._log.info(
            f"앙상블 신호: {final_signal} "
            f"(합의율={consensus_ratio:.1%}, 가중점수={weighted_score:.3f})"
        )

        # AI 의사결정 로깅
        self._ai_logger.log_ensemble_decision(
            bot_name=bot_id,
            component_signals=[
                {
                    "source": s.source.value,
                    "signal": s.signal,
                    "confidence": round(s.confidence, 3),
                    "weight": s.weight,
                }
                for s in individual_signals
            ],
            final_signal=final_signal,
            consensus_ratio=consensus_ratio,
            weighted_score=weighted_score,
        )

        return result

    async def _collect_channel_signals(  # noqa: PLR0912, PLR0915
        self,
        sentiment_data: dict[str, Any] | None,
        klines_df: Any | None,
    ) -> list[IndividualSignal]:
        """4채널 시그널 수집 (TSMOM, Funding, Leverage, SmartMoney)."""
        signals: list[IndividualSignal] = []

        if self._tsmom_channel and klines_df is not None:
            try:
                sig = await self._tsmom_channel.generate_signal(klines_df)
                signals.append(sig)
            except Exception as e:
                self._log.warning(f"TSMOM 채널 실패: {e}")

        if not sentiment_data:
            return signals

        if self._funding_channel:
            try:
                sig = await self._funding_channel.generate_signal(
                    sentiment_data.get("funding_rate"),
                    sentiment_data.get("long_short_ratio"),
                    basis=sentiment_data.get("basis"),
                    oi_change_pct=sentiment_data.get("oi_change_pct"),
                )
                signals.append(sig)
            except Exception as e:
                self._log.warning(f"FundingBasis 채널 실패: {e}")

        if self._leverage_channel:
            try:
                sig = await self._leverage_channel.generate_signal(
                    sentiment_data.get("open_interest"),
                    sentiment_data.get("current_price"),
                    sentiment_data.get("oi_history"),
                )
                signals.append(sig)
            except Exception as e:
                self._log.warning(f"LeverageTopology 채널 실패: {e}")

        if self._smart_money_channel:
            try:
                ls_ratio = sentiment_data.get("long_short_ratio")
                price = sentiment_data.get("current_price", 0)
                ls_hist = sentiment_data.get("ls_history", [])
                price_change_pct = 0.0
                if ls_hist and price > 0:
                    prev_price = ls_hist[-1].get("price", price)
                    if prev_price > 0:
                        price_change_pct = (price - prev_price) / prev_price
                sig = await self._smart_money_channel.generate_signal(
                    ls_ratio, price_change_pct, ls_hist,
                    global_long_ratio=sentiment_data.get("global_long_ratio"),
                    global_short_ratio=sentiment_data.get("global_short_ratio"),
                    taker_buy_sell_ratio=sentiment_data.get("taker_buy_sell_ratio"),
                )
                signals.append(sig)
            except Exception as e:
                self._log.warning(f"SmartMoney 채널 실패: {e}")

        # APEX-V Fast Layer: OFI 채널
        if self._ofi_channel and sentiment_data:
            try:
                ofi_snapshot = sentiment_data.get("ofi_snapshot")
                if ofi_snapshot:
                    sig = await self._ofi_channel.generate_signal(ofi_snapshot)
                    signals.append(sig)
            except Exception as e:
                self._log.warning(f"OFI 채널 실패: {e}")

        # APEX-V Fast Layer: WhaleFlow 채널
        if self._whale_flow_channel and sentiment_data:
            try:
                whale_snapshot = sentiment_data.get("whale_snapshot")
                if whale_snapshot:
                    sig = await self._whale_flow_channel.generate_signal(whale_snapshot)
                    signals.append(sig)
            except Exception as e:
                self._log.warning(f"WhaleFlow 채널 실패: {e}")

        # APEX-V: Liquidation Cascade Hunter
        if self._liquidation_cascade_channel and sentiment_data:
            try:
                liq_snapshot = sentiment_data.get("liquidation_snapshot")
                daily_avg = sentiment_data.get("liquidation_daily_avg", 0.0)
                if liq_snapshot:
                    depth_snap = sentiment_data.get("depth_snapshot")
                    sig = await self._liquidation_cascade_channel.generate_signal(
                        liq_snapshot, daily_avg, depth=depth_snap,
                    )
                    signals.append(sig)
            except Exception as e:
                self._log.warning(f"LiquidationCascade 채널 실패: {e}")

        return signals

    async def _get_gemini_signal(
        self, market_data: dict[str, Any]
    ) -> IndividualSignal:
        """Gemini 신호 가져오기."""
        if self._gemini is None:
            raise RuntimeError("Gemini generator is required")
        # get_signal_with_reason 사용 시도
        if hasattr(self._gemini, "get_signal_with_reason"):
            signal, reason = await self._gemini.get_signal_with_reason(market_data)
        else:
            signal = await self._gemini.get_signal(market_data)
            reason = "Gemini AI 분석"

        # Phase 9: 파싱된 신뢰도 사용, 없으면 0.6 기본값
        confidence = 0.6
        raw_conf = getattr(self._gemini, 'last_confidence', None)
        if isinstance(raw_conf, (int, float)) and 0 < raw_conf <= 1:
            confidence = float(raw_conf)

        return IndividualSignal(
            source=SignalSource.GEMINI_AI,
            signal=signal,
            confidence=confidence,
            reason=reason,
            weight=self.weights.get(SignalSource.GEMINI_AI, 0.4),
        )

    def _get_rule_based_signal(
        self, market_data: dict[str, Any]
    ) -> IndividualSignal:
        """규칙 기반 신호 가져오기."""
        if self._rule_based is None:
            raise RuntimeError("Rule-based generator is required")
        signal = self._rule_based.get_signal(market_data)

        return IndividualSignal(
            source=SignalSource.RULE_BASED,
            signal=signal,
            confidence=1.0,  # 규칙 기반은 명확
            reason="규칙 기반 분석",
            weight=self.weights.get(SignalSource.RULE_BASED, 0.3),
        )

    def _get_scoring_signal(
        self, market_data: dict[str, Any]
    ) -> IndividualSignal:
        """스코어링 신호 가져오기."""
        if self._scoring is None:
            raise RuntimeError("Scoring generator is required")
        # calculate_score 사용 시도
        if hasattr(self._scoring, "calculate_score"):
            result = self._scoring.calculate_score(market_data)
            signal = result.signal
            confidence = result.confidence
            reason = ", ".join(result.reasons) if result.reasons else "점수 기반"
        else:
            signal = self._scoring.get_signal(market_data)
            confidence = 0.7
            reason = "점수 기반 분석"

        return IndividualSignal(
            source=SignalSource.SCORING,
            signal=signal,
            confidence=confidence,
            reason=reason,
            weight=self.weights.get(SignalSource.SCORING, 0.3),
        )

    def _weighted_vote(
        self,
        signals: list[IndividualSignal],
    ) -> tuple[str, float, float]:
        """가중 투표.

        Args:
            signals: 개별 신호 목록

        Returns:
            (final_signal, weighted_score, consensus_ratio)
        """
        if not signals:
            return "WAIT", 0.0, 0.0

        # 가중 점수 계산
        total_weight = sum(s.weight for s in signals)
        weighted_score = sum(s.weighted_vote() for s in signals)

        if total_weight > 0:
            weighted_score /= total_weight

        # 신호별 카운트
        long_count = sum(1 for s in signals if s.signal == "LONG")
        short_count = sum(1 for s in signals if s.signal == "SHORT")
        wait_count = sum(1 for s in signals if s.signal == "WAIT")

        total_count = len(signals)

        # 합의 비율 계산
        max_count = max(long_count, short_count, wait_count)
        consensus_ratio = max_count / total_count if total_count > 0 else 0

        # 최종 신호 결정
        # 1. 가중 점수 기준 (최소 2개 소스 필요)
        has_enough_sources = len(signals) >= self.MIN_SOURCES
        if abs(weighted_score) >= self.weighted_threshold and has_enough_sources:
            if weighted_score > 0:
                return "LONG", weighted_score, consensus_ratio
            return "SHORT", weighted_score, consensus_ratio

        # 2. 합의 기준 (2/3 이상, 최소 2개 소스)
        if has_enough_sources:
            if long_count / total_count >= self.consensus_threshold:
                return "LONG", weighted_score, consensus_ratio
            if short_count / total_count >= self.consensus_threshold:
                return "SHORT", weighted_score, consensus_ratio

        # 3. 합의 실패 -> WAIT
        return "WAIT", weighted_score, consensus_ratio

    def get_signal(self, market_data: dict[str, Any]) -> str:
        """동기 신호 반환 (규칙 기반 + 스코어링만 사용).

        Args:
            market_data: 시장 데이터

        Returns:
            신호
        """
        signals: list[IndividualSignal] = []

        if self._rule_based:
            signals.append(self._get_rule_based_signal(market_data))

        if self._scoring:
            signals.append(self._get_scoring_signal(market_data))

        if not signals:
            return "WAIT"

        final_signal, _, _ = self._weighted_vote(signals)
        return final_signal

    async def get_signal_async(
        self,
        market_data: dict[str, Any],
        bot_id: str = "",
    ) -> str:
        """비동기 신호 반환 (Gemini 포함).

        Args:
            market_data: 시장 데이터
            bot_id: 봇 ID

        Returns:
            신호
        """
        result = await self.generate_ensemble_signal(market_data, bot_id)
        return result.final_signal
