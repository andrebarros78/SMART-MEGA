"""Transactional restoration of temporary terminal epoch global overrides.

Only the caller owns lock acquisition and epoch authority verification. This
helper never changes a rule, selects a draw, or writes external evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, MutableMapping


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
