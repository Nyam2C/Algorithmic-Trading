"""
Discord 권한 시스템

Discord 봇 명령어에 권한 레벨을 적용합니다.

권한 레벨:
- VIEWER (1): 조회 명령어 (상태, 포지션, 통계 등)
- TRADER (2): 조회 + 일시정지/재개 명령어
- ADMIN (3): 전체 제어 (긴급청산, 봇 시작/정지 등)

환경변수:
- DISCORD_ADMIN_USER_IDS: 관리자 사용자 ID (쉼표 구분)
- DISCORD_ADMIN_ROLE_IDS: 관리자 역할 ID (쉼표 구분)
- DISCORD_TRADER_ROLE_IDS: 트레이더 역할 ID (쉼표 구분)
"""
import os
from dataclasses import dataclass, field
from enum import IntEnum
from functools import wraps
from typing import Any, Callable, List, Optional, TypeVar

import discord
from loguru import logger


# =============================================================================
# 권한 레벨 정의
# =============================================================================


class PermissionLevel(IntEnum):
    """Discord 명령어 권한 레벨

    숫자가 높을수록 더 높은 권한을 나타냅니다.
    """

    VIEWER = 1  # 조회만 가능
    TRADER = 2  # 조회 + 일시정지/재개
    ADMIN = 3  # 전체 제어


# =============================================================================
# 권한 설정
# =============================================================================


@dataclass
class PermissionConfig:
    """권한 설정

    환경변수에서 읽어온 관리자/트레이더 ID 목록을 저장합니다.

    Attributes:
        admin_user_ids: 관리자 권한을 가진 사용자 ID 목록
        admin_role_ids: 관리자 권한을 가진 역할 ID 목록
        trader_role_ids: 트레이더 권한을 가진 역할 ID 목록
    """

    admin_user_ids: List[int] = field(default_factory=list)
    admin_role_ids: List[int] = field(default_factory=list)
    trader_role_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "PermissionConfig":
        """환경변수에서 권한 설정을 읽어옵니다.

        환경변수:
            DISCORD_ADMIN_USER_IDS: 관리자 사용자 ID (쉼표 구분)
            DISCORD_ADMIN_ROLE_IDS: 관리자 역할 ID (쉼표 구분)
            DISCORD_TRADER_ROLE_IDS: 트레이더 역할 ID (쉼표 구분)

        Returns:
            PermissionConfig 인스턴스
        """
        return cls(
            admin_user_ids=_parse_id_list(os.getenv("DISCORD_ADMIN_USER_IDS", "")),
            admin_role_ids=_parse_id_list(os.getenv("DISCORD_ADMIN_ROLE_IDS", "")),
            trader_role_ids=_parse_id_list(os.getenv("DISCORD_TRADER_ROLE_IDS", "")),
        )


# 전역 설정 인스턴스 (싱글톤 패턴)
_global_config: Optional[PermissionConfig] = None


def get_permission_config() -> PermissionConfig:
    """전역 권한 설정을 반환합니다.

    처음 호출 시 환경변수에서 설정을 로드하고, 이후 호출에서는 캐시된 값을 반환합니다.

    Returns:
        PermissionConfig 인스턴스
    """
    global _global_config
    if _global_config is None:
        _global_config = PermissionConfig.from_env()
        logger.info(
            f"권한 설정 로드: admin_users={len(_global_config.admin_user_ids)}, "
            f"admin_roles={len(_global_config.admin_role_ids)}, "
            f"trader_roles={len(_global_config.trader_role_ids)}"
        )
    return _global_config


def reset_permission_config() -> None:
    """전역 권한 설정을 초기화합니다. (테스트용)"""
    global _global_config
    _global_config = None


# =============================================================================
# 권한 체크 함수
# =============================================================================


