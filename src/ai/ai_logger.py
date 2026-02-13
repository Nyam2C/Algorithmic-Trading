"""AI 의사결정 과정 구조화 로깅 모듈.

Gemini API 호출, 앙상블 결정 등 AI 의사결정 과정을
event_type 바인딩으로 구조화 로깅합니다.
ai_signal.json.log 파일에 자동 라우팅됩니다.
"""
from typing import Any

from loguru import logger


class AIDecisionLogger:
    """AI 의사결정 과정을 구조화 로깅.

    event_type='AI_SIGNAL' 또는 'ENSEMBLE_SIGNAL'로 바인딩하여
    Phase 1에서 설정한 ai_signal.json.log에 자동 라우팅합니다.

    Example:
        >>> ai_logger = AIDecisionLogger()
        >>> ai_logger.log_gemini_call(
        ...     bot_name="btc-bot",
        ...     prompt_summary="RSI=35, MA7>MA25...",
        ...     raw_response="LONG",
        ...     parsed_signal="LONG",
        ...     reason="RSI 과매도 + 상승 추세",
        ...     memory_used=True,
        ...     latency_ms=1250.0,
        ...     model="gemini-2.5-flash",
        ... )
    """

    def __init__(self) -> None:
        """초기화."""
        self._log = logger.bind(module="ai_logger")

    def log_gemini_call(
        self,
        bot_name: str,
        prompt_summary: str,
        raw_response: str,
        parsed_signal: str,
        reason: str = "",
        memory_used: bool = False,
        latency_ms: float = 0.0,
        model: str = "",
    ) -> None:
        """Gemini API 호출 결과를 구조화 로깅.

        Args:
            bot_name: 봇 이름
            prompt_summary: 프롬프트 요약 (마지막 500자)
            raw_response: AI 원시 응답
            parsed_signal: 파싱된 시그널 (LONG/SHORT/WAIT)
            reason: AI가 제시한 이유
            memory_used: 메모리 컨텍스트 사용 여부
            latency_ms: API 응답시간 (밀리초)
            model: 사용된 모델명
        """
        logger.bind(
            event_type="AI_SIGNAL",
            signal=parsed_signal,
            bot_name=bot_name,
            prompt_summary=prompt_summary[-500:] if prompt_summary else "",
            raw_response=raw_response,
            parsed_signal=parsed_signal,
            reason=reason,
            memory_used=memory_used,
            latency_ms=round(latency_ms, 1),
            model=model,
        ).info("Gemini AI 시그널 생성")

    def log_ensemble_decision(
        self,
        bot_name: str,
        component_signals: list[dict[str, Any]],
        final_signal: str,
        consensus_ratio: float,
        weighted_score: float = 0.0,
    ) -> None:
        """앙상블 결정 과정을 구조화 로깅.

        Args:
            bot_name: 봇 이름
            component_signals: 개별 시그널 목록
            final_signal: 최종 시그널
            consensus_ratio: 합의 비율
            weighted_score: 가중 점수
        """
        logger.bind(
            event_type="ENSEMBLE_SIGNAL",
            signal=final_signal,
            bot_name=bot_name,
            component_signals=component_signals,
            final_signal=final_signal,
            consensus_ratio=round(consensus_ratio, 3),
            weighted_score=round(weighted_score, 3),
        ).info("앙상블 시그널 결정")
