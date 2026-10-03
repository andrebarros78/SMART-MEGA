from pathlib import Path

import pytest

import smart_operation_lock as operation_lock
import smart_regression_runner as regression_runner


ROOT = Path(__file__).resolve().parent


def test_no_windows_runtime_dependency_in_active_python_surface() -> None:
    offenders: list[str] = []
    for path in sorted(ROOT.glob("smart_*.py")):
        text = path.read_text(encoding="utf-8-sig").casefold()
        if "import msvcrt" in text or "from msvcrt" in text:
            offenders.append(path.name)
    assert offenders == []
    assert not (ROOT / "smart_python.cmd").exists()


def test_official_github_workflows_are_ubuntu_only() -> None:
    workflow_root = ROOT / ".github" / "workflows"
    offenders: list[tuple[str, str]] = []
    forbidden = ("windows-latest", "runs-on: windows", "pwsh", "powershell")
    for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8-sig").casefold()
        for token in forbidden:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == []


def test_operation_lock_enforces_posix_exclusion(tmp_path: Path) -> None:
    first = operation_lock.OperationLock(tmp_path, operation="first")
    second = operation_lock.OperationLock(tmp_path, operation="second")
    first.acquire()
    try:
        with pytest.raises(operation_lock.OperationalLockError, match="operation lock is held"):
            second.acquire()
    finally:
        first.release()

    acquired = second.acquire()
    try:
        assert acquired["status"] == "ACTIVE"
        assert acquired["recovery"]["os_lock_is_authority"] is True
    finally:
        second.release()


def test_regression_lock_enforces_posix_exclusion(tmp_path: Path) -> None:
    with regression_runner._RegressionLock(tmp_path):
        with pytest.raises(regression_runner._RegressionLockError, match="exclusive lock"):
            with regression_runner._RegressionLock(tmp_path):
                pass
