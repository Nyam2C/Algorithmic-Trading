"""Discord 명령 권한 메타 테스트 (P1-1).

각 명령 핸들러가 적절한 권한 체크를 가지고 있는지 AST로 정적 검증한다.
control.py / monitoring.py 명령은 closure 안에 정의되어 직접 단위 호출이 어렵기 때문에,
함수 본문에 `check_permission` 호출이 포함되었는지 AST로 확인하는 회귀 가드 역할이다.

이 테스트는 미래에 누군가가 실수로 권한 체크를 제거하면 즉시 감지한다.

배경:
- 코드 헬스 감사 P1-1에서 audit-reporter가 `@requires_permission` 데코레이터 부재만으로
  "RBAC 미작동"을 진단했으나, 실제로는 inline `check_permission()` 패턴이 작동 중이었다.
  본 테스트는 그 inline 패턴이 영구히 유지되도록 보호한다.
"""
import ast
from pathlib import Path

# control.py에서 권한 체크가 필수인 명령들 (자금 영향)
CONTROL_COMMANDS_REQUIRING_CHECK = {
    "control_cmd",  # /제어 (start/stop/pause/resume)
    "emergency_cmd",  # /긴급청산
    "alert_cmd",  # /알림 (TRADER+)
}

# monitoring.py에서 권한 체크가 필수인 명령들 (민감 정보 노출)
MONITORING_COMMANDS_REQUIRING_CHECK = {
    "account_cmd",  # /계정 — 잔고 노출
    "prompt_cmd",  # /프롬프트 — AI 시스템 프롬프트/응답 노출
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_function_calls_in_handler(
    source_path: Path, handler_name: str
) -> list[str]:
    """주어진 파일에서 handler_name 함수의 본문에 등장하는 함수 호출 이름 목록을 반환한다.

    중첩 함수(closure)도 재귀적으로 탐색한다.

    Args:
        source_path: 분석할 .py 파일 경로
        handler_name: 찾을 함수 이름

    Returns:
        함수 본문에서 호출되는 함수 이름 리스트.
        해당 핸들러가 없으면 빈 리스트.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            if node.name == handler_name:
                target = node
                break

    if target is None:
        return []

    calls: list[str] = []
    for node in ast.walk(target):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return calls


class TestControlCommandsHavePermissionCheck:
    """control.py — 자금 영향 명령은 항상 권한 체크가 있어야 한다."""

    def test_control_py_path_exists(self) -> None:
        """control.py 파일이 존재하는지 사전 점검."""
        path = PROJECT_ROOT / "src" / "discord_bot" / "commands" / "control.py"
        assert path.exists(), f"control.py가 없음: {path}"

    def test_all_control_commands_call_check_permission(self) -> None:
        """control.py의 모든 자금 영향 명령은 check_permission을 호출해야 한다."""
        path = PROJECT_ROOT / "src" / "discord_bot" / "commands" / "control.py"
        missing: list[str] = []
        for handler_name in CONTROL_COMMANDS_REQUIRING_CHECK:
            calls = _find_function_calls_in_handler(path, handler_name)
            if "check_permission" not in calls:
                missing.append(handler_name)
        assert not missing, (
            f"control.py 명령에 check_permission 호출 누락: {missing}. "
            f"자금 영향 명령은 반드시 권한 체크가 있어야 한다 (P1 보안)."
        )


class TestMonitoringCommandsHavePermissionCheck:
    """monitoring.py — 민감 정보 노출 명령은 권한 체크가 있어야 한다."""

    def test_monitoring_py_path_exists(self) -> None:
        path = PROJECT_ROOT / "src" / "discord_bot" / "commands" / "monitoring.py"
        assert path.exists(), f"monitoring.py가 없음: {path}"

    def test_sensitive_monitoring_commands_call_check_permission(self) -> None:
        """/계정, /프롬프트는 민감 정보를 노출하므로 권한 체크 필수."""
        path = PROJECT_ROOT / "src" / "discord_bot" / "commands" / "monitoring.py"
        missing: list[str] = []
        for handler_name in MONITORING_COMMANDS_REQUIRING_CHECK:
            calls = _find_function_calls_in_handler(path, handler_name)
            if "check_permission" not in calls:
                missing.append(handler_name)
        assert not missing, (
            f"monitoring.py 민감 명령에 check_permission 호출 누락: {missing}. "
            f"잔고(/계정)와 AI 프롬프트(/프롬프트)는 정보 노출 위험이 있다."
        )

    def test_handler_names_actually_exist(self) -> None:
        """타깃 핸들러 이름이 실제로 monitoring.py에 정의되어 있는지 확인.

        이 테스트는 monitoring.py의 명령 이름이 변경되었는데
        본 테스트의 상수가 갱신되지 않은 경우를 감지한다.
        """
        path = PROJECT_ROOT / "src" / "discord_bot" / "commands" / "monitoring.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        }
        for handler_name in MONITORING_COMMANDS_REQUIRING_CHECK:
            assert handler_name in defined_names, (
                f"{handler_name}이 monitoring.py에 정의되어 있지 않음. "
                f"이름이 변경되었다면 본 테스트의 상수도 함께 갱신 필요."
            )