def check_permission(
    interaction: discord.Interaction,
    required_level: PermissionLevel,
    config: Optional[PermissionConfig] = None,
) -> bool:
    """사용자의 권한을 확인합니다.

    권한 체크 순서:
    1. 사용자 ID가 admin_user_ids에 있으면 ADMIN 권한 부여
    2. 사용자 역할 중 admin_role_ids에 있으면 ADMIN 권한 부여
    3. 사용자 역할 중 trader_role_ids에 있으면 TRADER 권한 부여
    4. 그 외 모든 사용자는 VIEWER 권한 보유

    Args:
        interaction: Discord 상호작용 객체
        required_level: 필요한 권한 레벨
        config: 권한 설정 (None이면 전역 설정 사용)

    Returns:
        권한이 있으면 True, 없으면 False
    """
    if config is None:
        config = get_permission_config()

    user_id = interaction.user.id
    # Member는 roles 속성이 있고, User는 없음 (DM에서 호출 시)
    roles = getattr(interaction.user, "roles", [])
    user_level = _get_user_permission_level(user_id, roles, config)

    return user_level >= required_level


def _get_user_permission_level(
    user_id: int,
    roles: List[Any],
    config: PermissionConfig,
) -> PermissionLevel:
    """사용자의 권한 레벨을 계산합니다.

    Args:
        user_id: 사용자 ID
        roles: 사용자의 역할 목록
        config: 권한 설정

    Returns:
        사용자의 권한 레벨
    """
    # 1. ADMIN 사용자 ID 체크
    if user_id in config.admin_user_ids:
        return PermissionLevel.ADMIN

    # 2. 역할 ID 추출
    role_ids = {r.id for r in roles}

    # 3. ADMIN 역할 체크
    if role_ids & set(config.admin_role_ids):
        return PermissionLevel.ADMIN

    # 4. TRADER 역할 체크
    if role_ids & set(config.trader_role_ids):
        return PermissionLevel.TRADER

    # 5. 기본: VIEWER
    return PermissionLevel.VIEWER


# =============================================================================
# 권한 데코레이터
# =============================================================================

# 타입 힌트용 변수
F = TypeVar("F", bound=Callable[..., Any])


def requires_permission(
    level: PermissionLevel,
    config: Optional[PermissionConfig] = None,
) -> Callable[[F], F]:
    """명령어에 권한 체크를 추가하는 데코레이터

    권한이 없으면 권한 부족 메시지를 전송하고 함수를 실행하지 않습니다.

    Args:
        level: 필요한 권한 레벨
        config: 권한 설정 (None이면 전역 설정 사용)

    Returns:
        데코레이터 함수

    Example:
        @requires_permission(PermissionLevel.ADMIN)
        async def admin_command(interaction):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
            if not check_permission(interaction, level, config):
                level_name = level.name
                logger.warning(
                    f"권한 부족: {interaction.user} (ID: {interaction.user.id}) "
                    f"- 필요 권한: {level_name}"
                )
                await interaction.response.send_message(
                    f"🚫 권한이 없습니다. 이 명령어는 **{level_name}** 이상의 권한이 필요합니다.",
                    ephemeral=True,
                )
                return None
            return await func(interaction, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# 유틸리티 함수
# =============================================================================


def _parse_id_list(value: str) -> List[int]:
    """쉼표로 구분된 ID 문자열을 정수 리스트로 변환합니다.

    Args:
        value: 쉼표로 구분된 ID 문자열 (예: "123,456,789")

    Returns:
        정수 ID 리스트
    """
    if not value or not value.strip():
        return []

    result = []
    for part in value.split(","):
        part = part.strip()
        if part:
            try:
                result.append(int(part))
            except ValueError:
                logger.warning(f"잘못된 ID 값 무시: {part}")
    return result


def get_permission_level_name(level: PermissionLevel) -> str:
    """권한 레벨의 한글 이름을 반환합니다.

    Args:
        level: 권한 레벨

    Returns:
        한글 권한 이름
    """
    names = {
        PermissionLevel.VIEWER: "조회자",
        PermissionLevel.TRADER: "트레이더",
        PermissionLevel.ADMIN: "관리자",
    }
    return names.get(level, "알 수 없음")
