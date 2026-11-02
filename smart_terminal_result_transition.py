"""Ordered, resumable handoff from verified official result to adjudication.

The injected ingest/adjudication authorities own validation and persistence.
This coordinator has no rollback, fallback, promotion, or invented evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def apply_official_result_transition(
    root: Path, payload: dict[str, Any], normalized: dict[str, Any],
    binding: dict[str, Any], *, ensure_ingest: Callable,
    ensure_adjudication: Callable,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist/reuse ingestion before adjudication, propagating any failure."""
    ingest = ensure_ingest(root, payload, binding=binding)
    adjudication = ensure_adjudication(root, normalized["numbers"], binding=binding)
    return ingest, adjudication
