"""
n8n 콜백 서비스 모듈

n8n 웹훅으로 이벤트 콜백을 발송합니다.
Phase 4.1: aiohttp 세션 재사용 및 URL 마스킹
"""
from typing import Any, Optional

import aiohttp
from loguru import logger

from src.api.schemas.n8n import N8NCallbackPayload


class N8NCallbackService:
    """n8n 콜백 서비스

    n8n 웹훅 URL로 이벤트 콜백을 발송합니다.

    Attributes:
        webhook_url: n8n 웹훅 URL
        is_enabled: 콜백 활성화 여부

    Phase 4.1 개선:
        - aiohttp 세션 재사용으로 성능 개선
        - 웹훅 URL 마스킹으로 보안 강화
    """

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        """n8n 콜백 서비스 초기화

        Args:
            webhook_url: n8n 웹훅 URL (없으면 비활성화)
        """
        self.webhook_url = webhook_url
        self.is_enabled = webhook_url is not None
        self._session: Optional[aiohttp.ClientSession] = None

        if self.is_enabled:
            # URL 마스킹 (보안)
            masked_url = webhook_url[:30] + "***" if webhook_url and len(webhook_url) > 30 else webhook_url
            logger.info(f"n8n 콜백 서비스 활성화: {masked_url}")
        else:
            logger.info("n8n 콜백 서비스 비활성화 (URL 없음)")

    async def _get_session(self) -> aiohttp.ClientSession:
        """세션 반환 (재사용)

        세션이 없거나 닫혀있으면 새로 생성합니다.

        Returns:
            aiohttp.ClientSession 인스턴스
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self) -> None:
        """세션 종료

        서비스 종료 시 호출하여 리소스를 정리합니다.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("n8n 콜백 서비스 세션 종료")

    async def send_callback(self, payload: N8NCallbackPayload) -> bool:
        """콜백 발송

        Args:
            payload: 콜백 페이로드

        Returns:
            발송 성공 여부
        """
        if not self.is_enabled:
            logger.debug("n8n 콜백 비활성화됨, 발송 스킵")
            return False

        try:
            session = await self._get_session()
            async with session.post(
                self.webhook_url,  # type: ignore
                json=payload.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status >= 200 and response.status < 300:
                    logger.debug(
                        f"n8n 콜백 발송 성공: {payload.event_type} "
                        f"(bot={payload.bot_name})"
                    )
                    return True
                else:
                    logger.warning(
                        f"n8n 콜백 발송 실패: HTTP {response.status}"
                    )
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"n8n 콜백 발송 에러 (네트워크): {e}")
            return False
        except Exception as e:
            logger.error(f"n8n 콜백 발송 에러: {e}")
            return False

    async def send_signal(
        self,
        bot_name: str,
        signal: str,
        price: float,
        confidence: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """시그널 콜백 발송

        Args:
            bot_name: 봇 이름
            signal: 시그널 (LONG, SHORT, WAIT)
            price: 현재 가격
            confidence: 신뢰도
            metadata: 추가 메타데이터

        Returns:
            발송 성공 여부
        """
        payload = N8NCallbackPayload(
            event_type="signal",
            bot_name=bot_name,
            data={
                "signal": signal,
                "price": price,
                "confidence": confidence,
                **(metadata or {}),
            },
        )
        return await self.send_callback(payload)

    async def send_trade(
        self,
        bot_name: str,
        action: str,
        side: str,
        price: float,
        pnl: Optional[float] = None,
        quantity: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """거래 콜백 발송

        Args:
            bot_name: 봇 이름
            action: 액션 (OPEN, CLOSE)
            side: 포지션 방향 (LONG, SHORT)
            price: 거래 가격
            pnl: 손익 (청산 시)
            quantity: 수량
            metadata: 추가 메타데이터

        Returns:
            발송 성공 여부
        """
        data: dict[str, Any] = {
            "action": action,
            "side": side,
            "price": price,
        }

        if pnl is not None:
            data["pnl"] = pnl
        if quantity is not None:
            data["quantity"] = quantity
        if metadata:
            data.update(metadata)

        payload = N8NCallbackPayload(
            event_type="trade",
            bot_name=bot_name,
            data=data,
        )
        return await self.send_callback(payload)

    async def send_error(
        self,
        bot_name: str,
        error: Exception,
        context: Optional[str] = None,
    ) -> bool:
        """에러 콜백 발송

        Args:
            bot_name: 봇 이름
            error: 예외 객체
            context: 에러 컨텍스트

        Returns:
            발송 성공 여부
        """
        payload = N8NCallbackPayload(
            event_type="error",
            bot_name=bot_name,
            data={
                "error": str(error),
                "error_type": type(error).__name__,
                "context": context,
            },
        )
        return await self.send_callback(payload)

    async def send_status(
        self,
        bot_name: str,
        status: dict[str, Any],
    ) -> bool:
        """상태 콜백 발송

        Args:
            bot_name: 봇 이름
            status: 상태 정보

        Returns:
            발송 성공 여부
        """
        payload = N8NCallbackPayload(
            event_type="status",
            bot_name=bot_name,
            data=status,
        )
        return await self.send_callback(payload)
