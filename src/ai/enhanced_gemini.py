"""
Enhanced Gemini AI client with memory integration

Phase 4: AI 메모리 시스템 - 과거 거래 분석을 프롬프트에 주입
기존 GeminiSignalGenerator를 확장하여 메모리 컨텍스트 지원
"""
from typing import Dict, Optional
from pathlib import Path
from google.genai.errors import ClientError, ServerError
from loguru import logger

from src.ai.gemini import GeminiSignalGenerator
from src.analytics.memory_context import MemoryContext, AIMemoryContextBuilder
from src.utils.retry import async_retry


class EnhancedGeminiSignalGenerator(GeminiSignalGenerator):
    """메모리 주입된 Gemini 시그널 생성기

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
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.1,
        context_builder: Optional[AIMemoryContextBuilder] = None,
        memory_enabled: bool = True,
        memory_days: int = 7,
    ):
        """Enhanced Gemini 클라이언트 초기화

        Args:
            api_key: Gemini API 키
            model: 모델명 (기본: gemini-2.0-flash-exp)
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

        self._log = logger.bind(module="enhanced_gemini")
        self._log.info(
            f"Enhanced Gemini 초기화 (memory_enabled={self.memory_enabled})"
        )

    @property
    def memory_enabled(self) -> bool:
        """메모리 기능 활성화 여부"""
        return self._memory_enabled and self.context_builder is not None

    def _load_memory_prompt(self) -> str:
        """메모리 시스템 프롬프트 로드

        Returns:
            메모리 시스템 프롬프트 내용
        """
        try:
            prompt_dir = Path(__file__).parent / "prompts"
            prompt_path = prompt_dir / "memory_system.txt"
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except FileNotFoundError:
            self._log.warning("메모리 시스템 프롬프트 파일 없음 - 기본 프롬프트 사용")
            return self._get_default_memory_prompt()
        except Exception as e:
            self._log.error(f"메모리 프롬프트 로드 실패: {e}")
            return self._get_default_memory_prompt()

    def _get_default_memory_prompt(self) -> str:
        """기본 메모리 프롬프트 반환"""
        return """You are a Bitcoin futures trading analyst with MEMORY of past trades.
Review past trade statistics before making decisions.
If current conditions match historically successful patterns, increase confidence.
If current conditions match historically failed patterns, output WAIT.
Output ONLY: LONG, SHORT, or WAIT."""

    def set_context_builder(self, builder: AIMemoryContextBuilder) -> None:
        """컨텍스트 빌더 설정

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
        market_data: Dict,
        bot_id: Optional[str] = None,
    ) -> str:
        """메모리 포함 시그널 생성

        과거 거래 분석 결과를 프롬프트에 포함하여 시그널 생성

        Args:
            market_data: 시장 데이터 딕셔너리
            bot_id: 봇 ID (선택)

        Returns:
            시그널: "LONG", "SHORT", or "WAIT"
        """
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

            self._log.debug("Calling Gemini API with memory context...")

            # 3. Gemini API 호출
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

    def _build_prompt_with_memory(
        self,
        market_data: Dict,
        memory_context: Optional[MemoryContext],
    ) -> str:
        """메모리 포함 프롬프트 빌드

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
        full_prompt = f"{system_prompt}{memory_section}\n{market_prompt}"

        return full_prompt

    async def get_signal(self, market_data: Dict) -> str:
        """시그널 생성 (기존 호환성 유지)

        메모리 없이 기존 방식으로 시그널 생성

        Args:
            market_data: 시장 데이터 딕셔너리

        Returns:
            시그널: "LONG", "SHORT", or "WAIT"
        """
        # 기존 GeminiSignalGenerator의 get_signal 호출
        return await super().get_signal(market_data)
