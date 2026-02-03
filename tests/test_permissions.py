"""
Discord 권한 시스템 테스트

권한 체크 로직, 데코레이터, 환경변수 파싱을 테스트합니다.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.discord_bot.permissions import (
    PermissionLevel,
    PermissionConfig,
    check_permission,
    requires_permission,
)


# =============================================================================
# PermissionLevel 테스트
# =============================================================================


class TestPermissionLevel:
    """PermissionLevel 열거형 테스트"""

    def test_viewer_is_lowest(self):
        """VIEWER가 가장 낮은 권한 레벨"""
        assert PermissionLevel.VIEWER == 1
        assert PermissionLevel.VIEWER < PermissionLevel.TRADER
        assert PermissionLevel.VIEWER < PermissionLevel.ADMIN

    def test_trader_is_middle(self):
        """TRADER가 중간 권한 레벨"""
        assert PermissionLevel.TRADER == 2
        assert PermissionLevel.TRADER > PermissionLevel.VIEWER
        assert PermissionLevel.TRADER < PermissionLevel.ADMIN

    def test_admin_is_highest(self):
        """ADMIN이 가장 높은 권한 레벨"""
        assert PermissionLevel.ADMIN == 3
        assert PermissionLevel.ADMIN > PermissionLevel.VIEWER
        assert PermissionLevel.ADMIN > PermissionLevel.TRADER


# =============================================================================
# PermissionConfig 테스트
# =============================================================================


class TestPermissionConfig:
    """PermissionConfig 클래스 테스트"""

    def test_from_env_with_all_values(self):
        """모든 환경변수가 있을 때 올바르게 파싱"""
        with patch.dict(
            os.environ,
            {
                "DISCORD_ADMIN_USER_IDS": "123,456",
                "DISCORD_ADMIN_ROLE_IDS": "111,222",
                "DISCORD_TRADER_ROLE_IDS": "333,444",
            },
        ):
            config = PermissionConfig.from_env()

            assert config.admin_user_ids == [123, 456]
            assert config.admin_role_ids == [111, 222]
            assert config.trader_role_ids == [333, 444]

    def test_from_env_with_empty_values(self):
        """환경변수가 없을 때 빈 리스트 반환"""
        with patch.dict(os.environ, {}, clear=True):
            # 기존 환경변수 제거
            env = os.environ.copy()
            for key in [
                "DISCORD_ADMIN_USER_IDS",
                "DISCORD_ADMIN_ROLE_IDS",
                "DISCORD_TRADER_ROLE_IDS",
            ]:
                env.pop(key, None)

            with patch.dict(os.environ, env, clear=True):
                config = PermissionConfig.from_env()

                assert config.admin_user_ids == []
                assert config.admin_role_ids == []
                assert config.trader_role_ids == []

    def test_from_env_with_whitespace(self):
        """공백이 포함된 환경변수 처리"""
        with patch.dict(
            os.environ,
            {
                "DISCORD_ADMIN_USER_IDS": " 123 , 456 ",
                "DISCORD_ADMIN_ROLE_IDS": "",
                "DISCORD_TRADER_ROLE_IDS": "333",
            },
        ):
            config = PermissionConfig.from_env()

            assert config.admin_user_ids == [123, 456]
            assert config.admin_role_ids == []
            assert config.trader_role_ids == [333]

    def test_from_env_with_single_value(self):
        """단일 값만 있을 때"""
        with patch.dict(
            os.environ,
            {
                "DISCORD_ADMIN_USER_IDS": "123456789",
                "DISCORD_ADMIN_ROLE_IDS": "",
                "DISCORD_TRADER_ROLE_IDS": "",
            },
        ):
            config = PermissionConfig.from_env()

            assert config.admin_user_ids == [123456789]

    def test_default_config(self):
        """기본 설정"""
        config = PermissionConfig()

        assert config.admin_user_ids == []
        assert config.admin_role_ids == []
        assert config.trader_role_ids == []


# =============================================================================
# check_permission 함수 테스트
# =============================================================================


class TestCheckPermission:
    """check_permission 함수 테스트"""

    @pytest.fixture
    def mock_interaction(self):
        """mock discord.Interaction 생성"""
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        interaction.user.roles = []
        return interaction

    @pytest.fixture
    def mock_role(self):
        """mock discord.Role 생성"""

        def _create_role(role_id: int):
            role = MagicMock()
            role.id = role_id
            return role

        return _create_role

    def test_admin_user_has_all_permissions(self, mock_interaction):
        """ADMIN 사용자는 모든 권한 보유"""
        mock_interaction.user.id = 123

        config = PermissionConfig(admin_user_ids=[123])

        # VIEWER 권한 확인
        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config) is True
        # TRADER 권한 확인
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config) is True
        # ADMIN 권한 확인
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is True

    def test_admin_role_has_all_permissions(self, mock_interaction, mock_role):
        """ADMIN 역할은 모든 권한 보유"""
        mock_interaction.user.roles = [mock_role(111)]

        config = PermissionConfig(admin_role_ids=[111])

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config) is True
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config) is True
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is True

    def test_trader_role_has_trader_and_viewer(self, mock_interaction, mock_role):
        """TRADER 역할은 TRADER와 VIEWER 권한 보유"""
        mock_interaction.user.roles = [mock_role(333)]

        config = PermissionConfig(trader_role_ids=[333])

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config) is True
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config) is True
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is False

    def test_no_role_has_viewer_only(self, mock_interaction):
        """역할이 없으면 VIEWER 권한만 보유"""
        config = PermissionConfig(
            admin_user_ids=[123],
            admin_role_ids=[111],
            trader_role_ids=[333],
        )

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config) is True
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config) is False
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is False

    def test_multiple_roles_highest_wins(self, mock_interaction, mock_role):
        """여러 역할 중 가장 높은 권한이 적용"""
        mock_interaction.user.roles = [mock_role(333), mock_role(111)]  # trader  # admin

        config = PermissionConfig(
            admin_role_ids=[111],
            trader_role_ids=[333],
        )

        # admin 역할이 있으므로 모든 권한 보유
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is True

    def test_user_id_takes_precedence(self, mock_interaction, mock_role):
        """사용자 ID가 역할보다 우선"""
        mock_interaction.user.id = 123
        mock_interaction.user.roles = []  # 역할 없음

        config = PermissionConfig(admin_user_ids=[123])

        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config) is True


# =============================================================================
# requires_permission 데코레이터 테스트
# =============================================================================


class TestRequiresPermission:
    """requires_permission 데코레이터 테스트"""

    @pytest.fixture
    def mock_interaction(self):
        """mock discord.Interaction 생성"""
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        interaction.user.roles = []
        interaction.response = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_allowed_when_has_permission(self, mock_interaction):
        """권한이 있으면 함수 실행"""
        mock_interaction.user.id = 123

        config = PermissionConfig(admin_user_ids=[123])
        call_count = {"value": 0}

        @requires_permission(PermissionLevel.ADMIN, config)
        async def admin_command(interaction):
            call_count["value"] += 1
            return "success"

        result = await admin_command(mock_interaction)

        assert result == "success"
        assert call_count["value"] == 1

    @pytest.mark.asyncio
    async def test_denied_when_no_permission(self, mock_interaction):
        """권한이 없으면 거부 메시지"""
        config = PermissionConfig(admin_user_ids=[123])  # 다른 사용자

        @requires_permission(PermissionLevel.ADMIN, config)
        async def admin_command(interaction):
            return "success"

        result = await admin_command(mock_interaction)

        assert result is None
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "권한이 없습니다" in call_args[0][0]
        assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_viewer_allowed_for_everyone(self, mock_interaction):
        """VIEWER 권한은 모든 사용자 허용"""
        config = PermissionConfig()  # 빈 설정

        call_count = {"value": 0}

        @requires_permission(PermissionLevel.VIEWER, config)
        async def viewer_command(interaction):
            call_count["value"] += 1
            return "success"

        result = await viewer_command(mock_interaction)

        assert result == "success"
        assert call_count["value"] == 1

    @pytest.mark.asyncio
    async def test_trader_denied_for_viewer(self, mock_interaction):
        """VIEWER는 TRADER 명령어 실행 불가"""
        config = PermissionConfig(trader_role_ids=[333])  # 사용자는 역할 없음

        @requires_permission(PermissionLevel.TRADER, config)
        async def trader_command(interaction):
            return "success"

        result = await trader_command(mock_interaction)

        assert result is None
        mock_interaction.response.send_message.assert_called_once()


# =============================================================================
# 통합 테스트
# =============================================================================


class TestPermissionIntegration:
    """권한 시스템 통합 테스트"""

    @pytest.fixture
    def mock_interaction(self):
        """mock discord.Interaction 생성"""
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.response = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_role(self):
        """mock discord.Role 생성"""

        def _create_role(role_id: int):
            role = MagicMock()
            role.id = role_id
            return role

        return _create_role

    @pytest.mark.asyncio
    async def test_complete_permission_hierarchy(self, mock_interaction, mock_role):
        """전체 권한 계층 테스트"""
        config = PermissionConfig(
            admin_user_ids=[100],
            admin_role_ids=[200],
            trader_role_ids=[300],
        )

        # ADMIN 사용자
        mock_interaction.user.id = 100
        mock_interaction.user.roles = []

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config)
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config)
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config)

        # ADMIN 역할
        mock_interaction.user.id = 999
        mock_interaction.user.roles = [mock_role(200)]

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config)
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config)
        assert check_permission(mock_interaction, PermissionLevel.ADMIN, config)

        # TRADER 역할
        mock_interaction.user.roles = [mock_role(300)]

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config)
        assert check_permission(mock_interaction, PermissionLevel.TRADER, config)
        assert not check_permission(mock_interaction, PermissionLevel.ADMIN, config)

        # 일반 사용자 (VIEWER)
        mock_interaction.user.roles = []

        assert check_permission(mock_interaction, PermissionLevel.VIEWER, config)
        assert not check_permission(mock_interaction, PermissionLevel.TRADER, config)
        assert not check_permission(mock_interaction, PermissionLevel.ADMIN, config)
