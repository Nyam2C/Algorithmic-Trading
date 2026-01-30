"""
공통 API 응답 스키마

모든 API 응답에 사용되는 공통 모델을 정의합니다.
"""
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """표준 API 응답

    Attributes:
        success: 성공 여부
        data: 응답 데이터
        message: 응답 메시지 (선택)
    """

    success: bool = Field(..., description="요청 성공 여부")
    data: Optional[T] = Field(default=None, description="응답 데이터")
    message: Optional[str] = Field(default=None, description="응답 메시지")


class SuccessResponse(BaseModel):
    """성공 응답

    간단한 성공 응답에 사용됩니다.
    """

    success: bool = Field(default=True)
    message: str = Field(default="OK")


class ErrorResponse(BaseModel):
    """에러 응답

    Attributes:
        success: 항상 False
        error: 에러 코드
        message: 에러 메시지
        details: 추가 세부 정보 (선택)
    """

    success: bool = Field(default=False)
    error: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="추가 세부 정보"
    )
