"""After-result sequence lineage runner for the frozen terminal target.

Never alters pre-result decisions; preserves learning-then-proof ordering
and verifies the full target lineage before returning any success.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def ensure_learning_and_sequence(
    root: Path, binding: dict[str, Any], *,
    target: int, result_data: str, learning_event: str, proof_event: str,
    load_ledger: Callable, target_events: Callable,
    append_learning_update: Callable, append_sequence_proof: Callable,
    validate_target_sequence: Callable,
) -> dict[str, Any]:
    ledger_path = binding["ledger"]
    learned_path = binding["learned"]
    ledger = load_ledger(ledger_path)
    learning = target_events(ledger, learning_event)
    proofs = target_events(ledger, proof_event)
    if len(learning) > 1 or len(proofs) > 1:
        raise ValueError("duplicate target learning/proof events are forbidden")
    if not learning:
        append_learning_update(ledger_path, target, learned_path, root / result_data)
    ledger = load_ledger(ledger_path)
    proofs = target_events(ledger, proof_event)
    if not proofs:
        append_sequence_proof(ledger_path, target)
    ledger = load_ledger(ledger_path)
    validation = validate_target_sequence(
        ledger, target, require_learning=True, require_proof=True, verify_files=True, root=root
    )
    if validation.get("valid") is not True:
        raise RuntimeError("target sequential proof validation failed")
    return validation