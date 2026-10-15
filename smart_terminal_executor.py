from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from smart_operator_result import fetch as fetch_operator_result

import smart_terminal_engine as _engine

SCHEMA = "SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1"
Fetcher = Callable[[int], tuple[dict[str, Any], dict[str, Any]]]

def probe(root: str | Path, target: int, fetcher: Fetcher | None = None) -> dict[str, Any]:
    if fetcher is None:
        fetcher = lambda selected: fetch_operator_result(root, selected)
    return _engine.probe_active_epoch(root, int(target), fetcher=fetcher)

def execute(root: str | Path, target: int, fetcher: Fetcher | None = None, *, allow_terminal_write: bool = True) -> dict[str, Any]:
    if fetcher is None:
        fetcher = lambda selected: fetch_operator_result(root, selected)
    return _engine.execute_active_epoch(root, int(target), fetcher=fetcher, allow_terminal_write=allow_terminal_write)

def complete_adjudicated_sequence(root: str | Path, target: int) -> dict[str, Any]:
    """Finish post-result learning for an already adjudicated active epoch."""
    root = Path(root).resolve()
    target = int(target)
    with _engine.active_epoch_context(root, target):
        binding = _engine._runtime_binding(root)
        if binding.get("mode") != "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY":
            raise ValueError("sequence completion requires an adjudicated active epoch")
        learned = _engine._ensure_learned_state(root, binding=binding)
        sequence = _engine._ensure_learning_and_sequence(root, binding=binding)
        return {
            "target_contest": target,
            "learned_state_last_contest": int(learned["last_contest"]),
            "sequence": sequence,
        }


__all__ = ["SCHEMA", "probe", "execute", "complete_adjudicated_sequence"]
