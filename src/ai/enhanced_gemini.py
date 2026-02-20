"""Enhanced Gemini AI client with memory integration.

Phase 4: AI 메모리 시스템 - 과거 거래 분석을 프롬프트에 주입
기존 GeminiSignalGenerator를 확장하여 메모리 컨텍스트 지원
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from google.genai.errors import ClientError, ServerError
from loguru import logger

from src.ai.ai_logger import AIDecisionLogger
from src.ai.gemini import GeminiSignalGenerator
from src.analytics.memory_context import AIMemoryContextBuilder, MemoryContext
from src.utils.retry import async_retry


class EnhancedGeminiSignalGenerator(GeminiSignalGenerator):
    """메모리 주입된 Gemini 시그널 생성기.

    과거 거래 분석 결과를 AI 프롬프트에 주입하여
    데이터 기반 의사결정을 지원합니다.

    Attributes:
        context_builder: AIMemoryContextBuilder 인스턴스
        memory_enabled: 메모리 기능 활성화 여부
        memory_days: 메모리 분석 기간 (일)

    Example:
        >>> generator = EnhancedGeminiSignalGenerator(
        ...     api_key="...",
        ...     context_builder=context_builder,
        ... )
        >>> signal = await generator.get_signal_with_memory(
        ...     market_data=data,
        ...     bot_id="btc-bot",
        ... )
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.1,
        context_builder: AIMemoryContextBuilder | None = None,
        memory_enabled: bool = True,
        memory_days: int = 7,
    ):
        """Enhanced Gemini 클라이언트 초기화.

        Args:
            api_key: Gemini API 키
            model: 모델명 (기본: gemini-2.5-flash)
            temperature: 생성 온도 (기본: 0.1)
            context_builder: AI 메모리 컨텍스트 빌더 (선택)
            memory_enabled: 메모리 기능 활성화 (기본: True)
            memory_days: 메모리 분석 기간 (기본: 7일)
        """
        super().__init__(
            api_key=api_key,
            model=model,
            temperature=temperature,
        )

        self.context_builder = context_builder
        self._memory_enabled = memory_enabled if context_builder else False
        self.memory_days = memory_days

        # 메모리 시스템 프롬프트 로드
        self.memory_system_prompt = self._load_memory_prompt()

        self._ai_logger = AIDecisionLogger()
        self._log = logger.bind(module="enhanced_gemini")
        self._log.info(
            f"Enhanced Gemini 초기화 (memory_enabled={self.memory_enabled})"
        )

        # 마지막 AI 호출 기록 (디버깅/Discord 조회용)
        self._last_prompt: str | None = None
        self._last_response: str | None = None
        self._last_call_time: datetime | None = None
        self._last_signal: str | None = None

    @property
    def memory_enabled(self) -> bool:
        """메모리 기능 활성화 여부."""
        return self._memory_enabled and self.context_builder is not None

    def _load_memory_prompt(self) -> str:
        """메모리 시스템 프롬프트 로드.

        Returns:
            메모리 시스템 프롬프트 내용
        """
        try:
            prompt_dir = Path(__file__).parent / "prompts"
            prompt_path = prompt_dir / "memory_system.txt"
            with prompt_path.open(encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            self._log.warning("메모리 시스템 프롬프트 파일 없음 - 기본 프롬프트 사용")
            return self._get_default_memory_prompt()
        except Exception as e:
            self._log.error(f"메모리 프롬프트 로드 실패: {e}")
            return self._get_default_memory_prompt()

    def _get_default_memory_prompt(self) -> str:
        """기본 메모리 프롬프트 반환."""
        return """You are a Bitcoin futures trading analyst with MEMORY of past trades.
Review past trade statistics before making decisions.
If current conditions match historically successful patterns, increase confidence.
If current conditions match historically failed patterns, output WAIT.
Output ONLY: LONG, SHORT, or WAIT."""

    def set_context_builder(self, builder: AIMemoryContextBuilder) -> None:
        """컨텍스트 빌더 설정.

        Args:
            builder: AIMemoryContextBuilder 인스턴스
        """
        self.context_builder = builder
        self._memory_enabled = True
        self._log.info("컨텍스트 빌더 설정됨 - 메모리 활성화")

    @async_retry(
        max_attempts=3,
        delay=2.0,
        backoff=2.0,
        exceptions=(ClientError, ServerError, ConnectionError, TimeoutError),
    )
    async def get_signal_with_memory(
        self,
        market_data: dict,
        bot_id: str | None = None,
    ) -> str:
        """메모리 포함 시그널 생성.

        과거 거래 분석 결과를 프롬프트에 포함하여 시그널 생성

        Args:
            market_data: 시장 데이터 딕셔너리
            bot_id: 봇 ID (선택)

        Returns:
            시그널: "LONG", "SHORT", or "WAIT"
        """
        t0 = time.monotonic()
        raw_response_text = ""
        signal = "WAIT"
        memory_used = False
        prompt_summary = ""
        try:
            # 1. 메모리 컨텍스트 생성
            memory_context = None
            if self.memory_enabled and self.context_builder:
                try:
                    memory_context = await self.context_builder.build_context(
                        bot_id=bot_id,
                        days=self.memory_days,
                    )
                    if not memory_context.is_empty():
                        self._log.debug("메모리 컨텍스트 생성 완료")
                        memory_used = True
                    else:
                        self._log.debug("메모리 컨텍스트 비어있음")
                        memory_context = None
                except Exception as e:
                    self._log.warning(f"메모리 컨텍스트 생성 실패: {e}")
                    memory_context = None

            # 2. 프롬프트 빌드
            full_prompt = self._build_prompt_with_memory(
                market_data=market_data,
                memory_context=memory_context,
            )
            prompt_summary = full_prompt

            self._log.debug("Calling Gemini API with memory context...")

            # 3. Gemini API 호출 (세마포어로 동시 호출 제한)
            async with self._get_semaphore():
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config={
                        "temperature": self.temperature,
                        "max_output_tokens": 10,
                    },
                )

            # 4. 응답 파싱
            if response.text is None:
                self._log.warning("Empty response from Gemini, defaulting to WAIT")
                return "WAIT"

            raw_response_text = response.text
            signal = response.text.strip().upper()

            # 5. 시그널 검증
            if signal not in ["LONG", "SHORT", "WAIT"]:
                self._log.warning(
                    f"Invalid signal '{signal}' from Gemini, defaulting to WAIT"
                )
                return "WAIT"

            self._log.info(
                f"Signal generated: {signal} "
                f"(memory_used={memory_context is not None})"
            )
            return signal

        except Exception as e:
            self._log.error(f"Gemini API error: {e}")
            self._log.warning("Defaulting to WAIT due to error")
            return "WAIT"
        finally:
            # 마지막 호출 기록 저장
            self._last_prompt = prompt_summary
            self._last_response = raw_response_text
            self._last_call_time = datetime.now()
            self._last_signal = signal

            latency_ms = (time.monotonic() - t0) * 1000
            self._ai_logger.log_gemini_call(
                bot_name=bot_id or "",
                prompt_summary=prompt_summary,
                raw_response=raw_response_text,
                parsed_signal=signal,
                reason="",
                memory_used=memory_used,
                latency_ms=latency_ms,
                model=self.model,
            )

    def get_last_ai_call(self) -> dict[str, Any] | None:
        """마지막 AI 호출 정보 반환.

        Discord 디버깅 명령어에서 사용합니다.

        Returns:
            마지막 호출 정보 딕셔너리 또는 None
        """
        if self._last_prompt is None:
            return None
        return {
            "prompt": self._last_prompt,
            "response": self._last_response,
            "timestamp": self._last_call_time,
            "model": self.model,
            "signal": self._last_signal,
        }

    async def generate_weekly_report(
        self,
        bot_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """주간 배치 분석 리포트 생성.

        과거 거래 통계를 수집하여 AI에게 패턴 분석/파라미터 제안을 요청.

        Args:
            bot_id: 봇 ID
            days: 분석 기간 (기본: 7일)

        Returns:
            리포트 딕셔너리 (summary, insights, recommendations, raw_context)
        """
        t0 = time.monotonic()
        empty_result: dict[str, Any] = {
            "summary": "분석 불가",
            "insights": [],
            "recommendations": [],
            "raw_context": None,
        }

        if not self.context_builder:
            self._log.warning("주간 리포트: context_builder 미설정")
            return empty_result

        # 1. 메모리 컨텍스트 수집
        try:
            memory_context = await self.context_builder.build_context(
                bot_id=bot_id,
                days=days,
            )
        except Exception as e:
            self._log.warning(f"주간 리포트: 컨텍스트 수집 실패: {e}")
            return empty_result

        if memory_context.is_empty():
            self._log.info("주간 리포트: 거래 이력 없음 — 스킵")
            empty_result["summary"] = "거래 이력 없음"
            return empty_result

        # 2. 분석 프롬프트 로드
        analysis_prompt = self._load_weekly_analysis_prompt()

        # 3. 전체 프롬프트 조합
        full_prompt = (
            f"{analysis_prompt}\n\n"
            f"=== 거래 통계 ===\n{memory_context.to_prompt()}"
        )

        # 4. Gemini API 호출
        try:
            async with self._get_semaphore():
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config={
                        "temperature": 0.3,
                        "max_output_tokens": 1024,
                    },
                )

            raw_text = response.text or ""
            latency_ms = (time.monotonic() - t0) * 1000

            self._ai_logger.log_gemini_call(
                bot_name=bot_id,
                prompt_summary="weekly_report",
                raw_response=raw_text[:200],
                parsed_signal="REPORT",
                reason="weekly_analysis",
                memory_used=True,
                latency_ms=latency_ms,
                model=self.model,
            )

            # 5. 응답 파싱 (단순 텍스트 → 구조화)
            return self._parse_weekly_report(raw_text, memory_context)

        except Exception as e:
            self._log.warning(f"주간 리포트: Gemini 호출 실패: {e}")
            return empty_result

    def _load_weekly_analysis_prompt(self) -> str:
        """주간 분석 프롬프트 로드."""
        try:
            prompt_dir = Path(__file__).parent / "prompts"
            prompt_path = prompt_dir / "weekly_analysis.txt"
            with prompt_path.open(encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return (
                "You are a trading performance analyst.\n"
                "Analyze the following trade statistics and provide:\n"
                "1. Summary of performance\n"
                "2. Key insights and patterns\n"
                "3. Actionable recommendations\n"
                "Format: SUMMARY: ..., INSIGHTS: ..., RECOMMENDATIONS: ..."
            )

    @staticmethod
    def _parse_weekly_report(
        raw_text: str, memory_context: MemoryContext
    ) -> dict[str, Any]:
        """주간 리포트 응답 파싱."""
        lines = raw_text.strip().split("\n")

        summary = ""
        insights: list[str] = []
        recommendations: list[str] = []

        section = "summary"
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if lower.startswith(("insight", "패턴", "분석")):
                section = "insights"
                continue
            if lower.startswith(("recommend", "제안", "권장")):
                section = "recommendations"
                continue
            if lower.startswith("summary") or lower.startswith("요약"):
                section = "summary"
                continue

            if section == "summary":
                summary += stripped + " "
            elif section == "insights":
                insights.append(stripped.lstrip("- •"))
            elif section == "recommendations":
                recommendations.append(stripped.lstrip("- •"))

        if not summary:
            summary = raw_text[:200]

        return {
            "summary": summary.strip(),
            "insights": insights,
            "recommendations": recommendations,
            "raw_context": memory_context,
        }

    def _build_prompt_with_memory(
        self,
        market_data: dict,
        memory_context: MemoryContext | None,
    ) -> str:
        """메모리 포함 프롬프트 빌드.

        Args:
            market_data: 시장 데이터
            memory_context: 메모리 컨텍스트 (선택)

        Returns:
            전체 프롬프트 문자열
        """
        # 1. 시스템 프롬프트 선택
        if memory_context and not memory_context.is_empty():
            system_prompt = self.memory_system_prompt
        else:
            system_prompt = self.system_prompt

        # 2. 메모리 컨텍스트 추가
        memory_section = ""
        if memory_context and not memory_context.is_empty():
            memory_section = f"\n\n{memory_context.to_prompt()}\n"

        # 3. 시장 데이터 프롬프트
        market_prompt = self._build_market_prompt(market_data)

        # 4. 전체 프롬프트 조합
        return f"{system_prompt}{memory_section}\n{market_prompt}"


    async def get_signal_with_reason(self, market_data: dict) -> tuple[str, str]:
        """시그널+이유 생성 (프롬프트 기록 포함).

        앙상블 경로에서 호출될 때도 _last_prompt가 저장되도록 오버라이드.

        Args:
            market_data: 시장 데이터 딕셔너리

        Returns:
            (시그널, 이유) 튜플
        """
        signal = "WAIT"
        reason = ""
        prompt_text = ""
        raw_response = ""
        try:
            user_prompt = self._build_market_prompt_with_reason(market_data)
            prompt_text = f"{self.system_prompt}\n\n{user_prompt}"
            signal, reason = await super().get_signal_with_reason(market_data)
            raw_response = f'{{"signal": "{signal}", "reason": "{reason}"}}'
            return signal, reason
        except Exception:
            raise
        finally:
            self._last_prompt = prompt_text
            self._last_response = raw_response
            self._last_call_time = datetime.now()
            self._last_signal = signal

    async def get_signal(self, market_data: dict) -> str:
        """시그널 생성 (프롬프트 기록 포함).

        Args:
            market_data: 시장 데이터 딕셔너리

        Returns:
            시그널: "LONG", "SHORT", or "WAIT"
        """
        signal = "WAIT"
        prompt_text = ""
        raw_response = ""
        try:
            user_prompt = self._build_market_prompt(market_data)
            prompt_text = f"{self.system_prompt}\n\n{user_prompt}"
            signal = await super().get_signal(market_data)
            raw_response = signal
            return signal
        except Exception:
            raise
        finally:
            self._last_prompt = prompt_text
            self._last_response = raw_response
            self._last_call_time = datetime.now()
            self._last_signal = signal
