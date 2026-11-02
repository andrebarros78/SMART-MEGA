"""Transactional restoration of temporary terminal epoch global overrides.

Only the caller owns lock acquisition and epoch authority verification. This
helper never changes a rule, selects a draw, or writes external evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, MutableMapping


def authorize_epoch_runtime(
    root: Path, target: int, *,
    verify_active_epoch: Callable, derive_runtime_names: Callable,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the selected epoch before deriving temporary engine globals."""
    active = verify_active_epoch(root / "SMART_ACTIVE_EPOCH.json")
    selected = int(active.get("target_contest", -1))
    if int(target) != selected:
        raise ValueError("requested terminal target differs from active epoch")
    return active, derive_runtime_names(active, selected)


@contextmanager
def scoped_epoch_globals(
    namespace: MutableMapping[str, Any], overrides: Mapping[str, Any],
) -> Iterator[None]:
    """Restore original global bindings even when the scoped consumer fails."""
    names = tuple(overrides)
    saved = {name: namespace[name] for name in names}
    try:
        namespace.update(overrides)
        yield
    finally:
        for name, value in saved.items():
            namespace[name] = value
