from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import smart_3054_terminal_executor as _engine

SCHEMA = "SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1"
Fetcher = Callable[[int], tuple[dict[str, Any], dict[str, Any]]]

def probe(root: str | Path, target: int, fetcher: Fetcher | None = None) -> dict[str, Any]:
    if fetcher is None:
        return _engine.probe_active_epoch(root, int(target))
    return _engine.probe_active_epoch(root, int(target), fetcher=fetcher)

def execute(root: str | Path, target: int, fetcher: Fetcher | None = None, *, allow_terminal_write: bool = True) -> dict[str, Any]:
    if fetcher is None:
        return _engine.execute_active_epoch(root, int(target), allow_terminal_write=allow_terminal_write)
    return _engine.execute_active_epoch(root, int(target), fetcher=fetcher, allow_terminal_write=allow_terminal_write)

__all__ = ["SCHEMA", "probe", "execute"]
