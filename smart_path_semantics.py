from __future__ import annotations

from pathlib import Path, PureWindowsPath


def is_windows_absolute(value: str | Path) -> bool:
    try:
        return PureWindowsPath(str(value)).is_absolute()
    except (TypeError, ValueError):
        return False


def is_absolute_any(value: str | Path) -> bool:
    try:
        return Path(value).is_absolute() or is_windows_absolute(value)
    except (TypeError, ValueError):
        return is_windows_absolute(value)


def basename_any(value: str | Path) -> str:
    raw = str(value)
    if is_windows_absolute(raw) or "\\" in raw:
        return PureWindowsPath(raw).name
    return Path(raw).name


def windows_path_under(value: str | Path, parent: str | Path) -> bool:
    try:
        child = PureWindowsPath(str(value))
        root = PureWindowsPath(str(parent))
    except (TypeError, ValueError):
        return False
    if not child.is_absolute() or not root.is_absolute():
        return False
    return child == root or root in child.parents
